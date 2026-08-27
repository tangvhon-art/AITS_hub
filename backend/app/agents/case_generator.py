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


CASE_GENERATOR_PROMPT = """请根据以下需求描述，生成全面、专业、无重复的测试用例。

## 需求信息
- 需求标题：{requirement_title}
- 所属项目：{project_name}
- 已有用例数：{existing_count}

## 需求描述
{requirement_content}

## 输出格式（最高优先级，强制执行）
仅输出一个合法的 JSON 对象，**禁止输出任何前言、解释、思考过程、Markdown代码块、注释文字**。
根key固定为 "cases"，值为用例数组。
数组中每条用例为独立对象，所有字段严格按照下方定义生成。

## 字段强制约束
每条用例必须包含全部字段：title、module、priority、case_type、preconditions、steps、expected_result、bdd_content，不可缺省。
1. title：用例名称，简洁明确，不超过200字符；命名建议：测试完整XX流程 / 异常场景‑XX / 边界值‑XX；禁止标题重复。
2. module：所属模块，根据需求自行划分（如"登录模块"、"用户管理"）；模块名称用词统一。
3. priority：优先级，**仅允许枚举值**：P0 / P1 / P2 / P3
    - P0：核心主流程，必须通过
    - P1：重要功能，高优先级
    - P2：一般功能，中优先级
    - P3：边缘场景，低优先级
4. case_type：用例类型，**仅允许枚举值**：functional / performance / security；默认优先 functional；性能、安全场景按需生成。
5. preconditions：前置条件，执行用例前需要满足的环境、账号、数据准备；无特殊前置条件填写字符串"无"，禁止留空。
6. steps：测试步骤数组；数组内每一步为对象，必须包含 action、expected 两个字段；
    - action：单步操作描述；
    - expected：该步骤对应的单步预期现象；
    - 操作与预期一一对应，不可出现步骤多、预期少的失衡情况；
    - 至少1条步骤。
7. expected_result：整体预期结果，用例最终达成的可验证结果，一句话总结最终状态。
8. bdd_content：BDD Gherkin 格式内容，使用 Given‑When‑Then 语法；若不需要也不能省略字段，无内容时值填空字符串 ""。

示例单条用例结构参考：
{
  "cases": [
    {
      "title": "测试完整登录流程",
      "module": "登录模块",
      "priority": "P0",
      "case_type": "functional",
      "preconditions": "进入登录页面，已注册测试账号",
      "steps": [
        {
          "action": "输入用户名admin",
          "expected": "输入框正确回显admin"
        },
        {
          "action": "输入密码admin123，点击登录按钮",
          "expected": "无表单校验报错，页面跳转"
        }
      ],
      "expected_result": "登录成功，跳转到系统首页",
      "bdd_content": "Given 用户进入登录页面\nWhen 输入正确用户名与密码并点击登录\nThen 用户登录成功进入首页"
    }
  ]
}

JSON语法约束：
1. 输出第一个字符必须是 {，最后一个字符必须是 }；
2. 禁止尾部多余逗号；
3. 字符串内换行使用 \n 转义；
4. 所有字段名使用英文双引号包裹；
5. 禁止数组元素写成普通字符串，steps子项必须为对象。

## 生成要求
1. 覆盖以下场景类型：
   - 正向场景（正常流程）
   - 异常场景（错误输入、异常操作、非法参数、权限异常）
   - 边界条件（最大值、最小值、空值、超长文本、特殊字符）
   - 替代流程（备选路径）
2. 优先级分级严格按照枚举规则分配；核心主流程优先分配P0；
3. 用例类型按需生成，功能用例为主，高风险点补充安全/性能用例；
4. 步骤清晰可执行，每步包含操作描述和该步预期；
5. 预期结果明确、可验证，禁止模糊描述；
6. 生成 {count} 条用例，确保场景覆盖全面，用例之间不能重复、不能高度相似；
7. 参考已有用例数量 {existing_count}，主动规避已经覆盖过的场景，不再重复产出相同测试点；
8. 功能点较多时，均匀拆分到多条用例，不要单条用例塞入过多场景。
"""

DEFAULT_SYSTEM_PROMPT = """你是一名资深测试工程师（具备 ISTQB 等专业测试知识体系），精通等价类划分、边界值分析、错误推测、场景法、判定表等黑盒测试设计方法。你的任务是根据需求和功能点，生成高质量、可执行的测试用例。

## 输出格式（最高优先级，强制执行）
**仅输出 Markdown 表格，禁止输出任何前言、解释、思考过程、标题、注释，禁止使用 ```markdown 代码块包裹表格。**
表格固定表头：
| title | module | priority | preconditions | action | expected | expected_result | feature_name |
|-------|--------|----------|---------------|--------|----------|-----------------|--------------|

### 字段释义（严格遵守）
1. title：测试场景标题；格式：场景类型‑具体描述，示例：测试完整注册流程、异常场景‑输入空用户名、边界值‑用户名长度超过最大值16
2. module：所属模块，严格使用用户提供模块名称，不可自行新增模块
3. priority：优先级，仅允许取值 P0/P1/P2/P3；P0核心主流程、P1重要异常、P2次要场景、P3低优优化场景
4. preconditions：执行该用例前置条件；无特殊前置条件填写「无」，禁止留空
5. action：操作步骤，多条步骤必须使用 1.  2.  3. 有序编号，步骤清晰完整
6. expected：分步预期现象，必须和 action 操作步骤一一对应编号，1条操作对应1条预期现象
7. expected_result：最终执行结果（一句话总结最终状态，如注册成功、提示用户名已存在）
8. feature_name：绑定当前功能点名，不可错分到其他功能点

单元格内**禁止出现竖线 | 字符**，避免表格解析错乱。

示例参考：
| title | module | priority | preconditions | action | expected | expected_result | feature_name |
|-------|--------|----------|---------------|--------|----------|-----------------|--------------|
| 测试完整注册流程 | 注册校验 | P0 | 进入注册页 | 1. 打开注册页面 2. 输入用户名admin 3. 输入密码admin123 4. 点击注册按钮 | 1. 页面正常加载 2. 用户名输入框无错误提示 3. 密码输入框无错误提示 4. 注册成功跳转到首页 | 注册成功 | 用户名校验 |
| 异常场景‑输入已存在用户名注册 | 注册校验 | P1 | 进入注册页 | 1. 打开注册页面 2. 输入已注册用户名admin 3. 输入密码admin123 4. 点击注册按钮 | 1. 页面正常加载 2. 用户名输入框下方显示用户名已存在 3. 密码输入框无错误提示 4. 注册失败停留在注册页 | 阻止提交并提示用户名已存在 | 用户名校验 |
| 边界值‑用户名长度5位(低于最小值6) | 注册校验 | P1 | 进入注册页 | 1. 打开注册页面 2. 输入5位用户名abc12 3. 点击注册按钮 | 1. 页面正常加载 2. 用户名输入框提示长度需6‑16位 | 阻止提交并提示长度限制 | 用户名校验 |

## 测试设计方法（行业标准）
根据需求特点选择合适的方法设计用例，确保覆盖充分、无重复：
1. 等价类划分：将输入域划分为有效/无效等价类，每个等价类至少设计 1 条用例
2. 边界值分析：重点测试最小值、最大值、临界值、超限值（长度上下限±1、数值边界）
3. 错误推测：基于经验推测常见错误（空值、特殊字符、格式错误、未登录访问、重复提交等）
4. 场景法：覆盖主流程（Happy Path）、备选流程、异常流程
5. 判定表：存在多个条件组合时，确保条件组合覆盖完整（如"已登录且有权限/已登录无权限/未登录"）

## 生成规则
1. 只输出表格，不要输出任何标题、额外文字、代码块标记；输出第一个字符为 |
2. 每行一条用例，字段之间用 | 分隔；所有单元格内容不能出现换行
3. action 和 expected 必须包含完整的操作步骤，用 1. 2. 3. 编号，每个步骤之间用空格分隔
4. action 和 expected 的步骤编号一一对应，操作几步预期就几步，不可数量失衡
5. 优先级只能使用 P0/P1/P2/P3
6. module 和 feature_name 必须严格使用给定的模块名、功能点名，不可自行修改、新增
7. 单个功能点生成 3‑8 条用例；覆盖正向主流程、异常输入、边界极值、空值输入、特殊字符、超长文本等场景
8. title 必须是有意义的测试场景标题，格式为：测试场景类型+具体描述，如 测试完整登录流程、异常场景‑输入空用户名、边界值‑用户名长度超过最大值16
9. 禁止产出重复、高度相似的测试用例
10. 预期结果必须可验证：明确到具体的界面提示、页面跳转、数据状态，禁止使用"正常""正确"等模糊描述
11. 用例应互相独立、可单独执行，避免用例之间存在状态依赖"""


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

    FEATURE_CASE_SYSTEM_PROMPT = """你是一名资深测试工程师（具备 ISTQB 等专业测试知识体系），精通等价类划分、边界值分析、错误推测、场景法、判定表等黑盒测试设计方法。你的任务是根据需求和功能点，生成高质量、可执行的测试用例。

## 输出格式（最高优先级，强制执行）
**仅输出 Markdown 表格，禁止输出任何前言、解释、思考过程、标题、注释，禁止使用 ```markdown 代码块包裹表格。**
表格固定表头：
| title | module | priority | preconditions | action | expected | expected_result | feature_name |
|-------|--------|----------|---------------|--------|----------|-----------------|--------------|

### 字段释义（严格遵守）
1. title：测试场景标题；格式：场景类型‑具体描述，示例：测试完整注册流程、异常场景‑输入空用户名、边界值‑用户名长度超过最大值16
2. module：所属模块，严格使用用户提供模块名称，不可自行新增模块
3. priority：优先级，仅允许取值 P0/P1/P2/P3；P0核心主流程、P1重要异常、P2次要场景、P3低优优化场景
4. preconditions：执行该用例前置条件；无特殊前置条件填写「无」，禁止留空
5. action：操作步骤，多条步骤必须使用 1.  2.  3. 有序编号，步骤清晰完整
6. expected：分步预期现象，必须和 action 操作步骤一一对应编号，1条操作对应1条预期现象
7. expected_result：最终执行结果（一句话总结最终状态，如注册成功、提示用户名已存在）
8. feature_name：绑定当前功能点名，不可错分到其他功能点

单元格内**禁止出现竖线 | 字符**，避免表格解析错乱。

示例参考：
| title | module | priority | preconditions | action | expected | expected_result | feature_name |
|-------|--------|----------|---------------|--------|----------|-----------------|--------------|
| 测试完整注册流程 | 注册校验 | P0 | 进入注册页 | 1. 打开注册页面 2. 输入用户名admin 3. 输入密码admin123 4. 点击注册按钮 | 1. 页面正常加载 2. 用户名输入框无错误提示 3. 密码输入框无错误提示 4. 注册成功跳转到首页 | 注册成功 | 用户名校验 |
| 异常场景‑输入已存在用户名注册 | 注册校验 | P1 | 进入注册页 | 1. 打开注册页面 2. 输入已注册用户名admin 3. 输入密码admin123 4. 点击注册按钮 | 1. 页面正常加载 2. 用户名输入框下方显示用户名已存在 3. 密码输入框无错误提示 4. 注册失败停留在注册页 | 阻止提交并提示用户名已存在 | 用户名校验 |
| 边界值‑用户名长度5位(低于最小值6) | 注册校验 | P1 | 进入注册页 | 1. 打开注册页面 2. 输入5位用户名abc12 3. 点击注册按钮 | 1. 页面正常加载 2. 用户名输入框提示长度需6‑16位 | 阻止提交并提示长度限制 | 用户名校验 |

## 测试设计方法（行业标准）
根据需求特点选择合适的方法设计用例，确保覆盖充分、无重复：
1. 等价类划分：将输入域划分为有效/无效等价类，每个等价类至少设计 1 条用例
2. 边界值分析：重点测试最小值、最大值、临界值、超限值（长度上下限±1、数值边界）
3. 错误推测：基于经验推测常见错误（空值、特殊字符、格式错误、未登录访问、重复提交等）
4. 场景法：覆盖主流程（Happy Path）、备选流程、异常流程
5. 判定表：存在多个条件组合时，确保条件组合覆盖完整（如"已登录且有权限/已登录无权限/未登录"）

## 生成规则
1. 只输出表格，不要输出任何标题、额外文字、代码块标记；输出第一个字符为 |
2. 每行一条用例，字段之间用 | 分隔；所有单元格内容不能出现换行
3. action 和 expected 必须包含完整的操作步骤，用 1. 2. 3. 编号，每个步骤之间用空格分隔
4. action 和 expected 的步骤编号一一对应，操作几步预期就几步，不可数量失衡
5. 优先级只能使用 P0/P1/P2/P3
6. module 和 feature_name 必须严格使用给定的模块名、功能点名，不可自行修改、新增
7. 单个功能点生成 3‑8 条用例；覆盖正向主流程、异常输入、边界极值、空值输入、特殊字符、超长文本等场景
8. title 必须是有意义的测试场景标题，格式为：测试场景类型+具体描述，如 测试完整登录流程、异常场景‑输入空用户名、边界值‑用户名长度超过最大值16
9. 禁止产出重复、高度相似的测试用例
10. 预期结果必须可验证：明确到具体的界面提示、页面跳转、数据状态，禁止使用"正常""正确"等模糊描述
11. 用例应互相独立、可单独执行，避免用例之间存在状态依赖"""

    FEATURE_CASE_HUMAN_TEMPLATE = """## 需求：{title}

{content}

## 功能点列表
{features_text}

## 已有用例（避免重复）
{existing_cases}

请为以上所有功能点生成测试用例，输出 Markdown 表格。"""

    def generate_by_features(
        self,
        requirement_title: str,
        requirement_content: str,
        features: List[Dict[str, Any]],
        existing_cases: Optional[List[str]] = None,
        system_prompt: str = "",
        progress_callback=None,
    ) -> Dict[str, Any]:
        """
        基于功能点生成测试用例 — 单次 LLM 调用，输出 Markdown 表格，程序解析。

        一次调用所有功能点，LLM 输出 Markdown 表格格式（比 JSON 可靠得多），
        程序按行解析为用例对象。即使输出中途断开，已输出的行全部可用。
        """
        effective_system_prompt = system_prompt.strip() if system_prompt and system_prompt.strip() else self.FEATURE_CASE_SYSTEM_PROMPT

        logger.info(f"基于功能点生成用例（Markdown 单次调用）: {requirement_title}, 功能点数: {len(features)}")

        # 构建功能点文本
        lines = []
        for feat in features:
            methods = feat.get("design_methods", [])
            if isinstance(methods, str):
                methods_str = methods
            else:
                methods_str = "、".join(methods) if methods else "等价类划分、边界值分析、场景法"
            lines.append(f"- 模块[{feat.get('module_name', '未分组')}] 功能点[{feat.get('name', '')}] 优先级[{feat.get('priority', 'P1')}]")
            if feat.get("description"):
                lines.append(f"  描述：{feat['description']}")
            lines.append(f"  设计方法：{methods_str}")
            if feat.get("preconditions"):
                lines.append(f"  前置：{feat['preconditions']}")
        features_text = "\n".join(lines)

        existing_text = "无" if not existing_cases else "\n".join(f"- {t}" for t in existing_cases[:30])

        messages = [
            SystemMessage(content=effective_system_prompt),
            HumanMessage(content=self.FEATURE_CASE_HUMAN_TEMPLATE.format(
                title=requirement_title or "未命名需求",
                content=requirement_content or "（无详细内容）",
                features_text=features_text,
                existing_cases=existing_text,
            )),
        ]

        if progress_callback:
            try:
                progress_callback(0, 1, "LLM 调用中", 0)
            except Exception:
                pass

        response, token_usage, config_id = llm_factory.call_with_fallback(
            self.db,
            messages=messages,
            preferred_config_id=self.llm_config_id,
            temperature=0.3,
            max_tokens=8192,
        )

        if token_usage:
            self.token_usage["prompt_tokens"] += token_usage.get("prompt_tokens", 0)
            self.token_usage["completion_tokens"] += token_usage.get("completion_tokens", 0)
            self.token_usage["total_tokens"] += token_usage.get("total_tokens", 0)
        self.llm_config_id = config_id or self.llm_config_id

        raw = response.content if hasattr(response, "content") else str(response)
        logger.info(f"Markdown 用例生成完成, 输出长度: {len(raw)}, tokens: {token_usage}, config: {config_id}")

        # 解析 Markdown 表格
        all_cases = self._parse_markdown_cases(raw, features)

        if progress_callback:
            try:
                progress_callback(1, 1, "完成", len(all_cases))
            except Exception:
                pass

        logger.info(f"Markdown 解析完成: {len(all_cases)} 条用例")

        return {
            "raw_content": raw,
            "cases": all_cases,
            "token_usage": self.get_token_usage(),
            "llm_config_id": self.llm_config_id,
            "feature_count": len(features),
            "success_count": 1 if all_cases else 0,
            "fail_count": 0 if all_cases else 1,
        }

    @staticmethod
    def _parse_markdown_cases(raw: str, features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """解析 Markdown 表格为用例列表。即使输出被截断，已解析的行全部保留。"""
        if not raw or not raw.strip():
            logger.warning("Markdown 解析: raw 为空")
            return []

        # 去除 markdown 代码块包裹
        text = raw.strip()
        if text.startswith("```"):
            lines_temp = text.split("\n")
            # 去掉第一行 ```markdown 和最后的 ```
            if lines_temp and lines_temp[0].strip().startswith("```"):
                lines_temp = lines_temp[1:]
            if lines_temp and lines_temp[-1].strip() == "```":
                lines_temp = lines_temp[:-1]
            text = "\n".join(lines_temp)

        lines = text.strip().split("\n")

        # 找到表头行（含 | 且含 title 或 标题 的行）
        header_idx = -1
        for i, line in enumerate(lines):
            lower = line.lower().strip()
            if "|" in lower and ("title" in lower or "标题" in lower or "用例" in lower):
                header_idx = i
                break

        if header_idx == -1:
            # 宽松匹配：任何含 | 的行
            for i, line in enumerate(lines):
                if line.strip().startswith("|") and line.count("|") >= 3:
                    header_idx = i
                    break

        if header_idx == -1:
            logger.warning(f"Markdown 解析: 未找到表头行, raw 前200字符: {repr(text[:200])}")
            # 最后兜底：尝试 JSON 解析
            from app.agents.utils import extract_json
            parsed = extract_json(raw)
            if parsed and isinstance(parsed, dict):
                raw_cases = parsed.get("cases") or []
                if raw_cases:
                    logger.info(f"Markdown 解析失败，JSON 兜底成功: {len(raw_cases)} 条")
                    return raw_cases
            return []

        # 解析表头列顺序
        header_cells = [c.strip() for c in lines[header_idx].split("|")]
        header_cells = [c for c in header_cells if c]  # 去空

        # 列名映射（中英文）
        col_map = {
            "title": "title", "标题": "title", "用例标题": "title", "用例名称": "title",
            "module": "module", "模块": "module", "模块名": "module",
            "priority": "priority", "优先级": "priority",
            "preconditions": "preconditions", "前置条件": "preconditions", "前置": "preconditions",
            "action": "action", "操作": "action", "操作描述": "action", "步骤": "action",
            "expected": "expected", "预期": "expected", "预期结果": "expected",
            "expected_result": "expected_result", "整体预期": "expected_result", "最终结果": "expected_result",
            "feature_name": "feature_name", "功能点": "feature_name", "功能点名": "feature_name",
            "case_type": "case_type", "类型": "case_type",
        }

        col_order = []
        for cell in header_cells:
            col_order.append(col_map.get(cell.lower().strip(), cell.lower().strip()))

        # 构建 feature_name → module 映射
        feat_module_map = {}
        default_module = "未分组"
        for f in features:
            feat_module_map[f.get("name", "")] = f.get("module_name", "未分组")
        if features:
            default_module = features[0].get("module_name", "未分组")

        # 解析数据行（跳过分隔行 |---|）
        cases = []
        for line in lines[header_idx + 1:]:
            stripped = line.strip()
            if not stripped or not stripped.startswith("|"):
                continue
            # 跳过分隔行
            if stripped.replace("|", "").replace("-", "").replace(" ", "").replace(":", "") == "":
                continue

            cells = [c.strip() for c in stripped.split("|")]
            # 去掉首尾由 | 分隔符产生的空元素（只去一个，保留中间的空单元格以防列错位）
            if cells and cells[0] == "":
                cells.pop(0)
            if cells and cells[-1] == "":
                cells.pop(-1)

            if len(cells) < 3:
                continue

            # 数据行单元格数少于表头列数时，尝试检测缺失列并补位
            # 常见场景：LLM 漏了 module 列的值，导致 priority 值错位到 module 位置
            if len(cells) < len(col_order):
                for _i, _col in enumerate(col_order):
                    if _i >= len(cells):
                        break
                    _val = cells[_i].strip().upper()
                    # module 位置的值是 P0-P3，说明 module 列缺失
                    if _col == "module" and _val in ("P0", "P1", "P2", "P3"):
                        cells.insert(_i, "")
                        logger.info(f"检测到数据行缺失 module 列，已补位空值，行: {stripped[:80]}")
                        break

            # 按列顺序映射
            case = {}
            for i, col_name in enumerate(col_order):
                if i < len(cells):
                    case[col_name] = cells[i]

            # 跳过表头行被误判为数据行：title 值为已知列名（如 module/priority/preconditions 等）
            _all_col_names = set(col_map.keys()) | set(col_map.values())
            _title_val = str(case.get("title", "")).strip().lower()
            if _title_val and _title_val in _all_col_names:
                continue

            # 如果列数不匹配，按位置兜底
            if "title" not in case and len(cells) > 0:
                case["title"] = cells[0]
            if "action" not in case and len(cells) > 4:
                case["action"] = cells[4]
            if "expected" not in case and len(cells) > 5:
                case["expected"] = cells[5]

            # 补充默认字段
            if not case.get("title"):
                continue
            if not case.get("module"):
                case["module"] = feat_module_map.get(case.get("feature_name", ""), default_module)
            if not case.get("priority"):
                case["priority"] = "P2"
            if not case.get("case_type"):
                case["case_type"] = "functional"
            if not case.get("preconditions"):
                case["preconditions"] = ""
            if not case.get("feature_name"):
                case["feature_name"] = features[0].get("name", "") if features else ""
            if not case.get("expected_result"):
                case["expected_result"] = case.get("expected", "")
            if not case.get("bdd_content"):
                case["bdd_content"] = ""

            # 构建 steps — 将编号步骤拆分为多步骤列表
            action_str = case.get("action", "")
            expected_str = case.get("expected", "")
            case["steps"] = CaseGeneratorAgent._build_steps(action_str, expected_str)

            # 清理多余的中间字段
            for k in ["action", "expected"]:
                pass  # 保留在 case 里也可以，create_test_cases 不依赖

            cases.append(case)

        logger.info(f"Markdown 表格解析: 表头 {len(col_order)} 列, 数据 {len(cases)} 行")
        return cases

    @staticmethod
    def _build_steps(action_str: str, expected_str: str) -> List[Dict[str, str]]:
        """将编号操作步骤拆分为 steps 列表。

        输入: "1. 打开页面 2. 输入用户名 3. 点击提交", "1. 页面加载 2. 无错误 3. 提交成功"
        输出: [{"action": "打开页面", "expected": "页面加载"}, {"action": "输入用户名", "expected": "无错误"}, ...]
        """
        import re

        # 按编号拆分: "1. xxx 2. yyy" → ["xxx", "yyy"]
        def split_numbered(text: str) -> List[str]:
            if not text:
                return []
            # 匹配 "1. " 或 "1、" 开头的编号
            parts = re.split(r'\d+\.\s*|\d+、\s*', text)
            return [p.strip() for p in parts if p.strip()]

        actions = split_numbered(action_str)
        expecteds = split_numbered(expected_str)

        if not actions:
            return [{"action": action_str.strip(), "expected": expected_str.strip()}]

        steps = []
        for i, act in enumerate(actions):
            exp = expecteds[i] if i < len(expecteds) else ""
            steps.append({"action": act, "expected": exp})
        return steps
