"""AI 模型五维综合测评 Pydantic Schemas"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


# ═══════════ 测评对象 ═══════════
class EvalTargetCreate(BaseModel):
    name: str
    target_type: str = "llm"  # llm/agent/external_agent/business
    llm_config_id: Optional[int] = None
    agent_type: Optional[str] = None
    # 外部工作流（external_agent）：服务地址 / 调用路径 / 鉴权方式
    service_url: Optional[str] = None
    call_path: Optional[str] = None
    auth_type: Optional[str] = None
    auth_token: Optional[str] = None
    auth_header: Optional[str] = None
    business_scene: Optional[str] = None
    version_tag: Optional[str] = None
    description: Optional[str] = None


class EvalTargetUpdate(BaseModel):
    name: Optional[str] = None
    target_type: Optional[str] = None
    llm_config_id: Optional[int] = None
    agent_type: Optional[str] = None
    service_url: Optional[str] = None
    call_path: Optional[str] = None
    auth_type: Optional[str] = None
    auth_token: Optional[str] = None
    auth_header: Optional[str] = None
    business_scene: Optional[str] = None
    version_tag: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class EvalTargetResponse(BaseModel):
    id: int
    name: str
    target_type: str
    llm_config_id: Optional[int] = None
    agent_type: Optional[str] = None
    service_url: Optional[str] = None
    call_path: Optional[str] = None
    auth_type: Optional[str] = None
    auth_token: Optional[str] = None
    auth_header: Optional[str] = None
    business_scene: Optional[str] = None
    version_tag: Optional[str] = None
    description: Optional[str] = None
    status: str
    is_deleted: bool = False
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ═══════════ 测评数据集 ═══════════
class EvalDatasetCreate(BaseModel):
    name: str
    eval_type: str = "ai_judge"  # ai_judge/agent/business/redteam/manual
    source: str = "custom"  # builtin/custom/import/gray
    version: Optional[str] = None
    description: Optional[str] = None


class EvalDatasetUpdate(BaseModel):
    name: Optional[str] = None
    eval_type: Optional[str] = None
    source: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class EvalDatasetResponse(BaseModel):
    id: int
    name: str
    eval_type: str
    source: str
    version: Optional[str] = None
    case_count: int = 0
    description: Optional[str] = None
    status: str
    is_deleted: bool = False
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ═══════════ 测评用例 ═══════════
class EvalCaseCreate(BaseModel):
    dataset_id: Optional[int] = None
    eval_type: Optional[str] = None
    title: str
    prompt: str
    expected_output: Optional[str] = None
    ref_answer: Optional[str] = None
    category: Optional[str] = None
    difficulty: str = "P2"
    tags: Optional[List[str]] = None
    attack_type: Optional[str] = None
    constraints: Optional[str] = None


class EvalCaseUpdate(BaseModel):
    title: Optional[str] = None
    prompt: Optional[str] = None
    expected_output: Optional[str] = None
    ref_answer: Optional[str] = None
    category: Optional[str] = None
    difficulty: Optional[str] = None
    tags: Optional[List[str]] = None
    attack_type: Optional[str] = None
    constraints: Optional[str] = None
    status: Optional[str] = None


class EvalCaseResponse(BaseModel):
    id: int
    dataset_id: int
    eval_type: str
    title: str
    prompt: str
    expected_output: Optional[str] = None
    ref_answer: Optional[str] = None
    category: Optional[str] = None
    difficulty: Optional[str] = None
    tags: Optional[List[str]] = None
    attack_type: Optional[str] = None
    constraints: Optional[str] = None
    status: str
    is_deleted: bool = False
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ═══════════ 测评任务 ═══════════
class EvalTaskCreate(BaseModel):
    name: str
    target_id: int
    compare_target_id: Optional[int] = None
    version_id: Optional[int] = None
    modes: Dict[str, Any] = Field(default_factory=dict)  # {ai_judge:{datasets,..},...}
    dataset_ids: Dict[str, List[int]] = Field(default_factory=dict)  # {ai_judge:[1,2]}
    judge_config_ids: Optional[List[int]] = None
    settings: Optional[Dict[str, Any]] = None
    backend: str = "local"


class EvalTaskResponse(BaseModel):
    id: int
    name: str
    target_id: int
    compare_target_id: Optional[int] = None
    version_id: Optional[int] = None
    modes: Optional[Dict[str, Any]] = None
    dataset_ids: Optional[Dict[str, List[int]]] = None
    judge_config_ids: Optional[List[int]] = None
    settings: Optional[Dict[str, Any]] = None
    status: str
    progress: int = 0
    summary: Optional[Dict[str, Any]] = None
    conclusion: Optional[str] = None
    backend: str = "local"
    agent_task_id: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ═══════════ 模式批次 / 结果 ═══════════
class EvalRunResponse(BaseModel):
    id: int
    eval_task_id: int
    mode: str
    dataset_id: Optional[int] = None
    status: str
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    pass_rate: Optional[float] = None
    score_avg: Optional[float] = None
    metrics: Optional[Dict[str, Any]] = None
    progress: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EvalResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())
    id: int
    eval_task_id: int
    eval_run_id: int
    case_id: int
    target_id: Optional[int] = None
    model_output: Optional[str] = None
    judge_scores: Optional[List[Any]] = None
    score: Optional[float] = None
    dimension_scores: Optional[Dict[str, Any]] = None
    manual_score: Optional[float] = None
    manual_comment: Optional[str] = None
    review_status: str = "pending"
    agent_metrics: Optional[Dict[str, Any]] = None
    business_result: Optional[Dict[str, Any]] = None
    redteam_result: Optional[str] = None
    risk_level: Optional[str] = None
    trace: Optional[Any] = None
    latency: Optional[float] = None
    token_usage: Optional[Dict[str, Any]] = None
    status: str
    created_at: Optional[datetime] = None


class ManualScoreIn(BaseModel):
    manual_score: float = Field(ge=0, le=5)
    manual_comment: Optional[str] = None
    review_status: str = "done"


class EvalCompareIn(BaseModel):
    """版本对比请求体"""
    compare_task_id: Optional[int] = None


class EvalReportGenerateIn(BaseModel):
    """报告生成请求体"""
    report_type: str = "overall"


# ═══════════ 报告 / 问题 / 基线 ═══════════
class EvalReportResponse(BaseModel):
    id: int
    eval_task_id: int
    report_type: str
    title: str
    content: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None
    conclusion: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EvalIssueCreate(BaseModel):
    eval_task_id: Optional[int] = None
    issue_level: str = "P2"
    issue_type: Optional[str] = None
    title: str
    description: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None


class EvalIssueStatusUpdate(BaseModel):
    status: str  # open/fixing/fixed/closed/archived
    retest_result: Optional[str] = None
    owner_id: Optional[int] = None
    fix_suggestion: Optional[str] = None


class EvalIssueResponse(BaseModel):
    id: int
    eval_task_id: int
    issue_level: str
    issue_type: Optional[str] = None
    title: str
    description: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None
    status: str
    owner_id: Optional[int] = None
    fix_suggestion: Optional[str] = None
    retest_result: Optional[str] = None
    created_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EvalBaselineCreate(BaseModel):
    target_id: int
    version_id: Optional[int] = None
    baseline_name: str
    eval_task_id: Optional[int] = None


class EvalBaselineResponse(BaseModel):
    id: int
    target_id: int
    version_id: Optional[int] = None
    baseline_name: str
    eval_task_id: Optional[int] = None
    metrics: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PaginatedEvalResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[Any]


# ═══════════ 红队攻击日志 ═══════════
class RedteamRunIn(BaseModel):
    dataset_id: int
    target_id: Optional[int] = None
    concurrency: int = 5
    settings: Optional[Dict[str, Any]] = None
