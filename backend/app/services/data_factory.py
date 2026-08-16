import logging
import random
import string
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DataFactory:
    """测试数据工厂"""

    GENERATORS = {
        "name": lambda: random.choice(["张三", "李四", "王五", "赵六", "钱七", "孙八", "周九", "吴十"]),
        "email": lambda: f"test_{uuid.uuid4().hex[:8]}@example.com",
        "phone": lambda: f"1{random.choice(['3','5','7','8','9'])}{random.randint(100000000, 999999999)}",
        "uuid": lambda: str(uuid.uuid4()),
        "random_string": lambda length=8: "".join(random.choices(string.ascii_letters + string.digits, k=length)),
        "random_int": lambda min_v=1, max_v=100: random.randint(min_v, max_v),
        "timestamp": lambda: str(int(__import__("time").time())),
        "boolean": lambda: random.choice([True, False]),
        "address": lambda: random.choice(["北京市朝阳区", "上海市浦东新区", "广州市天河区", "深圳市南山区"]),
        "company": lambda: random.choice(["科技有限公司", "贸易有限公司", "咨询有限公司", "集团有限公司"]),
    }

    def generate(self, schema: List[dict], count: int = 10) -> List[dict]:
        """根据 schema 生成测试数据

        Args:
            schema: 字段定义列表 [{name, type, generator, default_value}]
            count: 生成行数
        """
        rows = []
        counter = 0

        for _ in range(count):
            row = {}
            for field in schema:
                name = field.get("name", "")
                field_type = field.get("type", "string")
                generator = field.get("generator")
                default_value = field.get("default_value")

                if generator and generator in self.GENERATORS:
                    try:
                        gen = self.GENERATORS[generator]
                        import inspect
                        sig = inspect.signature(gen)
                        params = {}
                        if "min_v" in sig.parameters:
                            params["min_v"] = field.get("min_value", 1)
                        if "max_v" in sig.parameters:
                            params["max_v"] = field.get("max_value", 100)
                        if "length" in sig.parameters:
                            params["length"] = field.get("length", 8)
                        row[name] = gen(**params) if params else gen()
                    except Exception as e:
                        logger.warning(f"生成器 {generator} 执行失败: {e}")
                        row[name] = default_value if default_value is not None else ""
                elif generator == "sequential":
                    counter += 1
                    row[name] = counter
                elif default_value is not None:
                    row[name] = default_value
                else:
                    row[name] = self._generate_default(field_type)

            rows.append(row)

        return rows

    def generate_from_pool(self, db, pool_id: int, count: int = 10) -> List[dict]:
        """从数据池生成数据"""
        from app.models.test_data_pool import TestDataPool

        pool = db.query(TestDataPool).filter(
            TestDataPool.id == pool_id,
            TestDataPool.is_deleted == False,
        ).first()

        if not pool:
            return []

        if pool.data_type == "static":
            return pool.data or []

        if pool.data_type in ("dynamic", "generated"):
            return self.generate(pool.schema or [], count)

        return pool.data or []

    def _generate_default(self, field_type: str) -> Any:
        """根据类型生成默认值"""
        defaults = {
            "string": "",
            "integer": 0,
            "float": 0.0,
            "boolean": False,
            "array": [],
            "object": {},
        }
        return defaults.get(field_type, "")
