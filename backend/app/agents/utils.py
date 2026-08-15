"""
Agent 公共工具函数

提供 LLM 输出解析等通用能力，消除各 Agent 中的重复代码。
"""
import json
import re
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def extract_json(content: str) -> Optional[Dict[str, Any]]:
    """
    从 LLM 输出文本中提取 JSON 对象。

    优先使用平衡括号匹配（支持嵌套对象），回退到贪婪正则。

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
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break  # 回退到正则

    # 3) 回退：贪婪正则（兼容旧实现）
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            logger.warning("extract_json: 正则提取后 JSON 解析失败")
            return None

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
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break

    json_match = re.search(r'\[[\s\S]*\]', text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            return None

    return None
