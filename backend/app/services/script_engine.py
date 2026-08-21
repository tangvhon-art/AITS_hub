"""
脚本引擎 - 支持 JS 前后置脚本
兼容 Postman pm.* API
优先使用 QuickJS，不可用时使用简化版
"""
import json
import re
import hashlib
import hmac
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import quickjs
    HAS_QUICKJS = True
except ImportError:
    HAS_QUICKJS = False

try:
    from py_mini_racer import py_mini_racer
    HAS_PYMINIRACER = True
except (ImportError, RuntimeError):
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
    """模拟 Postman pm.* API（简化版降级使用）"""

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
        self.use_quickjs = HAS_QUICKJS
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

        if self.use_quickjs:
            return self._execute_quickjs(script, env_vars, glob_vars, request or {}, response or {})
        elif self.use_pyminiracer:
            return self._execute_pyminiracer(script, env_vars, glob_vars, request or {}, response or {})
        else:
            return self._execute_simplified(script, env_vars, glob_vars, request or {}, response or {})

    def _execute_quickjs(self, script: str, env_vars: Dict, glob_vars: Dict,
                        request: Dict, response: Dict) -> ScriptResult:
        """使用 QuickJS 执行"""
        try:
            ctx = quickjs.Context()

            # 注册 Python 桥接函数（加密 + base64）
            ctx.add_callable("__py_md5__", lambda text: hashlib.md5(text.encode("utf-8")).hexdigest())
            ctx.add_callable("__py_hmac_sha256__", lambda msg, key: hmac.new(key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest())
            ctx.add_callable("__py_hmac_md5__", lambda msg, key: hmac.new(key.encode("utf-8"), msg.encode("utf-8"), hashlib.md5).hexdigest())
            ctx.add_callable("__py_sha256__", lambda text: hashlib.sha256(text.encode("utf-8")).hexdigest())
            ctx.add_callable("__py_sha1__", lambda text: hashlib.sha1(text.encode("utf-8")).hexdigest())
            ctx.add_callable("__py_b64_encode__", lambda text: __import__("base64").b64encode(text.encode("utf-8")).decode("ascii"))
            ctx.add_callable("__py_b64_decode__", lambda text: __import__("base64").b64decode(text.encode("ascii")).decode("utf-8"))

            # 注入 CryptoJS + pm 对象
            prelude = self._build_prelude_js(env_vars, glob_vars, request, response)
            ctx.eval(prelude)

            # 处理 require('crypto-js')
            user_script = self._patch_require(script)

            # 用 IIFE 包裹以支持顶层 return
            wrapped_script = "(function() {\n" + user_script + "\n})();"

            # 执行用户脚本
            ctx.eval(wrapped_script)

            # 提取结果
            output = ctx.eval("typeof __output__ !== 'undefined' ? __output__ : ''")
            tests_raw = ctx.eval("JSON.stringify(__tests__)")
            tests = json.loads(tests_raw) if tests_raw else []
            new_env_raw = ctx.eval("JSON.stringify(pm.environment.toObject())")
            new_env = json.loads(new_env_raw) if new_env_raw else {}
            new_glob_raw = ctx.eval("JSON.stringify(pm.globals.toObject())")
            new_glob = json.loads(new_glob_raw) if new_glob_raw else {}

            return ScriptResult(
                success=True,
                output=output or "",
                variables={**new_env, **new_glob},
                tests=tests,
            )
        except Exception as e:
            return ScriptResult(success=False, error=str(e))

    def _patch_require(self, script: str) -> str:
        """处理 require('crypto-js')：删除赋值语句，替换裸引用为 CryptoJS 全局变量"""
        # 删除 const/var/let CryptoJS = require('crypto-js') 整行（避免 IIFE 中的 TDZ 冲突）
        script = re.sub(
            r"(?:const|var|let)\s+CryptoJS\s*=\s*require\(['\"]crypto-js['\"]\)\s*;?",
            "",
            script
        )
        # 其他变量赋值：var xxx = require('crypto-js') → var xxx = CryptoJS
        script = re.sub(
            r"require\(['\"]crypto-js['\"]\)",
            "CryptoJS",
            script
        )
        return script

    def _build_prelude_js(self, env_vars: Dict, glob_vars: Dict,
                          request: Dict, response: Dict) -> str:
        """构建 QuickJS 前置代码：CryptoJS（Python桥接）+ pm API + console"""
        return f"""
var __tests__ = [];
var __output__ = "";

// ==================== CryptoJS 兼容层（Python 桥接） ====================
var CryptoJS = (function() {{
    var HexStr = function(hexStr) {{
        return {{
            toString: function() {{ return hexStr; }},
            toStringHex: function() {{ return hexStr; }}
        }};
    }};

    var MD5 = function(message) {{
        return HexStr(__py_md5__(String(message)));
    }};
    MD5.create = function() {{ return MD5; }};

    var SHA1 = function(message) {{
        return HexStr(__py_sha1__(String(message)));
    }};
    SHA1.create = function() {{ return SHA1; }};

    var SHA256 = function(message) {{
        return HexStr(__py_sha256__(String(message)));
    }};
    SHA256.create = function() {{ return SHA256; }};

    var HmacSHA256 = function(message, key) {{
        return HexStr(__py_hmac_sha256__(String(message), String(key)));
    }};
    HmacSHA256.create = function() {{ return HmacSHA256; }};

    var HmacMD5 = function(message, key) {{
        return HexStr(__py_hmac_md5__(String(message), String(key)));
    }};

    var enc = {{
        Hex: {{ stringify: function(x) {{ return x.toString(); }} }},
        Base64: {{
            stringify: function(x) {{
                if (typeof x === 'string') return __py_b64_encode__(x);
                return __py_b64_encode__(String(x));
            }},
            parse: function(str) {{ return {{ toString: function() {{ return __py_b64_decode__(str); }} }}; }}
        }},
        Utf8: {{
            stringify: function(x) {{ return String(x); }},
            parse: function(str) {{ return {{ toString: function() {{ return str; }} }}; }}
        }}
    }};

    var WordArray = {{
        create: function(words, sigBytes) {{
            return {{
                words: words || [],
                sigBytes: sigBytes || 0,
                toString: function() {{ return ''; }}
            }};
        }}
    }};

    return {{
        MD5: MD5,
        SHA1: SHA1,
        SHA256: SHA256,
        HmacSHA256: HmacSHA256,
        HmacMD5: HmacMD5,
        enc: enc,
        lib: {{ WordArray: WordArray }},
        algo: {{}},
        format: {{}}
    }};
}})();

// ==================== pm API ====================
var __env_vars__ = {json.dumps(env_vars)};
var __glob_vars__ = {json.dumps(glob_vars)};
var __request_obj__ = {json.dumps(request)};

// 构建请求头数组（支持 find/upsert/each）
var __request_headers__ = (__request_obj__.headers || []).map(function(h) {{
    return {{ key: h.key || "", value: h.value || "", disabled: h.disabled || false }};
}});

// 构建查询参数数组（支持 each）
var __request_query__ = (__request_obj__.query_params || []).map(function(q) {{
    return {{ key: q.key || "", value: q.value || "", disabled: q.disabled || false }};
}});

// 构建 body（兼容 Postman formdata 语法）
var __body_mode__ = __request_obj__.body_type || "raw";
if (__body_mode__ === "form-data") __body_mode__ = "formdata";

var __formdata_arr__ = [];
if (__body_mode__ === "formdata") {{
    var __raw_body_for_fd__ = __request_obj__.body;
    if (Array.isArray(__raw_body_for_fd__)) {{
        __formdata_arr__ = __raw_body_for_fd__.map(function(item) {{
            if (typeof item === 'object' && item !== null) {{
                return {{ key: item.key || "", value: String(item.value || ""), disabled: item.disabled || false }};
            }}
            return {{ key: "", value: String(item), disabled: false }};
        }});
    }} else if (typeof __raw_body_for_fd__ === 'string') {{
        try {{
            var parsed = JSON.parse(__raw_body_for_fd__);
            if (Array.isArray(parsed)) {{
                __formdata_arr__ = parsed.map(function(item) {{
                    return {{ key: item.key || "", value: String(item.value || ""), disabled: item.disabled || false }};
                }});
            }}
        }} catch(e) {{}}
    }}
}}

var __raw_body_str__ = "";
if (typeof __request_obj__.body === 'string') {{
    __raw_body_str__ = __request_obj__.body;
}} else if (__request_obj__.body !== null && __request_obj__.body !== undefined) {{
    try {{ __raw_body_str__ = JSON.stringify(__request_obj__.body); }} catch(e) {{ __raw_body_str__ = String(__request_obj__.body); }}
}}

var __request_body__ = {{
    mode: __body_mode__,
    raw: __raw_body_str__,
    formdata: {{
        _arr: __formdata_arr__,
        each: function(fn) {{ this._arr.forEach(function(item) {{ fn(item); }}); }}
    }}
}};

var pm = {{
    environment: {{
        _vars: __env_vars__,
        set: function(k, v) {{ this._vars[k] = v; }},
        get: function(k) {{ return this._vars[k]; }},
        toObject: function() {{ return this._vars; }}
    }},
    globals: {{
        _vars: __glob_vars__,
        set: function(k, v) {{ this._vars[k] = v; }},
        get: function(k) {{ return this._vars[k]; }},
        toObject: function() {{ return this._vars; }}
    }},
    request: {{
        method: __request_obj__.method || "GET",
        url: {{
            raw: __request_obj__.url || "",
            query: {{
                each: function(fn) {{
                    __request_query__.forEach(function(q) {{ fn(q); }});
                }}
            }}
        }},
        headers: {{
            _arr: __request_headers__,
            find: function(fn) {{
                for (var i = 0; i < this._arr.length; i++) {{
                    if (fn(this._arr[i])) return this._arr[i];
                }}
                return undefined;
            }},
            each: function(fn) {{
                this._arr.forEach(function(h) {{ fn(h); }});
            }},
            upsert: function(item) {{
                var found = false;
                for (var i = 0; i < this._arr.length; i++) {{
                    if (this._arr[i].key === item.key) {{
                        this._arr[i].value = item.value;
                        found = true;
                        break;
                    }}
                }}
                if (!found) this._arr.push(item);
            }},
            add: function(item) {{ this._arr.push(item); }},
            remove: function(key) {{
                this._arr = this._arr.filter(function(h) {{ return h.key !== key; }});
            }}
        }},
        body: __request_body__
    }},
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

var console = {{
    log: function() {{ __output__ += Array.prototype.slice.call(arguments).join(" ") + "\\n"; }},
    error: function() {{ __output__ += "[ERROR] " + Array.prototype.slice.call(arguments).join(" ") + "\\n"; }},
    warn: function() {{ __output__ += "[WARN] " + Array.prototype.slice.call(arguments).join(" ") + "\\n"; }}
}};
"""

    def _execute_pyminiracer(self, script: str, env_vars: Dict, glob_vars: Dict,
                             request: Dict, response: Dict) -> ScriptResult:
        """使用 PyMiniRacer 执行（降级方案）"""
        try:
            ctx = py_mini_racer.MiniRacer()

            prelude = self._build_prelude_js(env_vars, glob_vars, request, response)
            ctx.eval(prelude)

            user_script = self._patch_require(script)
            wrapped_script = "(function() {\n" + user_script + "\n})();"
            ctx.eval(wrapped_script)

            output = ctx.eval("typeof __output__ !== 'undefined' ? __output__ : ''")
            tests = json.loads(ctx.eval("JSON.stringify(__tests__)"))
            new_env = json.loads(ctx.eval("JSON.stringify(pm.environment.toObject())"))
            new_glob = json.loads(ctx.eval("JSON.stringify(pm.globals.toObject())"))

            return ScriptResult(
                success=True,
                output=output or "",
                variables={**new_env, **new_glob},
                tests=tests,
            )
        except Exception as e:
            return ScriptResult(success=False, error=str(e))

    def _execute_simplified(self, script: str, env_vars: Dict, glob_vars: Dict,
                            request: Dict, response: Dict) -> ScriptResult:
        """简化版执行器 - 仅支持变量设置/获取和基本断言"""
        try:
            pm = _PmApi(env_vars, glob_vars, request, response)
            output_lines = []

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
        m = re.match(r'pm\.environment\.set\(["\'](.+?)["\']\s*,\s*(.+?)\)', line)
        if m:
            pm.environment_set(m.group(1), self._parse_value(m.group(2)))
            return

        m = re.match(r'pm\.globals\.set\(["\'](.+?)["\']\s*,\s*(.+?)\)', line)
        if m:
            pm.globals_set(m.group(1), self._parse_value(m.group(2)))
            return

        m = re.match(r'pm\.test\(["\'](.+?)["\']\s*,\s*function\s*\(\s*\)\s*\{\s*return\s+(.+?)\s*;\s*\}\)', line)
        if m:
            test_name = m.group(1)
            expr = m.group(2)
            result = self._eval_simple_expr(expr, pm)
            pm._tests.append({"name": test_name, "passed": bool(result), "error": ""})
            return

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
        m = re.match(r'pm\.response\.code\s*===\s*(\d+)', expr)
        if m:
            return pm._response.get("status_code") == int(m.group(1))
        m = re.match(r'pm\.response\.code\s*!==\s*(\d+)', expr)
        if m:
            return pm._response.get("status_code") != int(m.group(1))
        return True
