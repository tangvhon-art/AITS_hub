"""
Agent 公共工具函数

提供 LLM 输出解析等通用能力，消除各 Agent 中的重复代码。
"""
import json
import re
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _repair_json_newlines(candidate: str) -> str:
    """
    修复 JSON 字符串值中的未转义换行符。

    LLM 输出的 JSON 中，字符串值（如含 Markdown 的 content 字段）
    常包含未转义的换行符，导致 json.loads 失败。
    本函数遍历字符，在字符串内部将裸换行符替换为 \\n 转义序列。
    """
    repaired = []
    in_string = False
    escape = False
    for ch in candidate:
        if escape:
            escape = False
            repaired.append(ch)
            continue
        if ch == '\\':
            escape = True
            repaired.append(ch)
            continue
        if ch == '"':
            in_string = not in_string
            repaired.append(ch)
            continue
        if in_string:
            if ch == '\n':
                repaired.append('\\n')
                continue
            if ch == '\r':
                continue
            if ch == '\t':
                repaired.append('\\t')
                continue
        repaired.append(ch)
    return ''.join(repaired)


def _repair_array_as_object(candidate: str) -> str:
    """
    修复 LLM 常见的把对象花括号 {} 误写为数组方括号 [] 的问题。

    典型场景：LLM 输出 "cases": [["title": "...", ...]] 而非 [{"title": "...", ...}]
    策略：使用括号匹配算法，当 [ 后紧跟 "key": 模式时，将 [ 及其对应的 ] 替换为 {} 。
    """
    result = list(candidate)
    stack: list = []  # (position, should_convert_to_brace)
    i = 0
    n = len(candidate)
    while i < n:
        ch = candidate[i]
        if ch == '"':
            i += 1
            while i < n:
                if candidate[i] == '\\':
                    i += 2
                    continue
                if candidate[i] == '"':
                    break
                i += 1
        elif ch == '[':
            j = i + 1
            while j < n and candidate[j] in ' \t\n\r':
                j += 1
            if j < n and candidate[j] == '"':
                result[i] = '{'
                stack.append((i, True))
            else:
                stack.append((i, False))
        elif ch == ']':
            if stack:
                _, converted = stack.pop()
                if converted:
                    result[i] = '}'
        elif ch == '{':
            stack.append((i, False))
        elif ch == '}':
            if stack:
                stack.pop()
        i += 1
    return ''.join(result)


def _safe_json_loads(candidate: str) -> Optional[Dict[str, Any]]:
    """尝试解析 JSON，失败时依次修复未转义换行符、数组误写为对象后重试"""
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(_repair_json_newlines(candidate))
    except json.JSONDecodeError:
        pass
    try:
        repaired = _repair_array_as_object(candidate)
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass
    try:
        repaired = _repair_json_newlines(_repair_array_as_object(candidate))
        return json.loads(repaired)
    except json.JSONDecodeError:
        return None


def extract_json(content: str) -> Optional[Dict[str, Any]]:
    """
    从 LLM 输出文本中提取 JSON 对象。

    优先使用平衡括号匹配（支持嵌套对象），回退到贪婪正则。
    自动修复 JSON 字符串值中的未转义换行符。

    Args:
        content: LLM 返回的原始文本，可能包含 markdown 代码块、前后缀说明文字等。

    Returns:
        解析后的 dict；如果无法提取或解析失败，返回 None。
    """
    if not content:
        return None

    text = content.strip()

    # 1) 去除 markdown 代码块包裹
    fence_match = re.search(r'```(?:json)?\s*\n?(.*?)```', text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # 2) 平衡括号扫描：找到第一个完整的 {...} JSON 对象
    start = text.find('{')
    if start != -1:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    result = _safe_json_loads(candidate)
                    if result is not None:
                        return result
                    break  # 回退到正则

    # 3) 回退：贪婪正则（兼容旧实现）
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        result = _safe_json_loads(json_match.group(0))
        if result is not None:
            return result
        logger.warning("extract_json: 正则提取后 JSON 解析失败")

    return None


def extract_json_list(content: str) -> Optional[list]:
    """
    从 LLM 输出文本中提取 JSON 数组。

    Args:
        content: LLM 返回的原始文本。

    Returns:
        解析后的 list；如果无法提取或解析失败，返回 None。
    """
    if not content:
        return None

    text = content.strip()

    fence_match = re.search(r'```(?:json)?\s*\n?(.*?)```', text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    start = text.find('[')
    if start != -1:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    result = _safe_json_loads(candidate)
                    if result is not None:
                        return result
                    break

    json_match = re.search(r'\[[\s\S]*\]', text)
    if json_match:
        result = _safe_json_loads(json_match.group(0))
        if result is not None:
            return result

    return None
