"""
用例评审 Agent

对测试用例进行多维度评审，给出评分、问题列表和改进建议。
采用 SYSTEM/HUMAN 分离模式：SYSTEM 放结构与规则，HUMAN 放预处理后的纯文本数据。
"""
import json
import re
import logging
import time
from typing import List, Dict, Any, Optional
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


REVIEW_SYSTEM_PROMPT = """你是一位资深测试评审专家，拥有10年以上测试用例评审经验。你的任务是对提供的测试用例进行系统性、专业化评审，给出评分、问题列表、遗漏场景和改进建议。

## 输出格式（最高优先级）
输出以下 5 个部分，每部分用 Markdown 二级标题分隔。不要输出任何其他内容。

## 评分
score: 85
passed: true
summary: 整体评价，80字以内，概括用例整体质量

## 问题列表
| case_index | case_title | module | issue_type | severity | description | suggestion |
|------------|-----------|--------|------------|----------|-------------|------------|
| 0 | 测试完整登录流程 | 登录模块 | 完整性 | high | 缺少前置条件描述，未说明用户已注册 | 补充前置条件：用户已注册账号admin/123456 |
| 2 | 异常场景-密码错误 | 登录模块 | 可执行性 | medium | 步骤描述不够具体，未说明输入的具体密码 | 修改步骤为：输入错误密码xxx123 |

## 遗漏场景
1. 缺少密码长度边界值测试（最小值6位、最大值16位）
2. 缺少SQL注入安全测试
3. 缺少并发登录场景测试

## 整体改进建议
1. 建议统一所有用例的前置条件格式，明确数据准备要求
2. 建议补充边界值和异常场景的用例覆盖
3. 建议增加安全测试相关的用例

## 分组评价
| requirement_title | module | case_count | coverage | comment |
|-------------------|--------|------------|----------|---------|
| 用户注册功能需求 | 注册校验 | 5 | 完整 | 覆盖正向和异常场景，边界值不足 |

## 规则
1. score 为 0-100 的整数，score >= 70 时 passed 为 true，否则为 false
2. case_index 对应用例编号（从0开始），必须是提供的用例中真实存在的编号
3. issue_type 只能取：需求覆盖、完整性、场景覆盖、可执行性、规范性、冗余性、数据合理
4. severity 只能取：high（严重，影响可用性）、medium（中等，影响质量）、low（轻微，建议优化）
5. 每条问题的 description 必须具体说明哪里有问题，suggestion 必须给出可操作的修改建议
6. 遗漏场景和整体改进建议用编号列表，每条一行
7. coverage 只能取：完整、部分、不足
8. 评审维度：需求覆盖度、完整性、场景覆盖、可执行性、规范性、冗余性、数据合理性
9. 如果没有发现问题，问题列表输出空表格（只有表头），但遗漏场景和整体改进建议仍需给出
10. 所有内容使用中文"""


class CaseReviewerAgent(BaseAgent):
    """用例评审 Agent"""

    agent_type = "case_reviewer"

    def __init__(self, db_session, llm_config_id: Optional[int] = None, task_id: Optional[int] = None, project_id: Optional[int] = None):
        super().__init__(db_session, llm_config_id, task_id, project_id=project_id)

    def run(self, **kwargs) -> Dict[str, Any]:
        return self.review(
            cases=kwargs.get("cases", []),
            requirement=kwargs.get("requirement", ""),
            system_prompt=kwargs.get("system_prompt", ""),
            groups=kwargs.get("groups"),
        )

    def review(
        self,
        cases: List[Dict[str, Any]],
        requirement: str = "",
        system_prompt: str = "",
        groups: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        评审测试用例（支持多需求多模块分组）

        Args:
            cases: 测试用例列表
            requirement: 需求描述（多需求时已拼接为纯文本）
            system_prompt: 自定义 system 提示词
            groups: 分组信息 [{requirement_title, module, case_count, requirement_id}]
        """
        self.start_time = time.time()
        self._log_step("review_start", {"case_count": len(cases)}, "running")

        # RAG 知识库增强
        rag_context = self.build_rag_context(
            f"用例评审 {requirement[:200]}",
            top_k=3,
        )

        system_content = system_prompt.strip() if system_prompt and system_prompt.strip() else REVIEW_SYSTEM_PROMPT
        if rag_context:
            system_content += f"\n\n## 参考知识库内容\n{rag_context}"

        # 构建 HUMAN 消息：纯文本预处理数据
        human_text = self._build_human_text(cases, requirement, groups)

        messages = [
            SystemMessage(content=system_content),
            HumanMessage(content=human_text),
        ]

        try:
            # 使用 _call_llm，max_tokens=8192 确保评审输出不被截断
            response = self._call_llm(messages, temperature=0.2, max_tokens=8192)
            self._log_step("llm_call", {}, "success")

            content = response.content if hasattr(response, "content") else str(response)
            content = self._clean_output(content)

            # 检查输出是否包含必要的 Markdown 章节
            has_score = "score" in content.lower()
            has_issues = "问题列表" in content or "issues" in content.lower()
            if not has_score or not has_issues:
                logger.warning(f"评审首次输出格式不完整，进行重试。原始内容前300字: {content[:300]}")
                retry_messages = [
                    SystemMessage(content=system_content),
                    HumanMessage(content=human_text + "\n\n请严格按照输出格式输出：评分、问题列表、遗漏场景、整体改进建议、分组评价共 5 个部分，用 ## 标题分隔。"),
                ]
                retry_response = self._call_llm(retry_messages, temperature=0.1, max_tokens=8192)
                retry_content = retry_response.content if hasattr(retry_response, "content") else str(retry_response)
                retry_content = self._clean_output(retry_content)
                if "score" in retry_content.lower() and ("问题列表" in retry_content or "issues" in retry_content.lower()):
                    content = retry_content
                    logger.info("评审重试输出格式正确")
                else:
                    logger.warning(f"评审重试仍格式不完整，内容前300字: {retry_content[:300]}")

            logger.info(f"用例评审完成，输出长度: {len(content)}, token_usage: {self.get_token_usage()}")

            return {
                "raw_content": content,
                "token_usage": self.get_token_usage(),
                "llm_config_id": self.llm_config_id,
            }

        except Exception as e:
            logger.error(f"用例评审失败: {e}", exc_info=True)
            self._log_step("review_error", {"error": str(e)}, "failed")
            return {
                "raw_content": "",
                "token_usage": self.get_token_usage(),
                "llm_config_id": self.llm_config_id,
                "error": str(e),
            }

    def _build_human_text(
        self,
        cases: List[Dict[str, Any]],
        requirement: str,
        groups: Optional[List[Dict]],
    ) -> str:
        """构建 HUMAN 消息：将数据预处理为纯文本，不堆砌 JSON"""
        parts = []

        # 1. 需求描述
        if requirement and requirement.strip():
            parts.append("## 一、需求描述")
            parts.append(requirement.strip())
            parts.append("")

        # 2. 分组概览
        if groups and len(groups) > 0:
            parts.append("## 二、评审分组概览")
            for i, g in enumerate(groups, 1):
                parts.append(
                    f"{i}. 需求：{g.get('requirement_title', '未知')} ｜ "
                    f"模块：{g.get('module', '未分类')} ｜ "
                    f"用例数：{g.get('case_count', 0)}"
                )
            parts.append("")

        # 3. 待评审用例（按分组组织，全局编号）
        parts.append("## 三、待评审用例（全局编号，按需求+模块分组）")

        if groups and len(groups) > 0:
            for g in groups:
                req_title = g.get("requirement_title", "")
                module = g.get("module", "")
                req_id = g.get("requirement_id")
                # 筛选该组的用例
                group_cases = []
                for c in cases:
                    c_req_id = c.get("req_id")
                    c_module = c.get("module", "")
                    if req_id is not None:
                        if c_req_id == req_id and c_module == module:
                            group_cases.append(c)
                    elif c_module == module and not c_req_id:
                        group_cases.append(c)

                if not group_cases:
                    continue
                parts.append(f"\n### 【{req_title} / {module}】")
                for case in group_cases:
                    idx = cases.index(case)
                    parts.append(self._format_case(idx, case))
        else:
            for i, case in enumerate(cases):
                parts.append(self._format_case(i, case))

        parts.append("")
        parts.append("## 四、评审要求")
        parts.append("请根据以上需求描述和用例数据，按照 SYSTEM 中的评审维度逐条检查，输出 JSON 格式的评审结果。")
        parts.append("注意：所有引用的用例信息必须来自上方数据，禁止编造。")

        return "\n".join(parts)

    @staticmethod
    def _format_case(idx: int, case: Dict[str, Any]) -> str:
        """格式化单条用例为纯文本"""
        lines = [f"\n用例[{idx}]：{case.get('title', '（无标题）')}"]
        lines.append(f"  所属模块：{case.get('module', '（未设置）')}")
        lines.append(f"  优先级：{case.get('priority', '（未设置）')}")

        pre = case.get("preconditions", "")
        lines.append(f"  前置条件：{pre if pre else '（无）'}")

        steps = case.get("steps", [])
        if steps and len(steps) > 0:
            lines.append("  测试步骤：")
            for si, step in enumerate(steps, 1):
                if isinstance(step, dict):
                    action = step.get("action", "")
                    expected = step.get("expected", "")
                    if expected:
                        lines.append(f"    {si}. {action} → 预期：{expected}")
                    else:
                        lines.append(f"    {si}. {action}")
                else:
                    lines.append(f"    {si}. {str(step)}")
        else:
            lines.append("  测试步骤：（无）")

        exp = case.get("expected_result", "")
        lines.append(f"  预期结果：{exp if exp else '（无）'}")

        return "\n".join(lines)

    @staticmethod
    def _clean_output(content: str) -> str:
        """清洗 LLM 输出：去除 markdown 代码块、前后空白"""
        if not content:
            return ""
        # 去除开头的 ```json 或 ```
        content = re.sub(r'^```(?:json)?\s*\n?', '', content.strip())
        # 去除结尾的 ```
        content = re.sub(r'\n?```\s*$', '', content)
        return content.strip()
