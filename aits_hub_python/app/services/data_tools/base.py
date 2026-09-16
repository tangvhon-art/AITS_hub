"""
通用造数工具基座
- DataTool 定义（参数 Schema 单一事实源）
- @data_tool 注册装饰器
- 统一参数校验/类型转换 validate_and_coerce
- 错误类型（REST 与 MCP 共用）
"""
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ==================== 错误类型 ====================

class DataToolError(Exception):
    """造数工具错误基类，携带 HTTP 状态码与业务 code"""

    def __init__(self, code: str, message: str, detail: Any = None, http_status: int = 400):
        self.code = code
        self.message = message
        self.detail = detail
        self.http_status = http_status
        super().__init__(message)


class ToolNotFoundError(DataToolError):
    def __init__(self, name: str, available: List[str]):
        super().__init__("TOOL_NOT_FOUND", f"工具不存在: {name}",
                         {"available": available}, 404)


class InvalidParamError(DataToolError):
    def __init__(self, field: str, reason: str):
        super().__init__("INVALID_PARAM", f"参数校验失败: {field} - {reason}",
                         {"field": field, "reason": reason}, 400)


class ParseError(DataToolError):
    def __init__(self, message: str, detail: Any = None):
        super().__init__("PARSE_ERROR", message, detail, 422)


class ToolTimeoutError(DataToolError):
    def __init__(self, message: str = "工具执行超时"):
        super().__init__("TOOL_TIMEOUT", message,
                         {"hint": "正则可能存在灾难性回溯，请检查表达式或缩短输入"}, 504)


class ExecError(DataToolError):
    def __init__(self, message: str = "工具执行失败"):
        super().__init__("EXEC_ERROR", message, None, 500)


# ==================== 工具定义 ====================

@dataclass
class DataTool:
    name: str                 # 与 MCP 工具名一致，如 gen_email
    title: str                # 中文展示名，如「生成邮箱」
    category: str             # test_data / json / text / encoding / random / crypto
    description: str          # 工具描述（MCP description 同源）
    parameters: dict          # JSON Schema 子集 {type, properties, required}
    executor: Callable        # 纯函数，参数已校验，返回 dict / list
    is_generator: bool = True # True → 响应包装为 {"count": n, "result": [...]}

    def to_parameters(self) -> dict:
        return {
            "type": self.parameters.get("type", "object"),
            "properties": self.parameters.get("properties", {}),
            "required": self.parameters.get("required", []),
        }


# ==================== 注册表 ====================

SERVICE_REGISTRY: Dict[str, DataTool] = {}

CATEGORY_META = [
    {"key": "test_data", "title": "测试数据", "icon": "ExperimentOutlined"},
    {"key": "json", "title": "JSON 工具", "icon": "FileTextOutlined"},
    {"key": "text", "title": "字符工具", "icon": "FontSizeOutlined"},
    {"key": "encoding", "title": "编码工具", "icon": "QrcodeOutlined"},
    {"key": "random", "title": "随机工具", "icon": "DiceOutlined"},
    {"key": "crypto", "title": "加解密工具", "icon": "LockOutlined"},
]

CATEGORY_KEYS = [c["key"] for c in CATEGORY_META]


def data_tool(name: str, title: str, category: str, description: str,
              parameters: Optional[dict] = None, is_generator: bool = True):
    """注册装饰器：定义工具时即写入 SERVICE_REGISTRY"""
    def deco(fn: Callable):
        if category not in CATEGORY_KEYS:
            raise ValueError(f"非法工具分类: {category}")
        if name in SERVICE_REGISTRY:
            raise ValueError(f"工具重复注册: {name}")
        SERVICE_REGISTRY[name] = DataTool(
            name=name, title=title, category=category, description=description,
            parameters=parameters or {"type": "object", "properties": {}, "required": []},
            executor=fn, is_generator=is_generator,
        )
        return fn
    return deco


# ==================== 参数校验与类型转换 ====================

def _coerce_value(field: str, value: Any, prop: dict) -> Any:
    """按 JSON Schema 类型做宽松转换"""
    ptype = prop.get("type", "string")
    if value is None:
        return None
    try:
        if ptype == "integer":
            v = int(value) if not isinstance(value, bool) else int(value)
            return v
        if ptype == "number":
            return float(value)
        if ptype == "boolean":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.strip().lower() in ("true", "1", "yes")
            return bool(value)
        if ptype == "array":
            if isinstance(value, list):
                return value
            if isinstance(value, str) and value.strip():
                return [x.strip() for x in value.split(",") if x.strip()]
            return []
        # string / 其它
        return str(value) if not isinstance(value, str) else value
    except (TypeError, ValueError):
        raise InvalidParamError(field, f"无法转换为 {ptype}")


def validate_and_coerce(tool: DataTool, params: dict) -> dict:
    """统一参数校验：必填检查、类型转换、枚举检查、count 边界裁剪"""
    schema = tool.parameters
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    if not isinstance(params, dict):
        raise InvalidParamError("params", "参数必须为 JSON 对象")

    clean: dict = {}
    for field, prop in properties.items():
        value = params.get(field)
        if value is None:
            if field in required:
                raise InvalidParamError(field, "必填参数缺失")
            continue
        value = _coerce_value(field, value, prop)
        # 枚举检查
        if "enum" in prop and value not in prop["enum"]:
            raise InvalidParamError(field, f"取值必须在 {prop['enum']} 中")
        clean[field] = value

    # count 特殊处理：存在 count 参数则默认 1、裁剪到 1..1000
    if "count" in properties:
        count = clean.get("count")
        if count is None:
            count = 1
        try:
            count = int(count)
        except (TypeError, ValueError):
            count = 1
        count = max(1, min(1000, count))
        clean["count"] = count

    # 未知参数忽略（不报错，保持向前兼容）
    return clean


# ==================== 统一执行分发器 ====================

def execute_tool(name: str, params: dict) -> dict:
    """统一执行入口：REST 与 MCP 双通道共用。

    - 生成类工具（is_generator=True）：executor 返回列表，包装为 {"count": n, "result": [...]}
    - 转换类工具（is_generator=False）：executor 返回 dict，原样透传
    """
    tool = SERVICE_REGISTRY.get(name)
    if not tool:
        raise ToolNotFoundError(name, list(SERVICE_REGISTRY.keys()))

    clean = validate_and_coerce(tool, params or {})
    try:
        result = tool.executor(**clean)
    except DataToolError:
        raise
    except Exception as e:  # noqa: BLE001
        logger.exception("造数工具 %s 执行失败", name)
        raise ExecError(f"工具 {name} 执行失败: {e}")

    if tool.is_generator:
        if not isinstance(result, list):
            result = [result]
        return {"count": len(result), "result": result}
    return result


def get_tool_meta() -> List[dict]:
    """按分类汇总工具元信息（categories 接口与前端表单渲染共用）"""
    categories = []
    for meta in CATEGORY_META:
        tools = [t for t in SERVICE_REGISTRY.values() if t.category == meta["key"]]
        categories.append({
            "key": meta["key"],
            "title": meta["title"],
            "icon": meta["icon"],
            "tools": [
                {
                    "name": t.name,
                    "title": t.title,
                    "description": t.description,
                    "parameters": t.to_parameters(),
                    "is_generator": t.is_generator,
                }
                for t in tools
            ],
        })
    return categories
