"""项目级工具：测试计划、脚本、版本、需求、报告、质量指标"""
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from app.agents.tools.base import BaseTool, ToolParameter


class ListProjectsTool(BaseTool):
    name = "list_projects"
    description = "列出系统中所有项目，返回项目ID、名称、描述和创建时间。当用户询问'有多少个项目'、'项目列表'、'所有项目'等问题时必须调用此工具"
    category = "project"
    parameters = ToolParameter(properties={
        "limit": {"type": "integer", "description": "返回数量，默认20，最大100"}
    }, required=[])

    async def execute(self, args, db, project_id=None, user_id=None):
        from app.models.project import Project
        limit = min(args.get("limit", 20), 100)
        query = db.query(Project).filter(Project.is_deleted == False)
        projects = query.order_by(Project.created_at.desc()).limit(limit).all()
        return {
            "total": query.count(),
            "projects": [{"id": p.id, "name": p.name, "description": p.description or "", "created_at": str(p.created_at) if p.created_at else None} for p in projects]
        }


class ListTestPlansTool(BaseTool):
    name = "list_test_plans"
    description = "查询测试计划列表，返回计划名称、状态和通过率"
    category = "project"
    parameters = ToolParameter(properties={"limit": {"type": "integer", "description": "返回数量，默认10，最大50"}}, required=[])

    async def execute(self, args, db, project_id=None, user_id=None):
        from app.models.test_plan import TestPlan
        if not project_id:
            return {"error": "未指定项目"}
        limit = min(args.get("limit", 10), 50)
        query = db.query(TestPlan).filter(TestPlan.project_id == project_id, TestPlan.is_deleted == False)
        plans = query.order_by(TestPlan.created_at.desc()).limit(limit).all()
        return {"total": query.count(), "plans": [{"id": p.id, "name": p.name, "status": p.status, "pass_rate": p.pass_rate} for p in plans]}


class ListScriptsTool(BaseTool):
    name = "list_scripts"
    description = "查询UI自动化脚本列表，返回脚本名称、类型和状态"
    category = "project"
    parameters = ToolParameter(properties={"limit": {"type": "integer", "description": "返回数量，默认10，最大50"}}, required=[])

    async def execute(self, args, db, project_id=None, user_id=None):
        from app.models.automation_script import AutomationScript
        if not project_id:
            return {"error": "未指定项目"}
        limit = min(args.get("limit", 10), 50)
        query = db.query(AutomationScript).filter(AutomationScript.project_id == project_id, AutomationScript.is_deleted == False)
        scripts = query.order_by(AutomationScript.created_at.desc()).limit(limit).all()
        return {"total": query.count(), "scripts": [{"id": s.id, "name": s.name, "script_type": s.script_type, "status": s.status} for s in scripts]}


class ListVersionsTool(BaseTool):
    name = "list_versions"
    description = "查询项目版本列表，返回版本名称、状态和发布日期"
    category = "project"
    parameters = ToolParameter(properties={}, required=[])

    async def execute(self, args, db, project_id=None, user_id=None):
        from app.models.project import ProjectVersion
        if not project_id:
            return {"error": "未指定项目"}
        versions = db.query(ProjectVersion).filter(ProjectVersion.project_id == project_id, ProjectVersion.is_deleted == False).order_by(ProjectVersion.release_date.desc()).all()
        return {"total": len(versions), "versions": [{"id": v.id, "name": v.name, "status": v.status, "release_date": str(v.release_date) if v.release_date else None} for v in versions]}


class ListRequirementsTool(BaseTool):
    name = "list_requirements"
    description = "查询需求列表，返回需求标题、状态和来源"
    category = "project"
    parameters = ToolParameter(properties={"limit": {"type": "integer", "description": "返回数量，默认10，最大50"}}, required=[])

    async def execute(self, args, db, project_id=None, user_id=None):
        from app.models.requirement import TestRequirement
        if not project_id:
            return {"error": "未指定项目"}
        limit = min(args.get("limit", 10), 50)
        query = db.query(TestRequirement).filter(TestRequirement.project_id == project_id, TestRequirement.is_deleted == False)
        reqs = query.order_by(TestRequirement.created_at.desc()).limit(limit).all()
        return {"total": query.count(), "requirements": [{"id": r.id, "title": r.title, "status": r.status, "source": r.source} for r in reqs]}


class ListReportsTool(BaseTool):
    name = "list_reports"
    description = "查询测试报告列表，返回报告标题、类型、状态和通过率"
    category = "project"
    parameters = ToolParameter(properties={"limit": {"type": "integer", "description": "返回数量，默认10，最大50"}}, required=[])

    async def execute(self, args, db, project_id=None, user_id=None):
        from app.models.report import TestReport
        if not project_id:
            return {"error": "未指定项目"}
        limit = min(args.get("limit", 10), 50)
        query = db.query(TestReport).filter(TestReport.project_id == project_id, TestReport.is_deleted == False)
        reports = query.order_by(TestReport.created_at.desc()).limit(limit).all()
        return {"total": query.count(), "reports": [{"id": r.id, "title": r.title, "report_type": r.report_type, "status": r.status, "pass_rate": r.pass_rate} for r in reports]}


class QueryQualityMetricsTool(BaseTool):
    name = "query_quality_metrics"
    description = "查询项目质量指标，合并UI和接口测试执行数据，返回通过率、执行次数和未解决缺陷数"
    category = "project"
    parameters = ToolParameter(properties={}, required=[])

    async def execute(self, args, db, project_id=None, user_id=None):
        from app.models.test_case import TestCase
        from app.models.test_run import TestRun
        from app.models.defect import Defect
        from app.models.api_test import ApiExecution
        if not project_id:
            return {"error": "未指定项目"}
        ui_runs = db.query(TestRun).filter(TestRun.project_id == project_id, TestRun.is_deleted == False).all()
        api_execs = db.query(ApiExecution).filter(ApiExecution.project_id == project_id, ApiExecution.is_deleted == False).all()
        total_ui = len(ui_runs)
        passed_ui = sum(1 for r in ui_runs if r.status == "passed")
        total_api = len(api_execs)
        passed_api = sum(1 for e in api_execs if e.status == "passed")
        total_runs = total_ui + total_api
        total_passed = passed_ui + passed_api
        pass_rate = round(total_passed / total_runs * 100, 2) if total_runs > 0 else 0
        open_defects = db.query(Defect).filter(Defect.project_id == project_id, Defect.status.in_(["open", "confirmed", "reopened"]), Defect.is_deleted == False).count()
        return {"total_runs": total_runs, "passed_runs": total_passed, "pass_rate": f"{pass_rate}%", "ui_test_runs": total_ui, "api_test_runs": total_api, "open_defects": open_defects}
