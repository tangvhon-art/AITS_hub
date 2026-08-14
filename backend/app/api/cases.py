import json
from datetime import datetime
from app.core.timezone import china_now_naive
from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.core.deps import get_current_user
from app.core.audit import log_audit
from app.models.user import User
from app.models.project import Project
from app.models.test_case import TestCase
from app.models.requirement import TestRequirement
from app.models.agent_task import AgentTask
from app.schemas.test_case import TestCaseCreate, TestCaseUpdate, TestCaseResponse, TestCaseBatchCreate
from app.schemas.requirement import CaseGenerateRequest
from app.agents.case_generator import CaseGeneratorAgent

router = APIRouter(prefix="/api/projects/{project_id}/cases", tags=["用例管理"])


def _check_project_access(project_id: int, db: Session, user: User) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.owner_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="无权访问该项目")
    return project


@router.get("", response_model=List[TestCaseResponse])
def list_cases(
    project_id: int,
    module: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取用例列表，支持按模块/优先级/状态筛选"""
    _check_project_access(project_id, db, current_user)
    query = db.query(TestCase).filter(TestCase.project_id == project_id)
    if module:
        query = query.filter(TestCase.module == module)
    if priority:
        query = query.filter(TestCase.priority == priority)
    if status:
        query = query.filter(TestCase.status == status)
    return query.order_by(TestCase.created_at.desc()).all()


@router.post("", response_model=TestCaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    project_id: int,
    case_data: TestCaseCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建单条用例"""
    _check_project_access(project_id, db, current_user)
    case = TestCase(
        project_id=project_id,
        req_id=case_data.req_id,
        title=case_data.title,
        module=case_data.module,
        priority=case_data.priority,
        case_type=case_data.case_type,
        preconditions=case_data.preconditions,
        steps=json.dumps(case_data.steps, ensure_ascii=False) if isinstance(case_data.steps, list) else case_data.steps,
        expected_result=case_data.expected_result,
        bdd_content=case_data.bdd_content,
        created_by=current_user.id,
    )
    db.add(case)
    db.flush()
    log_audit(
        db, action="create", resource_type="case",
        resource_id=case.id, resource_name=case.title,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "title": case.title, "priority": case.priority},
    )
    db.commit()
    db.refresh(case)
    return case


@router.post("/batch", response_model=List[TestCaseResponse], status_code=status.HTTP_201_CREATED)
def batch_create_cases(
    project_id: int,
    batch_data: TestCaseBatchCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量创建用例（AI 生成后保存）"""
    _check_project_access(project_id, db, current_user)
    cases = []
    for case_data in batch_data.cases:
        case = TestCase(
            project_id=project_id,
            req_id=case_data.req_id,
            title=case_data.title,
            module=case_data.module,
            priority=case_data.priority,
            case_type=case_data.case_type,
            preconditions=case_data.preconditions,
            steps=json.dumps(case_data.steps, ensure_ascii=False) if isinstance(case_data.steps, list) else case_data.steps,
            expected_result=case_data.expected_result,
            bdd_content=case_data.bdd_content,
            created_by=current_user.id,
        )
        db.add(case)
        cases.append(case)
    db.flush()
    log_audit(
        db, action="create", resource_type="case",
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "batch_count": len(cases), "action": "batch_create"},
    )
    db.commit()
    for case in cases:
        db.refresh(case)
    return cases


@router.get("/{case_id}", response_model=TestCaseResponse)
def get_case(
    project_id: int,
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取用例详情"""
    _check_project_access(project_id, db, current_user)
    case = db.query(TestCase).filter(
        TestCase.id == case_id,
        TestCase.project_id == project_id,
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")
    return case


@router.put("/{case_id}", response_model=TestCaseResponse)
def update_case(
    project_id: int,
    case_id: int,
    case_data: TestCaseUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新用例"""
    _check_project_access(project_id, db, current_user)
    case = db.query(TestCase).filter(
        TestCase.id == case_id,
        TestCase.project_id == project_id,
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")

    old_data = {"title": case.title, "priority": case.priority, "status": case.status}
    update_data = case_data.model_dump(exclude_unset=True)
    if "steps" in update_data and isinstance(update_data["steps"], list):
        update_data["steps"] = json.dumps(update_data["steps"], ensure_ascii=False)
    for key, value in update_data.items():
        setattr(case, key, value)
    log_audit(
        db, action="update", resource_type="case",
        resource_id=case.id, resource_name=case.title,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"before": old_data, "after": {k: v for k, v in update_data.items() if k != "steps"}},
    )
    db.commit()
    db.refresh(case)
    return case


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(
    project_id: int,
    case_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除用例"""
    _check_project_access(project_id, db, current_user)
    case = db.query(TestCase).filter(
        TestCase.id == case_id,
        TestCase.project_id == project_id,
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")
    case_name = case.title
    case.soft_delete()
    log_audit(
        db, action="delete", resource_type="case",
        resource_id=case_id, resource_name=case_name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()


@router.post("/generate")
def generate_cases(
    project_id: int,
    gen_request: CaseGenerateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    AI 生成测试用例（异步执行）
    提交后立即返回任务ID，生成结果可在Agent任务中查看
    """
    _check_project_access(project_id, db, current_user)

    # 获取需求内容
    requirement_content = gen_request.content
    req_id = gen_request.requirement_id
    req_title = None
    if req_id:
        requirement = db.query(TestRequirement).filter(
            TestRequirement.id == req_id,
            TestRequirement.project_id == project_id,
        ).first()
        if requirement:
            requirement_content = requirement.content or requirement.title
            req_title = requirement.title

    if not requirement_content or not requirement_content.strip():
        raise HTTPException(status_code=400, detail="需求内容不能为空")

    # 创建 Agent 任务记录
    task = AgentTask(
        project_id=project_id,
        agent_type="case_generator",
        status="pending",
        input_params={
            "content_length": len(requirement_content),
            "count": gen_request.count,
            "requirement_id": req_id,
            "requirement_title": req_title,
        },
        llm_config_id=gen_request.llm_config_id,
        created_by=current_user.id,
    )
    db.add(task)
    db.flush()
    log_audit(
        db, action="generate", resource_type="case",
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "count": gen_request.count, "requirement_id": req_id, "task_id": task.id},
    )
    db.commit()
    db.refresh(task)

    # 添加后台任务异步执行
    background_tasks.add_task(
        _generate_cases_background,
        task_id=task.id,
        project_id=project_id,
        requirement_content=requirement_content,
        count=gen_request.count,
        llm_config_id=gen_request.llm_config_id,
        req_id=req_id,
    )

    return {
        "task_id": task.id,
        "status": "pending",
        "message": "用例生成任务已提交，可在Agent任务中查看进度",
    }


def _generate_cases_background(
    task_id: int,
    project_id: int,
    requirement_content: str,
    count: int,
    llm_config_id: Optional[int] = None,
    req_id: Optional[int] = None,
):
    """后台执行用例生成"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if not task:
            return

        task.status = "running"
        db.commit()

        agent = CaseGeneratorAgent(db_session=db, llm_config_id=llm_config_id)
        result = agent.generate(
            requirement_content=requirement_content,
            count=count,
        )

        # 自动保存生成的用例到数据库
        cases_saved = 0
        for case_data in result.get("cases", []):
            try:
                case = TestCase(
                    project_id=project_id,
                    req_id=req_id,
                    title=case_data.get("title", ""),
                    module=case_data.get("module", "默认模块"),
                    priority=case_data.get("priority", "P2"),
                    case_type=case_data.get("case_type", "functional"),
                    preconditions=case_data.get("preconditions", ""),
                    steps=json.dumps(case_data.get("steps", []), ensure_ascii=False) if isinstance(case_data.get("steps"), list) else case_data.get("steps", "[]"),
                    expected_result=case_data.get("expected_result", ""),
                    bdd_content=case_data.get("bdd_content"),
                    created_by=task.created_by,
                )
                db.add(case)
                cases_saved += 1
            except Exception:
                continue

        db.commit()

        task.status = "success"
        task.output_result = {
            "case_count": len(result.get("cases", [])),
            "cases_saved": cases_saved,
            "cases": result.get("cases", []),
        }
        task.llm_config_id = result.get("llm_config_id")
        task.token_usage = result.get("token_usage", {})
        task.completed_at = china_now_naive()
        db.commit()

    except Exception as e:
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if task:
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = china_now_naive()
            db.commit()
    finally:
        db.close()
