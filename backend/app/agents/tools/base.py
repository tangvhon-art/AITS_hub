"""
BaseTool — 统一工具抽象基类

所有 Function Calling 工具、MCP 工具均实现此接口，统一注册到 ToolRegistry。
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session


class ToolParameter:
    """工具参数定义（JSON Schema 子集）"""

    def __init__(
        self,
        type: str = "object",
        properties: Optional[Dict[str, Any]] = None,
        required: Optional[list] = None,
    ):
        self.type = type
        self.properties = properties or {}
        self.required = required or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "properties": self.properties,
            "required": self.required,
        }


class BaseTool(ABC):
    """工具基类"""

    name: str = ""
    description: str = ""
    parameters: ToolParameter = ToolParameter()
    category: str = "general"  # 分类：test_case/defect/api_test/knowledge/...

    def __init__(self):
        if not self.name:
            raise ValueError(f"{self.__class__.__name__} 必须定义 name")

    @abstractmethod
    async def execute(
        self,
        args: Dict[str, Any],
        db: Session,
        project_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> Any:
        """执行工具，返回结果（不包裹 success/error，由 Registry 统一处理异常）"""
        ...

    def to_function_schema(self) -> Dict[str, Any]:
        """转换为 OpenAI Function Calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters.to_dict(),
            },
        }

    def to_mcp_tool(self) -> Dict[str, Any]:
        """转换为 MCP 工具格式"""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.parameters.to_dict(),
        }
