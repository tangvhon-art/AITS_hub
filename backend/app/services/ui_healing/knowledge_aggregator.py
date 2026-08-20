"""
页面知识聚合器 — 从原始访问记录聚合为页面画像和元素指纹

支持两种模式：
1. 批量聚合：从 ui_page_visit 表读取历史记录，聚合为 UIPageProfile + UIElementFingerprint
2. 即时聚合：在自愈流程中，当页面无知识时，即时采集并聚合
"""
import json
import logging
from collections import Counter, defaultdict
from typing import Dict, List, Any, Optional

from sqlalchemy.orm import Session

from app.core.timezone import china_now_naive
from app.models.ui_healing import UIPageVisit, UIPageProfile, UIElementFingerprint

logger = logging.getLogger(__name__)


def aggregate_page_knowledge_sync(
    db: Session,
    project_id: int = None,
    page_identifier: str = None,
    batch_size: int = 500,
) -> dict:
    """
    同步聚合页面知识（可被 Celery 任务或自愈引擎直接调用）

    Args:
        db: 数据库会话
        project_id: 项目ID（可选，None 表示全部）
        page_identifier: 页面标识（可选，None 表示全部页面）
        batch_size: 每批处理的最大访问记录数

    Returns:
        {"processed": int}
    """
    query = db.query(UIPageVisit).filter(
        UIPageVisit.action_result.in_(["success", "healed"])
    )
    if project_id:
        query = query.filter(UIPageVisit.project_id == project_id)
    if page_identifier:
        query = query.filter(UIPageVisit.page_identifier == page_identifier)

    page_groups: Dict[str, List[UIPageVisit]] = defaultdict(list)
    for visit in query.limit(batch_size * 10).all():
        page_groups[visit.page_identifier].append(visit)

    if not page_groups:
        logger.info("没有需要聚合的页面访问记录")
        return {"processed": 0}

    processed = 0
    for page_id, visits in page_groups.items():
        try:
            _aggregate_single_page(db, visits[0].project_id, page_id, visits)
            processed += 1
        except Exception as e:
            logger.error(f"聚合页面 {page_id} 失败: {e}", exc_info=True)

    db.commit()
    logger.info(f"页面知识聚合完成，处理 {processed} 个页面")
    return {"processed": processed}


def collect_and_aggregate_now(
    db: Session,
    project_id: int,
    page_identifier: str,
    page_url: str,
    elements: List[Dict],
    action_type: str = "healing_collect",
    page_title: str = "",
) -> bool:
    """
    即时采集单条页面访问记录并立即聚合

    用于自愈流程中，当页面无现有知识时，即时建立知识库。
    跳过 AI 生成页面描述（太慢），只做 SQL 级聚合。
    """
    try:
        visit = UIPageVisit(
            project_id=project_id,
            page_url=page_url,
            page_identifier=page_identifier,
            page_title=page_title or "",
            action_type=action_type,
            action_result="success",
            target_selector="",
            target_text="",
            elements_json=elements[:30] if elements else None,
            source="healing_collect",
        )
        db.add(visit)
        db.flush()

        _aggregate_single_page(db, project_id, page_identifier, [visit], skip_ai=True)
        db.commit()

        logger.info(
            f"即时采集聚合完成: page={page_identifier}, elements={len(elements or [])}"
        )
        return True
    except Exception as e:
        logger.error(f"即时采集聚合失败: {e}", exc_info=True)
        db.rollback()
        return False


def _aggregate_single_page(
    db: Session,
    project_id: int,
    page_identifier: str,
    visits: List[UIPageVisit],
    skip_ai: bool = False,
):
    """聚合单个页面的知识"""
    total_visits = len(visits)
    success_count = sum(1 for v in visits if v.action_result in ("success", "healed"))
    success_rate = round(success_count / total_visits, 4) if total_visits > 0 else 1.0

    element_counter: Counter = Counter()
    element_data: Dict[str, Dict] = {}
    success_selectors: Counter = Counter()
    failure_patterns: List[Dict] = []

    for v in visits:
        if v.elements_json:
            for el in v.elements_json:
                if not isinstance(el, dict):
                    continue
                text = (el.get("text") or "").strip()
                tag = el.get("tag", "")
                attrs = el.get("attrs", {})
                if not text and not attrs:
                    continue

                key = f"{tag}:{text}:{attrs.get('id', attrs.get('name', attrs.get('aria-label', '')))}"
                element_counter[key] += 1
                if key not in element_data:
                    element_data[key] = {"tag": tag, "text": text, "attrs": attrs}

                if v.action_result in ("success", "healed") and v.target_selector:
                    success_selectors[v.target_selector] += 1

        if v.action_result == "fail" and v.fail_reason:
            failure_patterns.append({
                "selector": v.target_selector,
                "reason": v.fail_reason[:200],
            })

    profile = db.query(UIPageProfile).filter(
        UIPageProfile.project_id == project_id,
        UIPageProfile.page_identifier == page_identifier,
    ).first()

    if not profile:
        profile = UIPageProfile(
            project_id=project_id,
            page_identifier=page_identifier,
        )
        db.add(profile)

    profile.visit_count = (profile.visit_count or 0) + total_visits
    profile.success_rate = success_rate

    key_elements = []
    for key, count in element_counter.most_common(20):
        data = element_data[key]
        selectors = _build_selectors(data)
        key_elements.append({
            "tag": data["tag"],
            "text": data["text"],
            "attributes": data["attrs"],
            "selectors": selectors,
            "occurrence_count": count,
            "frequency": round(count / total_visits, 2) if total_visits > 0 else 0,
        })
    profile.key_elements = key_elements

    top_success = [{"selector": sel, "count": cnt} for sel, cnt in success_selectors.most_common(10)]
    profile.success_paths = top_success

    seen_failures = set()
    unique_failures = []
    for fp in failure_patterns[:20]:
        key = f"{fp['selector']}:{fp['reason'][:50]}"
        if key not in seen_failures:
            seen_failures.add(key)
            unique_failures.append(fp)
    profile.failure_patterns = unique_failures

    profile.last_aggregated_at = china_now_naive()

    for el_info in key_elements:
        _upsert_element_fingerprint(db, project_id, page_identifier, el_info, total_visits)

    if not skip_ai:
        try:
            _ai_enrich_page_profile(db, profile, key_elements[:10])
        except Exception as e:
            logger.debug(f"AI 页面描述生成失败（不影响聚合）: {e}")


def _build_selectors(element_data: Dict) -> List[Dict]:
    """为元素构建多个备选定位器"""
    selectors = []
    tag = element_data.get("tag", "")
    text = element_data.get("text", "")
    attrs = element_data.get("attrs", {})

    priority_attrs = ["data-testid", "data-test", "id", "name", "aria-label", "placeholder", "title", "role"]
    for attr in priority_attrs:
        if attrs.get(attr):
            selectors.append({"type": "css", "value": f'[{attr}="{attrs[attr]}"]', "confidence": 0.9})

    if text:
        selectors.append({"type": "text", "value": f'text="{text}"', "confidence": 0.75})
        if tag:
            selectors.append({"type": "css", "value": f'{tag}:has-text("{text}")', "confidence": 0.7})

    if attrs.get("href"):
        selectors.append({"type": "css", "value": f'{tag}[href="{attrs["href"]}"]', "confidence": 0.7})

    return selectors


def _upsert_element_fingerprint(db: Session, project_id: int, page_identifier: str, el_info: Dict, total_visits: int):
    """更新或创建元素指纹"""
    text = el_info.get("text", "")
    attrs = el_info.get("attributes", {})
    tag = el_info.get("tag", "")

    existing = None
    if text:
        existing = db.query(UIElementFingerprint).filter(
            UIElementFingerprint.project_id == project_id,
            UIElementFingerprint.page_identifier == page_identifier,
            UIElementFingerprint.element_text == text,
        ).first()

    if not existing:
        existing = UIElementFingerprint(
            project_id=project_id,
            page_identifier=page_identifier,
            element_role=tag,
            element_text=text,
        )
        db.add(existing)

    existing.occurrence_count = (existing.occurrence_count or 0) + el_info.get("occurrence_count", 1)
    existing.success_count = (existing.success_count or 0) + el_info.get("occurrence_count", 1)
    existing.selectors = el_info.get("selectors", [])
    existing.attributes = attrs
    existing.is_stable = (el_info.get("frequency", 0) > 0.9)
    existing.last_seen_at = china_now_naive()


def _ai_enrich_page_profile(db: Session, profile: UIPageProfile, key_elements: List[Dict]):
    """使用 AI 生成页面名称和描述"""
    try:
        from app.agents.llm_factory import llm_factory
        from app.agents.utils import extract_json

        elements_desc = "\n".join([
            f"- {e['tag']}: {e['text'] or e['attributes']}"
            for e in key_elements[:10]
        ])

        prompt = f"""根据以下页面元素信息，推断这个页面的名称和功能描述。

页面标识: {profile.page_identifier}
关键元素:
{elements_desc}

请输出JSON:
{{"page_name": "页面名称", "page_description": "一句话功能描述"}}
只输出JSON。"""

        response, _token_usage, _config_id = llm_factory.call_with_fallback(
            db, [{"role": "user", "content": prompt}], preferred_config_id=None,
        )
        content = response.content if hasattr(response, "content") else str(response)
        result = extract_json(content.strip())

        if result:
            profile.page_name = result.get("page_name", profile.page_name or "")
            profile.page_description = result.get("page_description", profile.page_description or "")
    except Exception as e:
        logger.debug(f"AI 页面描述生成失败: {e}")
