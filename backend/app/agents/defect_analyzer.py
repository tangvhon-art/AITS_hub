"""
缺陷分析 Agent

分析执行失败日志和截图，推断根因并生成缺陷单。
"""
import json
import logging
from typing import Dict, Any, Optional
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


DEFECT_ANALYSIS_PROMPT = """你是一位资深缺陷分析专家，负责分析测试执行失败的原因并生成缺陷单。

请根据执行日志和错误信息，分析：
1. 失败的根本原因
2. 根因分类（frontend/backend/data/environment/requirement/other）
3. 严重程度（blocker/critical/major/minor/trivial）
4. 优先级（P0/P1/P2/P3）
5. 清晰的缺陷标题
6. 详细的复现步骤
7. 预期结果和实际结果

输出格式（严格 JSON）：
{{
    "title": "缺陷标题（简洁明了）",
    "description": "缺陷详细描述",
    "severity": "blocker/critical/major/minor/trivial",
    "priority": "P0/P1/P2/P3",
    "root_cause": "根因分析",
    "root_cause_category": "frontend/backend/data/environment/requirement/other",
    "reproduce_steps": "步骤1\\n步骤2\\n步骤3",
    "expected_result": "预期结果",
    "actual_result": "实际结果"
}}
"""


class DefectAnalyzerAgent(BaseAgent):
    """缺陷分析 Agent"""

    agent_type = "defect_analyzer"

    def __init__(self, db_session, llm_config_id: Optional[int] = None, task_id: Optional[int] = None):
        super().__init__(db_session, llm_config_id, task_id)

    def run(self, **kwargs) -> Dict[str, Any]:
        """执行缺陷分析"""
        return self.analyze(
            execution_log=kwargs.get("execution_log", ""),
            error_message=kwargs.get("error_message", ""),
            test_case=kwargs.get("test_case"),
            target_url=kwargs.get("target_url", ""),
        )

    def analyze(
        self,
        execution_log: str = "",
        error_message: str = "",
        test_case: Optional[Dict[str, Any]] = None,
        target_url: str = "",
    ) -> Dict[str, Any]:
        """
        分析执行失败并生成缺陷

        Args:
            execution_log: 执行日志（JSON字符串）
            error_message: 错误信息
            test_case: 关联用例信息
            target_url: 目标URL

        Returns:
            缺陷信息
        """
        import time
        self.start_time = time.time()
        self._log_step("analysis_start", {}, "running")

        # 构建分析上下文
        context = {
            "target_url": target_url,
            "error_message": error_message,
            "test_case": test_case or {},
        }

        # 解析执行日志
        try:
            log_data = json.loads(execution_log) if execution_log else []
            context["execution_steps"] = log_data[-10:]  # 最后10步
        except (json.JSONDecodeError, TypeError):
            context["execution_log"] = execution_log[:2000]

        messages = [
            SystemMessage(content=DEFECT_ANALYSIS_PROMPT),
            HumanMessage(content=f"分析上下文：\n{json.dumps(context, ensure_ascii=False, indent=2)}"),
        ]

        try:
            response = self._call_llm(messages)
            self._log_step("llm_call", {}, "success")

            defect = self._parse_defect(response.content)
            self._log_step("analysis_complete", {"severity": defect.get("severity")}, "success")

            return {
                **defect,
                "token_usage": self.get_token_usage(),
                "llm_config_id": self.llm_config_id,
            }

        except Exception as e:
            logger.error(f"缺陷分析失败: {e}")
            self._log_step("analysis_error", {"error": str(e)}, "failed")
            # 降级返回基础缺陷
            return {
                "title": f"执行失败: {error_message[:50]}" if error_message else "执行失败",
                "description": f"自动分析失败，请人工检查。错误信息: {error_message}",
                "severity": "major",
                "priority": "P2",
                "root_cause": "待分析",
                "root_cause_category": "other",
                "reproduce_steps": "",
                "expected_result": "",
                "actual_result": error_message,
                "error": str(e),
                "token_usage": self.get_token_usage(),
            }

    def _parse_defect(self, content: str) -> Dict[str, Any]:
        """解析缺陷分析结果"""
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        return {
            "title": "执行失败（解析失败）",
            "description": content[:500],
            "severity": "major",
            "priority": "P2",
            "root_cause": "待分析",
            "root_cause_category": "other",
            "reproduce_steps": "",
            "expected_result": "",
            "actual_result": "",
        }
