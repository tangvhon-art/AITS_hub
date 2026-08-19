"""
变量替换引擎
支持 {{var_name}} 语法，优先级: Mock函数 > local > scenario > environment > global
"""
import re
import json
from typing import Any, Dict, Optional
from app.services.mock_data_generator import mock_generator


class VariableEngine:
    """变量引擎"""

    VAR_PATTERN = re.compile(r"\{\{\s*([\w.\-]+)\s*\}\}")

    def __init__(self):
        self.global_vars: Dict[str, Any] = {}
        self.environment_vars: Dict[str, Any] = {}
        self.scenario_vars: Dict[str, Any] = {}
        self.local_vars: Dict[str, Any] = {}
        self.mock_generator = mock_generator

    def set(self, scope: str, name: str, value: Any):
        """设置变量"""
        scope_map = {
            "global": self.global_vars,
            "environment": self.environment_vars,
            "scenario": self.scenario_vars,
            "local": self.local_vars,
        }
        if scope in scope_map:
            scope_map[scope][name] = value

    def get(self, name: str) -> Any:
        """获取变量，按优先级 local > scenario > environment > global"""
        if name in self.local_vars:
            return self.local_vars[name]
        if name in self.scenario_vars:
            return self.scenario_vars[name]
        if name in self.environment_vars:
            return self.environment_vars[name]
        if name in self.global_vars:
            return self.global_vars[name]
        return None

    def has(self, name: str) -> bool:
        """检查变量是否存在"""
        return (name in self.local_vars or name in self.scenario_vars
                or name in self.environment_vars or name in self.global_vars)

    def replace(self, text: str) -> str:
        """替换文本中的 {{var_name}} 变量，先执行 Mock 函数替换"""
        if not text or not isinstance(text, str):
            return text

        # 第一步：Mock 函数替换（优先级最高）
        text = self.mock_generator.generate(text)

        def _replace_match(match):
            var_name = match.group(1)
            value = self.get(var_name)
            if value is None:
                return match.group(0)  # 保留原样
            if isinstance(value, (dict, list)):
                return json.dumps(value, ensure_ascii=False)
            return str(value)

        return self.VAR_PATTERN.sub(_replace_match, text)

    def replace_dict(self, data: Any) -> Any:
        """递归替换字典/列表中的变量"""
        if isinstance(data, str):
            return self.replace(data)
        if isinstance(data, dict):
            return {k: self.replace_dict(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self.replace_dict(item) for item in data]
        return data

    def replace_headers(self, headers: Optional[list]) -> Optional[list]:
        """替换请求头列表中的变量"""
        if not headers:
            return headers
        result = []
        for h in headers:
            new_h = dict(h)
            if "key" in new_h:
                new_h["key"] = self.replace(str(new_h["key"]))
            if "value" in new_h:
                new_h["value"] = self.replace(str(new_h["value"]))
            result.append(new_h)
        return result

    def replace_params(self, params: Optional[list]) -> Optional[list]:
        """替换参数列表中的变量"""
        return self.replace_headers(params)  # 格式相同

    def replace_body(self, body_type: str, body_content: Any) -> Any:
        """替换请求体中的变量"""
        if body_content is None:
            return body_content
        if body_type in ("raw", "json", "binary"):
            if isinstance(body_content, str):
                return self.replace(body_content)
            return self.replace_dict(body_content)
        if body_type in ("form-data", "x-www-form-urlencoded"):
            return self.replace_dict(body_content)
        return body_content

    def load_environment(self, environment_config: Dict[str, Any]):
        """从环境配置加载变量"""
        if not environment_config:
            return
        # 环境变量可能存在 config.variables 中
        variables = environment_config.get("variables", {})
        if isinstance(variables, dict):
            self.environment_vars.update(variables)
        elif isinstance(variables, list):
            for v in variables:
                if isinstance(v, dict) and v.get("key"):
                    self.environment_vars[v["key"]] = v.get("value", "")

    def load_from_dict(self, scope: str, data: Dict[str, Any]):
        """从字典批量加载变量"""
        if not data:
            return
        scope_map = {
            "global": self.global_vars,
            "environment": self.environment_vars,
            "scenario": self.scenario_vars,
            "local": self.local_vars,
        }
        if scope in scope_map:
            scope_map[scope].update(data)

    def clear_scope(self, scope: str):
        """清空指定作用域的变量"""
        scope_map = {
            "global": self.global_vars,
            "environment": self.environment_vars,
            "scenario": self.scenario_vars,
            "local": self.local_vars,
        }
        if scope in scope_map:
            scope_map[scope].clear()

    def all_vars(self) -> Dict[str, Any]:
        """获取所有变量（合并后）"""
        result = {}
        result.update(self.global_vars)
        result.update(self.environment_vars)
        result.update(self.scenario_vars)
        result.update(self.local_vars)
        return result
