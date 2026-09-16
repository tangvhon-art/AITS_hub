"""
钉钉自定义机器人客户端

支持：
- 加签验签（HMAC-SHA256 + base64 + urlencode）
- 发送 actionCard 卡片消息
- 发送 markdown 消息
- 发送纯文本消息（测试用）
- httpx 同步请求，超时 10 秒

文档：
- 发送消息：https://open.dingtalk.com/document/development/custom-robots-send-group-messages
- 安全设置：https://open.dingtalk.com/document/dingstart/customize-robot-security-settings
"""
import base64
import hashlib
import hmac
import logging
import time
import urllib.parse
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class DingTalkBotClient:
    """钉钉机器人客户端"""

    def __init__(self, webhook_url: str, secret: Optional[str] = None, sign_enabled: bool = False):
        self.webhook_url = webhook_url
        self.secret = secret or ""
        self.sign_enabled = sign_enabled

    @staticmethod
    def gen_sign(timestamp: int, secret: str) -> str:
        """
        生成钉钉机器人加签

        算法：
        1. string_to_sign = f"{timestamp}\n{secret}"
        2. hmac_code = HMAC-SHA256(key=secret.encode(), msg=string_to_sign.encode()).digest()
        3. sign = urlencode(base64.b64encode(hmac_code))
        """
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = base64.b64encode(hmac_code).decode("utf-8")
        return urllib.parse.quote_plus(sign)

    def _build_url(self) -> str:
        """构建带签名的 webhook URL"""
        if not (self.sign_enabled and self.secret):
            return self.webhook_url
        timestamp = int(time.time() * 1000)
        sign = self.gen_sign(timestamp, self.secret)
        separator = "&" if "?" in self.webhook_url else "?"
        return f"{self.webhook_url}{separator}timestamp={timestamp}&sign={sign}"

    def send_action_card(self, title: str, text: str, button_title: str = "查看详情",
                         button_url: str = "", btn_orientation: str = "0") -> Dict[str, Any]:
        """
        发送 actionCard 卡片消息

        Args:
            title: 卡片标题
            text: markdown 格式正文
            button_title: 按钮文字
            button_url: 按钮跳转链接
            btn_orientation: 按钮排列方向，0-竖直，1-横向
        """
        payload: Dict[str, Any] = {
            "msgtype": "actionCard",
            "actionCard": {
                "title": title,
                "text": text,
                "btnOrientation": btn_orientation,
            },
        }
        if button_url:
            payload["actionCard"]["singleTitle"] = button_title
            payload["actionCard"]["singleURL"] = button_url
        return self._post(payload)

    def send_markdown(self, title: str, text: str) -> Dict[str, Any]:
        """发送 markdown 消息"""
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": text,
            },
        }
        return self._post(payload)

    def send_text(self, text: str) -> Dict[str, Any]:
        """发送纯文本消息（测试用）"""
        payload = {
            "msgtype": "text",
            "text": {"content": text},
        }
        return self._post(payload)

    def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """同步 POST 请求"""
        result: Dict[str, Any] = {
            "success": False,
            "status_code": None,
            "response": None,
            "error": None,
        }
        url = self._build_url()
        try:
            with httpx.Client(timeout=10) as client:
                response = client.post(url, json=payload)
                result["status_code"] = response.status_code
                try:
                    result["response"] = response.json()
                except Exception:
                    result["response"] = response.text

                if response.status_code == 200:
                    resp_data = result["response"]
                    # 钉钉成功返回 {"errcode": 0, "errmsg": "ok"}
                    if isinstance(resp_data, dict):
                        errcode = resp_data.get("errcode")
                        if errcode == 0:
                            result["success"] = True
                        else:
                            result["error"] = resp_data.get("errmsg") or str(resp_data)
                    else:
                        result["success"] = True
                else:
                    result["error"] = f"HTTP {response.status_code}"
        except httpx.TimeoutException:
            result["error"] = "请求超时（10秒）"
            logger.warning(f"钉钉机器人请求超时: {self.webhook_url[:50]}...")
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"钉钉机器人发送失败: {e}")
        return result
