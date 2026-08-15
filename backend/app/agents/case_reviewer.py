"""
用例评审 Agent

对生成的测试用例进行规则检查和评分，给出修改意见。
"""
import json
import logging
from typing import List, Dict, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


REVIEW_SYSTEM_PROMPT = """你是一位资深测试评审专家，负责评审测试用例的质量。

请从以下维度对测试用例进行评审：
1. **完整性**：是否包含标题、前置条件、步骤、预期结果
2. **覆盖率**：是否覆盖正向、异常、边界场景
3. **可执行性**：步骤是否清晰可执行，预期结果是否明确
4. **规范性**：优先级是否合理，模块划分是否清晰
5. **冗余性**：是否有重复或高度相似的用例

输出格式（严格 JSON）：
{{
    "score": 0-100的整数评分,
    "passed": true/false,
    "summary": "整体评价（50字以内）",
    "issues": [
        {{
            "case_index": 用例序号（从0开始）,
            "issue_type": "完整性/覆盖率/可执行性/规范性/冗余性",
            "severity": "high/medium/low",
            "description": "问题描述",
            "suggestion": "修改建议"
        }}
    ],
    "overall_suggestions": ["整体改进建议1", "整体改进建议2"]
}}
"""


class CaseReviewerAgent(BaseAgent):
    """用例评审 Agent"""

    agent_type = "case_reviewer"

    def __init__(self, db_session, llm_config_id: Optional[int] = None, task_id: Optional[int] = None):
        super().__init__(db_session, llm_config_id, task_id)

    def run(self, **kwargs) -> Dict[str, Any]:
        """执行评审"""
        return self.review(
            cases=kwargs.get("cases", []),
            requirement=kwargs.get("requirement", ""),
        )

    def review(self, cases: List[Dict[str, Any]], requirement: str = "") -> Dict[str, Any]:
        """
        评审测试用例

        Args:
            cases: 测试用例列表
            requirement: 原始需求描述

        Returns:
            评审结果
        """
        self.start_time = __import__("time").time()
        self._log_step("review_start", {"case_count": len(cases)}, "running")

        # 构建用例摘要
        cases_summary = []
        for i, case in enumerate(cases):
            cases_summary.append({
                "index": i,
                "title": case.get("title", ""),
                "module": case.get("module", ""),
                "priority": case.get("priority", ""),
                "preconditions": case.get("preconditions", ""),
                "steps": case.get("steps", []),
                "expected_result": case.get("expected_result", ""),
            })

        messages = [
            SystemMessage(content=REVIEW_SYSTEM_PROMPT),
            HumanMessage(content=f"需求描述：{requirement}\n\n待评审用例：\n{json.dumps(cases_summary, ensure_ascii=False, indent=2)}"),
        ]

        try:
            response = self._call_llm(messages)
            self._log_step("llm_call", {}, "success")

            # 解析评审结果
            review_result = self._parse_review(response.content)
            self._log_step("review_complete", {"score": review_result.get("score")}, "success")

            return {
                "score": review_result.get("score", 0),
                "passed": review_result.get("passed", False),
                "summary": review_result.get("summary", ""),
                "issues": review_result.get("issues", []),
                "overall_suggestions": review_result.get("overall_suggestions", []),
                "token_usage": self.get_token_usage(),
                "llm_config_id": self.llm_config_id,
            }

        except Exception as e:
            logger.error(f"用例评审失败: {e}")
            self._log_step("review_error", {"error": str(e)}, "failed")
            return {
                "score": 0,
                "passed": False,
                "summary": f"评审失败: {str(e)}",
                "issues": [],
                "overall_suggestions": [],
                "error": str(e),
                "token_usage": self.get_token_usage(),
            }

    def _parse_review(self, content: str) -> Dict[str, Any]:
        """解析评审结果"""
        from app.agents.utils import extract_json
        parsed = extract_json(content)
        if parsed:
            return parsed

        # 降级返回
        return {
            "score": 60,
            "passed": False,
            "summary": "无法解析评审结果，请人工检查",
            "issues": [],
            "overall_suggestions": ["建议人工评审"],
        }
