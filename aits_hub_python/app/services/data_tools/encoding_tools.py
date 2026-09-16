"""
编码工具（6 个）：二维码 / 条形码 / 时间戳转换 / JWT 解码 / Base64↔图片 / Base64 编码
"""
import base64
import binascii
import io
import json
import re
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from app.services.data_tools.base import data_tool, InvalidParamError, ParseError

try:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q, ERROR_CORRECT_H
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

try:
    import barcode
    from barcode.writer import SVGWriter, ImageWriter
    HAS_BARCODE = True
except ImportError:
    HAS_BARCODE = False

try:
    from PIL import Image, UnidentifiedImageError
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

_QR_EC_MAP = {"L": ERROR_CORRECT_L, "M": ERROR_CORRECT_M, "Q": ERROR_CORRECT_Q, "H": ERROR_CORRECT_H}
MAX_B64_LEN = 8 * 1024 * 1024  # Base64 输入上限 8MB（约 6MB 解码后）


def _to_data_url(b64: str, mime: str) -> str:
    return f"data:{mime};base64,{b64}"


@data_tool(
    name="gen_qrcode", title="生成二维码", category="encoding",
    description="文本/链接生成二维码 PNG 图片（Base64 data URL）",
    parameters={
        "type": "object",
        "properties": {
            "content": {"type": "string", "title": "二维码内容", "description": "二维码内容（文本/URL）"},
            "size": {"type": "integer", "title": "图片边长", "description": "图片边长像素，默认256", "minimum": 64, "maximum": 1024},
            "error_correction": {"type": "string", "title": "纠错级别", "enum": ["L", "M", "Q", "H"],
                                 "x-enum-labels": ["L（7%）", "M（15%）", "Q（25%）", "H（30%）"],
                                 "description": "纠错级别：L / M / Q / H，默认 M"},
            "fg_color": {"type": "string", "title": "前景色", "description": "前景色（HEX，如 #000000）"},
            "bg_color": {"type": "string", "title": "背景色", "description": "背景色（HEX，如 #FFFFFF）"},
        },
        "required": ["content"],
    },
    is_generator=False,
)
def gen_qrcode(content: str, size: int = 256, error_correction: str = "M",
               fg_color: str = "#000000", bg_color: str = "#FFFFFF") -> dict:
    if not HAS_QRCODE:
        raise ParseError("二维码依赖 qrcode 库未安装")
    if not content:
        raise InvalidParamError("content", "内容不能为空")
    # 前端表单可能提交空字符串，归一为默认色
    fg_color = fg_color or "#000000"
    bg_color = bg_color or "#FFFFFF"
    qr = qrcode.QRCode(
        version=None,
        error_correction=_QR_EC_MAP.get(error_correction, ERROR_CORRECT_M),
        box_size=10,
        border=4,
    )
    qr.add_data(content)
    qr.make(fit=True)
    img = qr.make_image(fill_color=fg_color, back_color=bg_color)
    # 统一尺寸
    img = img.resize((int(size), int(size)))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return {"image_base64": b64, "mime": "image/png", "data_url": _to_data_url(b64, "image/png")}


@data_tool(
    name="gen_barcode", title="生成条形码", category="encoding",
    description="文本生成条形码（Code128/Code39/EAN13），返回 SVG 图片",
    parameters={
        "type": "object",
        "properties": {
            "content": {"type": "string", "title": "条形码内容", "description": "条形码内容（EAN13 需 12/13 位数字）"},
            "format": {"type": "string", "title": "条码格式", "enum": ["code128", "code39", "ean13", "ean8", "upca"],
                       "x-enum-labels": ["Code128", "Code39", "EAN13", "EAN8", "UPC-A"],
                       "description": "条码格式，默认 Code128"},
            "height": {"type": "integer", "title": "高度", "description": "高度 mm，默认 15", "minimum": 5, "maximum": 60},
        },
        "required": ["content"],
    },
    is_generator=False,
)
def gen_barcode(content: str, format: str = "code128", height: int = 15) -> dict:
    if not HAS_BARCODE:
        raise ParseError("条形码依赖 python-barcode 库未安装")
    if not content:
        raise InvalidParamError("content", "内容不能为空")
    try:
        if format == "ean13" and not re.fullmatch(r"\d{12}|\d{13}", content):
            raise InvalidParamError("content", "EAN13 需为 12 或 13 位数字")
        if format == "ean8" and not re.fullmatch(r"\d{7}|\d{8}", content):
            raise InvalidParamError("content", "EAN8 需为 7 或 8 位数字")
        if format == "upca" and not re.fullmatch(r"\d{11}|\d{12}", content):
            raise InvalidParamError("content", "UPC-A 需为 11 或 12 位数字")

        cls = barcode.get_barcode_class(format)
        writer = SVGWriter()
        gen = cls(content, writer=writer)
        buf = io.BytesIO()
        gen.write(buf, options={"height": int(height)})
        svg_text = buf.getvalue().decode("utf-8")
        b64 = base64.b64encode(svg_text.encode("utf-8")).decode("ascii")
        return {"image_base64": b64, "mime": "image/svg+xml",
                "data_url": _to_data_url(b64, "image/svg+xml")}
    except InvalidParamError:
        raise
    except Exception as e:  # noqa: BLE001
        raise ParseError(f"条形码生成失败: {e}")


@data_tool(
    name="timestamp_convert", title="时间戳转换", category="encoding",
    description="时间戳与日期时间互转，自动输出本地 / UTC / ISO 三种时区格式",
    parameters={
        "type": "object",
        "properties": {
            "value": {"type": "string", "title": "待转换值",
                      "description": "按输入类型自动匹配：时间戳转日期输入数字时间戳，日期转时间戳选择日期时间",
                      "x-widget-map": {
                          "depends": "from_type",
                          "timestamp": {"widget": "text", "placeholder": "输入时间戳（如 1756953000）"},
                          "datetime": {"widget": "datetime", "placeholder": "选择日期时间"},
                      }},
            "from_type": {"type": "string", "title": "输入类型", "enum": ["timestamp", "datetime"],
                          "x-enum-labels": ["时间戳 → 日期", "日期 → 时间戳"],
                          "description": "输入类型：时间戳转日期 / 日期转时间戳"},
            "unit": {"type": "string", "title": "时间戳单位", "enum": ["seconds", "milliseconds"],
                     "x-enum-labels": ["秒", "毫秒"],
                     "description": "时间戳单位（时间戳转日期时生效），默认秒"},
            "format": {"type": "string", "title": "日期格式", "description": "本地/UTC 日期格式（默认 %Y-%m-%d %H:%M:%S）"},
        },
        "required": ["value", "from_type"],
    },
    is_generator=False,
)
def timestamp_convert(value: str, from_type: str, unit: str = "seconds",
                      format: str = "%Y-%m-%d %H:%M:%S") -> dict:
    """时间戳 ⇄ 日期互转；自动按系统本地时区解析，输出 本地/UTC/ISO 三种格式"""
    fmt = format or "%Y-%m-%d %H:%M:%S"
    if from_type == "timestamp":
        try:
            num = float(str(value).strip())
        except ValueError:
            raise ParseError(f"时间戳需为数字: {value}")
        if unit == "milliseconds":
            num = num / 1000.0
        try:
            dt_local = datetime.fromtimestamp(num)          # 系统本地时区
            dt_utc = datetime.fromtimestamp(num, timezone.utc)
        except (OverflowError, OSError, ValueError):
            raise ParseError(f"时间戳超出支持范围: {value}")
        return {
            "local": dt_local.strftime(fmt),
            "utc": dt_utc.strftime(fmt),
            "iso": dt_local.astimezone().isoformat(),
            "timestamp": str(value).strip(),
            "unit": unit,
            "timezone": str(dt_local.astimezone().tzinfo or "Local"),
        }
    if from_type == "datetime":
        try:
            dt = datetime.strptime(str(value).strip(), fmt)
        except ValueError:
            raise ParseError(f"无法按格式 '{fmt}' 解析时间值: {value}")
        ts = dt.timestamp()
        seconds = int(ts)
        dt_utc = datetime.fromtimestamp(seconds, timezone.utc)
        return {
            "timestamp": seconds,
            "milliseconds": int(ts * 1000),
            "local": dt.strftime(fmt),
            "utc": dt_utc.strftime(fmt),
            "iso": dt.astimezone().isoformat(),
            "input": str(value).strip(),
            "timezone": str(dt.astimezone().tzinfo or "Local"),
        }
    raise InvalidParamError("from_type", "仅支持 timestamp / datetime")


@data_tool(
    name="jwt_decode", title="JWT 解码", category="encoding",
    description="解析 JWT 的 Header 与 Payload（仅解码，不验签）",
    parameters={
        "type": "object",
        "properties": {
            "token": {"type": "string", "title": "JWT Token", "description": "JWT Token（三段，用 . 分隔）"},
        },
        "required": ["token"],
    },
    is_generator=False,
)
def jwt_decode(token: str) -> dict:
    if not token or not isinstance(token, str):
        raise InvalidParamError("token", "Token 不能为空")
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise ParseError("JWT 格式错误：需为 header.payload.signature 三段结构",
                         {"segments": len(parts)})

    def _decode_segment(seg: str) -> dict:
        padded = seg + "=" * (-len(seg) % 4)
        try:
            raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        except (binascii.Error, ValueError):
            raise ParseError("JWT 段 Base64URL 解码失败（可能含非法字符）")
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ParseError("JWT 段不是合法 JSON")

    header = _decode_segment(parts[0])
    payload = _decode_segment(parts[1])
    return {
        "header": header,
        "payload": payload,
        "signature": parts[2],
        "note": "仅解码，未验证签名有效性",
    }


@data_tool(
    name="base64_image", title="Base64 ↔ 图片", category="encoding",
    description="Base64 转图片（data URL） / 图片转 Base64（互转）",
    parameters={
        "type": "object",
        "properties": {
            "action": {"type": "string", "title": "操作", "enum": ["encode", "decode"],
                       "x-enum-labels": ["图片 → Base64", "Base64 → 图片"],
                       "description": "图片转 Base64 / Base64 转图片"},
            "data": {"type": "string", "title": "数据", "description": "图片转 Base64 传图片 data URL 或 Base64；Base64 转图片传 Base64"},
            "mime_type": {"type": "string", "title": "图片类型", "description": "图片 MIME（图片转 Base64 时可省略自动识别）"},
        },
        "required": ["action", "data"],
    },
    is_generator=False,
)
def base64_image(action: str, data: str, mime_type: str = None) -> dict:
    if not data or not isinstance(data, str):
        raise InvalidParamError("data", "数据不能为空")
    if len(data) > MAX_B64_LEN:
        raise ParseError("Base64 输入超过 8MB 上限")

    if action == "decode":
        b64 = data.strip()
        if b64.startswith("data:"):
            # data URL 中提取纯 base64
            match = re.match(r"data:([^;,]+);base64,(.+)", b64, re.S)
            if not match:
                raise ParseError("data URL 格式不正确")
            mime_type = match.group(1)
            b64 = match.group(2)
        try:
            raw = base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError):
            raise ParseError("Base64 解码失败：内容非法或包含非 Base64 字符")
        # 图片魔数校验
        if HAS_PIL:
            try:
                img = Image.open(io.BytesIO(raw))
                img.verify()
                detected = img.format.lower()
                if not mime_type:
                    mime_type = f"image/{detected}" if detected != "jpg" else "image/jpeg"
            except UnidentifiedImageError:
                raise ParseError("解码结果不是合法图片")
        else:
            magic = raw[:4]
            mime_map = {
                b"\x89PNG": "image/png",
                b"\xff\xd8\xff": "image/jpeg",
                b"GIF8": "image/gif",
                b"RIFF": "image/webp",
                b"BM": "image/bmp",
            }
            detected = next((m for m, mime in mime_map.items() if raw.startswith(m)), None)
            if not detected:
                raise ParseError("解码结果不是合法图片（无法识别图片魔数）")
            mime_type = mime_type or next(mime for m, mime in mime_map.items() if raw.startswith(m))
        return {"image_base64": b64, "mime": mime_type or "image/png",
                "data_url": _to_data_url(b64, mime_type or "image/png")}

    if action == "encode":
        raw = data.strip()
        if raw.startswith("data:"):
            match = re.match(r"data:([^;,]+);base64,(.+)", raw, re.S)
            if not match:
                raise ParseError("data URL 格式不正确")
            mime_type = mime_type or match.group(1)
            raw = match.group(2)
        try:
            payload = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError):
            raise ParseError("Base64 解码失败：内容非法")
        if HAS_PIL:
            try:
                img = Image.open(io.BytesIO(payload))
                fmt = img.format.lower()
                mime_type = mime_type or (f"image/{fmt}" if fmt != "jpg" else "image/jpeg")
            except UnidentifiedImageError:
                raise ParseError("数据不是合法图片")
        return {"base64": raw, "mime": mime_type or "application/octet-stream",
                "size_bytes": len(payload)}

    raise InvalidParamError("action", "仅支持 encode / decode")


@data_tool(
    name="base64_encode", title="Base64 编码", category="encoding",
    description="文本/Base64 互转，支持 URL-safe 字符集",
    parameters={
        "type": "object",
        "properties": {
            "action": {"type": "string", "title": "操作", "enum": ["encode", "decode"],
                       "x-enum-labels": ["文本 → Base64", "Base64 → 文本"],
                       "description": "文本转 Base64 / Base64 转文本"},
            "text": {"type": "string", "title": "文本", "description": "待处理文本", "x-multiline": True},
            "urlsafe": {"type": "boolean", "title": "URL-safe 字符集", "description": "使用 URL-safe 字符集（+ / 变 - _）"},
            "charset": {"type": "string", "title": "字符编码", "description": "字符编码，默认 utf-8"},
        },
        "required": ["action", "text"],
    },
    is_generator=False,
)
def base64_encode(action: str, text: str, urlsafe: bool = False, charset: str = "utf-8") -> dict:
    if text is None:
        raise InvalidParamError("text", "内容不能为空")
    try:
        if action == "encode":
            raw = text.encode(charset)
            b64 = base64.urlsafe_b64encode(raw).decode("ascii") if urlsafe else base64.b64encode(raw).decode("ascii")
            return {"result": b64}
        if action == "decode":
            s = text.strip()
            try:
                raw = base64.b64decode(s, validate=True)
            except (binascii.Error, ValueError):
                raw = base64.urlsafe_b64decode(s)
            return {"result": raw.decode(charset)}
    except (UnicodeEncodeError, UnicodeDecodeError, LookupError):
        raise ParseError(f"文本与字符集 '{charset}' 不兼容")
    except (binascii.Error, ValueError):
        raise ParseError("Base64 解码失败：内容非法")
    raise InvalidParamError("action", "仅支持 encode / decode")
