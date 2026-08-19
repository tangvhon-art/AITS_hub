"""
BDD 用例生成 Agent

将需求或标准用例转换为 Gherkin 格式（Feature/Scenario/Given/When/Then）。
"""
import json
import logging
import re
from typing import Dict, Any, List, Optional
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


BDD_GENERATION_PROMPT = """你是一位 BDD（行为驱动开发）专家，负责将测试需求转换为 Gherkin 格式的用例。

Gherkin 格式规范：
- 使用 Feature 描述功能
- 使用 Scenario 描述场景
- 使用 Given 描述前置条件
- 使用 When 描述操作
- 使用 Then 描述预期结果
- 使用 And/But 连接多个步骤
- 使用 Scenario Outline + Examples 描述参数化场景

请将以下需求/用例转换为标准的 Gherkin 格式，输出完整的 Feature 文件内容。
要求：
1. 覆盖正向、异常、边界场景
2. 步骤描述清晰、可执行
3. 使用中文
4. 只输出 Gherkin 内容，不要额外解释
"""


class BDDGeneratorAgent(BaseAgent):
    """BDD 用例生成 Agent"""

    agent_type = "bdd_generator"

    def __init__(self, db_session, llm_config_id: Optional[int] = None, task_id: Optional[int] = None, project_id: Optional[int] = None):
        super().__init__(db_session, llm_config_id, task_id, project_id=project_id)

    def run(self, **kwargs) -> Dict[str, Any]:
        """执行 BDD 生成"""
        return self.generate(
            requirement=kwargs.get("requirement", ""),
            test_cases=kwargs.get("test_cases"),
            feature_name=kwargs.get("feature_name", ""),
        )

    def generate(
        self,
        requirement: str = "",
        test_cases: Optional[List[Dict[str, Any]]] = None,
        feature_name: str = "",
    ) -> Dict[str, Any]:
        """
        生成 BDD Gherkin 用例

        Args:
            requirement: 需求描述
            test_cases: 标准用例列表（可选）
            feature_name: Feature 名称

        Returns:
            BDD 内容
        """
        import time
        self.start_time = time.time()
        self._log_step("bdd_start", {}, "running")

        # 构建输入文本
        input_parts = [f"功能名称：{feature_name or '未命名功能'}", f"需求描述：{requirement}"]
        if test_cases:
            case_lines = []
            for i, tc in enumerate(test_cases):
                if isinstance(tc, dict):
                    case_lines.append(f"  用例{i+1}：{tc.get('title', '')}（优先级：{tc.get('priority', '')}）")
                    steps = tc.get("steps", [])
                    for step in steps:
                        if isinstance(step, dict):
                            case_lines.append(f"    - {step.get('action', '')}（预期：{step.get('expected', '')}）")
                else:
                    case_lines.append(f"  用例{i+1}：{tc}")
            input_parts.append("关联测试用例：\n" + "\n".join(case_lines))

        system_content = BDD_GENERATION_PROMPT
        if rag_context:
            system_content += f"\n\n{rag_context}"

        messages = [
            SystemMessage(content=system_content),
            HumanMessage(content="\n\n".join(input_parts)),
        ]

        try:
            response = self._call_llm(messages, temperature=0.3)
            self._log_step("llm_call", {}, "success")

            bdd_content = self._extract_gherkin(response.content if hasattr(response, "content") else str(response))
            scenario_count = bdd_content.count("Scenario:") + bdd_content.count("Scenario Outline:")

            result = {
                "feature_name": feature_name or "未命名功能",
                "bdd_content": bdd_content,
                "scenario_count": scenario_count,
                "token_usage": self.get_token_usage(),
                "llm_config_id": self.llm_config_id,
            }

            self._log_step("bdd_complete", {"scenarios": scenario_count}, "success")
            return result

        except Exception as e:
            logger.error(f"BDD 生成失败: {e}")
            self._log_step("bdd_error", {"error": str(e)}, "failed")
            return {
                "feature_name": feature_name or "未命名功能",
                "bdd_content": f"Feature: {feature_name or '未命名功能'}\n\n  # 生成失败: {str(e)}",
                "scenario_count": 0,
                "error": str(e),
                "token_usage": self.get_token_usage(),
            }

    def convert_case_to_bdd(self, test_case: Dict[str, Any]) -> str:
        """
        将单条标准用例转换为 BDD 格式

        Args:
            test_case: 标准用例

        Returns:
            Gherkin Scenario
        """
        title = test_case.get("title", "未命名场景")
        preconditions = test_case.get("preconditions", "")
        steps = test_case.get("steps", [])
        expected = test_case.get("expected_result", "")

        lines = [f"  Scenario: {title}"]

        if preconditions:
            lines.append(f"    Given {preconditions}")

        if isinstance(steps, list):
            for i, step in enumerate(steps):
                step_text = step if isinstance(step, str) else step.get("action", str(step))
                if i == 0 and not preconditions:
                    lines.append(f"    Given {step_text}")
                elif i == 0 and preconditions:
                    lines.append(f"    When {step_text}")
                else:
                    lines.append(f"    And {step_text}")
        elif isinstance(steps, str) and steps:
            for i, step in enumerate(steps.split("\n")):
                if step.strip():
                    if i == 0:
                        lines.append(f"    When {step.strip()}")
                    else:
                        lines.append(f"    And {step.strip()}")

        if expected:
            lines.append(f"    Then {expected}")

        return "\n".join(lines)

    def _extract_gherkin(self, content: str) -> str:
        """提取 Gherkin 内容"""
        # 尝试提取代码块
        code_match = re.search(r'```(?:gherkin|feature)?\s*([\s\S]*?)```', content)
        if code_match:
            return code_match.group(1).strip()

        # 如果包含 Feature 关键字，直接返回
        if "Feature:" in content:
            return content.strip()

        # 降级包装
        return f"Feature: 生成的功能\n\n{content}"
