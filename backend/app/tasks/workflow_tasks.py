"""
工作流接入相关 Celery 任务

- WorkflowCallbackTask: Webhook 回调到达后，按 uuid 定位任务，
  复用 finalize_* 公共函数解析 raw_content 写库
- SplitFeaturesWorkflowTask: 功能点拆分模块的 workflow 后端入口
  （split_features 原本不基于 AgentTask，需新建 task 包装）
- scan_workflow_timeout_task: 定时扫描超时未回调的 workflow 任务，
  触发降级 local 重跑（v0.7 确认 #6）
"""
import logging
from datetime import timedelta

from app.celery_app import celery_app
from app.core.task_base import BaseTask
from app.core.timezone import china_now_naive
from app.core.tasks import dispatch_task
from app.models.agent_task import AgentTask
from app.services.workflow_config_service import (
    AGENT_TYPE_TO_MODULE, get_callback_timeout,
)
from app.services.workflow_runner import run as workflow_run
from app.services.workflow_connector import WorkflowInvokeError
from app.services.workflow_call_logger import log_call
from app.services.workflow_finalize import FINALIZE_MAP, _finalize_failed

logger = logging.getLogger(__name__)


def _fallback_to_local(db, task: AgentTask, error: str) -> None:
    """降级到 local 重跑：标记 backend=local 后重新派发对应 local Celery 任务

    v0.7 确认 #6：外部平台调用失败 / 回调处理失败 / 超时未回调 时自动降级。
    优先从模块注册表获取降级配置，未注册的模块走 if-elif 兜底。
    """
    from app.tasks.requirement_tasks import generate_requirement_task
    from app.tasks.case_tasks import generate_cases_task, split_features_task
    from app.tasks.review_tasks import review_cases_task
    from app.tasks.report_tasks import generate_test_report_task

    module_id = AGENT_TYPE_TO_MODULE.get(task.agent_type)
    logger.warning(
        f"[workflow_fallback] task {task.id} 降级 local: module={module_id}, error={error}"
    )

    log_call(
        db, agent_task_id=task.id, module_id=module_id or task.agent_type,
        uuid=task.uuid, phase="fail", status="failed",
        fallback_used=True, error_msg=f"降级 local: {error}"[:2000],
    )

    # 清空 workflow 字段，标记降级，重新派发 local 任务
    task.backend = "local"
    task.uuid = None
    task.external_task_id = None
    task.status = "pending"
    task.error_message = f"workflow 降级: {error}"[:500]
    db.commit()

    # 优先从模块注册表获取降级配置
    try:
        from app.services.workflow_modules import ensure_registered
        from app.services.workflow_registry import WorkflowModuleRegistry
        ensure_registered()
        fallback_info = WorkflowModuleRegistry.get_fallback(module_id)
        if fallback_info:
            fallback_task_fn, args_builder = fallback_info
            args = args_builder(task) if args_builder else (task.id,)
            if args:
                # split_features 等特殊模块需要延迟导入 task 函数
                if module_id == "requirement.split_features":
                    dispatch_task(split_features_task, *args)
                elif module_id == "report.generate":
                    dispatch_task(generate_test_report_task, *args)
                elif module_id == "requirement.generate":
                    dispatch_task(generate_requirement_task, *args)
                elif module_id == "case.generate":
                    dispatch_task(generate_cases_task, *args)
                elif module_id == "case.review":
                    dispatch_task(review_cases_task, *args)
                else:
                    dispatch_task(fallback_task_fn, *args)
                return
    except Exception as e:
        logger.warning(f"[workflow_fallback] 注册表降级失败，走 if-elif 兜底: {e}")

    # if-elif 兜底（向后兼容）
    if module_id == "requirement.generate":
        dispatch_task(generate_requirement_task, task.id)
    elif module_id == "case.generate":
        dispatch_task(generate_cases_task, task.id)
    elif module_id == "case.review":
        dispatch_task(review_cases_task, task.id)
    elif module_id == "requirement.split_features":
        req_id = (task.input_params or {}).get("requirement_id")
        if req_id:
            dispatch_task(split_features_task, req_id, task.llm_config_id)
    elif module_id == "report.generate":
        params = task.input_params or {}
        report_id = params.get("report_id")
        if report_id:
            dispatch_task(
                generate_test_report_task,
                report_id, task.project_id,
                params.get("report_type", "full"),
                params.get("version_id"),
                params.get("title", "测试报告"),
                task.llm_config_id, task.id,
            )
    else:
        logger.error(f"[workflow_fallback] 未支持的 module_id: {module_id}")


class WorkflowCallbackTask(BaseTask):
    """处理 Webhook 回调：按 agent_type 路由到对应 finalize_* 函数

    幂等性：Webhook 端点已做幂等检查（status in success/failed 时直接返回），
    此处再次校验避免重复处理。
    """

    task_name = "handle_workflow_callback"

    def execute(self, db, task_id: int, raw_content: str, status: str = "success") -> dict:
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if not task:
            logger.error(f"[workflow_callback] AgentTask not found: {task_id}")
            return {"status": "aborted", "reason": "agent_task_not_found"}

        # 幂等：任务已完成/失败则跳过
        if task.status in ("success", "failed"):
            logger.info(
                f"[workflow_callback] task {task_id} 已处理 status={task.status}，跳过"
            )
            return {"status": "skipped", "reason": "already_finalized"}

        module_id = AGENT_TYPE_TO_MODULE.get(task.agent_type)
        if not module_id:
            raise ValueError(f"未知的 agent_type: {task.agent_type}")

        # 失败回调：直接降级 local
        if status == "failed":
            err = (raw_content or "外部工作流执行失败")[:500]
            log_call(
                db, agent_task_id=task.id, module_id=module_id, uuid=task.uuid,
                phase="callback", status="failed", error_msg=err,
            )
            _fallback_to_local(db, task, err)
            return {"status": "fallback", "reason": "workflow_failed"}

        # 成功回调：派发到 finalize_*
        log_call(
            db, agent_task_id=task.id, module_id=module_id, uuid=task.uuid,
            phase="callback", status="success",
            response_json={"content_len": len(raw_content) if raw_content else 0},
        )

        finalize_fn = FINALIZE_MAP.get(module_id)
        if not finalize_fn:
            raise ValueError(f"未实现 finalize 函数: module_id={module_id}")

        finalize_fn(db, task, raw_content)

        log_call(
            db, agent_task_id=task.id, module_id=module_id, uuid=task.uuid,
            phase="complete", status="success",
        )
        logger.info(
            f"[workflow_callback] task {task_id} 完成 finalize, module={module_id}"
        )
        return {"status": "success", "task_id": task_id}

    def on_failure(self, db, error: Exception, task_id: int, raw_content: str, status: str = "success") -> None:
        logger.exception(f"[workflow_callback] 处理失败: task_id={task_id}, error={error}")
        try:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if task and task.status not in ("success", "failed"):
                _fallback_to_local(db, task, str(error))
        except Exception:
            pass


class SplitFeaturesWorkflowTask(BaseTask):
    """功能点拆分的 workflow 后端入口

    split_features 原本不基于 AgentTask（直接传 requirement_id），此处通过
    创建 AgentTask 包装后，复用 workflow_runner.run() 发起外部调用；
    失败时降级到 split_features_task（local 入口）。
    """

    task_name = "split_features_workflow"

    def execute(self, db, task_id: int) -> dict:
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if not task:
            logger.error(f"AgentTask not found: {task_id}")
            return {"status": "aborted", "reason": "agent_task_not_found"}

        try:
            workflow_run(db, task, "requirement.split_features")
        except WorkflowInvokeError as e:
            logger.warning(f"功能点拆分 workflow 调用失败，降级 local: {e}")
            _fallback_to_local(db, task, str(e))
        return {"status": "success", "task_id": task_id}

    def on_failure(self, db, error: Exception, task_id: int) -> None:
        logger.exception(f"split_features_workflow_task 失败: task_id={task_id}, error={error}")
        try:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if task:
                _fallback_to_local(db, task, str(error))
        except Exception:
            pass


@celery_app.task(bind=True, name="handle_workflow_callback", max_retries=0, queue="ai")
def handle_workflow_callback_task(self, task_id: int, raw_content: str, status: str = "success"):
    """处理 Webhook 回调：按 agent_type 路由到对应 finalize_* 函数"""
    return WorkflowCallbackTask().run(task_id, raw_content, status=status)


@celery_app.task(bind=True, name="split_features_workflow", max_retries=0, queue="ai")
def split_features_workflow_task(self, task_id: int):
    """功能点拆分的 workflow 后端入口"""
    return SplitFeaturesWorkflowTask().run(task_id)


@celery_app.task(name="scan_workflow_timeout", queue="default")
def scan_workflow_timeout_task():
    """定时扫描超时未回调的 workflow 任务，触发降级 local 重跑

    触发条件：backend=workflow 且 status=running 且
    距 created_at 已超过 callback_timeout 秒（默认 1800s = 30 分钟）

    建议 beat 每 5 分钟调度一次（由 sys_crontab 配置）。
    """
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        callback_timeout = get_callback_timeout(db)
        now = china_now_naive()
        threshold = now - timedelta(seconds=callback_timeout)

        tasks = db.query(AgentTask).filter(
            AgentTask.backend == "workflow",
            AgentTask.status == "running",
            AgentTask.created_at < threshold,
        ).all()

        if not tasks:
            return

        logger.info(f"[workflow_timeout] 扫描到 {len(tasks)} 个超时任务")
        for t in tasks:
            try:
                _fallback_to_local(db, t, f"回调超时({callback_timeout}s)未收到")
            except Exception as e:
                logger.exception(f"[workflow_timeout] 降级失败 task={t.id}: {e}")
    except Exception as e:
        logger.exception(f"[workflow_timeout] 扫描失败: {e}")
    finally:
        db.close()
