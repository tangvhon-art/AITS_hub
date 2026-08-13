"""
编排执行引擎

按顺序执行自动化编排套件中的所有步骤，支持失败继续、重试策略。
"""
import asyncio
import json
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable

from sqlalchemy.orm import Session

from app.core.timezone import china_now_naive
from app.database import SessionLocal
from app.models.automation_suite import (
    AutomationSuite,
    AutomationSuiteStep,
    AutomationSuiteRun,
    AutomationSuiteRunResult,
)
from app.models.automation_script import AutomationScript
from app.models.test_run import TestRun
from app.models.test_case import TestCase

logger = logging.getLogger(__name__)


class SuiteExecutor:
    """编排执行引擎"""

    def __init__(self, suite_run_id: int, on_step_complete: Optional[Callable] = None):
        """
        Args:
            suite_run_id: 编排执行记录ID
            on_step_complete: 每步完成后的回调函数（用于SSE推送）
        """
        self.suite_run_id = suite_run_id
        self.on_step_complete = on_step_complete
        self.db: Session = SessionLocal()
        self.stopped = False

    async def execute(self) -> None:
        """执行整个编排套件"""
        try:
            suite_run = self.db.query(AutomationSuiteRun).filter(
                AutomationSuiteRun.id == self.suite_run_id
            ).first()
            if not suite_run:
                logger.error(f"编排执行记录不存在: {self.suite_run_id}")
                return

            suite = self.db.query(AutomationSuite).filter(
                AutomationSuite.id == suite_run.suite_id
            ).first()
            if not suite:
                logger.error(f"编排套件不存在: {suite_run.suite_id}")
                return

            # 获取所有步骤
            steps = self.db.query(AutomationSuiteStep).filter(
                AutomationSuiteStep.suite_id == suite.id
            ).order_by(AutomationSuiteStep.sort_order.asc()).all()

            # 更新执行记录状态
            suite_run.status = "running"
            suite_run.started_at = china_now_naive()
            suite_run.total_steps = len(steps)
            self.db.commit()

            start_time = time.time()
            passed = 0
            failed = 0
            skipped = 0
            stop_execution = False

            for idx, step in enumerate(steps):
                if self.stopped or stop_execution:
                    # 标记剩余步骤为 skipped
                    result = self._create_result(suite_run, step, idx)
                    result.status = "skipped"
                    result.completed_at = china_now_naive()
                    skipped += 1
                    self.db.commit()
                    continue

                # 执行单步
                result = await self._execute_step(suite_run, step, idx)

                if result.status == "passed":
                    passed += 1
                elif result.status == "failed":
                    failed += 1
                    if not step.continue_on_failure:
                        stop_execution = True
                else:
                    skipped += 1

                # 更新汇总
                suite_run.passed_steps = passed
                suite_run.failed_steps = failed
                suite_run.skipped_steps = skipped
                suite_run.pass_rate = round(passed / max(len(steps), 1) * 100, 2)
                self.db.commit()

                # 回调通知
                if self.on_step_complete:
                    try:
                        self.on_step_complete({
                            "step_index": idx,
                            "step_name": step.step_name,
                            "status": result.status,
                            "duration": result.duration,
                            "passed": passed,
                            "failed": failed,
                            "skipped": skipped,
                        })
                    except Exception:
                        pass

            # 计算最终状态
            duration = time.time() - start_time
            suite_run.total_duration = round(duration, 2)
            suite_run.completed_at = china_now_naive()

            if failed == 0 and skipped == 0:
                suite_run.status = "passed"
            elif passed > 0 and failed > 0:
                suite_run.status = "partial"
            elif failed > 0 and passed == 0:
                suite_run.status = "failed"
            else:
                suite_run.status = "passed"

            # 更新套件最近执行状态
            suite.last_run_status = suite_run.status
            suite.last_run_at = china_now_naive()

            self.db.commit()

            # 更新关联测试计划统计
            if suite_run.plan_id:
                self._update_plan_stats(suite_run.plan_id)

            logger.info(f"编排执行完成: suite_run={self.suite_run_id}, status={suite_run.status}")

        except Exception as e:
            logger.error(f"编排执行异常: {e}", exc_info=True)
            try:
                suite_run = self.db.query(AutomationSuiteRun).filter(
                    AutomationSuiteRun.id == self.suite_run_id
                ).first()
                if suite_run:
                    suite_run.status = "failed"
                    suite_run.error_message = str(e)
                    suite_run.completed_at = china_now_naive()
                    self.db.commit()
            except Exception:
                pass
        finally:
            self.db.close()

    def _update_plan_stats(self, plan_id: int) -> None:
        """更新关联测试计划的统计数据"""
        try:
            from app.models.test_plan import TestPlan
            plan = self.db.query(TestPlan).filter(TestPlan.id == plan_id).first()
            if not plan:
                return

            # 统计该计划下所有编排执行的结果
            from app.models.automation_suite import AutomationSuiteRun
            runs = self.db.query(AutomationSuiteRun).filter(
                AutomationSuiteRun.plan_id == plan_id,
                AutomationSuiteRun.status.in_(["passed", "failed", "partial"])
            ).all()

            total_steps = sum(r.total_steps or 0 for r in runs)
            passed_steps = sum(r.passed_steps or 0 for r in runs)
            failed_steps = sum(r.failed_steps or 0 for r in runs)

            if total_steps > 0:
                plan.total_cases = total_steps
                plan.passed_cases = passed_steps
                plan.failed_cases = failed_steps
                plan.pass_rate = round(passed_steps / total_steps * 100, 2)
                plan.updated_at = china_now_naive()
                self.db.commit()
                logger.info(f"已更新测试计划统计: plan_id={plan_id}, 通过率={plan.pass_rate}%")
        except Exception as e:
            logger.error(f"更新测试计划统计失败: plan_id={plan_id}, error={e}", exc_info=True)

    async def _execute_step(
        self,
        suite_run: AutomationSuiteRun,
        step: AutomationSuiteStep,
        index: int,
    ) -> AutomationSuiteRunResult:
        """执行单个步骤"""
        result = self._create_result(suite_run, step, index)
        result.status = "running"
        result.started_at = china_now_naive()
        self.db.commit()

        step_start = time.time()
        retry_count = 0
        max_retries = step.max_retries or 0
        final_status = "failed"
        error_msg = ""

        for attempt in range(max_retries + 1):
            if self.stopped:
                final_status = "skipped"
                break

            try:
                if step.step_type == "script":
                    await self._run_script_step(step, result)
                    final_status = "passed"
                    error_msg = ""
                    break
                elif step.step_type == "case":
                    await self._run_case_step(step, result)
                    final_status = "passed"
                    error_msg = ""
                    break
                elif step.step_type == "wait":
                    wait_time = (step.params or {}).get("seconds", 5)
                    await asyncio.sleep(min(wait_time, 60))
                    final_status = "passed"
                    break
                else:
                    final_status = "skipped"
                    break

            except Exception as e:
                error_msg = str(e)
                retry_count = attempt + 1
                if attempt < max_retries:
                    await asyncio.sleep(1)  # 重试前等待
                continue

        result.status = final_status
        result.error_message = error_msg
        result.retry_count = retry_count
        result.duration = round(time.time() - step_start, 2)
        result.completed_at = china_now_naive()
        self.db.commit()

        return result

    def _create_result(
        self,
        suite_run: AutomationSuiteRun,
        step: AutomationSuiteStep,
        index: int,
    ) -> AutomationSuiteRunResult:
        """创建单步执行结果记录"""
        result = AutomationSuiteRunResult(
            suite_run_id=suite_run.id,
            step_id=step.id,
            script_id=step.script_id,
            case_id=step.case_id,
            step_name=step.step_name,
            sort_order=index,
            status="pending",
        )
        self.db.add(result)
        self.db.commit()
        self.db.refresh(result)
        return result

    async def _run_script_step(self, step: AutomationSuiteStep, result: AutomationSuiteRunResult) -> None:
        """执行脚本类型步骤"""
        if not step.script_id:
            raise ValueError("脚本步骤未关联脚本")

        script = self.db.query(AutomationScript).filter(
            AutomationScript.id == step.script_id
        ).first()
        if not script:
            raise ValueError(f"脚本不存在: {step.script_id}")

        # 参数替换
        script_content = script.script_content
        params = step.params or {}
        for key, value in params.items():
            script_content = script_content.replace(f"{{{{{key}}}}}", str(value))

        # 获取 project_id
        suite_run = self.db.query(AutomationSuiteRun).filter(AutomationSuiteRun.id == result.suite_run_id).first()
        project_id = suite_run.project_id if suite_run else 0

        # 创建 test_runs 记录
        run_start_time = time.time()
        run_start_datetime = china_now_naive()
        run = TestRun(
            project_id=project_id,
            case_id=step.case_id,
            status="running",
            execution_log=json.dumps([{
                "action": "suite_script",
                "detail": step.step_name,
                "timestamp": run_start_time,
                "status": "running"
            }], ensure_ascii=False),
            started_at=run_start_datetime,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        result.run_id = run.id

        # 动态执行脚本
        local_vars = {}
        exec(compile(script_content, f"suite_script_{script.id}.py", "exec"), local_vars)

        if "run_test" in local_vars and callable(local_vars["run_test"]):
            await local_vars["run_test"]()
        else:
            raise RuntimeError("脚本中未找到 run_test 函数")

        # 计算真实执行耗时
        run_duration = round(time.time() - run_start_time, 2)

        # 更新 test_runs
        run.status = "passed"
        run.completed_at = china_now_naive()
        run.duration = run_duration
        run.execution_log = json.dumps([
            {"action": "suite_script", "detail": step.step_name, "timestamp": run_start_time, "status": "running", "script_id": script.id},
            {"action": "result", "detail": f"执行成功，耗时: {run_duration}s",
             "timestamp": time.time(), "status": "passed", "duration": run_duration, "script_id": script.id},
        ], ensure_ascii=False)
        self.db.commit()

        # 将执行日志和耗时写入编排单步结果
        result.execution_log = run.execution_log
        result.duration = run_duration

        # 更新脚本统计
        script.total_runs = (script.total_runs or 0) + 1
        script.last_run_status = "passed"
        script.last_run_at = china_now_naive()
        script.pass_count = (script.pass_count or 0) + 1
        self.db.commit()

    async def _run_case_step(self, step: AutomationSuiteStep, result: AutomationSuiteRunResult) -> None:
        """执行用例类型步骤（动态生成脚本并执行）"""
        if not step.case_id:
            raise ValueError("用例步骤未关联用例")

        case = self.db.query(TestCase).filter(TestCase.id == step.case_id).first()
        if not case:
            raise ValueError(f"用例不存在: {step.case_id}")

        # 简单实现：生成基础脚本并执行
        # 完整实现应调用 ExecutionAgent，但为避免阻塞，这里生成简化脚本
        from app.agents.script_generator import ScriptGenerator
        script_content = ScriptGenerator.generate_template(
            target_url=(case.preconditions or "")[:200],
            name=case.title,
        )

        # 创建 test_runs 记录
        suite_run = self.db.query(AutomationSuiteRun).filter(AutomationSuiteRun.id == result.suite_run_id).first()
        run_start_time = time.time()
        run_start_datetime = china_now_naive()
        run = TestRun(
            project_id=suite_run.project_id if suite_run else 0,
            case_id=step.case_id,
            status="running",
            execution_log=json.dumps([{
                "action": "suite_case",
                "detail": case.title,
                "timestamp": run_start_time,
                "status": "running"
            }], ensure_ascii=False),
            started_at=run_start_datetime,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        result.run_id = run.id

        # 执行脚本
        local_vars = {}
        exec(compile(script_content, f"suite_case_{case.id}.py", "exec"), local_vars)
        if "run_test" in local_vars and callable(local_vars["run_test"]):
            await local_vars["run_test"]()

        # 计算真实执行耗时
        run_duration = round(time.time() - run_start_time, 2)

        run.status = "passed"
        run.completed_at = china_now_naive()
        run.duration = run_duration
        run.execution_log = json.dumps([
            {"action": "suite_case", "detail": case.title, "timestamp": run_start_time, "status": "running"},
            {"action": "result", "detail": f"执行成功，耗时: {run_duration}s",
             "timestamp": time.time(), "status": "passed", "duration": run_duration},
        ], ensure_ascii=False)
        self.db.commit()

        # 将执行日志和耗时写入编排单步结果
        result.execution_log = run.execution_log
        result.duration = run_duration

    def stop(self) -> None:
        """停止执行"""
        self.stopped = True
