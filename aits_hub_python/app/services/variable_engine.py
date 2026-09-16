"""
变量替换引擎
支持 {{var_name}} 语法，优先级: Mock函数 > local > scenario > environment > global
"""
import logging
import re
import json
from typing import Any, Dict, Optional
from app.services.mock_data_generator import mock_generator

logger = logging.getLogger(__name__)


class VariableEngine:
    """变量引擎"""

    VAR_PATTERN = re.compile(r"\{\{\s*([\w.\-]+)\s*\}\}")
    # 同时支持 ${var_name} 语法（Postman/JS 模板字符串风格）
    DOLLAR_VAR_PATTERN = re.compile(r"\$\{\s*([\w.\-]+)\s*\}")

    def __init__(self):
        self.global_vars: Dict[str, Any] = {}
        self.environment_vars: Dict[str, Any] = {}
        self.scenario_vars: Dict[str, Any] = {}
        self.local_vars: Dict[str, Any] = {}
        self.mock_generator = mock_generator
        self._script_vars: list = []
        self._script_generated_keys: set = set()
        self._script_original_values: Dict[str, Any] = {}
        # 脚本通过 pm.request.headers.add/upsert 注入的请求头补丁：[{key, value}, ...]
        self.script_header_patches: list = []

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
        """替换文本中的 {{var_name}} 和 ${var_name} 变量，先执行 Mock 函数替换"""
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

        # 先替换 {{var_name}}，再替换 ${var_name}
        text = self.VAR_PATTERN.sub(_replace_match, text)
        text = self.DOLLAR_VAR_PATTERN.sub(_replace_match, text)
        return text

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
        """从环境配置加载静态变量，脚本类型变量存储待后续执行（需要请求上下文）"""
        if not environment_config:
            return
        variables = environment_config.get("variables", {})
        if isinstance(variables, dict):
            variables = [{"key": k, "value": v} for k, v in variables.items()]

        if not isinstance(variables, list):
            return

        self._script_vars = []
        self._script_generated_keys.clear()
        self._script_original_values.clear()
        for v in variables:
            if not isinstance(v, dict) or not v.get("key"):
                continue
            if v.get("value_type") == "script" and v.get("script"):
                self._script_vars.append(v)
            else:
                self.environment_vars[v["key"]] = v.get("value", "")

    def run_environment_scripts(self, request: Optional[Dict[str, Any]] = None) -> str:
        """执行环境中的脚本类型变量（需在请求上下文可用后调用），返回 console 输出"""
        if not self._script_vars:
            return ""
        from app.services.script_engine import ScriptEngine
        engine = ScriptEngine()
        console_output = ""
        input_headers = (request or {}).get("headers") or []

        for v in self._script_vars:
            logger.info(f"[SCRIPT] Executing env script: key={v.get('key')}")
            pre_env_snapshot = dict(self.environment_vars)
            result = engine.execute(
                script=v["script"],
                environment_vars=dict(self.environment_vars),
                global_vars=dict(self.global_vars),
                request=request or {},
            )
            if result.success:
                logger.info(f"[SCRIPT] Success. result.variables keys: {list(result.variables.keys())}")
                if result.variables:
                    for k, new_val in result.variables.items():
                        if k not in pre_env_snapshot:
                            self._script_generated_keys.add(k)
                        elif pre_env_snapshot[k] != new_val:
                            self._script_generated_keys.add(k)
                            if k not in self._script_original_values:
                                self._script_original_values[k] = pre_env_snapshot[k]
                    self.environment_vars.update(result.variables)
                logger.info(f"[SCRIPT] After update, env_vars keys: {list(self.environment_vars.keys())}")
                for _k in ["signature"]:
                    if _k in self.environment_vars:
                        logger.info(f"[SCRIPT] env_vars[{_k}] = {str(self.environment_vars[_k])[:80]}")
                # 收集脚本对 pm.request.headers 的修改（如签名头注入/占位符覆盖）
                if result.request_headers:
                    self.collect_header_patches(result.request_headers, input_headers)
                    logger.info(f"[SCRIPT] header patches: {self.script_header_patches}")
                console_output += result.output
            else:
                logger.warning(f"[SCRIPT] Failed [{v.get('key')}]: {result.error}")
                console_output += f"[ERROR] 脚本 {v.get('key')} 执行失败: {result.error}\n"
        return console_output

    def clear_script_vars(self):
        """清除脚本生成的动态变量值，恢复静态环境变量，在每步执行前调用"""
        for key in self._script_generated_keys:
            if key in self._script_original_values:
                self.environment_vars[key] = self._script_original_values[key]
            else:
                self.environment_vars.pop(key, None)
        self._script_generated_keys.clear()
        self._script_original_values.clear()
        self.script_header_patches = []

    def collect_header_patches(self, result_headers: Optional[list], input_headers: Optional[list]):
        """对比脚本执行后的 pm.request.headers 与输入请求头，收集新增/值被修改的头

        同名头只记录最后一次修改（覆盖式），禁用头忽略。
        """
        input_map: Dict[str, str] = {}
        for h in (input_headers or []):
            if isinstance(h, dict) and h.get("key"):
                input_map[str(h["key"]).lower()] = str(h.get("value", ""))
        patched = {str(p["key"]).lower(): p for p in self.script_header_patches}
        for h in (result_headers or []):
            if not isinstance(h, dict) or h.get("disabled"):
                continue
            key = str(h.get("key", ""))
            if not key:
                continue
            value = str(h.get("value", ""))
            lk = key.lower()
            if lk not in input_map or input_map[lk] != value:
                if lk in patched:
                    patched[lk]["value"] = value
                else:
                    patch = {"key": key, "value": value}
                    self.script_header_patches.append(patch)
                    patched[lk] = patch
            input_map[lk] = value

    def apply_header_patches(self, headers: Optional[list]) -> list:
        """将脚本注入的头补丁合并进请求头：同名更新值，不同名追加"""
        result = [dict(h) for h in (headers or []) if isinstance(h, dict)]
        for patch in self.script_header_patches:
            pk = str(patch["key"]).lower()
            merged = False
            for h in result:
                if str(h.get("key", "")).lower() == pk:
                    h["value"] = patch["value"]
                    merged = True
                    break
            if not merged:
                result.append({"key": patch["key"], "value": patch["value"], "enabled": True})
        return result

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
