"""
导入器基类
"""
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class ImportedApi:
    """导入的接口定义"""

    def __init__(self, name: str, method: str, path: str, description: str = "",
                 headers: List[Dict] = None, query_params: List[Dict] = None,
                 path_params: List[Dict] = None, body_type: str = "none",
                 body_content: Dict = None, response_examples: List[Dict] = None,
                 folder: str = ""):
        self.name = name
        self.method = method.upper()
        self.path = path
        self.description = description
        self.headers = headers or []
        self.query_params = query_params or []
        self.path_params = path_params or []
        self.body_type = body_type
        self.body_content = body_content or {}
        self.response_examples = response_examples or []
        self.folder = folder

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "method": self.method,
            "path": self.path,
            "description": self.description,
            "headers": self.headers,
            "query_params": self.query_params,
            "path_params": self.path_params,
            "body_type": self.body_type,
            "body_content": self.body_content,
            "response_examples": self.response_examples,
            "folder": self.folder,
        }


class BaseImporter(ABC):
    """导入器基类"""

    @abstractmethod
    def parse(self, content: str, file_name: str = "") -> List[ImportedApi]:
        """解析文件内容，返回接口列表"""
        pass

    def _load_json(self, content: str) -> Any:
        """加载 JSON"""
        return json.loads(content)

    def _extract_path_params(self, path: str) -> List[Dict]:
        """从路径中提取路径参数"""
        import re
        params = []
        for match in re.finditer(r'\{(\w+)\}', path):
            params.append({
                "key": match.group(1),
                "type": "string",
                "description": "",
                "required": True,
            })
        return params
