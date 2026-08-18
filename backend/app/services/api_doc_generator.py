"""
AI 接口文档生成器
读取完整接口定义（请求头、参数、请求体、响应报文），生成结构化接口文档
"""
import json
import logging
from typing import Any, Dict, Optional, Tuple

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.llm_factory import llm_factory

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位专业的 API 文档工程师，擅长根据接口定义生成清晰、完整、规范的接口文档。
请使用 Markdown 格式输出，包含完整的请求/响应说明、参数表格、示例等。"""


def build_doc_prompt(api_definition: Dict[str, Any], supplement_info: str = "") -> str:
    """构建 AI 生成接口文档的提示词"""

    # 请求头
    headers = api_definition.get("headers", []) or []
    headers_json = json.dumps(headers, ensure_ascii=False, indent=2)

    # 查询参数
    query_params = api_definition.get("query_params", []) or []
    query_json = json.dumps(query_params, ensure_ascii=False, indent=2)

    # 路径参数
    path_params = api_definition.get("path_params", []) or []
    path_json = json.dumps(path_params, ensure_ascii=False, indent=2)

    # 请求体
    body_type = api_definition.get("body_type", "none")
    body_content = api_definition.get("body_content", {})
    body_json = json.dumps(body_content, ensure_ascii=False, indent=2)

    # 响应示例
    response_examples = api_definition.get("response_examples", []) or []
    response_section = ""
    if response_examples:
        for i, ex in enumerate(response_examples):
            response_section += f"\n### 响应示例 {i + 1}\n```json\n{json.dumps(ex, ensure_ascii=False, indent=2)}\n```"
    else:
        response_section = "暂无"

    prompt = f"""请根据以下接口定义信息，生成一份完整的接口文档（Markdown 格式）。

## 接口基本信息
- 接口名称：{api_definition.get('name', '')}
- 请求方法：{api_definition.get('method', 'GET')}
- 接口路径：{api_definition.get('path', '')}
- 接口描述：{api_definition.get('description', '')}
- 标签：{api_definition.get('tags', '')}

## 请求头配置（原始 JSON）
```json
{headers_json}
```

## 查询参数（原始 JSON）
```json
{query_json}
```

## 路径参数（原始 JSON）
```json
{path_json}
```

## 请求体
- 类型：{body_type}
- 内容：
```json
{body_json}
```

## 响应示例
{response_section}
"""

    if supplement_info and supplement_info.strip():
        prompt += f"""
## 补充说明（请在生成文档时重点参考）
{supplement_info.strip()}
"""

    prompt += """
---

请根据以上信息生成完整的接口文档，要求：

1. **接口概述**：简要描述接口的用途和功能
2. **请求地址**：方法 + 完整路径
3. **请求头**：以表格形式列出（参数名 | 类型 | 是否必填 | 说明）
4. **路径参数**：以表格形式列出（参数名 | 类型 | 是否必填 | 说明）
5. **查询参数**：以表格形式列出（参数名 | 类型 | 是否必填 | 说明）
6. **请求体**：说明请求体类型，以表格或 JSON 结构列出字段说明
7. **响应说明**：
   - 响应状态码说明
   - 响应体字段说明（表格形式）
   - 响应示例
8. **错误码说明**：列出可能的错误状态码及含义
9. **调用示例**：提供 curl 调用示例

请确保文档结构清晰、内容完整、格式规范。直接输出 Markdown 内容，不要包裹在代码块中。
"""
    return prompt


class ApiDocGenerator:
    """AI 接口文档生成器"""

    def __init__(self, db_session, llm_config_id: Optional[int] = None):
        self.db = db_session
        self.llm_config_id = llm_config_id

    async def generate(self, api_definition: Dict[str, Any], system_prompt: str = "", supplement_info: str = "") -> Tuple[str, Dict[str, int], Optional[int]]:
        """
        生成接口文档
        返回 (markdown_content, token_usage, used_config_id)
        """
        prompt = build_doc_prompt(api_definition, supplement_info=supplement_info)

        effective_system_prompt = system_prompt.strip() if system_prompt and system_prompt.strip() else SYSTEM_PROMPT

        messages = [
            SystemMessage(content=effective_system_prompt),
            HumanMessage(content=prompt),
        ]

        response, token_usage, used_config_id = await llm_factory.acall_with_fallback(
            self.db, messages, preferred_config_id=self.llm_config_id
        )

        content = response.content if hasattr(response, "content") else str(response)
        return content, token_usage, used_config_id
