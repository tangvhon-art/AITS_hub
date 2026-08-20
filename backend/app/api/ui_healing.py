"""
UI 自动化自愈 API
- 自愈记录查询/确认
- 页面画像查询
- 元素指纹查询
- 手动触发聚合
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.core.deps import get_current_user
from app.core.timezone import china_now_naive
from app.models.ui_healing import UIHealingRecord, UIPageProfile, UIElementFingerprint, UIPageVisit
from app.models.automation_script import AutomationScript
from app.schemas.ui_healing import (
    HealingRecordResponse, HealingRecordListResponse, HealingConfirmRequest, HealingStatsResponse,
    PageProfileResponse, PageProfileListResponse,
    ElementFingerprintResponse,
)

router = APIRouter(prefix="/api/ui-healing", tags=["UI自动化自愈"])


# ==================== 自愈记录 ====================

@router.get("/records", response_model=HealingRecordListResponse)
def list_healing_records(
    project_id: int = Query(..., description="项目ID"),
    script_id: Optional[int] = None,
    run_id: Optional[int] = None,
    healing_level: Optional[str] = None,
    healing_result: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取自愈记录列表"""
    query = db.query(UIHealingRecord).filter(
        UIHealingRecord.project_id == project_id,
    )
    if script_id:
        query = query.filter(UIHealingRecord.script_id == script_id)
    if run_id:
        query = query.filter(UIHealingRecord.run_id == run_id)
    if healing_level:
        query = query.filter(UIHealingRecord.healing_level == healing_level)
    if healing_result:
        query = query.filter(UIHealingRecord.healing_result == healing_result)

    total = query.count()
    items = query.order_by(UIHealingRecord.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return {"total": total, "items": items}


@router.get("/records/{record_id}", response_model=HealingRecordResponse)
def get_healing_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取自愈记录详情"""
    record = db.query(UIHealingRecord).filter(UIHealingRecord.id == record_id).first()
    if not record:
        raise HTTPException(404, "记录不存在")
    return record


@router.post("/records/{record_id}/confirm", response_model=HealingRecordResponse)
def confirm_healing(
    record_id: int,
    data: HealingConfirmRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """确认自愈结果（L2/L3 人工确认，可选回写到脚本）"""
    record = db.query(UIHealingRecord).filter(UIHealingRecord.id == record_id).first()
    if not record:
        raise HTTPException(404, "记录不存在")

    record.confirmed_by = current_user.id
    record.confirmed_at = china_now_naive()
    record.healing_result = "success"

    # 回写到脚本
    if data.apply_to_script and record.script_id and record.suggested_selector:
        script = db.query(AutomationScript).filter(AutomationScript.id == record.script_id).first()
        if script and script.script_content:
            # 在脚本内容中替换原定位器
            old_sel = record.original_selector
            new_sel = record.suggested_selector
            if old_sel and new_sel and old_sel in script.script_content:
                script.script_content = script.script_content.replace(old_sel, new_sel)
                record.applied_to_script = True
                script.version = (script.version or 1) + 1

    db.commit()
    db.refresh(record)
    return record


@router.get("/stats", response_model=HealingStatsResponse)
def get_healing_stats(
    project_id: int = Query(..., description="项目ID"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取自愈统计数据"""
    base_query = db.query(UIHealingRecord).filter(UIHealingRecord.project_id == project_id)
    total = base_query.count()

    success = base_query.filter(UIHealingRecord.healing_result == "success").count()
    failed = base_query.filter(UIHealingRecord.healing_result == "fail").count()
    pending = base_query.filter(UIHealingRecord.healing_result.in_(["pending", "pending_review"])).count()

    l1 = base_query.filter(UIHealingRecord.healing_level == "L1").count()
    l2 = base_query.filter(UIHealingRecord.healing_level == "L2").count()
    l3 = base_query.filter(UIHealingRecord.healing_level == "L3").count()
    l4 = base_query.filter(UIHealingRecord.healing_level == "L4").count()

    applied = base_query.filter(UIHealingRecord.applied_to_script == True).count()

    return HealingStatsResponse(
        total=total,
        success=success,
        failed=failed,
        pending_review=pending,
        l1_count=l1,
        l2_count=l2,
        l3_count=l3,
        l4_count=l4,
        applied_count=applied,
        success_rate=round(success / total, 4) if total > 0 else 0.0,
    )


# ==================== 页面画像 ====================

@router.get("/page-profiles", response_model=PageProfileListResponse)
def list_page_profiles(
    project_id: int = Query(..., description="项目ID"),
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取页面画像列表"""
    query = db.query(UIPageProfile).filter(UIPageProfile.project_id == project_id)
    if keyword:
        query = query.filter(
            (UIPageProfile.page_name.contains(keyword)) |
            (UIPageProfile.page_identifier.contains(keyword))
        )
    total = query.count()
    items = query.order_by(UIPageProfile.visit_count.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return {"total": total, "items": items}


@router.get("/page-profiles/{profile_id}", response_model=PageProfileResponse)
def get_page_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取页面画像详情"""
    profile = db.query(UIPageProfile).filter(UIPageProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(404, "页面画像不存在")
    return profile


# ==================== 元素指纹 ====================

@router.get("/element-fingerprints")
def list_element_fingerprints(
    project_id: int = Query(..., description="项目ID"),
    page_identifier: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取元素指纹列表"""
    query = db.query(UIElementFingerprint).filter(
        UIElementFingerprint.project_id == project_id,
    )
    if page_identifier:
        query = query.filter(UIElementFingerprint.page_identifier == page_identifier)
    if keyword:
        query = query.filter(
            (UIElementFingerprint.element_text.contains(keyword)) |
            (UIElementFingerprint.element_role.contains(keyword))
        )
    total = query.count()
    items = query.order_by(UIElementFingerprint.occurrence_count.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return {"total": total, "items": [ElementFingerprintResponse.model_validate(i) for i in items]}


# ==================== 手动触发聚合 ====================

@router.post("/aggregate")
def trigger_aggregation(
    project_id: int = Query(..., description="项目ID"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """手动触发页面知识聚合（异步任务）"""
    from app.tasks.ui_healing_tasks import aggregate_page_knowledge
    task = aggregate_page_knowledge.delay(project_id=project_id)
    return {"message": "聚合任务已提交", "task_id": task.id}
