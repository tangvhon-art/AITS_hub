"""
外部工作流调用与回调日志记录器

记录 invoke/accept/callback/complete/fail 各阶段，含脱敏与降级标记。
供连接器、Webhook 接收端点、回调处理任务调用。
"""
import logging
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from app.models.workflow import WorkflowCallLog

logger = logging.getLogger(__name__)

# 入参出参中需脱敏的字段名（小写匹配）
_SENSITIVE_KEYS = {"auth_token", "secret", "authorization", "x-aits-signature", "api_key", "token"}


def _mask_value(value: Any) -> Any:
    if isinstance(value, str) and value:
        if len(value) <= 6:
            return "*" * len(value)
        return value[:3] + "***" + value[-2:]
    return value


def _sanitize(obj: Any) -> Any:
    """递归脱敏：将敏感字段的值替换为掩码"""
    if isinstance(obj, dict):
        return {
            k: ("***" if str(k).lower() in _SENSITIVE_KEYS else _sanitize(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, str):
        return _mask_value(obj) if any(s in obj.lower() for s in ("bearer ", "sk-")) else obj
    return obj


def log_call(
    db: Session,
    *,
    agent_task_id: int,
    module_id: str,
    phase: str,
    status: str,
    connector_id: Optional[int] = None,
    uuid: Optional[str] = None,
    request_json: Optional[Dict[str, Any]] = None,
    response_json: Optional[Dict[str, Any]] = None,
    external_task_id: Optional[str] = None,
    cost_ms: Optional[int] = None,
    retry_times: int = 0,
    fallback_used: bool = False,
    error_msg: Optional[str] = None,
) -> WorkflowCallLog:
    """写入一条调用/回调日志（脱敏后存储）。写入失败不影响主流程"""
    try:
        log = WorkflowCallLog(
            agent_task_id=agent_task_id,
            module_id=module_id,
            connector_id=connector_id,
            uuid=uuid,
            request_json=_sanitize(request_json) if request_json else None,
            response_json=_sanitize(response_json) if response_json else None,
            external_task_id=external_task_id,
            phase=phase,
            status=status,
            cost_ms=cost_ms,
            retry_times=retry_times,
            fallback_used=fallback_used,
            error_msg=(error_msg[:2000] if error_msg else None),
        )
        db.add(log)
        db.commit()
        return log
    except Exception as e:
        logger.warning(f"写入 workflow_call_logs 失败(phase={phase}): {e}")
        db.rollback()
        return None
