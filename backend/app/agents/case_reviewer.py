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


REVIEW_SYSTEM_PROMPT = """你是一位资深测试评审专家，拥有10年以上测试用例评审经验。你的任务是对提供的测试用例进行系统性、专业化评审，给出评分、分组评价、问题列表、遗漏场景和改进建议。

## 一、输出格式（最高优先级，必须严格遵守）

你必须且只能输出一个合法的 JSON 对象，结构如下（注意是多行易读格式，不是一行）：

{
  "score": 85,
  "passed": true,
  "summary": "整体评价，80字以内，概括用例整体质量",
  "group_reviews": [
    {
      "requirement_title": "需求名称",
      "module": "模块名称",
      "case_count": 5,
      "coverage": "完整",
      "comment": "该组用例覆盖评价，30字以内"
    }
  ],
  "issues": [
    {
      "case_index": 0,
      "case_title": "用例标题",
      "requirement_title": "所属需求",
      "module": "所属模块",
      "issue_type": "完整性",
      "severity": "high",
      "description": "具体问题描述，说明哪里有问题",
      "suggestion": "具体修改建议，可操作可执行"
    }
  ],
  "overall_suggestions": [
    "第一条整体改进建议",
    "第二条整体改进建议"
  ],
  "missing_scenarios": [
    "遗漏的场景1，如：缺少密码长度边界值测试",
    "遗漏的场景2"
  ]
}

### 字段取值规范
- score：0-100 的整数
- passed：score >= 70 为 true，否则为 false
- coverage：只能取 "完整"、"部分"、"不足" 三个值之一
- issue_type：只能取 "需求覆盖"、"完整性"、"场景覆盖"、"可执行性"、"规范性"、"冗余性"、"数据合理" 之一
- severity：只能取 "high"、"medium"、"low" 之一
- case_index：对应用例的全局编号（从0开始），必须是提供的用例中真实存在的编号

### 绝对禁止（违反任何一条都视为评审失败）
1. 禁止使用 ```json 或 ``` 等 Markdown 代码块包裹输出
2. 禁止在 JSON 前后添加任何解释、注释、前言、空行
3. 输出的第一个字符必须是 {，最后一个字符必须是 }
4. 禁止编造提供的用例中不存在的内容（如不存在的用例标题、不存在的步骤）
5. 禁止在 issues 中引用不存在的 case_index
6. 禁止输出思考过程、分析步骤等非 JSON 内容
7. 所有文本内容使用中文

## 二、评审维度（逐条检查，不要遗漏）

1. **需求覆盖度**：用例是否完整覆盖对应需求的所有功能点？是否有遗漏的业务场景？遗漏的必须写入 missing_scenarios
2. **完整性**：每条用例是否包含标题、前置条件、步骤（每步含操作和预期）、整体预期结果？缺少任何一项都算问题
3. **场景覆盖**：是否覆盖正向（正常流程）、异常（错误输入/异常操作）、边界（最大值/最小值/空值/超长）场景？
4. **可执行性**：步骤是否清晰可执行？操作描述是否具体（不能只写"测试一下"）？预期结果是否明确可验证？
5. **规范性**：优先级是否合理（P0核心主流程/P1重要功能/P2一般功能/P3边缘场景）？模块划分是否与需求一致？
6. **冗余性**：是否有重复或高度相似的用例可以合并？
7. **数据合理性**：测试数据是否合理？是否包含等价类和边界值数据？

## 三、评审原则

- 评分标准：90+优秀，80-89良好，70-79合格，<70不合格
- severity 分级：
  - high：严重问题，影响用例可用性或需求遗漏（如缺少前置条件、预期结果为空、核心场景遗漏）
  - medium：中等问题，影响用例质量（如步骤不够具体、优先级不合理）
  - low：轻微问题，建议优化（如命名不规范、可合并的重复用例）
- 改进建议必须具体可操作，不要泛泛而谈（不要只说"建议优化"，要说"建议补充密码长度为5位的边界测试用例"）
- 重点关注需求覆盖度：如果某个需求功能点没有对应用例，必须在 missing_scenarios 中明确指出
- 如果没有发现问题，issues 返回空数组 []，但 overall_suggestions 和 missing_scenarios 仍需给出
- 数据绝对准确：所有引用的用例信息必须来自提供的数据，禁止编造"""


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
            # 使用 _call_llm，它会自动初始化 LLM（ModelRouter 路由）并统计 token
            response = self._call_llm(messages, temperature=0.2)
            self._log_step("llm_call", {}, "success")

            content = response.content if hasattr(response, "content") else str(response)
            content = self._clean_output(content)

            # 检查是否为有效 JSON，不是则重试一次（强制格式，更低 temperature）
            from app.agents.utils import extract_json
            if not extract_json(content):
                logger.warning(f"评审首次输出非 JSON，进行重试。原始内容前300字: {content[:300]}")
                retry_messages = [
                    SystemMessage(content=(
                        "你是一个 JSON 格式化工具。请将下方的用例评审内容转换为严格的 JSON 格式输出。\n"
                        "必须且只能输出 JSON 对象，第一个字符是 {，最后一个字符是 }。\n"
                        "JSON 结构：{\"score\": 数字, \"passed\": true/false, \"summary\": \"整体评价\", "
                        "\"group_reviews\": [{\"requirement_title\": \"\", \"module\": \"\", \"case_count\": 数字, \"coverage\": \"完整/部分/不足\", \"comment\": \"\"}], "
                        "\"issues\": [{\"case_index\": 数字, \"case_title\": \"\", \"requirement_title\": \"\", \"module\": \"\", \"issue_type\": \"\", \"severity\": \"high/medium/low\", \"description\": \"\", \"suggestion\": \"\"}], "
                        "\"overall_suggestions\": [\"建议1\"], \"missing_scenarios\": [\"遗漏场景1\"]}\n"
                        "禁止输出任何 JSON 以外的内容。"
                    )),
                    HumanMessage(content=f"请将以下评审内容转为 JSON：\n\n{content}"),
                ]
                retry_response = self._call_llm(retry_messages, temperature=0.1)
                retry_content = retry_response.content if hasattr(retry_response, "content") else str(retry_response)
                retry_content = self._clean_output(retry_content)
                if extract_json(retry_content):
                    content = retry_content
                    logger.info("评审重试输出 JSON 成功")
                else:
                    logger.warning(f"评审重试仍非 JSON，内容前300字: {retry_content[:300]}")

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
