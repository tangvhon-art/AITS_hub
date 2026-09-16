"""
接口测试模块数据模型
包含11张表：api_modules, api_definitions, api_test_cases, api_case_assertions,
api_scenarios, api_scenario_steps, api_scenario_variables, api_executions,
api_execution_results, api_mock_expectations, api_debug_history
"""
from app.core.timezone import china_now_naive
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float, Boolean, JSON
from app.database import Base, SoftDeleteMixin


class ApiModule(SoftDeleteMixin, Base):
    """接口目录/模块表"""
    __tablename__ = "api_modules"
    __table_args__ = {"comment": "接口目录表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    parent_id = Column(Integer, ForeignKey("api_modules.id"), nullable=True, index=True, comment="父目录ID，顶级为NULL")
    name = Column(String(100), nullable=False, comment="目录名称")
    sort_order = Column(Integer, default=0, comment="排序")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")


class ApiDefinition(SoftDeleteMixin, Base):
    """接口定义表"""
    __tablename__ = "api_definitions"
    __table_args__ = {"comment": "接口定义表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    module_id = Column(Integer, ForeignKey("api_modules.id"), nullable=True, index=True, comment="所属目录ID")
    name = Column(String(200), nullable=False, comment="接口名称")
    method = Column(String(10), nullable=False, comment="请求方法: GET/POST/PUT/DELETE/PATCH/HEAD/OPTIONS")
    path = Column(String(500), nullable=False, comment="请求路径")
    description = Column(Text, nullable=True, comment="接口描述(Markdown)")
    tags = Column(String(500), nullable=True, comment="标签，逗号分隔")
    status = Column(String(20), default="draft", comment="状态: draft/active/deprecated")
    headers = Column(JSON, default=list, comment="请求头配置")
    query_params = Column(JSON, default=list, comment="查询参数配置")
    path_params = Column(JSON, default=list, comment="路径参数配置")
    body_type = Column(String(20), default="none", comment="请求体类型: none/form-data/x-www-form-urlencoded/raw/binary")
    body_content = Column(JSON, default=dict, comment="请求体内容")
    pre_script = Column(Text, nullable=True, comment="接口级前置脚本(JS)")
    post_script = Column(Text, nullable=True, comment="接口级后置脚本(JS)")
    raw_language = Column(String(20), default="Text", comment="raw请求体语言: Text/JSON/XML等")
    response_examples = Column(JSON, default=list, comment="响应示例列表")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")


class ApiTestCase(SoftDeleteMixin, Base):
    """接口测试用例表"""
    __tablename__ = "api_test_cases"
    __table_args__ = {"comment": "接口测试用例表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    module_id = Column(Integer, ForeignKey("api_modules.id"), nullable=True, index=True, comment="所属目录ID")
    api_id = Column(Integer, ForeignKey("api_definitions.id"), nullable=True, index=True, comment="关联接口定义ID")
    name = Column(String(200), nullable=False, comment="用例名称")
    description = Column(Text, nullable=True, comment="用例描述")
    priority = Column(String(10), default="P2", comment="优先级: P0/P1/P2/P3")
    tags = Column(String(500), nullable=True, comment="标签")
    method = Column(String(10), nullable=True, comment="请求方法(覆盖接口定义)")
    path = Column(String(500), nullable=True, comment="请求路径(覆盖接口定义)")
    headers = Column(JSON, default=list, comment="请求头")
    query_params = Column(JSON, default=list, comment="查询参数")
    body_type = Column(String(20), default="none", comment="请求体类型")
    body_content = Column(JSON, default=dict, comment="请求体内容")
    pre_script = Column(Text, nullable=True, comment="前置脚本(JS)")
    post_script = Column(Text, nullable=True, comment="后置脚本(JS)")
    param_source = Column(String(20), default="none", comment="参数化来源: none/csv/json/data_pool")
    param_data = Column(JSON, default=list, comment="参数化数据")
    data_pool_id = Column(Integer, ForeignKey("test_data_pools.id"), nullable=True, comment="关联测试数据池ID")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")


class ApiCaseAssertion(SoftDeleteMixin, Base):
    """用例断言配置表"""
    __tablename__ = "api_case_assertions"
    __table_args__ = {"comment": "接口用例断言表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    case_id = Column(Integer, ForeignKey("api_test_cases.id"), nullable=False, index=True, comment="用例ID")
    assert_type = Column(String(30), nullable=False, comment="断言类型: status_code/response_time/header/jsonpath/xpath/contains/equals/regex/script")
    assert_target = Column(String(500), nullable=True, comment="断言目标(如JSONPath表达式)")
    operator = Column(String(20), nullable=False, comment="操作符: equals/not_equals/contains/not_contains/less_than/greater_than/matches/in_range")
    expected_value = Column(Text, nullable=True, comment="期望值")
    sort_order = Column(Integer, default=0, comment="排序")
    enabled = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")


class ApiScenario(SoftDeleteMixin, Base):
    """接口测试场景表"""
    __tablename__ = "api_scenarios"
    __table_args__ = {"comment": "接口测试场景表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    module_id = Column(Integer, ForeignKey("api_modules.id"), nullable=True, index=True, comment="所属目录ID")
    plan_id = Column(Integer, ForeignKey("test_plans.id"), nullable=True, index=True, comment="关联测试计划ID")
    name = Column(String(200), nullable=False, comment="场景名称")
    description = Column(Text, nullable=True, comment="场景描述")
    environment_id = Column(Integer, ForeignKey("test_environments.id"), nullable=True, comment="默认环境ID")
    config = Column(JSON, default=dict, comment="执行配置: 并发数/失败是否继续/重试次数")
    data_pool_id = Column(Integer, ForeignKey("test_data_pools.id"), nullable=True, comment="关联测试数据池ID")
    pre_script = Column(Text, nullable=True, comment="场景前置脚本")
    post_script = Column(Text, nullable=True, comment="场景后置脚本")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")


class ApiScenarioStep(SoftDeleteMixin, Base):
    """场景步骤表"""
    __tablename__ = "api_scenario_steps"
    __table_args__ = {"comment": "场景步骤表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    scenario_id = Column(Integer, ForeignKey("api_scenarios.id"), nullable=False, index=True, comment="场景ID")
    step_type = Column(String(20), nullable=False, comment="步骤类型: api/case/script/wait/condition/loop")
    step_name = Column(String(200), nullable=False, comment="步骤名称")
    sort_order = Column(Integer, default=0, comment="执行顺序")
    enabled = Column(Boolean, default=True, comment="是否启用")
    api_id = Column(Integer, ForeignKey("api_definitions.id"), nullable=True, comment="关联接口ID(step_type=api)")
    case_id = Column(Integer, ForeignKey("api_test_cases.id"), nullable=True, comment="关联用例ID(step_type=case)")
    request_config = Column(JSON, default=dict, comment="请求配置(覆盖用)")
    script_content = Column(Text, nullable=True, comment="脚本内容(step_type=script)")
    wait_seconds = Column(Integer, nullable=True, comment="等待秒数(step_type=wait)")
    condition_expr = Column(Text, nullable=True, comment="条件表达式(step_type=condition)")
    loop_config = Column(JSON, default=dict, comment="循环配置(step_type=loop)")
    pre_script = Column(Text, nullable=True, comment="步骤前置脚本")
    post_script = Column(Text, nullable=True, comment="步骤后置脚本")
    continue_on_failure = Column(Boolean, default=False, comment="失败是否继续")
    max_retries = Column(Integer, default=0, comment="最大重试次数")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")


class ApiScenarioVariable(SoftDeleteMixin, Base):
    """场景变量提取配置表"""
    __tablename__ = "api_scenario_variables"
    __table_args__ = {"comment": "场景变量提取配置表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    step_id = Column(Integer, ForeignKey("api_scenario_steps.id"), nullable=False, index=True, comment="步骤ID")
    var_name = Column(String(100), nullable=False, comment="变量名")
    extract_type = Column(String(20), nullable=False, comment="提取方式: jsonpath/regex/header/cookie")
    extract_expr = Column(String(500), nullable=False, comment="提取表达式")
    default_value = Column(String(500), nullable=True, comment="默认值")
    scope = Column(String(20), default="scenario", comment="作用域: scenario/global")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")


class ApiExecution(SoftDeleteMixin, Base):
    """接口执行记录表"""
    __tablename__ = "api_executions"
    __table_args__ = {"comment": "接口执行记录表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    execution_type = Column(String(20), nullable=False, comment="执行类型: case/scenario/debug")
    ref_id = Column(Integer, nullable=True, comment="关联ID(用例ID/场景ID)")
    ref_name = Column(String(200), nullable=True, comment="关联名称")
    environment_id = Column(Integer, ForeignKey("test_environments.id"), nullable=True, comment="执行环境ID")
    status = Column(String(20), default="pending", index=True, comment="状态: pending/running/passed/failed/partial")
    total_steps = Column(Integer, default=0, comment="总步骤数")
    passed_steps = Column(Integer, default=0, comment="通过步骤数")
    failed_steps = Column(Integer, default=0, comment="失败步骤数")
    skipped_steps = Column(Integer, default=0, comment="跳过步骤数")
    pass_rate = Column(Float, default=0, comment="通过率")
    total_duration = Column(Float, default=0, comment="总耗时(秒)")
    avg_duration = Column(Float, default=0, comment="平均耗时(秒)")
    report_id = Column(Integer, ForeignKey("test_reports.id"), nullable=True, comment="关联测试报告ID")
    trigger_type = Column(String(20), default="manual", comment="触发方式: manual/schedule/api")
    executed_by = Column(Integer, ForeignKey("users.id"), comment="执行人ID")
    started_at = Column(DateTime, nullable=True, comment="开始时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    error_message = Column(Text, nullable=True, comment="错误信息")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")


class ApiExecutionResult(SoftDeleteMixin, Base):
    """执行结果详情表"""
    __tablename__ = "api_execution_results"
    __table_args__ = {"comment": "接口执行结果详情表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    execution_id = Column(Integer, ForeignKey("api_executions.id"), nullable=False, index=True, comment="执行记录ID")
    step_id = Column(Integer, nullable=True, comment="步骤ID(调试时为空)")
    step_name = Column(String(200), nullable=True, comment="步骤名称")
    sort_order = Column(Integer, default=0, comment="执行顺序")
    status = Column(String(20), default="pending", comment="状态: pending/running/passed/failed/skipped")
    request_method = Column(String(10), nullable=True, comment="请求方法")
    request_url = Column(String(1000), nullable=True, comment="请求URL")
    request_headers = Column(JSON, default=dict, comment="请求头")
    request_body = Column(Text, nullable=True, comment="请求体")
    response_status = Column(Integer, nullable=True, comment="响应状态码")
    response_time = Column(Float, default=0, comment="响应时间(ms)")
    response_size = Column(Integer, default=0, comment="响应大小(bytes)")
    response_headers = Column(JSON, default=dict, comment="响应头")
    response_body = Column(Text, nullable=True, comment="响应体")
    assertions = Column(JSON, default=list, comment="断言结果列表")
    console_log = Column(Text, nullable=True, comment="控制台输出")
    error_message = Column(Text, nullable=True, comment="错误信息")
    retry_count = Column(Integer, default=0, comment="重试次数")
    started_at = Column(DateTime, nullable=True, comment="开始时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")


class ApiMockExpectation(SoftDeleteMixin, Base):
    """Mock期望配置表"""
    __tablename__ = "api_mock_expectations"
    __table_args__ = {"comment": "接口Mock期望表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    api_id = Column(Integer, ForeignKey("api_definitions.id"), nullable=True, index=True, comment="关联接口ID")
    name = Column(String(200), nullable=False, comment="期望名称")
    method = Column(String(10), nullable=False, comment="请求方法")
    path = Column(String(500), nullable=False, comment="匹配路径")
    match_rules = Column(JSON, default=dict, comment="匹配规则(参数/头/体)")
    response_status = Column(Integer, default=200, comment="响应状态码")
    response_headers = Column(JSON, default=dict, comment="响应头")
    response_body = Column(Text, nullable=True, comment="响应体(支持模板)")
    delay_ms = Column(Integer, default=0, comment="响应延迟(ms)")
    enabled = Column(Boolean, default=True, comment="是否启用")
    hit_count = Column(Integer, default=0, comment="命中次数")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")


class ApiDebugHistory(SoftDeleteMixin, Base):
    """调试历史记录表"""
    __tablename__ = "api_debug_history"
    __table_args__ = {"comment": "接口调试历史表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="用户ID")
    method = Column(String(10), nullable=False, comment="请求方法")
    url = Column(String(1000), nullable=False, comment="请求URL")
    request_config = Column(JSON, default=dict, comment="完整请求配置")
    response_status = Column(Integer, nullable=True, comment="响应状态码")
    response_time = Column(Float, default=0, comment="响应时间(ms)")
    created_at = Column(DateTime, default=china_now_naive, index=True, comment="创建时间")
