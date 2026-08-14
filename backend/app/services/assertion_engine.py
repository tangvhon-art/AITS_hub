"""
断言引擎
支持9种断言类型: status_code, response_time, header, jsonpath, xpath, contains, equals, regex, script
操作符: equals, not_equals, contains, not_contains, less_than, greater_than, matches, in_range
"""
import re
import json
from typing import Any, Dict, List, Optional, Tuple

try:
    from jsonpath_ng import parse as jsonpath_parse
    HAS_JSONPATH = True
except ImportError:
    HAS_JSONPATH = False

try:
    from lxml import etree
    HAS_LXML = True
except ImportError:
    HAS_LXML = False


class AssertionResult:
    """断言结果"""

    def __init__(self, passed: bool, assert_type: str, target: str, operator: str,
                 expected: Any, actual: Any, message: str = ""):
        self.passed = passed
        self.assert_type = assert_type
        self.target = target
        self.operator = operator
        self.expected = expected
        self.actual = actual
        self.message = message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "assert_type": self.assert_type,
            "target": self.target,
            "operator": self.operator,
            "expected": self.expected,
            "actual": self.actual,
            "message": self.message,
        }


class AssertionEngine:
    """断言引擎"""

    def __init__(self):
        self.operators = {
            "equals": self._op_equals,
            "not_equals": self._op_not_equals,
            "contains": self._op_contains,
            "not_contains": self._op_not_contains,
            "less_than": self._op_less_than,
            "greater_than": self._op_greater_than,
            "matches": self._op_matches,
            "in_range": self._op_in_range,
        }

    def run_all(self, assertions: List[Dict[str, Any]], response) -> List[AssertionResult]:
        """运行所有断言"""
        results = []
        for assertion in assertions:
            if not assertion.get("enabled", True):
                continue
            result = self.run_single(assertion, response)
            results.append(result)
        return results

    def run_single(self, assertion: Dict[str, Any], response) -> AssertionResult:
        """运行单个断言"""
        assert_type = assertion.get("assert_type", "")
        target = assertion.get("assert_target", "")
        operator = assertion.get("operator", "equals")
        expected = assertion.get("expected_value", "")

        try:
            actual = self._extract_actual(assert_type, target, response)
            op_func = self.operators.get(operator, self._op_equals)
            passed, message = op_func(actual, expected)
            return AssertionResult(passed, assert_type, target, operator, expected, actual, message)
        except Exception as e:
            return AssertionResult(False, assert_type, target, operator, expected, None,
                                   f"断言执行异常: {e}")

    def _extract_actual(self, assert_type: str, target: str, response) -> Any:
        """提取实际值"""
        if assert_type == "status_code":
            return response.status_code
        if assert_type == "response_time":
            return response.elapsed_ms
        if assert_type == "header":
            return response.headers.get(target, "")
        if assert_type == "jsonpath":
            return self._extract_jsonpath(target, response)
        if assert_type == "xpath":
            return self._extract_xpath(target, response)
        if assert_type == "contains":
            return response.body
        if assert_type == "equals":
            return response.body
        if assert_type == "regex":
            return response.body
        if assert_type == "script":
            return None  # 脚本断言由 script_engine 处理
        return None

    def _extract_jsonpath(self, expr: str, response) -> Any:
        """JSONPath 提取"""
        if not HAS_JSONPATH:
            return None
        try:
            data = response.json()
            if data is None:
                return None
            jsonpath_expr = jsonpath_parse(expr)
            matches = [m.value for m in jsonpath_expr.find(data)]
            if len(matches) == 1:
                return matches[0]
            return matches
        except Exception:
            return None

    def _extract_xpath(self, expr: str, response) -> Any:
        """XPath 提取"""
        if not HAS_LXML:
            return None
        try:
            root = etree.fromstring(response.body.encode())
            result = root.xpath(expr)
            if isinstance(result, list) and len(result) == 1:
                return result[0]
            return result
        except Exception:
            return None

    # ==================== 操作符实现 ====================
    def _op_equals(self, actual: Any, expected: Any) -> Tuple[bool, str]:
        """等于"""
        try:
            # 尝试类型转换
            if isinstance(expected, str):
                if expected.isdigit() and isinstance(actual, (int, float)):
                    expected = type(actual)(expected)
                elif expected.lower() in ("true", "false"):
                    expected = expected.lower() == "true"
            passed = str(actual) == str(expected) or actual == expected
            return passed, "" if passed else f"期望 {expected}，实际 {actual}"
        except Exception as e:
            return False, f"比较异常: {e}"

    def _op_not_equals(self, actual: Any, expected: Any) -> Tuple[bool, str]:
        """不等于"""
        passed, _ = self._op_equals(actual, expected)
        return not passed, "" if not passed else f"值不应等于 {expected}"

    def _op_contains(self, actual: Any, expected: Any) -> Tuple[bool, str]:
        """包含"""
        actual_str = str(actual) if actual is not None else ""
        expected_str = str(expected) if expected is not None else ""
        passed = expected_str in actual_str
        return passed, "" if passed else f"响应中不包含 {expected}"

    def _op_not_contains(self, actual: Any, expected: Any) -> Tuple[bool, str]:
        """不包含"""
        passed, _ = self._op_contains(actual, expected)
        return not passed, "" if not passed else f"响应中不应包含 {expected}"

    def _op_less_than(self, actual: Any, expected: Any) -> Tuple[bool, str]:
        """小于"""
        try:
            actual_num = float(actual)
            expected_num = float(expected)
            passed = actual_num < expected_num
            return passed, "" if passed else f"{actual_num} 不小于 {expected_num}"
        except (ValueError, TypeError):
            return False, f"无法比较: actual={actual}, expected={expected}"

    def _op_greater_than(self, actual: Any, expected: Any) -> Tuple[bool, str]:
        """大于"""
        try:
            actual_num = float(actual)
            expected_num = float(expected)
            passed = actual_num > expected_num
            return passed, "" if passed else f"{actual_num} 不大于 {expected_num}"
        except (ValueError, TypeError):
            return False, f"无法比较: actual={actual}, expected={expected}"

    def _op_matches(self, actual: Any, expected: Any) -> Tuple[bool, str]:
        """正则匹配"""
        try:
            actual_str = str(actual) if actual is not None else ""
            passed = bool(re.search(str(expected), actual_str))
            return passed, "" if passed else f"不匹配正则: {expected}"
        except re.error as e:
            return False, f"正则表达式错误: {e}"

    def _op_in_range(self, actual: Any, expected: Any) -> Tuple[bool, str]:
        """在范围内，expected 格式: min,max"""
        try:
            actual_num = float(actual)
            if isinstance(expected, str):
                parts = expected.split(",")
                min_val = float(parts[0].strip())
                max_val = float(parts[1].strip())
            elif isinstance(expected, (list, tuple)) and len(expected) == 2:
                min_val, max_val = float(expected[0]), float(expected[1])
            else:
                return False, f"范围格式错误: {expected}"
            passed = min_val <= actual_num <= max_val
            return passed, "" if passed else f"{actual_num} 不在 [{min_val}, {max_val}] 范围内"
        except (ValueError, TypeError):
            return False, f"范围比较失败: actual={actual}, expected={expected}"
