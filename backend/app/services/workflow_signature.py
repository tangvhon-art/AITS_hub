"""
Webhook 回调签名工具

HMAC-SHA256 签名：外部平台回调 AITS 固定 Webhook 时，
对请求 body 用 secret 做 HMAC-SHA256，放入 X-Aits-Signature 头；
AITS 侧校验通过才处理（防伪造与重放）。

v0.7 确认 #4：支持携带签名回调。
"""
import hashlib
import hmac


def compute_signature(secret: str, body: bytes) -> str:
    """用 secret 对原始 body 字节计算 HMAC-SHA256，返回十六进制摘要"""
    if not secret:
        return ""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def verify_signature(secret: str, body: bytes, signature: str) -> bool:
    """校验签名：constant-time 比较，防时序攻击；secret 为空或签名缺失时拒绝"""
    if not secret or not signature:
        return False
    expected = compute_signature(secret, body)
    if not expected:
        return False
    return hmac.compare_digest(expected, signature)
