"""
字符工具（2 个）：文本对比 / 正则工具
"""
import difflib
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import List

from app.services.data_tools.base import data_tool, InvalidParamError, ParseError, ToolTimeoutError

# 正则执行线程池（共享，避免每次调用创建线程）
_REGEX_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="regex-tool")
REGEX_TIMEOUT = 2          # 秒
MAX_TEXT_LEN = 10 * 1024   # 10KB


@data_tool(
    name="text_compare", title="文本对比", category="text",
    description="两段文本逐行/逐字符 Diff，输出差异行（新增/删除/修改）",
    parameters={
        "type": "object",
        "properties": {
            "text_a": {"type": "string", "title": "基准文本", "description": "基准文本", "x-multiline": True},
            "text_b": {"type": "string", "title": "对比文本", "description": "对比文本", "x-multiline": True},
            "mode": {"type": "string", "title": "对比模式", "enum": ["line", "char"],
                     "x-enum-labels": ["逐行", "逐字符"], "description": "逐行 / 逐字符，默认逐行"},
            "ignore_whitespace": {"type": "boolean", "title": "忽略空白", "description": "忽略空白差异"},
            "ignore_case": {"type": "boolean", "title": "忽略大小写", "description": "忽略大小写差异"},
        },
        "required": ["text_a", "text_b"],
    },
    is_generator=False,
)
def text_compare(text_a: str, text_b: str, mode: str = "line",
                 ignore_whitespace: bool = False, ignore_case: bool = False) -> dict:
    a = text_a or ""
    b = text_b or ""

    if ignore_case:
        a, b = a.lower(), b.lower()
    if ignore_whitespace:
        a, b = re.sub(r"\s+", " ", a).strip(), re.sub(r"\s+", " ", b).strip()

    if mode == "char":
        sm = difflib.SequenceMatcher(None, a, b)
        diff_lines = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            old = a[i1:i2]
            new = b[j1:j2]
            if tag == "replace":
                diff_lines.append({"op": "changed", "old": old, "new": new})
            elif tag == "delete":
                diff_lines.append({"op": "removed", "old": old, "new": None})
            elif tag == "insert":
                diff_lines.append({"op": "added", "old": None, "new": new})
        return {"equal": len(diff_lines) == 0, "diff_lines": diff_lines, "diff_count": len(diff_lines)}

    # 逐行模式
    lines_a = a.splitlines()
    lines_b = b.splitlines()
    differ = difflib.Differ()
    diff = []
    added_line, removed_line = 1, 1
    for line in differ.compare(lines_a, lines_b):
        if line.startswith("  "):
            removed_line += 1
            added_line += 1
        elif line.startswith("- "):
            diff.append({"op": "removed", "line_no": removed_line, "content": line[2:]})
            removed_line += 1
        elif line.startswith("+ "):
            diff.append({"op": "added", "line_no": added_line, "content": line[2:]})
            added_line += 1
        elif line.startswith("? "):
            # Differ 的标记行，合并进上一条
            if diff:
                diff[-1]["marker"] = line[2:]
    return {"equal": len(diff) == 0, "diff_lines": diff, "diff_count": len(diff)}


_FLAG_MAP = {
    "i": re.IGNORECASE,
    "m": re.MULTILINE,
    "s": re.DOTALL,
    "x": re.VERBOSE,
}


def _run_regex(pattern: str, text: str, action: str, replacement: str, flags: list) -> dict:
    """在独立线程执行正则，带超时保护"""
    try:
        flag_int = 0
        for f in flags or []:
            flag_int |= _FLAG_MAP.get(str(f), 0)
        compiled = re.compile(pattern, flag_int)

        if action == "validate":
            return {"valid": True, "message": "正则表达式合法"}
        if action == "match":
            m = compiled.search(text)
            if not m:
                return {"matched": False, "groups": []}
            return {"matched": True, "groups": list(m.groups()),
                    "match": m.group(0), "start": m.start(), "end": m.end()}
        if action == "extract":
            matches = compiled.findall(text)
            return {"matches": matches, "count": len(matches)}
        if action == "replace":
            result = compiled.sub(replacement, text)
            return {"result": result, "changed": result != text}
        raise InvalidParamError("action", "仅支持 match/extract/replace/validate")
    except re.error as e:
        raise ParseError(f"正则表达式错误: {e}")


@data_tool(
    name="regex_tool", title="正则工具", category="text",
    description="正则匹配/提取/替换/校验，带 2 秒超时保护防止灾难性回溯",
    parameters={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "title": "正则表达式", "description": "正则表达式"},
            "text": {"type": "string", "title": "目标文本", "description": "目标文本（validate 动作可空）", "x-multiline": True},
            "action": {"type": "string", "title": "操作", "enum": ["match", "extract", "replace", "validate"],
                       "x-enum-labels": ["匹配", "提取", "替换", "校验表达式"],
                       "description": "匹配 / 提取 / 替换 / 校验表达式"},
            "replacement": {"type": "string", "title": "替换文本", "description": "replace 动作时的替换文本"},
            "flags": {"type": "array", "title": "正则标志", "items": {"type": "string", "enum": ["i", "m", "s", "x"]},
                      "x-enum-labels": ["忽略大小写（i）", "多行（m）", "DotAll（s）", "详细模式（x）"],
                      "description": "正则标志：忽略大小写 / 多行 / DotAll / 详细模式"},
        },
        "required": ["pattern", "action"],
    },
    is_generator=False,
)
def regex_tool(pattern: str, action: str, text: str = "", replacement: str = "", flags: list = None) -> dict:
    if not pattern:
        raise InvalidParamError("pattern", "正则表达式不能为空")
    if len(text or "") > MAX_TEXT_LEN:
        raise InvalidParamError("text", f"文本长度超过 {MAX_TEXT_LEN} 上限")
    future = _REGEX_EXECUTOR.submit(_run_regex, pattern, text or "", action, replacement, flags or [])
    try:
        return future.result(timeout=REGEX_TIMEOUT)
    except FutureTimeout:
        raise ToolTimeoutError("正则执行超时（2s），可能存在灾难性回溯")
    except (ParseError, InvalidParamError):
        raise
    except Exception as e:  # noqa: BLE001
        raise ParseError(f"正则执行失败: {e}")
