"""
Prompt 管理 API（全局公用，不绑定项目）
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.core.deps import get_current_user
from app.core.audit import log_audit
from app.core.timezone import china_now_naive
from app.models.user import User
from app.models.prompt import Prompt
from app.schemas.prompt import PromptCreate, PromptUpdate, PromptResponse

router = APIRouter(prefix="/api/prompts", tags=["Prompt 管理"])


@router.get("", response_model=List[PromptResponse])
def list_prompts(
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 Prompt 列表"""
    query = db.query(Prompt)
    if category:
        query = query.filter(Prompt.category == category)
    return query.order_by(Prompt.is_default.desc(), Prompt.id.desc()).all()


@router.post("", response_model=PromptResponse, status_code=201)
def create_prompt(
    data: PromptCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建 Prompt"""
    if data.is_default:
        db.query(Prompt).filter(
            Prompt.category == data.category,
            Prompt.is_default == True,
        ).update({Prompt.is_default: False}, synchronize_session=False)

    prompt = Prompt(
        name=data.name,
        description=data.description,
        category=data.category,
        system_prompt=data.system_prompt,
        user_prompt_template=data.user_prompt_template,
        variables=data.variables,
        is_default=data.is_default,
        status=data.status,
        created_by=current_user.id,
    )
    db.add(prompt)
    db.flush()
    log_audit(
        db, action="create", resource_type="prompt",
        resource_id=prompt.id, resource_name=prompt.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"category": data.category},
    )
    db.commit()
    db.refresh(prompt)
    return prompt


@router.put("/{prompt_id}", response_model=PromptResponse)
def update_prompt(
    prompt_id: int,
    data: PromptUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新 Prompt"""
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt 不存在")

    update_data = data.model_dump(exclude_unset=True)
    if data.is_default:
        db.query(Prompt).filter(
            Prompt.category == prompt.category,
            Prompt.id != prompt_id,
            Prompt.is_default == True,
        ).update({Prompt.is_default: False}, synchronize_session=False)

    for key, value in update_data.items():
        setattr(prompt, key, value)
    prompt.updated_at = china_now_naive()
    db.commit()
    db.refresh(prompt)
    return prompt


@router.delete("/{prompt_id}")
def delete_prompt(
    prompt_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除 Prompt"""
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt 不存在")
    prompt_name = prompt.name
    prompt.soft_delete()
    log_audit(
        db, action="delete", resource_type="prompt",
        resource_id=prompt_id, resource_name=prompt_name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return {"detail": "删除成功"}


@router.post("/seed-defaults")
def seed_default_prompts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """初始化默认 Prompt 模板（按分类补全缺失的默认 Prompt）"""
    existing_categories = {
        row[0] for row in db.query(Prompt.category).distinct().all()
    }

    defaults = [
        # ---- 用例生成 ----
        Prompt(
            name="用例生成 - 标准模板",
            description="适用于功能测试用例生成，覆盖正向、异常、边界场景",
            category="case_generation",
            system_prompt="你是一名资深测试用例设计专家，拥有 10 年以上软件测试经验。请根据需求描述生成全面、专业的测试用例。",
            user_prompt_template="",
            variables=["requirement_title", "requirement_content", "count"],
            is_default=True,
            status="active",
            created_by=current_user.id,
        ),
        Prompt(
            name="用例生成 - BDD Gherkin",
            description="生成 BDD Gherkin 格式的测试用例",
            category="case_generation",
            system_prompt="你是一名 BDD 测试专家，擅长用 Gherkin 语法（Given/When/Then）编写测试场景。请根据需求描述生成结构化的 BDD 测试用例。",
            user_prompt_template="",
            variables=["requirement_title", "requirement_content", "count"],
            is_default=False,
            status="active",
            created_by=current_user.id,
        ),
        Prompt(
            name="用例生成 - 安全测试",
            description="侧重安全测试场景，包含 SQL 注入、XSS、越权等",
            category="case_generation",
            system_prompt="你是一名安全测试专家，擅长设计安全测试用例。请根据需求描述生成覆盖 OWASP Top 10 安全风险的测试用例，包含 SQL 注入、XSS、CSRF、越权访问等场景。",
            user_prompt_template="",
            variables=["requirement_title", "requirement_content", "count"],
            is_default=False,
            status="active",
            created_by=current_user.id,
        ),
        # ---- 需求生成 ----
        Prompt(
            name="需求生成 - 标准模板",
            description="根据用户简要描述生成结构化需求文档",
            category="requirement_generation",
            system_prompt="你是一名资深需求分析师，擅长将简要描述转化为结构化、可执行的需求文档。请根据用户输入生成包含背景、功能描述、用户故事、验收标准等内容的需求文档。",
            user_prompt_template="",
            variables=["user_input", "project_name"],
            is_default=True,
            status="active",
            created_by=current_user.id,
        ),
        # ---- 报告生成 ----
        Prompt(
            name="报告生成 - 标准模板",
            description="根据测试统计数据生成测试报告",
            category="report_generation",
            system_prompt="你是一名测试报告分析专家，请根据提供的测试统计数据生成专业、结构清晰的测试报告，包含测试概览、质量分析、风险评估和改进建议。",
            user_prompt_template="",
            variables=["project_id", "version_id", "report_type"],
            is_default=True,
            status="active",
            created_by=current_user.id,
        ),
        # ---- 脚本生成 ----
        Prompt(
            name="脚本生成 - 标准模板",
            description="根据测试需求描述生成 Playwright 自动化脚本",
            category="script_generation",
            system_prompt="你是一名自动化测试专家，擅长使用 Playwright 编写可靠的 UI 自动化测试脚本。请根据测试需求描述生成结构清晰、可维护的 Playwright 脚本。",
            user_prompt_template="",
            variables=["description", "target_url"],
            is_default=True,
            status="active",
            created_by=current_user.id,
        ),
        # ---- API 测试 ----
        Prompt(
            name="API 文档生成 - 标准模板",
            description="根据接口定义生成接口文档",
            category="api_test",
            system_prompt="你是一名 API 文档专家，请根据接口定义信息生成清晰、完整的接口文档，包含接口说明、请求参数、响应示例等内容。",
            user_prompt_template="",
            variables=["api_definition"],
            is_default=True,
            status="active",
            created_by=current_user.id,
        ),
        Prompt(
            name="API 用例生成 - 标准模板",
            description="根据接口定义生成接口测试用例",
            category="api_test",
            system_prompt="你是一名 API 测试专家，请根据接口定义生成覆盖正常流程、异常场景、边界条件的接口测试用例，包含请求参数和断言。",
            user_prompt_template="",
            variables=["api_definition", "strategy", "case_count"],
            is_default=False,
            status="active",
            created_by=current_user.id,
        ),
    ]

    # 只插入尚无任何 Prompt 的分类
    to_insert = [p for p in defaults if p.category not in existing_categories]
    if not to_insert:
        return {"detail": "所有分类已有 Prompt，跳过初始化", "count": 0}

    for p in to_insert:
        db.add(p)
    db.commit()
    return {"detail": "初始化完成", "count": len(to_insert)}
