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
        targets: list,
        headers: dict,
        users: int,
        spawn_rate: int,
        duration: int,
        test_data: Optional[list] = None,
    ) -> str:
        """根据多接口配置生成 Locust 脚本

        targets: [{method, url, name, weight, body}]
        """
        headers_json = json.dumps(headers or {})
        test_data_json = json.dumps(test_data, ensure_ascii=False) if test_data else "[]"

        # 生成每个接口的 task 方法
        task_methods = []
        for i, t in enumerate(targets):
            method = (t.get("method") or "GET").upper()
            url = t.get("url") or "/"
            name = t.get("name") or f"接口{i+1}"
            weight = t.get("weight") or 1
            body_literal = json.dumps(t.get("body") or "", ensure_ascii=False)
            safe_name = f"task_{i}"

            if method == "GET":
                request_code = f'self.client.get("{url}", headers=HEADERS, name="{method} {name}")'
            elif method == "POST":
                request_code = f'self.client.post("{url}", headers=HEADERS, data=_build_body({body_literal}), name="{method} {name}")'
            elif method == "PUT":
                request_code = f'self.client.put("{url}", headers=HEADERS, data=_build_body({body_literal}), name="{method} {name}")'
            elif method == "DELETE":
                request_code = f'self.client.delete("{url}", headers=HEADERS, name="{method} {name}")'
            elif method == "PATCH":
                request_code = f'self.client.patch("{url}", headers=HEADERS, data=_build_body({body_literal}), name="{method} {name}")'
            else:
                request_code = f'self.client.request("{method}", "{url}", headers=HEADERS, name="{method} {name}")'

            task_methods.append(f'''
    @task({weight})
    def {safe_name}(self):
        try:
            {request_code}
        except Exception as e:
            print(f"Request error: {{e}}")
''')

        tasks_code = "\n".join(task_methods)

        script = f'''"""Locust 性能测试脚本 - 自动生成（多接口）"""
import json
import itertools
from locust import HttpUser, task, between

HEADERS = {headers_json}
TEST_DATA = {test_data_json}
_data_cycle = itertools.cycle(TEST_DATA) if TEST_DATA else None

def _build_body(template):
    if not _data_cycle or not template:
        return template or None
    row = next(_data_cycle)
    body = template
    for k, v in row.items():
        body = body.replace("{{{{" + str(k) + "}}}}", str(v))
    return body

class PerformanceTestUser(HttpUser):
    """模拟用户行为"""
    wait_time = between(0.5, 2.0)
{tasks_code}
'''
        return script

    def run(
        self,
        run_id: int,
        test_config: dict,
        targets: list,
        headers: dict,
        test_data: Optional[list] = None,
    ) -> dict:
        """启动 Locust 性能测试（通过子进程）

        targets: [{method, url, name, weight, body}]
        """
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
                targets=targets,
                headers=headers or {},
                users=test_config.get("users", 10),
                spawn_rate=test_config.get("spawn_rate", 1),
                duration=test_config.get("duration", 60),
                test_data=test_data,
            )

            with tempfile.NamedTemporaryFile(mode="w", suffix="_locust.py", delete=False) as f:
                f.write(script)
                script_path = f.name

            # 从第一个 target 提取 host
            first_url = targets[0].get("url", "") if targets else ""
            host = self._extract_host(first_url)
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
                "--csv-full-history",
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
            run.endpoint_stats = stats.get("endpoint_stats", [])
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

        def safe_float(val, default=0.0):
            if val is None or val == "" or val == "N/A":
                return default
            try:
                return float(val)
            except (ValueError, TypeError):
                return default

        def get_col(row, *names, default=0.0):
            for n in names:
                if n in row and row[n] not in (None, "", "N/A"):
                    return safe_float(row[n], default)
            return default

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
            "endpoint_stats": [],
        }

        csv_path = f"/tmp/locust_result_{run_id}_stats.csv"
        if os.path.exists(csv_path):
            try:
                with open(csv_path, "r") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        name = row.get("Name", "")
                        req_count = int(get_col(row, "Request Count", "requests", "samples"))
                        fail_count = int(get_col(row, "Failure Count", "failures", "failure_count"))
                        avg_rt = get_col(row, "Average Response Time", "Average", "average", "avg")
                        min_rt = get_col(row, "Min Response Time", "Min", "min")
                        max_rt = get_col(row, "Max Response Time", "Max", "max")
                        p50 = get_col(row, "50%", "Median Response Time", "Median", "p50")
                        p95 = get_col(row, "95%", "p95")
                        p99 = get_col(row, "99%", "p99")
                        rps = get_col(row, "Requests/s", "RPS", "throughput", "rps")
                        failures_per_s = get_col(row, "Failures/s", "failures_per_s", "failures_per_second")
                        avg_size = get_col(row, "Average Content Size (bytes)", "Average Size (bytes)", "avg_size", "average_size")
                        fail_rate = round(fail_count / req_count * 100, 2) if req_count > 0 else 0.0

                        if name == "Aggregated":
                            stats["total_requests"] = req_count
                            stats["total_failures"] = fail_count
                            stats["avg_response_time"] = avg_rt
                            stats["min_response_time"] = min_rt
                            stats["max_response_time"] = max_rt
                            stats["p50_response_time"] = p50
                            stats["p95_response_time"] = p95
                            stats["p99_response_time"] = p99
                            stats["requests_per_second"] = rps
                            stats["failures_per_second"] = failures_per_s
                            stats["failure_rate"] = fail_rate
                        else:
                            # 按接口统计（JMeter 聚合报告风格）
                            stats["endpoint_stats"].append({
                                "label": name,
                                "samples": req_count,
                                "failures": fail_count,
                                "average": round(avg_rt, 2),
                                "median": round(p50, 2),
                                "min": round(min_rt, 2),
                                "max": round(max_rt, 2),
                                "std_dev": round(safe_float(row.get("Std Dev", 0)), 2),
                                "error_pct": fail_rate,
                                "throughput": round(rps, 2),
                                "failures_per_s": round(failures_per_s, 2),
                                "avg_size_bytes": round(avg_size, 2),
                                "received_kb_s": round(avg_size * rps / 1024, 2),
                                "p50": round(p50, 2),
                                "p90": round(safe_float(row.get("90%", 0)), 2),
                                "p95": round(p95, 2),
                                "p99": round(p99, 2),
                            })
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

    def _parse_stats_history(self, run_id: int) -> dict:
        """解析 Locust stats_history CSV，提取聚合趋势和各接口独立趋势

        返回格式:
        {
            "aggregate": [{timestamp, users, rps, p50, p95, p99, avg}, ...],
            "by_endpoint": {"GET /api/x": [...], "POST /api/y": [...]}
        }
        """
        import csv

        history_path = f"/tmp/locust_result_{run_id}_stats_history.csv"
        if not os.path.exists(history_path):
            logger.warning(f"stats_history CSV 文件不存在: {history_path}")
            return {"aggregate": [], "by_endpoint": {}}

        def safe_float(val, default=0.0):
            if val is None or val == "" or val == "N/A":
                return default
            try:
                return float(val)
            except (ValueError, TypeError):
                return default

        def get_col(row, *names, default=0.0):
            """尝试多个列名获取值"""
            for n in names:
                if n in row and row[n] not in (None, "", "N/A"):
                    return safe_float(row[n], default)
            return default

        aggregate = []
        by_endpoint = {}
        total_rows = 0
        header_logged = False
        try:
            with open(history_path, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    total_rows += 1
                    if not header_logged:
                        logger.info(f"stats_history CSV 列名: {list(row.keys())}")
                        header_logged = True
                    name = row.get("Name", "")
                    avg_val = get_col(row, "Average Response Time", "Average", "avg_response_time", "avg")
                    record = {
                        "timestamp": row.get("Timestamp", ""),
                        "users": int(get_col(row, "User Count", "users", "user_count")),
                        "rps": get_col(row, "Requests/s", "rps", "throughput"),
                        "failures_per_s": get_col(row, "Failures/s", "failures_per_s", "failures"),
                        "median": get_col(row, "Median Response Time", "50%", "Median", "p50"),
                        "p50": get_col(row, "50%", "Median Response Time", "p50"),
                        "p95": get_col(row, "95%", "p95"),
                        "p99": get_col(row, "99%", "p99"),
                        "avg": avg_val,
                        "average": avg_val,
                    }
                    if name == "Aggregated":
                        aggregate.append(record)
                    elif name:
                        if name not in by_endpoint:
                            by_endpoint[name] = []
                        by_endpoint[name].append(record)
        except Exception as e:
            logger.warning(f"解析 stats_history CSV 失败: {e}")

        if total_rows > 0 and len(aggregate) == 0:
            logger.warning(f"stats_history CSV 有 {total_rows} 行但无 Aggregated 行")
        else:
            if aggregate:
                logger.info(f"stats_history 聚合首条: users={aggregate[0].get('users')}, rps={aggregate[0].get('rps')}, avg={aggregate[0].get('avg')}, p50={aggregate[0].get('p50')}")
            logger.info(f"stats_history 解析完成: 聚合 {len(aggregate)} 条, {len(by_endpoint)} 个接口趋势 (共 {total_rows} 行)")

        # 修复：Aggregated 行 avg 可能为0，用各接口同时间戳的 avg 平均值替代
        if by_endpoint and aggregate:
            # 按时间戳索引各接口记录
            endpoint_by_ts = {}
            for ep_name, ep_records in by_endpoint.items():
                for rec in ep_records:
                    ts = rec.get("timestamp", "")
                    if ts not in endpoint_by_ts:
                        endpoint_by_ts[ts] = []
                    endpoint_by_ts[ts].append(rec)
            # 对每条 aggregate 记录，用各接口 avg 平均值计算
            for agg_rec in aggregate:
                ts = agg_rec.get("timestamp", "")
                ep_recs = endpoint_by_ts.get(ts, [])
                if ep_recs:
                    avg_vals = [r.get("avg", 0) for r in ep_recs if r.get("avg", 0) > 0]
                    if avg_vals:
                        calc_avg = sum(avg_vals) / len(avg_vals)
                        # 如果原 avg 为0或异常，用计算值替代
                        if not agg_rec.get("avg") or agg_rec.get("avg") == 0:
                            agg_rec["avg"] = round(calc_avg, 2)
                            agg_rec["average"] = round(calc_avg, 2)
                        # 同时用各接口 rps 总和修正 aggregate rps
                        rps_vals = [r.get("rps", 0) for r in ep_recs]
                        if rps_vals and (not agg_rec.get("rps") or agg_rec.get("rps") == 0):
                            agg_rec["rps"] = round(sum(rps_vals), 2)
            logger.info(f"已用各接口平均值修复 aggregate avg，首条 avg={aggregate[0].get('avg') if aggregate else 'N/A'}")

        return {"aggregate": aggregate, "by_endpoint": by_endpoint}

    def _cleanup_csv_files(self, run_id: int):
        """清理 Locust CSV 临时文件"""
        for suffix in ["_stats.csv", "_failures.csv", "_stats_history.csv", "_exceptions.csv"]:
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
