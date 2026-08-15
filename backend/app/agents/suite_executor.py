"""
编排执行引擎

按顺序执行自动化编排套件中的所有步骤，支持失败继续、重试策略。
所有脚本步骤共享同一个浏览器上下文（page），保证 cookie/session 串联。
"""
import asyncio
import json
import logging
import re
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
from app.models.defect import Defect
from app.agents.script_generator import ScriptGenerator

logger = logging.getLogger(__name__)


class SuiteExecutor:
    """编排执行引擎"""

    def __init__(self, suite_run_id: int, headless: bool = True, on_step_complete: Optional[Callable] = None):
        """
        Args:
            suite_run_id: 编排执行记录ID
            headless: 是否以无头模式运行浏览器
            on_step_complete: 每步完成后的回调函数（用于SSE推送）
        """
        self.suite_run_id = suite_run_id
        self.headless = headless
        self.on_step_complete = on_step_complete
        self.db: Session = SessionLocal()
        self.stopped = False
        # 共享浏览器上下文（编排模式下所有脚本共用）
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._browser_initialized = False

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

            # 初始化共享浏览器上下文（所有脚本步骤共用，保证cookie/session串联）
            await self._init_shared_browser()

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
                        # 关键步骤失败且不允许继续时，立即将编排任务标记为失败，避免前端长时间看到 running
                        suite_run.status = "failed"
                        suite_run.error_message = result.error_message or "步骤执行失败"
                        self.db.commit()
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

            if failed > 0 and passed == 0:
                suite_run.status = "failed"
            elif failed > 0 and passed > 0:
                suite_run.status = "partial"
            elif failed == 0 and passed == 0 and skipped > 0:
                suite_run.status = "skipped"
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
            # 统一关闭共享浏览器
            await self._close_shared_browser()
            self.db.close()

    async def _init_shared_browser(self) -> None:
        """初始化共享浏览器上下文（编排模式下所有脚本共用）"""
        if self._browser_initialized:
            return
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=self.headless)
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 720},
                # 共享cookie存储，所有页面共用
            )
            self._page = await self._context.new_page()
            self._browser_initialized = True
            logger.info(f"编排 #{self.suite_run_id} 共享浏览器已初始化")
        except Exception as e:
            logger.error(f"共享浏览器初始化失败: {e}", exc_info=True)
            # 初始化失败时，后续脚本将回退到独立浏览器模式
            self._browser_initialized = False

    async def _close_shared_browser(self) -> None:
        """关闭共享浏览器"""
        try:
            if self._page:
                await self._page.close()
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
            logger.info(f"编排 #{self.suite_run_id} 共享浏览器已关闭")
        except Exception as e:
            logger.warning(f"关闭共享浏览器失败: {e}")
        finally:
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None
            self._browser_initialized = False

    @staticmethod
    def _convert_script_to_suite_mode(script_content: str) -> str:
        """
        将独立执行的脚本转换为编排模式：
        1. 移除 async with async_playwright() as p: 及其内部的 browser/context/page 创建
        2. 移除 await browser.close()
        3. 将 run_test() 改为 run_test(page)，使用外部注入的共享 page
        4. 调整缩进（原 async with 块内的 8 空格缩进改为 4 空格）

        Args:
            script_content: 原始脚本内容

        Returns:
            转换后的脚本内容
        """
        content = script_content

        # 1. 移除 async with async_playwright() as p: 行（及其变体）
        content = re.sub(
            r'[ \t]*async with async_playwright\(\) as \w+:[ \t]*\n',
            '',
            content
        )

        # 2. 移除 browser = await p.chromium.launch(...) 行（支持多种写法）
        content = re.sub(
            r'[ \t]*\w+\s*=\s*await \w+\.chromium\.launch\([^)]*\)[ \t]*\n',
            '',
            content
        )

        # 3. 移除 context = await browser.new_context(...) 行（可能跨多行）
        content = re.sub(
            r'[ \t]*\w+\s*=\s*await \w+\.new_context\([^)]*\)[ \t]*\n',
            '',
            content,
            flags=re.DOTALL
        )

        # 4. 移除 page = await context.new_page() 行
        content = re.sub(
            r'[ \t]*\w+\s*=\s*await \w+\.new_page\(\)[ \t]*\n',
            '',
            content
        )

        # 5. 移除 await browser.close() 行
        content = re.sub(
            r'[ \t]*await \w+\.close\(\)[ \t]*\n',
            '',
            content
        )

        # 6. 将 async def run_test(): 改为 async def run_test(page):
        content = re.sub(
            r'async def run_test\(\s*\):',
            'async def run_test(page):',
            content
        )
        # 兼容 def run_test(): 同步写法
        content = re.sub(
            r'def run_test\(\s*\):',
            'def run_test(page):',
            content
        )

        # 7. 调整缩进：将 run_test 函数体内 8 空格缩进的行改为 4 空格
        # （因为原来代码在 async with 块内，多了一层缩进）
        lines = content.split('\n')
        in_run_test = False
        adjusted_lines = []
        for line in lines:
            if 'def run_test(page):' in line:
                in_run_test = True
                adjusted_lines.append(line)
                continue
            if in_run_test:
                # 遇到下一个顶层定义（def/import/if 等）则退出函数体
                stripped = line.lstrip()
                if stripped and not line.startswith(' ') and not line.startswith('\t'):
                    in_run_test = False
                elif line.startswith('        '):  # 8空格缩进
                    # 减少4个空格缩进
                    line = line[4:]
                elif line.startswith('\t\t'):  # 2个tab
                    line = line[1:]
            adjusted_lines.append(line)
        content = '\n'.join(adjusted_lines)

        # 8. 移除 if __name__ == "__main__": 块（避免独立执行逻辑干扰）
        content = re.sub(
            r'\nif __name__\s*==\s*["\']__main__["\']\s*:.*?(?=\n*$)',
            '',
            content,
            flags=re.DOTALL
        )

        return content

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

    def _create_defect_from_failure(
        self,
        suite_run: AutomationSuiteRun,
        step: AutomationSuiteStep,
        result: AutomationSuiteRunResult,
        error_msg: str,
    ) -> Optional[Defect]:
        """
        编排步骤执行失败时，自动创建缺陷记录

        Args:
            suite_run: 编排执行记录
            step: 失败的步骤
            result: 步骤执行结果
            error_msg: 错误信息

        Returns:
            创建的缺陷记录（如果创建成功）
        """
        # 去重：同一编排运行中，同一步骤只创建一个缺陷
        existing = self.db.query(Defect).filter(
            Defect.project_id == suite_run.project_id,
            Defect.run_id == result.run_id if result.run_id else Defect.run_id.is_(None),
            Defect.title == f"[编排失败] {step.step_name}",
        ).first()
        if existing:
            # 已存在缺陷，追加重试信息到 error_log
            try:
                retry_info = f"\n\n[第{result.retry_count + 1}次重试失败] {error_msg}"
                existing.error_log = (existing.error_log or "") + retry_info
                self.db.commit()
            except Exception:
                pass
            return existing

        # 根据错误类型推断严重程度
        severity = "major"
        error_lower = (error_msg or "").lower()
        if "timeout" in error_lower or "超时" in error_lower:
            severity = "major"
        elif "selector" in error_lower or "选择器" in error_lower or "not found" in error_lower:
            severity = "minor"
        elif "assert" in error_lower or "断言" in error_lower:
            severity = "major"
        elif "exception" in error_lower or "error" in error_lower or "异常" in error_lower:
            severity = "critical"

        # 从执行日志提取复现步骤
        reproduce_steps = ""
        try:
            if result.execution_log:
                logs = json.loads(result.execution_log) if isinstance(result.execution_log, str) else result.execution_log
                step_descriptions = []
                for i, log_item in enumerate(logs, 1):
                    detail = log_item.get("detail", "")
                    if detail:
                        step_descriptions.append(f"{i}. {detail}")
                reproduce_steps = "\n".join(step_descriptions)
        except Exception:
            pass

        # 获取编排名称
        suite_name = ""
        try:
            suite = self.db.query(AutomationSuite).filter(AutomationSuite.id == suite_run.suite_id).first()
            suite_name = suite.name if suite else ""
        except Exception:
            pass

        defect = Defect(
            project_id=suite_run.project_id,
            run_id=result.run_id,
            case_id=step.case_id,
            title=f"[编排失败] {step.step_name}",
            description=(
                f"自动化编排执行失败\n"
                f"编排名称: {suite_name}\n"
                f"步骤名称: {step.step_name}\n"
                f"步骤类型: {step.step_type}\n"
                f"重试次数: {result.retry_count}\n"
                f"错误信息: {error_msg}"
            ),
            severity=severity,
            priority="medium",
            status="open",
            reproduce_steps=reproduce_steps,
            actual_result=error_msg,
            error_log=error_msg,
            screenshot_url=result.screenshot_url,
            created_by=suite_run.executed_by,
        )
        self.db.add(defect)
        self.db.commit()
        self.db.refresh(defect)

        # 将缺陷ID记录到执行结果中（方便前端展示关联）
        try:
            if result.execution_log:
                logs = json.loads(result.execution_log) if isinstance(result.execution_log, str) else result.execution_log
            else:
                logs = []
            logs.append({
                "action": "defect_created",
                "detail": f"已自动创建缺陷 #{defect.id}",
                "timestamp": time.time(),
                "status": "success",
                "defect_id": defect.id,
            })
            result.execution_log = json.dumps(logs, ensure_ascii=False)
            self.db.commit()
        except Exception:
            pass

        logger.info(f"编排步骤失败，已自动创建缺陷: defect_id={defect.id}, step={step.step_name}")
        return defect

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
                retry_count = attempt
                if attempt < max_retries:
                    retry_count = attempt + 1
                    await asyncio.sleep(1)  # 重试前等待
                continue

        result.status = final_status
        result.error_message = error_msg
        result.retry_count = retry_count
        result.duration = round(time.time() - step_start, 2)
        result.completed_at = china_now_naive()

        # 失败步骤补充执行日志，避免详情页无日志展示
        if final_status == "failed" and (not result.execution_log or result.execution_log == "null"):
            result.execution_log = json.dumps([
                {"action": "step_failed", "detail": error_msg or "步骤执行失败",
                 "timestamp": time.time(), "status": "failed", "step_name": step.step_name}
            ], ensure_ascii=False)

        self.db.commit()

        # 步骤失败时，同步更新其关联的 TestRun 状态，避免执行日志中子任务一直显示 running
        if final_status == "failed" and result.run_id:
            try:
                sub_run = self.db.query(TestRun).filter(TestRun.id == result.run_id).first()
                if sub_run and sub_run.status == "running":
                    sub_run.status = "failed"
                    sub_run.error_message = error_msg or "步骤执行失败"
                    sub_run.completed_at = china_now_naive()
                    sub_run.duration = round(time.time() - step_start, 2)
                    self.db.commit()
            except Exception as sub_e:
                logger.warning(f"更新子执行记录状态失败: {sub_e}")

        # 步骤失败时，自动创建缺陷
        if final_status == "failed":
            try:
                self._create_defect_from_failure(suite_run, step, result, error_msg)
            except Exception as defect_e:
                logger.warning(f"自动创建缺陷失败（不影响编排流程）: {defect_e}")

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

    @staticmethod
    def _extract_navigation_urls(script_content: str) -> List[Dict[str, str]]:
        """从脚本内容中提取 page.goto 导航操作，用于执行日志展示"""
        navigations = []
        if not script_content:
            return navigations
        # 匹配 await page.goto("url", ...) 或 page.goto("url", ...)
        pattern = re.compile(r'await\s+page\.goto\s*\(\s*["\']([^"\']+)["\']', re.MULTILINE)
        for match in pattern.finditer(script_content):
            url = match.group(1)
            # 尝试提取同行或上一行的中文注释作为描述
            desc = "页面导航"
            lines = script_content[:match.start()].split('\n')
            if lines:
                prev_line = lines[-1].strip()
                if prev_line.startswith('#'):
                    desc = prev_line.lstrip('#').strip()
            navigations.append({"url": url, "description": desc})
        return navigations

    async def _run_script_step(self, step: AutomationSuiteStep, result: AutomationSuiteRunResult) -> None:
        """执行脚本类型步骤（使用共享浏览器上下文，支持AI自动修复）"""
        if not step.script_id:
            raise ValueError("脚本步骤未关联脚本")

        script = self.db.query(AutomationScript).filter(
            AutomationScript.id == step.script_id
        ).first()
        if not script:
            raise ValueError(f"脚本不存在: {step.script_id}")

        # 参数替换 + 无头模式配置（回退到独立浏览器时使用）
        script_content = script.script_content
        params = step.params or {}
        for key, value in params.items():
            script_content = script_content.replace(f"{{{{{key}}}}}", str(value))
        script_content = self._apply_headless_to_script(script_content)

        # 提取导航操作，后续写入执行日志
        navigation_logs = [
            {"action": "navigate", "detail": nav["description"], "url": nav["url"], "status": "info"}
            for nav in self._extract_navigation_urls(script_content)
        ]

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

        # 判断是否使用共享浏览器
        use_shared_browser = self._browser_initialized and self._page is not None

        current_content = script_content
        max_attempts = (step.max_retries or 0) + 1
        exec_log = json.loads(run.execution_log)
        last_error = ""
        fixed = False

        for attempt in range(1, max_attempts + 1):
            try:
                if use_shared_browser:
                    suite_script = self._convert_script_to_suite_mode(current_content)
                    local_vars = {}
                    exec(compile(suite_script, f"suite_script_{script.id}_a{attempt}.py", "exec"), local_vars)
                    if "run_test" in local_vars and callable(local_vars["run_test"]):
                        await local_vars["run_test"](self._page)
                    else:
                        raise RuntimeError("脚本中未找到 run_test 函数")
                else:
                    local_vars = {}
                    exec(compile(current_content, f"suite_script_{script.id}_a{attempt}.py", "exec"), local_vars)
                    if "run_test" in local_vars and callable(local_vars["run_test"]):
                        await local_vars["run_test"]()
                    else:
                        raise RuntimeError("脚本中未找到 run_test 函数")

                # 执行成功
                run_duration = round(time.time() - run_start_time, 2)
                run.status = "passed"
                run.completed_at = china_now_naive()
                run.duration = run_duration
                exec_log.append({
                    "action": "result", "detail": f"执行成功，耗时: {run_duration}s",
                    "timestamp": time.time(), "status": "passed", "duration": run_duration,
                    "script_id": script.id, "shared_browser": use_shared_browser, "attempt": attempt, "fixed": fixed
                })
                run.execution_log = json.dumps(exec_log, ensure_ascii=False)
                self.db.commit()

                result.execution_log = json.dumps(navigation_logs + exec_log, ensure_ascii=False)
                result.duration = run_duration

                # 更新脚本统计
                script.total_runs = (script.total_runs or 0) + 1
                script.last_run_status = "passed"
                script.last_run_at = china_now_naive()
                script.pass_count = (script.pass_count or 0) + 1
                self.db.commit()
                return

            except Exception as e:
                last_error = str(e)
                exec_log.append({
                    "action": "result",
                    "detail": f"第{attempt}次执行失败，错误: {last_error}",
                    "timestamp": time.time(), "status": "failed", "script_id": script.id,
                    "shared_browser": use_shared_browser, "attempt": attempt, "fixed": fixed
                })
                run.execution_log = json.dumps(exec_log, ensure_ascii=False)
                self.db.commit()

                # 判断是否需要AI修复重试
                if step.auto_fix and attempt < max_attempts:
                    logger.info(f"步骤 '{step.step_name}' 第{attempt}次执行失败，启用AI修复")
                    exec_log.append({
                        "action": "ai_fix", "detail": f"调用AI修复脚本（第{attempt}次失败后）",
                        "timestamp": time.time(), "status": "running", "attempt": attempt
                    })
                    run.execution_log = json.dumps(exec_log, ensure_ascii=False)
                    self.db.commit()

                    try:
                        fixed_content = await ScriptGenerator.fix_script_with_ai(
                            script_content=current_content,
                            error_message=last_error,
                            script_name=script.name,
                            target_url=script.target_url or "",
                            db_session=self.db,
                        )
                        if fixed_content and fixed_content != current_content:
                            current_content = self._apply_headless_to_script(fixed_content)
                            fixed = True
                            # 修复成功后同步更新脚本库内容
                            script.script_content = fixed_content
                            script.version = (script.version or 1) + 1
                            script.status = "active"
                            self.db.commit()
                            exec_log.append({
                                "action": "ai_fix", "detail": "AI修复完成，使用修复后脚本重试",
                                "timestamp": time.time(), "status": "success", "attempt": attempt,
                                "new_version": script.version
                            })
                        else:
                            exec_log.append({
                                "action": "ai_fix", "detail": "AI修复未产生变化，停止重试",
                                "timestamp": time.time(), "status": "skipped", "attempt": attempt
                            })
                    except Exception as fix_e:
                        logger.warning(f"AI修复失败: {fix_e}")
                        exec_log.append({
                            "action": "ai_fix", "detail": f"AI修复异常: {fix_e}",
                            "timestamp": time.time(), "status": "failed", "attempt": attempt
                        })

                    run.execution_log = json.dumps(exec_log, ensure_ascii=False)
                    self.db.commit()
                    continue
                else:
                    break

        # 执行失败，抛出异常由 _execute_step 统一处理
        raise RuntimeError(last_error or "脚本步骤执行失败")

    async def _run_case_step(self, step: AutomationSuiteStep, result: AutomationSuiteRunResult) -> None:
        """执行用例类型步骤（动态生成脚本并执行，支持AI自动修复）"""
        if not step.case_id:
            raise ValueError("用例步骤未关联用例")

        case = self.db.query(TestCase).filter(TestCase.id == step.case_id).first()
        if not case:
            raise ValueError(f"用例不存在: {step.case_id}")

        # 简单实现：生成基础脚本并执行
        script_content = ScriptGenerator.generate_template(
            target_url=(case.preconditions or "")[:200],
            name=case.title,
        )
        script_content = self._apply_headless_to_script(script_content)

        # 提取导航操作，后续写入执行日志
        navigation_logs = [
            {"action": "navigate", "detail": nav["description"], "url": nav["url"], "status": "info"}
            for nav in self._extract_navigation_urls(script_content)
        ]

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

        # 判断是否使用共享浏览器
        use_shared_browser = self._browser_initialized and self._page is not None

        current_content = script_content
        max_attempts = (step.max_retries or 0) + 1
        exec_log = json.loads(run.execution_log)
        last_error = ""
        fixed = False

        for attempt in range(1, max_attempts + 1):
            try:
                if use_shared_browser:
                    suite_script = self._convert_script_to_suite_mode(current_content)
                    local_vars = {}
                    exec(compile(suite_script, f"suite_case_{case.id}_a{attempt}.py", "exec"), local_vars)
                    if "run_test" in local_vars and callable(local_vars["run_test"]):
                        await local_vars["run_test"](self._page)
                else:
                    local_vars = {}
                    exec(compile(current_content, f"suite_case_{case.id}_a{attempt}.py", "exec"), local_vars)
                    if "run_test" in local_vars and callable(local_vars["run_test"]):
                        await local_vars["run_test"]()

                # 执行成功
                run_duration = round(time.time() - run_start_time, 2)
                run.status = "passed"
                run.completed_at = china_now_naive()
                run.duration = run_duration
                exec_log.append({
                    "action": "result", "detail": f"执行成功，耗时: {run_duration}s",
                    "timestamp": time.time(), "status": "passed", "duration": run_duration,
                    "shared_browser": use_shared_browser, "attempt": attempt, "fixed": fixed
                })
                run.execution_log = json.dumps(exec_log, ensure_ascii=False)
                self.db.commit()

                result.execution_log = json.dumps(navigation_logs + exec_log, ensure_ascii=False)
                result.duration = run_duration
                return

            except Exception as e:
                last_error = str(e)
                exec_log.append({
                    "action": "result",
                    "detail": f"第{attempt}次执行失败，错误: {last_error}",
                    "timestamp": time.time(), "status": "failed",
                    "shared_browser": use_shared_browser, "attempt": attempt, "fixed": fixed
                })
                run.execution_log = json.dumps(exec_log, ensure_ascii=False)
                self.db.commit()

                # 判断是否需要AI修复重试
                if step.auto_fix and attempt < max_attempts:
                    logger.info(f"用例步骤 '{step.step_name}' 第{attempt}次执行失败，启用AI修复")
                    exec_log.append({
                        "action": "ai_fix", "detail": f"调用AI修复脚本（第{attempt}次失败后）",
                        "timestamp": time.time(), "status": "running", "attempt": attempt
                    })
                    run.execution_log = json.dumps(exec_log, ensure_ascii=False)
                    self.db.commit()

                    try:
                        fixed_content = await ScriptGenerator.fix_script_with_ai(
                            script_content=current_content,
                            error_message=last_error,
                            script_name=case.title,
                            target_url=(case.preconditions or "")[:200],
                            db_session=self.db,
                        )
                        if fixed_content and fixed_content != current_content:
                            current_content = self._apply_headless_to_script(fixed_content)
                            fixed = True
                            exec_log.append({
                                "action": "ai_fix", "detail": "AI修复完成，使用修复后脚本重试",
                                "timestamp": time.time(), "status": "success", "attempt": attempt
                            })
                        else:
                            exec_log.append({
                                "action": "ai_fix", "detail": "AI修复未产生变化，停止重试",
                                "timestamp": time.time(), "status": "skipped", "attempt": attempt
                            })
                    except Exception as fix_e:
                        logger.warning(f"AI修复失败: {fix_e}")
                        exec_log.append({
                            "action": "ai_fix", "detail": f"AI修复异常: {fix_e}",
                            "timestamp": time.time(), "status": "failed", "attempt": attempt
                        })

                    run.execution_log = json.dumps(exec_log, ensure_ascii=False)
                    self.db.commit()
                    continue
                else:
                    break

        # 执行失败，抛出异常由 _execute_step 统一处理
        raise RuntimeError(last_error or "用例步骤执行失败")

    def _apply_headless_to_script(self, script_content: str) -> str:
        """根据当前 headless 设置调整脚本中的浏览器启动参数"""
        from app.services.script_runner import apply_headless_mode
        return apply_headless_mode(script_content, self.headless)

    def stop(self) -> None:
        """停止执行"""
        self.stopped = True
