"""
测试计划异步执行任务
使用 Celery 执行测试计划，按顺序执行节点，支持失败策略和重试
"""
import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.celery_app import celery_app
from app.database import SessionLocal
from app.core.timezone import china_now_naive
from app.models.test_plan import (
    TestPlan, TestPlanItem, TestPlanExecution, TestPlanExecutionResult,
    TestEnvironment,
)
from app.models.api_test import ApiTestCase, ApiCaseAssertion, ApiScenario, ApiScenarioStep
from app.services.http_client import HttpClient
from app.services.variable_engine import VariableEngine
from app.services.assertion_engine import AssertionEngine
from app.services.script_engine import ScriptEngine
from app.services.scenario_executor import ScenarioExecutor

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="execute_test_plan")
def execute_test_plan_task(self, execution_id: int):
    """
    执行测试计划（Celery 任务）
    按顺序执行每个节点，支持失败策略和重试
    """
    db = SessionLocal()
    try:
        execution = db.query(TestPlanExecution).filter(
            TestPlanExecution.id == execution_id
        ).first()
        if not execution:
            logger.error(f"执行记录不存在: {execution_id}")
            return

        plan = db.query(TestPlan).filter(TestPlan.id == execution.plan_id).first()
        if not plan:
            execution.status = "failed"
            execution.error_message = "测试计划不存在"
            execution.finished_at = china_now_naive()
            db.commit()
            return

        # 检查是否已被取消
        db.refresh(execution)
        if execution.status == "cancelled":
            return

        # 标记为执行中
        execution.status = "running"
        execution.started_at = china_now_naive()
        plan.status = "running"
        db.commit()

        # 加载环境变量
        var_engine = VariableEngine()
        environment = None
        if plan.environment_id:
            env = db.query(TestEnvironment).filter(TestEnvironment.id == plan.environment_id).first()
            if env:
                environment = {"base_url": env.base_url, "config": env.config or {}}
                var_engine.load_environment(env.config or {})
                var_engine.set("environment", "base_url", env.base_url)

        # 获取启用的节点
        items = db.query(TestPlanItem).filter(
            TestPlanItem.plan_id == plan.id,
            TestPlanItem.enabled == True,
            TestPlanItem.is_deleted == False
        ).order_by(TestPlanItem.sort_order).all()

        execution.total_items = len(items)
        db.commit()

        passed = 0
        failed = 0
        skipped = 0
        stop_execution = False

        for idx, item in enumerate(items):
            # 检查是否被取消
            db.refresh(execution)
            if execution.status == "cancelled":
                stop_execution = True
                # 剩余节点标记为跳过
                result = TestPlanExecutionResult(
                    execution_id=execution.id,
                    item_id=item.id,
                    item_type=item.item_type,
                    ref_id=item.ref_id,
                    item_name=item.item_name,
                    sort_order=idx,
                    status="skipped",
                    error_message="执行被取消",
                    started_at=china_now_naive(),
                    finished_at=china_now_naive(),
                )
                db.add(result)
                skipped += 1
                continue

            if stop_execution:
                result = TestPlanExecutionResult(
                    execution_id=execution.id,
                    item_id=item.id,
                    item_type=item.item_type,
                    ref_id=item.ref_id,
                    item_name=item.item_name,
                    sort_order=idx,
                    status="skipped",
                    error_message="前置节点失败，停止执行",
                    started_at=china_now_naive(),
                    finished_at=china_now_naive(),
                )
                db.add(result)
                skipped += 1
                continue

            # 执行节点
            result = asyncio.run(_execute_item(db, item, idx, execution.id, var_engine, environment))
            db.add(result)
            db.flush()

            if result.status == "passed":
                passed += 1
            elif result.status == "failed" or result.status == "error":
                failed += 1
                if item.fail_strategy == "stop":
                    stop_execution = True
            else:
                skipped += 1

            # 更新统计
            execution.passed_count = passed
            execution.failed_count = failed
            execution.skipped_count = skipped
            total = passed + failed + skipped
            execution.pass_rate = round(passed / total * 100, 2) if total > 0 else 0
            db.commit()

        # 执行完成
        execution.status = "completed" if failed == 0 else "failed"
        execution.finished_at = china_now_naive()
        total = passed + failed + skipped
        execution.pass_rate = round(passed / total * 100, 2) if total > 0 else 0

        # 更新计划状态和最近通过率
        plan.status = "completed" if failed == 0 else "draft"
        plan.last_pass_rate = execution.pass_rate
        plan.pass_rate = int(execution.pass_rate)
        plan.passed_cases = passed
        plan.failed_cases = failed
        plan.total_cases = total

        db.commit()
        logger.info(f"测试计划执行完成: execution_id={execution_id}, passed={passed}, failed={failed}, skipped={skipped}")

    except Exception as e:
        logger.exception(f"测试计划执行异常: {e}")
        try:
            execution = db.query(TestPlanExecution).filter(
                TestPlanExecution.id == execution_id
            ).first()
            if execution:
                execution.status = "failed"
                execution.error_message = str(e)
                execution.finished_at = china_now_naive()
                plan = db.query(TestPlan).filter(TestPlan.id == execution.plan_id).first()
                if plan:
                    plan.status = "draft"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


async def _execute_item(
    db, item: TestPlanItem, idx: int, execution_id: int,
    var_engine: VariableEngine, environment: Optional[Dict]
) -> TestPlanExecutionResult:
    """执行单个节点"""
    result = TestPlanExecutionResult(
        execution_id=execution_id,
        item_id=item.id,
        item_type=item.item_type,
        ref_id=item.ref_id,
        item_name=item.item_name,
        sort_order=idx,
        status="pending",
        started_at=china_now_naive(),
    )

    start_time = time.time()
    max_retries = item.max_retries or 0

    for attempt in range(max_retries + 1):
        result.retry_count = attempt
        try:
            if item.item_type == "case":
                await _execute_case_node(db, item, result, var_engine, environment)
            elif item.item_type == "scenario":
                await _execute_scenario_node(db, item, result, var_engine, environment)
            else:
                result.status = "error"
                result.error_message = f"不支持的节点类型: {item.item_type}"

            if result.status == "passed":
                break
            if attempt < max_retries:
                await asyncio.sleep(1)
        except Exception as e:
            result.status = "error"
            result.error_message = str(e)
            if attempt < max_retries:
                await asyncio.sleep(1)

    result.finished_at = china_now_naive()
    result.duration_ms = int((time.time() - start_time) * 1000)
    return result


async def _execute_case_node(
    db, item: TestPlanItem, result: TestPlanExecutionResult,
    var_engine: VariableEngine, environment: Optional[Dict]
):
    """执行接口用例节点"""
    case = db.query(ApiTestCase).filter(ApiTestCase.id == item.ref_id).first()
    if not case:
        result.status = "error"
        result.error_message = f"接口用例不存在: {item.ref_id}"
        return

    method = case.method or "GET"
    base_url = var_engine.get("base_url") or ""
    url = var_engine.replace(base_url + (case.path or ""))
    headers = var_engine.replace_headers(case.headers)
    params = var_engine.replace_params(case.query_params)
    body_content = var_engine.replace_body(case.body_type, case.body_content)

    # 前置脚本
    script_engine = ScriptEngine()
    console_log = ""
    if case.pre_script:
        script_result = script_engine.execute(
            case.pre_script,
            environment_vars=var_engine.environment_vars,
            global_vars=var_engine.global_vars,
            request={"method": method, "url": url},
        )
        for k, v in script_result.variables.items():
            var_engine.set("scenario", k, v)
        console_log += script_result.output
        url = var_engine.replace(base_url + (case.path or ""))
        headers = var_engine.replace_headers(case.headers)
        params = var_engine.replace_params(case.query_params)
        body_content = var_engine.replace_body(case.body_type, case.body_content)

    result.request_data = {
        "method": method,
        "url": url,
        "headers": {h.get("key", ""): h.get("value", "") for h in headers if h.get("enabled", True)},
        "body": body_content,
    }

    # 发送请求
    http_client = HttpClient(timeout=item.timeout if item.timeout > 0 else 30)
    response = await http_client.asend(
        method=method, url=url, headers=headers, params=params,
        body_type=case.body_type, body_content=body_content,
    )

    result.response_data = {
        "status_code": response.status_code,
        "body": response.body,
        "headers": response.headers,
        "duration": response.elapsed_ms,
        "size": response.size,
    }

    # 后置脚本
    if case.post_script:
        script_result = script_engine.execute(
            case.post_script,
            environment_vars=var_engine.environment_vars,
            global_vars=var_engine.global_vars,
            request={"method": method, "url": url},
            response=response.to_dict(),
        )
        console_log += script_result.output

    # 断言
    assertions = db.query(ApiCaseAssertion).filter(
        ApiCaseAssertion.case_id == case.id,
        ApiCaseAssertion.enabled == True,
    ).order_by(ApiCaseAssertion.sort_order).all()

    assertion_engine = AssertionEngine()
    assertion_dicts = [
        {"assert_type": a.assert_type, "assert_target": a.assert_target,
         "operator": a.operator, "expected_value": a.expected_value, "enabled": a.enabled}
        for a in assertions
    ]
    assertion_results = assertion_engine.run_all(assertion_dicts, response)
    result.assertions = [a.to_dict() for a in assertion_results]

    all_passed = all(a.passed for a in assertion_results) and not response.error
    result.status = "passed" if all_passed else "failed"
    if not all_passed:
        failed = [a for a in assertion_results if not a.passed]
        result.error_message = response.error or f"{len(failed)}个断言失败"


async def _execute_scenario_node(
    db, item: TestPlanItem, result: TestPlanExecutionResult,
    var_engine: VariableEngine, environment: Optional[Dict]
):
    """执行场景编排节点"""
    scenario = db.query(ApiScenario).filter(ApiScenario.id == item.ref_id).first()
    if not scenario:
        result.status = "error"
        result.error_message = f"场景编排不存在: {item.ref_id}"
        return

    # 获取场景步骤
    steps = db.query(ApiScenarioStep).filter(
        ApiScenarioStep.scenario_id == scenario.id,
        ApiScenarioStep.is_deleted == False
    ).order_by(ApiScenarioStep.sort_order).all()

    step_dicts = []
    for step in steps:
        step_dict = {
            "id": step.id,
            "step_type": step.step_type,
            "step_name": step.step_name,
            "sort_order": step.sort_order,
            "enabled": step.enabled,
            "api_id": step.api_id,
            "case_id": step.case_id,
            "request_config": step.request_config or {},
            "script_content": step.script_content,
            "wait_seconds": step.wait_seconds,
            "condition_expr": step.condition_expr,
            "loop_config": step.loop_config or {},
            "pre_script": step.pre_script,
            "post_script": step.post_script,
            "continue_on_failure": step.continue_on_failure,
            "max_retries": step.max_retries,
            "assertions": [],
        }
        step_dicts.append(step_dict)

    scenario_dict = {
        "id": scenario.id,
        "name": scenario.name,
        "pre_script": scenario.pre_script,
        "post_script": scenario.post_script,
    }

    # 使用场景执行引擎
    executor = ScenarioExecutor(db, variable_engine=var_engine)
    exec_result = await executor.execute_scenario(
        scenario=scenario_dict,
        steps=step_dicts,
        environment=environment,
    )

    result.status = "passed" if exec_result.get("failed_steps", 0) == 0 else "failed"
    result.request_data = {"scenario": scenario.name, "steps": len(step_dicts)}
    result.response_data = {
        "total_steps": exec_result.get("total_steps", 0),
        "passed_steps": exec_result.get("passed_steps", 0),
        "failed_steps": exec_result.get("failed_steps", 0),
        "skipped_steps": exec_result.get("skipped_steps", 0),
        "pass_rate": exec_result.get("pass_rate", 0),
        "total_duration": exec_result.get("total_duration", 0),
    }
    result.assertions = exec_result.get("results", [])
    result.extracted_vars = dict(var_engine.scenario_vars)

    if result.status == "failed":
        result.error_message = f"场景执行失败: {exec_result.get('failed_steps', 0)}个步骤失败"
