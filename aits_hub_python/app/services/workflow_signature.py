"""
Webhook 回调签名工具

HMAC-SHA256 签名：外部平台回调 AITS 固定 Webhook 时，
对请求 body 用 secret 做 HMAC-SHA256，放入 X-Aits-Signature 头；
AITS 侧校验通过才处理（防伪造与重放）。

支持两种签名模式（向后兼容）：
1. 简单模式：signature = HMAC-SHA256(secret, body)
2. 时间戳模式：signature = HMAC-SHA256(secret, body + timestamp)，
   同时在 X-Aits-Timestamp 头携带时间戳，校验时检查时间戳在有效窗口内（防重放）

v0.7 确认 #4：支持携带签名回调。
"""
import hashlib
import hmac
import time

# 时间戳有效窗口（秒）：超过此时间的回调视为重放攻击
TIMESTAMP_VALID_WINDOW = 300  # 5 分钟


def compute_signature(secret: str, body: bytes, timestamp: str = "") -> str:
    """用 secret 对原始 body 字节计算 HMAC-SHA256，返回十六进制摘要

    Args:
        secret: 签名密钥
        body: 请求体原始字节
        timestamp: 可选时间戳字符串，非空时参与签名计算（防重放）
    """
    if not secret:
        return ""
    sign_body = body + timestamp.encode("utf-8") if timestamp else body
    return hmac.new(secret.encode("utf-8"), sign_body, hashlib.sha256).hexdigest()


def verify_signature(secret: str, body: bytes, signature: str, timestamp: str = "") -> bool:
    """校验签名：constant-time 比较，防时序攻击；secret 为空或签名缺失时拒绝

    Args:
        secret: 签名密钥
        body: 请求体原始字节
        signature: 待校验的签名
        timestamp: 可选时间戳字符串，非空时检查时间戳有效性（防重放）
    """
    if not secret or not signature:
        return False

    # 时间戳模式：检查时间戳有效性
    if timestamp:
        try:
            ts = int(timestamp)
            now = int(time.time())
            if abs(now - ts) > TIMESTAMP_VALID_WINDOW:
                return False  # 时间戳超出有效窗口，可能是重放攻击
        except (ValueError, TypeError):
            return False  # 时间戳格式非法

    expected = compute_signature(secret, body, timestamp)
    if not expected:
        return False
    return hmac.compare_digest(expected, signature)
