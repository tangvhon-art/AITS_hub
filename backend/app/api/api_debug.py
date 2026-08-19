"""
接口调试 API
发送调试请求 + 历史记录
"""
import json
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.core.deps import get_current_user, get_project
from app.core.audit import log_audit
from app.models.user import User
from app.models.project import Project
from app.models.api_test import ApiDebugHistory
from app.schemas.api_test import (
    ApiDebugSendRequest, ApiDebugResponse, ApiDebugHistoryResponse,
)
from app.services.http_client import HttpClient
from app.services.variable_engine import VariableEngine
from app.services.script_engine import ScriptEngine

router = APIRouter(prefix="/api/projects/{project_id}/api-debug", tags=["接口测试-调试"])

@router.post("/send", response_model=ApiDebugResponse)
async def send_debug_request(
    project_id: int,
    data: ApiDebugSendRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """发送调试请求"""
    get_project(project_id, db, current_user)

    # 查询环境，获取 base_url 和变量
    from app.models.test_plan import TestEnvironment
    from app.models.test_data_pool import EnvironmentVariableOverride

    base_url = ""
    env_vars_dict = data.environment_vars or {}

    if data.environment_id:
        env = db.query(TestEnvironment).filter(
            TestEnvironment.id == data.environment_id,
            TestEnvironment.project_id == project_id,
        ).first()
        if env:
            base_url = env.base_url or ""
            # 加载环境自身配置的变量（config.variables，支持 dict 和 list 两种格式）
            env_config = env.config or {}
            env_variables = env_config.get("variables", {})
            if isinstance(env_variables, dict):
                for k, v in env_variables.items():
                    if k not in env_vars_dict:
                        env_vars_dict[k] = v
            elif isinstance(env_variables, list):
                for v in env_variables:
                    if isinstance(v, dict) and v.get("key"):
                        if v["key"] not in env_vars_dict:
                            env_vars_dict[v["key"]] = v.get("value", "")
            # 加载环境变量覆盖（优先级更高）
            overrides = db.query(EnvironmentVariableOverride).filter(
                EnvironmentVariableOverride.environment_id == env.id,
            ).all()
            for ov in overrides:
                env_vars_dict[ov.key] = ov.value

    # 变量替换
    var_engine = VariableEngine()
    if env_vars_dict:
        var_engine.load_from_dict("environment", env_vars_dict)

    # 拼接 base_url
    url = var_engine.replace(data.url)
    if base_url and not url.startswith(("http://", "https://")):
        url = base_url.rstrip("/") + "/" + url.lstrip("/")

    headers = var_engine.replace_headers(data.headers)
    params = var_engine.replace_params(data.query_params)
    body_content = var_engine.replace_body(data.body_type, data.body_content)

    # 前置脚本
    script_engine = ScriptEngine()
    console_log = ""
    if data.pre_script:
        script_result = script_engine.execute(
            data.pre_script,
            environment_vars=var_engine.environment_vars,
            global_vars=var_engine.global_vars,
            request={"method": data.method, "url": url},
        )
        for k, v in script_result.variables.items():
            var_engine.set("scenario", k, v)
        console_log += script_result.output
        # 重新替换变量
        url = var_engine.replace(data.url)
        if base_url and not url.startswith(("http://", "https://")):
            url = base_url.rstrip("/") + "/" + url.lstrip("/")
        headers = var_engine.replace_headers(data.headers)
        params = var_engine.replace_params(data.query_params)
        body_content = var_engine.replace_body(data.body_type, data.body_content)

    # 发送请求
    http_client = HttpClient(timeout=data.timeout or 30)
    response = await http_client.asend(
        method=data.method,
        url=url,
        headers=headers,
        params=params,
        body_type=data.body_type,
        body_content=body_content,
    )

    # 后置脚本
    tests = []
    if data.post_script:
        script_result = script_engine.execute(
            data.post_script,
            environment_vars=var_engine.environment_vars,
            global_vars=var_engine.global_vars,
            request={"method": data.method, "url": url},
            response=response.to_dict(),
        )
        console_log += script_result.output
        tests = script_result.tests

    # 保存历史记录
    history = ApiDebugHistory(
        project_id=project_id,
        user_id=current_user.id,
        method=data.method,
        url=url,
        request_config={
            "headers": headers,
            "query_params": params,
            "body_type": data.body_type,
            "body_content": body_content,
        },
        response_status=response.status_code,
        response_time=response.elapsed_ms,
    )
    db.add(history)
    db.commit()

    log_audit(
        db, action="execute", resource_type="project",
        resource_id=project_id, resource_name="接口调试",
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "method": data.method, "url": url, "status": response.status_code},
    )

    return ApiDebugResponse(
        status_code=response.status_code,
        response_time=response.elapsed_ms,
        response_size=response.size,
        response_headers=response.headers,
        response_body=response.body,
        error=response.error,
        console_log=console_log,
        tests=tests,
    )

@router.get("/history", response_model=List[ApiDebugHistoryResponse])
def list_debug_history(
    project_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """调试历史列表"""
    get_project(project_id, db, current_user)
    history = db.query(ApiDebugHistory).filter(
        ApiDebugHistory.project_id == project_id,
        ApiDebugHistory.user_id == current_user.id,
    ).order_by(ApiDebugHistory.id.desc()).limit(limit).all()
    return history

@router.delete("/history", status_code=status.HTTP_204_NO_CONTENT)
def clear_debug_history(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """清除调试历史"""
    get_project(project_id, db, current_user)
    db.query(ApiDebugHistory).filter(
        ApiDebugHistory.project_id == project_id,
        ApiDebugHistory.user_id == current_user.id,
    ).update({ApiDebugHistory.is_deleted: True}, synchronize_session=False)

    log_audit(
        db, action="delete", resource_type="project",
        resource_id=project_id, resource_name="调试历史",
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "type": "api_debug_history"},
    )
    db.commit()
