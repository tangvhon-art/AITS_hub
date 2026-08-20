"""
用例生成 Agent

根据需求描述自动生成结构化测试用例。
支持自定义 Prompt 作为 system 提示词输入。
"""
import json
import logging
from typing import List, Dict, Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from app.agents.llm_factory import llm_factory
from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class TestCaseItem(BaseModel):
    """单条测试用例结构 - 与 TestCase 表字段完全对应"""
    title: str = Field(description="用例名称，简洁明确，不超过200字符")
    module: str = Field(default="", description="所属模块，根据需求功能划分")
    priority: str = Field(default="P1", description="优先级，可选值：P0(核心主流程)、P1(重要功能)、P2(一般功能)、P3(边缘场景)")
    case_type: str = Field(default="functional", description="用例类型，可选值：functional(功能)、performance(性能)、security(安全)")
    preconditions: str = Field(default="", description="前置条件，执行用例前需要满足的环境和数据准备")
    steps: List[Dict[str, str]] = Field(default_factory=list, description="测试步骤数组，每个元素包含 action(操作描述) 和 expected(该步骤预期结果)")
    expected_result: str = Field(default="", description="整体预期结果，用例最终预期达成的可验证结果")
    bdd_content: str = Field(default="", description="BDD Gherkin 格式内容，如 Feature/Scenario/Given/When/Then，非必填")


class TestCaseList(BaseModel):
    """用例列表输出"""
    cases: List[TestCaseItem] = Field(description="测试用例列表")


CASE_GENERATOR_PROMPT = """请根据以下需求描述，生成全面、专业的测试用例。

## 需求信息
- 需求标题：{requirement_title}
- 所属项目：{project_name}
- 已有用例数：{existing_count}

## 需求描述
{requirement_content}

## 生成要求
1. 覆盖以下场景类型：
   - 正向场景（正常流程）
   - 异常场景（错误输入、异常操作）
   - 边界条件（最大值、最小值、空值、超长等）
   - 替代流程（备选路径）
2. 优先级分级（priority 字段）：
   - P0：核心主流程，必须通过
   - P1：重要功能，高优先级
   - P2：一般功能，中优先级
   - P3：边缘场景，低优先级
3. 用例类型（case_type 字段）：
   - functional：功能测试用例（默认）
   - performance：性能测试用例
   - security：安全测试用例
4. 每条用例必须包含以下字段：
   - title：用例名称，简洁明确，不超过200字符
   - module：所属模块，根据需求功能模块划分（如"登录模块"、"用户管理"等）
   - priority：优先级，P0/P1/P2/P3
   - case_type：用例类型，functional/performance/security
   - preconditions：前置条件，执行用例前需要满足的环境和数据准备
   - steps：测试步骤数组，每个步骤是一个对象，包含：
     - action：操作描述（如"输入用户名admin"、"点击登录按钮"）
     - expected：该步骤的预期结果（如"用户名输入框显示admin"、"跳转到首页"）
   - expected_result：整体预期结果，用例最终预期达成的可验证结果
   - bdd_content：BDD Gherkin 格式内容（可选），使用 Given/When/Then 语法描述
5. 步骤清晰可执行，每步包含操作描述和该步预期
6. 预期结果明确可验证
7. 生成 {count} 条用例，确保覆盖全面且不重复
8. 根据已有用例数避免生成重复场景
"""

DEFAULT_SYSTEM_PROMPT = """你是一名资深软件测试工程师，拥有丰富的测试用例设计经验。你的任务是根据需求描述生成全面、专业、可执行的测试用例。

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
- 覆盖正向场景（正常流程）、异常场景（错误输入、异常操作）、边界条件（最大值、最小值、空值、超长）、替代流程（备选路径）
- 优先级分级：P0（核心主流程）、P1（重要功能）、P2（一般功能）、P3（边缘场景）
- 用例类型：functional（功能测试）、performance（性能测试）、security（安全测试）
- 每条用例必须包含：title（简洁明确，不超过200字）、module（按功能模块划分）、priority、case_type、preconditions（环境和数据准备）、steps（每步含 action 和 expected）、expected_result（可验证的最终结果）
- 步骤清晰可执行，预期结果明确可验证
- 根据已有用例数避免生成重复场景
- 所有内容使用中文"""


class CaseGeneratorAgent(BaseAgent):
    """用例生成 Agent"""

    def __init__(self, db_session=None, llm_config_id: Optional[int] = None, project_id: Optional[int] = None):
        super().__init__(db_session, agent_name="case_generator", project_id=project_id, llm_config_id=llm_config_id)

    def run(self, **kwargs) -> Dict[str, Any]:
        """BaseAgent 抽象方法实现"""
        requirement_content = kwargs.get("requirement_content", "")
        count = kwargs.get("count", 10)
        result = self.generate(requirement_content, count)
        return result

    def generate(
        self,
        requirement_content: str,
        count: int = 10,
        requirement_title: str = "",
        project_name: str = "",
        existing_count: int = 0,
        system_prompt: str = "",
    ) -> Dict[str, Any]:
        """
        生成测试用例

        Args:
            requirement_content: 需求描述文本
            count: 期望生成的用例数量
            requirement_title: 需求标题
            project_name: 项目名称
            existing_count: 已有用例数量
            system_prompt: 自定义 system 提示词（来自 Prompt 管理）

        Returns:
            dict: 包含 cases 列表和 token_usage
        """
        effective_system_prompt = system_prompt.strip() if system_prompt and system_prompt.strip() else DEFAULT_SYSTEM_PROMPT

        # 直接构造消息，system prompt 不经过 .format() 解析，避免其中的 JSON 花括号被当作模板变量
        messages = [
            SystemMessage(content=effective_system_prompt),
            HumanMessage(content=CASE_GENERATOR_PROMPT.format(
                requirement_content=requirement_content,
                count=count,
                requirement_title=requirement_title or "未指定",
                project_name=project_name or "未指定",
                existing_count=existing_count,
            )),
        ]

        _, used_config_id = llm_factory.get_llm_with_fallback(
            self.db, preferred_config_id=self.llm_config_id
        )

        logger.info(f"开始生成用例，需求标题: {requirement_title}, 需求长度: {len(requirement_content)}, 期望数量: {count}")

        response, token_usage, config_id = llm_factory.call_with_fallback(
            self.db,
            messages=messages,
            preferred_config_id=self.llm_config_id,
            max_tokens=8192,
        )

        if token_usage:
            self.token_usage["prompt_tokens"] += token_usage.get("prompt_tokens", 0)
            self.token_usage["completion_tokens"] += token_usage.get("completion_tokens", 0)
            self.token_usage["total_tokens"] += token_usage.get("total_tokens", 0)
        self.llm_config_id = config_id or used_config_id
        self._log_step("llm_call", {"requirement_len": len(requirement_content), "count": count}, "success")

        logger.info(f"用例生成完成，原始输出长度: {len(response.content)}")

        return {
            "raw_content": response.content,
            "token_usage": self.get_token_usage(),
            "llm_config_id": self.llm_config_id,
        }

    # ── 功能点驱动生成 ──────────────────────────────────

    FEATURE_CASE_SYSTEM_PROMPT = """你是一名资深测试工程师。根据给定的单个功能点，生成 3-8 条测试用例。

## 输出规则（最高优先级）
1. 只输出一个 JSON 对象，第一个字符是 {，最后一个字符是 }
2. 禁止输出 markdown 代码块、注释、解释文字
3. 所有字段名必须用英文，绝对不能用中文字段名

## 输出格式
{"cases": [{"title": "用例标题", "module": "模块名", "priority": "P0", "case_type": "functional", "preconditions": "前置条件", "steps": [{"action": "操作", "expected": "预期"}], "expected_result": "结果", "feature_name": "功能点名", "bdd_content": ""}]}

## steps 字段规则
steps 是数组，每个元素必须且只能有两个字段：
- "action"（操作描述，不是"操作描述"）
- "expected"（预期结果，不是"预期结果"）
禁止在 steps 元素中使用中文字段名

## 用例设计
- 覆盖正向、异常、边界场景
- P0 功能点 5-8 条，P1 功能点 3-6 条，P2 功能点 2-4 条，P3 功能点 1-2 条
- 每条用例必须有 title、steps、expected_result 三个核心字段
- 优先级可选：P0、P1、P2、P3
- 类型固定：functional"""

    FEATURE_CASE_HUMAN_TEMPLATE = """## 需求标题
{title}

## 需求内容
{content}

## 本次要生成的功能点
{features_text}

## 已有用例标题（避免重复）
{existing_cases}

请为以上功能点生成测试用例。只输出 JSON，第一个字符是 {{，最后一个字符是 }}。"""

    def generate_by_features(
        self,
        requirement_title: str,
        requirement_content: str,
        features: List[Dict[str, Any]],
        existing_cases: Optional[List[str]] = None,
        system_prompt: str = "",
    ) -> Dict[str, Any]:
        """
        基于功能点生成测试用例 — 按单个功能点逐条调用 LLM，确保每次输出小且可靠。

        每次只给 LLM 一个功能点，生成 3-8 条用例，JSON 输出极小（< 2K tokens），
        从根本上避免截断和格式错乱。
        """
        effective_system_prompt = system_prompt.strip() if system_prompt and system_prompt.strip() else self.FEATURE_CASE_SYSTEM_PROMPT

        logger.info(f"基于功能点生成用例（逐个功能点）: {requirement_title}, 功能点数: {len(features)}")

        all_cases: List[Dict[str, Any]] = []
        all_existing = list(existing_cases or [])
        success_count = 0
        fail_count = 0

        for idx, feat in enumerate(features, 1):
            feat_name = feat.get("name", f"功能点{idx}")
            feat_module = feat.get("module_name", "未分组")
            feat_priority = feat.get("priority", "P1")
            feat_preconditions = feat.get("preconditions", "")

            logger.info(f"生成功能点 [{idx}/{len(features)}]: {feat_name} (模块: {feat_module})")

            # 构建单个功能点的文本
            methods = feat.get("design_methods", [])
            if isinstance(methods, str):
                methods_str = methods
            else:
                methods_str = "、".join(methods) if methods else "等价类划分、边界值分析、场景法"

            features_text = f"""**功能点：{feat_name}**（优先级：{feat_priority}）
- 模块：{feat_module}
- 描述：{feat.get('description', '无')}
- 建议设计方法：{methods_str}
- 前置条件：{feat_preconditions or '无'}"""

            existing_text = "无" if not all_existing else "\n".join(f"- {t}" for t in all_existing[:20])

            messages = [
                SystemMessage(content=effective_system_prompt),
                HumanMessage(content=self.FEATURE_CASE_HUMAN_TEMPLATE.format(
                    title=requirement_title or "未命名需求",
                    content=requirement_content or "（无详细内容）",
                    features_text=features_text,
                    existing_cases=existing_text,
                )),
            ]

            try:
                response, token_usage, config_id = llm_factory.call_with_fallback(
                    self.db,
                    messages=messages,
                    preferred_config_id=self.llm_config_id,
                    temperature=0.3,
                    max_tokens=4096,
                )

                if token_usage:
                    self.token_usage["prompt_tokens"] += token_usage.get("prompt_tokens", 0)
                    self.token_usage["completion_tokens"] += token_usage.get("completion_tokens", 0)
                    self.token_usage["total_tokens"] += token_usage.get("total_tokens", 0)
                self.llm_config_id = config_id or self.llm_config_id

                raw = response.content if hasattr(response, "content") else str(response)
                logger.info(f"功能点 [{feat_name}] LLM 输出长度: {len(raw)}")

                # 解析并修复用例
                feat_cases = self._parse_and_repair_cases(raw, feat_name, feat_module, feat_priority, feat_preconditions)

                if feat_cases:
                    all_cases.extend(feat_cases)
                    all_existing.extend(c.get("title", "") for c in feat_cases)
                    success_count += 1
                    logger.info(f"功能点 [{feat_name}] 成功: {len(feat_cases)} 条用例")
                else:
                    fail_count += 1
                    logger.warning(f"功能点 [{feat_name}] 解析失败，尝试重试")

                    # 重试一次
                    retry_messages = [
                        SystemMessage(content=effective_system_prompt),
                        HumanMessage(content=self.FEATURE_CASE_HUMAN_TEMPLATE.format(
                            title=requirement_title or "未命名需求",
                            content=requirement_content or "（无详细内容）",
                            features_text=features_text,
                            existing_cases=existing_text,
                        )),
                        HumanMessage(content="上一次输出格式有误。请重新输出完整的 JSON。确保 steps 中每个元素用 action 和 expected 两个英文键名。"),
                    ]
                    retry_response, retry_usage, _ = llm_factory.call_with_fallback(
                        self.db,
                        messages=retry_messages,
                        preferred_config_id=self.llm_config_id,
                        temperature=0.3,
                        max_tokens=4096,
                    )
                    if retry_usage:
                        self.token_usage["prompt_tokens"] += retry_usage.get("prompt_tokens", 0)
                        self.token_usage["completion_tokens"] += retry_usage.get("completion_tokens", 0)
                        self.token_usage["total_tokens"] += retry_usage.get("total_tokens", 0)
                    raw = retry_response.content if hasattr(retry_response, "content") else str(retry_response)
                    feat_cases = self._parse_and_repair_cases(raw, feat_name, feat_module, feat_priority, feat_preconditions)
                    if feat_cases:
                        all_cases.extend(feat_cases)
                        all_existing.extend(c.get("title", "") for c in feat_cases)
                        success_count += 1
                        logger.info(f"功能点 [{feat_name}] 重试成功: {len(feat_cases)} 条用例")
                    else:
                        logger.warning(f"功能点 [{feat_name}] 重试仍失败，跳过")

            except Exception as e:
                fail_count += 1
                logger.error(f"功能点 [{feat_name}] 生成异常: {e}")

        logger.info(f"全部功能点生成完成: 成功 {success_count}/{len(features)}, 失败 {fail_count}, 共 {len(all_cases)} 条用例")

        return {
            "raw_content": json.dumps({"cases": all_cases}, ensure_ascii=False),
            "cases": all_cases,
            "token_usage": self.get_token_usage(),
            "llm_config_id": self.llm_config_id,
            "feature_count": len(features),
            "success_count": success_count,
            "fail_count": fail_count,
        }

    @staticmethod
    def _parse_and_repair_cases(
        raw: str,
        feat_name: str,
        feat_module: str,
        feat_priority: str,
        feat_preconditions: str,
    ) -> List[Dict[str, Any]]:
        """解析 LLM 输出并修复常见格式问题，逐条校验，丢弃无效用例。"""
        from app.agents.utils import extract_json

        parsed = extract_json(raw)
        if not parsed:
            # 尝试直接 json.loads（可能是纯数组）
            try:
                parsed = json.loads(raw.strip())
            except json.JSONDecodeError:
                pass

        raw_cases = []
        if isinstance(parsed, dict):
            raw_cases = parsed.get("cases") or parsed.get("用例") or []
        elif isinstance(parsed, list):
            raw_cases = parsed

        if not raw_cases:
            return []

        # 中文字段名 → 英文
        field_map = {
            "操作描述": "action", "操作": "action", "步骤": "action",
            "预期结果": "expected", "预期": "expected", "期望": "expected",
            "标题": "title", "用例名称": "title", "用例标题": "title",
            "模块": "module", "模块名": "module", "模块名称": "module",
            "优先级": "priority", "类型": "case_type", "用例类型": "case_type",
            "前置条件": "preconditions",
            "整体预期结果": "expected_result", "预期最终结果": "expected_result",
            "功能点": "feature_name", "功能点名称": "feature_name",
        }

        valid_cases = []
        for c in raw_cases:
            if not isinstance(c, dict):
                continue

            # 修复顶层字段名
            repaired = {}
            for k, v in c.items():
                repaired[field_map.get(k, k)] = v

            # 修复 steps 中的中文字段名
            steps = repaired.get("steps", [])
            if isinstance(steps, list):
                fixed_steps = []
                for s in steps:
                    if isinstance(s, dict):
                        fixed = {}
                        for k, v in s.items():
                            fixed[field_map.get(k, k)] = v
                        fixed_steps.append(fixed)
                    elif isinstance(s, str):
                        # 如果 step 是纯字符串，尝试拆分为 action/expected
                        fixed_steps.append({"action": s, "expected": ""})
                repaired["steps"] = fixed_steps

            # 补充缺失字段
            if not repaired.get("title"):
                repaired["title"] = f"{feat_name} - 用例{len(valid_cases) + 1}"
            if not repaired.get("module"):
                repaired["module"] = feat_module
            if not repaired.get("priority"):
                repaired["priority"] = feat_priority
            if not repaired.get("case_type"):
                repaired["case_type"] = "functional"
            if not repaired.get("preconditions"):
                repaired["preconditions"] = feat_preconditions
            if not repaired.get("feature_name"):
                repaired["feature_name"] = feat_name
            if not repaired.get("expected_result"):
                # 从 steps 最后一步的 expected 取
                if repaired["steps"] and isinstance(repaired["steps"][-1], dict):
                    repaired["expected_result"] = repaired["steps"][-1].get("expected", "")
            if not repaired.get("bdd_content"):
                repaired["bdd_content"] = ""

            # 确保 steps 每个元素有 action 和 expected
            for s in repaired["steps"]:
                if not isinstance(s, dict):
                    continue
                if "action" not in s:
                    s["action"] = str(s.get("操作", s.get("操作描述", "")))
                if "expected" not in s:
                    s["expected"] = str(s.get("预期结果", s.get("预期", "")))
                # 清理多余的中文键
                for cn_key in ["操作描述", "操作", "步骤", "预期结果", "预期", "期望"]:
                    s.pop(cn_key, None)

            # 校验：至少有 title
            if repaired.get("title") and len(repaired.get("title", "")) > 0:
                valid_cases.append(repaired)

        return valid_cases
