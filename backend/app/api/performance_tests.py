import logging
from typing import Optional
from fastapi import APIRouter, Body, Depends, Query, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db, SessionLocal
from app.core.deps import get_current_user, get_project
from app.core.audit import log_audit
from app.core.timezone import china_now_naive
from app.models.user import User
from app.models.performance_test import PerformanceTest, PerformanceTestRun
from app.schemas.performance_test import (
    PerformanceTestCreate, PerformanceTestUpdate, PerformanceTestResponse,
    PerformanceTestRunResponse, PaginatedResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/projects/{project_id}/performance-tests",
    tags=["性能测试"],
)

run_router = APIRouter(
    prefix="/api/performance-test-runs",
    tags=["性能测试"],
)


@router.post("", response_model=PerformanceTestResponse)
def create_test(
    project_id: int,
    data: PerformanceTestCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    test = PerformanceTest(
        project_id=project_id,
        name=data.name,
        description=data.description,
        target_type=data.target_type,
        target_id=data.target_id,
        target_url=data.target_url,
        targets=data.targets,
        users=data.users,
        spawn_rate=data.spawn_rate,
        duration=data.duration,
        headers=data.headers,
        body_template=data.body_template,
        variable_config=data.variable_config,
        data_pool_id=data.data_pool_id,
        environment_id=data.environment_id,
        created_by=current_user.id,
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    return PerformanceTestResponse.model_validate(test)


@router.post("/search", response_model=PaginatedResponse)
def list_tests(
    project_id: int,
    keyword: Optional[str] = Body(None),
    status: Optional[str] = Body(None),
    page: int = Body(1),
    page_size: int = Body(20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    query = db.query(PerformanceTest).filter(PerformanceTest.project_id == project_id)
    if keyword:
        query = query.filter(PerformanceTest.name.contains(keyword))
    if status:
        query = query.filter(PerformanceTest.status == status)
    total = query.count()
    items = query.order_by(PerformanceTest.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[PerformanceTestResponse.model_validate(t) for t in items],
    )


@router.get("/{test_id}", response_model=PerformanceTestResponse)
def get_test(
    project_id: int,
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    test = db.query(PerformanceTest).filter(
        PerformanceTest.id == test_id,
        PerformanceTest.project_id == project_id,
    ).first()
    if not test:
        raise HTTPException(status_code=404, detail="性能测试不存在")
    return PerformanceTestResponse.model_validate(test)


@router.put("/{test_id}", response_model=PerformanceTestResponse)
def update_test(
    project_id: int,
    test_id: int,
    data: PerformanceTestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    test = db.query(PerformanceTest).filter(
        PerformanceTest.id == test_id,
        PerformanceTest.project_id == project_id,
    ).first()
    if not test:
        raise HTTPException(status_code=404, detail="性能测试不存在")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(test, key, value)
    test.updated_at = china_now_naive()
    db.commit()
    db.refresh(test)
    return PerformanceTestResponse.model_validate(test)


@router.delete("/{test_id}")
def delete_test(
    project_id: int,
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    test = db.query(PerformanceTest).filter(
        PerformanceTest.id == test_id,
        PerformanceTest.project_id == project_id,
    ).first()
    if not test:
        raise HTTPException(status_code=404, detail="性能测试不存在")
    test.soft_delete()
    db.commit()
    return {"detail": "删除成功"}


@router.post("/{test_id}/run")
def run_test(
    project_id: int,
    test_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    test = db.query(PerformanceTest).filter(
        PerformanceTest.id == test_id,
        PerformanceTest.project_id == project_id,
    ).first()
    if not test:
        raise HTTPException(status_code=404, detail="性能测试不存在")

    from app.services.performance_runner import PerformanceRunner
    from app.services.variable_engine import VariableEngine
    from app.services.http_client import HttpClient
    runner = PerformanceRunner(db)

    # 构建多接口 targets 列表
    targets = []
    env = None
    if test.environment_id:
        from app.models.test_plan import TestEnvironment
        env = db.query(TestEnvironment).filter(TestEnvironment.id == test.environment_id).first()
    base_url = env.base_url if env else ""

    if test.targets and len(test.targets) > 0:
        # 多接口模式
        for t in test.targets:
            target_info = {}
            if t.get("target_id"):
                target_info = runner.get_target_info(t.get("target_type", "api_definition"), t["target_id"])
            url = t.get("url") or f"{base_url}{target_info.get('path', '/')}"
            targets.append({
                "method": t.get("method") or target_info.get("method", "GET"),
                "url": url,
                "name": t.get("name") or target_info.get("name", "接口"),
                "weight": t.get("weight", 1),
                "body": t.get("body") or target_info.get("body"),
                "headers": target_info.get("headers"),
            })
    else:
        # 单接口兼容模式
        target_info = runner.get_target_info(test.target_type, test.target_id)
        if not target_info and not test.target_url:
            raise HTTPException(status_code=400, detail="无法获取目标接口信息，请设置 target_url 或 targets")
        target_url = test.target_url or f"{base_url}{target_info.get('path', '/')}"
        targets.append({
            "method": target_info.get("method", "GET"),
            "url": target_url,
            "name": target_info.get("name", "接口"),
            "weight": 1,
            "body": test.body_template or target_info.get("body"),
            "headers": target_info.get("headers"),
        })

    headers = {**(test.headers or {})}
    # 合并第一个 target 的 headers
    if targets and targets[0].get("headers"):
        headers = {**headers, **targets[0]["headers"]}

    # 加载环境变量 + 执行环境脚本（如签名生成）
    var_engine = VariableEngine()
    if env:
        var_engine.load_environment(env.config or {})

    # 将 headers 转为列表格式供变量替换使用
    header_list = [{"key": k, "value": v, "enabled": True} for k, v in headers.items()]

    # 第一遍：替换静态环境变量
    resolved_header_list = var_engine.replace_headers(header_list)
    resolved_targets = []
    for t in targets:
        resolved_body = var_engine.replace(t.get("body") or "") if t.get("body") else None
        resolved_targets.append({**t, "body": resolved_body})

    # 用第一个 target 的请求上下文执行环境脚本
    if targets:
        first = resolved_targets[0]
        serialized_body = first.get("body") or ""
        # 如果 body 是 JSON 字符串，用 serialize_body 统一格式
        if serialized_body:
            try:
                serialized_body = HttpClient.serialize_body("json", serialized_body)
            except Exception:
                pass
        var_engine.run_environment_scripts({
            "method": first.get("method", "GET"),
            "url": first.get("url", ""),
            "headers": resolved_header_list,
            "query_params": [],
            "body": serialized_body,
            "body_type": "json",
        })

    # 第二遍：替换脚本生成的变量（如 {{signature}}）
    final_header_list = var_engine.replace_headers(header_list)
    headers = {h["key"]: h["value"] for h in final_header_list if h.get("value") is not None}
    for t in resolved_targets:
        if t.get("body"):
            t["body"] = var_engine.replace(t["body"])
    targets = resolved_targets

    test_data = None
    if test.data_pool_id:
        from app.services.data_factory import DataFactory
        factory = DataFactory()
        test_data = factory.generate_from_pool(db, test.data_pool_id, count=test.users * 2)

    config_snapshot = {
        "users": test.users,
        "spawn_rate": test.spawn_rate,
        "duration": test.duration,
        "targets": targets,
    }

    run = PerformanceTestRun(
        test_id=test.id,
        project_id=project_id,
        config_snapshot=config_snapshot,
        status="pending",
        triggered_by=current_user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    test.status = "running"
    db.commit()

    log_audit(
        db, action="run", resource_type="performance_test",
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"test_id": test.id, "run_id": run.id},
    )
    db.commit()

    from app.tasks.performance_tasks import run_performance_test_task
    run_performance_test_task.delay(
        run_id=run.id,
        test_config=config_snapshot,
        targets=targets,
        headers=headers,
        test_data=test_data,
    )

    return {"run_id": run.id, "status": "pending", "detail": "性能测试已启动"}


@router.post("/{test_id}/stop")
def stop_test(
    project_id: int,
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    test = db.query(PerformanceTest).filter(
        PerformanceTest.id == test_id,
        PerformanceTest.project_id == project_id,
    ).first()
    if not test:
        raise HTTPException(status_code=404, detail="性能测试不存在")

    run = db.query(PerformanceTestRun).filter(
        PerformanceTestRun.test_id == test_id,
        PerformanceTestRun.status == "running",
    ).first()

    if run:
        from app.services.performance_runner import PerformanceRunner
        runner = PerformanceRunner(db)
        runner.stop(run.id)

    test.status = "stopped"
    db.commit()
    return {"detail": "已停止"}


@router.get("/{test_id}/runs", response_model=PaginatedResponse)
def list_runs(
    project_id: int,
    test_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    query = db.query(PerformanceTestRun).filter(
        PerformanceTestRun.test_id == test_id,
        PerformanceTestRun.project_id == project_id,
    )
    total = query.count()
    items = query.order_by(PerformanceTestRun.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[PerformanceTestRunResponse.model_validate(r) for r in items],
    )


@run_router.get("/{run_id}", response_model=PerformanceTestRunResponse)
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = db.query(PerformanceTestRun).filter(PerformanceTestRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    return PerformanceTestRunResponse.model_validate(run)


@router.get("/convert/preview")
def convert_preview(
    project_id: int,
    target_type: str = Query(...),
    target_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    from app.services.performance_runner import PerformanceRunner
    runner = PerformanceRunner(db)
    info = runner.get_target_info(target_type, target_id)
    if not info:
        raise HTTPException(status_code=404, detail="目标不存在")
    return {
        "target_type": target_type,
        "target_id": target_id,
        "method": info.get("method"),
        "path": info.get("path"),
        "name": info.get("name"),
        "suggested_name": f"性能测试 - {info.get('name', '')}",
    }


# ==================== 性能测试 AI 分析 ====================

class PerformanceAnalyzeRequest(BaseModel):
    llm_config_id: Optional[int] = None
    prompt_id: Optional[int] = None


@run_router.post("/{run_id}/analyze")
def analyze_performance(
    run_id: int,
    data: PerformanceAnalyzeRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """对性能测试执行结果进行 AI 分析，异步生成性能报告"""
    run = db.query(PerformanceTestRun).filter(PerformanceTestRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    if run.status != "completed":
        raise HTTPException(status_code=400, detail=f"执行记录状态为 {run.status}，仅 completed 状态可分析")

    from app.tasks.performance_tasks import analyze_performance_task
    analyze_performance_task.delay(
        run_id=run_id,
        user_id=current_user.id,
        llm_config_id=data.llm_config_id,
        prompt_id=data.prompt_id,
    )

    log_audit(
        db, action="analyze", resource_type="performance_run",
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"run_id": run_id},
    )
    db.commit()

    return {"run_id": run_id, "status": "processing", "detail": "性能分析已启动，完成后将生成性能报告"}
