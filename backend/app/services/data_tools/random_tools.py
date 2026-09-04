"""
随机工具（8 个）：UUID / IP / MAC / 整数 / 浮点数 / 日期 / 颜色 / 密码
安全类（UUID、密码）使用 secrets，其余使用 random；全部支持 count 批量生成
"""
import random
import secrets
import string
import uuid as uuid_mod
from datetime import datetime, timedelta

from app.services.data_tools.base import data_tool, InvalidParamError

_CHARSETS = {
    "upper": string.ascii_uppercase,
    "lower": string.ascii_lowercase,
    "digit": string.digits,
    "special": "!@#$%^&*()-_=+[]{};:,.<>?",
}
# 易混淆字符（avoid_confusing 时剔除）
_CONFUSING = set("0O1lI|")


@data_tool(
    name="gen_uuid", title="UUID", category="random",
    description="生成 UUID（v1/v4），支持格式选项",
    parameters={
        "type": "object",
        "properties": {
            "count": {"type": "integer", "title": "生成数量", "description": "生成数量，默认1，最大1000", "minimum": 1, "maximum": 1000},
            "version": {"type": "string", "title": "UUID 版本", "enum": ["4", "1"], "x-enum-labels": ["v4（随机）", "v1（时间）"],
                        "description": "UUID 版本，默认 v4"},
            "hyphens": {"type": "boolean", "title": "带连字符", "description": "带连字符（如 550e8400-e29b-41d4-a716-446655440000），默认开启"},
            "uppercase": {"type": "boolean", "title": "大写", "description": "输出大写字母，默认小写"},
        },
        "required": [],
    },
)
def gen_uuid(count: int = 1, version: str = "4", hyphens: bool = True, uppercase: bool = False) -> list:
    values = []
    for _ in range(count):
        v = uuid_mod.uuid1() if version == "1" else uuid_mod.uuid4()
        s = str(v)
        if not hyphens:
            s = s.replace("-", "")
        if uppercase:
            s = s.upper()
        values.append(s)
    return values


@data_tool(
    name="gen_ip", title="IP 地址", category="random",
    description="生成 IPv4 / IPv6 地址",
    parameters={
        "type": "object",
        "properties": {
            "count": {"type": "integer", "title": "生成数量", "description": "生成数量，默认1，最大1000", "minimum": 1, "maximum": 1000},
            "version": {"type": "string", "title": "IP 版本", "enum": ["4", "6"], "x-enum-labels": ["IPv4", "IPv6"],
                        "description": "IP 版本，默认 IPv4"},
        },
        "required": [],
    },
)
def gen_ip(count: int = 1, version: str = "4") -> list:
    values = []
    for _ in range(count):
        if version == "6":
            values.append(":".join(f"{secrets.randbelow(65536):x}" for _ in range(8)))
        else:
            values.append(".".join(str(random.randint(1, 254)) for _ in range(4)))
    return values


@data_tool(
    name="gen_mac", title="MAC 地址", category="random",
    description="生成 MAC 地址，支持分隔符格式",
    parameters={
        "type": "object",
        "properties": {
            "count": {"type": "integer", "title": "生成数量", "description": "生成数量，默认1，最大1000", "minimum": 1, "maximum": 1000},
            "separator": {"type": "string", "title": "分隔符", "enum": [":", "-", ".", "none"],
                          "x-enum-labels": ["冒号（:）", "连字符（-）", "点分（.）", "无"],
                          "description": "分隔符：冒号 / 连字符 / 点分 / 无，默认冒号"},
        },
        "required": [],
    },
)
def gen_mac(count: int = 1, separator: str = ":") -> list:
    values = []
    for _ in range(count):
        octets = [f"{secrets.randbelow(256):02x}" for _ in range(6)]
        if separator == "none":
            values.append("".join(octets))
        elif separator == ".":
            values.append(".".join(["".join(octets[i:i + 2]) for i in range(0, 6, 2)]))
        elif separator == "-":
            values.append("-".join(octets))
        else:
            values.append(":".join(octets))
    return values


@data_tool(
    name="gen_int", title="整数", category="random",
    description="指定范围内随机整数（闭区间）",
    parameters={
        "type": "object",
        "properties": {
            "count": {"type": "integer", "title": "生成数量", "description": "生成数量，默认1，最大1000", "minimum": 1, "maximum": 1000},
            "min": {"type": "integer", "title": "最小值", "description": "最小值，默认0"},
            "max": {"type": "integer", "title": "最大值", "description": "最大值，默认100"},
        },
        "required": [],
    },
)
def gen_int(count: int = 1, min: int = 0, max: int = 100) -> list:
    if max < min:
        min, max = max, min
    return [random.randint(int(min), int(max)) for _ in range(count)]


@data_tool(
    name="gen_float", title="浮点数", category="random",
    description="指定范围内随机浮点数，可设小数位",
    parameters={
        "type": "object",
        "properties": {
            "count": {"type": "integer", "title": "生成数量", "description": "生成数量，默认1，最大1000", "minimum": 1, "maximum": 1000},
            "min": {"type": "number", "title": "最小值", "description": "最小值，默认0"},
            "max": {"type": "number", "title": "最大值", "description": "最大值，默认1"},
            "precision": {"type": "integer", "title": "小数位数", "description": "小数位数，默认2", "minimum": 0, "maximum": 10},
        },
        "required": [],
    },
)
def gen_float(count: int = 1, min: float = 0.0, max: float = 1.0, precision: int = 2) -> list:
    if max < min:
        min, max = max, min
    return [round(random.uniform(float(min), float(max)), int(precision)) for _ in range(count)]


@data_tool(
    name="gen_date", title="日期", category="random",
    description="指定范围内随机日期，可含时间",
    parameters={
        "type": "object",
        "properties": {
            "count": {"type": "integer", "title": "生成数量", "description": "生成数量，默认1，最大1000", "minimum": 1, "maximum": 1000},
            "start": {"type": "string", "title": "开始日期", "x-widget": "date", "description": "开始日期 YYYY-MM-DD，默认 2000-01-01"},
            "end": {"type": "string", "title": "结束日期", "x-widget": "date", "description": "结束日期 YYYY-MM-DD，默认 2030-12-31"},
            "format": {"type": "string", "title": "输出格式", "description": "输出格式，默认 %Y-%m-%d（含时间时建议 %Y-%m-%d %H:%M:%S）"},
            "include_time": {"type": "boolean", "title": "包含时间", "description": "是否包含随机时间"},
        },
        "required": [],
    },
)
def gen_date(count: int = 1, start: str = "2000-01-01", end: str = "2030-12-31",
             format: str = "%Y-%m-%d", include_time: bool = False) -> list:
    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")
    except ValueError:
        raise InvalidParamError("start/end", "日期需为 YYYY-MM-DD 格式")
    if start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt
    delta = end_dt - start_dt
    values = []
    for _ in range(count):
        base = start_dt + timedelta(days=random.randint(0, delta.days))
        if include_time:
            base = base.replace(hour=random.randint(0, 23), minute=random.randint(0, 59),
                                second=random.randint(0, 59))
        values.append(base.strftime(format))
    return values


@data_tool(
    name="gen_color", title="颜色", category="random",
    description="随机颜色，支持 HEX / RGB / HSL 格式",
    parameters={
        "type": "object",
        "properties": {
            "count": {"type": "integer", "title": "生成数量", "description": "生成数量，默认1，最大1000", "minimum": 1, "maximum": 1000},
            "format": {"type": "string", "title": "颜色格式", "enum": ["hex", "rgb", "hsl"],
                       "x-enum-labels": ["HEX（#RRGGBB）", "RGB", "HSL"], "description": "颜色格式，默认 HEX"},
        },
        "required": [],
    },
)
def gen_color(count: int = 1, format: str = "hex") -> list:
    values = []
    for _ in range(count):
        r, g, b = random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)
        if format == "hex":
            values.append(f"#{r:02X}{g:02X}{b:02X}")
        elif format == "rgb":
            values.append(f"rgb({r}, {g}, {b})")
        else:
            # RGB → HSL
            rn, gn, bn = r / 255, g / 255, b / 255
            mx, mn = max(rn, gn, bn), min(rn, gn, bn)
            l = (mx + mn) / 2
            if mx == mn:
                h, s = 0.0, 0.0
            else:
                d = mx - mn
                s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
                if mx == rn:
                    h = ((gn - bn) / d + (6 if gn < bn else 0)) / 6
                elif mx == gn:
                    h = ((bn - rn) / d + 2) / 6
                else:
                    h = ((rn - gn) / d + 4) / 6
            values.append(f"hsl({round(h * 360)}, {round(s * 100)}%, {round(l * 100)}%)")
    return values


@data_tool(
    name="gen_password", title="密码", category="random",
    description="随机强密码（secrets 安全随机），可配字符集与长度",
    parameters={
        "type": "object",
        "properties": {
            "count": {"type": "integer", "title": "生成数量", "description": "生成数量，默认1，最大1000", "minimum": 1, "maximum": 1000},
            "length": {"type": "integer", "title": "密码长度", "description": "密码长度 8~64，默认16", "minimum": 8, "maximum": 64},
            "charset": {"type": "array", "title": "字符集", "items": {"type": "string", "enum": ["upper", "lower", "digit", "special"]},
                        "x-enum-labels": ["大写字母", "小写字母", "数字", "特殊符号"],
                        "description": "字符集（多选）：大写 / 小写 / 数字 / 特殊符号，默认全部"},
            "min_each": {"type": "boolean", "title": "每类至少一位", "description": "所选字符集每类至少出现 1 位，默认开启"},
            "avoid_confusing": {"type": "boolean", "title": "剔除易混淆字符", "description": "剔除易混淆字符 0/O/1/l/I，默认开启"},
        },
        "required": [],
    },
)
def gen_password(count: int = 1, length: int = 16, charset: list = None,
                 min_each: bool = True, avoid_confusing: bool = True) -> list:
    length = int(length)
    if length < 8 or length > 64:
        raise InvalidParamError("length", "密码长度需在 8~64 之间")
    selected = charset or ["upper", "lower", "digit", "special"]
    pools = []
    for key in selected:
        if key not in _CHARSETS:
            raise InvalidParamError("charset", f"不支持的字符集: {key}")
        pool = _CHARSETS[key]
        if avoid_confusing:
            pool = "".join(c for c in pool if c not in _CONFUSING)
        if not pool:
            raise InvalidParamError("charset", f"字符集 {key} 在剔除混淆字符后为空")
        pools.append(pool)

    all_chars = "".join(pools)
    values = []
    for _ in range(count):
        if min_each and len(pools) <= length:
            chars = [secrets.choice(p) for p in pools]
            chars += [secrets.choice(all_chars) for _ in range(length - len(pools))]
            secrets.SystemRandom().shuffle(chars)
            values.append("".join(chars))
        else:
            values.append("".join(secrets.choice(all_chars) for _ in range(length)))
    return values
