"""
UI 自愈引擎 — L1/L2/L3 三级自愈策略

L1: 同属性回退（从元素指纹库匹配备选定位器，本地即时）
L2: AI 修复推理（截图 + DOM 树 + 页面知识，大模型推理候选定位器）
L3: 视觉坐标点击（视觉模型识别目标区域，coordinate click 兜底）
"""
import json
import re
import logging
from typing import Optional, List, Dict, Any, Tuple
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models.ui_healing import UIElementFingerprint, UIPageProfile, UIHealingRecord
from app.core.timezone import china_now_naive

logger = logging.getLogger(__name__)


def normalize_page_identifier(url: str) -> str:
    """将 URL 归一化为页面标识（去掉 query 和 hash，保留路径）"""
    try:
        parsed = urlparse(url)
        path = parsed.path.rstrip("/") or "/"
        return f"{parsed.netloc}{path}"
    except Exception:
        return url or "/"


def extract_selector_info(selector: str) -> Dict[str, Any]:
    """从定位器中提取信息（文本、属性等）"""
    info = {"text": "", "tag": "", "attributes": {}}
    if not selector:
        return info

    # text=登录
    m = re.match(r'text=(.+)', selector)
    if m:
        info["text"] = m.group(1).strip().strip('"\'')
        return info

    # has-text=
    m = re.match(r'.*:has-text\(["\']?(.+?)["\']?\)\s*$', selector)
    if m:
        info["text"] = m.group(1)

    # CSS 选择器中的属性
    for attr_match in re.finditer(r'\[([\w-]+)=["\']?([^"\'\]]+)["\']?\]', selector):
        attr_name, attr_val = attr_match.group(1), attr_match.group(2)
        info["attributes"][attr_name] = attr_val
        if attr_name in ("aria-label", "placeholder", "title", "value"):
            info["text"] = attr_val

    # 标签名
    tag_match = re.match(r'^([a-zA-Z]\w*)', selector)
    if tag_match:
        info["tag"] = tag_match.group(1)

    # ID
    id_match = re.search(r'#([\w-]+)', selector)
    if id_match:
        info["attributes"]["id"] = id_match.group(1)

    # class
    class_match = re.search(r'\.([\w-]+)', selector)
    if class_match:
        info["attributes"]["class"] = class_match.group(1)

    return info


class HealingEngine:
    """自愈引擎"""

    # L1 备选定位器属性优先级
    L1_ATTR_PRIORITY = ["data-testid", "data-test", "id", "name", "aria-label", "placeholder", "title", "role"]

    def __init__(self, db: Session, project_id: int):
        self.db = db
        self.project_id = project_id

    def heal(
        self,
        page,
        selector: str,
        action_type: str,
        action_value: str = "",
        page_url: str = "",
        timeout: float = 3000,
    ) -> Tuple[bool, str, str, str, List[Dict]]:
        """
        执行自愈流程

        Args:
            page: Playwright Page 对象
            selector: 失败的定位器
            action_type: click/fill/select/wait
            action_value: fill 的值
            page_url: 当前页面URL
            timeout: 每次尝试超时（毫秒）

        Returns:
            (是否成功, 修复后的定位器, 自愈等级, 策略描述, 候选列表)
        """
        page_identifier = normalize_page_identifier(page_url)
        sel_info = extract_selector_info(selector)
        candidates: List[Dict] = []

        # === L1: 同属性回退 ===
        l1_result = self._l1_attribute_fallback(page, selector, sel_info, page_identifier, timeout)
        if l1_result:
            healed_selector, strategy, cands = l1_result
            candidates.extend(cands)
            logger.info(f"L1 自愈成功: {selector} → {healed_selector} ({strategy})")
            return True, healed_selector, "L1", strategy, candidates

        # === L2: AI 修复推理 ===
        l2_result = self._l2_ai_healing(page, selector, sel_info, action_type, page_identifier, page_url, timeout)
        if l2_result:
            healed_selector, strategy, cands = l2_result
            candidates.extend(cands)
            logger.info(f"L2 自愈成功: {selector} → {healed_selector} ({strategy})")
            return True, healed_selector, "L2", strategy, candidates

        # === L3: 视觉坐标点击 ===
        if action_type in ("click",):
            l3_result = self._l3_visual_click(page, selector, sel_info, action_value, timeout)
            if l3_result:
                healed_selector, strategy, cands = l3_result
                candidates.extend(cands)
                logger.info(f"L3 自愈成功: {selector} → {healed_selector} ({strategy})")
                return True, healed_selector, "L3", strategy, candidates

        return False, "", "L4", "所有自愈策略均失败", candidates

    def _l1_attribute_fallback(
        self, page, selector: str, sel_info: Dict, page_identifier: str, timeout: float
    ) -> Optional[Tuple[str, str, List[Dict]]]:
        """L1: 从元素指纹库和当前页面查找备选定位器"""
        candidates = []
        target_text = sel_info.get("text", "")
        target_attrs = sel_info.get("attributes", {})

        # 1. 从元素指纹库查找
        if target_text:
            fingerprints = self.db.query(UIElementFingerprint).filter(
                UIElementFingerprint.project_id == self.project_id,
                UIElementFingerprint.page_identifier == page_identifier,
                UIElementFingerprint.element_text == target_text,
            ).order_by(UIElementFingerprint.success_count.desc()).limit(5).all()

            for fp in fingerprints:
                if fp.selectors:
                    for sel in fp.selectors:
                        if isinstance(sel, dict) and sel.get("value"):
                            alt_selector = sel["value"]
                            if alt_selector != selector:
                                candidates.append({
                                    "selector": alt_selector,
                                    "type": sel.get("type", "css"),
                                    "confidence": sel.get("confidence", 0.7),
                                    "reason": f"元素指纹库匹配（成功{fp.success_count}次）",
                                    "source": "fingerprint",
                                })

        # 2. 在当前页面上按文本/属性查找备选
        try:
            # 按文本查找
            if target_text:
                alt_selectors = self._find_by_text(page, target_text, timeout)
                for alt in alt_selectors:
                    if alt != selector and alt not in [c["selector"] for c in candidates]:
                        candidates.append({
                            "selector": alt,
                            "type": "css",
                            "confidence": 0.75,
                            "reason": "当前页面按文本匹配",
                            "source": "page_scan",
                        })

            # 按属性查找（aria-label, placeholder, name, data-testid 等）
            for attr_name, attr_val in target_attrs.items():
                if attr_name in self.L1_ATTR_PRIORITY and attr_val:
                    alt = f'[{attr_name}="{attr_val}"]'
                    if alt != selector and alt not in [c["selector"] for c in candidates]:
                        candidates.append({
                            "selector": alt,
                            "type": "css",
                            "confidence": 0.8,
                            "reason": f"按属性 {attr_name} 匹配",
                            "source": "attribute",
                        })
        except Exception as e:
            logger.debug(f"L1 页面扫描失败: {e}")

        # 3. 生成通用备选（text → role → placeholder 等）
        if target_text and not candidates:
            generic_alts = [
                f'button:has-text("{target_text}")',
                f'a:has-text("{target_text}")',
                f'[role="button"]:has-text("{target_text}")',
                f'text="{target_text}"',
            ]
            for alt in generic_alts:
                if alt != selector:
                    candidates.append({
                        "selector": alt,
                        "type": "css",
                        "confidence": 0.6,
                        "reason": "通用文本定位回退",
                        "source": "generic",
                    })

        # 按置信度排序并尝试
        candidates.sort(key=lambda c: c.get("confidence", 0), reverse=True)
        for cand in candidates:
            try:
                loc = page.locator(cand["selector"]).first
                loc.wait_for(state="visible", timeout=timeout)
                count = page.locator(cand["selector"]).count()
                if count == 1:
                    return cand["selector"], cand["reason"], candidates
            except Exception:
                continue

        return None

    def _find_by_text(self, page, text: str, timeout: float) -> List[str]:
        """在当前页面上按文本查找元素，返回备选CSS选择器"""
        alts = []
        try:
            # 使用 Playwright 的 text= 引擎
            count = page.locator(f'text="{text}"').count()
            if count == 1:
                alts.append(f'text="{text}"')
            elif count > 1:
                # 多个匹配，尝试更精确的
                for tag in ["button", "a", "input", "[role=button]"]:
                    c = page.locator(f'{tag}:has-text("{text}")').count()
                    if c == 1:
                        alts.append(f'{tag}:has-text("{text}")')
                        break
        except Exception:
            pass
        return alts

    def _l2_ai_healing(
        self, page, selector: str, sel_info: Dict, action_type: str,
        page_identifier: str, page_url: str, timeout: float
    ) -> Optional[Tuple[str, str, List[Dict]]]:
        """L2: AI 修复推理 — 截图 + DOM 树交给大模型分析"""
        try:
            from app.agents.llm_factory import llm_factory
            from app.agents.utils import extract_json

            # 1. 收集页面元素列表
            elements = self._collect_interactive_elements(page)
            if not elements:
                return None

            # 2. 查询页面知识
            page_profile = self.db.query(UIPageProfile).filter(
                UIPageProfile.project_id == self.project_id,
                UIPageProfile.page_identifier == page_identifier,
            ).first()

            # 3. 构建 Prompt
            target_text = sel_info.get("text", "") or selector
            elements_text = json.dumps(elements[:50], ensure_ascii=False, indent=2)
            profile_desc = ""
            if page_profile:
                profile_desc = f"页面名称: {page_profile.page_name}\n页面描述: {page_profile.page_description}"

            prompt = f"""你是一名 UI 自动化测试专家。页面元素定位失败，请找到正确的定位方式。

【失败信息】
- 原定位器: {selector}
- 操作类型: {action_type}
- 目标元素文本/特征: {target_text}

【页面信息】
- URL: {page_url}
{profile_desc}

【当前页面可交互元素列表】（前50个）
{elements_text}

【任务】
从元素列表中找到与原定位器目标最匹配的元素，输出候选定位器。
优先使用稳定属性（data-testid, id, name, aria-label），其次文本，最后CSS结构。
每个候选给出置信度(0-1)和理由。

只输出JSON:
{{"candidates": [{{"selector": "...", "type": "css|text|xpath", "confidence": 0.9, "reason": "..."}}]}}"""

            # 4. 调用 LLM
            response, _token_usage, _config_id = llm_factory.call_with_fallback(
                self.db,
                [{"role": "user", "content": prompt}],
                preferred_config_id=None,
            )
            content = response.content if hasattr(response, "content") else str(response)
            result = extract_json(content.strip())

            if not result or "candidates" not in result:
                return None

            ai_candidates = result["candidates"]
            if not isinstance(ai_candidates, list):
                return None

            # 5. 按置信度尝试
            ai_candidates.sort(key=lambda c: c.get("confidence", 0), reverse=True)
            for cand in ai_candidates:
                cand_sel = cand.get("selector", "")
                if not cand_sel or cand_sel == selector:
                    continue
                try:
                    loc = page.locator(cand_sel).first
                    loc.wait_for(state="visible", timeout=timeout)
                    count = page.locator(cand_sel).count()
                    if count == 1:
                        return cand_sel, f"AI推理: {cand.get('reason', '')}", ai_candidates
                except Exception:
                    continue

            return None

        except Exception as e:
            logger.warning(f"L2 AI 修复失败: {e}")
            return None

    def _l3_visual_click(
        self, page, selector: str, sel_info: Dict, action_value: str, timeout: float
    ) -> Optional[Tuple[str, str, List[Dict]]]:
        """L3: 视觉坐标点击 — 截图 + 视觉模型识别目标坐标"""
        try:
            from app.agents.llm_factory import llm_factory
            from app.agents.utils import extract_json
            import base64

            target_text = sel_info.get("text", "") or selector

            # 截图
            screenshot_bytes = page.screenshot(type="png", full_page=False)
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode()

            # 获取视口尺寸
            viewport = page.viewport_size or {"width": 1280, "height": 720}

            prompt = f"""这是一张网页截图。请找到目标元素的位置。

目标元素: {target_text}
操作: 点击

请返回元素中心点的坐标（相对于截图左上角），格式:
{{"found": true, "x": 123, "y": 456, "confidence": 0.8, "description": "元素描述"}}

如果找不到，返回: {{"found": false}}
只输出JSON。"""

            # 尝试使用支持视觉的模型
            response, _token_usage, _config_id = llm_factory.call_with_fallback(
                self.db,
                [{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}},
                ]}],
                preferred_config_id=None,
            )
            content = response.content if hasattr(response, "content") else str(response)
            result = extract_json(content.strip())

            if not result or not result.get("found"):
                return None

            x, y = int(result["x"]), int(result["y"])
            confidence = result.get("confidence", 0.5)

            if confidence < 0.5:
                return None

            # 执行坐标点击
            page.mouse.click(x, y)

            coord_selector = f"coordinate({x},{y})"
            return coord_selector, f"视觉定位点击({x},{y}), 置信度{confidence}", [{
                "selector": coord_selector,
                "type": "coordinate",
                "confidence": confidence,
                "reason": result.get("description", "视觉模型识别"),
            }]

        except Exception as e:
            logger.warning(f"L3 视觉点击失败: {e}")
            return None

    def _collect_interactive_elements(self, page) -> List[Dict]:
        """收集页面上的可交互元素"""
        try:
            elements = page.evaluate("""() => {
                const selectors = 'button, a, input, select, textarea, [role="button"], [role="link"], [role="tab"], [onclick], [data-testid], [data-test]';
                const nodes = document.querySelectorAll(selectors);
                const results = [];
                nodes.forEach((el, i) => {
                    if (i >= 50) return;
                    const rect = el.getBoundingClientRect();
                    if (rect.width === 0 || rect.height === 0) return;
                    const attrs = {};
                    for (const attr of el.attributes) {
                        if (['id','name','class','type','placeholder','aria-label','role','title','data-testid','data-test','value','href'].includes(attr.name)) {
                            attrs[attr.name] = attr.value.substring(0, 100);
                        }
                    }
                    results.push({
                        tag: el.tagName.toLowerCase(),
                        text: (el.innerText || el.value || '').substring(0, 80).trim(),
                        attrs: attrs,
                        visible: rect.width > 0 && rect.height > 0,
                    });
                });
                return results;
            }""")
            return elements if isinstance(elements, list) else []
        except Exception as e:
            logger.debug(f"收集页面元素失败: {e}")
            return []

    def save_healing_record(
        self,
        script_id: Optional[int],
        run_id: Optional[int],
        page_url: str,
        original_selector: str,
        action_type: str,
        fail_reason: str,
        healing_level: str,
        healing_strategy: str,
        suggested_selector: str,
        ai_reasoning: str,
        candidates: List[Dict],
        healing_result: str,
        screenshot_before: str = "",
        screenshot_after: str = "",
    ) -> int:
        """保存自愈记录到数据库"""
        try:
            record = UIHealingRecord(
                project_id=self.project_id,
                script_id=script_id,
                run_id=run_id,
                page_url=page_url,
                page_identifier=normalize_page_identifier(page_url),
                original_selector=original_selector,
                action_type=action_type,
                fail_reason=fail_reason[:200],
                healing_level=healing_level,
                healing_strategy=healing_strategy[:200],
                suggested_selector=suggested_selector,
                ai_reasoning=ai_reasoning,
                candidates=candidates,
                healing_result=healing_result,
                screenshot_before=screenshot_before,
                screenshot_after=screenshot_after,
            )
            self.db.add(record)
            self.db.commit()
            self.db.refresh(record)
            return record.id
        except Exception as e:
            logger.warning(f"保存自愈记录失败: {e}")
            self.db.rollback()
            return 0


# 全局引擎缓存（按 project_id）
_engines: Dict[int, HealingEngine] = {}


def get_healing_engine(db: Session, project_id: int) -> HealingEngine:
    """获取自愈引擎实例"""
    return HealingEngine(db, project_id)
