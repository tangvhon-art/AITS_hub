"""AI 模型五维综合测评 Celery 任务（全部路由 eval 队列）

- RunEvalTask: 编排入口，group 并行调度五维模式子任务，完成后汇总并触发报告/建单/通知
- EvalModeTask: 模式执行（ai_judge/agent/business/redteam 四个薄封装共用）
- RunEvalAggregateTask: 聚合任务（chord body）
- GenerateEvalReportTask / AutoCreateEvalIssuesTask: 报告与问题闭环
"""
import logging

from celery import group

from app.celery_app import celery_app
from app.core.task_base import BaseTask
from app.core.timezone import china_now_naive
from app.core.tasks import dispatch_task
from app.models.eval import EvalTask, EvalRun, EvalDataset, EvalReport
from app.services import eval_service

logger = logging.getLogger(__name__)


def _get_run(db, run_id: int):
    return db.query(EvalRun).filter(EvalRun.id == run_id).first()


def _get_task(db, task_id: int):
    return db.query(EvalTask).filter(EvalTask.id == task_id).first()


def _get_dataset(db, dataset_id):
    return db.query(EvalDataset).filter(EvalDataset.id == dataset_id).first()


def _notify(db, task: EvalTask):
    """测评完成事件通知（复用事件通知，失败不影响主流程）"""
    try:
        from app.services.notification_service import notify_event
        notify_event(
            db, event_type="eval_task_completed",
            title=f"测评任务完成：{task.name}",
            content=f"结论：{task.conclusion}；五维汇总：{task.summary}",
            project_id=None,  # AI 测评系统级，不归属项目
        )
    except Exception as e:
        logger.warning(f"测评完成通知失败: {e}")


# ---------------------------------------------------------------------------
# 模式执行子任务
# ---------------------------------------------------------------------------
class EvalModeTask(BaseTask):
    """单模式测评执行"""

    task_name = "eval_mode"

    def execute(self, db, run_id: int, mode: str, task_id: int) -> dict:
        run = _get_run(db, run_id)
        if not run:
            logger.error(f"[eval][{mode}] run 不存在: {run_id}")
            return {"status": "aborted", "reason": "run_not_found", "mode": mode, "run_id": run_id}
        task = _get_task(db, task_id)
        dataset = _get_dataset(db, run.dataset_id)
        if mode == "ai_judge":
            eval_service.run_mode_ai_judge(db, task, run, dataset, task.judge_config_ids, task.settings)
        elif mode == "agent":
            eval_service.run_mode_agent(db, task, run, dataset, task.settings)
        elif mode == "business":
            eval_service.run_mode_business(db, task, run, dataset, task.settings)
        elif mode == "redteam":
            eval_service.run_mode_redteam(db, task, run, dataset, task.settings)
        else:
            logger.warning(f"[eval][{mode}] 未支持的模式，跳过")
            run.status = "completed"; run.completed_at = china_now_naive(); db.commit()
        return {"mode": mode, "run_id": run_id}

    def on_failure(self, db, error: Exception, run_id: int, mode: str, task_id: int) -> None:
        logger.exception(f"[eval][{mode}] 执行失败 run={run_id}")
        try:
            run = _get_run(db, run_id)
            if run:
                run.status = "failed"; db.commit()
        except Exception:
            pass


def _execute_mode(run_id: int, mode: str, task_id: int):
    return EvalModeTask().run(run_id, mode, task_id)


@celery_app.task(bind=True, name="run_ai_judge_eval", max_retries=0, queue="eval")
def run_ai_judge_eval(self, eval_run_id: int, eval_task_id: int, **kw):
    return _execute_mode(eval_run_id, "ai_judge", eval_task_id)


@celery_app.task(bind=True, name="run_agent_eval", max_retries=0, queue="eval")
def run_agent_eval(self, eval_run_id: int, eval_task_id: int, **kw):
    return _execute_mode(eval_run_id, "agent", eval_task_id)


@celery_app.task(bind=True, name="run_business_eval", max_retries=0, queue="eval")
def run_business_eval(self, eval_run_id: int, eval_task_id: int, **kw):
    return _execute_mode(eval_run_id, "business", eval_task_id)


@celery_app.task(bind=True, name="run_redteam_eval", max_retries=0, queue="eval")
def run_redteam_eval(self, eval_run_id: int, eval_task_id: int, **kw):
    return _execute_mode(eval_run_id, "redteam", eval_task_id)


# ---------------------------------------------------------------------------
# 任务编排入口
# ---------------------------------------------------------------------------
class RunEvalTask(BaseTask):
    """测评任务编排：创建各模式 run，chord 并行调度子任务"""

    task_name = "run_eval_task"

    def execute(self, db, eval_task_id: int) -> dict:
        task = _get_task(db, eval_task_id)
        if not task:
            logger.error(f"[eval] 任务不存在: {eval_task_id}")
            return {"error": "task not found"}
        task.status = "running"
        task.started_at = china_now_naive()
        task.progress = 5
        db.commit()

        # 创建各模式 run（datasets 从 task.dataset_ids 取）
        sigs = []
        for mode, dataset_ids in (task.dataset_ids or {}).items():
            for did in (dataset_ids or []):
                run = EvalRun(eval_task_id=task.id, mode=mode, dataset_id=did, status="pending")
                db.add(run); db.commit()
                run_id = run.id
                if mode == "ai_judge":
                    sigs.append(run_ai_judge_eval.s(run_id, task.id))
                elif mode == "agent":
                    sigs.append(run_agent_eval.s(run_id, task.id))
                elif mode == "business":
                    sigs.append(run_business_eval.s(run_id, task.id))
                elif mode == "redteam":
                    sigs.append(run_redteam_eval.s(run_id, task.id))

        # chord：header 并行执行模式子任务，全部完成后执行聚合任务
        if sigs:
            header = group(sigs)
            chord = header | run_eval_aggregate.s(task.id)
            chord.apply_async(queue="eval")
            return {"task_id": task.id, "dispatched": len(sigs)}
        # 无任何模式子任务时直接聚合
        run_eval_aggregate(task.id)
        return {"task_id": task.id, "dispatched": 0}

    def on_failure(self, db, error: Exception, eval_task_id: int) -> None:
        logger.exception(f"[eval] run_eval_task 编排失败: {eval_task_id}")
        try:
            task = _get_task(db, eval_task_id)
            if task and task.status == "running":
                task.status = "failed"
                task.completed_at = china_now_naive()
                db.commit()
        except Exception:
            pass


@celery_app.task(bind=True, name="run_eval_task", max_retries=0, queue="eval")
def run_eval_task(self, eval_task_id: int, **kw):
    """编排：为任务创建各模式 run，chord 并行调度子任务，完成后由聚合任务汇总"""
    return RunEvalTask().run(eval_task_id)


class RunEvalAggregateTask(BaseTask):
    """聚合任务：汇总五维结果 → 结论 → 报告 → 自动建单 → 通知"""

    task_name = "run_eval_aggregate"

    def execute(self, db, header_results: list = None, eval_task_id: int = 0) -> dict:
        task = _get_task(db, eval_task_id)
        if not task:
            return {"error": "task not found"}
        # 汇总 + 结论
        agg = eval_service.aggregate_task(db, task)
        task.progress = 90
        db.commit()
        # 问题自动建单
        issues = eval_service.auto_create_issues(db, task)
        # 报告生成
        report_content = eval_service.generate_report_content(db, task)
        db.add(EvalReport(
            eval_task_id=task.id, report_type="overall",
            title=f"{task.name} · 总报告", content=report_content["content"],
            summary=report_content["summary"], conclusion=report_content["conclusion"],
            status="completed", created_by=task.created_by,
        ))
        task.progress = 100
        db.commit()
        _notify(db, task)
        return {"task_id": task.id, "conclusion": task.conclusion, "issues": len(issues)}

    def on_failure(self, db, error: Exception, header_results: list = None, eval_task_id: int = 0) -> None:
        logger.exception(f"[eval] run_eval_aggregate 聚合失败: {eval_task_id}")
        try:
            task = _get_task(db, eval_task_id)
            if task:
                task.status = "failed"
                task.completed_at = china_now_naive()
                db.commit()
        except Exception:
            pass


@celery_app.task(bind=True, name="run_eval_aggregate", max_retries=0, queue="eval")
def run_eval_aggregate(self, header_results: list = None, eval_task_id: int = 0, *args, **kw):
    """聚合任务：汇总五维结果 → 结论 → 报告 → 自动建单 → 通知

    chord body：第一个位置参数为 header 子任务结果列表，第二个为 eval_task_id。
    """
    return RunEvalAggregateTask().run(header_results, eval_task_id)


# ---------------------------------------------------------------------------
# 报告生成（独立触发，可委派外部工作流 M5）
# ---------------------------------------------------------------------------
class GenerateEvalReportTask(BaseTask):
    """生成测评报告"""

    task_name = "generate_eval_report"

    def execute(self, db, eval_task_id: int, report_type: str = "overall") -> dict:
        task = _get_task(db, eval_task_id)
        if not task:
            return {"error": "task not found"}
        content = eval_service.generate_report_content(db, task)
        report = db.query(EvalReport).filter(
            EvalReport.eval_task_id == task.id, EvalReport.report_type == report_type,
        ).first()
        if not report:
            report = EvalReport(
                eval_task_id=task.id, report_type=report_type,
                title=f"{task.name} · 报告", status="generating", created_by=task.created_by,
            )
            db.add(report); db.commit()
        report.content = content["content"]
        report.summary = content["summary"]
        report.conclusion = content["conclusion"]
        report.status = "completed"
        db.commit()
        return {"report_id": report.id, "conclusion": content["conclusion"]}


@celery_app.task(bind=True, name="generate_eval_report", max_retries=0, queue="eval")
def generate_eval_report(self, eval_task_id: int, report_type: str = "overall", **kw):
    return GenerateEvalReportTask().run(eval_task_id, report_type=report_type)


class AutoCreateEvalIssuesTask(BaseTask):
    """测评问题自动建单"""

    task_name = "auto_create_eval_issues"

    def execute(self, db, eval_task_id: int) -> dict:
        task = _get_task(db, eval_task_id)
        if not task:
            return {"error": "task not found"}
        issues = eval_service.auto_create_issues(db, task)
        return {"task_id": task.id, "issues": [i.id for i in issues]}


@celery_app.task(bind=True, name="auto_create_eval_issues", max_retries=0, queue="eval")
def auto_create_eval_issues(self, eval_task_id: int, **kw):
    return AutoCreateEvalIssuesTask().run(eval_task_id)
