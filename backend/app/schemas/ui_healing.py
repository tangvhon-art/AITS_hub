"""
UI 自动化自愈 Schema
"""
from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ==================== 页面访问记录 ====================

class PageVisitResponse(BaseModel):
    id: int
    project_id: int
    script_id: Optional[int] = None
    run_id: Optional[int] = None
    page_url: str = ""
    page_title: str = ""
    page_identifier: str = ""
    action_type: str = ""
    target_selector: str = ""
    action_result: str = ""
    fail_reason: str = ""
    source: str = "execution"
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PageVisitListResponse(BaseModel):
    total: int
    items: List[PageVisitResponse]


# ==================== 页面画像 ====================

class PageProfileResponse(BaseModel):
    id: int
    project_id: int
    page_identifier: str
    page_name: str = ""
    page_description: str = ""
    key_elements: Optional[Any] = None
    success_paths: Optional[Any] = None
    failure_patterns: Optional[Any] = None
    reachable_from: Optional[Any] = None
    visit_count: int = 0
    success_rate: float = 1.0
    last_aggregated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PageProfileListResponse(BaseModel):
    total: int
    items: List[PageProfileResponse]


# ==================== 元素指纹 ====================

class ElementFingerprintResponse(BaseModel):
    id: int
    project_id: int
    page_identifier: str = ""
    element_role: str = ""
    element_text: str = ""
    selectors: Optional[Any] = None
    attributes: Optional[Any] = None
    occurrence_count: int = 1
    success_count: int = 0
    fail_count: int = 0
    is_stable: bool = False
    last_seen_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== 自愈记录 ====================

class HealingRecordResponse(BaseModel):
    id: int
    project_id: int
    script_id: Optional[int] = None
    run_id: Optional[int] = None
    step_index: Optional[int] = None
    page_url: str = ""
    page_identifier: str = ""
    original_selector: str = ""
    action_type: str = ""
    fail_reason: str = ""
    healing_level: str = ""
    healing_strategy: str = ""
    suggested_selector: str = ""
    ai_reasoning: str = ""
    candidates: Optional[Any] = None
    healing_result: str = ""
    applied_to_script: bool = False
    confirmed_by: Optional[int] = None
    confirmed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class HealingRecordListResponse(BaseModel):
    total: int
    items: List[HealingRecordResponse]


class HealingConfirmRequest(BaseModel):
    apply_to_script: bool = Field(True, description="是否同时回写到脚本")


class HealingStatsResponse(BaseModel):
    total: int = 0
    success: int = 0
    failed: int = 0
    pending_review: int = 0
    l1_count: int = 0
    l2_count: int = 0
    l3_count: int = 0
    l4_count: int = 0
    applied_count: int = 0
    success_rate: float = 0.0
