"""
通知 Agent

支持邮件发送（SMTP）和飞书 Webhook 消息。
飞书发送逻辑已统一收敛到 app.services.feishu_bot.FeishuBotClient，本 Agent 仅做适配调用。
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List, Optional

from app.agents.base_agent import BaseAgent
from app.config import settings
from app.services.feishu_bot import FeishuBotClient

logger = logging.getLogger(__name__)


class NotificationAgent(BaseAgent):
    """通知 Agent"""

    agent_type = "notification"

    def __init__(self, db_session, llm_config_id: Optional[int] = None, task_id: Optional[int] = None):
        super().__init__(db_session, llm_config_id, task_id)

    def send(
        self,
        title: str,
        content: str,
        channels: List[str] = None,
        email_to: List[str] = None,
        feishu_webhook: str = "",
        feishu_secret: str = None,
        feishu_sign_enabled: bool = False,
    ) -> Dict[str, Any]:
        """
        发送通知

        Args:
            title: 通知标题
            content: 通知内容
            channels: 通知渠道 ["email", "feishu"]
            email_to: 邮件收件人列表
            feishu_webhook: 飞书 Webhook URL
            feishu_secret: 飞书签名密钥（明文）
            feishu_sign_enabled: 是否启用飞书签名校验

        Returns:
            发送结果
        """
        import time
        self.start_time = time.time()
        channels = channels or ["email"]
        results = {}

        if "email" in channels and email_to:
            results["email"] = self._send_email(title, content, email_to)

        if "feishu" in channels and feishu_webhook:
            results["feishu"] = self._send_feishu(
                title, content, feishu_webhook,
                secret=feishu_secret, sign_enabled=feishu_sign_enabled,
            )

        return {
            "title": title,
            "channels": channels,
            "results": results,
            "success": all(r.get("success", False) for r in results.values()) if results else False,
        }

    def _send_email(self, title: str, content: str, to_list: List[str]) -> Dict[str, Any]:
        """发送邮件"""
        try:
            msg = MIMEMultipart()
            msg["Subject"] = title
            msg["From"] = settings.SMTP_FROM or "aits@example.com"
            msg["To"] = ", ".join(to_list)

            # 支持 HTML 内容
            if content.strip().startswith("<"):
                msg.attach(MIMEText(content, "html", "utf-8"))
            else:
                msg.attach(MIMEText(content, "plain", "utf-8"))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if settings.SMTP_USER:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(msg["From"], to_list, msg.as_string())

            self._log_step("email_sent", {"to": to_list}, "success")
            return {"success": True, "message": "邮件发送成功"}

        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            self._log_step("email_error", {"error": str(e)}, "failed")
            return {"success": False, "message": str(e)}

    def _send_feishu(
        self,
        title: str,
        content: str,
        webhook: str,
        secret: Optional[str] = None,
        sign_enabled: bool = False,
    ) -> Dict[str, Any]:
        """发送飞书 Webhook 消息（复用 FeishuBotClient）"""
        try:
            client = FeishuBotClient(
                webhook_url=webhook,
                secret=secret,
                sign_enabled=sign_enabled,
            )

            # 构建简单卡片（保持与旧逻辑兼容的标题+正文结构）
            card = {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": "blue",
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": content,
                    }
                ],
            }

            result = client.send_card(card)

            if result.get("success"):
                self._log_step("feishu_sent", {}, "success")
                return {"success": True, "message": "飞书消息发送成功"}
            else:
                self._log_step("feishu_error", {"error": result.get("error")}, "failed")
                return {"success": False, "message": result.get("error") or "发送失败"}

        except Exception as e:
            logger.error(f"飞书消息发送失败: {e}")
            self._log_step("feishu_error", {"error": str(e)}, "failed")
            return {"success": False, "message": str(e)}

    def run(self, **kwargs) -> Dict[str, Any]:
        """BaseAgent 接口实现"""
        return self.send(
            title=kwargs.get("title", ""),
            content=kwargs.get("content", ""),
            channels=kwargs.get("channels"),
            email_to=kwargs.get("email_to"),
            feishu_webhook=kwargs.get("feishu_webhook", ""),
            feishu_secret=kwargs.get("feishu_secret"),
            feishu_sign_enabled=kwargs.get("feishu_sign_enabled", False),
        )
