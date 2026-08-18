"""
Prompt 管理 API（全局公用，不绑定项目）
"""
from fastapi import APIRouter, Body, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.core.deps import get_current_user
from app.core.audit import log_audit
from app.core.crud import CRUDBase
from app.core.timezone import china_now_naive
from app.models.user import User
from app.models.prompt import Prompt
from app.schemas.prompt import PromptCreate, PromptUpdate, PromptResponse

router = APIRouter(prefix="/api/prompts", tags=["Prompt 管理"])

# 全局资源，project_id=None
prompt_crud = CRUDBase(Prompt, "Prompt")


@router.post("/search", response_model=List[PromptResponse])
def list_prompts(
    category: Optional[str] = Body(default=None, embed=True),
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
    prompt = prompt_crud.get(db, prompt_id)

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
    prompt = prompt_crud.get(db, prompt_id)
    prompt_name = prompt.name
    prompt_crud.soft_delete(db, prompt_id)
    log_audit(
        db, action="delete", resource_type="prompt",
        resource_id=prompt_id, resource_name=prompt_name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
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

你必须且只能输出一个合法的 JSON 对象，包含以下结构。

### 关键规则：数组中的每个元素必须是对象，用花括号 {} 包裹，绝对不能用方括号 [] 包裹

正确写法：[{"key": "value"}, {"key": "value"}]
错误写法：[["key": "value"], ["key": "value"]]  ← 禁止！

### 完整示例

{"cases": [{"title": "用户登录-正确账号密码", "module": "登录模块", "priority": "P0", "case_type": "functional", "preconditions": "已注册账号admin/123456", "steps": [{"action": "打开登录页面", "expected": "登录页面正常显示"}, {"action": "输入用户名admin", "expected": "用户名输入框显示admin"}, {"action": "输入密码123456", "expected": "密码输入框显示掩码"}, {"action": "点击登录按钮", "expected": "页面跳转到首页"}], "expected_result": "成功登录并跳转到首页，显示用户信息", "bdd_content": "Given 用户已注册 When 用户输入正确账号密码并点击登录 Then 系统跳转到首页"}, {"title": "用户登录-密码错误", "module": "登录模块", "priority": "P1", "case_type": "functional", "preconditions": "已注册账号admin", "steps": [{"action": "打开登录页面", "expected": "登录页面正常显示"}, {"action": "输入用户名admin", "expected": "用户名输入框显示admin"}, {"action": "输入错误密码xxx", "expected": "密码输入框显示掩码"}, {"action": "点击登录按钮", "expected": "页面显示错误提示"}], "expected_result": "登录失败，页面提示密码错误", "bdd_content": ""}]}

### 绝对禁止
1. 禁止使用 ```json ``` 等 Markdown 代码块包裹输出
2. 禁止在 JSON 前后添加任何解释、前言、注释或空行
3. 禁止输出思考过程、分析步骤等非 JSON 内容
4. 输出的第一个字符必须是 {，最后一个字符必须是 }
5. JSON 字符串内的换行使用 \\n，引号使用 \\"，确保 JSON 合法可解析
6. steps 数组的元素必须用花括号 {} 包裹，禁止用方括号 []
7. cases 数组的元素必须用花括号 {} 包裹，禁止用方括号 []
8. 所有字段名必须用英文：title, module, priority, case_type, preconditions, steps, action, expected, expected_result, bdd_content

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
        # ---- 用例评审 ----
        Prompt(
            name="用例评审 - 标准模板",
            description="多维度评审测试用例，生成评分、问题列表和改进建议",
            category="case_review",
            system_prompt="""你是一位资深测试评审专家，拥有丰富的测试用例评审经验。你的任务是对测试用例进行多维度评审，给出评分、问题列表和改进建议。

## 评审维度
1. **完整性**：是否包含标题、前置条件、步骤、预期结果
2. **覆盖率**：是否覆盖正向、异常、边界场景
3. **可执行性**：步骤是否清晰可执行，预期结果是否明确
4. **规范性**：优先级是否合理，模块划分是否清晰
5. **冗余性**：是否有重复或高度相似的用例

## 输出格式（最高优先级，必须严格遵守）

你必须且只能输出一个合法的 JSON 对象，包含以下结构：

{"score": 85, "passed": true, "summary": "整体评价（50字以内）", "issues": [{"case_index": 0, "issue_type": "完整性/覆盖率/可执行性/规范性/冗余性", "severity": "high/medium/low", "description": "问题描述", "suggestion": "修改建议"}], "overall_suggestions": ["整体改进建议1", "整体改进建议2"]}

### 绝对禁止
1. 禁止使用 ```json ``` 等 Markdown 代码块包裹输出
2. 禁止在 JSON 前后添加任何解释、前言、注释或空行
3. 禁止输出思考过程、分析步骤等非 JSON 内容
4. 输出的第一个字符必须是 {，最后一个字符必须是 }
5. score 为 0-100 的整数，passed 为 true 或 false
6. 如果没有发现问题，issues 返回空数组 []，overall_suggestions 仍需给出总体评价建议

## 评审原则
- 评分标准：90+优秀，80-89良好，70-79合格，<70不合格
- 每个问题必须指明具体的用例序号（case_index 从0开始）
- severity 分级：high（严重问题，影响用例可用性）、medium（中等问题，影响用例质量）、low（轻微问题，建议优化）
- 改进建议要具体、可操作，不要泛泛而谈
- 所有内容使用中文""",
            user_prompt_template="",
            variables=["cases", "requirement"],
            is_default=True,
            status="active",
            created_by=current_user.id,
        ),
        # ---- API 文档生成 ----
        Prompt(
            name="API 文档生成 - 标准模板",
            description="根据接口定义生成接口文档",
            category="api_doc_generation",
            system_prompt="你是一名 API 文档专家，请根据接口定义信息生成清晰、完整的接口文档，包含接口说明、请求参数、响应示例等内容。",
            user_prompt_template="",
            variables=["api_definition"],
            is_default=True,
            status="active",
            created_by=current_user.id,
        ),
        # ---- API 用例生成 ----
        Prompt(
            name="API 用例生成 - 标准模板",
            description="根据接口定义生成接口测试用例",
            category="api_case_generation",
            system_prompt="""你是一名资深接口测试工程师，拥有丰富的 API 测试用例设计经验。你的任务是根据接口定义生成高质量、全覆盖的接口测试用例。

## 输出格式（最高优先级，必须严格遵守）

你必须且只能输出一个合法的 JSON 对象，包含以下结构。

### 关键规则：数组中的每个元素必须是对象，用花括号 {} 包裹，绝对不能用方括号 [] 包裹

正确写法：[{"key": "value"}, {"key": "value"}]
错误写法：[["key": "value"], ["key": "value"]]  ← 禁止！

### 完整示例

{"cases": [{"name": "获取用户列表-正常请求", "priority": "P0", "description": "验证正常分页查询", "request": {"headers": {"Authorization": "Bearer token"}, "params": {"page": 1, "page_size": 20}, "body": {}}, "assertions": [{"type": "status_code", "operator": "equals", "expected": 200, "target": ""}, {"type": "response_json", "operator": "contains", "expected": "items", "target": "$.data"}]}, {"name": "创建用户-缺少必填字段", "priority": "P1", "description": "验证缺少用户名时返回错误", "request": {"headers": {"Content-Type": "application/json"}, "params": {}, "body": {"email": "test@test.com"}}, "assertions": [{"type": "status_code", "operator": "equals", "expected": 400, "target": ""}]}]}

### 绝对禁止
1. 禁止使用 ```json ``` 等 Markdown 代码块包裹输出
2. 禁止在 JSON 前后添加任何解释、前言、注释或空行
3. 禁止输出思考过程、分析步骤等非 JSON 内容
4. 输出的第一个字符必须是 {，最后一个字符必须是 }
5. JSON 字符串内的换行使用 \\n，引号使用 \\"，确保 JSON 合法可解析
6. cases 数组和 assertions 数组的元素必须用花括号 {} 包裹，禁止用方括号 []
7. 所有字段名必须用英文

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

    # 插入尚无任何 Prompt 的分类
    to_insert = [p for p in defaults if p.category not in existing_categories]
    for p in to_insert:
        db.add(p)

    # 更新已有的默认 Prompt（按 category + is_default 匹配，同步最新的 system_prompt）
    updated_count = 0
    default_map = {p.category: p for p in defaults if p.is_default}
    existing_defaults = db.query(Prompt).filter(
        Prompt.is_default == True,
        Prompt.category.in_(list(default_map.keys())),
        Prompt.is_deleted == False,
    ).all()
    for ed in existing_defaults:
        nd = default_map.get(ed.category)
        if nd and ed.system_prompt != nd.system_prompt:
            ed.system_prompt = nd.system_prompt
            ed.description = nd.description
            updated_count += 1

    db.commit()
    total = len(to_insert) + updated_count
    if total == 0:
        return {"detail": "所有分类已有 Prompt，无需更新", "count": 0}
    return {"detail": f"初始化完成（新增 {len(to_insert)}，更新 {updated_count}）", "count": total}
