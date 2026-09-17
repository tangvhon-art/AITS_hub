"""
测试用例集 API

提供用例集 CRUD、用例集-用例关联管理、XMind 导图树数据与按用例集导出能力。
"""
import io
import json
import logging
import uuid
import zipfile
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from urllib.parse import quote

from app.database import get_db
from app.core.audit import log_audit
from app.core.deps import get_current_user, get_project
from app.core.timezone import china_now_naive
from app.models.user import User
from app.models.test_case import TestCase
from app.models.requirement import TestRequirement, RequirementFeature
from app.models.case_suite import TestCaseSuite, TestCaseSuiteCase, CaseSuiteCaseExecStatus
from app.schemas.case_suite import (
    CaseSuiteCreate,
    CaseSuiteUpdate,
    CaseSuiteCasesBody,
    CaseSuiteResponse,
    CaseSuiteListResponse,
    CaseExecStatusUpdate,
)
from app.api.import_export import _make_xmind_topic

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_id}/case-suites", tags=["测试用例集"])


# ── 工具函数 ───────────────────────────────────────────


def _get_suite(project_id: int, suite_id: int, db: Session) -> TestCaseSuite:
    suite = db.query(TestCaseSuite).filter(
        TestCaseSuite.id == suite_id,
        TestCaseSuite.project_id == project_id,
        TestCaseSuite.is_deleted == False,
    ).first()
    if not suite:
        raise HTTPException(status_code=404, detail="用例集不存在")
    return suite


def _suite_stats(db: Session, project_id: int, suite_id: int) -> Dict[str, int]:
    """统计用例集关联用例数与模块覆盖数"""
    case_count = db.query(func.count(TestCaseSuiteCase.id)).filter(
        TestCaseSuiteCase.suite_id == suite_id,
        TestCaseSuiteCase.case_id.in_(
            db.query(TestCase.id).filter(
                TestCase.project_id == project_id,
                TestCase.is_deleted == False,
            )
        ),
    ).scalar() or 0

    module_count = (
        db.query(func.count(func.distinct(TestCase.module)))
        .join(TestCaseSuiteCase, TestCaseSuiteCase.case_id == TestCase.id)
        .filter(
            TestCaseSuiteCase.suite_id == suite_id,
            TestCase.project_id == project_id,
            TestCase.is_deleted == False,
            TestCase.module != "",
        )
        .scalar()
        or 0
    )
    return {"case_count": case_count, "module_count": module_count}


def _suite_cases(db: Session, project_id: int, suite_id: int) -> List[TestCase]:
    """获取用例集内的全部有效用例（按模块、优先级排序）"""
    return (
        db.query(TestCase)
        .join(TestCaseSuiteCase, TestCaseSuiteCase.case_id == TestCase.id)
        .filter(
            TestCaseSuiteCase.suite_id == suite_id,
            TestCase.project_id == project_id,
            TestCase.is_deleted == False,
        )
        .order_by(TestCase.module, TestCase.priority, TestCase.id)
        .all()
    )


def _steps_text(steps_raw: Optional[str]) -> str:
    """将测试步骤 JSON 转为编号列表文本（需求文档格式：1. …；2. …）"""
    if not steps_raw:
        return ""
    try:
        steps_list = json.loads(steps_raw)
    except (json.JSONDecodeError, TypeError):
        return steps_raw or ""
    if not isinstance(steps_list, list):
        return steps_raw or ""
    parts = []
    for i, step in enumerate(steps_list):
        if isinstance(step, dict):
            action = step.get("action", "")
            expected = step.get("expected", "")
            text = action if action else (expected if expected else "")
            if expected and expected != action:
                text = f"{action}，预期结果：{expected}" if action else f"预期结果：{expected}"
        elif isinstance(step, str):
            text = step
        else:
            text = str(step)
        if text:
            parts.append(f"{i + 1}. {text}")
    return "；".join(parts)


def _build_mind_data(db: Session, project_id: int, suite: TestCaseSuite) -> Dict:
    """构建导图树数据：根=用例集名 → 模块 → 用例 → 前置条件/步骤/预期结果"""
    cases = _suite_cases(db, project_id, suite.id)

    # 用例集内用例的执行状态：无记录默认为待执行（pending）
    exec_map: Dict[int, str] = {}
    if cases:
        exec_rows = (
            db.query(CaseSuiteCaseExecStatus)
            .filter(CaseSuiteCaseExecStatus.suite_id == suite.id)
            .all()
        )
        exec_map = {row.case_id: row.exec_status for row in exec_rows}

    # 需求回显：优先取用例直接关联的需求（req_id），缺失时按模块反查功能点模块名
    req_title_map: Dict[int, str] = {}
    req_ids = {c.req_id for c in cases if c.req_id}
    if req_ids:
        req_title_map = {
            rid: title
            for rid, title in db.query(TestRequirement.id, TestRequirement.title)
            .filter(TestRequirement.id.in_(req_ids), TestRequirement.is_deleted == False)
            .all()
        }
    module_req_map: Dict[str, int] = {}
    no_req_modules = {c.module for c in cases if not c.req_id and c.module}
    if no_req_modules:
        for mname, rid in (
            db.query(RequirementFeature.module_name, RequirementFeature.requirement_id)
            .filter(
                RequirementFeature.module_name.in_(no_req_modules),
                RequirementFeature.project_id == project_id,
                RequirementFeature.is_deleted == False,
            )
            .all()
        ):
            module_req_map.setdefault(mname, rid)
        extra_ids = set(module_req_map.values()) - set(req_title_map)
        if extra_ids:
            req_title_map.update({
                rid: title
                for rid, title in db.query(TestRequirement.id, TestRequirement.title)
                .filter(TestRequirement.id.in_(extra_ids), TestRequirement.is_deleted == False)
                .all()
            })

    # 按模块分组（未分类归为「未分类模块」）
    modules: Dict[str, List[TestCase]] = {}
    for case in cases:
        module_name = case.module or "未分类模块"
        modules.setdefault(module_name, []).append(case)

    # 用例排序：优先级 P0→P3，再按 id
    PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

    module_nodes = []
    for module_name, module_cases in modules.items():
        module_cases.sort(key=lambda c: (PRIORITY_ORDER.get(c.priority, 9), c.id))
        case_nodes = []
        for case in module_cases:
            req_name = req_title_map.get(case.req_id) if case.req_id else (
                req_title_map.get(module_req_map.get(case.module or "")) if (case.module and case.module in module_req_map) else None
            )
            case_nodes.append({
                "id": case.id,
                "title": f"[{case.priority}] {case.title}",
                "priority": case.priority,
                "preconditions": case.preconditions or "",
                "steps": _steps_text(case.steps),
                "expected_result": case.expected_result or "",
                "exec_status": exec_map.get(case.id, "pending"),
                "req_id": case.req_id,
                "req_name": req_name,
            })
        module_nodes.append({
            "module": module_name,
            "cases": case_nodes,
        })

    return {
        "root": {
            "title": suite.name,
            "children": module_nodes,
        },
        "stat": {
            "total_cases": len(cases),
            "modules": len(module_nodes),
            "module_case_counts": {m["module"]: len(m["cases"]) for m in module_nodes},
        },
    }


# ── 用例集 CRUD ───────────────────────────────────────


@router.get("", response_model=CaseSuiteListResponse)
def list_case_suites(
    project_id: int,
    name: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """用例集列表（含用例数、模块数统计；支持名称搜索、分页）"""
    get_project(project_id, db, current_user)

    query = db.query(TestCaseSuite).filter(
        TestCaseSuite.project_id == project_id,
        TestCaseSuite.is_deleted == False,
    )
    if name:
        query = query.filter(TestCaseSuite.name.ilike(f"%{name}%"))

    total = query.count()
    suites = (
        query.order_by(TestCaseSuite.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for suite in suites:
        stats = _suite_stats(db, project_id, suite.id)
        items.append(
            CaseSuiteResponse(
                id=suite.id,
                project_id=suite.project_id,
                name=suite.name,
                description=suite.description or "",
                case_count=stats["case_count"],
                module_count=stats["module_count"],
                created_by=suite.created_by,
                created_at=suite.created_at,
                updated_at=suite.updated_at,
            )
        )
    return CaseSuiteListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=CaseSuiteResponse, status_code=201)
def create_case_suite(
    project_id: int,
    data: CaseSuiteCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """新建用例集"""
    get_project(project_id, db, current_user)
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=400, detail="用例集名称不能为空")

    suite = TestCaseSuite(
        project_id=project_id,
        name=data.name.strip(),
        description=data.description or "",
        created_by=current_user.id,
    )
    db.add(suite)
    db.flush()
    log_audit(
        db, action="create", resource_type="case_suite",
        resource_id=suite.id, resource_name=suite.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "name": suite.name},
    )
    db.commit()
    db.refresh(suite)
    return CaseSuiteResponse(
        id=suite.id, project_id=suite.project_id, name=suite.name,
        description=suite.description or "", case_count=0, module_count=0,
        created_by=suite.created_by, created_at=suite.created_at, updated_at=suite.updated_at,
    )


@router.put("/{suite_id}", response_model=CaseSuiteResponse)
def update_case_suite(
    project_id: int,
    suite_id: int,
    data: CaseSuiteUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """编辑用例集（名称/描述）"""
    get_project(project_id, db, current_user)
    suite = _get_suite(project_id, suite_id, db)

    old_name = suite.name
    if data.name is not None and data.name.strip():
        suite.name = data.name.strip()
    if data.description is not None:
        suite.description = data.description

    log_audit(
        db, action="update", resource_type="case_suite",
        resource_id=suite.id, resource_name=suite.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "before": {"name": old_name}, "after": {"name": suite.name}},
    )
    db.commit()
    db.refresh(suite)

    stats = _suite_stats(db, project_id, suite.id)
    return CaseSuiteResponse(
        id=suite.id, project_id=suite.project_id, name=suite.name,
        description=suite.description or "",
        case_count=stats["case_count"], module_count=stats["module_count"],
        created_by=suite.created_by, created_at=suite.created_at, updated_at=suite.updated_at,
    )


@router.delete("/{suite_id}")
def delete_case_suite(
    project_id: int,
    suite_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除用例集（仅删关联关系，不删用例）"""
    get_project(project_id, db, current_user)
    suite = _get_suite(project_id, suite_id, db)
    name = suite.name

    suite.soft_delete()
    # 级联清理关联关系（仅删关联记录，不影响用例本身）
    db.query(TestCaseSuiteCase).filter(TestCaseSuiteCase.suite_id == suite_id).delete(
        synchronize_session=False
    )

    log_audit(
        db, action="delete", resource_type="case_suite",
        resource_id=suite_id, resource_name=name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "name": name},
    )
    db.commit()
    return {"message": "用例集已删除", "suite_id": suite_id}


# ── 用例集-用例关联管理 ───────────────────────────────


@router.get("/{suite_id}/cases")
def list_suite_cases(
    project_id: int,
    suite_id: int,
    module: Optional[str] = None,
    priority: Optional[str] = None,
    req_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """集合内用例列表（分页，含模块/优先级/需求筛选）"""
    get_project(project_id, db, current_user)
    suite = _get_suite(project_id, suite_id, db)

    query = (
        db.query(TestCase)
        .join(TestCaseSuiteCase, TestCaseSuiteCase.case_id == TestCase.id)
        .filter(
            TestCaseSuiteCase.suite_id == suite_id,
            TestCase.project_id == project_id,
            TestCase.is_deleted == False,
        )
    )
    if module:
        query = query.filter(TestCase.module == module)
    if priority:
        query = query.filter(TestCase.priority == priority)
    if req_id is not None:
        query = query.filter(TestCase.req_id == req_id)

    total = query.count()
    cases = (
        query.order_by(TestCase.module, TestCase.priority, TestCase.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = []
    for case in cases:
        items.append(_serialize_case(case))
    return {"items": items, "total": total, "page": page, "page_size": page_size, "suite": {"id": suite.id, "name": suite.name}}


@router.post("/{suite_id}/cases")
def add_cases_to_suite(
    project_id: int,
    suite_id: int,
    data: CaseSuiteCasesBody,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量加入用例（自动去重），支持按用例ID / 需求ID / 模块名 三种方式关联"""
    get_project(project_id, db, current_user)
    suite = _get_suite(project_id, suite_id, db)

    if not data.case_ids and not data.req_ids and not data.module_names:
        raise HTTPException(status_code=400, detail="case_ids / req_ids / module_names 至少提供一种")

    # 汇总目标用例 ID（三种方式取并集）
    target_ids: set = set(data.case_ids)

    if data.req_ids:
        target_ids.update(
            cid for (cid,) in db.query(TestCase.id).filter(
                TestCase.req_id.in_(data.req_ids),
                TestCase.project_id == project_id,
                TestCase.is_deleted == False,
            ).all()
        )
    if data.module_names:
        target_ids.update(
            cid for (cid,) in db.query(TestCase.id).filter(
                TestCase.module.in_(data.module_names),
                TestCase.project_id == project_id,
                TestCase.is_deleted == False,
            ).all()
        )

    case_ids = list(target_ids)
    if not case_ids:
        raise HTTPException(status_code=404, detail="未匹配到任何有效用例")

    # 过滤项目内有效用例
    valid_ids = {
        cid for (cid,) in db.query(TestCase.id).filter(
            TestCase.id.in_(case_ids),
            TestCase.project_id == project_id,
            TestCase.is_deleted == False,
        ).all()
    }

    existing = {
        rel.case_id for rel in db.query(TestCaseSuiteCase).filter(
            TestCaseSuiteCase.suite_id == suite_id,
            TestCaseSuiteCase.case_id.in_(valid_ids),
        ).all()
    }

    added = 0
    for cid in valid_ids:
        if cid in existing:
            continue
        db.add(TestCaseSuiteCase(suite_id=suite_id, case_id=cid))
        added += 1

    if added:
        log_audit(
            db, action="add_cases", resource_type="case_suite",
            resource_id=suite.id, resource_name=suite.name,
            user=current_user,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            detail={
                "project_id": project_id,
                "case_ids": sorted(valid_ids) if data.case_ids else [],
                "req_ids": data.req_ids,
                "module_names": data.module_names,
                "added": added,
                "matched": len(valid_ids),
            },
        )
    db.commit()
    return {"message": f"已加入 {added} 条用例（匹配 {len(valid_ids)} 条）", "added": added, "matched": len(valid_ids)}


@router.delete("/{suite_id}/cases")
def remove_cases_from_suite(
    project_id: int,
    suite_id: int,
    data: CaseSuiteCasesBody,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量移除用例（仅移除关联关系，不影响用例本身）"""
    get_project(project_id, db, current_user)
    suite = _get_suite(project_id, suite_id, db)

    removed = db.query(TestCaseSuiteCase).filter(
        TestCaseSuiteCase.suite_id == suite_id,
        TestCaseSuiteCase.case_id.in_(data.case_ids),
    ).delete(synchronize_session=False)

    if removed:
        log_audit(
            db, action="remove_cases", resource_type="case_suite",
            resource_id=suite.id, resource_name=suite.name,
            user=current_user,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            detail={"project_id": project_id, "case_ids": data.case_ids, "removed": removed},
        )
    db.commit()
    return {"message": f"已移除 {removed} 条用例", "removed": removed}


# ── 添加用例数据源 ─────────────────────────────────────


@router.get("/available-cases")
def available_cases(
    project_id: int,
    module: Optional[str] = None,
    priority: Optional[str] = None,
    keyword: Optional[str] = None,
    req_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """「添加用例」弹窗数据源：项目全部用例（含模块/优先级/关键字/需求筛选）"""
    get_project(project_id, db, current_user)

    query = db.query(TestCase).filter(
        TestCase.project_id == project_id,
        TestCase.is_deleted == False,
    )
    if module:
        query = query.filter(TestCase.module == module)
    if priority:
        query = query.filter(TestCase.priority == priority)
    if keyword:
        query = query.filter(TestCase.title.ilike(f"%{keyword}%"))
    if req_id is not None:
        query = query.filter(TestCase.req_id == req_id)

    total = query.count()
    cases = (
        query.order_by(TestCase.module, TestCase.priority, TestCase.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # 模块列表（供筛选项）
    modules = [
        m[0] for m in db.query(TestCase.module).filter(
            TestCase.project_id == project_id,
            TestCase.is_deleted == False,
            TestCase.module != "",
        ).distinct().order_by(TestCase.module).all()
    ]

    return {
        "items": [_serialize_case(c) for c in cases],
        "total": total,
        "page": page,
        "page_size": page_size,
        "modules": modules,
    }


# ── XMind 导图 ─────────────────────────────────────────


@router.get("/{suite_id}/mind")
def suite_mind_data(
    project_id: int,
    suite_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导图树数据：返回 XMind 树形 JSON（根=用例集名→模块→用例→前置/步骤/预期）"""
    get_project(project_id, db, current_user)
    suite = _get_suite(project_id, suite_id, db)
    return _build_mind_data(db, project_id, suite)


@router.put("/{suite_id}/cases/{case_id}/exec-status")
def update_case_exec_status(
    project_id: int,
    suite_id: int,
    case_id: int,
    body: CaseExecStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新用例集内用例的执行状态（upsert：无记录则写入，有记录则更新）"""
    get_project(project_id, db, current_user)
    suite = _get_suite(project_id, suite_id, db)

    # 校验用例确实存在于本用例集
    link = (
        db.query(TestCaseSuiteCase)
        .filter(
            TestCaseSuiteCase.suite_id == suite_id,
            TestCaseSuiteCase.case_id == case_id,
        )
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="用例不在该用例集中")

    row = (
        db.query(CaseSuiteCaseExecStatus)
        .filter(
            CaseSuiteCaseExecStatus.suite_id == suite_id,
            CaseSuiteCaseExecStatus.case_id == case_id,
        )
        .first()
    )
    now = china_now_naive()
    if row:
        row.exec_status = body.exec_status
        row.executed_at = now
        row.executed_by = current_user.id
    else:
        row = CaseSuiteCaseExecStatus(
            project_id=project_id,
            suite_id=suite_id,
            case_id=case_id,
            exec_status=body.exec_status,
            executed_at=now,
            executed_by=current_user.id,
        )
        db.add(row)

    log_audit(
        db, action="update", resource_type="case_exec_status",
        resource_id=case_id, resource_name=f"用例#{case_id}执行状态",
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "suite_id": suite_id, "case_id": case_id, "exec_status": body.exec_status},
    )
    db.commit()
    db.refresh(row)
    return {
        "case_id": case_id,
        "suite_id": suite_id,
        "exec_status": row.exec_status,
        "executed_at": row.executed_at.isoformat() if row.executed_at else None,
    }


@router.get("/{suite_id}/export-xmind")
def export_suite_xmind(
    project_id: int,
    suite_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """按用例集导出 .xmind 文件（结构：用例集名 → 模块 → 用例 → 前置/步骤/预期）"""
    project = get_project(project_id, db, current_user)
    suite = _get_suite(project_id, suite_id, db)

    mind = _build_mind_data(db, project_id, suite)

    # 构建 XMind topic 树：每条用例按「用例标题 → 前置条件 → 测试步骤 → 预期结果」链式拼接，
    # 与数据导入导出模块（import_export.export_cases_xmind）的格式逻辑保持一致
    module_topics = []
    for mod in mind["root"]["children"]:
        case_topics = []
        for c in mod["cases"]:
            expected_topic = _make_xmind_topic(f"预期结果：{c['expected_result'] or '无'}")
            steps_topic = _make_xmind_topic(f"测试步骤：{c['steps'] or '无步骤'}", [expected_topic])
            precond_topic = _make_xmind_topic(f"前置条件：{c['preconditions'] or '无'}", [steps_topic])
            case_topics.append(_make_xmind_topic(c["title"], [precond_topic]))
        module_topics.append(_make_xmind_topic(mod["module"], case_topics))

    root_topic = _make_xmind_topic(suite.name, module_topics)

    content = [{
        "id": uuid.uuid4().hex,
        "class": "sheet",
        "title": suite.name,
        "rootTopic": root_topic,
    }]

    metadata = {"creator": {"name": "AITS", "version": "1.0"}}
    manifest = {"file-entries": {"content.json": {}, "metadata.json": {}}}

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("content.json", json.dumps(content, ensure_ascii=False))
        zf.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False))
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
    output.seek(0)

    log_audit(
        db, action="export", resource_type="case_suite",
        resource_id=suite.id, resource_name=suite.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "count": mind["stat"]["total_cases"], "format": "xmind"},
    )
    db.commit()

    filename = f"{suite.name}.xmind"
    return StreamingResponse(
        output,
        media_type="application/vnd.xmind.workbook",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


# ── 序列化 ─────────────────────────────────────────────


def _serialize_case(case: TestCase) -> Dict:
    """序列化用例（steps 反序列化为列表，供前端直接渲染）"""
    steps = []
    if case.steps:
        try:
            steps = json.loads(case.steps)
        except (json.JSONDecodeError, TypeError):
            steps = []
    return {
        "id": case.id,
        "project_id": case.project_id,
        "req_id": case.req_id,
        "feature_id": case.feature_id,
        "title": case.title,
        "module": case.module or "",
        "priority": case.priority,
        "case_type": case.case_type,
        "preconditions": case.preconditions or "",
        "steps": steps,
        "expected_result": case.expected_result or "",
        "status": case.status,
        "created_by": case.created_by,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
    }
