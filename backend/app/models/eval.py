"""AI 模型五维综合测评数据模型

覆盖五维测评（AI 裁判 / 人工 / Agent 交互 / 业务落地 / 对抗红队）的
9 张业务表，全部继承 SoftDeleteMixin 支持软删，系统级（不归属项目）。
测评任务异步执行状态复用 agent_tasks（eval_tasks.agent_task_id 关联）。
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, JSON, ForeignKey
from app.core.timezone import china_now_naive
from app.database import Base, SoftDeleteMixin


class EvalTarget(SoftDeleteMixin, Base):
    """测评对象表：被测对象（llm / agent / external_agent / business）"""
    __tablename__ = "eval_targets"
    __table_args__ = {"comment": "测评对象表"}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="被测对象名称")
    target_type = Column(String(20), nullable=False, index=True, comment="类型：llm/agent/external_agent/business")
    llm_config_id = Column(Integer, ForeignKey("llm_configs.id"), nullable=True, comment="target_type=llm 时绑定模型")
    agent_type = Column(String(50), nullable=True, comment="target_type=agent 时绑定 AITS 内置 Agent 类型")
    # 外部工作流（external_agent）：直接填写调用服务地址 / 调用路径 / 鉴权方式，无需预绑定平台连接
    service_url = Column(String(500), nullable=True, comment="target_type=external_agent 时外部服务地址（Base URL）")
    call_path = Column(String(200), nullable=True, comment="target_type=external_agent 时调用路径")
    auth_type = Column(String(30), default="none", comment="target_type=external_agent 时鉴权方式：none/bearer/apikey/custom")
    auth_token = Column(Text, nullable=True, comment="target_type=external_agent 时鉴权凭证（API Key / Bearer Token，加密存储）")
    auth_header = Column(String(100), default="Authorization", comment="target_type=external_agent 时鉴权 Header 名")
    business_scene = Column(String(100), nullable=True, comment="business 时业务场景标识")
    version_tag = Column(String(50), nullable=True, comment="版本标识（模型/Agent 版本）")
    description = Column(Text, nullable=True, comment="描述")
    status = Column(String(20), default="active", comment="active/inactive")
    created_by = Column(Integer, comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")


class EvalDataset(SoftDeleteMixin, Base):
    """测评数据集表"""
    __tablename__ = "eval_datasets"
    __table_args__ = {"comment": "测评数据集表"}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="数据集名称")
    eval_type = Column(String(20), nullable=False, index=True, comment="ai_judge/agent/business/redteam/manual")
    source = Column(String(20), default="custom", comment="builtin/custom/import/gray")
    version = Column(String(30), nullable=True, comment="数据集版本")
    case_count = Column(Integer, default=0, comment="用例数冗余统计")
    description = Column(Text, nullable=True, comment="描述")
    status = Column(String(20), default="active", comment="active/archived")
    created_by = Column(Integer, comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")


class EvalCase(SoftDeleteMixin, Base):
    """测评用例表"""
    __tablename__ = "eval_cases"
    __table_args__ = {"comment": "测评用例表"}

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("eval_datasets.id"), nullable=False, index=True, comment="所属数据集")
    eval_type = Column(String(20), nullable=False, index=True, comment="测评类型（冗余便于检索）")
    title = Column(String(200), nullable=False, comment="用例标题")
    prompt = Column(Text, nullable=False, comment="用户输入/任务描述/攻击载荷")
    expected_output = Column(Text, nullable=True, comment="预期输出/判定规则")
    ref_answer = Column(Text, nullable=True, comment="参考答案（人工测评用）")
    category = Column(String(50), nullable=True, comment="场景分类（业务类型/攻击类别）")
    difficulty = Column(String(10), default="P2", comment="难度 P0/P1/P2/P3")
    tags = Column(JSON, nullable=True, comment="标签列表")
    attack_type = Column(String(50), nullable=True, comment="红队攻击类型（越狱/注入/隐私/偏见/边界）")
    constraints = Column(Text, nullable=True, comment="约束条件")
    status = Column(String(20), default="active", comment="active/archived")
    created_by = Column(Integer, comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")


class EvalTask(SoftDeleteMixin, Base):
    """测评任务主表"""
    __tablename__ = "eval_tasks"
    __table_args__ = {"comment": "测评任务主表"}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, comment="测评任务名称")
    target_id = Column(Integer, ForeignKey("eval_targets.id"), nullable=False, comment="被测对象")
    compare_target_id = Column(Integer, nullable=True, comment="对比被测对象（版本对比）")
    version_id = Column(Integer, nullable=True, comment="关联项目版本 project_versions.id")
    modes = Column(JSON, nullable=False, comment="启用的五维模式配置 {ai_judge:{...},redteam:{...}}")
    dataset_ids = Column(JSON, nullable=False, comment="各模式使用数据集 {ai_judge:[1,2],redteam:[3]}")
    judge_config_ids = Column(JSON, nullable=True, comment="裁判模型 llm_configs.id 列表")
    settings = Column(JSON, nullable=True, comment="执行配置：抽样/超时/并发/速率/顺序")
    status = Column(String(20), default="draft", index=True, comment="draft/ready/running/completed/failed/canceled")
    progress = Column(Integer, default=0, comment="整体进度 0-100")
    summary = Column(JSON, nullable=True, comment="结果汇总（五维得分、通过率、结论）")
    conclusion = Column(String(20), nullable=True, comment="准入结论 pass/conditional/reject")
    backend = Column(String(20), default="local", comment="执行后端 local/workflow")
    agent_task_id = Column(Integer, nullable=True, comment="关联 agent_tasks.id（异步执行载体）")
    started_at = Column(DateTime, nullable=True, comment="开始时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    created_by = Column(Integer, comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")


class EvalRun(SoftDeleteMixin, Base):
    """模式执行批次表"""
    __tablename__ = "eval_runs"
    __table_args__ = {"comment": "模式执行批次表"}

    id = Column(Integer, primary_key=True, index=True)
    eval_task_id = Column(Integer, ForeignKey("eval_tasks.id"), nullable=False, index=True, comment="所属任务")
    mode = Column(String(20), nullable=False, index=True, comment="ai_judge/manual/agent/business/redteam")
    dataset_id = Column(Integer, ForeignKey("eval_datasets.id"), nullable=True, comment="使用的数据集")
    status = Column(String(20), default="pending", comment="pending/running/completed/failed")
    total_cases = Column(Integer, default=0, comment="用例总数")
    passed_cases = Column(Integer, default=0, comment="通过用例数")
    failed_cases = Column(Integer, default=0, comment="失败用例数")
    pass_rate = Column(Float, nullable=True, comment="通过率")
    score_avg = Column(Float, nullable=True, comment="平均分（AI裁判/人工）")
    metrics = Column(JSON, nullable=True, comment="模式专属指标（Agent五维/业务指标/红队指标）")
    logs = Column(JSON, nullable=True, comment="执行日志摘要")
    progress = Column(Integer, default=0, comment="模式进度 0-100")
    started_at = Column(DateTime, nullable=True, comment="开始时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")


class EvalResult(SoftDeleteMixin, Base):
    """用例级测评结果表（核心明细表）"""
    __tablename__ = "eval_results"
    __table_args__ = {"comment": "用例级测评结果表"}

    id = Column(Integer, primary_key=True, index=True)
    eval_task_id = Column(Integer, ForeignKey("eval_tasks.id"), nullable=False, index=True, comment="所属任务")
    eval_run_id = Column(Integer, ForeignKey("eval_runs.id"), nullable=False, index=True, comment="所属批次")
    case_id = Column(Integer, ForeignKey("eval_cases.id"), nullable=False, index=True, comment="关联用例")
    target_id = Column(Integer, nullable=True, comment="被测对象")
    model_output = Column(Text, nullable=True, comment="被测对象输出")
    judge_scores = Column(JSON, nullable=True, comment="多裁判打分明细 [{judge_id,scores,reason}]")
    score = Column(Float, nullable=True, comment="聚合综合分")
    dimension_scores = Column(JSON, nullable=True, comment="五维各维度得分")
    manual_score = Column(Float, nullable=True, comment="人工打分")
    manual_comment = Column(Text, nullable=True, comment="人工评语")
    review_status = Column(String(20), default="pending", comment="pending/done 人工复核状态")
    agent_metrics = Column(JSON, nullable=True, comment="Agent 模式指标（拆解/工具/闭环/纠错/质量）")
    business_result = Column(JSON, nullable=True, comment="业务判定 success/fail + 原因")
    redteam_result = Column(String(20), nullable=True, comment="blocked/passed/partial")
    risk_level = Column(String(10), nullable=True, comment="P0-P3 风险定级")
    trace = Column(JSON, nullable=True, comment="Agent 交互轨迹/思考链（回放用）")
    latency = Column(Float, nullable=True, comment="响应时延 ms")
    token_usage = Column(JSON, nullable=True, comment="Token 用量")
    status = Column(String(20), default="pending", index=True, comment="passed/failed/flagged/blocked")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")


class EvalReport(SoftDeleteMixin, Base):
    """测评报告表"""
    __tablename__ = "eval_reports"
    __table_args__ = {"comment": "测评报告表"}

    id = Column(Integer, primary_key=True, index=True)
    eval_task_id = Column(Integer, ForeignKey("eval_tasks.id"), nullable=False, index=True, comment="关联测评任务")
    report_type = Column(String(20), default="overall", comment="overall/ai_judge/manual/agent/business/redteam")
    title = Column(String(200), nullable=False, comment="报告标题")
    content = Column(Text, nullable=True, comment="报告内容（Markdown/HTML）")
    summary = Column(JSON, nullable=True, comment="指标汇总")
    conclusion = Column(String(20), nullable=True, comment="准入结论 pass/conditional/reject")
    status = Column(String(20), default="generating", comment="generating/completed/failed")
    file_url = Column(String(500), nullable=True, comment="导出文件路径")
    created_by = Column(Integer, comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")


class EvalIssue(SoftDeleteMixin, Base):
    """问题台账表"""
    __tablename__ = "eval_issues"
    __table_args__ = {"comment": "测评问题台账表"}

    id = Column(Integer, primary_key=True, index=True)
    eval_task_id = Column(Integer, ForeignKey("eval_tasks.id"), nullable=False, index=True, comment="关联任务")
    issue_level = Column(String(10), default="P2", comment="P0/P1/P2/P3")
    issue_type = Column(String(50), nullable=True, comment="安全越狱/违规输出/幻觉/业务失败/Agent失败/能力降级/边界适配")
    title = Column(String(200), nullable=False, comment="问题标题")
    description = Column(Text, nullable=True, comment="问题描述")
    evidence = Column(JSON, nullable=True, comment="证据：关联 result_ids/用例/输出/攻击日志")
    status = Column(String(20), default="open", comment="open/fixing/fixed/closed/archived")
    owner_id = Column(Integer, nullable=True, comment="负责人")
    fix_suggestion = Column(Text, nullable=True, comment="修复建议")
    retest_result = Column(Text, nullable=True, comment="复测结果")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    closed_at = Column(DateTime, nullable=True, comment="关闭时间")


class EvalBaseline(SoftDeleteMixin, Base):
    """测评基线表"""
    __tablename__ = "eval_baselines"
    __table_args__ = {"comment": "测评基线表"}

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, nullable=False, comment="被测对象")
    version_id = Column(Integer, nullable=True, comment="关联版本")
    baseline_name = Column(String(100), nullable=False, comment="基线名称")
    eval_task_id = Column(Integer, nullable=True, comment="来源测评任务")
    metrics = Column(JSON, nullable=True, comment="基线指标快照")
    created_by = Column(Integer, comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
