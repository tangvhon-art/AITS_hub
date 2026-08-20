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

        steps = ContentExtractor._normalize_steps(raw.get("steps") or raw.get("步骤") or [])

        priority = raw.get("priority") or raw.get("优先级") or "P2"
        if priority not in ("P0", "P1", "P2", "P3"):
            priority = "P2"

        case_type = raw.get("case_type") or raw.get("用例类型") or raw.get("type") or "functional"
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

    @staticmethod
    def _normalize_steps(steps: Any) -> List[Dict[str, str]]:
        """
        深度归一化测试步骤数组。

        处理以下异常情况：
        - steps 为字符串 → 包装为单步骤
        - steps 为嵌套数组 [[...], [...]] → 展平
        - 步骤元素为列表/元组而非字典 → 尝试转换为字典
        - 步骤使用中文键名 → 映射为英文键名
        - 步骤缺少 action/expected 字段 → 填充默认值
        """
        if isinstance(steps, str):
            return [{"action": steps, "expected": ""}] if steps.strip() else []

        if not isinstance(steps, list):
            return []

        normalized: List[Dict[str, str]] = []
        for step in steps:
            if step is None:
                continue
            if isinstance(step, str):
                normalized.append({"action": step, "expected": ""})
                continue
            if isinstance(step, dict):
                # 映射中文键名到英文
                action = step.get("action") or step.get("操作") or step.get("操作描述") or step.get("步骤") or ""
                expected = step.get("expected") or step.get("预期") or step.get("预期结果") or step.get("结果") or ""
                normalized.append({"action": str(action), "expected": str(expected)})
                continue
            if isinstance(step, list):
                # 嵌套数组，尝试提取 key-value 对
                action = ""
                expected = ""
                for item in step:
                    if isinstance(item, str):
                        if not action:
                            action = item
                        else:
                            expected = item
                    elif isinstance(item, (list, tuple)) and len(item) >= 2:
                        key, val = str(item[0]), str(item[1])
                        if "action" in key or "操作" in key:
                            action = val
                        elif "expected" in key or "预期" in key:
                            expected = val
                if action or expected:
                    normalized.append({"action": action, "expected": expected})
                continue
        return normalized

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
        从 LLM 输出提取评审结果（Markdown 格式）。

        支持两种格式：
        1. 新格式：Markdown 章节（## 评分、## 问题列表、## 遗漏场景、## 整体改进建议、## 分组评价）
        2. 旧格式：JSON（向后兼容）

        Returns:
            {"score", "passed", "summary", "issues", "overall_suggestions", "group_reviews", "missing_scenarios"}
        """
        defaults = {
            "score": 60,
            "passed": False,
            "summary": "评审完成",
            "issues": [],
            "overall_suggestions": [],
            "group_reviews": [],
            "missing_scenarios": [],
        }

        if not content or not content.strip():
            logger.warning("评审提取: 内容为空")
            return defaults

        # 策略 1: 尝试 JSON 解析（向后兼容旧格式）
        parsed = extract_json(content)
        if parsed and isinstance(parsed, dict) and ("score" in parsed or "issues" in parsed):
            logger.info("评审提取: JSON 解析成功（旧格式兼容）")
            score = parsed.get("score")
            try:
                score = int(score) if score is not None else 60
            except (ValueError, TypeError):
                score = 60
            return {
                "score": max(0, min(100, score)),
                "passed": bool(parsed.get("passed", score >= 70)),
                "summary": str(parsed.get("summary") or "评审完成")[:200],
                "issues": parsed.get("issues") or [],
                "overall_suggestions": parsed.get("overall_suggestions") or [],
                "group_reviews": parsed.get("group_reviews") or [],
                "missing_scenarios": parsed.get("missing_scenarios") or [],
            }

        # 策略 2: Markdown 解析（新格式）
        logger.info("评审提取: 使用 Markdown 解析")
        result = {**defaults}

        # 去除代码块标记
        clean = content.strip()
        if clean.startswith("```"):
            clean = re.sub(r'^```\w*\n?', '', clean)
            clean = re.sub(r'\n?```$', '', clean)

        # 按 ## 标题分割章节
        sections = re.split(r'\n##\s+', clean)

        # 如果没有 ## 分割，尝试按 # 分割
        if len(sections) <= 1:
            sections = re.split(r'\n#\s+', clean)

        # 去除开头的空 section
        sections = [s.strip() for s in sections if s.strip()]

        for section in sections:
            first_line = section.split('\n')[0].strip().lower()

            # 提取评分
            if 'score' in first_line or '评分' in first_line:
                score_match = re.search(r'score\s*[:：]\s*(\d+)', section, re.IGNORECASE)
                if score_match:
                    score = int(score_match.group(1))
                    result["score"] = max(0, min(100, score))
                    result["passed"] = score >= 70
                else:
                    # 尝试匹配 "评分：85" 或 "85分"
                    score_match = re.search(r'(\d+)\s*分?', section)
                    if score_match:
                        score = int(score_match.group(1))
                        if 0 <= score <= 100:
                            result["score"] = score
                            result["passed"] = score >= 70

                passed_match = re.search(r'passed\s*[:：]\s*(true|false)', section, re.IGNORECASE)
                if passed_match:
                    result["passed"] = passed_match.group(1).lower() == "true"

                summary_match = re.search(r'summary\s*[:：]\s*(.+)', section, re.IGNORECASE)
                if summary_match:
                    result["summary"] = summary_match.group(1).strip()[:200]

            # 提取问题列表
            elif '问题' in first_line or 'issue' in first_line:
                issues = ContentExtractor._parse_markdown_issues_table(section)
                if issues:
                    result["issues"] = issues
                    logger.info(f"评审提取: Markdown 表格解析到 {len(issues)} 个问题")

            # 提取遗漏场景
            elif '遗漏' in first_line or 'missing' in first_line or '缺失' in first_line:
                missing = ContentExtractor._parse_numbered_list(section)
                if missing:
                    result["missing_scenarios"] = missing
                    logger.info(f"评审提取: 解析到 {len(missing)} 个遗漏场景")

            # 提取整体改进建议
            elif '建议' in first_line or 'suggestion' in first_line:
                suggestions = ContentExtractor._parse_numbered_list(section)
                if suggestions:
                    result["overall_suggestions"] = suggestions
                    logger.info(f"评审提取: 解析到 {len(suggestions)} 条改进建议")

            # 提取分组评价
            elif '分组' in first_line or 'group' in first_line:
                groups = ContentExtractor._parse_markdown_groups_table(section)
                if groups:
                    result["group_reviews"] = groups

        # 如果 Markdown 解析也没有提取到 issues，尝试正则兜底
        if not result["issues"]:
            issue_pattern = re.findall(
                r'(?:问题|issue)[\s\d]*[:：]\s*(.+?)(?=(?:问题|issue|建议|suggestion|遗漏|$))',
                content, re.IGNORECASE | re.DOTALL
            )
            for i, desc in enumerate(issue_pattern[:10]):
                desc = desc.strip().strip('"').strip("'")
                if desc and len(desc) > 5:
                    result["issues"].append({
                        "case_index": i,
                        "case_title": "",
                        "requirement_title": "",
                        "module": "",
                        "issue_type": "完整性",
                        "severity": "medium",
                        "description": desc[:200],
                        "suggestion": "",
                    })

        if not result["overall_suggestions"]:
            sug_pattern = re.findall(
                r'(?:建议|suggestion)[\s\d]*[:：]\s*(.+?)(?=(?:建议|suggestion|问题|issue|遗漏|缺少|缺失|missing|$))',
                content, re.IGNORECASE | re.DOTALL
            )
            for s in sug_pattern[:5]:
                s = s.strip().strip('"').strip("'")
                if s and len(s) > 5:
                    result["overall_suggestions"].append(s[:200])

        logger.info(
            f"评审提取完成: score={result['score']}, issues={len(result['issues'])}, "
            f"suggestions={len(result['overall_suggestions'])}, missing={len(result['missing_scenarios'])}"
        )
        return result

    @staticmethod
    def _parse_markdown_issues_table(section: str) -> list:
        """从 Markdown 章节中解析问题列表表格。"""
        issues = []
        lines = section.split('\n')
        col_order = []
        for line in lines:
            stripped = line.strip()
            if not stripped.startswith('|'):
                continue
            cells = [c.strip() for c in stripped.split('|')[1:-1]]
            if not cells:
                continue
            # 表头行
            if not col_order and ('case_index' in cells[0].lower() or 'case_title' in ''.join(cells).lower()):
                col_order = [c.lower().strip() for c in cells]
                continue
            # 分割行
            if not col_order and all(re.match(r'^[-:]+$', c) for c in cells):
                continue
            if not col_order:
                continue
            # 数据行
            if all(re.match(r'^[-:]+$', c) for c in cells):
                continue
            issue = {}
            for i, val in enumerate(cells):
                if i < len(col_order):
                    issue[col_order[i]] = val
            if issue.get('case_index') is not None or issue.get('case_title'):
                # 尝试转换 case_index 为 int
                ci = issue.get('case_index', '')
                try:
                    issue['case_index'] = int(ci)
                except (ValueError, TypeError):
                    pass
                issues.append(issue)
        return issues

    @staticmethod
    def _parse_numbered_list(section: str) -> list:
        """从 Markdown 章节中解析编号列表（1. xxx 2. xxx 或 - xxx）。"""
        items = []
        lines = section.split('\n')
        for line in lines:
            stripped = line.strip()
            # 匹配 "1. xxx" 或 "1、xxx"
            m = re.match(r'^\d+[.、]\s*(.+)', stripped)
            if m:
                val = m.group(1).strip()
                if val and len(val) > 3:
                    items.append(val[:200])
                continue
            # 匹配 "- xxx" 或 "* xxx"
            m = re.match(r'^[-*]\s+(.+)', stripped)
            if m:
                val = m.group(1).strip()
                if val and len(val) > 3:
                    items.append(val[:200])
        return items

    @staticmethod
    def _parse_markdown_groups_table(section: str) -> list:
        """从 Markdown 章节中解析分组评价表格。"""
        groups = []
        lines = section.split('\n')
        col_order = []
        for line in lines:
            stripped = line.strip()
            if not stripped.startswith('|'):
                continue
            cells = [c.strip() for c in stripped.split('|')[1:-1]]
            if not cells:
                continue
            if not col_order and ('requirement_title' in cells[0].lower() or 'module' in ''.join(cells).lower()):
                col_order = [c.lower().strip() for c in cells]
                continue
            if not col_order:
                continue
            if all(re.match(r'^[-:]+$', c) for c in cells):
                continue
            group = {}
            for i, val in enumerate(cells):
                if i < len(col_order):
                    group[col_order[i]] = val
            if group:
                # 尝试转换 case_count
                cc = group.get('case_count', '0')
                try:
                    group['case_count'] = int(cc)
                except (ValueError, TypeError):
                    pass
                groups.append(group)
        return groups

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
