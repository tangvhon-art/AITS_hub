"""
通知异步发送任务

核心逻辑抽取为 _send_notification_sync，供 Celery 任务与线程降级共用。
发送失败自动重试 2 次（间隔 10s、30s）。
"""
import json
import logging
import time
from typing import Any, Dict

from app.celery_app import celery_app
from app.core.timezone import china_now_naive
from app.database import SessionLocal
from app.models.notification import NotificationChannel, NotificationRecord

logger = logging.getLogger(__name__)

# 重试间隔（秒）：第1次失败后等10s，第2次失败后等30s
RETRY_DELAYS = [10, 30]
MAX_ATTEMPTS = 3  # 首次 + 2次重试


def _do_send(channel: NotificationChannel, card: Dict[str, Any]) -> Dict[str, Any]:
    """执行实际的飞书发送"""
    from app.agents.llm_factory import decrypt_api_key
    from app.services.feishu_bot import FeishuBotClient

    secret = decrypt_api_key(channel.secret) if channel.secret else None
    client = FeishuBotClient(
        webhook_url=channel.webhook_url,
        secret=secret,
        sign_enabled=channel.sign_enabled,
    )
    return client.send_card(card)


def _send_notification_sync(record_id: int):
    """
    发送通知的核心同步逻辑（含重试）。

    - 查询记录与渠道
    - 解析卡片 JSON
    - 最多尝试 3 次（首次 + 2次重试，间隔 10s/30s）
    - 更新记录状态、响应码、响应体、错误信息、重试次数、发送时间
    """
    db = SessionLocal()
    try:
        record = db.query(NotificationRecord).filter(NotificationRecord.id == record_id).first()
        if not record:
            logger.error(f"通知记录不存在: {record_id}")
            return

        channel = db.query(NotificationChannel).filter(
            NotificationChannel.id == record.channel_id
        ).first()
        if not channel:
            record.status = "failed"
            record.error_message = "通知渠道不存在或已删除"
            record.sent_at = china_now_naive()
            db.commit()
            return

        if not channel.enabled:
            record.status = "failed"
            record.error_message = "通知渠道已禁用"
            record.sent_at = china_now_naive()
            db.commit()
            return

        # 解析卡片内容
        try:
            card = json.loads(record.content) if record.content else {}
        except (json.JSONDecodeError, TypeError):
            record.status = "failed"
            record.error_message = "卡片内容解析失败"
            record.sent_at = china_now_naive()
            db.commit()
            return

        # 标记为发送中
        record.status = "pending"
        db.commit()

        last_error = ""
        last_status_code = None
        last_response = None

        for attempt in range(MAX_ATTEMPTS):
            try:
                result = _do_send(channel, card)
                last_status_code = result.get("status_code")
                last_response = result.get("response")

                if result.get("success"):
                    record.status = "success"
                    record.response_code = last_status_code
                    record.response_body = json.dumps(last_response, ensure_ascii=False) if last_response is not None else None
                    record.error_message = None
                    record.retry_count = attempt
                    record.sent_at = china_now_naive()
                    db.commit()
                    logger.info(f"通知发送成功: record_id={record_id}, attempt={attempt + 1}")
                    return
                else:
                    last_error = result.get("error") or "发送失败"
                    logger.warning(
                        f"通知发送失败（第{attempt + 1}次）: record_id={record_id}, error={last_error}"
                    )
            except Exception as e:
                last_error = str(e)
                logger.exception(f"通知发送异常（第{attempt + 1}次）: record_id={record_id}, error={e}")

            # 还有重试机会则等待
            if attempt < len(RETRY_DELAYS):
                record.retry_count = attempt + 1
                db.commit()
                time.sleep(RETRY_DELAYS[attempt])

        # 全部重试失败
        record.status = "failed"
        record.response_code = last_status_code
        record.response_body = json.dumps(last_response, ensure_ascii=False) if last_response is not None else None
        record.error_message = last_error[:500] if last_error else "发送失败"
        record.sent_at = china_now_naive()
        db.commit()
        logger.error(f"通知最终发送失败: record_id={record_id}, error={last_error}")

    except Exception as e:
        logger.exception(f"通知任务执行异常: record_id={record_id}, error={e}")
        try:
            db.rollback()
            record = db.query(NotificationRecord).filter(NotificationRecord.id == record_id).first()
            if record and record.status == "pending":
                record.status = "failed"
                record.error_message = f"任务异常: {str(e)[:400]}"
                record.sent_at = china_now_naive()
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@celery_app.task(bind=True, name="send_notification")
def send_notification_task(self, record_id: int):
    """Celery 任务入口：异步发送通知"""
    _send_notification_sync(record_id)
