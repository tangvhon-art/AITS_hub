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

        exec_result = {
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

        # 独立场景执行（非测试计划内）时发送通知
        project_id = scenario.get("project_id")
        if project_id:
            try:
                from app.services.notification_service import notify_event
                notify_event(
                    project_id,
                    "api.scenario.completed",
                    {
                        "scenario_id": scenario.get("id"),
                        "scenario_name": scenario.get("name", ""),
                        "execution_id": scenario.get("execution_id"),
                        "environment_name": scenario.get("environment_name", "默认环境"),
                        "total_steps": exec_result["total_steps"],
                        "passed_steps": exec_result["passed_steps"],
                        "failed_steps": exec_result["failed_steps"],
                        "total_duration": exec_result["total_duration"],
                    },
                    triggered_by=scenario.get("triggered_by"),
                )
            except Exception as notify_e:
                logger.warning(f"发送场景执行通知失败（不影响业务）: {notify_e}")

        return exec_result

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

        # 原始请求上下文（变量替换前）
        base_url = self.variable_engine.get("base_url") or ""
        raw_url = base_url + path
        raw_headers = request_config.get("headers", api.headers) or []
        raw_params = request_config.get("query_params", api.query_params) or []
        raw_body_type = request_config.get("body_type", api.body_type) or "raw"

        # 第一遍：替换静态环境变量
        resolved_url = self.variable_engine.replace(raw_url)
        resolved_headers = self.variable_engine.replace_headers(raw_headers)
        resolved_params = self.variable_engine.replace_params(raw_params)
        body_type = request_config.get("body_type", api.body_type)
        resolved_body = self.variable_engine.replace_body(body_type, request_config.get("body_content", api.body_content))

        # Query Params 覆盖：{"name":"${name}"} 格式，合并到原参数列表
        params_override = request_config.get("query_params_override")
        if params_override:
            try:
                if isinstance(params_override, str):
                    override_str = self.variable_engine.replace(params_override)
                    override_dict = json.loads(override_str)
                else:
                    override_dict = params_override
                if isinstance(override_dict, dict):
                    resolved_params = self._merge_query_params(resolved_params, override_dict)
                    logger.info(f"步骤 {step.get('step_name')} QueryParams已合并覆盖: {override_dict}")
            except Exception as e:
                logger.warning(f"QueryParams覆盖合并失败: {e}，使用原参数")

        # 请求参数覆盖：深度合并 body_override 到原请求体
        body_override = request_config.get("body_override")
        if body_override:
            try:
                if isinstance(body_override, str):
                    override_str = self.variable_engine.replace(body_override)
                    override_data = json.loads(override_str)
                else:
                    override_data = body_override
                if isinstance(override_data, dict) and isinstance(resolved_body, dict):
                    resolved_body = self._deep_merge(resolved_body, override_data)
                    logger.info(f"步骤 {step.get('step_name')} 请求体已合并覆盖参数")
                elif isinstance(override_data, dict):
                    resolved_body = override_data
            except Exception as e:
                logger.warning(f"请求参数覆盖合并失败: {e}，使用原请求体")

        # 执行环境脚本变量（用已解析的 body/headers，保证签名与实际请求一致）
        result.console_log += self.variable_engine.run_environment_scripts({
            "method": method,
            "url": resolved_url,
            "headers": resolved_headers,
            "query_params": resolved_params,
            "body": HttpClient.serialize_body(body_type, resolved_body),
            "body_type": body_type or "raw",
        })

        # 前置脚本
        if step.get("pre_script"):
            script_result = self.script_engine.execute(
                step["pre_script"],
                environment_vars=self.variable_engine.environment_vars,
                global_vars=self.variable_engine.global_vars,
                request={
                    "method": method,
                    "url": resolved_url,
                    "headers": resolved_headers,
                    "query_params": resolved_params,
                    "body": HttpClient.serialize_body(body_type, resolved_body),
                    "body_type": body_type or "raw",
                },
            )
            for k, v in script_result.variables.items():
                self.variable_engine.set("scenario", k, v)
            result.console_log += script_result.output

        # 第二遍：替换脚本生成的变量（如 {{signature}}），从已覆盖参数的基础上重新解析
        url = self.variable_engine.replace(resolved_url)
        if resolved_url != url:
            logger.info(f"步骤 {step.get('step_name')} URL变量替换: {resolved_url} -> {url}")
        headers = self.variable_engine.replace_headers(resolved_headers)
        params = self.variable_engine.replace_params(resolved_params)
        body_content = self.variable_engine.replace_body(body_type, resolved_body)

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
                request={
                    "method": method,
                    "url": url,
                    "headers": raw_headers,
                    "query_params": raw_params,
                    "body": HttpClient.serialize_body(body_type, body_content),
                    "body_type": body_type or "raw",
                },
                response=response.to_dict(),
            )
            for k, v in script_result.variables.items():
                self.variable_engine.set("scenario", k, v)
            result.console_log += script_result.output

        # 提取变量
        self._extract_variables(step.get("id"), response)

        # 断言：优先使用步骤自带的断言，否则尝试从关联用例加载
        assertions = step.get("assertions", [])
        if not assertions and step.get("case_id"):
            from app.models.api_test import ApiCaseAssertion
            case_id = step.get("case_id")
            case_assertions = self.db.query(ApiCaseAssertion).filter(
                ApiCaseAssertion.case_id == case_id,
                ApiCaseAssertion.enabled == True,
            ).order_by(ApiCaseAssertion.sort_order).all()
            assertions = [
                {
                    "assert_type": a.assert_type,
                    "assert_target": a.assert_target,
                    "operator": a.operator,
                    "expected_value": a.expected_value,
                    "enabled": a.enabled,
                }
                for a in case_assertions
            ]

        if assertions:
            assertion_results = self.assertion_engine.run_all(assertions, response)
            result.assertions = [a.to_dict() for a in assertion_results]
            all_passed = all(a.passed for a in assertion_results) if assertion_results else True
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

        # 如果关联了接口，使用接口的 method 和 path
        if case.api_id:
            from app.models.api_test import ApiDefinition
            api_def = self.db.query(ApiDefinition).filter(ApiDefinition.id == case.api_id).first()
            if api_def:
                method = api_def.method or "GET"
                path = api_def.path or ""
            else:
                method = case.method or "GET"
                path = case.path or ""
        else:
            method = case.method or "GET"
            path = case.path or ""

        # 原始请求上下文（变量替换前）
        base_url = self.variable_engine.get("base_url") or ""
        raw_url = base_url + path
        raw_headers = case.headers or []
        raw_params = case.query_params or []

        # 第一遍：替换静态环境变量
        resolved_url = self.variable_engine.replace(raw_url)
        resolved_headers = self.variable_engine.replace_headers(raw_headers)
        resolved_params = self.variable_engine.replace_params(raw_params)
        body_type = case.body_type
        resolved_body = self.variable_engine.replace_body(body_type, case.body_content)

        # Query Params 覆盖（用例步骤同样支持）
        request_config = step.get("request_config", {})
        params_override = request_config.get("query_params_override")
        if params_override:
            try:
                if isinstance(params_override, str):
                    override_str = self.variable_engine.replace(params_override)
                    override_dict = json.loads(override_str)
                else:
                    override_dict = params_override
                if isinstance(override_dict, dict):
                    resolved_params = self._merge_query_params(resolved_params, override_dict)
                    logger.info(f"用例步骤 {step.get('step_name')} QueryParams已合并覆盖: {override_dict}")
            except Exception as e:
                logger.warning(f"用例步骤 QueryParams覆盖合并失败: {e}")

        # 执行环境脚本变量（用已解析的 body/headers）
        result.console_log += self.variable_engine.run_environment_scripts({
            "method": method,
            "url": resolved_url,
            "headers": resolved_headers,
            "query_params": resolved_params,
            "body": HttpClient.serialize_body(body_type, resolved_body),
            "body_type": body_type or "raw",
        })

        # 前置脚本
        if case.pre_script:
            script_result = self.script_engine.execute(
                case.pre_script,
                environment_vars=self.variable_engine.environment_vars,
                global_vars=self.variable_engine.global_vars,
                request={
                    "method": method,
                    "url": resolved_url,
                    "headers": resolved_headers,
                    "query_params": resolved_params,
                    "body": HttpClient.serialize_body(body_type, resolved_body),
                    "body_type": body_type or "raw",
                },
            )
            for k, v in script_result.variables.items():
                self.variable_engine.set("scenario", k, v)
            result.console_log += script_result.output

        # 第二遍：替换脚本生成的变量（如 {{signature}}）
        url = self.variable_engine.replace(resolved_url)
        if resolved_url != url:
            logger.info(f"用例步骤 {step.get('step_name')} URL变量替换: {resolved_url} -> {url}")
        headers = self.variable_engine.replace_headers(resolved_headers)
        params = self.variable_engine.replace_params(resolved_params)
        body_content = self.variable_engine.replace_body(body_type, resolved_body)

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
                request={
                    "method": method,
                    "url": url,
                    "headers": raw_headers,
                    "query_params": raw_params,
                    "body": HttpClient.serialize_body(body_type, body_content),
                    "body_type": body_type or "raw",
                },
                response=response.to_dict(),
            )
            for k, v in script_result.variables.items():
                self.variable_engine.set("scenario", k, v)
            result.console_log += script_result.output

        # 提取变量（与 api 步骤一致）
        self._extract_variables(step.get("id"), response)

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

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """深度合并两个字典，override 覆盖 base 中的同名字段，嵌套字典递归合并"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ScenarioExecutor._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    @staticmethod
    def _merge_query_params(original: list, override: dict) -> list:
        """将 dict 格式的覆盖参数合并到 list 格式的原参数列表
        original: [{"key":"id","value":"123","enabled":true}, ...]
        override: {"name":"${name}", "page":"1"}
        已存在的 key 更新 value，不存在的 key 新增
        """
        if not original:
            original = []
        result = [dict(item) for item in original]  # 深拷贝
        existing_keys = {item.get("key"): idx for idx, item in enumerate(result) if item.get("key")}
        for key, value in override.items():
            if key in existing_keys:
                result[existing_keys[key]]["value"] = str(value)
                result[existing_keys[key]]["enabled"] = True
            else:
                result.append({"key": key, "value": str(value), "enabled": True})
        return result

    def _extract_variables(self, step_id: Optional[int], response: HttpResponse):
        """从响应中提取变量"""
        if not step_id:
            logger.warning(f"变量提取跳过: step_id 为空")
            return

        from app.models.api_test import ApiScenarioVariable

        variables = self.db.query(ApiScenarioVariable).filter(
            ApiScenarioVariable.step_id == step_id,
            ApiScenarioVariable.is_deleted == False,
        ).all()

        if not variables:
            logger.info(f"步骤 {step_id} 无配置的提取变量")
            return

        logger.info(f"步骤 {step_id} 开始提取 {len(variables)} 个变量")

        for var in variables:
            try:
                value = None
                if var.extract_type == "jsonpath":
                    try:
                        from jsonpath_ng import parse as jsonpath_parse
                        data = response.json()
                        if data:
                            expr = var.extract_expr
                            # 兼容 $data.xxx 写法（自动补全为 $.data.xxx）
                            if expr.startswith("$") and not expr.startswith("$.") and not expr.startswith("$["):
                                expr = "$." + expr[1:]
                            try:
                                matches = [m.value for m in jsonpath_parse(expr).find(data)]
                            except Exception:
                                # 兜底：再试原始表达式
                                matches = [m.value for m in jsonpath_parse(var.extract_expr).find(data)]
                            value = matches[0] if matches else var.default_value
                            logger.info(f"变量提取 {var.var_name}: expr={expr}, matches={len(matches)}, value={value}")
                        else:
                            logger.warning(f"变量提取 {var.var_name}: 响应体为空或非JSON")
                    except ImportError:
                        value = var.default_value
                    except Exception as je:
                        logger.warning(f"变量提取 {var.var_name}: JSON解析失败 {je}, body前200字={response.body[:200] if response.body else 'empty'}")
                elif var.extract_type == "regex":
                    import re
                    match = re.search(var.extract_expr, response.body or "")
                    value = match.group(1) if match else var.default_value
                elif var.extract_type == "header":
                    value = response.headers.get(var.extract_expr, var.default_value)
                elif var.extract_type == "cookie":
                    cookies = response.headers.get("set-cookie", "")
                    value = cookies if cookies else var.default_value

                if value is not None:
                    scope = var.scope if var.scope in ("scenario", "global") else "scenario"
                    self.variable_engine.set(scope, var.var_name, value)
                    logger.info(f"变量已设置: {var.var_name}={value} (scope={scope})")
                else:
                    logger.warning(f"变量提取 {var.var_name}: 值为None，使用默认值={var.default_value}")
            except Exception as e:
                logger.warning(f"变量提取失败 {var.var_name}: {e}")
