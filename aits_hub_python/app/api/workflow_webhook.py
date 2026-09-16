"""
外部工作流回调 Webhook 接收端点（无需鉴权，靠 HMAC 签名校验）

固定端点：POST /api/workflow/webhook
- 通过 HMAC-SHA256 签名校验防伪造（X-Aits-Signature 头）
- 通过 uuid 定位 AgentTask（不依赖外部 task_id）
- 幂等：同一 uuid 重复回调只处理一次
- 快速应答 202 + 派发 handle_workflow_callback_task Celery 任务
"""
import json
import logging
import time
from collections import defaultdict
from typing import Dict

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agent_task import AgentTask
from app.services.workflow_config_service import (
    is_webhook_enabled, get_webhook_secret, AGENT_TYPE_TO_MODULE,
)
from app.services.workflow_signature import verify_signature
from app.services.workflow_call_logger import log_call
from app.core.tasks import dispatch_task
from app.tasks.workflow_tasks import handle_workflow_callback_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflow", tags=["外部工作流回调"])

# ── 简单内存级速率限制（基于客户端 IP，防止恶意请求打满）──
# 每个 IP 每分钟最多 60 次请求，超过则返回 429
_RATE_LIMIT_WINDOW = 60  # 秒
_RATE_LIMIT_MAX = 60     # 窗口内最大请求数
_rate_limit_store: Dict[str, list] = defaultdict(list)


def _check_rate_limit(client_ip: str) -> bool:
    """检查客户端 IP 是否超过速率限制，返回 True 表示允许，False 表示超限"""
    now = time.time()
    # 清理过期记录
    _rate_limit_store[client_ip] = [
        t for t in _rate_limit_store[client_ip]
        if now - t < _RATE_LIMIT_WINDOW
    ]
    if len(_rate_limit_store[client_ip]) >= _RATE_LIMIT_MAX:
        return False
    _rate_limit_store[client_ip].append(now)
    return True


@router.post("/webhook")
async def receive_webhook(request: Request, response: Response, db: Session = Depends(get_db)):
    """接收外部平台回调

    请求体约定：
    ```
    {
        "uuid": "wf_xxx",         // 必填，AITS 生成并传给外部的回调定位 ID
        "status": "success",      // 必填，success / failed
        "content": "...",         // success 时必填，外部 agent 输出内容（raw 文本）
        "task_id": "...",         // 可选，外部平台自己的 task_id
        "error": "..."            // failed 时必填，失败原因
    }
    ```
    """
    # 0. 速率限制（基于客户端 IP，每分钟最多 60 次）
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        logger.warning(f"[webhook] 速率限制触发: client_ip={client_ip}")
        response.status_code = status.HTTP_429_TOO_MANY_REQUESTS
        return {"error": "rate limit exceeded"}

    # 1. 获取原始 body 字节（用于签名校验）
    body = await request.body()

    # 2. 全局开关检查
    if not is_webhook_enabled(db):
        logger.warning("[webhook] Webhook 未启用，拒绝回调")
        response.status_code = status.HTTP_403_FORBIDDEN
        return {"error": "webhook disabled"}

    # 3. 签名校验（HMAC-SHA256，支持可选时间戳防重放）
    signature = request.headers.get("X-Aits-Signature", "")
    timestamp = request.headers.get("X-Aits-Timestamp", "")
    secret = get_webhook_secret(db)
    if not verify_signature(secret, body, signature, timestamp):
        logger.warning(f"[webhook] 签名校验失败: signature={signature[:20] if signature else '(empty)'}, timestamp={timestamp or '(none)'}")
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return {"error": "invalid signature or timestamp expired"}

    # 4. 解析 body JSON
    try:
        payload = json.loads(body) if body else {}
    except Exception:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": "invalid json"}

    uuid = payload.get("uuid")
    cb_status = (payload.get("status") or "success").lower()
    content = payload.get("content") or ""
    external_task_id = payload.get("task_id")
    error = payload.get("error") or ""

    if not uuid:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": "missing uuid"}

    if cb_status not in ("success", "failed"):
        cb_status = "success"

    # 5. uuid 定位任务
    task = db.query(AgentTask).filter(
        AgentTask.uuid == uuid,
        AgentTask.backend == "workflow",
    ).first()
    if not task:
        logger.warning(f"[webhook] uuid 未定位到任务: {uuid}")
        response.status_code = status.HTTP_404_NOT_FOUND
        return {"error": "task not found"}

    module_id = AGENT_TYPE_TO_MODULE.get(task.agent_type, task.agent_type)

    # 6. 幂等检查：任务已完成/失败则直接返回成功（重复回调）
    if task.status in ("success", "failed"):
        logger.info(
            f"[webhook] 任务已处理 uuid={uuid} status={task.status}，幂等返回"
        )
        log_call(
            db, agent_task_id=task.id, module_id=module_id, uuid=uuid,
            phase="callback", status="success",
            response_json={"idempotent": True, "current_status": task.status},
        )
        return {"message": "already processed", "task_status": task.status}

    # 7. 更新 external_task_id（若回调中携带）
    if external_task_id and not task.external_task_id:
        task.external_task_id = external_task_id
        db.commit()

    # 7.5 success 回调但 content 为空：提前降级 local，避免 finalize 失败后再降级
    if cb_status == "success" and not (content or "").strip():
        logger.warning(f"[webhook] success 回调 content 为空，直接降级 local: uuid={uuid}")
        log_call(
            db, agent_task_id=task.id, module_id=module_id, uuid=uuid,
            phase="callback", status="failed",
            error_msg="外部返回 content 为空，自动降级 local",
        )
        from app.tasks.workflow_tasks import _fallback_to_local
        _fallback_to_local(db, task, "外部返回 content 为空")
        return {"message": "empty content, fallback to local", "task_id": task.id}

    # 8. 记录 callback 日志
    log_call(
        db, agent_task_id=task.id, module_id=module_id, uuid=uuid,
        phase="callback",
        status="success" if cb_status == "success" else "failed",
        response_json={
            "content_len": len(content) if content else 0,
            "error": error[:500] if error else None,
        },
        external_task_id=external_task_id,
        error_msg=error[:2000] if error else None,
    )

    # 9. 快速应答 202 + 派发回调处理任务（不阻塞外部平台）
    response.status_code = status.HTTP_202_ACCEPTED
    dispatch_task(handle_workflow_callback_task, task.id, content, cb_status)

    logger.info(
        f"[webhook] 收到回调 uuid={uuid} status={cb_status}，已派发处理任务 task_id={task.id}"
    )
    return {"message": "accepted", "task_id": task.id}
