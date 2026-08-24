"""
接口测试模块 Pydantic Schemas
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


# ==================== ApiModule ====================
class ApiModuleBase(BaseModel):
    name: str = Field(..., max_length=100)
    parent_id: Optional[int] = None
    sort_order: int = 0


class ApiModuleCreate(ApiModuleBase):
    pass


class ApiModuleUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None


class ApiModuleResponse(BaseModel):
    id: int
    project_id: int
    parent_id: Optional[int] = None
    name: str
    sort_order: int = 0
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    children: List["ApiModuleResponse"] = []

    class Config:
        from_attributes = True


ApiModuleResponse.model_rebuild()


# ==================== ApiDefinition ====================
class ApiDefinitionBase(BaseModel):
    name: str = Field(..., max_length=200)
    module_id: Optional[int] = None
    method: str = "GET"
    path: str = ""
    description: Optional[str] = ""
    tags: Optional[str] = ""
    status: str = "draft"
    headers: Optional[List[Dict[str, Any]]] = []
    query_params: Optional[List[Dict[str, Any]]] = []
    path_params: Optional[List[Dict[str, Any]]] = []
    body_type: str = "none"
    body_content: Optional[Dict[str, Any]] = {}
    pre_script: Optional[str] = ""
    post_script: Optional[str] = ""
    raw_language: Optional[str] = "Text"
    response_examples: Optional[List[Dict[str, Any]]] = []


class ApiDefinitionCreate(ApiDefinitionBase):
    pass


class ApiDefinitionUpdate(BaseModel):
    name: Optional[str] = None
    module_id: Optional[int] = None
    method: Optional[str] = None
    path: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None
    status: Optional[str] = None
    headers: Optional[List[Dict[str, Any]]] = None
    query_params: Optional[List[Dict[str, Any]]] = None
    path_params: Optional[List[Dict[str, Any]]] = None
    body_type: Optional[str] = None
    body_content: Optional[Dict[str, Any]] = None
    pre_script: Optional[str] = None
    post_script: Optional[str] = None
    raw_language: Optional[str] = None
    response_examples: Optional[List[Dict[str, Any]]] = None


class ApiDefinitionResponse(BaseModel):
    id: int
    project_id: int
    module_id: Optional[int] = None
    name: str
    method: str
    path: str
    description: Optional[str] = ""
    tags: Optional[str] = ""
    status: str = "draft"
    headers: Optional[List[Dict[str, Any]]] = []
    query_params: Optional[List[Dict[str, Any]]] = []
    path_params: Optional[List[Dict[str, Any]]] = []
    body_type: str = "none"
    body_content: Optional[Dict[str, Any]] = {}
    pre_script: Optional[str] = ""
    post_script: Optional[str] = ""
    raw_language: Optional[str] = "Text"
    response_examples: Optional[List[Dict[str, Any]]] = []
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== ApiCaseAssertion ====================
class ApiCaseAssertionBase(BaseModel):
    assert_type: str
    assert_target: Optional[str] = ""
    operator: str = "equals"
    expected_value: Optional[str] = ""
    sort_order: int = 0
    enabled: bool = True


class ApiCaseAssertionCreate(ApiCaseAssertionBase):
    pass


class ApiCaseAssertionUpdate(BaseModel):
    assert_type: Optional[str] = None
    assert_target: Optional[str] = None
    operator: Optional[str] = None
    expected_value: Optional[str] = None
    sort_order: Optional[int] = None
    enabled: Optional[bool] = None


class ApiCaseAssertionResponse(BaseModel):
    id: int
    case_id: int
    assert_type: str
    assert_target: Optional[str] = ""
    operator: str
    expected_value: Optional[str] = ""
    sort_order: int = 0
    enabled: bool = True
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== ApiTestCase ====================
class ApiTestCaseBase(BaseModel):
    name: str = Field(..., max_length=200)
    module_id: Optional[int] = None
    api_id: Optional[int] = None
    description: Optional[str] = ""
    priority: str = "P2"
    tags: Optional[str] = ""
    method: Optional[str] = None
    path: Optional[str] = None
    headers: Optional[List[Dict[str, Any]]] = []
    query_params: Optional[List[Dict[str, Any]]] = []
    body_type: str = "none"
    body_content: Optional[Dict[str, Any]] = {}
    pre_script: Optional[str] = ""
    post_script: Optional[str] = ""
    param_source: str = "none"
    param_data: Optional[List[Dict[str, Any]]] = []
    data_pool_id: Optional[int] = None


class ApiTestCaseCreate(ApiTestCaseBase):
    assertions: Optional[List[ApiCaseAssertionCreate]] = []


class ApiTestCaseUpdate(BaseModel):
    name: Optional[str] = None
    module_id: Optional[int] = None
    api_id: Optional[int] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    tags: Optional[str] = None
    method: Optional[str] = None
    path: Optional[str] = None
    headers: Optional[List[Dict[str, Any]]] = None
    query_params: Optional[List[Dict[str, Any]]] = None
    body_type: Optional[str] = None
    body_content: Optional[Dict[str, Any]] = None
    pre_script: Optional[str] = None
    post_script: Optional[str] = None
    param_source: Optional[str] = None
    param_data: Optional[List[Dict[str, Any]]] = None
    data_pool_id: Optional[int] = None


class ApiTestCaseResponse(BaseModel):
    id: int
    project_id: int
    module_id: Optional[int] = None
    api_id: Optional[int] = None
    name: str
    description: Optional[str] = ""
    priority: str = "P2"
    tags: Optional[str] = ""
    method: Optional[str] = None
    path: Optional[str] = None
    headers: Optional[List[Dict[str, Any]]] = []
    query_params: Optional[List[Dict[str, Any]]] = []
    body_type: str = "none"
    body_content: Optional[Dict[str, Any]] = {}
    pre_script: Optional[str] = ""
    post_script: Optional[str] = ""
    param_source: str = "none"
    param_data: Optional[List[Dict[str, Any]]] = []
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    assertions: List[ApiCaseAssertionResponse] = []

    class Config:
        from_attributes = True


# ==================== ApiScenarioVariable ====================
class ApiScenarioVariableBase(BaseModel):
    var_name: str
    extract_type: str = "jsonpath"
    extract_expr: str
    default_value: Optional[str] = ""
    scope: str = "scenario"


class ApiScenarioVariableCreate(ApiScenarioVariableBase):
    pass


class ApiScenarioVariableUpdate(BaseModel):
    var_name: Optional[str] = None
    extract_type: Optional[str] = None
    extract_expr: Optional[str] = None
    default_value: Optional[str] = None
    scope: Optional[str] = None


class ApiScenarioVariableResponse(BaseModel):
    id: int
    step_id: int
    var_name: str
    extract_type: str
    extract_expr: str
    default_value: Optional[str] = ""
    scope: str = "scenario"
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== ApiScenarioStep ====================
class ApiScenarioStepBase(BaseModel):
    step_type: str = "api"
    step_name: str = ""
    sort_order: int = 0
    enabled: bool = True
    api_id: Optional[int] = None
    case_id: Optional[int] = None
    request_config: Optional[Dict[str, Any]] = {}
    script_content: Optional[str] = ""
    wait_seconds: Optional[int] = None
    condition_expr: Optional[str] = ""
    loop_config: Optional[Dict[str, Any]] = {}
    pre_script: Optional[str] = ""
    post_script: Optional[str] = ""
    continue_on_failure: bool = False
    max_retries: int = 0


class ApiScenarioStepCreate(ApiScenarioStepBase):
    variables: Optional[List[ApiScenarioVariableCreate]] = []


class ApiScenarioStepUpdate(BaseModel):
    step_type: Optional[str] = None
    step_name: Optional[str] = None
    sort_order: Optional[int] = None
    enabled: Optional[bool] = None
    api_id: Optional[int] = None
    case_id: Optional[int] = None
    request_config: Optional[Dict[str, Any]] = None
    script_content: Optional[str] = None
    wait_seconds: Optional[int] = None
    condition_expr: Optional[str] = None
    loop_config: Optional[Dict[str, Any]] = None
    pre_script: Optional[str] = None
    post_script: Optional[str] = None
    continue_on_failure: Optional[bool] = None
    max_retries: Optional[int] = None


class ApiScenarioStepResponse(BaseModel):
    id: int
    scenario_id: int
    step_type: str
    step_name: str
    sort_order: int = 0
    enabled: bool = True
    api_id: Optional[int] = None
    case_id: Optional[int] = None
    request_config: Optional[Dict[str, Any]] = {}
    script_content: Optional[str] = ""
    wait_seconds: Optional[int] = None
    condition_expr: Optional[str] = ""
    loop_config: Optional[Dict[str, Any]] = {}
    pre_script: Optional[str] = ""
    post_script: Optional[str] = ""
    continue_on_failure: bool = False
    max_retries: int = 0
    created_at: Optional[datetime] = None
    variables: List[ApiScenarioVariableResponse] = []

    class Config:
        from_attributes = True


# ==================== ApiScenario ====================
class ApiScenarioBase(BaseModel):
    name: str = Field(..., max_length=200)
    module_id: Optional[int] = None
    plan_id: Optional[int] = None
    description: Optional[str] = ""
    environment_id: Optional[int] = None
    config: Optional[Dict[str, Any]] = {}
    data_pool_id: Optional[int] = None
    pre_script: Optional[str] = ""
    post_script: Optional[str] = ""


class ApiScenarioCreate(ApiScenarioBase):
    pass


class ApiScenarioUpdate(BaseModel):
    name: Optional[str] = None
    module_id: Optional[int] = None
    plan_id: Optional[int] = None
    description: Optional[str] = None
    environment_id: Optional[int] = None
    config: Optional[Dict[str, Any]] = None
    data_pool_id: Optional[int] = None
    pre_script: Optional[str] = None
    post_script: Optional[str] = None


class ApiScenarioResponse(BaseModel):
    id: int
    project_id: int
    module_id: Optional[int] = None
    plan_id: Optional[int] = None
    name: str
    description: Optional[str] = ""
    environment_id: Optional[int] = None
    config: Optional[Dict[str, Any]] = {}
    pre_script: Optional[str] = ""
    post_script: Optional[str] = ""
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    steps: List[ApiScenarioStepResponse] = []

    class Config:
        from_attributes = True


class StepReorderRequest(BaseModel):
    step_ids: List[int]


# ==================== ApiExecution ====================
class ApiExecutionResponse(BaseModel):
    id: int
    project_id: int
    execution_type: str
    ref_id: Optional[int] = None
    ref_name: Optional[str] = ""
    environment_id: Optional[int] = None
    status: str = "pending"
    total_steps: int = 0
    passed_steps: int = 0
    failed_steps: int = 0
    skipped_steps: int = 0
    pass_rate: float = 0
    total_duration: float = 0
    avg_duration: float = 0
    report_id: Optional[int] = None
    trigger_type: str = "manual"
    executed_by: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = ""
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApiExecutionResultResponse(BaseModel):
    id: int
    execution_id: int
    step_id: Optional[int] = None
    step_name: Optional[str] = ""
    sort_order: int = 0
    status: str = "pending"
    request_method: Optional[str] = ""
    request_url: Optional[str] = ""
    request_headers: Optional[Dict[str, Any]] = {}
    request_body: Optional[str] = ""
    response_status: Optional[int] = None
    response_time: float = 0
    response_size: int = 0
    response_headers: Optional[Dict[str, Any]] = {}
    response_body: Optional[str] = ""
    assertions: Optional[List[Dict[str, Any]]] = []
    console_log: Optional[str] = ""
    error_message: Optional[str] = ""
    retry_count: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== ApiMockExpectation ====================
class ApiMockExpectationBase(BaseModel):
    name: str = Field(..., max_length=200)
    api_id: Optional[int] = None
    method: str = "GET"
    path: str = ""
    match_rules: Optional[Dict[str, Any]] = {}
    response_status: int = 200
    response_headers: Optional[Dict[str, Any]] = {}
    response_body: Optional[str] = ""
    delay_ms: int = 0
    enabled: bool = True


class ApiMockExpectationCreate(ApiMockExpectationBase):
    pass


class ApiMockExpectationUpdate(BaseModel):
    name: Optional[str] = None
    api_id: Optional[int] = None
    method: Optional[str] = None
    path: Optional[str] = None
    match_rules: Optional[Dict[str, Any]] = None
    response_status: Optional[int] = None
    response_headers: Optional[Dict[str, Any]] = None
    response_body: Optional[str] = None
    delay_ms: Optional[int] = None
    enabled: Optional[bool] = None


class ApiMockExpectationResponse(BaseModel):
    id: int
    project_id: int
    api_id: Optional[int] = None
    name: str
    method: str
    path: str
    match_rules: Optional[Dict[str, Any]] = {}
    response_status: int = 200
    response_headers: Optional[Dict[str, Any]] = {}
    response_body: Optional[str] = ""
    delay_ms: int = 0
    enabled: bool = True
    hit_count: int = 0
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== ApiDebugHistory ====================
class ApiDebugHistoryResponse(BaseModel):
    id: int
    project_id: int
    user_id: int
    method: str
    url: str
    request_config: Optional[Dict[str, Any]] = {}
    response_status: Optional[int] = None
    response_time: float = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== Debug Request ====================
class ApiDebugRequest(BaseModel):
    method: str = "GET"
    url: str = ""
    headers: Optional[List[Dict[str, Any]]] = []
    query_params: Optional[List[Dict[str, Any]]] = []
    body_type: str = "none"
    body_content: Optional[Any] = None
    environment_id: Optional[int] = None
    pre_script: Optional[str] = ""
    post_script: Optional[str] = ""
    timeout: int = 30


# ==================== AI Generate ====================
class AiGenerateRequest(BaseModel):
    api_id: int
    strategy: str = "comprehensive"
    case_count: int = 5
    coverage_scenarios: Optional[List[str]] = ["normal", "missing_param", "invalid_param"]
    assertion_depth: str = "standard"
    llm_config_id: Optional[int] = None
    prompt_id: Optional[int] = None
    language: str = "zh"


class AiGenerateBatchRequest(BaseModel):
    api_ids: Optional[List[int]] = []
    module_id: Optional[int] = None
    strategy: str = "comprehensive"
    case_count: int = 5
    coverage_scenarios: Optional[List[str]] = ["normal", "missing_param", "invalid_param"]
    assertion_depth: str = "standard"
    llm_config_id: Optional[int] = None


class AiGenerateSaveRequest(BaseModel):
    selected_indices: Optional[List[int]] = None
    module_id: Optional[int] = None


# ==================== Import ====================
class ApiImportRequest(BaseModel):
    import_type: str  # postman/swagger/jmeter/har/apifox
    file_content: str
    file_name: Optional[str] = ""
    module_id: Optional[int] = None
    import_mode: str = "merge"  # overwrite/merge/skip


class ApiImportPreviewResponse(BaseModel):
    import_type: str = ""
    file_name: str = ""
    total_count: int = 0
    apis: List[Dict[str, Any]] = []


# ==================== Run Request ====================
def _normalize_env_vars(v):
    """将 environment_vars 从数组格式 [{key,value}] 转为字典格式 {key: value}"""
    if isinstance(v, list):
        return {item["key"]: item.get("value", "") for item in v if isinstance(item, dict) and item.get("key")}
    return v


class ApiCaseRunRequest(BaseModel):
    environment_id: Optional[int] = None
    variables: Optional[Dict[str, Any]] = {}
    environment_vars: Optional[Dict[str, Any]] = {}
    base_url: Optional[str] = ""

    @field_validator("environment_vars", mode="before")
    @classmethod
    def normalize_env_vars(cls, v):
        return _normalize_env_vars(v)


class ApiCaseBatchRunRequest(BaseModel):
    case_ids: List[int]
    environment_id: Optional[int] = None


class ApiScenarioRunRequest(BaseModel):
    environment_id: Optional[int] = None
    variables: Optional[Dict[str, Any]] = {}
    extra_vars: Optional[Dict[str, Any]] = {}


# ==================== 通用分页响应 ====================
class PaginatedResponse(BaseModel):
    total: int = 0
    page: int = 1
    page_size: int = 20
    items: List[Any] = []


# ==================== Debug 响应 ====================
class ApiDebugSendRequest(BaseModel):
    method: str = "GET"
    url: str = ""
    headers: Optional[List[Dict[str, Any]]] = []
    query_params: Optional[List[Dict[str, Any]]] = []
    body_type: str = "none"
    body_content: Optional[Any] = None
    environment_id: Optional[int] = None
    environment_vars: Optional[Dict[str, Any]] = {}
    pre_script: Optional[str] = ""
    post_script: Optional[str] = ""
    timeout: int = 30

    @field_validator("environment_vars", mode="before")
    @classmethod
    def normalize_env_vars(cls, v):
        return _normalize_env_vars(v)


class ApiDebugResponse(BaseModel):
    status_code: int = 0
    response_time: float = 0
    response_size: int = 0
    response_headers: Optional[Dict[str, Any]] = {}
    response_body: str = ""
    error: Optional[str] = None
    console_log: str = ""
    tests: List[Dict[str, Any]] = []


# ==================== 用例执行响应 ====================
class ApiCaseRunResponse(BaseModel):
    execution_id: int
    status: str
    response_status: int = 0
    response_time: float = 0
    response_body: str = ""
    response_headers: Optional[Dict[str, Any]] = {}
    assertions: List[Dict[str, Any]] = []
    console_log: str = ""
    tests: List[Dict[str, Any]] = []
    error: Optional[str] = None
