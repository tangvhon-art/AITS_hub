"""
用例评审 Agent

对生成的测试用例进行规则检查和评分，给出修改意见。
"""
import json
import logging
from typing import List, Dict, Any, Optional
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


REVIEW_SYSTEM_PROMPT = """你是一位资深测试评审专家，拥有丰富的测试用例评审经验。你的任务是对测试用例进行多维度评审，给出评分、问题列表和改进建议。

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
- 所有内容使用中文"""


class CaseReviewerAgent(BaseAgent):
    """用例评审 Agent"""

    agent_type = "case_reviewer"

    def __init__(self, db_session, llm_config_id: Optional[int] = None, task_id: Optional[int] = None, project_id: Optional[int] = None):
        super().__init__(db_session, llm_config_id, task_id, project_id=project_id)

    def run(self, **kwargs) -> Dict[str, Any]:
        """执行评审"""
        return self.review(
            cases=kwargs.get("cases", []),
            requirement=kwargs.get("requirement", ""),
            system_prompt=kwargs.get("system_prompt", ""),
        )

    def review(self, cases: List[Dict[str, Any]], requirement: str = "", system_prompt: str = "") -> Dict[str, Any]:
        """
        评审测试用例

        Args:
            cases: 测试用例列表
            requirement: 原始需求描述
            system_prompt: 自定义 system 提示词（来自 Prompt 管理）

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

        # P2-9: RAG 知识库增强 - 检索项目测试规范和历史评审
        rag_context = self.build_rag_context(
            f"用例评审 {requirement[:200]}",
            top_k=3,
        )

        system_content = system_prompt.strip() if system_prompt and system_prompt.strip() else REVIEW_SYSTEM_PROMPT
        if rag_context:
            system_content += f"\n\n{rag_context}"

        messages = [
            SystemMessage(content=system_content),
            HumanMessage(content=f"需求描述：{requirement}\n\n待评审用例：\n{json.dumps(cases_summary, ensure_ascii=False, indent=2)}"),
        ]

        try:
            response = self._call_llm(messages)
            self._log_step("llm_call", {}, "success")

            logger.info(f"用例评审完成，原始输出长度: {len(response.content)}")

            return {
                "raw_content": response.content,
                "token_usage": self.get_token_usage(),
                "llm_config_id": self.llm_config_id,
            }

        except Exception as e:
            logger.error(f"用例评审失败: {e}")
            self._log_step("review_error", {"error": str(e)}, "failed")
            return {
                "raw_content": "",
                "token_usage": self.get_token_usage(),
                "llm_config_id": self.llm_config_id,
                "error": str(e),
            }
