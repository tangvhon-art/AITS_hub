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

DEFAULT_SYSTEM_PROMPT = """你是一名资深测试工程师。根据需求和功能点，生成测试用例。

## 输出格式（最高优先级）
输出 Markdown 表格，不要输出任何其他内容。第一行是表头，之后每行一条用例。

| title | module | priority | preconditions | action | expected | expected_result | feature_name |
|-------|--------|----------|---------------|--------|----------|-----------------|--------------|
| 测试完整注册流程 | 注册校验 | P0 | 进入注册页 | 1. 打开注册页面 2. 输入用户名admin 3. 输入密码admin123 4. 点击注册按钮 | 1. 页面正常加载 2. 用户名输入框无错误提示 3. 密码输入框无错误提示 4. 注册成功跳转到首页 | 注册成功 | 用户名校验 |
| 异常场景-输入已存在用户名注册 | 注册校验 | P1 | 进入注册页 | 1. 打开注册页面 2. 输入已注册用户名admin 3. 输入密码admin123 4. 点击注册按钮 | 1. 页面正常加载 2. 用户名输入框下方显示用户名已存在 3. 密码输入框无错误提示 4. 注册失败停留在注册页 | 阻止提交并提示用户名已存在 | 用户名校验 |
| 边界值-用户名长度5位(低于最小值6) | 注册校验 | P1 | 进入注册页 | 1. 打开注册页面 2. 输入5位用户名abc12 3. 点击注册按钮 | 1. 页面正常加载 2. 用户名输入框提示长度需6-16位 | 阻止提交并提示长度限制 | 用户名校验 |

## 规则
1. 只输出表格，不要输出标题、解释、代码块标记
2. 每行一条用例，字段用 | 分隔
3. action 和 expected 必须包含完整的操作步骤，用 1. 2. 3. 编号，每个步骤之间用空格分隔
4. action 和 expected 的步骤要一一对应
5. 优先级用 P0/P1/P2/P3
6. module 和 feature_name 必须使用给定的模块名和功能点名
7. 每个功能点生成 3-8 条用例，覆盖正向/异常/边界
8. title 必须是有意义的测试场景标题，格式为：测试场景类型+具体描述，如 测试完整登录流程、异常场景-输入空用户名、边界值-用户名长度超过最大值16"""


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

    FEATURE_CASE_SYSTEM_PROMPT = """你是一名资深测试工程师。根据需求和功能点，生成测试用例。

## 输出格式（最高优先级）
输出 Markdown 表格，不要输出任何其他内容。第一行是表头，之后每行一条用例。

| title | module | priority | preconditions | action | expected | expected_result | feature_name |
|-------|--------|----------|---------------|--------|----------|-----------------|--------------|
| 测试完整注册流程 | 注册校验 | P0 | 进入注册页 | 1. 打开注册页面 2. 输入用户名admin 3. 输入密码admin123 4. 点击注册按钮 | 1. 页面正常加载 2. 用户名输入框无错误提示 3. 密码输入框无错误提示 4. 注册成功跳转到首页 | 注册成功 | 用户名校验 |
| 异常场景-输入已存在用户名注册 | 注册校验 | P1 | 进入注册页 | 1. 打开注册页面 2. 输入已注册用户名admin 3. 输入密码admin123 4. 点击注册按钮 | 1. 页面正常加载 2. 用户名输入框下方显示用户名已存在 3. 密码输入框无错误提示 4. 注册失败停留在注册页 | 阻止提交并提示用户名已存在 | 用户名校验 |
| 边界值-用户名长度5位(低于最小值6) | 注册校验 | P1 | 进入注册页 | 1. 打开注册页面 2. 输入5位用户名abc12 3. 点击注册按钮 | 1. 页面正常加载 2. 用户名输入框提示长度需6-16位 | 阻止提交并提示长度限制 | 用户名校验 |

## 规则
1. 只输出表格，不要输出标题、解释、代码块标记
2. 每行一条用例，字段用 | 分隔
3. action 和 expected 必须包含完整的操作步骤，用"1. 2. 3."编号，每个步骤之间用空格分隔
4. action 和 expected 的步骤要一一对应
5. 优先级用 P0/P1/P2/P3
6. module 和 feature_name 必须使用给定的模块名和功能点名
7. 每个功能点生成 3-8 条用例，覆盖正向/异常/边界
8. title 必须是有意义的测试场景标题，格式为：测试场景类型+具体描述，如 测试完整登录流程、异常场景-输入空用户名、边界值-用户名长度超过最大值16"""

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
            cells = [c for c in cells if c != "" or True]  # 保留空单元格
            # 去掉首尾空元素
            while cells and cells[0] == "":
                cells.pop(0)
            while cells and cells[-1] == "":
                cells.pop(-1)

            if len(cells) < 3:
                continue

            # 按列顺序映射
            case = {}
            for i, col_name in enumerate(col_order):
                if i < len(cells):
                    case[col_name] = cells[i]

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
