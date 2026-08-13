"""
用例生成 Agent

根据需求描述自动生成结构化测试用例。
支持标准格式（前置/步骤/预期/优先级）和 BDD Gherkin 格式。
"""
import json
import logging
from typing import List, Dict, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from app.agents.llm_factory import llm_factory

logger = logging.getLogger(__name__)


class TestCaseItem(BaseModel):
    """单条测试用例结构"""
    title: str = Field(description="用例名称")
    module: str = Field(default="", description="所属模块")
    priority: str = Field(default="P1", description="优先级 P0/P1/P2/P3")
    case_type: str = Field(default="functional", description="用例类型")
    preconditions: str = Field(default="", description="前置条件")
    steps: List[Dict[str, str]] = Field(default_factory=list, description="测试步骤，每步含 action 和 expected")
    expected_result: str = Field(default="", description="预期结果")


class TestCaseList(BaseModel):
    """用例列表输出"""
    cases: List[TestCaseItem] = Field(description="测试用例列表")


CASE_GENERATOR_PROMPT = """你是一名资深测试用例设计专家，拥有 10 年以上软件测试经验。

请根据以下需求描述，生成全面、专业的测试用例。

## 需求描述
{requirement_content}

## 生成要求
1. 覆盖以下场景类型：
   - 正向场景（正常流程）
   - 异常场景（错误输入、异常操作）
   - 边界条件（最大值、最小值、空值、超长等）
   - 替代流程（备选路径）
2. 优先级分级：
   - P0：核心主流程，必须通过
   - P1：重要功能，高优先级
   - P2：一般功能，中优先级
   - P3：边缘场景，低优先级
3. 步骤清晰可执行，每步包含操作描述和该步预期
4. 预期结果明确可验证
5. 生成 {count} 条用例，确保覆盖全面且不重复

## 输出格式
{format_instructions}
"""


class CaseGeneratorAgent:
    """用例生成 Agent"""

    def __init__(self, db_session=None, llm_config_id: Optional[int] = None):
        self.db = db_session
        self.llm_config_id = llm_config_id

    def generate(
        self,
        requirement_content: str,
        count: int = 10,
    ) -> Dict[str, Any]:
        """
        生成测试用例

        Args:
            requirement_content: 需求描述文本
            count: 期望生成的用例数量

        Returns:
            dict: 包含 cases 列表和 token_usage
        """
        parser = PydanticOutputParser(pydantic_object=TestCaseList)

        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一名专业的软件测试工程师，擅长设计全面的测试用例。"),
            ("user", CASE_GENERATOR_PROMPT),
        ])

        # 获取 LLM（带降级）
        llm, used_config_id = llm_factory.get_llm_with_fallback(
            self.db, preferred_config_id=self.llm_config_id
        )

        chain = prompt | llm

        messages = prompt.format_messages(
            requirement_content=requirement_content,
            count=count,
            format_instructions=parser.get_format_instructions(),
        )

        logger.info(f"开始生成用例，需求长度: {len(requirement_content)}, 期望数量: {count}")

        response, token_usage, config_id = llm_factory.call_with_fallback(
            self.db,
            messages=messages,
            preferred_config_id=self.llm_config_id,
        )

        # 解析输出
        try:
            result = parser.parse(response.content)
            cases = [case.model_dump() for case in result.cases]
        except Exception as e:
            logger.warning(f"Pydantic 解析失败，尝试 JSON 解析: {e}")
            cases = self._fallback_parse(response.content)

        logger.info(f"用例生成完成，实际数量: {len(cases)}")

        return {
            "cases": cases,
            "token_usage": token_usage,
            "llm_config_id": config_id or used_config_id,
        }

    def _fallback_parse(self, content: str) -> List[Dict[str, Any]]:
        """当 Pydantic 解析失败时的降级解析"""
        import re
        # 尝试提取 JSON 代码块
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
        if json_match:
            content = json_match.group(1)

        try:
            data = json.loads(content)
            if isinstance(data, dict) and "cases" in data:
                return data["cases"]
            elif isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

        # 最后降级：返回单条用例，内容为原始输出
        return [{
            "title": "AI 生成用例（格式解析降级）",
            "module": "",
            "priority": "P1",
            "case_type": "functional",
            "preconditions": "",
            "steps": [{"action": "查看 AI 输出", "expected": "输出可解析"}],
            "expected_result": content[:500],
        }]
