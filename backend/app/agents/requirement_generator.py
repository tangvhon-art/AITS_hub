"""
需求生成 Agent

根据用户输入的简要描述，自动生成结构化的需求文档。
支持自定义 Prompt 作为 system 提示词输入。
"""
import logging
from typing import Dict, Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.llm_factory import llm_factory
from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


REQUIREMENT_GENERATOR_PROMPT = """请根据用户的简要描述，生成一份结构化、专业的需求文档。

## 用户输入
{user_input}

## 所属项目
{project_name}

## 生成要求
1. 需求文档应包含以下部分（使用 Markdown 格式）：
   - 需求背景：说明需求的来源和业务背景
   - 功能描述：详细描述需要实现的功能点
   - 用户故事：以 "作为...我希望...以便..." 格式描述
   - 验收标准：明确的、可测试的验收条件
   - 非功能需求：性能、安全、兼容性等要求（如适用）
   - 依赖与约束：相关依赖和限制条件（如适用）
2. 内容要具体、可执行，避免模糊描述
3. 标题要简洁明了，概括核心需求
4. 根据用户输入合理扩展，补充用户可能遗漏但必要的细节
"""

DEFAULT_SYSTEM_PROMPT = """你是一名资深需求分析师，拥有丰富的软件工程和产品分析经验。你的任务是将用户提供的简要需求描述转化为结构化、专业、可执行的需求文档。

## 输出格式（最高优先级，必须严格遵守）

你必须且只能输出一个合法的 JSON 对象，包含以下两个字段：

{"title": "需求标题（简洁概括核心需求，不超过50字）", "content": "需求详细内容（Markdown 格式）"}

### 绝对禁止
1. 禁止使用 ```json ``` 等 Markdown 代码块包裹输出
2. 禁止在 JSON 前后添加任何解释、前言、注释或空行
3. 禁止输出思考过程、分析步骤等非 JSON 内容
4. 输出的第一个字符必须是 {，最后一个字符必须是 }
5. content 字段内的换行使用 \\n，引号使用 \\"，确保 JSON 合法可解析

## content 字段文档结构（Markdown 格式）

content 字段应包含以下章节，使用 Markdown 二级标题（##）分隔：

### 需求背景
说明需求的业务来源、痛点或机会，2-3 段简述，让读者快速理解为什么要做这个需求。

### 功能描述
逐条列出需要实现的功能点（无序列表）。每条包含功能名称和简要说明，确保具体到可开发、可测试的粒度。

### 用户故事
使用标准格式：「作为 [角色]，我希望 [功能]，以便 [价值]」。至少提供 3 个核心用户故事。

### 验收标准
使用编号列表，每条验收标准必须明确、可测试，覆盖正常流程和边界情况。至少提供 5 条。

### 非功能需求
根据需求性质选择性包含：性能要求、安全要求、兼容性要求、可用性要求等。

### 依赖与约束
列出实现该需求的前提条件、技术依赖或业务约束（如适用，无则省略此章节）。

## 生成原则
- 根据用户输入合理扩展，补充用户可能遗漏但必要的细节
- 避免模糊描述，所有功能点应具体到可开发、可测试的程度
- 保持专业术语准确，语言简洁
- 标题应概括核心需求，不超过 50 字
- 所有内容使用中文"""


class RequirementGeneratorAgent(BaseAgent):
    """需求生成 Agent"""

    def __init__(self, db_session=None, llm_config_id: Optional[int] = None, project_id: Optional[int] = None):
        super().__init__(db_session, agent_name="requirement_generator", project_id=project_id, llm_config_id=llm_config_id)

    def run(self, **kwargs) -> Dict[str, Any]:
        user_input = kwargs.get("user_input", "")
        result = self.generate(user_input)
        return result

    def generate(
        self,
        user_input: str,
        project_name: str = "",
        system_prompt: str = "",
    ) -> Dict[str, Any]:
        effective_system_prompt = system_prompt.strip() if system_prompt and system_prompt.strip() else DEFAULT_SYSTEM_PROMPT

        # 直接构造消息，system prompt 不经过 .format() 解析，避免其中的 JSON 花括号被当作模板变量
        messages = [
            SystemMessage(content=effective_system_prompt),
            HumanMessage(content=REQUIREMENT_GENERATOR_PROMPT.format(
                user_input=user_input,
                project_name=project_name or "未指定",
            )),
        ]

        _, used_config_id = llm_factory.get_llm_with_fallback(
            self.db, preferred_config_id=self.llm_config_id
        )

        logger.info(f"开始生成需求文档，输入长度: {len(user_input)}")

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
        self._log_step("llm_call", {"input_len": len(user_input)}, "success")

        logger.info(f"需求文档生成完成，原始输出长度: {len(response.content)}")

        return {
            "raw_content": response.content,
            "token_usage": self.get_token_usage(),
            "llm_config_id": self.llm_config_id,
        }
