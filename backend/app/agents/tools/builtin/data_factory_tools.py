"""
造数工厂 MCP 工具：34 个 BaseTool 子类，全部薄转发到 SERVICE_REGISTRY
- category = "data_factory"
- 执行不依赖 db/project_id（无状态工具），天然满足 MCP Server 端点（db=None）调用
"""
from typing import Any, Dict, Optional

from app.agents.tools.base import BaseTool, ToolParameter
from app.services.data_tools import SERVICE_REGISTRY, execute_tool


async def _run(name: str, args: Dict[str, Any]) -> Any:
    return execute_tool(name, args)


def _make_tool(name: str) -> BaseTool:
    """按注册表元信息动态生成 BaseTool 子类"""
    meta = SERVICE_REGISTRY[name]
    cls_name = "".join(part.capitalize() for part in name.split("_")) + "Tool"
    attrs = {
        "name": name,
        "description": meta.description,
        "category": "data_factory",
        "parameters": ToolParameter(**meta.to_parameters()),
        "execute": lambda self, args, db=None, project_id=None, user_id=None, _n=name: _run(_n, args),
    }
    return type(cls_name, (BaseTool,), attrs)()


DATA_FACTORY_TOOLS: list = [_make_tool(name) for name in SERVICE_REGISTRY]


def get_data_factory_tools() -> list:
    """供 register_builtin_tools 使用"""
    return DATA_FACTORY_TOOLS
