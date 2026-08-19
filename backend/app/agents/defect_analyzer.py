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


DEFECT_ANALYSIS_PROMPT = """你是一位资深缺陷分析专家，拥有丰富的软件缺陷定位和分析经验。你的任务是根据测试执行失败日志和错误信息，分析根本原因并生成结构化的缺陷单。

## 分析要求
请根据执行日志和错误信息，分析以下内容：
1. 失败的根本原因（root_cause）
2. 根因分类（root_cause_category）：frontend/backend/data/environment/requirement/other
3. 严重程度（severity）：blocker/critical/major/minor/trivial
4. 优先级（priority）：P0/P1/P2/P3
5. 清晰的缺陷标题（title）
6. 详细的缺陷描述（description）
7. 详细的复现步骤（reproduce_steps）
8. 预期结果（expected_result）和实际结果（actual_result）

## 输出格式（最高优先级，必须严格遵守）

你必须且只能输出一个合法的 JSON 对象，包含以下结构：

{"title": "缺陷标题（简洁明了）", "description": "缺陷详细描述", "severity": "blocker/critical/major/minor/trivial", "priority": "P0/P1/P2/P3", "root_cause": "根因分析", "root_cause_category": "frontend/backend/data/environment/requirement/other", "reproduce_steps": "步骤1\\n步骤2\\n步骤3", "expected_result": "预期结果", "actual_result": "实际结果"}

### 绝对禁止
1. 禁止使用 ```json ``` 等 Markdown 代码块包裹输出
2. 禁止在 JSON 前后添加任何解释、前言、注释或空行
3. 禁止输出思考过程、分析步骤等非 JSON 内容
4. 输出的第一个字符必须是 {，最后一个字符必须是 }
5. reproduce_steps 中的换行使用 \\n，引号使用 \\"，确保 JSON 合法可解析
6. severity 和 root_cause_category 必须使用上述指定的枚举值，不要自创

## 分析原则
- 严重程度判定：blocker（系统崩溃/核心功能不可用）、critical（主要功能失败）、major（功能异常但有规避方案）、minor（次要功能问题）、trivial（界面/文案问题）
- 优先级判定：P0（立即修复，阻塞发布）、P1（高优先级，本版本必须修复）、P2（中优先级，下版本修复）、P3（低优先级，择机修复）
- 根因分类：frontend（前端代码问题）、backend（后端代码问题）、data（数据问题）、environment（环境/配置问题）、requirement（需求问题）、other（其他）
- 复现步骤要详细到每一步操作，让其他人可以按照步骤重现问题
- 根因分析要深入，不要只描述现象，要分析底层原因
- 所有内容使用中文"""


class DefectAnalyzerAgent(BaseAgent):
    """缺陷分析 Agent"""

    agent_type = "defect_analyzer"

    def __init__(self, db_session, llm_config_id: Optional[int] = None, task_id: Optional[int] = None, project_id: Optional[int] = None):
        super().__init__(db_session, llm_config_id, task_id, project_id=project_id)

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

        # P2-9: RAG 知识库增强 - 检索类似缺陷或项目知识
        rag_context = self.build_rag_context(
            f"缺陷分析 {error_message[:200]} {target_url}",
            top_k=3,
        )

        system_content = DEFECT_ANALYSIS_PROMPT
        if rag_context:
            system_content += f"\n\n{rag_context}"

        # 将上下文格式化为纯文本
        context_parts = []
        if context.get("target_url"):
            context_parts.append(f"失败接口/URL：{context['target_url']}")
        if context.get("error_message"):
            context_parts.append(f"错误信息：{context['error_message']}")
        if context.get("test_case"):
            tc = context["test_case"]
            if isinstance(tc, dict):
                tc_lines = [f"  - {k}：{v}" for k, v in tc.items() if v]
                context_parts.append("关联测试用例：\n" + "\n".join(tc_lines))
            else:
                context_parts.append(f"关联测试用例：{tc}")
        if context.get("execution_steps"):
            steps = context["execution_steps"]
            step_lines = []
            for si, step in enumerate(steps):
                if isinstance(step, dict):
                    action = step.get("action", step.get("step", ""))
                    result = step.get("result", step.get("status", ""))
                    error = step.get("error", "")
                    line = f"  {si+1}. {action}"
                    if result:
                        line += f" → {result}"
                    if error:
                        line += f"（错误：{error}）"
                    step_lines.append(line)
                else:
                    step_lines.append(f"  {si+1}. {step}")
            context_parts.append("执行步骤（最后10步）：\n" + "\n".join(step_lines))
        elif context.get("execution_log"):
            context_parts.append(f"执行日志：\n{context['execution_log']}")

        context_text = "\n\n".join(context_parts) if context_parts else "无详细上下文"

        messages = [
            SystemMessage(content=system_content),
            HumanMessage(content=f"请分析以下测试失败信息：\n\n{context_text}"),
        ]

        try:
            response = self._call_llm(messages, temperature=0.2)

            content = response.content if hasattr(response, "content") else str(response)
            # 内容清洗：去除 markdown 代码块包裹
            import re
            content = re.sub(r'^```(?:json)?\s*\n?', '', content)
            content = re.sub(r'\n?```\s*$', '', content)
            content = content.strip()
            self._log_step("llm_call", {}, "success")

            logger.info(f"缺陷分析完成，输出长度: {len(content)}")

            return {
                "raw_content": content,
                "token_usage": self.get_token_usage(),
                "llm_config_id": self.llm_config_id,
            }

        except Exception as e:
            logger.error(f"缺陷分析失败: {e}")
            self._log_step("analysis_error", {"error": str(e)}, "failed")
            return {
                "raw_content": "",
                "token_usage": self.get_token_usage(),
                "llm_config_id": self.llm_config_id,
                "error": str(e),
            }
