"""
前置 JS 动态环境变量生成器（execjs）+ 接口请求生命周期装饰器

契约：
1. 每次接口请求前重新执行 JS 脚本（execjs，Node.js 运行时），
   JS 脚本 return 一个 JSON 对象（或调用 pm.environment.set），
   解析后写入请求级 DynamicVarContext；
2. JS 脚本支持两种来源：
   - 内联字符串（直接写脚本内容）
   - 外部文件：以 "@file:xxx.js" 引用 backend/app/js_scripts/ 下的文件；
3. api_request_lifecycle 装饰器保证固定生命周期：
   JS 生成变量 -> 发起 HTTP 请求 -> finally 清理全部动态变量，
   无论成功/失败/抛出异常，清理必定执行，杜绝变量残留污染下一次请求。

约束：不使用 os.environ，不修改进程级系统环境变量；
     JS 内可直接使用 Node 内置模块（如 require('crypto') 做签名）。
"""
import functools
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# execjs 懒加载：未安装时给出明确错误而不是静默失败
try:
    import execjs
    HAS_EXECJS = True
except ImportError:
    execjs = None
    HAS_EXECJS = False

# 外部 JS 脚本根目录：backend/app/js_scripts/
JS_SCRIPT_DIR = Path(__file__).resolve().parent.parent / "js_scripts"

# @file: 前缀，标识脚本引用外部 js 文件
FILE_REF_PREFIX = "@file:"


class JsGenResult:
    """JS 变量生成结果"""

    def __init__(self, success: bool, variables: Optional[Dict[str, Any]] = None,
                 output: str = "", error: str = "",
                 header_patches: Optional[List[Dict[str, Any]]] = None):
        self.success = success
        self.variables = variables or {}
        self.output = output
        self.error = error
        # 脚本通过 pm.request.headers.add/upsert 注入的请求头补丁：[{key, value}, ...]
        self.header_patches = header_patches or []


class JsEnvGenerator:
    """基于 execjs 的动态环境变量生成器

    JS 脚本可读取注入的 __vars__（静态+响应缓存变量快照）与 __request__（本次请求上下文），
    通过 return JSON 对象（推荐）或 pm.environment.set(k, v)（兼容存量脚本）输出动态变量。
    """

    def __init__(self, script_dir: Optional[Path] = None):
        self.script_dir = script_dir or JS_SCRIPT_DIR

    # ==================== 脚本来源解析 ====================

    def resolve_script(self, script_ref: str) -> str:
        """解析脚本来源：内联字符串原样返回；@file:xxx.js 从 js_scripts 目录读取"""
        if not script_ref:
            return ""
        ref = script_ref.strip()
        if not ref.startswith(FILE_REF_PREFIX):
            return ref

        rel_path = ref[len(FILE_REF_PREFIX):].strip()
        # 防目录穿越：解析后必须仍位于 script_dir 内
        target = (self.script_dir / rel_path).resolve()
        if not str(target).startswith(str(self.script_dir.resolve())):
            raise ValueError(f"非法的 JS 文件路径: {rel_path}")
        if not target.is_file():
            raise FileNotFoundError(f"JS 脚本文件不存在: {target}")
        return target.read_text(encoding="utf-8")

    @staticmethod
    def _patch_require(script: str) -> str:
        """处理 require('crypto-js')：prelude 已注入 CryptoJS 兼容层（Node crypto 实现），
        execjs 以 stdin 方式运行 Node 无法解析 npm 模块，需拦截重定向到全局 CryptoJS"""
        # 删除 const/var/let CryptoJS = require('crypto-js') 整行（避免 IIFE 中的 TDZ 冲突）
        script = re.sub(
            r"(?:const|var|let)\s+CryptoJS\s*=\s*require\(['\"]crypto-js['\"]\)\s*;?",
            "",
            script
        )
        # 其他引用：require('crypto-js') → CryptoJS 全局变量
        script = re.sub(
            r"require\(['\"]crypto-js['\"]\)",
            "CryptoJS",
            script
        )
        return script

    # ==================== 执行 JS 生成变量 ====================

    def generate(self, script_ref: str, vars_snapshot: Dict[str, Any],
                 request_ctx: Optional[Dict[str, Any]] = None) -> JsGenResult:
        """执行一段前置 JS 脚本，返回其产出的动态变量字典

        :param script_ref: 内联脚本字符串，或 "@file:xxx.js" 文件引用
        :param vars_snapshot: 注入给 JS 的变量快照（静态层 + 响应缓存，只读语义）
        :param request_ctx: 本次请求上下文 {method, url, headers, query_params, body, body_type}
        """
        if not HAS_EXECJS:
            return JsGenResult(False, error="未安装 PyExecJS，请执行 pip install PyExecJS（需系统已安装 Node.js）")

        script_ref = (script_ref or "").strip()
        if not script_ref:
            return JsGenResult(True)

        # 外部文件引用读取
        try:
            user_script = self.resolve_script(script_ref)
        except (ValueError, FileNotFoundError, OSError) as e:
            return JsGenResult(False, error=f"JS 脚本加载失败: {e}")

        if not user_script.strip():
            return JsGenResult(True)

        # 拦截 require('crypto-js')，重定向到 prelude 内置 CryptoJS 兼容层
        user_script = self._patch_require(user_script)

        # 构建完整 JS：注入上下文 + 包裹用户脚本 + 归集产出
        full_source = self._build_source(user_script, vars_snapshot, request_ctx or {})

        try:
            ctx = execjs.compile(full_source)
            raw = ctx.call("__aits_run__")
        except Exception as e:
            # execjs 各类运行时错误统一收敛为失败结果
            return JsGenResult(False, error=f"JS 执行失败: {e}")

        # 解析 JS 返回的 JSON 信封 {vars, logs}
        try:
            envelope = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except (TypeError, ValueError) as e:
            return JsGenResult(False, error=f"JS 返回值解析失败: {e}")

        variables = envelope.get("vars") or {}
        if not isinstance(variables, dict):
            return JsGenResult(False, output=envelope.get("logs", ""),
                               error="JS 必须返回 JSON 对象（键值对变量）")
        logs = envelope.get("logs") or ""
        header_patches = envelope.get("header_patches") or []
        if not isinstance(header_patches, list):
            header_patches = []
        return JsGenResult(True, variables=variables, output=logs,
                           header_patches=header_patches)

    def _build_source(self, user_script: str, vars_snapshot: Dict[str, Any],
                      request_ctx: Dict[str, Any]) -> str:
        """构建完整可执行 JS 源码

        结构：
        - 注入 __vars__ / __request__ 只读上下文
        - console.log 收集到 __logs__
        - CryptoJS 兼容层（Node crypto 实现）
        - pm.environment.set/get shim + pm.request（Postman 风格数组 API）兼容存量脚本
        - 用户脚本以 IIFE 包裹，支持顶层 return
        - __aits_run__ 归集产出：return JSON 对象 + pm.environment.set 收集值 + 请求头补丁
        """
        return f"""
var __vars__ = {json.dumps(vars_snapshot, ensure_ascii=False, default=str)};
var __request__ = {json.dumps(request_ctx, ensure_ascii=False, default=str)};
var __logs__ = [];
var __out__ = {{}};

var console = {{
    log: function() {{ __logs__.push(Array.prototype.slice.call(arguments).join(" ")); }},
    warn: function() {{ __logs__.push("[WARN] " + Array.prototype.slice.call(arguments).join(" ")); }},
    error: function() {{ __logs__.push("[ERROR] " + Array.prototype.slice.call(arguments).join(" ")); }}
}};

// ==================== CryptoJS 兼容层（Node crypto 实现） ====================
var CryptoJS = (function() {{
    var _crypto = null;
    try {{ _crypto = require("crypto"); }} catch (e) {{}}
    var _md = function(algo, msg) {{
        if (!_crypto) throw new Error("crypto 模块不可用");
        return {{ toString: function() {{ return _crypto.createHash(algo).update(String(msg), "utf8").digest("hex"); }} }};
    }};
    var _hmac = function(algo, msg, key) {{
        if (!_crypto) throw new Error("crypto 模块不可用");
        return {{ toString: function() {{ return _crypto.createHmac(algo, String(key)).update(String(msg), "utf8").digest("hex"); }} }};
    }};
    return {{
        MD5: function(m) {{ return _md("md5", m); }},
        SHA1: function(m) {{ return _md("sha1", m); }},
        SHA256: function(m) {{ return _md("sha256", m); }},
        HmacSHA256: function(m, k) {{ return _hmac("sha256", m, k); }},
        HmacMD5: function(m, k) {{ return _hmac("md5", m, k); }},
        enc: {{
            Hex: {{ stringify: function(x) {{ return x.toString(); }} }},
            Base64: {{
                stringify: function(x) {{ return Buffer.from(String(x.toString()), "utf8").toString("base64"); }},
                parse: function(s) {{ return {{ toString: function() {{ return Buffer.from(String(s), "base64").toString("utf8"); }} }}; }}
            }},
            Utf8: {{
                stringify: function(x) {{ return String(x.toString()); }},
                parse: function(s) {{ return {{ toString: function() {{ return String(s); }} }}; }}
            }}
        }}
    }};
}})();

// ==================== pm.request（Postman 风格数组 API） ====================
function __attach_pm_list_methods__(arr) {{
    arr.find = function(fn) {{
        for (var i = 0; i < this.length; i++) {{ if (fn(this[i])) return this[i]; }}
        return undefined;
    }};
    arr.each = function(fn) {{ this.forEach(function(item) {{ fn(item); }}); }};
    arr.upsert = function(item) {{
        var found = false;
        for (var i = 0; i < this.length; i++) {{
            if (this[i].key === item.key) {{ this[i].value = item.value; found = true; break; }}
        }}
        if (!found) this.push(item);
    }};
    arr.add = function(item) {{ this.push(item); }};
    arr.toArray = function() {{ return this.slice(); }};
    arr.remove = function(key) {{
        for (var i = this.length - 1; i >= 0; i--) {{ if (this[i].key === key) this.splice(i, 1); }}
    }};
}}

var __request_headers__ = (__request__.headers || []).map(function(h) {{
    return {{ key: h.key || "", value: h.value || "", disabled: h.disabled || false }};
}});
__attach_pm_list_methods__(__request_headers__);

var __request_query__ = (__request__.query_params || []).map(function(q) {{
    return {{ key: q.key || "", value: q.value || "", disabled: q.disabled || false }};
}});
__attach_pm_list_methods__(__request_query__);

var __body_mode__ = __request__.body_type || "raw";
if (__body_mode__ === "form-data") __body_mode__ = "formdata";
if (__body_mode__ === "json" || __body_mode__ === "text" || __body_mode__ === "binary") __body_mode__ = "raw";

var __formdata_arr__ = [];
if (__body_mode__ === "formdata") {{
    var __raw_body_for_fd__ = __request__.body;
    if (Array.isArray(__raw_body_for_fd__)) {{
        __formdata_arr__ = __raw_body_for_fd__.map(function(item) {{
            if (typeof item === "object" && item !== null) {{
                return {{ key: item.key || "", value: String(item.value || ""), disabled: item.disabled || false }};
            }}
            return {{ key: "", value: String(item), disabled: false }};
        }});
    }} else if (typeof __raw_body_for_fd__ === "string") {{
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
__attach_pm_list_methods__(__formdata_arr__);

var __raw_body_str__ = "";
if (typeof __request__.body === "string") {{
    __raw_body_str__ = __request__.body;
}} else if (__request__.body !== null && __request__.body !== undefined) {{
    try {{ __raw_body_str__ = JSON.stringify(__request__.body); }} catch(e) {{ __raw_body_str__ = String(__request__.body); }}
}}

// 兼容存量 Postman 风格脚本：pm.environment.set 收集的变量作为回退产出
var pm = {{
    environment: {{
        set: function(k, v) {{ __out__[k] = v; }},
        get: function(k) {{ return (k in __out__) ? __out__[k] : __vars__[k]; }}
    }},
    globals: {{
        set: function(k, v) {{ __out__[k] = v; }},
        get: function(k) {{ return __vars__[k]; }}
    }},
    variables: {{
        set: function(k, v) {{ __out__[k] = v; }},
        get: function(k) {{ return (k in __out__) ? __out__[k] : __vars__[k]; }},
        replaceIn: function(str) {{
            return String(str == null ? "" : str).replace(/\{{\{{([^}}]+)\}}\}}/g, function(m, name) {{
                name = name.trim();
                if (name in __out__) return String(__out__[name]);
                if (name in __vars__) return String(__vars__[name]);
                return m;
            }});
        }}
    }},
    request: {{
        method: __request__.method || "GET",
        url: {{ raw: __request__.url || "", query: __request_query__, toString: function() {{ return this.raw; }} }},
        headers: __request_headers__,
        body: {{ mode: __body_mode__, raw: __raw_body_str__, formdata: __formdata_arr__ }}
    }}
}};

function __aits_run__() {{
    var __user_result__ = (function() {{
{user_script}
    }})();

    var vars = {{}};
    if (__user_result__ && typeof __user_result__ === "object") {{
        vars = __user_result__;                       // 推荐：return JSON 对象
    }} else if (typeof __user_result__ === "string" && __user_result__) {{
        try {{ vars = JSON.parse(__user_result__); }} catch (e) {{}}  // 兼容：return JSON 字符串
    }}
    for (var k in __out__) {{                          // 回退：pm.environment.set 收集值
        if (!(k in vars)) {{ vars[k] = __out__[k]; }}
    }}

    // 收集脚本对 pm.request.headers 的修改（新增或值变更，同名取最后一次）
    var __input_keys__ = {{}};
    (__request__.headers || []).forEach(function(h) {{
        if (h && h.key) {{ __input_keys__[String(h.key).toLowerCase()] = String(h.value || ""); }}
    }});
    var header_patches = [];
    var __patch_map__ = {{}};
    pm.request.headers.forEach(function(h) {{
        if (!h || !h.key || h.disabled) return;
        var lk = String(h.key).toLowerCase();
        var val = String(h.value || "");
        if (!(lk in __input_keys__) || __input_keys__[lk] !== val) {{
            if (lk in __patch_map__) {{ __patch_map__[lk].value = val; }}
            else {{ var p = {{ key: h.key, value: val }}; header_patches.push(p); __patch_map__[lk] = p; }}
        }}
        __input_keys__[lk] = val;
    }});

    return JSON.stringify({{ vars: vars, logs: __logs__.join("\\n"), header_patches: header_patches }});
}}
"""


def api_request_lifecycle(func):
    """接口请求生命周期装饰器（装饰器 + try-finally 实现）

    被装饰方法签名约定：async func(self, step, result, request_ctx, **kwargs)
    其中 self 必须持有：
    - self.var_store: ScenarioVarStore（双缓存变量仓库）
    - self.js_generator: JsEnvGenerator
    - self._collect_pre_scripts(step, kwargs): 返回本次请求需要执行的前置 JS 列表

    固定流程：
      [1] 请求前：重新执行全部前置 JS，产出写入请求级动态缓存；
      [2] 发起 HTTP 请求及后续逻辑（被装饰方法本体）；
      [3] finally：无论成功/失败/异常，清理本次生成的全部动态环境变量。
    """

    @functools.wraps(func)
    async def wrapper(self, step, result, request_ctx, **kwargs):
        pre_scripts: List[str] = []
        try:
            # ---------- [1] 请求前：JS 生成动态环境变量（每次都重新执行） ----------
            pre_scripts = self._collect_pre_scripts(step, kwargs)
            for script_ref in pre_scripts:
                gen = self.js_generator.generate(
                    script_ref,
                    vars_snapshot=self.var_store.readable_vars(),
                    request_ctx=request_ctx,
                )
                if gen.output:
                    result.console_log += gen.output + ("\n" if not gen.output.endswith("\n") else "")
                if not gen.success:
                    # JS 生成失败：记录错误但仍继续请求（由断言/状态码判定成败），保证清理逻辑可达
                    result.console_log += f"[LIFECYCLE] 前置JS执行失败: {gen.error}\n"
                    logger.warning(f"前置JS执行失败: {gen.error}")
                    continue
                # JS 返回的 JSON 对象解析后写入请求级动态缓存（不使用 os.environ）
                self.var_store.dynamic.load_dict(gen.variables)
                if gen.variables:
                    result.console_log += (
                        f"[LIFECYCLE] 前置JS生成 {len(gen.variables)} 个动态环境变量: "
                        f"{', '.join(gen.variables.keys())}\n"
                    )
                # 脚本对 pm.request.headers 的修改（如签名头注入）合并进请求上下文
                if gen.header_patches:
                    for patch in gen.header_patches:
                        pk = str(patch.get("key", "")).lower()
                        if not pk:
                            continue
                        merged = False
                        for h in request_ctx.get("headers") or []:
                            if isinstance(h, dict) and str(h.get("key", "")).lower() == pk:
                                h["value"] = str(patch.get("value", ""))
                                merged = True
                                break
                        if not merged:
                            request_ctx.setdefault("headers", []).append(
                                {"key": patch.get("key"), "value": str(patch.get("value", "")), "enabled": True}
                            )
                    result.console_log += (
                        f"[LIFECYCLE] 前置JS注入 {len(gen.header_patches)} 个请求头: "
                        f"{', '.join(str(p.get('key')) for p in gen.header_patches)}\n"
                    )

            # ---------- [2] 使用动态变量发起 HTTP 请求 ----------
            return await func(self, step, result, request_ctx, **kwargs)
        finally:
            # ---------- [3] 清理：无论成功/失败/异常必定执行，杜绝变量残留 ----------
            cleaned = self.var_store.dynamic.keys()
            self.var_store.clear_request_scope()
            if cleaned:
                result.console_log += (
                    f"[LIFECYCLE] 请求结束，已清理 {len(cleaned)} 个动态环境变量: "
                    f"{', '.join(cleaned)}\n"
                )
            logger.info(f"步骤 {step.get('step_name')} 生命周期结束，动态变量已清理: {cleaned}")

    return wrapper
