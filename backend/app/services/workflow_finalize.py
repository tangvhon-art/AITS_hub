"""
工作流回调结果写库闭环

复用 ContentExtractor + AICreationService，对回调 raw_content 进行解析并写库。
local 与 workflow 后端使用同一套 finalize_* 函数，避免双轨写库逻辑。

每个 finalize_* 函数：
- 输入：AgentTask（已带 input_params）+ raw_content（外部 agent 输出文本）
- 输出：写入业务表 + 更新 task.status/output_result/completed_at + 发送通知
- 失败：抛异常由 handle_workflow_callback_task 接住并触发降级 local
"""
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.timezone import china_now_naive
from app.models.agent_task import AgentTask
from app.models.requirement import TestRequirement, RequirementFeature
from app.models.test_case import TestCase
from app.services.content_extractor import ContentExtractor
from app.services.ai_creation_service import AICreationService
from app.services.notification_service import notify_event, notify_ai_task_failed

logger = logging.getLogger(__name__)


def _finalize_failed(db: Session, task: AgentTask, error: str, module_id: str) -> None:
    """标记任务失败并发送通知（不抛异常，由调用方决定是否继续降级）"""
    try:
        task.status = "failed"
        task.error_message = (error or "")[:500]
        task.completed_at = china_now_naive()
        db.commit()
    except Exception:
        db.rollback()
    try:
        notify_ai_task_failed(
            task.project_id,
            task_type=module_id or task.agent_type,
            error=error,
            related_object=task.agent_type,
            triggered_by=task.created_by,
        )
    except Exception as ne:
        logger.warning(f"[finalize] 发送失败通知异常: {ne}")


def finalize_requirement(db: Session, task: AgentTask, raw_content: str) -> None:
    """需求生成写库闭环

    与 generate_requirement_task 的写库段保持一致：
    ContentExtractor.extract_requirement → AICreationService.create_requirement
    """
    params = task.input_params or {}
    project_id = task.project_id
    version_id = params.get("version_id")
    module_id = "requirement.generate"

    try:
        extracted = ContentExtractor.extract_requirement(raw_content)
        requirement = AICreationService.create_requirement(
            db,
            project_id=project_id,
            title=extracted["title"],
            content=extracted["content"],
            version_id=version_id,
            created_by=task.created_by,
        )
        task.status = "success"
        task.output_result = {
            "requirement_id": requirement.id,
            "title": requirement.title,
        }
        task.completed_at = china_now_naive()
        db.commit()

        try:
            duration = 0.0
            if task.created_at and task.completed_at:
                duration = round((task.completed_at - task.created_at).total_seconds(), 2)
            version_name = "-"
            if version_id:
                from app.models.project_version import ProjectVersion
                ver = db.query(ProjectVersion).filter(ProjectVersion.id == version_id).first()
                if ver:
                    version_name = ver.name
            notify_event(
                project_id,
                "ai.requirement.generated",
                {
                    "requirement_id": requirement.id,
                    "requirement_title": requirement.title,
                    "version_name": version_name,
                    "success": True,
                    "duration": duration,
                },
                triggered_by=task.created_by,
            )
        except Exception as ne:
            logger.warning(f"[finalize_requirement] 通知失败: {ne}")
    except Exception as e:
        logger.exception(f"[finalize_requirement] 失败: task_id={task.id}, error={e}")
        _finalize_failed(db, task, str(e), module_id)
        raise


def finalize_split_features(db: Session, task: AgentTask, raw_content: str) -> None:
    """功能点拆分写库闭环

    复用 FeatureSplitterAgent._parse_modules 解析 modules，
    按 task.input_params.requirement_id 定位需求并落库。
    """
    params = task.input_params or {}
    requirement_id = params.get("requirement_id")
    module_id = "requirement.split_features"

    try:
        if not requirement_id:
            raise ValueError("input_params.requirement_id 缺失")
        req = db.query(TestRequirement).filter(
            TestRequirement.id == requirement_id,
            TestRequirement.is_deleted == False,  # noqa: E712
        ).first()
        if not req:
            raise ValueError(f"需求不存在: {requirement_id}")

        from app.agents.feature_splitter import FeatureSplitterAgent
        modules = FeatureSplitterAgent._parse_modules(raw_content)
        if not modules:
            req.feature_split_status = "failed"
            db.commit()
            raise ValueError("功能点拆分结果为空")

        # 软删除旧功能点
        db.query(RequirementFeature).filter(
            RequirementFeature.requirement_id == requirement_id,
            RequirementFeature.is_deleted == False,  # noqa: E712
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
        task.status = "success"
        task.output_result = {
            "module_count": len(modules),
            "feature_count": feature_count,
        }
        task.completed_at = china_now_naive()
        db.commit()

        try:
            notify_event(
                req.project_id,
                "requirement.features_split",
                {
                    "source_name": req.title,
                    "module_count": len(modules),
                    "feature_count": feature_count,
                },
            )
        except Exception as ne:
            logger.warning(f"[finalize_split_features] 通知失败: {ne}")
    except Exception as e:
        logger.exception(f"[finalize_split_features] 失败: task_id={task.id}, error={e}")
        try:
            req = db.query(TestRequirement).filter(TestRequirement.id == requirement_id).first()
            if req:
                req.feature_split_status = "failed"
                db.commit()
        except Exception:
            db.rollback()
        _finalize_failed(db, task, str(e), module_id)
        raise


def finalize_cases(db: Session, task: AgentTask, raw_content: str) -> None:
    """用例生成写库闭环

    与 generate_cases_task 的写库段保持一致：
    ContentExtractor.extract_test_cases → AICreationService.create_test_cases
    """
    params = task.input_params or {}
    project_id = task.project_id
    req_id = params.get("requirement_id")
    feature_ids = params.get("feature_ids") or []
    module_id = "case.generate"

    try:
        cases = ContentExtractor.extract_test_cases(raw_content)
        if not cases:
            raise ValueError("从外部回调内容中未能解析出测试用例")

        # 构建 feature_name_map（与 generate_cases_task 一致）
        feature_name_map: Dict[str, int] = {}
        if feature_ids and req_id:
            feats = db.query(RequirementFeature).filter(
                RequirementFeature.id.in_(feature_ids),
                RequirementFeature.requirement_id == req_id,
                RequirementFeature.is_deleted == False,  # noqa: E712
            ).all()
            for f in feats:
                feature_name_map[f.name] = f.id

        created = AICreationService.create_test_cases(
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

        task.status = "success"
        task.output_result = {
            "case_count": len(cases),
            "cases_saved": len(created),
        }
        task.completed_at = china_now_naive()
        db.commit()

        try:
            duration = 0.0
            if task.created_at and task.completed_at:
                duration = round((task.completed_at - task.created_at).total_seconds(), 2)
            req_title = params.get("requirement_title") or "需求"
            notify_event(
                project_id,
                "ai.case.generated",
                {
                    "source_name": req_title,
                    "strategy": "workflow",
                    "success_count": len(created),
                    "failed_count": len(cases) - len(created),
                    "duration": duration,
                },
                triggered_by=task.created_by,
            )
        except Exception as ne:
            logger.warning(f"[finalize_cases] 通知失败: {ne}")
    except Exception as e:
        logger.exception(f"[finalize_cases] 失败: task_id={task.id}, error={e}")
        _finalize_failed(db, task, str(e), module_id)
        raise


def finalize_review(db: Session, task: AgentTask, raw_content: str) -> None:
    """用例评审写库闭环（评审结果存 task.output_result，不写业务表）

    与 review_cases_task 的解析+回填段保持一致：
    ContentExtractor.extract_review → 回填 issue 元数据 → 写 task.output_result
    """
    params = task.input_params or {}
    cases = params.get("cases", [])
    requirements = params.get("requirements", [])
    groups = params.get("groups", [])
    module_id = "case.review"

    try:
        extracted = ContentExtractor.extract_review(raw_content)

        # 回填 issue 元数据（与 review_cases_task 一致）
        issues = extracted.get("issues", [])
        if issues:
            req_title_map: Dict[Any, str] = {}
            for r in requirements:
                if r.get("id") is not None and r.get("title"):
                    req_title_map[r["id"]] = r["title"]
            for g in groups:
                rid = g.get("requirement_id")
                if rid is not None and g.get("requirement_title") and not req_title_map.get(rid):
                    req_title_map[rid] = g["requirement_title"]
            missing_ids = {
                c.get("req_id") for c in cases
                if c.get("req_id") and c.get("req_id") not in req_title_map
            }
            if missing_ids:
                rows = db.query(TestRequirement.id, TestRequirement.title).filter(
                    TestRequirement.id.in_(list(missing_ids)),
                    TestRequirement.is_deleted == False,  # noqa: E712
                ).all()
                for rid, title in rows:
                    if title:
                        req_title_map[rid] = title

            case_meta_map: Dict[Any, Dict[str, str]] = {}
            for case in cases:
                cid = case.get("id")
                if cid is not None:
                    case_meta_map[cid] = {
                        "module": case.get("module", "") or "",
                        "requirement_title": req_title_map.get(case.get("req_id"), "") or "",
                    }
            for issue in issues:
                cid = issue.get("case_id")
                if cid is not None and cid in case_meta_map:
                    meta = case_meta_map[cid]
                    if not issue.get("module"):
                        issue["module"] = meta["module"]
                    cur_title = (issue.get("requirement_title") or "").strip()
                    if meta["requirement_title"] and (
                        not cur_title
                        or "需求ID=" in cur_title
                        or cur_title == "未关联需求"
                    ):
                        issue["requirement_title"] = meta["requirement_title"]

        result = {**extracted, "raw_content": raw_content}
        task.status = "success"
        task.output_result = result
        task.completed_at = china_now_naive()
        db.commit()

        try:
            duration = 0.0
            if task.created_at and task.completed_at:
                duration = round((task.completed_at - task.created_at).total_seconds(), 2)
            notify_event(
                task.project_id,
                "ai.case_review.completed",
                {
                    "score": result.get("score"),
                    "passed": result.get("passed"),
                    "case_count": len(cases),
                    "duration": duration,
                },
                triggered_by=task.created_by,
            )
        except Exception as ne:
            logger.warning(f"[finalize_review] 通知失败: {ne}")
    except Exception as e:
        logger.exception(f"[finalize_review] 失败: task_id={task.id}, error={e}")
        _finalize_failed(db, task, str(e), module_id)
        raise


# module_id → finalize 函数路由表
FINALIZE_MAP = {
    "requirement.generate": finalize_requirement,
    "requirement.split_features": finalize_split_features,
    "case.generate": finalize_cases,
    "case.review": finalize_review,
}
