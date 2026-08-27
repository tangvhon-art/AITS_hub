"""
AI 接口测试用例生成器
复用 LLMFactory，支持多种生成策略和断言深度
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.llm_factory import llm_factory

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """你是一名资深接口测试工程师，拥有丰富的 API 测试用例设计经验，熟悉 HTTP 协议、RESTful 设计与 API 测试方法论。你的任务是根据接口定义生成高质量、全覆盖的接口测试用例。

## 输出格式（最高优先级，必须严格遵守）
你必须且只能输出一个合法的 JSON 对象，包含以下结构。
### 关键规则：数组中的每个元素必须是对象，用花括号 {} 包裹，绝对不能用方括号 [] 包裹
正确写法：[{"key": "value"}, {"key": "value"}]
错误写法：[["key": "value"], ["key": "value"]]  ← 禁止！
### 完整示例
{"cases": [{"name": "获取用户列表-正常请求", "priority": "P0", "description": "验证正常分页查询", "request": {"headers": {"Authorization": "Bearer token"}, "params": {"page": 1, "page_size": 20}, "body": {}}, "assertions": [{"type": "status_code", "operator": "equals", "expected": 200, "target": ""}, {"type": "response_json", "operator": "contains", "expected": "items", "target": "$.data"}]}, {"name": "创建用户-缺少必填字段", "priority": "P1", "description": "验证缺少用户名时返回错误", "request": {"headers": {"Content-Type": "application/json"}, "params": {}, "body": {"email": "test@test.com"}}, "assertions": [{"type": "status_code", "operator": "equals", "expected": 400, "target": ""}]}]}

### 字段强制约束
1. 根对象仅有唯一key：cases，值为用例数组。
2. cases数组内每一条用例对象字段【全部必填】：name、priority、description、request、assertions。
3. request 对象字段 headers、params、body 不可省略；无数据时值必须为空对象 {}，禁止赋值 null。
    - GET 请求：请求参数放入 params，body固定为空对象{}；
    - POST/PUT JSON请求：请求体放入 body。
4. priority 仅允许取值：P0（核心主流程）、P1（重要异常场景）、P2（次要优化场景）。
5. 断言对象字段【全部必填】：type、operator、expected、target；
    - type 仅可选择：status_code、response_json、response_time、header、json_path；
    - operator 仅可选择：equals、not_equals、contains、not_contains、greater_than、less_than、exists、not_exists；
    - target：status_code / response_time 断言填空字符串 ""；json_path断言填写json‑path路径。

### JSON语法绝对禁止规则（违反直接无效）
1. 禁止使用 ```json ``` 等 Markdown 代码块包裹输出
2. 禁止在 JSON 前后添加任何解释、前言、注释或空行
3. 禁止输出思考过程、分析步骤等非 JSON 内容
4. 输出的第一个字符必须是 {，最后一个字符必须是 }
5. JSON 字符串内的换行使用 \\n，引号使用 \\"，确保 JSON 合法可解析
6. cases 数组和 assertions 数组的元素必须用花括号 {} 包裹，禁止用方括号 []
7. 所有字段名必须使用英文双引号包裹
8. 数组、对象最后一个元素后面**禁止添加多余的尾部逗号**

## API 测试设计规范（行业标准）
1. 方法语义验证：GET 验证查询且无副作用、POST 验证创建、PUT 验证整体更新、DELETE 验证删除；写操作补充重复执行（幂等性）与并发场景（如适用）
2. 鉴权与权限：验证无 token、非法 token、过期 token、低权限 token 访问受保护接口的响应（401/403）
3. 参数校验：缺失必填字段、非法数据类型、边界极值、空字符串、null、非法枚举值、超长参数、未知字段
4. 响应断言：状态码（HTTP 语义正确）、响应体关键字段与业务状态码、响应头（Content-Type 等）、响应时间（性能基线）、JSON Path 字段存在性
5. 安全用例：SQL 注入、XSS 载荷、越权访问（IDOR）、敏感信息泄露检查（错误信息是否暴露堆栈或内部细节）
6. 数据独立性：每个用例携带独立的测试数据，禁止用例之间共享可变状态

## 用例设计原则
- 覆盖场景：正常有效值、缺失必填字段、非法数据类型、边界极值、空字符串入参、null入参、非法枚举值、超长参数、权限校验（无token、非法token）
- 断言类型：status_code、response_json、response_time、header、json_path
- 每个用例至少包含 1 条断言，断言算子只能使用指定列表内的值
- 用例名称使用中文，优先级合理分配 P0/P1/P2
- 禁止产出重复、高度相似的测试用例
- 所有文本内容使用中文"""


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

    # 请求头
    headers_lines = []
    for h in api_definition.get("headers", []) or []:
        if isinstance(h, dict) and h.get("key"):
            headers_lines.append(f"  - {h['key']}: {h.get('value', '')} ({'启用' if h.get('enabled', True) else '禁用'})")

    # 请求参数
    parameters = []
    for p in api_definition.get("query_params", []) or []:
        if isinstance(p, dict) and p.get("key"):
            parameters.append(f"  - Query: {p['key']} ({p.get('type', 'string')}) - {p.get('description', '')} [必填: {p.get('required', False)}]")
    for p in api_definition.get("path_params", []) or []:
        if isinstance(p, dict) and p.get("key"):
            parameters.append(f"  - Path: {p['key']} ({p.get('type', 'string')}) - {p.get('description', '')} [必填: {p.get('required', True)}]")

    # 请求体
    body_type = api_definition.get("body_type", "none")
    request_body = api_definition.get("body_content", {})

    # 响应示例（全部）
    response_examples = api_definition.get("response_examples", []) or []
    response_section = ""
    if response_examples:
        for i, ex in enumerate(response_examples):
            response_section += f"\n  示例 {i + 1}:\n{json.dumps(ex, ensure_ascii=False, indent=4)}"
    else:
        response_section = "  无"

    prompt = f"""你是一个专业的接口测试工程师。请根据以下接口定义，生成 {case_count} 个接口测试用例。

接口信息：
- 名称：{api_definition.get('name', '')}
- 方法：{api_definition.get('method', 'GET')}
- 路径：{api_definition.get('path', '')}
- 描述：{api_definition.get('description', '')}
- 标签：{api_definition.get('tags', '')}

请求头：
{chr(10).join(headers_lines) if headers_lines else '  无'}

请求参数：
{chr(10).join(parameters) if parameters else '  无'}

请求体类型：{body_type}
请求体内容：
{json.dumps(request_body, ensure_ascii=False, indent=2) if request_body else '  无'}

响应示例：
{response_section}

生成要求：
1. 生成策略：{strategy} - {strategy_desc.get(strategy, strategy_desc['comprehensive'])}
2. 覆盖场景：{', '.join(coverage)}
3. 断言深度：{assertion_depth} - {assertion_desc.get(assertion_depth, assertion_desc['standard'])}
4. 每个用例包含：name, priority, description, request(headers/params/body), assertions
5. request.headers 为字典格式，request.params 为字典格式，request.body 为具体请求体
6. assertions 中 type 可选：status_code / response_json / response_time / header / json_path
7. 用例名称使用{language}中文
8. 请基于请求参数和请求体的字段设计测试数据，包括正常值、缺失必填字段、非法类型等

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
                       assertion_depth: str = "standard", language: str = "zh",
                       system_prompt: str = "",
                       ) -> Dict[str, Any]:
        """
        生成接口测试用例
        返回 (cases, token_usage, used_config_id)
        """
        prompt = build_generate_prompt(
            api_definition, strategy, case_count, coverage_scenarios, assertion_depth, language
        )

        effective_system_prompt = system_prompt.strip() if system_prompt and system_prompt.strip() else SYSTEM_PROMPT

        messages = [
            SystemMessage(content=effective_system_prompt),
            HumanMessage(content=prompt),
        ]

        response, token_usage, used_config_id = await llm_factory.acall_with_fallback(
            self.db, messages, preferred_config_id=self.llm_config_id
        )

        content = response.content if hasattr(response, "content") else str(response)
        logger.info(f"接口用例生成完成，原始输出长度: {len(content)}")

        return {
            "raw_content": content,
            "token_usage": token_usage,
            "llm_config_id": used_config_id,
        }
