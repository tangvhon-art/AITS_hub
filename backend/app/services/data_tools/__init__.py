"""
通用造数工具包
- 导入各工具模块触发 @data_tool 注册
- 导出 SERVICE_REGISTRY / execute_tool / get_tool_meta 供 REST 与 MCP 共用
"""
from app.services.data_tools import base  # noqa: F401  (先导入基座，注册装饰器依赖)
from app.services.data_tools.base import (  # noqa: F401
    SERVICE_REGISTRY,
    CATEGORY_META,
    DataTool,
    DataToolError,
    ToolNotFoundError,
    InvalidParamError,
    ParseError,
    ToolTimeoutError,
    ExecError,
    execute_tool,
    get_tool_meta,
)
# 工具模块（导入即注册）
from app.services.data_tools import test_data   # noqa: F401,E402
from app.services.data_tools import json_tools  # noqa: F401,E402
from app.services.data_tools import text_tools  # noqa: F401,E402
from app.services.data_tools import encoding_tools  # noqa: F401,E402
from app.services.data_tools import random_tools  # noqa: F401,E402
from app.services.data_tools import crypto_tools  # noqa: F401,E402
