"""
UI 自愈聚合任务 — 定时将原始访问记录聚合为页面画像和元素指纹

- SQL 统计：访问次数、成功率、元素出现频率
- AI 聚合：页面名称、功能描述、关键元素排序、失败模式
"""
import json
import logging
from collections import Counter, defaultdict
from typing import Dict, List, Any

from app.celery_app import celery_app
from app.database import SessionLocal
from app.core.timezone import china_now_naive
from app.models.ui_healing import UIPageVisit, UIPageProfile, UIElementFingerprint

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.ui_healing_tasks.aggregate_page_knowledge")
def aggregate_page_knowledge(project_id: int = None, batch_size: int = 500):
    """
    聚合页面知识（定时任务）

    1. 按 page_identifier 分组统计原始记录
    2. SQL 计算访问次数、成功率
    3. 提取元素指纹
    4. AI 生成页面名称和描述
    """
    db = SessionLocal()
    try:
        query = db.query(UIPageVisit).filter(UIPageVisit.action_result.in_(["success", "healed"]))
        if project_id:
            query = query.filter(UIPageVisit.project_id == project_id)

        # 按页面分组
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

    except Exception as e:
        logger.error(f"页面知识聚合任务失败: {e}", exc_info=True)
        return {"error": str(e)}
    finally:
        db.close()


def _aggregate_single_page(db, project_id: int, page_identifier: str, visits: List[UIPageVisit]):
    """聚合单个页面的知识"""
    # 1. SQL 统计
    total_visits = len(visits)
    success_count = sum(1 for v in visits if v.action_result in ("success", "healed"))
    success_rate = round(success_count / total_visits, 4) if total_visits > 0 else 1.0

    # 2. 收集所有元素
    element_counter = Counter()
    element_data = {}
    success_selectors = Counter()
    failure_patterns = []

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

                # 元素唯一键
                key = f"{tag}:{text}:{attrs.get('id', attrs.get('name', attrs.get('aria-label', '')))}"
                element_counter[key] += 1
                if key not in element_data:
                    element_data[key] = {"tag": tag, "text": text, "attrs": attrs}

                # 收集成功定位器
                if v.action_result in ("success", "healed") and v.target_selector:
                    success_selectors[v.target_selector] += 1

        if v.action_result == "fail" and v.fail_reason:
            failure_patterns.append({
                "selector": v.target_selector,
                "reason": v.fail_reason[:200],
            })

    # 3. 更新或创建页面画像
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

    # 关键元素（按出现频率排序）
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
            "frequency": round(count / total_visits, 2),
        })
    profile.key_elements = key_elements

    # 成功路径
    top_success = [{"selector": sel, "count": cnt} for sel, cnt in success_selectors.most_common(10)]
    profile.success_paths = top_success

    # 失败模式（去重）
    seen_failures = set()
    unique_failures = []
    for fp in failure_patterns[:20]:
        key = f"{fp['selector']}:{fp['reason'][:50]}"
        if key not in seen_failures:
            seen_failures.add(key)
            unique_failures.append(fp)
    profile.failure_patterns = unique_failures

    profile.last_aggregated_at = china_now_naive()

    # 4. 更新元素指纹库
    for el_info in key_elements:
        _upsert_element_fingerprint(db, project_id, page_identifier, el_info, total_visits)

    # 5. AI 生成页面名称和描述（异步，不阻塞聚合）
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


def _upsert_element_fingerprint(db, project_id: int, page_identifier: str, el_info: Dict, total_visits: int):
    """更新或创建元素指纹"""
    text = el_info.get("text", "")
    attrs = el_info.get("attributes", {})
    tag = el_info.get("tag", "")

    # 查找已有指纹（按文本+页面）
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


def _ai_enrich_page_profile(db, profile, key_elements: List[Dict]):
    """使用 AI 生成页面名称和描述"""
    try:
        from app.agents.llm_factory import llm_factory

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

        from app.agents.utils import extract_json
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
