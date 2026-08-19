"""
AI 创建服务

统一 AI 生成内容的创建逻辑，复用与 API 端点相同的校验和默认值规则。
Celery 任务和 API 端点都调用此 Service，确保数据一致性。
"""
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.requirement import TestRequirement
from app.models.test_case import TestCase
from app.models.defect import Defect
from app.models.report import TestReport
from app.models.api_test import ApiTestCase, ApiCaseAssertion
from app.core.timezone import china_now_naive

logger = logging.getLogger(__name__)


class AICreationService:
    """统一 AI 内容创建服务"""

    # ==================== 需求创建 ====================

    @staticmethod
    def create_requirement(
        db: Session,
        project_id: int,
        title: str,
        content: str,
        version_id: Optional[int] = None,
        created_by: Optional[int] = None,
    ) -> TestRequirement:
        """创建需求文档（复用 API 校验逻辑）"""
        requirement = TestRequirement(
            project_id=project_id,
            title=title or "AI 生成需求",
            content=content or "",
            source="ai",
            version_id=version_id,
            status="generated",
            created_by=created_by,
        )
        db.add(requirement)
        db.commit()
        db.refresh(requirement)
        logger.info(f"AI 需求创建成功: id={requirement.id}, title={requirement.title}")

        # 异步触发功能点拆分
        if content and content.strip():
            from app.core.tasks import dispatch_task
            from app.tasks.case_tasks import split_features_task
            dispatch_task(split_features_task, requirement.id)

        return requirement

    # ==================== 用例创建 ====================

    @staticmethod
    def create_test_cases(
        db: Session,
        project_id: int,
        cases: List[Dict[str, Any]],
        requirement_id: Optional[int] = None,
        created_by: Optional[int] = None,
        feature_name_map: Optional[Dict[str, int]] = None,
    ) -> List[TestCase]:
        """批量创建测试用例（复用 API 校验逻辑）

        Args:
            feature_name_map: 功能点名称 → feature_id 的映射，用于关联功能点
        """
        created = []
        errors = []
        for case_data in cases:
            try:
                steps = case_data.get("steps") or []
                if isinstance(steps, list):
                    steps_json = json.dumps(steps, ensure_ascii=False)
                else:
                    steps_json = str(steps)

                # 关联功能点
                feature_id = None
                if feature_name_map:
                    fname = case_data.get("feature_name", "")
                    feature_id = feature_name_map.get(fname)

                case = TestCase(
                    project_id=project_id,
                    req_id=requirement_id,
                    feature_id=feature_id,
                    title=case_data.get("title", "未命名用例")[:200],
                    module=case_data.get("module") or "",
                    priority=case_data.get("priority") or "P2",
                    case_type=case_data.get("case_type") or "functional",
                    preconditions=case_data.get("preconditions") or "",
                    steps=steps_json,
                    expected_result=case_data.get("expected_result") or "",
                    bdd_content=case_data.get("bdd_content") or "",
                    created_by=created_by,
                )
                db.add(case)
                created.append(case)
            except Exception as e:
                errors.append({"title": case_data.get("title", ""), "error": str(e)})
                logger.warning(f"用例创建失败: {e}")

        db.commit()
        for case in created:
            db.refresh(case)
        logger.info(f"AI 用例批量创建: 成功 {len(created)} 条, 失败 {len(errors)} 条")
        return created

    # ==================== 接口用例创建 ====================

    @staticmethod
    def create_api_cases(
        db: Session,
        project_id: int,
        cases: List[Dict[str, Any]],
        api_id: Optional[int] = None,
        module_id: Optional[int] = None,
        created_by: Optional[int] = None,
    ) -> List[ApiTestCase]:
        """批量创建接口测试用例"""
        created = []
        for case_data in cases:
            try:
                request_data = case_data.get("request") or {}
                assertions = case_data.get("assertions") or []

                case = ApiTestCase(
                    project_id=project_id,
                    api_id=api_id,
                    module_id=module_id,
                    name=case_data.get("name", "未命名用例")[:200],
                    description=case_data.get("description") or "",
                    priority=case_data.get("priority") or "P2",
                    headers=request_data.get("headers") if isinstance(request_data.get("headers"), str) else None,
                    query_params=request_data.get("params") if isinstance(request_data.get("params"), str) else None,
                    body_content=json.dumps(request_data.get("body"), ensure_ascii=False) if request_data.get("body") else None,
                )
                db.add(case)
                db.flush()

                # 创建断言
                for assertion_data in assertions:
                    if not isinstance(assertion_data, dict):
                        continue
                    assertion = ApiCaseAssertion(
                        case_id=case.id,
                        assert_type=assertion_data.get("type") or assertion_data.get("assert_type") or "status_code",
                        assert_target=assertion_data.get("target") or assertion_data.get("assert_target") or "",
                        operator=assertion_data.get("operator") or "equals",
                        expected_value=str(assertion_data.get("expected") or assertion_data.get("expected_value") or ""),
                        enabled=True,
                    )
                    db.add(assertion)

                created.append(case)
            except Exception as e:
                logger.warning(f"接口用例创建失败: {case_data.get('name', '')}, error={e}")

        db.commit()
        for case in created:
            db.refresh(case)
        logger.info(f"AI 接口用例批量创建: 成功 {len(created)} 条")
        return created

    # ==================== 缺陷创建 ====================

    @staticmethod
    def create_defect(
        db: Session,
        project_id: int,
        defect_data: Dict[str, Any],
        run_id: Optional[int] = None,
        case_id: Optional[int] = None,
        version_id: Optional[int] = None,
        created_by: Optional[int] = None,
    ) -> Defect:
        """创建缺陷（复用 API 校验逻辑）"""
        defect = Defect(
            project_id=project_id,
            run_id=run_id,
            case_id=case_id,
            title=defect_data.get("title", "执行失败")[:200],
            description=defect_data.get("description") or "",
            severity=defect_data.get("severity") or "major",
            priority=defect_data.get("priority") or "P2",
            status="open",
            root_cause=defect_data.get("root_cause") or "待分析",
            root_cause_category=defect_data.get("root_cause_category") or "other",
            reproduce_steps=defect_data.get("reproduce_steps") or "",
            expected_result=defect_data.get("expected_result") or "",
            actual_result=defect_data.get("actual_result") or "",
            version_id=version_id,
            created_by=created_by,
        )
        db.add(defect)
        db.commit()
        db.refresh(defect)
        logger.info(f"AI 缺陷创建成功: id={defect.id}, title={defect.title}")
        return defect

    # ==================== 报告创建/更新 ====================

    @staticmethod
    def update_report(
        db: Session,
        report: TestReport,
        content: str,
        summary: str = "",
        stats: Optional[Dict[str, Any]] = None,
    ) -> TestReport:
        """更新测试报告内容"""
        report.content = content
        report.summary = summary or content[:200] if content else ""
        if stats:
            report.total_cases = stats.get("total_cases", 0)
            report.passed_cases = stats.get("passed_cases", 0)
            report.failed_cases = stats.get("failed_cases", 0)
            report.pass_rate = stats.get("pass_rate", 0.0)
            report.total_defects = stats.get("total_defects", 0)
            report.open_defects = stats.get("open_defects", 0)
            report.total_runs = stats.get("total_runs", 0)
            report.avg_duration = stats.get("avg_duration", 0.0)
        report.status = "completed"
        report.completed_at = china_now_naive()
        report.updated_at = china_now_naive()
        db.commit()
        db.refresh(report)
        logger.info(f"AI 报告更新成功: id={report.id}")
        return report
