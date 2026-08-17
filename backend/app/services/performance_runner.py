import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class PerformanceRunner:
    """Locust 性能测试执行器"""

    def __init__(self, db: Session):
        self.db = db

    def generate_locust_script(
        self,
        method: str,
        url: str,
        headers: dict,
        body: Optional[str],
        users: int,
        spawn_rate: int,
        duration: int,
        test_data: Optional[list] = None,
    ) -> str:
        """根据配置生成 Locust 脚本"""
        headers_json = json.dumps(headers or {})
        body_literal = body or ""
        test_data_json = json.dumps(test_data, ensure_ascii=False) if test_data else "[]"

        script = f'''"""Locust 性能测试脚本 - 自动生成"""
import json
import itertools
from locust import HttpUser, task, between

HEADERS = {headers_json}
BODY_TEMPLATE = """{body_literal}"""
TEST_DATA = {test_data_json}
_data_cycle = itertools.cycle(TEST_DATA) if TEST_DATA else None

def build_body():
    if not _data_cycle:
        return BODY_TEMPLATE or None
    row = next(_data_cycle)
    if BODY_TEMPLATE:
        body = BODY_TEMPLATE
        for k, v in row.items():
            body = body.replace("{{{{" + str(k) + "}}}}", str(v))
        return body
    return json.dumps(row)

class PerformanceTestUser(HttpUser):
    """模拟用户行为"""
    wait_time = between(0.5, 2.0)

    @task
    def send_request(self):
        """发送请求"""
        try:
            body = build_body()
            if "{method.upper()}" == "GET":
                self.client.get("{url}", headers=HEADERS, name="{method.upper()} {url}")
            elif "{method.upper()}" == "POST":
                self.client.post("{url}", headers=HEADERS, data=body, name="{method.upper()} {url}")
            elif "{method.upper()}" == "PUT":
                self.client.put("{url}", headers=HEADERS, data=body, name="{method.upper()} {url}")
            elif "{method.upper()}" == "DELETE":
                self.client.delete("{url}", headers=HEADERS, name="{method.upper()} {url}")
            elif "{method.upper()}" == "PATCH":
                self.client.patch("{url}", headers=HEADERS, data=body, name="{method.upper()} {url}")
        except Exception as e:
            print(f"Request error: {{e}}")
'''
        return script

    def run(
        self,
        run_id: int,
        test_config: dict,
        target_url: str,
        method: str,
        headers: dict,
        body: Optional[str],
        test_data: Optional[list] = None,
    ) -> dict:
        """启动 Locust 性能测试（通过子进程）"""
        from app.models.performance_test import PerformanceTest, PerformanceTestRun
        from app.core.timezone import china_now_naive

        run = self.db.query(PerformanceTestRun).filter(PerformanceTestRun.id == run_id).first()
        if not run:
            return {"error": "执行记录不存在"}

        test = self.db.query(PerformanceTest).filter(PerformanceTest.id == run.test_id).first()

        run.status = "running"
        run.started_at = china_now_naive()
        self.db.commit()

        try:
            script = self.generate_locust_script(
                method=method,
                url=target_url,
                headers=headers or {},
                body=body,
                users=test_config.get("users", 10),
                spawn_rate=test_config.get("spawn_rate", 1),
                duration=test_config.get("duration", 60),
                test_data=test_data,
            )

            with tempfile.NamedTemporaryFile(mode="w", suffix="_locust.py", delete=False) as f:
                f.write(script)
                script_path = f.name

            host = self._extract_host(target_url)
            users = test_config.get("users", 10)
            spawn_rate = test_config.get("spawn_rate", 1)
            duration = test_config.get("duration", 60)

            cmd = [
                sys.executable, "-m", "locust",
                "-f", script_path,
                "--headless",
                "-u", str(users),
                "-r", str(spawn_rate),
                "-t", f"{duration}s",
                "--host", host,
                "--csv", f"/tmp/locust_result_{run_id}",
            ]

            logger.info(f"启动 Locust: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 120)

            stats = self._parse_locust_output(result.stdout, run_id)

            run.status = "completed"
            run.finished_at = china_now_naive()
            run.total_requests = stats.get("total_requests", 0)
            run.total_failures = stats.get("total_failures", 0)
            run.avg_response_time = stats.get("avg_response_time", 0.0)
            run.min_response_time = stats.get("min_response_time", 0.0)
            run.max_response_time = stats.get("max_response_time", 0.0)
            run.p50_response_time = stats.get("p50_response_time", 0.0)
            run.p95_response_time = stats.get("p95_response_time", 0.0)
            run.p99_response_time = stats.get("p99_response_time", 0.0)
            run.requests_per_second = stats.get("requests_per_second", 0.0)
            run.failure_rate = stats.get("failure_rate", 0.0)
            run.stats_history = stats.get("stats_history", [])
            run.error_summary = stats.get("error_summary", {})
            if test:
                test.status = "completed"
            self.db.commit()

            os.unlink(script_path)
            self._cleanup_csv_files(run_id)

            return {"status": "completed", "stats": stats}

        except subprocess.TimeoutExpired:
            run.status = "failed"
            run.finished_at = china_now_naive()
            run.error_summary = {"error": "执行超时"}
            if test:
                test.status = "failed"
            self.db.commit()
            return {"status": "failed", "error": "执行超时"}
        except Exception as e:
            logger.error(f"性能测试执行失败: {e}", exc_info=True)
            run.status = "failed"
            run.finished_at = china_now_naive()
            run.error_summary = {"error": str(e)}
            if test:
                test.status = "failed"
            self.db.commit()
            return {"status": "failed", "error": str(e)}

    def stop(self, run_id: int):
        """停止执行"""
        from app.models.performance_test import PerformanceTestRun
        from app.core.timezone import china_now_naive

        run = self.db.query(PerformanceTestRun).filter(PerformanceTestRun.id == run_id).first()
        if run and run.status == "running":
            run.status = "stopped"
            run.finished_at = china_now_naive()
            self.db.commit()

    def _extract_host(self, url: str) -> str:
        """从 URL 提取 host"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
        return "http://localhost"

    def _parse_locust_output(self, stdout: str, run_id: int) -> dict:
        """从 Locust CSV 输出解析统计数据"""
        import csv

        stats = {
            "total_requests": 0,
            "total_failures": 0,
            "avg_response_time": 0.0,
            "min_response_time": 0.0,
            "max_response_time": 0.0,
            "p50_response_time": 0.0,
            "p95_response_time": 0.0,
            "p99_response_time": 0.0,
            "requests_per_second": 0.0,
            "failure_rate": 0.0,
            "stats_history": [],
            "error_summary": {},
        }

        csv_path = f"/tmp/locust_result_{run_id}_stats.csv"
        if os.path.exists(csv_path):
            try:
                with open(csv_path, "r") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get("Name") == "Aggregated":
                            stats["total_requests"] = int(float(row.get("Request Count", 0)))
                            stats["total_failures"] = int(float(row.get("Failure Count", 0)))
                            stats["avg_response_time"] = float(row.get("Average Response Time", 0))
                            stats["min_response_time"] = float(row.get("Min Response Time", 0))
                            stats["max_response_time"] = float(row.get("Max Response Time", 0))
                            stats["p50_response_time"] = float(row.get("50%", 0) or 0)
                            stats["p95_response_time"] = float(row.get("95%", 0) or 0)
                            stats["p99_response_time"] = float(row.get("99%", 0) or 0)
                            stats["requests_per_second"] = float(row.get("Requests/s", 0))
                            total = stats["total_requests"]
                            fails = stats["total_failures"]
                            stats["failure_rate"] = round(fails / total * 100, 2) if total > 0 else 0.0
                            break
            except Exception as e:
                logger.warning(f"解析 Locust CSV 失败: {e}")

        failures_path = f"/tmp/locust_result_{run_id}_failures.csv"
        if os.path.exists(failures_path):
            try:
                with open(failures_path, "r") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        err_type = row.get("Error", "Unknown")
                        count = int(float(row.get("Occurrences", 0)))
                        stats["error_summary"][err_type] = count
            except Exception:
                pass

        stats["stats_history"] = self._parse_stats_history(run_id)

        return stats

    def _parse_stats_history(self, run_id: int) -> list:
        """解析 Locust stats_history CSV，提取每秒的 Aggregated 数据"""
        import csv

        history_path = f"/tmp/locust_result_{run_id}_stats_history.csv"
        if not os.path.exists(history_path):
            logger.warning(f"stats_history CSV 文件不存在: {history_path}")
            return []

        history = []
        total_rows = 0
        try:
            with open(history_path, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    total_rows += 1
                    if row.get("Name") != "Aggregated":
                        continue
                    history.append({
                        "timestamp": row.get("Timestamp", ""),
                        "users": int(float(row.get("User Count", 0))),
                        "rps": float(row.get("Requests/s", 0) or 0),
                        "failures_per_s": float(row.get("Failures/s", 0) or 0),
                        "p50": float(row.get("50%", 0) or 0),
                        "p95": float(row.get("95%", 0) or 0),
                        "p99": float(row.get("99%", 0) or 0),
                        "avg": float(row.get("Average Response Time", 0) or 0),
                    })
        except Exception as e:
            logger.warning(f"解析 stats_history CSV 失败: {e}")

        if total_rows > 0 and len(history) == 0:
            logger.warning(f"stats_history CSV 有 {total_rows} 行但无 Aggregated 行，可能 Locust 版本输出格式不同")
        else:
            logger.info(f"stats_history 解析完成: {len(history)} 条 Aggregated 记录 (共 {total_rows} 行)")

        return history

    def _cleanup_csv_files(self, run_id: int):
        """清理 Locust CSV 临时文件"""
        for suffix in ["_stats.csv", "_failures.csv", "_stats_history.csv"]:
            path = f"/tmp/locust_result_{run_id}{suffix}"
            if os.path.exists(path):
                try:
                    os.unlink(path)
                except Exception:
                    pass

    def _convert_headers(self, raw_headers) -> dict:
        """将 headers 从列表格式转为字典格式"""
        if isinstance(raw_headers, dict):
            return raw_headers
        if isinstance(raw_headers, list):
            result = {}
            for h in raw_headers:
                if isinstance(h, dict) and h.get("key"):
                    if h.get("enabled", True):
                        result[h["key"]] = h.get("value", "")
            return result
        return {}

    def _convert_body(self, body_content, body_type: str = "none") -> Optional[str]:
        """将 body_content 转为字符串"""
        if not body_content:
            return None
        if isinstance(body_content, str):
            return body_content
        if isinstance(body_content, (dict, list)):
            return json.dumps(body_content, ensure_ascii=False)
        return str(body_content)

    def get_target_info(self, target_type: str, target_id: int) -> dict:
        """从目标获取请求信息"""
        if target_type == "api_definition":
            from app.models.api_test import ApiDefinition
            d = self.db.query(ApiDefinition).filter(ApiDefinition.id == target_id).first()
            if d:
                return {
                    "method": d.method,
                    "path": d.path,
                    "headers": self._convert_headers(d.headers),
                    "body": self._convert_body(d.body_content, d.body_type),
                    "name": d.name,
                }
        elif target_type == "api_case":
            from app.models.api_test import ApiTestCase
            c = self.db.query(ApiTestCase).filter(ApiTestCase.id == target_id).first()
            if c:
                method = c.method
                path = c.path
                if not method or not path:
                    from app.models.api_test import ApiDefinition
                    d = self.db.query(ApiDefinition).filter(ApiDefinition.id == c.api_id).first()
                    if d:
                        method = method or d.method
                        path = path or d.path
                return {
                    "method": method or "GET",
                    "path": path or "/",
                    "headers": self._convert_headers(c.headers),
                    "body": self._convert_body(c.body_content, c.body_type),
                    "name": c.name,
                }
        elif target_type == "api_scenario":
            from app.models.api_test import ApiScenario
            s = self.db.query(ApiScenario).filter(ApiScenario.id == target_id).first()
            if s:
                return {
                    "method": "GET",
                    "path": "/",
                    "headers": {},
                    "body": None,
                    "name": s.name,
                }
        return {}
