"""
用例生成 Agent

根据需求描述自动生成结构化测试用例。
支持自定义 Prompt 作为 system 提示词输入。
"""
import json
import logging
from typing import List, Dict, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
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

## 输出格式
{format_instructions}
"""

DEFAULT_SYSTEM_PROMPT = "你是一名专业的软件测试工程师，擅长设计全面的测试用例。请严格按照指定的 JSON 格式输出，不要输出任何多余内容。"


class CaseGeneratorAgent(BaseAgent):
    """用例生成 Agent"""

    def __init__(self, db_session=None, llm_config_id: Optional[int] = None, project_id: Optional[int] = None):
        super().__init__(db_session, agent_name="case_generator", project_id=project_id, llm_config_id=llm_config_id)

    def run(self, **kwargs) -> Dict[str, Any]:
        """BaseAgent 抽象方法实现"""
        requirement_content = kwargs.get("requirement_content", "")
        count = kwargs.get("count", 10)
        result = self.generate(requirement_content, count)
        return {"cases": result}

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
        parser = PydanticOutputParser(pydantic_object=TestCaseList)

        effective_system_prompt = system_prompt.strip() if system_prompt and system_prompt.strip() else DEFAULT_SYSTEM_PROMPT

        prompt = ChatPromptTemplate.from_messages([
            ("system", effective_system_prompt),
            ("user", CASE_GENERATOR_PROMPT),
        ])

        llm, used_config_id = llm_factory.get_llm_with_fallback(
            self.db, preferred_config_id=self.llm_config_id
        )

        messages = prompt.format_messages(
            requirement_content=requirement_content,
            count=count,
            requirement_title=requirement_title or "未指定",
            project_name=project_name or "未指定",
            existing_count=existing_count,
            format_instructions=parser.get_format_instructions(),
        )

        logger.info(f"开始生成用例，需求标题: {requirement_title}, 需求长度: {len(requirement_content)}, 期望数量: {count}")

        response, token_usage, config_id = llm_factory.call_with_fallback(
            self.db,
            messages=messages,
            preferred_config_id=self.llm_config_id,
        )

        if token_usage:
            self.token_usage["prompt_tokens"] += token_usage.get("prompt_tokens", 0)
            self.token_usage["completion_tokens"] += token_usage.get("completion_tokens", 0)
            self.token_usage["total_tokens"] += token_usage.get("total_tokens", 0)
        self.llm_config_id = config_id or used_config_id
        self._log_step("llm_call", {"requirement_len": len(requirement_content), "count": count}, "success")

        try:
            result = parser.parse(response.content)
            cases = [case.model_dump() for case in result.cases]
        except Exception as e:
            logger.warning(f"Pydantic 解析失败，尝试 JSON 解析: {e}")
            cases = self._fallback_parse(response.content)

        logger.info(f"用例生成完成，实际数量: {len(cases)}")

        return {
            "cases": cases,
            "token_usage": self.get_token_usage(),
            "llm_config_id": self.llm_config_id,
        }

    def _fallback_parse(self, content: str) -> List[Dict[str, Any]]:
        """当 Pydantic 解析失败时的降级解析"""
        from app.agents.utils import extract_json, extract_json_list

        parsed = extract_json(content)
        if parsed and isinstance(parsed, dict) and "cases" in parsed:
            cases = parsed["cases"]
            if isinstance(cases, list):
                return cases

        parsed_list = extract_json_list(content)
        if parsed_list:
            return parsed_list

        return [{
            "title": "AI 生成用例（格式解析降级）",
            "module": "",
            "priority": "P1",
            "case_type": "functional",
            "preconditions": "",
            "steps": [{"action": "查看 AI 输出", "expected": "输出可解析"}],
            "expected_result": content[:500],
            "bdd_content": "",
        }]
