from datetime import datetime
from app.core.timezone import china_now_naive
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON
from app.database import Base, SoftDeleteMixin


class AgentTask(SoftDeleteMixin, Base):
    __tablename__ = "agent_tasks"
    __table_args__ = {"comment": "Agent任务表"}

    id = Column(Integer, primary_key=True, index=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=True, index=True, comment="所属项目ID")
    agent_type = Column(String(50), nullable=False, index=True, comment="Agent类型：case_generator-用例生成，case_reviewer-用例评审，case_optimizer-用例优化，requirement_generator-需求生成，api_case_generator-接口用例生成，api_doc_generator-接口文档生成，ui_execution-UI执行，defect_analyzer-缺陷分析，report_generator-报告生成，bdd_generator-BDD生成，script_generator-脚本生成，script_fixer-脚本修复，knowledge_processor-知识库处理，supervisor-编排，notification-通知")
    status = Column(String(20), default="pending", index=True, comment="状态：pending-等待，running-执行中，success-成功，failed-失败，retrying-重试中")
    input_params = Column(JSON, default=dict, comment="输入参数（JSON）")
    output_result = Column(JSON, default=dict, comment="输出结果（JSON）")
    llm_config_id = Column(Integer, ForeignKey("llm_configs.id"), nullable=True, comment="使用的模型配置ID")
    token_usage = Column(JSON, default=dict, comment="Token消耗统计：prompt_tokens/completion_tokens/total_tokens")
    error_message = Column(Text, default="", comment="错误信息")
    retry_count = Column(Integer, default=0, comment="重试次数")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, index=True, comment="创建时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    # ── 外部工作流接入扩展字段 ──
    backend = Column(String(20), default="local", index=True, comment="执行后端：local/workflow（含页面选择）")
    uuid = Column(String(64), nullable=True, index=True, comment="AITS回调定位ID（传给外部，回调原样带回）")
    external_task_id = Column(String(128), nullable=True, comment="外部平台受理的任务ID")
