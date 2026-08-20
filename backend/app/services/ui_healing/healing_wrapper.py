"""
Playwright 自愈包装器

通过 monkey-patch Page 的 click/fill/select/wait_for_selector/goto 等方法，
在定位器失败时自动触发自愈引擎，并旁路采集页面数据。

增强：
- Shadow DOM 穿透采集
- iframe 内容采集
- 渲染等待（domcontentloaded）
- 导航事件采集（goto hook）
- 自动聚合触发（自愈成功/失败后异步聚合）
- 采集与自愈开关解耦（collect_enabled 独立于 heal_enabled）
"""
import json
import logging
import os
import time
import threading
import asyncio
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_INSTALLED_FLAG = "_healing_wrapper_installed"

_execution_context = {
    "db_factory": None,
    "project_id": None,
    "script_id": None,
    "run_id": None,
    "enabled": True,
    "heal_enabled": True,
    "collect_enabled": True,
    "step_counter": 0,
}

_SCREENSHOT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "uploads", "healing",
)


def _normalize_page_id(url: str) -> str:
    try:
        parsed = urlparse(url)
        path = parsed.path.rstrip("/") or "/"
        return f"{parsed.netloc}{path}"
    except Exception:
        return url or "/"


# ============================================================
#  页面采集函数（async，支持 Shadow DOM + iframe）
# ============================================================

_COLLECT_JS = """() => {
    const SELECTOR = 'button, a, input, select, textarea, [role="button"], [role="link"], [role="tab"], [onclick], [data-testid], [data-test]';
    const results = [];

    function collectFromNode(root, depth) {
        if (depth > 3 || results.length >= 80) return;
        try {
            root.querySelectorAll(SELECTOR).forEach(el => {
                if (results.length >= 80) return;
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) return;
                const attrs = {};
                for (const attr of el.attributes) {
                    attrs[attr.name] = attr.value.substring(0, 100);
                }
                let parent = el.parentElement;
                let chain = [];
                for (let d = 0; d < 3 && parent; d++) {
                    chain.push(parent.tagName.toLowerCase() + (parent.id ? '#' + parent.id : '') + (parent.className ? '.' + String(parent.className).split(' ')[0] : ''));
                    parent = parent.parentElement;
                }
                results.push({
                    tag: el.tagName.toLowerCase(),
                    text: (el.innerText || el.value || '').substring(0, 80).trim(),
                    attrs: attrs,
                    parent_chain: chain.join(' > '),
                    in_shadow_dom: depth > 0,
                });
            });
        } catch(e) {}
        try {
            root.querySelectorAll('*').forEach(el => {
                if (el.shadowRoot) {
                    collectFromNode(el.shadowRoot, depth + 1);
                }
            });
        } catch(e) {}
    }

    collectFromNode(document, 0);
    return results;
}"""

_IFRAME_COLLECT_JS = """() => {
    const SELECTOR = 'button, a, input, select, textarea, [role="button"], [role="link"], [role="tab"], [onclick], [data-testid], [data-test]';
    const results = [];
    document.querySelectorAll(SELECTOR).forEach((el, i) => {
        if (i >= 20) return;
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return;
        const attrs = {};
        for (const attr of el.attributes) {
            attrs[attr.name] = attr.value.substring(0, 100);
        }
        results.push({
            tag: el.tagName.toLowerCase(),
            text: (el.innerText || el.value || '').substring(0, 80).trim(),
            attrs: attrs,
            parent_chain: '',
            in_iframe: true,
        });
    });
    return results;
}"""

_DOM_SNAPSHOT_JS = """() => {
    function walk(node, depth) {
        if (depth > 8) return '';
        if (node.nodeType === 3) {
            const t = node.textContent.trim();
            return t ? t.substring(0, 50) : '';
        }
        if (node.nodeType !== 1) return '';
        const tag = node.tagName.toLowerCase();
        const skip = ['script','style','meta','link','svg','path','br','noscript','canvas'];
        if (skip.includes(tag)) return '';
        let attrs = '';
        for (const attr of node.attributes || []) {
            if (['id','class','name','type','placeholder','role','aria-label','data-testid','href','value','title'].includes(attr.name)) {
                attrs += ` ${attr.name}="${attr.value.substring(0,60)}"`;
            }
        }
        let html = `<${tag}${attrs}>`;
        for (const child of node.childNodes) html += walk(child, depth + 1);
        if (node.shadowRoot) {
            for (const child of node.shadowRoot.childNodes) html += walk(child, depth + 1);
        }
        html += `</${tag}>`;
        return html;
    }
    return walk(document.body, 0);
}"""


async def _collect_elements(page) -> list:
    """收集页面可交互元素（含 Shadow DOM 和 iframe）"""
    elements = []

    # 0. 等待页面渲染稳定（短超时，不阻塞执行）
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=3000)
    except Exception:
        pass

    # 1. 主文档 + Shadow DOM
    try:
        main_elements = await page.evaluate(_COLLECT_JS)
        if isinstance(main_elements, list):
            elements.extend(main_elements)
        else:
            logger.warning(f"page.evaluate 返回非列表类型: {type(main_elements)}")
    except Exception as e:
        logger.warning(f"主文档元素采集失败: {e}")

    # 2. iframe 内容
    try:
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            try:
                frame_elements = await frame.evaluate(_IFRAME_COLLECT_JS)
                if isinstance(frame_elements, list):
                    elements.extend(frame_elements)
            except Exception:
                pass
    except Exception:
        pass

    if not elements:
        logger.warning(f"元素采集结果为空: url={page.url}")

    return elements[:80]


async def _get_dom_snapshot(page, max_length: int = 12000) -> str:
    """获取精简 DOM 快照（含 Shadow DOM）"""
    try:
        dom = await page.evaluate(_DOM_SNAPSHOT_JS)
        return dom[:max_length] if isinstance(dom, str) else ""
    except Exception:
        return ""


async def _save_screenshot(page, prefix: str = "heal") -> str:
    """保存截图，返回相对路径"""
    try:
        os.makedirs(_SCREENSHOT_DIR, exist_ok=True)
        filename = f"{prefix}_{int(time.time() * 1000)}.png"
        filepath = os.path.join(_SCREENSHOT_DIR, filename)
        await page.screenshot(path=filepath, type="png", full_page=False, timeout=3000)
        return f"uploads/healing/{filename}"
    except Exception as e:
        logger.debug(f"截图保存失败: {e}")
        return ""


def _is_selector_error(error_msg: str) -> bool:
    msg_lower = error_msg.lower()
    return any(kw in msg_lower for kw in [
        "timeout", "not found", "waiting for", "locator",
        "strict mode violation", "resolved to", "element is not",
    ])


def _is_strict_mode_error(error_msg: str) -> bool:
    return "strict mode violation" in error_msg.lower()


def _auto_apply_to_script(db, script_id: int, old_selector: str, new_selector: str, record_id: int):
    """L1 自愈成功后自动回写脚本"""
    try:
        from app.models.automation_script import AutomationScript
        from app.models.ui_healing import UIHealingRecord
        from app.core.timezone import china_now_naive

        script = db.query(AutomationScript).filter(AutomationScript.id == script_id).first()
        if script and script.script_content and old_selector in script.script_content:
            script.script_content = script.script_content.replace(old_selector, new_selector)
            script.version = (script.version or 1) + 1
            script.heal_count = (script.heal_count or 0) + 1
            script.last_healed_at = china_now_naive()

            record = db.query(UIHealingRecord).filter(UIHealingRecord.id == record_id).first()
            if record:
                record.applied_to_script = True
            db.commit()
            logger.info(f"L1 自愈已自动回写脚本 {script_id}: {old_selector} -> {new_selector}")
    except Exception as e:
        logger.warning(f"自动回写脚本失败: {e}")
        db.rollback()


def _update_fingerprint_feedback(db, project_id: int, page_identifier: str,
                                 candidates: list, success: bool):
    """更新元素指纹的成功/失败计数"""
    try:
        from app.models.ui_healing import UIElementFingerprint
        from app.core.timezone import china_now_naive
        for cand in (candidates or []):
            if cand.get("source") == "fingerprint":
                fp = db.query(UIElementFingerprint).filter(
                    UIElementFingerprint.project_id == project_id,
                    UIElementFingerprint.page_identifier == page_identifier,
                    UIElementFingerprint.element_text == cand.get("_text", ""),
                ).first()
                if fp:
                    if success:
                        fp.success_count = (fp.success_count or 0) + 1
                    else:
                        fp.fail_count = (fp.fail_count or 0) + 1
                    fp.last_seen_at = china_now_naive()
                    db.commit()
                    break
    except Exception:
        db.rollback()


def _notify_l4_failure(ctx: dict, selector: str, error_msg: str):
    """L4 失败发送通知"""
    try:
        from app.services.notification_service import notify_event
        notify_event(
            project_id=ctx["project_id"],
            event_code="ui_healing_failed",
            context={
                "title": f"UI自愈失败: {selector[:50]}",
                "content": f"脚本ID: {ctx['script_id']}, 执行ID: {ctx['run_id']}, 错误: {error_msg[:100]}",
                "selector": selector[:100],
                "script_id": ctx["script_id"],
                "run_id": ctx["run_id"],
            },
        )
    except Exception:
        pass


def _trigger_auto_aggregate(project_id: int):
    """异步触发页面知识聚合（不阻塞当前流程）"""
    try:
        from app.tasks.ui_healing_tasks import aggregate_page_knowledge
        aggregate_page_knowledge.delay(project_id)
    except Exception as e:
        logger.debug(f"触发自动聚合失败: {e}")


class BypassCollector:
    """旁路采集器 — 守护线程异步上报"""

    def collect_async(self, **kwargs):
        ctx = _execution_context
        if not ctx["enabled"] or not ctx["db_factory"]:
            return
        if not ctx.get("collect_enabled", True):
            return

        def _report():
            try:
                db = ctx["db_factory"]()
                try:
                    from app.models.ui_healing import UIPageVisit
                    visit = UIPageVisit(
                        project_id=ctx["project_id"],
                        script_id=ctx["script_id"],
                        run_id=ctx["run_id"],
                        step_index=ctx["step_counter"],
                        **{k: v for k, v in kwargs.items() if k in (
                            "page_url", "page_title", "page_identifier", "action_type",
                            "target_selector", "target_text", "action_result", "fail_reason",
                            "dom_snapshot", "elements_json", "source",
                        )},
                    )
                    db.add(visit)
                    db.commit()
                finally:
                    db.close()
            except Exception as e:
                logger.debug(f"旁路采集失败: {e}")

        threading.Thread(target=_report, daemon=True).start()


_collector = BypassCollector()


def install_healing_wrapper(
    db_session_factory,
    project_id: int,
    script_id: Optional[int] = None,
    run_id: Optional[int] = None,
    enabled: bool = True,
):
    """安装 Playwright Page 自愈包装器"""
    if not enabled:
        return

    _execution_context["db_factory"] = db_session_factory
    _execution_context["project_id"] = project_id
    _execution_context["script_id"] = script_id
    _execution_context["run_id"] = run_id
    _execution_context["enabled"] = True
    _execution_context["collect_enabled"] = True
    _execution_context["step_counter"] = 0

    # 查询脚本级自愈开关（采集开关始终开启）
    if script_id:
        try:
            db = db_session_factory()
            try:
                from app.models.automation_script import AutomationScript
                script = db.query(AutomationScript).filter(AutomationScript.id == script_id).first()
                _execution_context["heal_enabled"] = script.heal_enabled if script else True
            finally:
                db.close()
        except Exception:
            _execution_context["heal_enabled"] = True

    try:
        from playwright.async_api import Page as AsyncPage
    except ImportError:
        logger.warning("Playwright 未安装，自愈包装器未启用")
        return

    if getattr(AsyncPage, _INSTALLED_FLAG, False):
        return

    # ============================================================
    #  Action 方法包装器（click/fill/select 等）
    # ============================================================
    def _make_wrapper(method_name: str, original_method):
        async def wrapper(self, *args, **kwargs):
            if not _execution_context["enabled"]:
                return await original_method(self, *args, **kwargs)

            selector = args[0] if args else kwargs.get("selector", "")
            action_type = method_name.replace("wait_for_", "wait_")
            action_value = args[1] if len(args) > 1 else kwargs.get("value", "")
            collect_enabled = _execution_context.get("collect_enabled", True)

            # === 成功路径 ===
            try:
                result = await original_method(self, *args, **kwargs)
                if collect_enabled:
                    try:
                        page_url = self.url
                        _execution_context["step_counter"] += 1
                        elements = await _collect_elements(self)
                        _collector.collect_async(
                            page_url=page_url,
                            page_identifier=_normalize_page_id(page_url),
                            action_type=action_type,
                            target_selector=str(selector) if selector else "",
                            target_text=str(action_value) if action_value else "",
                            action_result="success",
                            elements_json=(elements or [])[:30],
                            source="execution",
                        )
                    except Exception:
                        pass
                return result

            except Exception as original_error:
                error_msg = str(original_error)

                # 非定位器错误：采集失败信息后抛出
                if not _is_selector_error(error_msg) or not selector:
                    if collect_enabled:
                        try:
                            _collector.collect_async(
                                page_url=self.url,
                                page_identifier=_normalize_page_id(self.url),
                                action_type=action_type,
                                target_selector=str(selector),
                                action_result="fail",
                                fail_reason=error_msg[:500],
                                source="execution",
                            )
                        except Exception:
                            pass
                    raise

                # 自愈开关关闭：采集后抛出
                if not _execution_context.get("heal_enabled", True):
                    if collect_enabled:
                        try:
                            _collector.collect_async(
                                page_url=self.url,
                                page_identifier=_normalize_page_id(self.url),
                                action_type=action_type,
                                target_selector=str(selector),
                                action_result="fail",
                                fail_reason=error_msg[:500],
                                elements_json=(await _collect_elements(self) or [])[:30],
                                source="execution",
                            )
                        except Exception:
                            pass
                    raise

                logger.info(f"定位器失败，触发自愈: {selector} ({method_name})")

                screenshot_before = await _save_screenshot(self, "before")

                # === strict mode 快速路径 ===
                if _is_strict_mode_error(error_msg):
                    try:
                        loc = self.locator(str(selector)).first
                        if method_name == "click":
                            result = await loc.click(timeout=3000)
                        elif method_name == "fill":
                            result = await loc.fill(str(action_value), timeout=3000)
                        elif method_name == "check":
                            result = await loc.check(timeout=3000)
                        elif method_name == "select_option":
                            result = await loc.select_option(*args[1:], timeout=3000)
                        elif method_name == "hover":
                            result = await loc.hover(timeout=3000)
                        else:
                            result = await loc.first.wait_for(state="visible", timeout=3000)

                        ctx = _execution_context
                        db = ctx["db_factory"]()
                        try:
                            from app.services.ui_healing.healing_engine import HealingEngine
                            engine = HealingEngine(db, ctx["project_id"])
                            healed = f"{selector} >> nth=0"
                            record_id = engine.save_healing_record(
                                script_id=ctx["script_id"], run_id=ctx["run_id"],
                                page_url=self.url, original_selector=str(selector),
                                action_type=action_type, fail_reason=error_msg[:200],
                                healing_level="L1", healing_strategy="strict mode: 使用 .first 匹配",
                                suggested_selector=healed, ai_reasoning="",
                                candidates=[], healing_result="success",
                                screenshot_before=screenshot_before,
                                screenshot_after=await _save_screenshot(self, "after"),
                            )
                            _auto_apply_to_script(db, ctx["script_id"], str(selector), healed, record_id)
                        finally:
                            db.close()
                        return result
                    except Exception:
                        pass  # 继续完整自愈流程

                # === 完整自愈流程 L1→L2→L3→L4 ===
                try:
                    from app.services.ui_healing.healing_engine import HealingEngine
                    ctx = _execution_context
                    db = ctx["db_factory"]()
                    try:
                        engine = HealingEngine(db, ctx["project_id"])
                        success, healed_selector, level, strategy, candidates = await engine.heal(
                            page=self, selector=str(selector), action_type=action_type,
                            action_value=str(action_value) if action_value else "",
                            page_url=self.url, timeout=2000,
                        )

                        if success:
                            new_args = list(args)
                            new_args[0] = healed_selector
                            result = await original_method(self, *new_args, **kwargs)

                            screenshot_after = await _save_screenshot(self, "after")
                            auto_apply = (level == "L1")
                            healing_result = "success" if auto_apply else "pending_review"

                            record_id = engine.save_healing_record(
                                script_id=ctx["script_id"], run_id=ctx["run_id"],
                                page_url=self.url, original_selector=str(selector),
                                action_type=action_type, fail_reason=error_msg[:200],
                                healing_level=level, healing_strategy=strategy,
                                suggested_selector=healed_selector,
                                ai_reasoning=json.dumps(candidates, ensure_ascii=False)[:2000],
                                candidates=candidates, healing_result=healing_result,
                                screenshot_before=screenshot_before,
                                screenshot_after=screenshot_after,
                            )

                            if auto_apply and ctx["script_id"] and record_id:
                                _auto_apply_to_script(db, ctx["script_id"],
                                                      str(selector), healed_selector, record_id)

                            _update_fingerprint_feedback(
                                db, ctx["project_id"], _normalize_page_id(self.url),
                                candidates, success=True,
                            )

                            if collect_enabled:
                                _collector.collect_async(
                                    page_url=self.url,
                                    page_identifier=_normalize_page_id(self.url),
                                    action_type=action_type,
                                    target_selector=str(selector),
                                    action_result="healed",
                                    fail_reason=f"自愈[{level}]: {strategy}",
                                    source="execution",
                                )
                            # 自动聚合触发
                            _trigger_auto_aggregate(ctx["project_id"])
                            return result
                        else:
                            # L4 全部失败
                            dom_snapshot = await _get_dom_snapshot(self)
                            engine.save_healing_record(
                                script_id=ctx["script_id"], run_id=ctx["run_id"],
                                page_url=self.url, original_selector=str(selector),
                                action_type=action_type, fail_reason=error_msg[:200],
                                healing_level="L4", healing_strategy="所有策略均失败",
                                suggested_selector="", ai_reasoning=dom_snapshot[:5000],
                                candidates=candidates, healing_result="fail",
                                screenshot_before=screenshot_before,
                            )
                            if collect_enabled:
                                elements = await _collect_elements(self)
                                _collector.collect_async(
                                    page_url=self.url,
                                    page_identifier=_normalize_page_id(self.url),
                                    action_type=action_type,
                                    target_selector=str(selector),
                                    action_result="fail",
                                    fail_reason=error_msg[:500],
                                    dom_snapshot=dom_snapshot[:8000],
                                    elements_json=(elements or [])[:30],
                                    source="execution",
                                )
                            # 自动聚合触发
                            _trigger_auto_aggregate(ctx["project_id"])
                            _notify_l4_failure(ctx, str(selector), error_msg)
                    finally:
                        db.close()
                except Exception as heal_e:
                    logger.error(f"自愈过程异常: {heal_e}", exc_info=True)

                raise

        return wrapper

    methods = ["click", "fill", "check", "uncheck", "select_option",
               "wait_for_selector", "hover", "tap"]
    for method_name in methods:
        if hasattr(AsyncPage, method_name):
            original = getattr(AsyncPage, method_name)
            if not getattr(original, "_healing_wrapped", False):
                wrapped = _make_wrapper(method_name, original)
                wrapped._healing_wrapped = True
                setattr(AsyncPage, method_name, wrapped)

    # ============================================================
    #  导航方法包装器（goto）— 页面跳转后采集
    # ============================================================
    original_goto = getattr(AsyncPage, "goto", None)
    if original_goto and not getattr(original_goto, "_healing_wrapped", False):
        async def _goto_wrapper(self, *args, **kwargs):
            result = await original_goto(self, *args, **kwargs)

            if not _execution_context.get("enabled"):
                return result
            if not _execution_context.get("collect_enabled", True):
                return result

            try:
                # 等待页面渲染
                try:
                    await self.wait_for_load_state("domcontentloaded", timeout=5000)
                except Exception:
                    pass

                page_url = self.url
                _execution_context["step_counter"] += 1
                elements = await _collect_elements(self)
                _collector.collect_async(
                    page_url=page_url,
                    page_identifier=_normalize_page_id(page_url),
                    action_type="navigate",
                    target_selector="",
                    target_text="",
                    action_result="success",
                    elements_json=(elements or [])[:30],
                    source="execution",
                )
            except Exception:
                pass

            return result

        _goto_wrapper._healing_wrapped = True
        setattr(AsyncPage, "goto", _goto_wrapper)

    setattr(AsyncPage, _INSTALLED_FLAG, True)
    logger.info(
        f"自愈包装器已安装 (project={project_id}, "
        f"heal_enabled={_execution_context['heal_enabled']}, "
        f"collect_enabled={_execution_context['collect_enabled']})"
    )


def uninstall_healing_wrapper():
    try:
        from playwright.async_api import Page as AsyncPage
        setattr(AsyncPage, _INSTALLED_FLAG, False)
    except ImportError:
        pass
