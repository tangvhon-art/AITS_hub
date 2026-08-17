"""
需求生成 Agent

根据用户输入的简要描述，自动生成结构化的需求文档。
支持自定义 Prompt 作为 system 提示词输入。
"""
import json
import logging
from typing import Dict, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from app.agents.llm_factory import llm_factory
from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class RequirementDraft(BaseModel):
    """AI 生成的需求文档结构"""
    title: str = Field(description="需求标题，简洁概括核心功能，不超过200字符")
    content: str = Field(description="需求详细内容，包含背景、功能描述、验收标准等，使用 Markdown 格式")


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

## 输出格式
{format_instructions}
"""

DEFAULT_SYSTEM_PROMPT = "你是一名专业的需求分析师，擅长将简短的需求描述转化为结构化、详细的需求文档。请严格按照指定的 JSON 格式输出，不要输出任何多余内容。"


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
        parser = PydanticOutputParser(pydantic_object=RequirementDraft)

        effective_system_prompt = system_prompt.strip() if system_prompt and system_prompt.strip() else DEFAULT_SYSTEM_PROMPT

        prompt = ChatPromptTemplate.from_messages([
            ("system", effective_system_prompt),
            ("user", REQUIREMENT_GENERATOR_PROMPT),
        ])

        llm, used_config_id = llm_factory.get_llm_with_fallback(
            self.db, preferred_config_id=self.llm_config_id
        )

        messages = prompt.format_messages(
            user_input=user_input,
            project_name=project_name or "未指定",
            format_instructions=parser.get_format_instructions(),
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

        try:
            result = parser.parse(response.content)
            draft = result.model_dump()
        except Exception as e:
            logger.warning(f"Pydantic 解析失败，尝试 JSON 解析: {e}")
            draft = self._fallback_parse(response.content)

        logger.info(f"需求文档生成完成，标题: {draft.get('title', '未知')}")

        return {
            "title": draft.get("title", ""),
            "content": draft.get("content", ""),
            "token_usage": self.get_token_usage(),
            "llm_config_id": self.llm_config_id,
        }

    def _fallback_parse(self, content: str) -> Dict[str, Any]:
        from app.agents.utils import extract_json

        parsed = extract_json(content)
        if parsed and isinstance(parsed, dict):
            return {
                "title": parsed.get("title", "AI 生成需求"),
                "content": parsed.get("content", content[:2000]),
            }

        return {
            "title": "AI 生成需求（格式解析降级）",
            "content": content[:2000],
        }
