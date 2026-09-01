"""
外部工作流平台连接器

职责：按连接配置调用外部平台 agent，携带 uuid + input + callback_url；
      接收受理响应（立即返回 task_id，不等待结果）。

v0.7 确认 #1：无需外部平台原生支持异步受理 API；AITS 发起 HTTP 调用，
外部受理即返回 task_id，AITS 保存后任务挂起等待 Webhook 回调。
"""
import logging
from typing import Optional, Dict, Any

import httpx

from app.models.workflow import WorkflowPlatformConnector
from app.agents.llm_factory import decrypt_api_key

logger = logging.getLogger(__name__)


class WorkflowInvokeError(Exception):
    """外部平台调用/受理失败"""


def _build_headers(connector: WorkflowPlatformConnector) -> Dict[str, str]:
    """按 auth_type 注入鉴权 Header（auth_token 已解密）"""
    headers = {"Content-Type": "application/json"}
    token = decrypt_api_key(connector.auth_token) if connector.auth_token else ""
    header_name = connector.auth_header or "Authorization"
    if not token:
        return headers
    if connector.auth_type == "bearer":
        headers[header_name] = f"Bearer {token}"
    elif connector.auth_type == "apikey":
        headers[header_name] = token
    else:  # custom：原样放入指定 Header
        headers[header_name] = token
    return headers


def _build_payload(connector: WorkflowPlatformConnector,
                   uuid: str,
                   input_payload: Dict[str, Any],
                   callback_url: str) -> Dict[str, Any]:
    """构造统一请求体：{uuid, input, callback_url, response_mode:async}"""
    return {
        "uuid": uuid,
        "input": input_payload,
        "callback_url": callback_url,
        "response_mode": "async",
    }


def _parse_accept_response(resp_json: Dict[str, Any]) -> Dict[str, Any]:
    """从受理响应解析 task_id 与状态（兼容多种字段命名）"""
    task_id = (
        resp_json.get("task_id")
        or resp_json.get("id")
        or resp_json.get("workflow_id")
        or resp_json.get("run_id")
    )
    status = (
        resp_json.get("status")
        or ("accepted" if task_id else "unknown")
    )
    return {"task_id": str(task_id) if task_id is not None else None, "status": status}


def invoke(
    connector: WorkflowPlatformConnector,
    uuid: str,
    input_payload: Dict[str, Any],
    callback_url: str,
    max_retries: int = 2,
) -> Dict[str, Any]:
    """同步发起调用并等待受理响应（不等待 agent 执行完成）

    对瞬时网络错误和 5xx 服务端错误进行指数退避重试（默认2次），
    4xx 客户端错误不重试（通常是配置问题，重试无意义）。

    Returns:
        {"task_id": "...", "status": "accepted", "raw": {...}}
    Raises:
        WorkflowInvokeError: 调用失败或受理未返回 task_id
    """
    import time

    url = connector.base_url.rstrip("/") + (connector.run_path or "/v1/workflows/run")
    headers = _build_headers(connector)
    payload = _build_payload(connector, uuid, input_payload, callback_url)
    timeout = connector.accept_timeout or 30

    logger.info(
        f"[workflow] 调用外部平台: connector={connector.name}, url={url}, "
        f"uuid={uuid}, platform_type={connector.platform_type}"
    )

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as e:
            last_error = f"调用外部平台网络失败: {e}"
            if attempt < max_retries:
                wait = 2 ** attempt
                logger.warning(f"[workflow] 第{attempt + 1}次调用网络失败，{wait}s后重试: {e}")
                time.sleep(wait)
                continue
            raise WorkflowInvokeError(last_error)

        # 5xx 服务端错误重试；4xx 客户端错误不重试
        if resp.status_code >= 500 and attempt < max_retries:
            wait = 2 ** attempt
            logger.warning(
                f"[workflow] 第{attempt + 1}次调用返回 HTTP {resp.status_code}，"
                f"{wait}s后重试: {resp.text[:200]}"
            )
            time.sleep(wait)
            continue

        if resp.status_code >= 400:
            raise WorkflowInvokeError(
                f"外部平台受理 HTTP {resp.status_code}: {resp.text[:500]}"
            )

        try:
            resp_json = resp.json()
        except Exception:
            raise WorkflowInvokeError(f"外部平台受理响应非 JSON: {resp.text[:300]}")

        parsed = _parse_accept_response(resp_json)
        if not parsed["task_id"]:
            raise WorkflowInvokeError(f"外部平台未返回 task_id: {resp_json}")
        parsed["raw"] = resp_json
        if attempt > 0:
            logger.info(f"[workflow] 第{attempt + 1}次重试成功: uuid={uuid}")
        return parsed

    # 理论上不会走到这里（循环内要么 return 要么 raise），兜底 raise
    raise WorkflowInvokeError(last_error or "调用外部平台失败")
