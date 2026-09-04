"""
加解密工具（5 个）：MD5 / SHA 系列 / HMAC 签名 / AES 加密 / AES 解密
基于 cryptography 库；密钥/IV 支持随机生成或用户指定（Base64 传输）
"""
import base64
import binascii
import hashlib
import hmac as hmac_mod
import secrets

from app.services.data_tools.base import data_tool, InvalidParamError, ParseError

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding as sym_padding
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

_AES_MODES = ["cbc", "ecb", "gcm"]
_SHA_ALGOS = {"sha256": hashlib.sha256, "sha1": hashlib.sha1, "sha512": hashlib.sha512,
              "sha224": hashlib.sha224, "sha384": hashlib.sha384}
# HMAC 支持的摘要算法（含 MD5）
_HMAC_ALGOS = {"md5": hashlib.md5, "sha1": hashlib.sha1, "sha256": hashlib.sha256,
               "sha512": hashlib.sha512, "sha224": hashlib.sha224, "sha384": hashlib.sha384}


def _b64decode_field(field: str, value: str) -> bytes:
    if not value:
        raise InvalidParamError(field, f"{field} 不能为空")
    try:
        return base64.b64decode(str(value).strip())
    except (binascii.Error, ValueError):
        raise InvalidParamError(field, f"{field} 需为 Base64 编码的字节串")


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _pkcs7_pad(data: bytes, block_size: int = 16) -> bytes:
    padder = sym_padding.PKCS7(block_size * 8).padder()
    return padder.update(data) + padder.finalize()


def _pkcs7_unpad(data: bytes, block_size: int = 16) -> bytes:
    unpadder = sym_padding.PKCS7(block_size * 8).unpadder()
    return unpadder.update(data) + unpadder.finalize()


def _normalize_key_length(key_length: int) -> int:
    try:
        k = int(key_length)
    except (TypeError, ValueError):
        raise InvalidParamError("key_length", "密钥长度需为 16/24/32")
    if k not in (16, 24, 32):
        raise InvalidParamError("key_length", "密钥长度需为 16/24/32（对应 AES-128/192/256）")
    return k


@data_tool(
    name="md5_hash", title="MD5", category="crypto",
    description="计算 MD5 摘要（32 位/16 位，可大写）",
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "title": "待计算文本", "description": "待计算文本", "x-multiline": True},
            "format": {"type": "string", "title": "输出格式", "enum": ["32", "16"], "x-enum-labels": ["32 位完整", "16 位"],
                       "description": "32 位完整 / 16 位（摘要中间16位），默认 32 位"},
            "uppercase": {"type": "boolean", "title": "大写输出", "description": "是否大写输出"},
        },
        "required": ["text"],
    },
    is_generator=False,
)
def md5_hash(text: str, format: str = "32", uppercase: bool = False) -> dict:
    digest = hashlib.md5((text or "").encode("utf-8")).hexdigest()
    if format == "16":
        digest = digest[8:24]
    if uppercase:
        digest = digest.upper()
    return {"result": digest}


@data_tool(
    name="sha_hash", title="SHA 摘要", category="crypto",
    description="SHA256 / SHA1 / SHA512 摘要，支持 HMAC 模式",
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "title": "待计算文本", "description": "待计算文本", "x-multiline": True},
            "algorithm": {"type": "string", "title": "摘要算法", "enum": ["sha256", "sha1", "sha512", "sha224", "sha384"],
                          "x-enum-labels": ["SHA256", "SHA1", "SHA512", "SHA224", "SHA384"],
                          "description": "摘要算法，默认 SHA256"},
            "key": {"type": "string", "title": "HMAC 密钥", "description": "HMAC 密钥（可选，填写后使用 HMAC 模式）"},
        },
        "required": ["text"],
    },
    is_generator=False,
)
def sha_hash(text: str, algorithm: str = "sha256", key: str = None) -> dict:
    algo = _SHA_ALGOS.get(algorithm)
    if not algo:
        raise InvalidParamError("algorithm", f"不支持的算法: {algorithm}")
    raw = (text or "").encode("utf-8")
    if key:
        digest = hmac_mod.new(str(key).encode("utf-8"), raw, algo).hexdigest()
    else:
        digest = algo(raw).hexdigest()
    return {"result": digest, "algorithm": algorithm, "hmac": bool(key)}


def _aes_crypt(action: str, text: str, key_b64: str, mode: str, iv_b64: str,
               key_length: int, tag_b64: str = None) -> dict:
    if not HAS_CRYPTO:
        raise ParseError("AES 依赖 cryptography 库未安装")
    mode = (mode or "cbc").lower()
    if mode not in _AES_MODES:
        raise InvalidParamError("mode", f"AES 模式仅支持 {_AES_MODES}")
    kl = _normalize_key_length(key_length)

    # 密钥处理
    if key_b64:
        key = _b64decode_field("key", key_b64)
        if len(key) not in (16, 24, 32):
            raise InvalidParamError("key", "密钥解码后长度需为 16/24/32 字节")
        kl = len(key)
    else:
        if action == "decrypt":
            raise InvalidParamError("key", "解密必须提供密钥")
        key = secrets.token_bytes(kl)

    # IV 处理（ECB 不需要）
    iv = None
    if mode != "ecb":
        if iv_b64:
            iv = _b64decode_field("iv", iv_b64)
            if len(iv) != 16:
                raise InvalidParamError("iv", "IV 解码后长度需为 16 字节")
        else:
            if action == "decrypt":
                raise InvalidParamError("iv", f"{mode.upper()} 模式解密必须提供 IV")
            iv = secrets.token_bytes(16)

    try:
        if action == "encrypt":
            data = (text or "").encode("utf-8")
            if mode == "cbc":
                cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
                enc = cipher.encryptor()
                ct = enc.update(_pkcs7_pad(data)) + enc.finalize()
                return {"ciphertext": _b64encode(ct), "key": _b64encode(key), "iv": _b64encode(iv),
                        "mode": mode.upper(), "key_length": kl}
            if mode == "ecb":
                cipher = Cipher(algorithms.AES(key), modes.ECB())
                enc = cipher.encryptor()
                ct = enc.update(_pkcs7_pad(data)) + enc.finalize()
                return {"ciphertext": _b64encode(ct), "key": _b64encode(key),
                        "mode": mode.upper(), "key_length": kl}
            # gcm
            cipher = Cipher(algorithms.AES(key), modes.GCM(iv))
            enc = cipher.encryptor()
            ct = enc.update(data) + enc.finalize()
            return {"ciphertext": _b64encode(ct), "tag": _b64encode(enc.tag),
                    "key": _b64encode(key), "iv": _b64encode(iv),
                    "mode": mode.upper(), "key_length": kl}

        # decrypt
        ct = _b64decode_field("ciphertext", text)
        if mode == "gcm":
            tag = _b64decode_field("tag", tag_b64) if tag_b64 else None
            if not tag:
                raise InvalidParamError("tag", "GCM 模式解密必须提供 tag")
            try:
                cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag))
                dec = cipher.decryptor()
                return {"plaintext": (dec.update(ct) + dec.finalize()).decode("utf-8")}
            except Exception as e:  # noqa: BLE001
                raise ParseError(f"AES-GCM 解密失败（tag 校验未通过或密钥/IV 不匹配）: {e}")
        if mode == "cbc":
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
            dec = cipher.decryptor()
            padded = dec.update(ct) + dec.finalize()
            try:
                return {"plaintext": _pkcs7_unpad(padded).decode("utf-8")}
            except Exception as e:  # noqa: BLE001
                raise ParseError(f"AES-CBC 解密失败（密钥/IV 不匹配或密文损坏）: {e}")
        cipher = Cipher(algorithms.AES(key), modes.ECB())
        dec = cipher.decryptor()
        padded = dec.update(ct) + dec.finalize()
        try:
            return {"plaintext": _pkcs7_unpad(padded).decode("utf-8")}
        except Exception as e:  # noqa: BLE001
            raise ParseError(f"AES-ECB 解密失败（密钥不匹配或密文损坏）: {e}")
    except ParseError:
        raise
    except InvalidParamError:
        raise
    except Exception as e:  # noqa: BLE001
        raise ParseError(f"AES 操作失败: {e}")


@data_tool(
    name="hmac_sign", title="HMAC 签名", category="crypto",
    description="HMAC 签名（密钥 + MD5/SHA1/SHA256/SHA512 等算法）",
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "title": "待签名文本", "description": "待签名文本", "x-multiline": True},
            "key": {"type": "string", "title": "密钥", "description": "HMAC 密钥（必填）"},
            "algorithm": {"type": "string", "title": "签名算法", "enum": ["md5", "sha1", "sha256", "sha512", "sha224", "sha384"],
                          "x-enum-labels": ["MD5", "SHA1", "SHA256", "SHA512", "SHA224", "SHA384"],
                          "description": "HMAC 签名算法，默认 SHA256"},
            "uppercase": {"type": "boolean", "title": "大写输出", "description": "是否大写输出"},
        },
        "required": ["text", "key"],
    },
    is_generator=False,
)
def hmac_sign(text: str, key: str, algorithm: str = "sha256", uppercase: bool = False) -> dict:
    algo = _HMAC_ALGOS.get(str(algorithm).lower())
    if not algo:
        raise InvalidParamError("algorithm", f"不支持的 HMAC 算法: {algorithm}")
    if not key:
        raise InvalidParamError("key", "HMAC 密钥不能为空")
    digest = hmac_mod.new(str(key).encode("utf-8"), (text or "").encode("utf-8"), algo).hexdigest()
    if uppercase:
        digest = digest.upper()
    return {"result": digest, "algorithm": str(algorithm).lower(), "key": str(key)}


@data_tool(
    name="aes_encrypt", title="AES 加密", category="crypto",
    description="AES 对称加密（CBC/ECB/GCM），密钥/IV 可随机生成",
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "title": "待加密明文", "description": "待加密明文", "x-multiline": True},
            "key": {"type": "string", "title": "密钥", "description": "密钥（Base64，16/24/32字节），留空自动生成并随结果返回"},
            "mode": {"type": "string", "title": "加密模式", "enum": ["cbc", "ecb", "gcm"],
                     "x-enum-labels": ["CBC", "ECB", "GCM"], "description": "加密模式，默认 CBC"},
            "iv": {"type": "string", "title": "IV", "description": "IV（Base64，16字节，CBC/GCM 必填或自动生成）"},
            "key_length": {"type": "integer", "title": "密钥长度", "enum": [16, 24, 32],
                           "x-enum-labels": ["AES-128（16）", "AES-192（24）", "AES-256（32）"],
                           "description": "自动生成密钥的长度：AES-128 / AES-192 / AES-256，默认 AES-128"},
        },
        "required": ["text"],
    },
    is_generator=False,
)
def aes_encrypt(text: str, key: str = None, mode: str = "cbc", iv: str = None, key_length: int = 16) -> dict:
    return _aes_crypt("encrypt", text, key, mode, iv, key_length)


@data_tool(
    name="aes_decrypt", title="AES 解密", category="crypto",
    description="对应 AES 解密，参数需与加密时严格匹配",
    parameters={
        "type": "object",
        "properties": {
            "ciphertext": {"type": "string", "title": "密文", "description": "密文（Base64）"},
            "key": {"type": "string", "title": "密钥", "description": "密钥（Base64）"},
            "mode": {"type": "string", "title": "解密模式", "enum": ["cbc", "ecb", "gcm"],
                     "x-enum-labels": ["CBC", "ECB", "GCM"], "description": "解密模式，默认 CBC"},
            "iv": {"type": "string", "title": "IV", "description": "IV（Base64，CBC/GCM 必填）"},
            "tag": {"type": "string", "title": "GCM 认证标签", "description": "GCM 认证标签（Base64，GCM 模式必填）"},
        },
        "required": ["ciphertext", "key"],
    },
    is_generator=False,
)
def aes_decrypt(ciphertext: str, key: str, mode: str = "cbc", iv: str = None, tag: str = None) -> dict:
    return _aes_crypt("decrypt", ciphertext, key, mode, iv, 16, tag)
