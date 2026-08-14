"""
Agent 任务记录工具
提供统一的 AgentTask 创建和更新方法
"""
from typing import Optional, Any, Dict
from sqlalchemy.orm import Session
from app.models.agent_task import AgentTask
from app.core.timezone import china_now_naive


def create_agent_task(
    db: Session,
    agent_type: str,
    input_params: Dict[str, Any],
    project_id: Optional[int] = None,
    created_by: Optional[int] = None,
    llm_config_id: Optional[int] = None,
    status: str = "pending",
) -> AgentTask:
    """
    创建 Agent 任务记录

    Args:
        db: 数据库会话
        agent_type: Agent类型 case_generator/ui_execution/reviewer/defect_analyzer/report_generator/script_generator/script_fixer/knowledge_processor
        input_params: 输入参数
        project_id: 项目ID
        created_by: 创建人ID
        llm_config_id: 使用的模型配置ID
        status: 初始状态

    Returns:
        AgentTask 对象
    """
    task = AgentTask(
        project_id=project_id,
        agent_type=agent_type,
        status=status,
        input_params=input_params,
        output_result={},
        llm_config_id=llm_config_id,
        token_usage={},
        error_message="",
        retry_count=0,
        created_by=created_by,
    )
    db.add(task)
    db.flush()
    return task


def update_agent_task(
    db: Session,
    task_id: int,
    status: Optional[str] = None,
    output_result: Optional[Dict[str, Any]] = None,
    token_usage: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    increment_retry: bool = False,
) -> Optional[AgentTask]:
    """
    更新 Agent 任务记录

    Args:
        db: 数据库会话
        task_id: 任务ID
        status: 新状态
        output_result: 输出结果
        token_usage: Token使用量
        error_message: 错误信息
        increment_retry: 是否增加重试次数

    Returns:
        更新后的 AgentTask 对象
    """
    task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
    if not task:
        return None

    if status is not None:
        task.status = status
        if status in ("success", "failed"):
            task.completed_at = china_now_naive()
    if output_result is not None:
        task.output_result = output_result
    if token_usage is not None:
        task.token_usage = token_usage
    if error_message is not None:
        task.error_message = error_message
    if increment_retry:
        task.retry_count = (task.retry_count or 0) + 1

    db.flush()
    return task
