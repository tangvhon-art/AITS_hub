import json
from datetime import datetime
from app.core.timezone import china_now_naive
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.core.deps import get_current_user
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
    db.commit()
    db.refresh(case)
    return case


@router.post("/batch", response_model=List[TestCaseResponse], status_code=status.HTTP_201_CREATED)
def batch_create_cases(
    project_id: int,
    batch_data: TestCaseBatchCreate,
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

    update_data = case_data.model_dump(exclude_unset=True)
    if "steps" in update_data and isinstance(update_data["steps"], list):
        update_data["steps"] = json.dumps(update_data["steps"], ensure_ascii=False)
    for key, value in update_data.items():
        setattr(case, key, value)
    db.commit()
    db.refresh(case)
    return case


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(
    project_id: int,
    case_id: int,
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
    db.delete(case)
    db.commit()


@router.post("/generate")
def generate_cases(
    project_id: int,
    gen_request: CaseGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    AI 生成测试用例（同步返回，简单场景直接生成）
    对于大需求，建议使用异步任务
    """
    _check_project_access(project_id, db, current_user)

    # 获取需求内容
    requirement_content = gen_request.content
    req_id = gen_request.requirement_id
    if req_id:
        requirement = db.query(TestRequirement).filter(
            TestRequirement.id == req_id,
            TestRequirement.project_id == project_id,
        ).first()
        if requirement:
            requirement_content = requirement.content or requirement.title

    if not requirement_content.strip():
        raise HTTPException(status_code=400, detail="需求内容不能为空")

    # 创建 Agent 任务记录
    task = AgentTask(
        project_id=project_id,
        agent_type="case_generator",
        status="running",
        input_params={"content_length": len(requirement_content), "count": gen_request.count},
        created_by=current_user.id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    try:
        # 同步生成（MVP-1 简化版，后续改异步）
        agent = CaseGeneratorAgent(db_session=db, llm_config_id=gen_request.llm_config_id)
        result = agent.generate(
            requirement_content=requirement_content,
            count=gen_request.count,
        )

        task.status = "success"
        task.output_result = {"case_count": len(result["cases"])}
        task.llm_config_id = result.get("llm_config_id")
        task.token_usage = result.get("token_usage", {})
        task.completed_at = china_now_naive()
        db.commit()

        return {
            "task_id": task.id,
            "status": "success",
            "cases": result["cases"],
            "token_usage": result.get("token_usage", {}),
        }

    except Exception as e:
        task.status = "failed"
        task.error_message = str(e)
        task.completed_at = china_now_naive()
        db.commit()
        raise HTTPException(status_code=500, detail=f"用例生成失败: {str(e)}")
