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

DEFAULT_SYSTEM_PROMPT = """你是一名资深软件测试工程师，拥有丰富的测试用例设计经验。你的任务是根据需求描述生成全面、专业、可执行的测试用例。

## 输出格式（最高优先级，必须严格遵守）

你必须且只能输出一个合法的 JSON 对象，包含以下结构：

{"cases": [{"title": "用例名称", "module": "所属模块", "priority": "P0/P1/P2/P3", "case_type": "functional/performance/security", "preconditions": "前置条件", "steps": [{"action": "操作描述", "expected": "该步骤预期结果"}], "expected_result": "整体预期结果", "bdd_content": "BDD Gherkin 内容（可选）"}]}

### 绝对禁止
1. 禁止使用 ```json ``` 等 Markdown 代码块包裹输出
2. 禁止在 JSON 前后添加任何解释、前言、注释或空行
3. 禁止输出思考过程、分析步骤等非 JSON 内容
4. 输出的第一个字符必须是 {，最后一个字符必须是 }
5. JSON 字符串内的换行使用 \\n，引号使用 \\"，确保 JSON 合法可解析

## 用例设计原则
- 覆盖正向场景（正常流程）、异常场景（错误输入、异常操作）、边界条件（最大值、最小值、空值、超长）、替代流程（备选路径）
- 优先级分级：P0（核心主流程）、P1（重要功能）、P2（一般功能）、P3（边缘场景）
- 用例类型：functional（功能测试）、performance（性能测试）、security（安全测试）
- 每条用例必须包含：title（简洁明确，不超过200字）、module（按功能模块划分）、priority、case_type、preconditions（环境和数据准备）、steps（每步含 action 和 expected）、expected_result（可验证的最终结果）
- 步骤清晰可执行，预期结果明确可验证
- 根据已有用例数避免生成重复场景
- 所有内容使用中文"""


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
