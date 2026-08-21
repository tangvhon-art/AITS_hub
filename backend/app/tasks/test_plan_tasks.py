"""
测试计划异步执行任务
使用 Celery 执行测试计划，支持接口(case/scenario)与UI(script/suite)混合编排。

核心设计：
- 全串行：所有节点按 sort_order 依次执行（不区分 API/UI 类型，用户要求单独串行）
- 失败隔离：fail_strategy="stop" 时，仅跳过后续**同类型**节点，**其他类型继续执行**
  - 例：case 失败 → 后续 case/scenario 被跳过，但 script/suite 正常执行；反之亦然
- 核心逻辑抽取到 _run_test_plan_execution，供 Celery 任务与线程降级共用
"""
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from app.celery_app import celery_app
from app.database import SessionLocal
from app.core.timezone import china_now_naive
from app.models.test_plan import (
    TestPlan, TestPlanItem, TestPlanExecution, TestPlanExecutionResult,
    TestEnvironment,
)
from app.models.api_test import ApiTestCase, ApiCaseAssertion, ApiScenario, ApiScenarioStep
from app.models.automation_script import AutomationScript
from app.models.automation_suite import AutomationSuite, AutomationSuiteRun
from app.models.report import TestReport
from app.services.http_client import HttpClient
from app.services.variable_engine import VariableEngine
from app.services.assertion_engine import AssertionEngine, AssertionResult
from app.services.script_engine import ScriptEngine
from app.services.scenario_executor import ScenarioExecutor
from app.services.notification_service import notify_event

logger = logging.getLogger(__name__)


# ============ 断言标准化 ============

def _normalize_assertion_result(a: AssertionResult, step_name: str = "") -> Dict[str, Any]:
    """将 AssertionResult 标准化为前端期望的断言字典（兼容字段名）"""
    return {
        "passed": a.passed,
        "assert_type": a.assert_type,
        "assert_target": a.target,
        "operator": a.operator,
        "expected_value": a.expected,
        "actual_value": a.actual,
        "message": a.message,
        "step_name": step_name,
    }


def _normalize_assertion_dict(a: Dict[str, Any], step_name: str = "") -> Dict[str, Any]:
    """将断言字典（来自场景步骤结果）标准化为前端期望的字段名"""
    return {
        "passed": a.get("passed"),
        "assert_type": a.get("assert_type", ""),
        "assert_target": a.get("assert_target") if a.get("assert_target") is not None else a.get("target", ""),
        "operator": a.get("operator", ""),
        "expected_value": a.get("expected_value") if a.get("expected_value") is not None else a.get("expected", ""),
        "actual_value": a.get("actual_value") if a.get("actual_value") is not None else a.get("actual", ""),
        "message": a.get("message", ""),
        "step_name": a.get("step_name") or step_name,
    }


# ============ 工具函数 ============

def _record_skipped(db, execution_id: int, item: TestPlanItem, reason: str):
    """记录跳过的节点结果"""
    result = TestPlanExecutionResult(
        execution_id=execution_id,
        item_id=item.id,
        item_type=item.item_type,
        ref_id=item.ref_id,
        item_name=item.item_name,
        sort_order=item.sort_order,
        status="skipped",
        error_message=reason,
        started_at=china_now_naive(),
        finished_at=china_now_naive(),
    )
    db.add(result)
    db.commit()


def _increment_stat(db, execution_id: int, status: str):
    """SQL 原子自增统计（单线程下仍安全，避免 ORM stale 问题）"""
    if status == "passed":
        db.query(TestPlanExecution).filter(TestPlanExecution.id == execution_id).update(
            {TestPlanExecution.passed_count: TestPlanExecution.passed_count + 1}
        )
    elif status in ("failed", "error"):
        db.query(TestPlanExecution).filter(TestPlanExecution.id == execution_id).update(
            {TestPlanExecution.failed_count: TestPlanExecution.failed_count + 1}
        )
    else:
        db.query(TestPlanExecution).filter(TestPlanExecution.id == execution_id).update(
            {TestPlanExecution.skipped_count: TestPlanExecution.skipped_count + 1}
        )
    db.commit()


def _is_cancelled(db, execution_id: int) -> bool:
    execution = db.query(TestPlanExecution).filter(
        TestPlanExecution.id == execution_id
    ).first()
    return bool(execution and execution.status == "cancelled")


def _node_family(item_type: str) -> str:
    """
    返回节点所属家族，用于 fail_strategy="stop" 的隔离。
    - "api" 家族: case / scenario
    - "ui"  家族: script / suite
    """
    if item_type in ("case", "scenario"):
        return "api"
    if item_type in ("script", "suite"):
        return "ui"
    return item_type or "unknown"


# ============ 主执行入口 ============

def _create_execution_report(db, plan: TestPlan, execution: TestPlanExecution):
    """
    P1-10: 测试计划执行完成后，创建 TestReport 记录。
    报告统计统一基于 TestPlanItem / TestPlanExecution 口径。
    """
    try:
        total = execution.total_items or 0
        passed = execution.passed_count or 0
        failed = execution.failed_count or 0
        skipped = execution.skipped_count or 0
        pass_rate = execution.pass_rate or 0
        duration = 0.0
        if execution.started_at and execution.finished_at:
            duration = round((execution.finished_at - execution.started_at).total_seconds(), 2)

        # 统计关联缺陷数（通过执行结果中的 error_message 简单关联，或后续扩展）
        report = TestReport(
            project_id=plan.project_id,
            version_id=plan.version_id,
            title=f"测试计划执行报告 - {plan.name}",
            report_type="execution",
            status="completed",
            content=f"# {plan.name} 执行报告\n\n"
                    f"- 执行时间：{execution.started_at} ~ {execution.finished_at}\n"
                    f"- 总节点数：{total}\n"
                    f"- 通过：{passed}\n"
                    f"- 失败：{failed}\n"
                    f"- 跳过：{skipped}\n"
                    f"- 通过率：{pass_rate}%\n"
                    f"- 总耗时：{duration}s\n",
            summary={
                "plan_id": plan.id,
                "plan_name": plan.name,
                "execution_id": execution.id,
                "total_items": total,
                "passed_count": passed,
                "failed_count": failed,
                "skipped_count": skipped,
                "pass_rate": pass_rate,
                "duration": duration,
                "trigger_type": execution.triggered_by,
                "executed_by": execution.triggered_by,
                "started_at": execution.started_at.isoformat() if execution.started_at else None,
                "finished_at": execution.finished_at.isoformat() if execution.finished_at else None,
            },
            total_cases=total,
            passed_cases=passed,
            failed_cases=failed,
            pass_rate=pass_rate,
            total_runs=1,
            avg_duration=duration,
            created_by=execution.triggered_by,
        )
        db.add(report)
        logger.info(f"已创建测试报告: plan={plan.name}, execution_id={execution.id}")
    except Exception as e:
        logger.exception(f"创建测试报告失败: {e}")


def _run_test_plan_execution(execution_id: int):
    """
    执行测试计划核心逻辑（同步，全串行）。
    所有节点按 sort_order 依次执行。
    fail_strategy="stop"：本节点失败，仅跳过后续**同家族**节点（api/ui 互相隔离）。
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

        db.refresh(execution)
        if execution.status == "cancelled":
            return

        execution.status = "running"
        execution.started_at = china_now_naive()
        plan.status = "running"
        db.commit()

        environment = None
        if plan.environment_id:
            env = db.query(TestEnvironment).filter(TestEnvironment.id == plan.environment_id).first()
            if env:
                environment = {"base_url": env.base_url, "config": env.config or {}}

        items = db.query(TestPlanItem).filter(
            TestPlanItem.plan_id == plan.id,
            TestPlanItem.enabled == True,
            TestPlanItem.is_deleted == False
        ).order_by(TestPlanItem.sort_order).all()

        execution.total_items = len(items)
        execution.passed_count = 0
        execution.failed_count = 0
        execution.skipped_count = 0
        db.commit()

        logger.info(
            f"测试计划执行开始: execution_id={execution_id}, total_nodes={len(items)}, "
            f"api_nodes={sum(1 for it in items if _node_family(it.item_type) == 'api')}, "
            f"ui_nodes={sum(1 for it in items if _node_family(it.item_type) == 'ui')}"
        )

        # 初始化接口用 VariableEngine（仅 API 家族节点共享，UI 节点不共享）
        var_engine = VariableEngine()
        if environment:
            var_engine.load_environment(environment.get("config", {}))
            var_engine.set("environment", "base_url", environment.get("base_url", ""))

        # stopped_families: 哪些家族因 fail_strategy="stop" 触发跳过
        stopped_families: set = set()

        for item in items:
            family = _node_family(item.item_type)

            if _is_cancelled(db, execution_id):
                _record_skipped(db, execution_id, item, "执行被取消")
                _increment_stat(db, execution_id, "skipped")
                continue

            if family in stopped_families:
                reason = f"同家族({family})前置节点失败且 fail_strategy=stop，跳过"
                _record_skipped(db, execution_id, item, reason)
                _increment_stat(db, execution_id, "skipped")
                continue

            logger.info(
                f"  → 执行节点 [{item.item_type}] id={item.id} name={item.item_name!r} "
                f"(sort={item.sort_order})"
            )

            # 串行执行（单 Session、单 asyncio.run 入口）
            result = asyncio.run(_execute_any_item(
                db, item, execution_id, plan.id, var_engine, environment
            ))
            db.add(result)
            db.commit()
            _increment_stat(db, execution_id, result.status)

            logger.info(
                f"    ← 节点 [{item.item_type}] {item.item_name!r} 结果={result.status}, "
                f"耗时={result.duration_ms}ms, fail_strategy={item.fail_strategy}"
            )

            if result.status in ("failed", "error") and item.fail_strategy == "stop":
                stopped_families.add(family)
                logger.warning(
                    f"    ⚠ 节点失败触发 stop: 同家族 '{family}' 的后续节点将被跳过"
                )

        # 最终聚合
        db.refresh(execution)
        if execution.status == "cancelled":
            logger.info(f"测试计划已被取消: execution_id={execution_id}")
            return

        total = (execution.passed_count or 0) + (execution.failed_count or 0) + (execution.skipped_count or 0)
        execution.pass_rate = round((execution.passed_count or 0) / total * 100, 2) if total > 0 else 0
        execution.status = "completed" if (execution.failed_count or 0) == 0 else "failed"
        execution.finished_at = china_now_naive()

        plan.status = "completed"
        plan.last_execution_id = execution.id
        plan.last_pass_rate = execution.pass_rate
        plan.pass_rate = int(execution.pass_rate)
        plan.total_cases = total
        plan.passed_cases = execution.passed_count or 0
        plan.failed_cases = execution.failed_count or 0

        # P1-10: 执行完成后创建 TestReport 记录
        _create_execution_report(db, plan, execution)

        db.commit()

        logger.info(
            f"测试计划执行完成: execution_id={execution_id}, "
            f"passed={execution.passed_count}, failed={execution.failed_count}, "
            f"skipped={execution.skipped_count}, pass_rate={execution.pass_rate}%, "
            f"stopped_families={stopped_families}"
        )

        # 发送通知（异步，不阻塞）
        try:
            env_name = "默认环境"
            if plan.environment_id:
                env_obj = db.query(TestEnvironment).filter(TestEnvironment.id == plan.environment_id).first()
                if env_obj:
                    env_name = env_obj.name
            duration = 0.0
            if execution.started_at and execution.finished_at:
                duration = round((execution.finished_at - execution.started_at).total_seconds(), 2)
            failed_nodes = []
            if execution.failed_count and execution.failed_count > 0:
                failed_results = db.query(TestPlanExecutionResult).filter(
                    TestPlanExecutionResult.execution_id == execution_id,
                    TestPlanExecutionResult.status.in_(["failed", "error"]),
                ).order_by(TestPlanExecutionResult.sort_order).limit(20).all()
                failed_nodes = [r.item_name for r in failed_results if r.item_name]

            event_code = "plan.execution.failed" if execution.failed_count and execution.failed_count > 0 else "plan.execution.completed"
            notify_event(
                plan.project_id,
                event_code,
                {
                    "plan_id": plan.id,
                    "plan_name": plan.name,
                    "execution_id": execution.id,
                    "environment_name": env_name,
                    "total_count": total,
                    "passed_count": execution.passed_count or 0,
                    "failed_count": execution.failed_count or 0,
                    "skipped_count": execution.skipped_count or 0,
                    "pass_rate": execution.pass_rate or 0,
                    "duration": duration,
                    "failed_nodes": failed_nodes,
                },
                triggered_by=execution.triggered_by,
            )
        except Exception as notify_e:
            logger.warning(f"发送测试计划通知失败（不影响业务）: {notify_e}")

    except Exception as e:
        logger.exception(f"测试计划执行异常: {e}")
        try:
            db.rollback()
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


@celery_app.task(bind=True, name="execute_test_plan", max_retries=0, queue="execution")
def execute_test_plan_task(self, execution_id: int):
    """执行测试计划（Celery 任务入口）"""
    _run_test_plan_execution(execution_id)


# ============ 统一节点执行器 ============

async def _execute_any_item(
    db, item: TestPlanItem, execution_id: int, plan_id: int,
    var_engine: VariableEngine, environment: Optional[Dict]
) -> TestPlanExecutionResult:
    """
    统一入口，根据 item_type 分派到对应执行器。
    API 家族节点共享 var_engine；UI 家族节点独立执行，不使用 var_engine。
    """
    result = TestPlanExecutionResult(
        execution_id=execution_id,
        item_id=item.id,
        item_type=item.item_type,
        ref_id=item.ref_id,
        item_name=item.item_name,
        sort_order=item.sort_order,
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
            elif item.item_type == "script":
                await _execute_script_node(db, item, result)
            elif item.item_type == "suite":
                await _execute_suite_node(db, item, result, plan_id)
            elif item.item_type == "ui_case":
                result.status = "skipped"
                result.error_message = "功能用例需手动执行"
            else:
                result.status = "error"
                result.error_message = f"不支持的节点类型: {item.item_type}"

            if result.status == "passed":
                break
            if attempt < max_retries:
                await asyncio.sleep(1)
        except Exception as e:
            logger.exception(
                f"节点执行异常 [{item.item_type}] {item.item_name!r}: {e}"
            )
            result.status = "error"
            result.error_message = str(e)
            if attempt < max_retries:
                await asyncio.sleep(1)

    result.finished_at = china_now_naive()
    result.duration_ms = int((time.time() - start_time) * 1000)
    return result


# ============ API 家族：case / scenario ============

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

    script_engine = ScriptEngine()
    if case.pre_script:
        script_result = script_engine.execute(
            case.pre_script,
            environment_vars=var_engine.environment_vars,
            global_vars=var_engine.global_vars,
            request={"method": method, "url": url},
        )
        for k, v in script_result.variables.items():
            var_engine.set("scenario", k, v)
        url = var_engine.replace(base_url + (case.path or ""))
        headers = var_engine.replace_headers(case.headers)
        params = var_engine.replace_params(case.query_params)
        body_content = var_engine.replace_body(case.body_type, case.body_content)

    result.request_data = {
        "method": method,
        "url": url,
        "headers": {h.get("key", ""): h.get("value", "") for h in (headers or []) if h.get("enabled", True)},
        "body": body_content,
    }

    timeout = item.timeout if item.timeout and item.timeout > 0 else 30
    http_client = HttpClient(timeout=timeout)
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

    if case.post_script:
        script_engine.execute(
            case.post_script,
            environment_vars=var_engine.environment_vars,
            global_vars=var_engine.global_vars,
            request={"method": method, "url": url},
            response=response.to_dict(),
        )

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
    result.assertions = [_normalize_assertion_result(a) for a in assertion_results]

    all_passed = all(a.passed for a in assertion_results) and not response.error
    result.status = "passed" if all_passed else "failed"
    if not all_passed:
        failed_asserts = [a for a in assertion_results if not a.passed]
        result.error_message = response.error or f"{len(failed_asserts)}个断言失败"


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

    steps = db.query(ApiScenarioStep).filter(
        ApiScenarioStep.scenario_id == scenario.id,
        ApiScenarioStep.is_deleted == False
    ).order_by(ApiScenarioStep.sort_order).all()

    step_dicts = []
    for step in steps:
        step_assertions: List[Dict[str, Any]] = []
        if step.case_id:
            case_assertions = db.query(ApiCaseAssertion).filter(
                ApiCaseAssertion.case_id == step.case_id,
                ApiCaseAssertion.enabled == True,
            ).order_by(ApiCaseAssertion.sort_order).all()
            step_assertions.extend([
                {"assert_type": a.assert_type, "assert_target": a.assert_target,
                 "operator": a.operator, "expected_value": a.expected_value,
                 "enabled": a.enabled}
                for a in case_assertions
            ])
        request_config = step.request_config or {}
        if isinstance(request_config, dict) and request_config.get("assertions"):
            for a in request_config["assertions"]:
                if isinstance(a, dict) and a.get("enabled", True):
                    step_assertions.append({
                        "assert_type": a.get("assert_type", ""),
                        "assert_target": a.get("assert_target", ""),
                        "operator": a.get("operator", "equals"),
                        "expected_value": a.get("expected_value", ""),
                        "enabled": a.get("enabled", True),
                    })

        step_dicts.append({
            "id": step.id,
            "step_type": step.step_type,
            "step_name": step.step_name,
            "sort_order": step.sort_order,
            "enabled": step.enabled,
            "api_id": step.api_id,
            "case_id": step.case_id,
            "request_config": request_config,
            "script_content": step.script_content,
            "wait_seconds": step.wait_seconds,
            "condition_expr": step.condition_expr,
            "loop_config": step.loop_config or {},
            "pre_script": step.pre_script,
            "post_script": step.post_script,
            "continue_on_failure": step.continue_on_failure,
            "max_retries": step.max_retries,
            "assertions": step_assertions,
        })

    scenario_dict = {
        "id": scenario.id,
        "name": scenario.name,
        "pre_script": scenario.pre_script,
        "post_script": scenario.post_script,
    }

    executor = ScenarioExecutor(db, variable_engine=var_engine)
    exec_result = await executor.execute_scenario(
        scenario=scenario_dict,
        steps=step_dicts,
        environment=environment,
    )

    failed_steps = exec_result.get("failed_steps", 0)
    result.status = "passed" if failed_steps == 0 else "failed"

    result.request_data = {
        "scenario": scenario.name,
        "steps": len(step_dicts),
    }
    result.response_data = {
        "total_steps": exec_result.get("total_steps", 0),
        "passed_steps": exec_result.get("passed_steps", 0),
        "failed_steps": failed_steps,
        "skipped_steps": exec_result.get("skipped_steps", 0),
        "pass_rate": exec_result.get("pass_rate", 0),
        "total_duration": exec_result.get("total_duration", 0),
        "step_results": [
            {
                "step_name": sr.get("step_name", ""),
                "sort_order": sr.get("sort_order", 0),
                "status": sr.get("status", ""),
                "request_method": sr.get("request_method", ""),
                "request_url": sr.get("request_url", ""),
                "response_status": sr.get("response_status"),
                "response_time": sr.get("response_time", 0),
                "error_message": sr.get("error_message", ""),
            }
            for sr in exec_result.get("results", [])
        ],
    }

    flat_assertions: List[Dict[str, Any]] = []
    for sr in exec_result.get("results", []):
        step_name = sr.get("step_name", "")
        for a in sr.get("assertions", []):
            flat_assertions.append(_normalize_assertion_dict(a, step_name))
    result.assertions = flat_assertions
    result.extracted_vars = dict(var_engine.scenario_vars)

    if result.status == "failed":
        result.error_message = f"场景执行失败: {failed_steps}个步骤失败"


# ============ UI 家族：script / suite ============

async def _execute_script_node(db, item: TestPlanItem, result: TestPlanExecutionResult):
    """执行UI脚本库中的单个脚本（独立浏览器实例）"""
    script = db.query(AutomationScript).filter(AutomationScript.id == item.ref_id).first()
    if not script:
        result.status = "error"
        result.error_message = f"UI脚本不存在: {item.ref_id}"
        return

    from app.services.script_runner import apply_headless_mode, execute_script_async

    content = apply_headless_mode(script.script_content or "", True)
    result.request_data = {
        "script": script.name,
        "target_url": script.target_url,
        "version": script.version,
        "language": script.language,
        "category": "ui_script",
    }

    success, error = await execute_script_async(content, script.id)
    result.response_data = {
        "success": success,
        "error": error,
        "category": "ui_script",
    }
    result.status = "passed" if success else "failed"
    if not success:
        result.error_message = error or "脚本执行失败"


async def _execute_suite_node(db, item: TestPlanItem, result: TestPlanExecutionResult, plan_id: int):
    """执行UI自动化编排套件（复用 SuiteExecutor，共享浏览器 + AI修复）"""
    suite = db.query(AutomationSuite).filter(AutomationSuite.id == item.ref_id).first()
    if not suite:
        result.status = "error"
        result.error_message = f"编排套件不存在: {item.ref_id}"
        return

    suite_run = AutomationSuiteRun(
        suite_id=suite.id,
        project_id=suite.project_id,
        plan_id=None,
        status="pending",
        total_steps=suite.total_steps or 0,
        trigger_type="api",
    )
    db.add(suite_run)
    db.commit()
    suite_run_id = suite_run.id

    result.request_data = {
        "suite": suite.name,
        "suite_run_id": suite_run_id,
        "total_steps": suite.total_steps,
        "category": "ui_suite",
    }

    from app.agents.suite_executor import SuiteExecutor
    executor = SuiteExecutor(suite_run_id, headless=True)
    await executor.execute()

    suite_run = db.query(AutomationSuiteRun).filter(
        AutomationSuiteRun.id == suite_run_id
    ).first()

    result.response_data = {
        "suite_run_id": suite_run_id,
        "status": suite_run.status if suite_run else "unknown",
        "passed_steps": suite_run.passed_steps if suite_run else 0,
        "failed_steps": suite_run.failed_steps if suite_run else 0,
        "skipped_steps": suite_run.skipped_steps if suite_run else 0,
        "pass_rate": suite_run.pass_rate if suite_run else 0,
        "total_duration": suite_run.total_duration if suite_run else 0,
        "category": "ui_suite",
    }

    if not suite_run:
        result.status = "error"
        result.error_message = "套件执行记录丢失"
    elif suite_run.status == "passed":
        result.status = "passed"
    elif suite_run.status == "partial":
        result.status = "failed"
        result.error_message = f"部分步骤失败: {suite_run.failed_steps}个"
    else:
        result.status = "failed"
        result.error_message = (suite_run.error_message or "套件执行失败") if suite_run else "套件执行失败"
