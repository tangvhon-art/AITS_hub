"""
脚本引擎 - 支持 JS 前后置脚本
兼容 Postman pm.* API
优先使用 PyMiniRacer，不可用时使用简化版
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple

try:
    from py_mini_racer import py_mini_racer
    HAS_PYMINIRACER = True
except ImportError:
    HAS_PYMINIRACER = False


class ScriptResult:
    """脚本执行结果"""

    def __init__(self, success: bool, output: str = "", error: str = "",
                 variables: Optional[Dict[str, Any]] = None,
                 tests: Optional[List[Dict[str, Any]]] = None):
        self.success = success
        self.output = output
        self.error = error
        self.variables = variables or {}
        self.tests = tests or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "variables": self.variables,
            "tests": self.tests,
        }


class _PmApi:
    """模拟 Postman pm.* API"""

    def __init__(self, environment_vars: Dict[str, Any], global_vars: Dict[str, Any],
                 request: Dict[str, Any], response: Optional[Dict[str, Any]] = None):
        self._environment = environment_vars
        self._globals = global_vars
        self._request = request
        self._response = response or {}
        self._tests: List[Dict[str, Any]] = []
        self._console_logs: List[str] = []

    def environment_set(self, key: str, value: Any):
        self._environment[key] = value

    def environment_get(self, key: str) -> Any:
        return self._environment.get(key)

    def globals_set(self, key: str, value: Any):
        self._globals[key] = value

    def globals_get(self, key: str) -> Any:
        return self._globals.get(key)

    def test(self, name: str, func):
        try:
            result = func()
            self._tests.append({"name": name, "passed": bool(result), "error": ""})
        except Exception as e:
            self._tests.append({"name": name, "passed": False, "error": str(e)})

    def expect(self, actual: Any):
        return _Expectation(actual)

    def console_log(self, *args):
        self._console_logs.append(" ".join(str(a) for a in args))

    @property
    def request(self):
        return self._request

    @property
    def response(self):
        return _ResponseWrapper(self._response)


class _ResponseWrapper:
    """响应包装器"""

    def __init__(self, response: Dict[str, Any]):
        self._response = response
        self.code = response.get("status_code", 0)
        self.status = response.get("status_code", 0)

    def json(self) -> Any:
        body = self._response.get("body", "")
        try:
            return json.loads(body)
        except Exception:
            return None

    def text(self) -> str:
        return self._response.get("body", "")

    def headers(self) -> Dict[str, str]:
        return self._response.get("headers", {})


class _Expectation:
    """简单的 expect 链式断言"""

    def __init__(self, actual: Any):
        self._actual = actual

    def to_equal(self, expected: Any) -> bool:
        return str(self._actual) == str(expected)

    def to_not_equal(self, expected: Any) -> bool:
        return str(self._actual) != str(expected)

    def to_include(self, expected: Any) -> bool:
        return str(expected) in str(self._actual)

    def to_be_above(self, expected: Any) -> bool:
        try:
            return float(self._actual) > float(expected)
        except (ValueError, TypeError):
            return False

    def to_be_below(self, expected: Any) -> bool:
        try:
            return float(self._actual) < float(expected)
        except (ValueError, TypeError):
            return False

    def to_be_a(self, expected_type: str) -> bool:
        type_map = {
            "string": str, "number": (int, float), "boolean": bool,
            "object": dict, "array": list, "null": type(None),
        }
        return isinstance(self._actual, type_map.get(expected_type, object))


class ScriptEngine:
    """脚本引擎"""

    def __init__(self):
        self.use_pyminiracer = HAS_PYMINIRACER

    def execute(self, script: str, environment_vars: Optional[Dict[str, Any]] = None,
                global_vars: Optional[Dict[str, Any]] = None,
                request: Optional[Dict[str, Any]] = None,
                response: Optional[Dict[str, Any]] = None) -> ScriptResult:
        """执行 JS 脚本"""
        if not script or not script.strip():
            return ScriptResult(success=True)

        env_vars = dict(environment_vars or {})
        glob_vars = dict(global_vars or {})

        if self.use_pyminiracer:
            return self._execute_pyminiracer(script, env_vars, glob_vars, request or {}, response or {})
        else:
            return self._execute_simplified(script, env_vars, glob_vars, request or {}, response or {})

    def _execute_pyminiracer(self, script: str, env_vars: Dict, glob_vars: Dict,
                             request: Dict, response: Dict) -> ScriptResult:
        """使用 PyMiniRacer 执行"""
        try:
            ctx = py_mini_racer.MiniRacer()

            # 注入 pm 对象
            pm_code = self._build_pm_js(env_vars, glob_vars, request, response)
            ctx.eval(pm_code)

            # 执行用户脚本
            ctx.eval(script)

            # 提取结果
            output = ctx.eval("JSON.stringify(__output__)") if ctx.eval("typeof __output__ !== 'undefined'") else ""
            tests = json.loads(ctx.eval("JSON.stringify(__tests__)"))
            new_env = json.loads(ctx.eval("JSON.stringify(pm.environment.toObject())"))
            new_glob = json.loads(ctx.eval("JSON.stringify(pm.globals.toObject())"))

            return ScriptResult(
                success=True,
                output=output,
                variables={**new_env, **new_glob},
                tests=tests,
            )
        except Exception as e:
            return ScriptResult(success=False, error=str(e))

    def _build_pm_js(self, env_vars: Dict, glob_vars: Dict, request: Dict, response: Dict) -> str:
        """构建 pm API 的 JS 代码"""
        return f"""
        var __tests__ = [];
        var __output__ = "";
        var pm = {{
            environment: {{
                _vars: {json.dumps(env_vars)},
                set: function(k, v) {{ this._vars[k] = v; }},
                get: function(k) {{ return this._vars[k]; }},
                toObject: function() {{ return this._vars; }}
            }},
            globals: {{
                _vars: {json.dumps(glob_vars)},
                set: function(k, v) {{ this._vars[k] = v; }},
                get: function(k) {{ return this._vars[k]; }},
                toObject: function() {{ return this._vars; }}
            }},
            request: {json.dumps(request)},
            response: {{
                code: {response.get('status_code', 0)},
                status: {response.get('status_code', 0)},
                json: function() {{ try {{ return JSON.parse({json.dumps(response.get('body', ''))}); }} catch(e) {{ return null; }} }},
                text: function() {{ return {json.dumps(response.get('body', ''))}; }},
                headers: function() {{ return {json.dumps(response.get('headers', {}))}; }}
            }},
            test: function(name, func) {{
                try {{ var r = func(); __tests__.push({{name: name, passed: !!r, error: ""}}); }}
                catch(e) {{ __tests__.push({{name: name, passed: false, error: e.message}}); }}
            }},
            expect: function(actual) {{
                return {{
                    to: {{
                        equal: function(exp) {{ return String(actual) === String(exp); }},
                        not: {{ equal: function(exp) {{ return String(actual) !== String(exp); }} }},
                        include: function(exp) {{ return String(actual).indexOf(String(exp)) >= 0; }},
                        be: {{
                            above: function(exp) {{ return Number(actual) > Number(exp); }},
                            below: function(exp) {{ return Number(actual) < Number(exp); }}
                        }}
                    }}
                }};
            }}
        }};
        var console = {{ log: function() {{ __output__ += Array.prototype.slice.call(arguments).join(" ") + "\\n"; }} }};
        """

    def _execute_simplified(self, script: str, env_vars: Dict, glob_vars: Dict,
                            request: Dict, response: Dict) -> ScriptResult:
        """简化版执行器 - 仅支持变量设置/获取和基本断言"""
        try:
            pm = _PmApi(env_vars, glob_vars, request, response)
            output_lines = []

            # 解析并执行简单的 pm.* 调用
            lines = script.split("\n")
            for line in lines:
                line = line.strip()
                if not line or line.startswith("//"):
                    continue
                self._execute_line(line, pm, output_lines)

            return ScriptResult(
                success=True,
                output="\n".join(output_lines),
                variables={**pm._environment, **pm._globals},
                tests=pm._tests,
            )
        except Exception as e:
            return ScriptResult(success=False, error=str(e))

    def _execute_line(self, line: str, pm: _PmApi, output_lines: List[str]):
        """执行单行脚本（简化版）"""
        # pm.environment.set("key", "value")
        m = re.match(r'pm\.environment\.set\(["\'](.+?)["\']\s*,\s*(.+?)\)', line)
        if m:
            pm.environment_set(m.group(1), self._parse_value(m.group(2)))
            return

        # pm.globals.set("key", "value")
        m = re.match(r'pm\.globals\.set\(["\'](.+?)["\']\s*,\s*(.+?)\)', line)
        if m:
            pm.globals_set(m.group(1), self._parse_value(m.group(2)))
            return

        # pm.test("name", function() { return ... })
        m = re.match(r'pm\.test\(["\'](.+?)["\']\s*,\s*function\s*\(\s*\)\s*\{\s*return\s+(.+?)\s*;\s*\}\)', line)
        if m:
            test_name = m.group(1)
            expr = m.group(2)
            result = self._eval_simple_expr(expr, pm)
            pm._tests.append({"name": test_name, "passed": bool(result), "error": ""})
            return

        # console.log(...)
        m = re.match(r'console\.log\((.+?)\)', line)
        if m:
            output_lines.append(m.group(1).strip('"\''))
            return

    def _parse_value(self, val: str) -> Any:
        """解析值字符串"""
        val = val.strip().rstrip(";")
        if val.startswith('"') and val.endswith('"'):
            return val[1:-1]
        if val.startswith("'") and val.endswith("'"):
            return val[1:-1]
        if val.lower() == "true":
            return True
        if val.lower() == "false":
            return False
        if val.lower() == "null":
            return None
        try:
            return int(val)
        except ValueError:
            try:
                return float(val)
            except ValueError:
                return val

    def _eval_simple_expr(self, expr: str, pm: _PmApi) -> bool:
        """评估简单的布尔表达式"""
        expr = expr.strip()
        # pm.response.code === 200
        m = re.match(r'pm\.response\.code\s*===\s*(\d+)', expr)
        if m:
            return pm._response.get("status_code") == int(m.group(1))
        # pm.response.code !== 200
        m = re.match(r'pm\.response\.code\s*!==\s*(\d+)', expr)
        if m:
            return pm._response.get("status_code") != int(m.group(1))
        return True
