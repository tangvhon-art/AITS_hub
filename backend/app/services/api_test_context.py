"""
接口测试变量上下文（双缓存隔离架构）

设计目标：
1. DynamicVarContext（动态环境变量缓存，请求级）：
   存放前置 JS 脚本生成的动态参数（token/签名/时间戳等），
   每次接口请求结束后必须全部清理，禁止残留污染下一次请求。
2. ExtractedVarCache（响应提取缓存，场景级）：
   存放接口响应提取值（jsonpath/regex/header/cookie）与后置脚本产出，
   与动态环境变量完全隔离，整个场景执行期间有效，供后续步骤引用。
3. 静态层（只读）：环境配置静态变量、base_url、extra_vars，场景内不清理。

约束：
- 禁止使用 os.environ 存储动态变量，禁止修改进程级系统环境变量；
- 变量查找优先级：动态缓存 > 响应缓存 > 静态层。
"""
import json
import re
from typing import Any, Dict, List, Optional

from app.services.mock_data_generator import mock_generator


class DynamicVarContext:
    """请求级动态环境变量上下文

    专门存放 JS 脚本输出的动态参数，提供 set/get/has/load_dict/keys/clear，
    每次接口请求生命周期结束（无论成功/失败/异常）都必须调用 clear()。
    """

    def __init__(self):
        self._vars: Dict[str, Any] = {}

    def set(self, name: str, value: Any):
        self._vars[name] = value

    def get(self, name: str, default: Any = None) -> Any:
        return self._vars.get(name, default)

    def has(self, name: str) -> bool:
        return name in self._vars

    def load_dict(self, data: Dict[str, Any]):
        """批量写入（JS 返回的 JSON 对象解析后写入）"""
        if data:
            self._vars.update(data)

    def keys(self) -> List[str]:
        return list(self._vars.keys())

    def all(self) -> Dict[str, Any]:
        return dict(self._vars)

    def clear(self):
        """清理本次请求生成的全部动态环境变量（生命周期收尾，必须执行）"""
        self._vars.clear()


class ExtractedVarCache:
    """场景级响应提取变量缓存

    存放接口响应取值结果（提取/后置脚本产出），与动态环境变量隔离：
    - 动态缓存 clear() 不影响本缓存；
    - 本缓存仅在场景执行结束时清理。
    """

    def __init__(self):
        self._vars: Dict[str, Any] = {}

    def set(self, name: str, value: Any):
        self._vars[name] = value

    def get(self, name: str, default: Any = None) -> Any:
        return self._vars.get(name, default)

    def has(self, name: str) -> bool:
        return name in self._vars

    def delete(self, name: str):
        self._vars.pop(name, None)

    def all(self) -> Dict[str, Any]:
        return dict(self._vars)

    def clear(self):
        self._vars.clear()


class ScenarioVarStore:
    """场景变量仓库：组合「动态缓存 + 响应缓存 + 静态层」三层

    接口请求逻辑只从本对象读取变量（不使用全局变量），
    替换语法兼容 {{var}} 与 ${var}，Mock 函数优先替换。
    """

    VAR_PATTERN = re.compile(r"\{\{\s*([\w.\-]+)\s*\}\}")
    DOLLAR_VAR_PATTERN = re.compile(r"\$\{\s*([\w.\-]+)\s*\}")

    def __init__(self):
        self.dynamic = DynamicVarContext()    # 请求级：JS 动态环境变量
        self.extracted = ExtractedVarCache()  # 场景级：响应提取缓存
        self.static: Dict[str, Any] = {}      # 场景级：静态环境变量（只读语义）
        self.mock_generator = mock_generator

    # ==================== 变量读写 ====================

    def get(self, name: str) -> Any:
        """按优先级取变量：动态 > 响应缓存 > 静态层"""
        if self.dynamic.has(name):
            return self.dynamic.get(name)
        if self.extracted.has(name):
            return self.extracted.get(name)
        return self.static.get(name)

    def has(self, name: str) -> bool:
        return self.dynamic.has(name) or self.extracted.has(name) or name in self.static

    def load_static(self, data: Dict[str, Any]):
        """加载静态变量（环境配置/extra_vars/外部引擎导入）"""
        if data:
            self.static.update(data)

    def clear_request_scope(self):
        """请求级清理：只清动态环境变量缓存，响应缓存与静态层不受影响"""
        self.dynamic.clear()

    def clear_all(self):
        """场景结束清理"""
        self.dynamic.clear()
        self.extracted.clear()

    def readable_vars(self) -> Dict[str, Any]:
        """供 JS 脚本读取的变量快照（静态 + 响应缓存 + 动态，按优先级合并）"""
        merged: Dict[str, Any] = {}
        merged.update(self.static)
        merged.update(self.extracted.all())
        merged.update(self.dynamic.all())
        return merged

    # ==================== 变量替换（从 VariableEngine 平移） ====================

    def replace(self, text: str) -> str:
        """替换文本中的 {{var}} 与 ${var}，Mock 函数优先"""
        if not text or not isinstance(text, str):
            return text

        # 第一步：Mock 函数替换（优先级最高）
        text = self.mock_generator.generate(text)

        def _replace_match(match):
            var_name = match.group(1)
            value = self.get(var_name)
            if value is None:
                return match.group(0)  # 未命中保留原样
            if isinstance(value, (dict, list)):
                return json.dumps(value, ensure_ascii=False)
            return str(value)

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
        """替换查询参数列表中的变量（与 headers 同构）"""
        return self.replace_headers(params)

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
