"""
AI 接口文档生成器
读取完整接口定义（请求头、参数、请求体、响应报文），生成结构化接口文档
"""
import json
import logging
import re
from typing import Any, Dict, Optional, Tuple

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.llm_factory import llm_factory

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位专业的 API 文档工程师，擅长根据接口定义生成清晰、完整、规范的接口文档。

## 输出格式
直接输出 Markdown 格式文本，不要输出 JSON，不要用代码块包裹整个文档。

## 文档结构（必须包含以下章节）

### 接口概述
简要描述接口的用途、功能和使用场景。

### 请求地址
- 请求方法：GET/POST/PUT/DELETE 等
- 接口路径：完整路径

### 请求头
以表格形式列出：| 参数名 | 类型 | 是否必填 | 默认值 | 说明 |
如无请求头，注明"无"。

### 路径参数
以表格形式列出：| 参数名 | 类型 | 是否必填 | 说明 |
如无路径参数，注明"无"。

### 查询参数
以表格形式列出：| 参数名 | 类型 | 是否必填 | 默认值 | 说明 |
如无查询参数，注明"无"。

### 请求体
说明请求体类型（application/json / multipart/form-data / x-www-form-urlencoded / 无），以表格列出字段：
| 字段名 | 类型 | 是否必填 | 说明 |
嵌套字段用"父.子"格式表示。

### 响应说明
- 响应状态码：200 成功，其他错误码
- 响应体字段以表格列出：| 字段名 | 类型 | 说明 |
- 提供 JSON 响应示例

### 错误码说明
列出可能的错误状态码及含义。

### 调用示例
提供 curl 调用示例。

## 生成原则（必须严格遵守）
1. 所有参数信息必须来自提供的接口定义，禁止编造不存在的参数
2. 参数表格必须完整，不要遗漏任何已定义的参数
3. 字段类型根据参数定义推断（string/integer/boolean/array/object）
4. 如果某项数据为空，明确注明"无"，不要省略章节
5. 文档结构清晰，使用 Markdown 表格和代码块
6. 所有内容使用中文
7. 禁止重复输出相同内容"""


def _format_params_table(params: list, param_type: str) -> str:
    """将参数列表格式化为文本"""
    if not params:
        return "无"
    lines = []
    for p in params:
        if not isinstance(p, dict):
            continue
        name = p.get("key", p.get("name", ""))
        ptype = p.get("type", "string")
        required = "是" if p.get("required", p.get("enabled", True)) else "否"
        default = p.get("value", p.get("default", ""))
        desc = p.get("description", "")
        if param_type == "header":
            lines.append(f"  - {name}: 类型={ptype}, 必填={required}, 默认值={default}, 说明={desc}")
        else:
            lines.append(f"  - {name}: 类型={ptype}, 必填={required}, 默认值={default}, 说明={desc}")
    return "\n".join(lines) if lines else "无"


def _format_body_fields(body_type: str, body_content: Any) -> str:
    """将请求体格式化为文本"""
    if body_type == "none" or not body_content:
        return "无请求体"

    if isinstance(body_content, str):
        try:
            body_content = json.loads(body_content)
        except (json.JSONDecodeError, TypeError):
            return f"原始内容：{body_content[:500]}"

    if isinstance(body_content, dict):
        # 检查是否是 form-data / x-www-form-urlencoded 格式（列表）
        if isinstance(body_content, list):
            lines = []
            for item in body_content:
                if isinstance(item, dict):
                    name = item.get("key", item.get("name", ""))
                    ptype = item.get("type", "string")
                    required = "是" if item.get("required", item.get("enabled", True)) else "否"
                    desc = item.get("description", "")
                    lines.append(f"  - {name}: 类型={ptype}, 必填={required}, 说明={desc}")
            return "\n".join(lines) if lines else "无"

        # JSON 对象，列出字段
        lines = []
        for key, value in body_content.items():
            vtype = type(value).__name__ if value is not None else "string"
            type_map = {"str": "string", "int": "integer", "float": "number",
                        "bool": "boolean", "list": "array", "dict": "object"}
            ptype = type_map.get(vtype, vtype)
            lines.append(f"  - {key}: 类型={ptype}, 示例值={value}")
        return "\n".join(lines) if lines else "无"

    return f"原始内容：{json.dumps(body_content, ensure_ascii=False)[:500]}"


def build_doc_prompt(api_definition: Dict[str, Any], supplement_info: str = "") -> str:
    """构建 AI 生成接口文档的提示词"""

    # 请求头
    headers = api_definition.get("headers", []) or []
    headers_text = _format_params_table(headers, "header")

    # 查询参数
    query_params = api_definition.get("query_params", []) or []
    query_text = _format_params_table(query_params, "query")

    # 路径参数
    path_params = api_definition.get("path_params", []) or []
    path_text = _format_params_table(path_params, "path")

    # 请求体
    body_type = api_definition.get("body_type", "none")
    body_content = api_definition.get("body_content", {})
    body_text = _format_body_fields(body_type, body_content)

    # 响应示例
    response_examples = api_definition.get("response_examples", []) or []
    response_section = ""
    if response_examples:
        for i, ex in enumerate(response_examples):
            response_section += f"\n响应示例 {i + 1}：\n{json.dumps(ex, ensure_ascii=False, indent=2)[:1000]}"
    else:
        response_section = "暂无"

    prompt = f"""## 接口基本信息
- 接口名称：{api_definition.get('name', '')}
- 请求方法：{api_definition.get('method', 'GET')}
- 接口路径：{api_definition.get('path', '')}
- 接口描述：{api_definition.get('description', '') or '无'}
- 标签：{api_definition.get('tags', '') or '无'}

## 请求头
{headers_text}

## 路径参数
{path_text}

## 查询参数
{query_text}

## 请求体
- 类型：{body_type}
- 字段：
{body_text}

## 响应示例
{response_section}
"""

    if supplement_info and supplement_info.strip():
        prompt += f"""
## 补充说明（请在生成文档时重点参考）
{supplement_info.strip()}
"""

    prompt += "\n请根据以上信息生成完整的接口文档。"
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

        # 内容清洗
        content = re.sub(r'^```(?:markdown)?\s*\n?', '', content)
        content = re.sub(r'\n?```\s*$', '', content)
        content = content.strip()

        return content, token_usage, used_config_id
