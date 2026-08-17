"""
飞书自定义机器人客户端

支持：
- HMAC-SHA256 签名校验
- 发送消息卡片（interactive card）
- 发送纯文本消息（测试用）
- httpx 同步请求，超时 10 秒
"""
import base64
import hashlib
import hmac
import logging
import time
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class FeishuBotClient:
    """飞书机器人客户端"""

    def __init__(self, webhook_url: str, secret: Optional[str] = None, sign_enabled: bool = False):
        self.webhook_url = webhook_url
        self.secret = secret or ""
        self.sign_enabled = sign_enabled

    @staticmethod
    def gen_sign(timestamp: int, secret: str) -> str:
        """
        生成飞书机器人签名（HMAC-SHA256）

        算法：HMAC-SHA256(key=string_to_sign, msg=b'')，其中 string_to_sign = f"{timestamp}\n{secret}"
        """
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        return base64.b64encode(hmac_code).decode("utf-8")

    def _build_payload(self, msg_type: str, **kwargs) -> Dict[str, Any]:
        """构建请求 payload，按需附加签名"""
        payload: Dict[str, Any] = {"msg_type": msg_type}
        payload.update(kwargs)
        if self.sign_enabled and self.secret:
            timestamp = int(time.time())
            payload["timestamp"] = str(timestamp)
            payload["sign"] = self.gen_sign(timestamp, self.secret)
        return payload

    def send_card(self, card: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送消息卡片

        Returns:
            {"success": bool, "status_code": int|None, "response": dict|str|None, "error": str|None}
        """
        payload = self._build_payload("interactive", card=card)
        return self._post(payload)

    def send_text(self, text: str) -> Dict[str, Any]:
        """发送纯文本消息（测试用）"""
        payload = self._build_payload("text", content={"text": text})
        return self._post(payload)

    def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """同步 POST 请求"""
        result: Dict[str, Any] = {
            "success": False,
            "status_code": None,
            "response": None,
            "error": None,
        }
        try:
            with httpx.Client(timeout=10) as client:
                response = client.post(self.webhook_url, json=payload)
                result["status_code"] = response.status_code
                try:
                    result["response"] = response.json()
                except Exception:
                    result["response"] = response.text

                if response.status_code == 200:
                    resp_data = result["response"]
                    # 飞书成功返回 {"code": 0, ...} 或 {"StatusCode": 0, ...}
                    if isinstance(resp_data, dict):
                        code = resp_data.get("code", resp_data.get("StatusCode"))
                        if code == 0:
                            result["success"] = True
                        else:
                            result["error"] = resp_data.get("msg") or resp_data.get("StatusMessage") or str(resp_data)
                    else:
                        result["success"] = True
                else:
                    result["error"] = f"HTTP {response.status_code}"
        except httpx.TimeoutException:
            result["error"] = "请求超时（10秒）"
            logger.warning(f"飞书机器人请求超时: {self.webhook_url[:50]}...")
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"飞书机器人发送失败: {e}")
        return result
