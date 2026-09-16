"""
Mock 数据生成器
支持 {{$function(args)}} 语法，在变量替换之前优先解析 Mock 函数
支持函数：randomPhone, randomInt, randomFloat, randomString, uuid,
        randomEmail, randomName, randomDate, timestamp, datetime,
        randomBoolean, randomIP, randomIdCard
"""
import re
import uuid
import random
import string
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


# 手机号前缀
PHONE_PREFIXES = [
    "130", "131", "132", "133", "134", "135", "136", "137", "138", "139",
    "150", "151", "152", "153", "155", "156", "157", "158", "159",
    "170", "171", "172", "173", "175", "176", "177", "178",
    "180", "181", "182", "183", "184", "185", "186", "187", "188", "189",
    "198", "199",
]

# 姓氏
SURNAMES = [
    "赵", "钱", "孙", "李", "周", "吴", "郑", "王", "冯", "陈",
    "褚", "卫", "蒋", "沈", "韩", "杨", "朱", "秦", "尤", "许",
    "何", "吕", "施", "张", "孔", "曹", "严", "华", "金", "魏",
    "陶", "姜", "戚", "谢", "邹", "喻", "柏", "水", "窦", "章",
    "云", "苏", "潘", "葛", "奚", "范", "彭", "郎", "鲁", "韦",
    "昌", "马", "苗", "凤", "花", "方", "俞", "任", "袁", "柳",
    "唐", "罗", "薛", "伍", "余", "米", "贝", "明", "臧", "计",
]

# 名字常用字
GIVEN_NAMES = [
    "伟", "芳", "娜", "敏", "静", "丽", "强", "磊", "军", "洋",
    "勇", "艳", "杰", "娟", "涛", "明", "超", "秀英", "霞", "平",
    "刚", "桂英", "文", "辉", "玲", "鑫", "斌", "波", "宇", "浩",
    "凯", "健", "俊", "帆", "鹏", "博", "婷", "雪", "倩", "琳",
    "欣", "颖", "佳", "悦", "璐", "瑶", "怡", "雯", "洁", "蕊",
    "建国", "建华", "志强", "志明", "永强", "海燕", "丽华", "秀兰",
]

# 邮箱域名
EMAIL_DOMAINS = [
    "gmail.com", "qq.com", "163.com", "126.com", "outlook.com",
    "hotmail.com", "yahoo.com", "foxmail.com", "sina.com", "sohu.com",
]

# 身份证地区码（前6位）
ID_CARD_REGIONS = [
    "110101", "110102", "110105", "110106", "110108",  # 北京
    "310101", "310104", "310105", "310106", "310107",  # 上海
    "440103", "440104", "440105", "440106", "440111",  # 广州
    "440303", "440304", "440305", "440306", "440307",  # 深圳
    "330102", "330103", "330104", "330105", "330106",  # 杭州
    "320102", "320104", "320105", "320106", "320111",  # 南京
    "510104", "510105", "510106", "510107", "510108",  # 成都
    "420102", "420103", "420104", "420105", "420106",  # 武汉
]


class MockDataGenerator:
    """Mock 数据生成器"""

    # 匹配 {{$function(args)}} 模式
    MOCK_PATTERN = re.compile(r"\{\{\s*\$(\w+)\s*\(([^)]*)\)\s*\}\}")

    def __init__(self):
        self.functions: Dict[str, callable] = {
            "randomPhone": self._random_phone,
            "randomInt": self._random_int,
            "randomFloat": self._random_float,
            "randomString": self._random_string,
            "uuid": self._uuid,
            "randomEmail": self._random_email,
            "randomName": self._random_name,
            "randomDate": self._random_date,
            "timestamp": self._timestamp,
            "datetime": self._datetime,
            "randomBoolean": self._random_boolean,
            "randomIP": self._random_ip,
            "randomIdCard": self._random_id_card,
        }

    def get_function_list(self) -> List[Dict[str, Any]]:
        """获取所有支持的函数列表（用于前端展示）"""
        return [
            {
                "name": "randomPhone",
                "description": "随机生成中国大陆手机号",
                "syntax": "{{$randomPhone()}}",
                "example": "13812345678",
                "args": [],
            },
            {
                "name": "randomInt",
                "description": "随机生成指定范围内的整数",
                "syntax": "{{$randomInt(min,max)}}",
                "example": "{{$randomInt(1,100)}} → 42",
                "args": ["min: 最小值", "max: 最大值"],
            },
            {
                "name": "randomFloat",
                "description": "随机生成指定范围内的浮点数",
                "syntax": "{{$randomFloat(min,max)}}",
                "example": "{{$randomFloat(0,1)}} → 0.73",
                "args": ["min: 最小值", "max: 最大值"],
            },
            {
                "name": "randomString",
                "description": "随机生成指定长度的字符串（字母+数字）",
                "syntax": "{{$randomString(length)}}",
                "example": "{{$randomString(8)}} → aB3kL9mP",
                "args": ["length: 字符串长度"],
            },
            {
                "name": "uuid",
                "description": "生成 UUID v4",
                "syntax": "{{$uuid()}}",
                "example": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "args": [],
            },
            {
                "name": "randomEmail",
                "description": "随机生成邮箱地址，可选指定域名后缀",
                "syntax": "{{$randomEmail()}} 或 {{$randomEmail(example.com)}}",
                "example": "user123@gmail.com 或 user123@example.com",
                "args": ["domain: 域名后缀（可选，如 example.com，不传则随机）"],
            },
            {
                "name": "randomName",
                "description": "随机生成中文姓名",
                "syntax": "{{$randomName()}}",
                "example": "张伟",
                "args": [],
            },
            {
                "name": "randomDate",
                "description": "随机生成指定日期范围内的日期",
                "syntax": "{{$randomDate(start,end)}}",
                "example": "{{$randomDate(2020-01-01,2025-12-31)}} → 2023-06-15",
                "args": ["start: 开始日期(YYYY-MM-DD)", "end: 结束日期(YYYY-MM-DD)"],
            },
            {
                "name": "timestamp",
                "description": "生成当前时间戳（秒）",
                "syntax": "{{$timestamp()}}",
                "example": "1718438400",
                "args": [],
            },
            {
                "name": "datetime",
                "description": "生成当前日期时间（YYYY-MM-DD HH:MM:SS）",
                "syntax": "{{$datetime()}}",
                "example": "2025-06-15 14:30:00",
                "args": [],
            },
            {
                "name": "randomBoolean",
                "description": "随机生成布尔值 true/false",
                "syntax": "{{$randomBoolean()}}",
                "example": "true",
                "args": [],
            },
            {
                "name": "randomIP",
                "description": "随机生成 IPv4 地址",
                "syntax": "{{$randomIP()}}",
                "example": "192.168.1.100",
                "args": [],
            },
            {
                "name": "randomIdCard",
                "description": "随机生成中国大陆身份证号（18位，含校验位）",
                "syntax": "{{$randomIdCard()}}",
                "example": "110101199001011234",
                "args": [],
            },
        ]

    def generate(self, text: str) -> str:
        """
        解析文本中的 {{$function(args)}} 并替换为生成的值
        优先级：Mock 函数 > 变量替换
        """
        if not text or not isinstance(text, str):
            return text

        def _replace_match(match):
            func_name = match.group(1)
            args_str = match.group(2).strip()
            return self._call_function(func_name, args_str)

        return self.MOCK_PATTERN.sub(_replace_match, text)

    def generate_dict(self, data: Any) -> Any:
        """递归替换字典/列表中的 Mock 函数"""
        if isinstance(data, str):
            return self.generate(data)
        if isinstance(data, dict):
            return {k: self.generate_dict(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self.generate_dict(item) for item in data]
        return data

    def generate_headers(self, headers: Optional[list]) -> Optional[list]:
        """替换请求头列表中的 Mock 函数"""
        if not headers:
            return headers
        result = []
        for h in headers:
            new_h = dict(h)
            if "key" in new_h:
                new_h["key"] = self.generate(str(new_h["key"]))
            if "value" in new_h:
                new_h["value"] = self.generate(str(new_h["value"]))
            result.append(new_h)
        return result

    def generate_params(self, params: Optional[list]) -> Optional[list]:
        """替换参数列表中的 Mock 函数"""
        return self.generate_headers(params)

    def generate_body(self, body_type: str, body_content: Any) -> Any:
        """替换请求体中的 Mock 函数"""
        if body_content is None:
            return body_content
        if body_type in ("raw", "json", "binary"):
            if isinstance(body_content, str):
                return self.generate(body_content)
            return self.generate_dict(body_content)
        if body_type in ("form-data", "x-www-form-urlencoded"):
            return self.generate_dict(body_content)
        return body_content

    def _call_function(self, func_name: str, args_str: str) -> str:
        """调用 Mock 函数"""
        if func_name not in self.functions:
            # 未知函数，保留原样
            return f"{{{{${func_name}({args_str})}}}}"

        try:
            args = self._parse_args(args_str)
            result = self.functions[func_name](*args)
            return str(result)
        except Exception as e:
            # 函数执行失败，保留原样并附加错误信息
            return f"{{{{${func_name}({args_str})}}}}"

    def _parse_args(self, args_str: str) -> Tuple:
        """解析函数参数字符串"""
        if not args_str:
            return ()
        # 简单按逗号分割，去除空白和引号
        args = []
        for arg in args_str.split(","):
            arg = arg.strip()
            # 去除引号
            if (arg.startswith('"') and arg.endswith('"')) or \
               (arg.startswith("'") and arg.endswith("'")):
                arg = arg[1:-1]
            # 尝试转为数字
            try:
                if "." in arg:
                    arg = float(arg)
                else:
                    arg = int(arg)
            except (ValueError, TypeError):
                pass
            args.append(arg)
        return tuple(args)

    # ==================== Mock 函数实现 ====================

    def _random_phone(self) -> str:
        """随机手机号"""
        prefix = random.choice(PHONE_PREFIXES)
        suffix = "".join(random.choices(string.digits, k=8))
        return prefix + suffix

    def _random_int(self, min_val: int = 0, max_val: int = 100) -> int:
        """随机整数"""
        return random.randint(int(min_val), int(max_val))

    def _random_float(self, min_val: float = 0.0, max_val: float = 1.0) -> float:
        """随机浮点数，保留2位小数"""
        return round(random.uniform(float(min_val), float(max_val)), 2)

    def _random_string(self, length: int = 8) -> str:
        """随机字符串（大小写字母+数字）"""
        length = int(length)
        chars = string.ascii_letters + string.digits
        return "".join(random.choices(chars, k=length))

    def _uuid(self) -> str:
        """UUID v4"""
        return str(uuid.uuid4())

    def _random_email(self, domain: str = "") -> str:
        """随机邮箱，可选指定域名后缀（如 example.com）"""
        username = "".join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(6, 12)))
        if domain:
            domain = domain.lstrip("@")
        else:
            domain = random.choice(EMAIL_DOMAINS)
        return f"{username}@{domain}"

    def _random_name(self) -> str:
        """随机中文姓名"""
        surname = random.choice(SURNAMES)
        given = random.choice(GIVEN_NAMES)
        return surname + given

    def _random_date(self, start: str = "2000-01-01", end: str = "2030-12-31") -> str:
        """随机日期"""
        try:
            start_date = datetime.strptime(str(start), "%Y-%m-%d")
            end_date = datetime.strptime(str(end), "%Y-%m-%d")
        except ValueError:
            start_date = datetime(2000, 1, 1)
            end_date = datetime(2030, 12, 31)

        if start_date > end_date:
            start_date, end_date = end_date, start_date

        delta = end_date - start_date
        random_days = random.randint(0, delta.days)
        return (start_date + timedelta(days=random_days)).strftime("%Y-%m-%d")

    def _timestamp(self) -> int:
        """当前时间戳（秒）"""
        return int(time.time())

    def _datetime(self) -> str:
        """当前日期时间"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _random_boolean(self) -> str:
        """随机布尔值"""
        return "true" if random.choice([True, False]) else "false"

    def _random_ip(self) -> str:
        """随机 IPv4 地址"""
        return ".".join(str(random.randint(1, 254)) for _ in range(4))

    def _random_id_card(self) -> str:
        """随机身份证号（18位，含校验位）"""
        # 地区码
        region = random.choice(ID_CARD_REGIONS)
        # 出生日期（18-60岁之间）
        today = datetime.now()
        start = today.replace(year=today.year - 60)
        end = today.replace(year=today.year - 18)
        delta = end - start
        birth_date = start + timedelta(days=random.randint(0, delta.days))
        birth = birth_date.strftime("%Y%m%d")
        # 顺序码（3位，最后一位奇数为男，偶数为女）
        seq = random.randint(100, 999)
        # 前17位
        id_17 = region + birth + str(seq)
        # 计算校验位
        weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
        check_codes = ["1", "0", "X", "9", "8", "7", "6", "5", "4", "3", "2"]
        total = sum(int(id_17[i]) * weights[i] for i in range(17))
        check_code = check_codes[total % 11]
        return id_17 + check_code


# 全局单例
mock_generator = MockDataGenerator()
