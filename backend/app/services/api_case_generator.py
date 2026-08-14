"""
AI 接口测试用例生成器
复用 LLMFactory，支持多种生成策略和断言深度
"""
import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.llm_factory import llm_factory

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """你是一个专业的接口测试工程师，擅长根据接口定义生成高质量的测试用例。
请严格按照要求的 JSON 格式返回，不要输出任何额外的解释文字。"""


def build_generate_prompt(api_definition: Dict[str, Any], strategy: str = "comprehensive",
                          case_count: int = 5, coverage_scenarios: Optional[List[str]] = None,
                          assertion_depth: str = "standard", language: str = "zh") -> str:
    """构建 AI 生成用例的提示词"""
    coverage = coverage_scenarios or ["normal", "missing_param", "invalid_param"]

    strategy_desc = {
        "normal": "仅生成正常流程用例",
        "abnormal": "包含正常和异常场景（参数缺失、非法值、越权）",
        "boundary": "包含边界值测试（数值边界、字符串长度、空值）",
        "comprehensive": "全面覆盖（正常+异常+边界+安全）",
    }

    assertion_desc = {
        "basic": "仅断言响应状态码",
        "standard": "状态码 + 关键字段值校验",
        "deep": "状态码 + 全字段 + 业务规则校验",
    }

    parameters = []
    for p in api_definition.get("query_params", []) or []:
        parameters.append(f"  - Query: {p.get('key')} ({p.get('type', 'string')}) - {p.get('description', '')}")
    for p in api_definition.get("path_params", []) or []:
        parameters.append(f"  - Path: {p.get('key')} ({p.get('type', 'string')}) - {p.get('description', '')}")

    request_body = api_definition.get("body_content", {})
    response_example = (api_definition.get("response_examples") or [{}])[0] if api_definition.get("response_examples") else {}

    prompt = f"""你是一个专业的接口测试工程师。请根据以下接口定义，生成 {case_count} 个接口测试用例。

接口信息：
- 名称：{api_definition.get('name', '')}
- 方法：{api_definition.get('method', 'GET')}
- 路径：{api_definition.get('path', '')}
- 描述：{api_definition.get('description', '')}

请求参数：
{chr(10).join(parameters) if parameters else '  无'}

请求体：
{json.dumps(request_body, ensure_ascii=False, indent=2) if request_body else '  无'}

响应示例：
{json.dumps(response_example, ensure_ascii=False, indent=2) if response_example else '  无'}

生成要求：
1. 生成策略：{strategy} - {strategy_desc.get(strategy, strategy_desc['comprehensive'])}
2. 覆盖场景：{', '.join(coverage)}
3. 断言深度：{assertion_depth} - {assertion_desc.get(assertion_depth, assertion_desc['standard'])}
4. 每个用例包含：name, priority, description, request(headers/params/body), assertions
5. 用例名称使用{language}中文

请严格按照以下 JSON 格式返回，不要输出其他内容：
{{"cases": [{{"name": "用例名称", "priority": "P1", "description": "用例描述", "request": {{"headers": {{}}, "params": {{}}, "body": {{}}}}, "assertions": [{{"type": "status_code", "operator": "equals", "expected": 200, "target": ""}}]}}]}}
"""
    return prompt


def parse_llm_response(content: str) -> List[Dict[str, Any]]:
    """解析 LLM 返回的 JSON"""
    try:
        # 尝试提取 JSON 部分
        content = content.strip()
        # 去掉可能的 markdown 代码块标记
        if content.startswith("```"):
            content = re.sub(r'^```(?:json)?\s*', '', content)
            content = re.sub(r'\s*```$', '', content)

        data = json.loads(content)
        cases = data.get("cases", [])
        return cases
    except json.JSONDecodeError:
        # 尝试从文本中提取 JSON
        import re
        match = re.search(r'\{[\s\S]*"cases"[\s\S]*\}', content)
        if match:
            try:
                data = json.loads(match.group())
                return data.get("cases", [])
            except json.JSONDecodeError:
                pass
        logger.error(f"无法解析 LLM 响应: {content[:500]}")
        return []


def validate_cases(cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """校验并规范化生成的用例"""
    valid_cases = []
    for case in cases:
        if not isinstance(case, dict):
            continue
        name = case.get("name", "").strip()
        if not name:
            continue
        valid_case = {
            "name": name[:200],
            "priority": case.get("priority", "P2"),
            "description": case.get("description", ""),
            "request": case.get("request", {}),
            "assertions": case.get("assertions", []),
        }
        # 规范化断言
        normalized_assertions = []
        for a in valid_case["assertions"]:
            if not isinstance(a, dict):
                continue
            normalized_assertions.append({
                "assert_type": a.get("type", a.get("assert_type", "status_code")),
                "assert_target": a.get("target", a.get("assert_target", "")),
                "operator": a.get("operator", "equals"),
                "expected_value": str(a.get("expected", a.get("expected_value", ""))),
                "enabled": True,
            })
        valid_case["assertions"] = normalized_assertions
        valid_cases.append(valid_case)
    return valid_cases


class ApiCaseGenerator:
    """AI 接口用例生成器"""

    def __init__(self, db_session, llm_config_id: Optional[int] = None):
        self.db = db_session
        self.llm_config_id = llm_config_id

    async def generate(self, api_definition: Dict[str, Any], strategy: str = "comprehensive",
                       case_count: int = 5, coverage_scenarios: Optional[List[str]] = None,
                       assertion_depth: str = "standard", language: str = "zh"
                       ) -> tuple[List[Dict[str, Any]], Dict[str, int], Optional[int]]:
        """
        生成接口测试用例
        返回 (cases, token_usage, used_config_id)
        """
        prompt = build_generate_prompt(
            api_definition, strategy, case_count, coverage_scenarios, assertion_depth, language
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]

        response, token_usage, used_config_id = await llm_factory.acall_with_fallback(
            self.db, messages, preferred_config_id=self.llm_config_id
        )

        content = response.content if hasattr(response, "content") else str(response)
        cases = parse_llm_response(content)
        cases = validate_cases(cases)

        return cases, token_usage, used_config_id


import re  # 放在文件末尾避免影响顶部导入
