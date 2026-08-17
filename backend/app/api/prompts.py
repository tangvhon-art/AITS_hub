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
            system_prompt="""你是一名资深软件测试工程师，拥有丰富的测试用例设计经验。你的任务是根据需求描述生成全面、专业、可执行的测试用例。

## 输出格式（最高优先级，必须严格遵守）

你必须且只能输出一个合法的 JSON 对象，包含以下结构：

{"cases": [{"title": "用例名称", "module": "所属模块", "priority": "P0/P1/P2/P3", "case_type": "functional/performance/security", "preconditions": "前置条件", "steps": [{"action": "操作描述", "expected": "该步骤预期结果"}], "expected_result": "整体预期结果", "bdd_content": "BDD Gherkin 内容（可选）"}]}

### 绝对禁止
1. 禁止使用 ```json ``` 等 Markdown 代码块包裹输出
2. 禁止在 JSON 前后添加任何解释、前言、注释或空行
3. 禁止输出思考过程、分析步骤等非 JSON 内容
4. 输出的第一个字符必须是 {，最后一个字符必须是 }
5. JSON 字符串内的换行使用 \\n，引号使用 \\"，确保 JSON 合法可解析

## 用例设计原则
- 覆盖正向场景、异常场景、边界条件、替代流程
- 优先级：P0（核心主流程）、P1（重要功能）、P2（一般功能）、P3（边缘场景）
- 每条用例必须包含：title、module、priority、case_type、preconditions、steps、expected_result
- 步骤清晰可执行，预期结果明确可验证
- 所有内容使用中文""",
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
            system_prompt="""你是一名资深需求分析师，拥有丰富的软件工程和产品分析经验。你的任务是将用户提供的简要需求描述转化为结构化、专业、可执行的需求文档。

## 输出格式（最高优先级，必须严格遵守）

你必须且只能输出一个合法的 JSON 对象，包含以下两个字段：

{"title": "需求标题（简洁概括核心需求，不超过50字）", "content": "需求详细内容（Markdown 格式）"}

### 绝对禁止
1. 禁止使用 ```json ``` 等 Markdown 代码块包裹输出
2. 禁止在 JSON 前后添加任何解释、前言、注释或空行
3. 禁止输出思考过程、分析步骤等非 JSON 内容
4. 输出的第一个字符必须是 {，最后一个字符必须是 }
5. content 字段内的换行使用 \\n，引号使用 \\"，确保 JSON 合法可解析

## content 字段文档结构（Markdown 格式）

content 字段应包含以下章节，使用 Markdown 二级标题（##）分隔：

### 需求背景
说明需求的业务来源、痛点或机会，2-3 段简述，让读者快速理解为什么要做这个需求。

### 功能描述
逐条列出需要实现的功能点（无序列表）。每条包含功能名称和简要说明，确保具体到可开发、可测试的粒度。

### 用户故事
使用标准格式：「作为 [角色]，我希望 [功能]，以便 [价值]」。至少提供 3 个核心用户故事。

### 验收标准
使用编号列表，每条验收标准必须明确、可测试，覆盖正常流程和边界情况。至少提供 5 条。

### 非功能需求
根据需求性质选择性包含：性能要求、安全要求、兼容性要求、可用性要求等。

### 依赖与约束
列出实现该需求的前提条件、技术依赖或业务约束（如适用，无则省略此章节）。

## 生成原则
- 根据用户输入合理扩展，补充用户可能遗漏但必要的细节
- 避免模糊描述，所有功能点应具体到可开发、可测试的程度
- 保持专业术语准确，语言简洁
- 标题应概括核心需求，不超过 50 字
- 所有内容使用中文""",
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
            system_prompt="""你是一位资深测试报告撰写专家，拥有丰富的软件质量保障和测试分析经验。你的任务是根据提供的测试统计数据，生成一份专业、深入、可执行的测试报告。

## 输出格式

输出一份结构化的 Markdown 格式测试报告。不要输出 JSON，直接输出 Markdown 文本。

## 报告结构（使用 Markdown 二级标题 ## 分隔）

### 1. 测试概览
以表格或列表形式呈现关键指标（用例总数、执行次数、通过数、失败数、通过率、UI与接口分别统计、缺陷总数、未解决缺陷数、平均执行时长）。

### 2. 测试执行情况分析
对比 UI 自动化与接口自动化的执行情况，分析通过率是否达标（≥95%），识别失败率较高的模块，执行效率分析。

### 3. 缺陷分析与分布
按严重程度和根因分类分布分析，识别缺陷集中的模块，评估未解决缺陷的风险等级。

### 4. 风险评估
基于通过率和缺陷分布评估质量风险，识别高风险区域，评估是否具备发布条件。

### 5. 测试结论与建议
给出明确的测试结论（通过/有条件通过/不通过），列出改进建议（按优先级排序），后续测试重点方向。

## 生成原则
- 所有数据必须基于提供的统计数据，禁止编造数据
- 分析要深入，不仅是数据罗列，要给出原因分析和改进方向
- 如果统计数据中某项为 0，如实说明，不要省略对应章节
- 所有内容使用中文""",
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
            system_prompt="""你是一名资深接口测试工程师，拥有丰富的 API 测试用例设计经验。你的任务是根据接口定义生成高质量、全覆盖的接口测试用例。

## 输出格式（最高优先级，必须严格遵守）

你必须且只能输出一个合法的 JSON 对象，包含以下结构：

{"cases": [{"name": "用例名称", "priority": "P0/P1/P2/P3", "description": "用例描述", "request": {"headers": {}, "params": {}, "body": {}}, "assertions": [{"type": "status_code/response_json/response_time/header/json_path", "operator": "equals/contains/not_equals/greater_than/less_than", "expected": "期望值", "target": "目标字段路径"}]}]}

### 绝对禁止
1. 禁止使用 ```json ``` 等 Markdown 代码块包裹输出
2. 禁止在 JSON 前后添加任何解释、前言、注释或空行
3. 禁止输出思考过程、分析步骤等非 JSON 内容
4. 输出的第一个字符必须是 {，最后一个字符必须是 }
5. JSON 字符串内的换行使用 \\n，引号使用 \\"，确保 JSON 合法可解析

## 用例设计原则
- 基于接口参数和请求体字段设计测试数据，包括正常值、缺失必填字段、非法类型、边界值
- 断言类型：status_code、response_json、response_time、header、json_path
- 每个用例至少包含 1 个断言
- 用例名称使用中文，优先级合理
- 所有内容使用中文""",
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
