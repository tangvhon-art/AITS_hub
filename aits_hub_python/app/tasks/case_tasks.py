"""
测试用例 AI 生成 Celery 任务
"""
import json
import logging

from app.celery_app import celery_app
from app.core.task_base import BaseTask
from app.core.timezone import china_now_naive
from app.models.agent_task import AgentTask
from app.models.test_case import TestCase
from app.models.project import Project
from app.models.requirement import TestRequirement, RequirementFeature
from app.agents.case_generator import CaseGeneratorAgent
from app.agents.feature_splitter import FeatureSplitterAgent
from app.services.content_extractor import ContentExtractor
from app.services.ai_creation_service import AICreationService
from app.services.notification_service import notify_event, notify_ai_task_failed
from app.services.workflow_connector import WorkflowInvokeError
from app.services.workflow_runner import run as workflow_run
from app.services.agent_task_status import mark_running, finalize_agent_task
from app.services.agent_backend_dispatcher import resolve_backend

logger = logging.getLogger(__name__)

SPLIT_MODULE_ID = "requirement.split_features"
CASE_MODULE_ID = "case.generate"


class SplitFeaturesTask(BaseTask):
    """需求功能点拆分任务"""

    task_name = "split_requirement_features"

    def execute(self, db, requirement_id: int, page_backend=None, llm_config_id=None) -> dict:
        req = db.query(TestRequirement).filter(
            TestRequirement.id == requirement_id,
            TestRequirement.is_deleted == False,
        ).first()
        if not req:
            logger.error(f"需求不存在: {requirement_id}")
            return {"status": "aborted", "reason": "requirement_not_found"}

        # ── 执行后端分发：页面选择优先 → 模块配置 → local ──
        backend = resolve_backend(db, SPLIT_MODULE_ID, req.project_id, page_choice=page_backend)
        if backend == "workflow":
            try:
                task = AgentTask(
                    project_id=req.project_id,
                    agent_type="feature_splitter",
                    status="pending",
                    backend="workflow",
                    llm_config_id=llm_config_id,
                    input_params={
                        "requirement_id": requirement_id,
                        "requirement_title": req.title or "",
                        "requirement_content": req.content or "",
                    },
                    created_by=None,
                )
                db.add(task)
                db.commit()
                db.refresh(task)

                # workflow 入口由独立 Celery 任务承接（避免阻塞当前 task）
                from app.tasks.workflow_tasks import split_features_workflow_task
                from app.core.tasks import dispatch_task
                dispatch_task(split_features_workflow_task, task.id)
                logger.info(
                    f"功能点拆分走 workflow 后端: req={requirement_id}, task={task.id}"
                )
                return {"status": "pending_workflow", "agent_task_id": task.id}
            except Exception as e:
                logger.warning(
                    f"功能点拆分 workflow 派发失败，降级 local: req={requirement_id}, error={e}"
                )
                # fall through 到 local 逻辑

        req.feature_split_status = "splitting"
        db.commit()

        agent = FeatureSplitterAgent(db_session=db, llm_config_id=llm_config_id, project_id=req.project_id)
        result = agent.split_features(title=req.title, content=req.content or "")
        modules = result.get("modules", [])

        if not modules:
            req.feature_split_status = "failed"
            db.commit()
            logger.warning(f"功能点拆分结果为空: requirement_id={requirement_id}")
            return {"status": "failed", "reason": "empty_modules", "project_id": req.project_id, "source_name": req.title}

        # 软删除旧功能点
        db.query(RequirementFeature).filter(
            RequirementFeature.requirement_id == requirement_id,
            RequirementFeature.is_deleted == False,
        ).update({"is_deleted": True, "deleted_at": china_now_naive()})

        # 插入新功能点
        feature_count = 0
        for mod in modules:
            for feat in mod.get("features", []):
                rf = RequirementFeature(
                    requirement_id=requirement_id,
                    project_id=req.project_id,
                    module_name=mod["module_name"],
                    module_desc=mod.get("module_desc", ""),
                    name=feat["name"],
                    description=feat.get("description", ""),
                    priority=feat.get("priority", "P1"),
                    design_methods=json.dumps(feat.get("design_methods", []), ensure_ascii=False),
                    preconditions=feat.get("preconditions", ""),
                    sort_order=feat.get("sort_order", feature_count),
                )
                db.add(rf)
                feature_count += 1

        req.feature_split_status = "split"
        db.commit()

        logger.info(f"功能点拆分完成: requirement_id={requirement_id}, 模块={len(modules)}, 功能点={feature_count}")

        return {
            "status": "success",
            "project_id": req.project_id,
            "source_name": req.title,
            "module_count": len(modules),
            "feature_count": feature_count,
        }

    def on_success(self, db, result: dict, requirement_id: int, page_backend=None, llm_config_id=None) -> None:
        if result.get("status") != "success":
            return
        # 发送通知
        try:
            notify_event(
                result.get("project_id"),
                "requirement.features_split",
                {
                    "source_name": result.get("source_name"),
                    "module_count": result.get("module_count", 0),
                    "feature_count": result.get("feature_count", 0),
                },
            )
        except Exception as ne:
            logger.warning(f"发送功能点拆分通知失败: {ne}")

    def on_failure(self, db, error: Exception, requirement_id: int, page_backend=None, llm_config_id=None) -> None:
        logger.error(f"功能点拆分失败: requirement_id={requirement_id}, error={error}", exc_info=True)
        try:
            req = db.query(TestRequirement).filter(TestRequirement.id == requirement_id).first()
            if req:
                req.feature_split_status = "failed"
                db.commit()
        except Exception:
            pass


def _update_progress(db, task, done: int, total: int, feat_name: str, case_count: int):
    """更新用例生成进度到 task.output_result。"""
    try:
        task.output_result = {
            "progress": f"{done}/{total}",
            "current_feature": feat_name,
            "case_count_so_far": case_count,
        }
        db.commit()
    except Exception:
        db.rollback()


class GenerateCasesTask(BaseTask):
    """AI 生成测试用例任务"""

    task_name = "generate_cases"

    def execute(self, db, task_id: int) -> dict:
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if not task:
            logger.error(f"AgentTask not found: {task_id}")
            return {"status": "aborted", "reason": "agent_task_not_found"}

        # ── 执行后端分发：页面选择优先 → 模块配置 → local ──
        page_choice = (task.input_params or {}).get("page_backend")
        backend = resolve_backend(db, CASE_MODULE_ID, task.project_id, page_choice=page_choice)
        task.backend = backend
        db.commit()

        if backend == "workflow":
            try:
                workflow_run(db, task, CASE_MODULE_ID)
                # 受理成功：任务挂起，等待 Webhook 回调（不执行本地 LLM）
                return {"status": "pending_workflow"}
            except WorkflowInvokeError as e:
                logger.warning(f"用例生成 workflow 调用失败，降级 local: {e}")
                task.backend = "local"
                task.status = "pending"
                task.error_message = f"workflow 降级: {e}"[:500]
                db.commit()
                # fall through 到 local 逻辑

        task.status = "running"
        db.commit()

        # 取消防护：任务已被用户取消则中止执行
        if not mark_running(db, task):
            db.commit()
            logger.info(f"用例生成任务已被取消，中止执行: task_id={task_id}")
            return {"status": "aborted", "reason": "cancelled"}

        input_params = task.input_params or {}
        project_id = task.project_id
        req_id = input_params.get("requirement_id")
        count = input_params.get("count", 10)
        content = input_params.get("content", "")
        prompt_id = input_params.get("prompt_id")
        feature_ids = input_params.get("feature_ids") or []

        logger.info(f"[generate_cases v2] task_id={task_id}, project_id={project_id}, req_id={req_id}, feature_ids={feature_ids}")

        # 获取需求信息
        requirement_content = content
        requirement_title = ""
        if req_id:
            req = db.query(TestRequirement).filter(
                TestRequirement.id == req_id,
                TestRequirement.project_id == project_id,
            ).first()
            if req:
                requirement_content = req.content or req.title or content
                requirement_title = req.title or ""

        # 获取项目名称
        project = db.query(Project).filter(Project.id == project_id).first()
        project_name = project.name if project else ""

        # 获取已有用例数
        existing_count = db.query(TestCase).filter(
            TestCase.project_id == project_id,
            TestCase.is_deleted == False,
        ).count()

        # 获取自定义 Prompt
        system_prompt = ""
        if prompt_id:
            from app.models.prompt import Prompt
            prompt_obj = db.query(Prompt).filter(
                Prompt.id == prompt_id,
            ).first()
            if prompt_obj:
                system_prompt = prompt_obj.system_prompt or ""
                logger.info(f"使用自定义 Prompt: {prompt_obj.name}")

        # 执行生成
        agent = CaseGeneratorAgent(db_session=db, llm_config_id=task.llm_config_id, project_id=project_id)

        feature_name_map = {}
        if feature_ids and req_id:
            # ── 功能点驱动生成 ──
            features_db = db.query(RequirementFeature).filter(
                RequirementFeature.id.in_(feature_ids),
                RequirementFeature.requirement_id == req_id,
                RequirementFeature.is_deleted == False,
            ).all()

            if not features_db:
                raise ValueError("选中的功能点不存在或已被删除")

            features_data = []
            for f in features_db:
                try:
                    methods = json.loads(f.design_methods) if f.design_methods else []
                except (json.JSONDecodeError, TypeError):
                    methods = []
                features_data.append({
                    "id": f.id,
                    "module_name": f.module_name,
                    "name": f.name,
                    "description": f.description,
                    "priority": f.priority,
                    "design_methods": methods,
                    "preconditions": f.preconditions,
                })
                feature_name_map[f.name] = f.id

            existing_titles = [
                t[0] for t in db.query(TestCase.title).filter(
                    TestCase.project_id == project_id,
                    TestCase.req_id == req_id,
                    TestCase.is_deleted == False,
                ).limit(50).all()
            ]

            logger.info(f"[generate_cases v2] 开始按功能点并行生成: {len(features_data)} 个功能点")

            result = agent.generate_by_features(
                requirement_title=requirement_title,
                requirement_content=requirement_content,
                features=features_data,
                existing_cases=existing_titles,
                system_prompt=system_prompt,
                progress_callback=lambda done, total, name, cnt: _update_progress(db, task, done, total, name, cnt),
            )

            logger.info(f"[generate_cases v2] 生成完成: {result.get('success_count', 0)} 成功, {result.get('fail_count', 0)} 失败, {len(result.get('cases', []))} 条用例")
        else:
            # ── 传统数量驱动生成（兼容旧逻辑） ──
            result = agent.generate(
                requirement_content=requirement_content,
                count=count,
                requirement_title=requirement_title,
                project_name=project_name,
                existing_count=existing_count,
                system_prompt=system_prompt,
            )

        # 提取并创建用例 — 按模块分批生成直接返回 cases 列表，传统模式从 raw_content 解析
        if "cases" in result and isinstance(result["cases"], list):
            cases = result["cases"]
        else:
            cases = ContentExtractor.extract_test_cases(result["raw_content"])
        created_cases = AICreationService.create_test_cases(
            db,
            project_id=project_id,
            cases=cases,
            requirement_id=req_id,
            created_by=task.created_by,
            feature_name_map=feature_name_map or None,
        )

        # 更新需求状态
        if req_id:
            req = db.query(TestRequirement).filter(TestRequirement.id == req_id).first()
            if req and req.status == "pending":
                req.status = "generated"

        finalize_agent_task(db, task, "success")
        task.output_result = {
            "case_count": len(cases),
            "cases_saved": len(created_cases),
        }
        task.llm_config_id = result.get("llm_config_id")
        task.token_usage = result.get("token_usage", {})
        db.commit()

        logger.info(f"用例生成任务完成: task_id={task_id}, saved={len(created_cases)}")

        return {
            "status": "success",
            "task_id": task_id,
            "project_id": project_id,
            "created_by": task.created_by,
            "source_name": requirement_title or "需求",
            "strategy": input_params.get("strategy", "comprehensive"),
            "success_count": len(created_cases),
            "failed_count": len(cases) - len(created_cases),
        }

    def on_success(self, db, result: dict, task_id: int) -> None:
        if result.get("status") != "success":
            return

        # 发送AI用例生成完成通知
        try:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if not task:
                return
            duration = 0.0
            if task.created_at and task.completed_at:
                duration = round((task.completed_at - task.created_at).total_seconds(), 2)
            notify_event(
                result.get("project_id"),
                "ai.case.generated",
                {
                    "source_name": result.get("source_name") or "需求",
                    "strategy": result.get("strategy", "comprehensive"),
                    "success_count": result.get("success_count", 0),
                    "failed_count": result.get("failed_count", 0),
                    "duration": duration,
                },
                triggered_by=result.get("created_by"),
            )
        except Exception as notify_e:
            logger.warning(f"发送用例生成通知失败: {notify_e}")

    def on_failure(self, db, error: Exception, task_id: int) -> None:
        logger.error(f"用例生成任务失败: task_id={task_id}, error={error}", exc_info=True)
        try:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if task:
                finalize_agent_task(db, task, "failed", str(error))
                db.commit()
                notify_ai_task_failed(
                    task.project_id,
                    task_type="功能用例生成",
                    error=str(error),
                    related_object="测试用例生成",
                    triggered_by=task.created_by,
                )
        except Exception:
            pass


@celery_app.task(bind=True, name="split_requirement_features", max_retries=1, queue="ai")
def split_features_task(self, requirement_id: int, page_backend=None, llm_config_id=None):
    """异步拆分需求功能点（page_backend 为页面选择的执行后端，优先级高于系统默认）"""
    return SplitFeaturesTask().run(requirement_id, page_backend=page_backend, llm_config_id=llm_config_id)


@celery_app.task(bind=True, name="generate_cases", max_retries=2, queue="ai")
def generate_cases_task(self, task_id: int):
    """AI 生成测试用例任务"""
    return GenerateCasesTask().run(task_id)
