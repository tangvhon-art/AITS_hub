"""
测试数据生成工具（6 个）
复用 mock_data_generator 的姓氏库、手机号前缀库、身份证地区码与校验位算法
"""
import random
import re
import string
from datetime import datetime, timedelta

from app.services.data_tools.base import data_tool, InvalidParamError
from app.services.mock_data_generator import (
    SURNAMES, GIVEN_NAMES, PHONE_PREFIXES, EMAIL_DOMAINS, ID_CARD_REGIONS,
)

# ==================== 常量与数据 ====================

# 性别名字池（GIVEN_NAMES 为混合池）
MALE_GIVEN = [
    "伟", "强", "磊", "军", "洋", "勇", "杰", "涛", "明", "超",
    "刚", "文", "辉", "鑫", "斌", "波", "宇", "浩", "凯", "健",
    "俊", "帆", "鹏", "博", "建国", "建华", "志强", "志明", "永强",
]
FEMALE_GIVEN = [
    "芳", "娜", "敏", "静", "丽", "艳", "娟", "秀英", "霞", "平",
    "桂英", "玲", "婷", "雪", "倩", "琳", "欣", "颖", "佳", "悦",
    "璐", "瑶", "怡", "雯", "洁", "蕊", "海燕", "丽华", "秀兰",
]

# 省份 - 城市 - 区县 字典
REGION_MAP = {
    "北京": {"北京": ["东城区", "西城区", "朝阳区", "海淀区", "丰台区", "通州区"]},
    "上海": {"上海": ["黄浦区", "徐汇区", "静安区", "浦东新区", "闵行区", "宝山区"]},
    "广东": {"广州": ["天河区", "越秀区", "海珠区", "白云区", "番禺区"],
              "深圳": ["南山区", "福田区", "罗湖区", "宝安区", "龙岗区"]},
    "浙江": {"杭州": ["西湖区", "上城区", "拱墅区", "滨江区", "余杭区"],
              "宁波": ["海曙区", "鄞州区", "江北区", "镇海区"]},
    "江苏": {"南京": ["玄武区", "秦淮区", "建邺区", "鼓楼区", "栖霞区"],
              "苏州": ["姑苏区", "虎丘区", "吴中区", "相城区"]},
    "四川": {"成都": ["锦江区", "青羊区", "金牛区", "武侯区", "成华区"]},
    "湖北": {"武汉": ["江岸区", "江汉区", "硚口区", "汉阳区", "武昌区"]},
    "陕西": {"西安": ["新城区", "碑林区", "莲湖区", "雁塔区", "未央区"]},
}

STREETS = ["科技路", "建设大道", "人民路", "中山路", "解放路", "长江路",
           "文化街", "迎宾大道", "中心街", "工业园路", "创业路", "和平路"]

# 银行卡 BIN 前缀
BANK_CARD_BINS = {
    "debit": ["622202", "622848", "621700", "622700", "621661"],   # 银联借记卡
    "credit": ["622588", "622689", "622280"],                      # 银联贷记卡
    "visa": ["4"],                                                  # VISA
    "mastercard": ["51", "52", "53", "54", "55"],                  # MasterCard
}


def _luhn_checksum(digits: str) -> str:
    """Luhn 校验位：使 前缀+中间位+校验位 通过 Luhn 校验"""
    total = 0
    # 对不含校验位的前缀，从右往左：偶数位（i=0 为最右）翻倍
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 0:
            d2 = d * 2
            total += d2 - 9 if d2 > 9 else d2
        else:
            total += d
    return str((10 - (total % 10)) % 10)


def _valid_bank_card(card: str) -> bool:
    total = 0
    reverse = card[::-1]
    for i, ch in enumerate(reverse):
        d = int(ch)
        if i % 2 == 1:
            d2 = d * 2
            total += d2 - 9 if d2 > 9 else d2
        else:
            total += d
    return total % 10 == 0


# ==================== 工具实现 ====================

@data_tool(
    name="gen_chinese_name", title="生成中文名称", category="test_data",
    description="随机生成 2~4 字中文姓名，支持指定姓氏与性别",
    parameters={
        "type": "object",
        "properties": {
            "count": {"type": "integer", "title": "生成数量", "description": "生成数量，默认1，最大1000", "minimum": 1, "maximum": 1000},
            "surname": {"type": "string", "title": "姓氏", "description": "指定姓氏（如：张）"},
            "gender": {"type": "string", "title": "性别", "enum": ["male", "female"], "x-enum-labels": ["男", "女"],
                       "description": "男 / 女，不选则随机混合"},
        },
        "required": [],
    },
)
def gen_chinese_name(count: int = 1, surname: str = None, gender: str = None) -> list:
    if gender == "male":
        given_pool = MALE_GIVEN
    elif gender == "female":
        given_pool = FEMALE_GIVEN
    else:
        given_pool = GIVEN_NAMES
    names = []
    for _ in range(count):
        s = surname if surname else random.choice(SURNAMES)
        # 名字 1~2 字（2字名概率更高）
        g = random.choice(given_pool)
        if random.random() < 0.3:
            g += random.choice(given_pool)
        names.append(s + g)
    return names


@data_tool(
    name="gen_phone", title="生成手机号", category="test_data",
    description="生成中国大陆 11 位手机号，支持指定前三位前缀",
    parameters={
        "type": "object",
        "properties": {
            "count": {"type": "integer", "title": "生成数量", "description": "生成数量，默认1，最大1000", "minimum": 1, "maximum": 1000},
            "prefix": {"type": "string", "title": "号段前缀", "description": "固定前3位（如 138），必须为合法号段"},
        },
        "required": [],
    },
)
def gen_phone(count: int = 1, prefix: str = None) -> list:
    if prefix:
        prefix = str(prefix).strip()
        if not re.fullmatch(r"1[3-9]\d", prefix) and prefix not in PHONE_PREFIXES:
            raise InvalidParamError("prefix", "非法手机号前缀，需为 130-199 合法号段")
    phones = []
    for _ in range(count):
        p = prefix if prefix else random.choice(PHONE_PREFIXES)
        phones.append(p + "".join(random.choices(string.digits, k=8)))
    return phones


@data_tool(
    name="gen_email", title="生成邮箱", category="test_data",
    description="生成邮箱地址，支持固定邮箱后缀（domain 参数）",
    parameters={
        "type": "object",
        "properties": {
            "count": {"type": "integer", "title": "生成数量", "description": "生成数量，默认1，最大1000", "minimum": 1, "maximum": 1000},
            "domain": {"type": "string", "title": "邮箱后缀", "description": "固定邮箱后缀，如 example.com（不传则随机域名）"},
            "username_min": {"type": "integer", "title": "用户名最小长度", "description": "用户名最小长度，默认6", "minimum": 3, "maximum": 20},
            "username_max": {"type": "integer", "title": "用户名最大长度", "description": "用户名最大长度，默认12", "minimum": 3, "maximum": 32},
        },
        "required": [],
    },
)
def gen_email(count: int = 1, domain: str = None, username_min: int = 6, username_max: int = 12) -> list:
    if domain:
        domain = str(domain).strip().lstrip("@")
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", domain):
            raise InvalidParamError("domain", "非法邮箱域名")
    if username_min > username_max:
        username_min, username_max = username_max, username_min
    emails = []
    for _ in range(count):
        length = random.randint(int(username_min), int(username_max))
        user = "".join(random.choices(string.ascii_lowercase + string.digits, k=length))
        d = domain if domain else random.choice(EMAIL_DOMAINS)
        emails.append(f"{user}@{d}")
    return emails


@data_tool(
    name="gen_address", title="生成地址", category="test_data",
    description="生成结构化中文地址，支持限定省份与输出层级",
    parameters={
        "type": "object",
        "properties": {
            "count": {"type": "integer", "title": "生成数量", "description": "生成数量，默认1，最大1000", "minimum": 1, "maximum": 1000},
            "province": {"type": "string", "title": "限定省份", "description": "限定省份（北京/上海/广东/浙江/江苏/四川/湖北/陕西）"},
            "level": {"type": "string", "title": "输出层级", "enum": ["province", "city", "district", "full"],
                      "x-enum-labels": ["省", "市", "区县", "详细地址"],
                      "description": "输出层级：省 / 市 / 区县 / 详细地址，默认详细地址"},
        },
        "required": [],
    },
)
def gen_address(count: int = 1, province: str = None, level: str = "full") -> list:
    if province and province not in REGION_MAP:
        raise InvalidParamError("province", f"暂不支持的省份，可选: {list(REGION_MAP.keys())}")
    addresses = []
    for _ in range(count):
        if province:
            prov = province
        else:
            prov = random.choice(list(REGION_MAP.keys()))
        city = random.choice(list(REGION_MAP[prov].keys()))
        district = random.choice(REGION_MAP[prov][city])
        if level == "province":
            addresses.append(prov)
        elif level == "city":
            addresses.append(f"{prov}{city}市")
        elif level == "district":
            addresses.append(f"{prov}{city}市{district}")
        else:
            street = random.choice(STREETS)
            door = random.randint(1, 300)
            bld = random.randint(1, 30)
            room = random.randint(101, 3200)
            addresses.append(f"{prov}{city}市{district}{street}{door}号{bld}栋{room}室")
    return addresses


@data_tool(
    name="gen_id_card", title="生成身份证", category="test_data",
    description="生成 18 位中国大陆身份证号（含校验位），支持性别与出生年份范围",
    parameters={
        "type": "object",
        "properties": {
            "count": {"type": "integer", "title": "生成数量", "description": "生成数量，默认1，最大1000", "minimum": 1, "maximum": 1000},
            "gender": {"type": "string", "title": "性别", "enum": ["male", "female"], "x-enum-labels": ["男", "女"],
                       "description": "男（顺序码奇数）/ 女（顺序码偶数），不选则随机"},
            "birth_start": {"type": "string", "title": "出生年份下限", "description": "出生年份下限，如 1960（默认 60 岁）"},
            "birth_end": {"type": "string", "title": "出生年份上限", "description": "出生年份上限，如 2005（默认 18 岁）"},
        },
        "required": [],
    },
)
def gen_id_card(count: int = 1, gender: str = None, birth_start: str = None, birth_end: str = None) -> list:
    today = datetime.now()
    try:
        start_year = int(birth_start) if birth_start else today.year - 60
        end_year = int(birth_end) if birth_end else today.year - 18
    except (TypeError, ValueError):
        raise InvalidParamError("birth_start/birth_end", "出生年份需为 4 位数字")
    if start_year > end_year:
        start_year, end_year = end_year, start_year
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = end - start

    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    check_codes = ["1", "0", "X", "9", "8", "7", "6", "5", "4", "3", "2"]

    cards = []
    for _ in range(count):
        region = random.choice(ID_CARD_REGIONS)
        birth = (start + timedelta(days=random.randint(0, delta.days))).strftime("%Y%m%d")
        # 顺序码：奇数男 / 偶数女
        while True:
            seq = random.randint(100, 999)
            if gender == "male" and seq % 2 == 0:
                continue
            if gender == "female" and seq % 2 == 1:
                continue
            break
        id_17 = region + birth + str(seq)
        total = sum(int(id_17[i]) * weights[i] for i in range(17))
        cards.append(id_17 + check_codes[total % 11])
    return cards


@data_tool(
    name="gen_bank_card", title="生成银行卡号", category="test_data",
    description="生成符合 Luhn 校验的银行卡号，支持卡组织与卡号长度",
    parameters={
        "type": "object",
        "properties": {
            "count": {"type": "integer", "title": "生成数量", "description": "生成数量，默认1，最大1000", "minimum": 1, "maximum": 1000},
            "card_type": {"type": "string", "title": "卡类型", "enum": ["debit", "credit", "visa", "mastercard"],
                          "x-enum-labels": ["银联借记", "银联贷记", "VISA", "MasterCard"],
                          "description": "卡类型：银联借记 / 银联贷记 / VISA / MasterCard，默认银联借记"},
            "length": {"type": "integer", "title": "卡号长度", "description": "卡号长度 16~19，默认16", "minimum": 16, "maximum": 19},
        },
        "required": [],
    },
)
def gen_bank_card(count: int = 1, card_type: str = "debit", length: int = 16) -> list:
    bins = BANK_CARD_BINS.get(card_type, BANK_CARD_BINS["debit"])
    cards = []
    for _ in range(count):
        prefix = random.choice(bins)
        middle_len = length - len(prefix) - 1
        middle = "".join(random.choices(string.digits, k=middle_len))
        partial = prefix + middle
        cards.append(partial + _luhn_checksum(partial))
    return cards
