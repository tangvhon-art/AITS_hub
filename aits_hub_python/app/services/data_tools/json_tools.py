"""
JSON 工具（5 个）：格式化 / 校验 / 对比 / JSONPath 查询 / 结构转换
"""
import json
import logging

from app.services.data_tools.base import data_tool, InvalidParamError, ParseError

logger = logging.getLogger(__name__)

try:
    from jsonpath_ng import parse as jp_parse
    from jsonpath_ng.exceptions import JsonPathParserError
    HAS_JSONPATH = True
except ImportError:
    HAS_JSONPATH = False

try:
    import xmltodict
    HAS_XMLTODICT = True
except ImportError:
    HAS_XMLTODICT = False

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

MAX_JSON_INPUT = 1024 * 1024  # 1MB


def _load_json(text: str):
    if not text or not isinstance(text, str):
        raise ParseError("JSON 输入为空")
    if len(text) > MAX_JSON_INPUT:
        raise ParseError("JSON 输入超过 1MB 上限")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        detail = {"line": e.lineno, "col": e.colno, "msg": e.msg,
                  "context": text[max(0, e.pos - 20):e.pos + 20]}
        raise ParseError("JSON 解析失败", detail)


def _dump_json(obj, indent=2, sort_keys=False) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=indent, sort_keys=sort_keys)


@data_tool(
    name="json_format", title="JSON 格式化", category="json",
    description="JSON 美化/压缩、按键排序",
    parameters={
        "type": "object",
        "properties": {
            "input": {"type": "string", "title": "JSON 文本", "description": "待格式化 JSON 文本", "x-multiline": True},
            "indent": {"type": "integer", "title": "缩进空格数", "enum": [2, 4], "description": "缩进空格数，默认2"},
            "sort_keys": {"type": "boolean", "title": "按键名排序", "description": "是否按键名排序"},
            "mode": {"type": "string", "title": "输出模式", "enum": ["beautify", "minify"],
                     "x-enum-labels": ["美化", "压缩"], "description": "美化 / 压缩，默认美化"},
        },
        "required": ["input"],
    },
    is_generator=False,
)
def json_format(input: str, indent: int = 2, sort_keys: bool = False, mode: str = "beautify") -> dict:
    obj = _load_json(input)
    if mode == "minify":
        return {"result": json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=sort_keys)}
    return {"result": _dump_json(obj, indent=int(indent), sort_keys=bool(sort_keys))}


@data_tool(
    name="json_validate", title="JSON 校验", category="json",
    description="校验 JSON 语法合法性并给出错误定位",
    parameters={
        "type": "object",
        "properties": {
            "input": {"type": "string", "title": "JSON 文本", "description": "待校验 JSON 文本", "x-multiline": True},
        },
        "required": ["input"],
    },
    is_generator=False,
)
def json_validate(input: str) -> dict:
    try:
        _load_json(input)
        return {"valid": True, "error": None}
    except ParseError as e:
        return {"valid": False, "error": e.detail or {"msg": e.message}}


def _diff_json(a, b, path="", ignore_order=False, ignore_empty=False, output=None):
    """递归对比两个 JSON 值，输出差异清单"""
    if output is None:
        output = []

    if ignore_empty:
        a = _strip_empty(a)
        b = _strip_empty(b)

    if type(a) is not type(b):
        output.append({"path": path or "$", "op": "changed", "old": a, "new": b})
        return output

    if isinstance(a, dict):
        keys = set(a.keys()) | set(b.keys())
        for k in sorted(keys):
            child_path = f"{path}.{k}" if path else f"$.{k}"
            if k not in a:
                output.append({"path": child_path, "op": "added", "old": None, "new": b[k]})
            elif k not in b:
                output.append({"path": child_path, "op": "removed", "old": a[k], "new": None})
            else:
                _diff_json(a[k], b[k], child_path, ignore_order, ignore_empty, output)
    elif isinstance(a, list):
        if ignore_order:
            # 按元素值匹配（JSON 可序列化比较）
            remaining = list(b)
            for i, item in enumerate(a):
                matched = None
                for j, other in enumerate(remaining):
                    if _json_equal(item, other):
                        matched = j
                        break
                if matched is not None:
                    del remaining[matched]
                else:
                    output.append({"path": f"{path}[{i}]", "op": "removed", "old": item, "new": None})
            for item in remaining:
                output.append({"path": path, "op": "added", "old": None, "new": item})
        else:
            max_len = max(len(a), len(b))
            for i in range(max_len):
                child_path = f"{path}[{i}]"
                if i >= len(a):
                    output.append({"path": child_path, "op": "added", "old": None, "new": b[i]})
                elif i >= len(b):
                    output.append({"path": child_path, "op": "removed", "old": a[i], "new": None})
                else:
                    _diff_json(a[i], b[i], child_path, ignore_order, ignore_empty, output)
    else:
        if a != b:
            output.append({"path": path or "$", "op": "changed", "old": a, "new": b})
    return output


def _json_equal(x, y) -> bool:
    try:
        return json.dumps(x, ensure_ascii=False, sort_keys=True) == json.dumps(y, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return x == y


def _strip_empty(obj):
    """递归移除 None/空串/空数组/空对象（ignore_empty 用）"""
    if isinstance(obj, dict):
        return {k: _strip_empty(v) for k, v in obj.items()
                if _strip_empty(v) not in (None, "", [], {})}
    if isinstance(obj, list):
        return [_strip_empty(i) for i in obj if _strip_empty(i) not in (None, "", [], {})]
    return obj


@data_tool(
    name="json_compare", title="JSON 对比", category="json",
    description="两个 JSON 逐层 Diff，输出新增/删除/修改差异清单",
    parameters={
        "type": "object",
        "properties": {
            "input_a": {"type": "string", "title": "基准 JSON", "description": "基准 JSON", "x-multiline": True},
            "input_b": {"type": "string", "title": "对比 JSON", "description": "对比 JSON", "x-multiline": True},
            "ignore_order": {"type": "boolean", "title": "忽略数组顺序", "description": "数组元素顺序是否敏感"},
            "ignore_empty": {"type": "boolean", "title": "忽略空值差异", "description": "是否忽略空值差异"},
        },
        "required": ["input_a", "input_b"],
    },
    is_generator=False,
)
def json_compare(input_a: str, input_b: str, ignore_order: bool = False, ignore_empty: bool = False) -> dict:
    a = _load_json(input_a)
    b = _load_json(input_b)
    diff = _diff_json(a, b, ignore_order=bool(ignore_order), ignore_empty=bool(ignore_empty))
    return {"equal": len(diff) == 0, "diff": diff, "diff_count": len(diff)}


@data_tool(
    name="jsonpath_query", title="JSONPath 查询", category="json",
    description="按 JSONPath 表达式从 JSON 中提取数据",
    parameters={
        "type": "object",
        "properties": {
            "input": {"type": "string", "title": "JSON 文本", "description": "JSON 文本", "x-multiline": True},
            "expression": {"type": "string", "title": "JSONPath 表达式", "description": "JSONPath 表达式，如 $.store.book[*].title"},
        },
        "required": ["input", "expression"],
    },
    is_generator=False,
)
def jsonpath_query(input: str, expression: str) -> dict:
    if not HAS_JSONPATH:
        raise ParseError("JSONPath 依赖 jsonpath-ng 未安装")
    obj = _load_json(input)
    if not expression or not isinstance(expression, str):
        raise InvalidParamError("expression", "表达式不能为空")
    try:
        jp_expr = jp_parse(expression)
    except JsonPathParserError as e:
        raise ParseError(f"JSONPath 表达式语法错误: {e}")
    matches = []
    for m in jp_expr.find(obj):
        value = m.value
        # 非 JSON 可序列化值转字符串
        if isinstance(value, (dict, list, str, int, float, bool)) or value is None:
            matches.append(value)
        else:
            matches.append(str(value))
    return {"matches": matches, "count": len(matches)}


@data_tool(
    name="convert_structure", title="结构转换", category="json",
    description="JSON / XML / YAML 三种结构互转",
    parameters={
        "type": "object",
        "properties": {
            "input": {"type": "string", "title": "源结构文本", "description": "源结构文本", "x-multiline": True},
            "from_type": {"type": "string", "title": "源格式", "enum": ["json", "xml", "yaml"],
                          "x-enum-labels": ["JSON", "XML", "YAML"], "description": "源格式"},
            "to_type": {"type": "string", "title": "目标格式", "enum": ["json", "xml", "yaml"],
                        "x-enum-labels": ["JSON", "XML", "YAML"], "description": "目标格式"},
        },
        "required": ["input", "from_type", "to_type"],
    },
    is_generator=False,
)
def convert_structure(input: str, from_type: str, to_type: str) -> dict:
    if from_type == to_type:
        return {"result": input}

    # 1. 解析为 Python 对象
    if from_type == "json":
        obj = _load_json(input)
    elif from_type == "yaml":
        if not HAS_YAML:
            raise ParseError("YAML 依赖 PyYAML 未安装")
        try:
            obj = yaml.safe_load(input)
        except yaml.YAMLError as e:
            raise ParseError(f"YAML 解析失败: {e}")
    elif from_type == "xml":
        if not HAS_XMLTODICT:
            raise ParseError("XML 转换依赖 xmltodict 未安装")
        try:
            obj = xmltodict.parse(input)
        except Exception as e:  # noqa: BLE001
            raise ParseError(f"XML 解析失败: {e}")
    else:
        raise InvalidParamError("from_type", "仅支持 json/xml/yaml")

    # 2. 输出目标格式
    try:
        if to_type == "json":
            return {"result": _dump_json(obj)}
        if to_type == "yaml":
            if not HAS_YAML:
                raise ParseError("YAML 依赖 PyYAML 未安装")
            return {"result": yaml.safe_dump(obj, allow_unicode=True, sort_keys=False)}
        if to_type == "xml":
            if not HAS_XMLTODICT:
                raise ParseError("XML 转换依赖 xmltodict 未安装")
            return {"result": xmltodict.unparse({"root": obj}, pretty=True)}
    except ParseError:
        raise
    except Exception as e:  # noqa: BLE001
        raise ParseError(f"结构转换失败: {e}")
    raise InvalidParamError("to_type", "仅支持 json/xml/yaml")
