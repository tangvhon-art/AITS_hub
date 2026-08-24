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
    var_engine = VariableEngine()

    if data.environment_id:
        env = db.query(TestEnvironment).filter(
            TestEnvironment.id == data.environment_id,
            TestEnvironment.project_id == project_id,
        ).first()
        if env:
            base_url = env.base_url or ""
            # 加载环境配置（静态变量 + 脚本变量存储）
            var_engine.load_environment(env.config or {})
            # 前端传入的变量覆盖环境配置
            if data.environment_vars:
                for k, v in data.environment_vars.items():
                    var_engine.set("environment", k, v)
            # 加载环境变量覆盖（优先级最高）
            overrides = db.query(EnvironmentVariableOverride).filter(
                EnvironmentVariableOverride.environment_id == env.id,
            ).all()
            for ov in overrides:
                var_engine.set("environment", ov.key, ov.value)
    elif data.environment_vars:
        var_engine.load_from_dict("environment", data.environment_vars)

    # 计算原始 URL（变量替换前）
    raw_url = data.url
    if base_url and not raw_url.startswith(("http://", "https://")):
        raw_url = base_url.rstrip("/") + "/" + raw_url.lstrip("/")

    # 第一遍：替换静态环境变量（如 {{xp_authorization}}）
    resolved_url = var_engine.replace(raw_url)
    resolved_headers = var_engine.replace_headers(data.headers)
    resolved_params = var_engine.replace_params(data.query_params)
    resolved_body = var_engine.replace_body(data.body_type, data.body_content)

    # 执行环境脚本变量（用已解析的 body/headers，保证签名与实际请求一致）
    console_log = var_engine.run_environment_scripts({
        "method": data.method,
        "url": resolved_url,
        "headers": resolved_headers,
        "query_params": resolved_params,
        "body": HttpClient.serialize_body(data.body_type, resolved_body),
        "body_type": data.body_type or "raw",
    })

    # 前置脚本（也用已解析的上下文）
    script_engine = ScriptEngine()
    if data.pre_script:
        script_result = script_engine.execute(
            data.pre_script,
            environment_vars=var_engine.environment_vars,
            global_vars=var_engine.global_vars,
            request={
                "method": data.method,
                "url": resolved_url,
                "headers": resolved_headers,
                "query_params": resolved_params,
                "body": HttpClient.serialize_body(data.body_type, resolved_body),
                "body_type": data.body_type or "raw",
            },
        )
        for k, v in script_result.variables.items():
            var_engine.set("scenario", k, v)
        # 前置脚本对 pm.request.headers 的修改同样纳入补丁
        if script_result.request_headers:
            var_engine.collect_header_patches(script_result.request_headers, resolved_headers)
        console_log += script_result.output

    # 第二遍：从原始数据重新替换所有变量（静态 + 脚本生成的），
    # 不使用第一遍的结果，确保 {{signature}} 等占位符始终是未解析状态
    import logging as _log
    _logger = _log.getLogger(__name__)
    _orig_sig_headers = [h.get('value') for h in (data.headers or []) if h.get('key') == 'XP-Signature']
    _logger.info(f"[DEBUG] Original XP-Signature header value: {_orig_sig_headers}")
    _logger.info(f"[DEBUG] env_vars keys before 2nd pass: {list(var_engine.environment_vars.keys())}")
    _logger.info(f"[DEBUG] signature in env_vars: {var_engine.get('signature')}")
    url = var_engine.replace(raw_url)
    headers = var_engine.replace_headers(data.headers)
    params = var_engine.replace_params(data.query_params)
    body_content = var_engine.replace_body(data.body_type, data.body_content)
    # 合并环境/前置脚本注入的请求头（如签名头，同名覆盖占位符）
    if var_engine.script_header_patches:
        headers = var_engine.apply_header_patches(headers)
    _sig_val = [h.get('value') for h in (headers or []) if h.get('key') == 'XP-Signature']
    _logger.info(f"[DEBUG] XP-Signature after 2nd pass: {_sig_val}")

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
            request={
                "method": data.method,
                "url": url,
                "headers": data.headers or [],
                "query_params": data.query_params or [],
                "body": HttpClient.serialize_body(data.body_type, body_content),
                "body_type": data.body_type or "raw",
            },
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
