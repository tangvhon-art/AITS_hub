"""
多策略内容提取器

从 LLM 输出中提取结构化数据，按优先级尝试多种策略：
1. JSON 严格解析
2. extract_json() 平衡括号提取
3. Markdown 结构提取
4. 正则字段提取
5. 原文兜底（完整保留，不截断）
"""
import re
import logging
import json
from typing import Any, Dict, List, Optional

from app.agents.utils import extract_json, extract_json_list

logger = logging.getLogger(__name__)


class ContentExtractor:
    """多策略 LLM 输出提取器"""

    # ==================== 需求提取 ====================

    @staticmethod
    def extract_requirement(content: str) -> Dict[str, str]:
        """
        从 LLM 输出提取需求文档。

        Returns:
            {"title": str, "content": str}
        """
        if not content or not content.strip():
            return {"title": "AI 生成需求", "content": ""}

        # 策略 1: JSON 解析
        parsed = extract_json(content)
        if parsed and isinstance(parsed, dict):
            title = parsed.get("title") or parsed.get("标题") or ""
            body = parsed.get("content") or parsed.get("内容") or parsed.get("body") or ""
            if title and body:
                logger.info("需求提取: JSON 解析成功")
                return {"title": str(title)[:200], "content": str(body)}
            if body:
                return {"title": str(title)[:200] if title else ContentExtractor._extract_title_from_markdown(content), "content": str(body)}

        # 策略 2: 正则字段提取（JSON 格式不规范但字段可见）
        title_match = re.search(r'"title"\s*:\s*"([^"]*)"', content)
        content_start = re.search(r'"content"\s*:\s*"', content)
        if title_match and content_start:
            title = title_match.group(1)
            body_start = content_start.end()
            body_text = content[body_start:].rstrip()
            if body_text.endswith('}'):
                body_text = body_text[:-1].rstrip()
            if body_text.endswith('"'):
                body_text = body_text[:-1]
            body = body_text.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
            if title and body:
                logger.info("需求提取: 正则字段提取成功")
                return {"title": title[:200], "content": body}

        # 策略 3: Markdown 结构提取
        result = ContentExtractor._extract_markdown_document(content)
        if result["title"] and result["content"]:
            logger.info("需求提取: Markdown 结构提取成功")
            return result

        # 策略 4: 原文兜底（不截断）
        logger.info("需求提取: 使用原文兜底")
        title = ContentExtractor._extract_title_from_markdown(content)
        return {"title": title, "content": content.strip()}

    # ==================== 用例提取 ====================

    @staticmethod
    def extract_test_cases(content: str) -> List[Dict[str, Any]]:
        """
        从 LLM 输出提取测试用例列表。

        Returns:
            [{"title", "module", "priority", "case_type", "preconditions", "steps", "expected_result", "bdd_content"}]
        """
        if not content or not content.strip():
            return []

        # 策略 1: JSON 对象解析 ({"cases": [...]})
        parsed = extract_json(content)
        if parsed:
            cases = None
            if isinstance(parsed, dict):
                cases = parsed.get("cases") or parsed.get("用例") or []
            elif isinstance(parsed, list):
                cases = parsed
            if cases and isinstance(cases, list) and len(cases) > 0:
                logger.info(f"用例提取: JSON 解析成功, {len(cases)} 条")
                return [ContentExtractor._normalize_test_case(c) for c in cases]

        # 策略 2: JSON 数组解析
        case_list = extract_json_list(content)
        if case_list and isinstance(case_list, list) and len(case_list) > 0:
            logger.info(f"用例提取: JSON 数组解析成功, {len(case_list)} 条")
            return [ContentExtractor._normalize_test_case(c) for c in case_list]

        # 策略 3: Markdown 列表提取
        cases = ContentExtractor._extract_cases_from_markdown(content)
        if cases:
            logger.info(f"用例提取: Markdown 提取成功, {len(cases)} 条")
            return cases

        # 策略 4: 原文兜底（单条用例，完整内容）
        logger.info("用例提取: 使用原文兜底（单条）")
        title = ContentExtractor._extract_title_from_markdown(content)
        return [{
            "title": title[:200],
            "module": "",
            "priority": "P2",
            "case_type": "functional",
            "preconditions": "",
            "steps": [{"action": "查看 AI 生成的用例内容", "expected": "内容完整可读"}],
            "expected_result": content.strip()[:500],
            "bdd_content": "",
        }]

    @staticmethod
    def _normalize_test_case(raw: Any) -> Dict[str, Any]:
        """将原始数据归一化为标准用例格式"""
        if not isinstance(raw, dict):
            return {
                "title": str(raw)[:200] if raw else "未命名用例",
                "module": "", "priority": "P2", "case_type": "functional",
                "preconditions": "", "steps": [], "expected_result": "", "bdd_content": "",
            }

        # steps 可能是 list 或 string
        steps = raw.get("steps") or raw.get("步骤") or []
        if isinstance(steps, str):
            steps = [{"action": steps, "expected": ""}]

        priority = raw.get("priority") or raw.get("优先级") or "P2"
        if priority not in ("P0", "P1", "P2", "P3"):
            priority = "P2"

        case_type = raw.get("case_type") or raw.get("用例类型") or "functional"
        if case_type not in ("functional", "performance", "security"):
            case_type = "functional"

        return {
            "title": str(raw.get("title") or raw.get("标题") or raw.get("name") or "未命名用例")[:200],
            "module": str(raw.get("module") or raw.get("模块") or ""),
            "priority": priority,
            "case_type": case_type,
            "preconditions": str(raw.get("preconditions") or raw.get("前置条件") or ""),
            "steps": steps,
            "expected_result": str(raw.get("expected_result") or raw.get("预期结果") or ""),
            "bdd_content": str(raw.get("bdd_content") or raw.get("BDD") or ""),
        }

    # ==================== 接口用例提取 ====================

    @staticmethod
    def extract_api_cases(content: str) -> List[Dict[str, Any]]:
        """
        从 LLM 输出提取接口测试用例列表。

        Returns:
            [{"name", "priority", "description", "request": {...}, "assertions": [...]}]
        """
        if not content or not content.strip():
            return []

        # 策略 1: JSON 解析
        parsed = extract_json(content)
        if parsed:
            cases = None
            if isinstance(parsed, dict):
                cases = parsed.get("cases") or []
            elif isinstance(parsed, list):
                cases = parsed
            if cases and isinstance(cases, list) and len(cases) > 0:
                logger.info(f"接口用例提取: JSON 解析成功, {len(cases)} 条")
                return [ContentExtractor._normalize_api_case(c) for c in cases if isinstance(c, dict) and c.get("name")]

        # 策略 2: JSON 数组解析
        case_list = extract_json_list(content)
        if case_list and isinstance(case_list, list) and len(case_list) > 0:
            result = [ContentExtractor._normalize_api_case(c) for c in case_list if isinstance(c, dict) and c.get("name")]
            if result:
                logger.info(f"接口用例提取: JSON 数组解析成功, {len(result)} 条")
                return result

        logger.info("接口用例提取: 无法提取，返回空列表")
        return []

    @staticmethod
    def _normalize_api_case(raw: Dict[str, Any]) -> Dict[str, Any]:
        """归一化接口用例"""
        priority = raw.get("priority") or "P2"
        if priority not in ("P0", "P1", "P2", "P3"):
            priority = "P2"

        request = raw.get("request") or {}
        if not isinstance(request, dict):
            request = {}

        assertions = raw.get("assertions") or []
        if not isinstance(assertions, list):
            assertions = []

        return {
            "name": str(raw.get("name") or raw.get("名称") or "未命名用例")[:200],
            "priority": priority,
            "description": str(raw.get("description") or raw.get("描述") or ""),
            "request": {
                "headers": request.get("headers") or {},
                "params": request.get("params") or {},
                "body": request.get("body") or {},
            },
            "assertions": assertions,
        }

    # ==================== 缺陷提取 ====================

    @staticmethod
    def extract_defect(content: str) -> Dict[str, Any]:
        """
        从 LLM 输出提取缺陷信息。

        Returns:
            {"title", "description", "severity", "priority", "root_cause",
             "root_cause_category", "reproduce_steps", "expected_result", "actual_result"}
        """
        defaults = {
            "title": "执行失败",
            "description": "",
            "severity": "major",
            "priority": "P2",
            "root_cause": "待分析",
            "root_cause_category": "other",
            "reproduce_steps": "",
            "expected_result": "",
            "actual_result": "",
        }

        if not content or not content.strip():
            return defaults

        # 策略 1: JSON 解析
        parsed = extract_json(content)
        if parsed and isinstance(parsed, dict):
            logger.info("缺陷提取: JSON 解析成功")
            return ContentExtractor._merge_defect(parsed, defaults)

        # 策略 2: 正则字段提取
        result = ContentExtractor._extract_defect_by_regex(content)
        if result:
            logger.info("缺陷提取: 正则提取成功")
            return ContentExtractor._merge_defect(result, defaults)

        # 策略 3: 原文兜底
        logger.info("缺陷提取: 使用原文兜底")
        return {**defaults, "title": "执行失败（AI 分析）", "description": content.strip(), "root_cause": content.strip()[:500]}

    @staticmethod
    def _merge_defect(data: Dict, defaults: Dict) -> Dict[str, Any]:
        """合并缺陷数据，填充默认值"""
        severity = data.get("severity") or defaults["severity"]
        if severity not in ("blocker", "critical", "major", "minor", "trivial"):
            severity = defaults["severity"]

        priority = data.get("priority") or defaults["priority"]
        if priority not in ("P0", "P1", "P2", "P3"):
            priority = defaults["priority"]

        category = data.get("root_cause_category") or defaults["root_cause_category"]
        if category not in ("frontend", "backend", "data", "environment", "requirement", "other"):
            category = defaults["root_cause_category"]

        return {
            "title": str(data.get("title") or defaults["title"])[:200],
            "description": str(data.get("description") or ""),
            "severity": severity,
            "priority": priority,
            "root_cause": str(data.get("root_cause") or defaults["root_cause"]),
            "root_cause_category": category,
            "reproduce_steps": str(data.get("reproduce_steps") or ""),
            "expected_result": str(data.get("expected_result") or ""),
            "actual_result": str(data.get("actual_result") or ""),
        }

    # ==================== 评审提取 ====================

    @staticmethod
    def extract_review(content: str) -> Dict[str, Any]:
        """
        从 LLM 输出提取评审结果。

        Returns:
            {"score", "passed", "summary", "issues", "overall_suggestions"}
        """
        defaults = {
            "score": 60,
            "passed": False,
            "summary": "评审完成",
            "issues": [],
            "overall_suggestions": [],
        }

        if not content or not content.strip():
            return defaults

        # 策略 1: JSON 解析
        parsed = extract_json(content)
        if parsed and isinstance(parsed, dict):
            logger.info("评审提取: JSON 解析成功")
            score = parsed.get("score")
            try:
                score = int(score) if score is not None else 60
            except (ValueError, TypeError):
                score = 60
            return {
                "score": max(0, min(100, score)),
                "passed": bool(parsed.get("passed", score >= 80)),
                "summary": str(parsed.get("summary") or "评审完成")[:200],
                "issues": parsed.get("issues") or [],
                "overall_suggestions": parsed.get("overall_suggestions") or [],
            }

        # 策略 2: 正则提取评分
        score_match = re.search(r'(\d+)\s*分', content)
        if score_match:
            score = int(score_match.group(1))
            logger.info(f"评审提取: 正则提取成功, score={score}")
            return {
                **defaults,
                "score": max(0, min(100, score)),
                "passed": score >= 80,
                "summary": content.strip()[:200],
            }

        # 策略 3: 原文兜底
        logger.info("评审提取: 使用原文兜底")
        return {**defaults, "summary": content.strip()[:200]}

    # ==================== 报告提取 ====================

    @staticmethod
    def extract_report(content: str) -> str:
        """
        从 LLM 输出提取报告内容（Markdown 格式，直接使用）。

        Returns:
            Markdown 格式的报告内容字符串
        """
        if not content or not content.strip():
            return "# 测试报告\n\n报告生成失败，请重试。"

        # 报告是 Markdown 格式，直接使用完整内容
        return content.strip()

    # ==================== 通用工具方法 ====================

    @staticmethod
    def _extract_title_from_markdown(content: str) -> str:
        """从 Markdown 内容提取标题"""
        # 尝试一级标题
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()[:200]
        # 尝试二级标题
        match = re.search(r'^##\s+(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()[:200]
        # 尝试第一行非空行
        for line in content.strip().split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('```'):
                return line[:200]
        return "AI 生成需求"

    @staticmethod
    def _extract_markdown_document(content: str) -> Dict[str, str]:
        """从 Markdown 提取标题和内容"""
        title = ContentExtractor._extract_title_from_markdown(content)
        # 移除标题行后的内容作为正文
        lines = content.strip().split('\n')
        body_lines = []
        title_removed = False
        for line in lines:
            if not title_removed and (line.strip().startswith('# ') or line.strip().startswith('## ')):
                title_removed = True
                continue
            body_lines.append(line)
        body = '\n'.join(body_lines).strip()
        if not body:
            body = content.strip()
        return {"title": title, "content": body}

    @staticmethod
    def _extract_cases_from_markdown(content: str) -> List[Dict[str, Any]]:
        """从 Markdown 列表提取用例"""
        cases = []
        # 匹配 "### 用例名称" 或 "## 用例名称" 开头的区块
        blocks = re.split(r'^#{2,3}\s+', content, flags=re.MULTILINE)
        for block in blocks[1:]:  # 跳过第一块（标题前内容）
            lines = block.strip().split('\n')
            if not lines:
                continue
            title = lines[0].strip()[:200]
            if not title:
                continue
            body = '\n'.join(lines[1:]).strip()
            cases.append({
                "title": title,
                "module": "",
                "priority": "P2",
                "case_type": "functional",
                "preconditions": "",
                "steps": [{"action": "查看用例详情", "expected": "执行成功"}],
                "expected_result": body[:500],
                "bdd_content": "",
            })
        return cases

    @staticmethod
    def _extract_defect_by_regex(content: str) -> Optional[Dict[str, Any]]:
        """正则提取缺陷字段"""
        patterns = {
            "title": r'(?:标题|title)[：:]\s*(.+)',
            "severity": r'(?:严重程度|severity)[：:]\s*(\w+)',
            "priority": r'(?:优先级|priority)[：:]\s*(\w+)',
            "root_cause": r'(?:根因|root_cause)[：:]\s*(.+)',
            "root_cause_category": r'(?:根因分类|root_cause_category)[：:]\s*(\w+)',
            "reproduce_steps": r'(?:复现步骤|reproduce_steps)[：:]\s*([\s\S]+?)(?=\n(?:预期|expected|实际|actual|严重|优先|根因|标题|$))',
            "expected_result": r'(?:预期结果|expected_result)[：:]\s*(.+)',
            "actual_result": r'(?:实际结果|actual_result)[：:]\s*(.+)',
        }
        result = {}
        for field, pattern in patterns.items():
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                result[field] = match.group(1).strip()
        return result if result else None
