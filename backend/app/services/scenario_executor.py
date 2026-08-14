"""
场景执行引擎
支持6种步骤类型: api, case, script, wait, condition, loop
"""
import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from app.core.timezone import china_now_naive
from app.services.http_client import HttpClient, HttpResponse
from app.services.variable_engine import VariableEngine
from app.services.assertion_engine import AssertionEngine
from app.services.script_engine import ScriptEngine

logger = logging.getLogger(__name__)


class StepExecutionResult:
    """步骤执行结果"""

    def __init__(self):
        self.step_id: Optional[int] = None
        self.step_name: str = ""
        self.sort_order: int = 0
        self.status: str = "pending"
        self.request_method: str = ""
        self.request_url: str = ""
        self.request_headers: Dict = {}
        self.request_body: str = ""
        self.response_status: Optional[int] = None
        self.response_time: float = 0
        self.response_size: int = 0
        self.response_headers: Dict = {}
        self.response_body: str = ""
        self.assertions: List[Dict] = []
        self.console_log: str = ""
        self.error_message: str = ""
        self.retry_count: int = 0
        self.started_at = None
        self.completed_at = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "step_name": self.step_name,
            "sort_order": self.sort_order,
            "status": self.status,
            "request_method": self.request_method,
            "request_url": self.request_url,
            "request_headers": self.request_headers,
            "request_body": self.request_body,
            "response_status": self.response_status,
            "response_time": self.response_time,
            "response_size": self.response_size,
            "response_headers": self.response_headers,
            "response_body": self.response_body,
            "assertions": self.assertions,
            "console_log": self.console_log,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class ScenarioExecutor:
    """场景执行引擎"""

    def __init__(self, db_session, variable_engine: Optional[VariableEngine] = None):
        self.db = db_session
        self.http_client = HttpClient()
        self.assertion_engine = AssertionEngine()
        self.script_engine = ScriptEngine()
        self.variable_engine = variable_engine or VariableEngine()
        self.results: List[StepExecutionResult] = []

    async def execute_scenario(self, scenario: Dict[str, Any], steps: List[Dict[str, Any]],
                               environment: Optional[Dict[str, Any]] = None,
                               extra_vars: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        执行测试场景
        返回汇总结果
        """
        start_time = time.time()
        self.results = []

        # 加载环境变量
        if environment:
            self.variable_engine.load_environment(environment.get("config", {}))
            base_url = environment.get("base_url", "")
            self.variable_engine.set("environment", "base_url", base_url)

        # 加载额外变量
        if extra_vars:
            self.variable_engine.load_from_dict("scenario", extra_vars)

        # 场景前置脚本
        if scenario.get("pre_script"):
            script_result = self.script_engine.execute(
                scenario["pre_script"],
                environment_vars=self.variable_engine.environment_vars,
                global_vars=self.variable_engine.global_vars,
                request={},
            )
            if script_result.variables:
                for k, v in script_result.variables.items():
                    self.variable_engine.set("scenario", k, v)

        # 执行步骤
        passed = 0
        failed = 0
        skipped = 0

        for idx, step in enumerate(steps):
            if not step.get("enabled", True):
                result = StepExecutionResult()
                result.step_id = step.get("id")
                result.step_name = step.get("step_name", f"步骤{idx+1}")
                result.sort_order = idx
                result.status = "skipped"
                self.results.append(result)
                skipped += 1
                continue

            result = await self._execute_step(step, idx)
            self.results.append(result)

            if result.status == "passed":
                passed += 1
            elif result.status == "failed":
                failed += 1
                if not step.get("continue_on_failure", False):
                    # 后续步骤标记为跳过
                    for remaining_step in steps[idx + 1:]:
                        skip_result = StepExecutionResult()
                        skip_result.step_id = remaining_step.get("id")
                        skip_result.step_name = remaining_step.get("step_name", "")
                        skip_result.sort_order = steps.index(remaining_step)
                        skip_result.status = "skipped"
                        self.results.append(skip_result)
                        skipped += 1
                    break

        # 场景后置脚本
        if scenario.get("post_script"):
            self.script_engine.execute(
                scenario["post_script"],
                environment_vars=self.variable_engine.environment_vars,
                global_vars=self.variable_engine.global_vars,
                request={},
            )

        total_duration = time.time() - start_time
        total = len(self.results)
        pass_rate = (passed / total * 100) if total > 0 else 0

        return {
            "total_steps": total,
            "passed_steps": passed,
            "failed_steps": failed,
            "skipped_steps": skipped,
            "pass_rate": round(pass_rate, 2),
            "total_duration": round(total_duration, 3),
            "avg_duration": round(total_duration / total, 3) if total > 0 else 0,
            "status": "passed" if failed == 0 else ("partial" if passed > 0 else "failed"),
            "results": [r.to_dict() for r in self.results],
        }

    async def _execute_step(self, step: Dict[str, Any], index: int) -> StepExecutionResult:
        """执行单个步骤"""
        result = StepExecutionResult()
        result.step_id = step.get("id")
        result.step_name = step.get("step_name", f"步骤{index+1}")
        result.sort_order = index
        result.started_at = china_now_naive()

        step_type = step.get("step_type", "api")
        max_retries = step.get("max_retries", 0)

        for attempt in range(max_retries + 1):
            result.retry_count = attempt
            try:
                if step_type == "api":
                    await self._execute_api_step(step, result)
                elif step_type == "case":
                    await self._execute_case_step(step, result)
                elif step_type == "script":
                    self._execute_script_step(step, result)
                elif step_type == "wait":
                    self._execute_wait_step(step, result)
                elif step_type == "condition":
                    self._execute_condition_step(step, result)
                elif step_type == "loop":
                    await self._execute_loop_step(step, result)
                else:
                    result.status = "failed"
                    result.error_message = f"不支持的步骤类型: {step_type}"

                if result.status == "passed":
                    break
                if attempt < max_retries:
                    await asyncio.sleep(1)
            except Exception as e:
                result.status = "failed"
                result.error_message = str(e)
                if attempt < max_retries:
                    await asyncio.sleep(1)

        result.completed_at = china_now_naive()
        return result

    async def _execute_api_step(self, step: Dict[str, Any], result: StepExecutionResult):
        """执行 API 步骤"""
        from app.models.api_test import ApiDefinition

        api_id = step.get("api_id")
        if not api_id:
            result.status = "failed"
            result.error_message = "未指定接口ID"
            return

        api = self.db.query(ApiDefinition).filter(ApiDefinition.id == api_id).first()
        if not api:
            result.status = "failed"
            result.error_message = f"接口不存在: {api_id}"
            return

        # 合并请求配置
        request_config = step.get("request_config", {})
        method = request_config.get("method", api.method)
        path = request_config.get("path", api.path)

        # 变量替换
        base_url = self.variable_engine.get("base_url") or ""
        url = self.variable_engine.replace(base_url + path)
        headers = self.variable_engine.replace_headers(request_config.get("headers", api.headers))
        params = self.variable_engine.replace_params(request_config.get("query_params", api.query_params))
        body_type = request_config.get("body_type", api.body_type)
        body_content = self.variable_engine.replace_body(body_type, request_config.get("body_content", api.body_content))

        # 前置脚本
        if step.get("pre_script"):
            script_result = self.script_engine.execute(
                step["pre_script"],
                environment_vars=self.variable_engine.environment_vars,
                global_vars=self.variable_engine.global_vars,
                request={"method": method, "url": url},
            )
            for k, v in script_result.variables.items():
                self.variable_engine.set("scenario", k, v)
            result.console_log += script_result.output

        result.request_method = method
        result.request_url = url
        result.request_headers = {h.get("key", ""): h.get("value", "") for h in headers if h.get("enabled", True)}
        result.request_body = json.dumps(body_content, ensure_ascii=False) if body_content else ""

        # 发送请求
        response = await self.http_client.asend(
            method=method, url=url, headers=headers, params=params,
            body_type=body_type, body_content=body_content,
        )

        result.response_status = response.status_code
        result.response_time = response.elapsed_ms
        result.response_size = response.size
        result.response_headers = response.headers
        result.response_body = response.body

        if response.error:
            result.status = "failed"
            result.error_message = response.error
            return

        # 后置脚本 + 变量提取
        if step.get("post_script"):
            script_result = self.script_engine.execute(
                step["post_script"],
                environment_vars=self.variable_engine.environment_vars,
                global_vars=self.variable_engine.global_vars,
                request={"method": method, "url": url},
                response=response.to_dict(),
            )
            for k, v in script_result.variables.items():
                self.variable_engine.set("scenario", k, v)
            result.console_log += script_result.output

        # 提取变量
        self._extract_variables(step.get("id"), response)

        # 断言
        assertions = step.get("assertions", [])
        if assertions:
            assertion_results = self.assertion_engine.run_all(assertions, response)
            result.assertions = [a.to_dict() for a in assertion_results]
            all_passed = all(a.passed for a in assertion_results)
            result.status = "passed" if all_passed else "failed"
            if not all_passed:
                failed = [a for a in assertion_results if not a.passed]
                result.error_message = f"{len(failed)}个断言失败"
        else:
            result.status = "passed" if response.status_code < 400 else "failed"

    async def _execute_case_step(self, step: Dict[str, Any], result: StepExecutionResult):
        """执行用例步骤（复用用例执行逻辑）"""
        from app.models.api_test import ApiTestCase, ApiCaseAssertion

        case_id = step.get("case_id")
        if not case_id:
            result.status = "failed"
            result.error_message = "未指定用例ID"
            return

        case = self.db.query(ApiTestCase).filter(ApiTestCase.id == case_id).first()
        if not case:
            result.status = "failed"
            result.error_message = f"用例不存在: {case_id}"
            return

        # 构建请求
        method = case.method or "GET"
        path = case.path or ""
        base_url = self.variable_engine.get("base_url") or ""
        url = self.variable_engine.replace(base_url + path)
        headers = self.variable_engine.replace_headers(case.headers)
        params = self.variable_engine.replace_params(case.query_params)
        body_type = case.body_type
        body_content = self.variable_engine.replace_body(body_type, case.body_content)

        # 前置脚本
        if case.pre_script:
            script_result = self.script_engine.execute(
                case.pre_script,
                environment_vars=self.variable_engine.environment_vars,
                global_vars=self.variable_engine.global_vars,
                request={"method": method, "url": url},
            )
            for k, v in script_result.variables.items():
                self.variable_engine.set("scenario", k, v)
            result.console_log += script_result.output

        result.request_method = method
        result.request_url = url
        result.request_headers = {h.get("key", ""): h.get("value", "") for h in headers if h.get("enabled", True)}
        result.request_body = json.dumps(body_content, ensure_ascii=False) if body_content else ""

        response = await self.http_client.asend(
            method=method, url=url, headers=headers, params=params,
            body_type=body_type, body_content=body_content,
        )

        result.response_status = response.status_code
        result.response_time = response.elapsed_ms
        result.response_size = response.size
        result.response_headers = response.headers
        result.response_body = response.body

        if response.error:
            result.status = "failed"
            result.error_message = response.error
            return

        # 后置脚本
        if case.post_script:
            script_result = self.script_engine.execute(
                case.post_script,
                environment_vars=self.variable_engine.environment_vars,
                global_vars=self.variable_engine.global_vars,
                request={"method": method, "url": url},
                response=response.to_dict(),
            )
            for k, v in script_result.variables.items():
                self.variable_engine.set("scenario", k, v)
            result.console_log += script_result.output

        # 断言
        assertions = self.db.query(ApiCaseAssertion).filter(
            ApiCaseAssertion.case_id == case_id,
            ApiCaseAssertion.enabled == True,
        ).order_by(ApiCaseAssertion.sort_order).all()

        assertion_dicts = [
            {"assert_type": a.assert_type, "assert_target": a.assert_target,
             "operator": a.operator, "expected_value": a.expected_value, "enabled": a.enabled}
            for a in assertions
        ]

        if assertion_dicts:
            assertion_results = self.assertion_engine.run_all(assertion_dicts, response)
            result.assertions = [a.to_dict() for a in assertion_results]
            all_passed = all(a.passed for a in assertion_results)
            result.status = "passed" if all_passed else "failed"
            if not all_passed:
                result.error_message = "断言失败"
        else:
            result.status = "passed" if response.status_code < 400 else "failed"

    def _execute_script_step(self, step: Dict[str, Any], result: StepExecutionResult):
        """执行脚本步骤"""
        script = step.get("script_content", "")
        if not script:
            result.status = "passed"
            return

        script_result = self.script_engine.execute(
            script,
            environment_vars=self.variable_engine.environment_vars,
            global_vars=self.variable_engine.global_vars,
            request={},
        )

        for k, v in script_result.variables.items():
            self.variable_engine.set("scenario", k, v)

        result.console_log = script_result.output
        result.status = "passed" if script_result.success else "failed"
        if not script_result.success:
            result.error_message = script_result.error

    def _execute_wait_step(self, step: Dict[str, Any], result: StepExecutionResult):
        """执行等待步骤"""
        seconds = step.get("wait_seconds", 1)
        time.sleep(seconds)
        result.status = "passed"
        result.console_log = f"等待 {seconds} 秒"

    def _execute_condition_step(self, step: Dict[str, Any], result: StepExecutionResult):
        """执行条件步骤（简化：判断变量是否存在/等于）"""
        expr = step.get("condition_expr", "")
        if not expr:
            result.status = "passed"
            return

        # 简化条件判断: var == value 或 var != value
        try:
            if "==" in expr:
                parts = expr.split("==")
                var_name = parts[0].strip()
                expected = parts[1].strip().strip('"').strip("'")
                actual = str(self.variable_engine.get(var_name) or "")
                result.status = "passed" if actual == expected else "skipped"
            elif "!=" in expr:
                parts = expr.split("!=")
                var_name = parts[0].strip()
                expected = parts[1].strip().strip('"').strip("'")
                actual = str(self.variable_engine.get(var_name) or "")
                result.status = "passed" if actual != expected else "skipped"
            else:
                # 判断变量是否存在且为真
                actual = self.variable_engine.get(expr.strip())
                result.status = "passed" if actual else "skipped"
        except Exception as e:
            result.status = "failed"
            result.error_message = f"条件判断异常: {e}"

    async def _execute_loop_step(self, step: Dict[str, Any], result: StepExecutionResult):
        """执行循环步骤（简化：固定次数循环）"""
        loop_config = step.get("loop_config", {})
        loop_count = loop_config.get("count", 1)
        loop_var = loop_config.get("variable", "loop_index")

        for i in range(loop_count):
            self.variable_engine.set("local", loop_var, i)
            # 循环体中的子步骤执行（简化：只记录）
            pass

        result.status = "passed"
        result.console_log = f"循环执行 {loop_count} 次"

    def _extract_variables(self, step_id: Optional[int], response: HttpResponse):
        """从响应中提取变量"""
        if not step_id:
            return

        from app.models.api_test import ApiScenarioVariable

        variables = self.db.query(ApiScenarioVariable).filter(
            ApiScenarioVariable.step_id == step_id
        ).all()

        for var in variables:
            try:
                value = None
                if var.extract_type == "jsonpath":
                    try:
                        from jsonpath_ng import parse as jsonpath_parse
                        data = response.json()
                        if data:
                            matches = [m.value for m in jsonpath_parse(var.extract_expr).find(data)]
                            value = matches[0] if matches else var.default_value
                    except ImportError:
                        value = var.default_value
                elif var.extract_type == "regex":
                    import re
                    match = re.search(var.extract_expr, response.body)
                    value = match.group(1) if match else var.default_value
                elif var.extract_type == "header":
                    value = response.headers.get(var.extract_expr, var.default_value)
                elif var.extract_type == "cookie":
                    cookies = response.headers.get("set-cookie", "")
                    value = cookies if cookies else var.default_value

                if value is not None:
                    scope = var.scope if var.scope in ("scenario", "global") else "scenario"
                    self.variable_engine.set(scope, var.var_name, value)
            except Exception as e:
                logger.warning(f"变量提取失败 {var.var_name}: {e}")
