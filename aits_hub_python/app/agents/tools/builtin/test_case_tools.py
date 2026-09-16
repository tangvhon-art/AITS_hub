"""测试用例相关工具"""
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from app.agents.tools.base import BaseTool, ToolParameter


class QueryProjectStatsTool(BaseTool):
    name = "query_project_stats"
    description = "查询项目的统计数据，包括用例数量、缺陷数量、执行记录、测试计划等概览信息"
    category = "test_case"
    parameters = ToolParameter(properties={}, required=[])

    async def execute(self, args: Dict[str, Any], db: Session, project_id: Optional[int] = None, user_id: Optional[int] = None) -> Any:
        from app.models.test_case import TestCase
        from app.models.defect import Defect
        from app.models.test_run import TestRun
        from app.models.test_plan import TestPlan

        if not project_id:
            return {"error": "未指定项目"}

        total_cases = db.query(TestCase).filter(TestCase.project_id == project_id, TestCase.is_deleted == False).count()
        passed_cases = db.query(TestCase).filter(TestCase.project_id == project_id, TestCase.status == "passed", TestCase.is_deleted == False).count()
        failed_cases = db.query(TestCase).filter(TestCase.project_id == project_id, TestCase.status == "failed", TestCase.is_deleted == False).count()
        total_defects = db.query(Defect).filter(Defect.project_id == project_id, Defect.is_deleted == False).count()
        open_defects = db.query(Defect).filter(Defect.project_id == project_id, Defect.status == "open", Defect.is_deleted == False).count()
        total_runs = db.query(TestRun).filter(TestRun.project_id == project_id, TestRun.is_deleted == False).count()
        total_plans = db.query(TestPlan).filter(TestPlan.project_id == project_id, TestPlan.is_deleted == False).count()
        pass_rate = round(passed_cases / total_cases * 100, 2) if total_cases > 0 else 0

        return {
            "total_cases": total_cases, "passed_cases": passed_cases, "failed_cases": failed_cases,
            "pass_rate": f"{pass_rate}%", "total_defects": total_defects, "open_defects": open_defects,
            "total_runs": total_runs, "total_plans": total_plans,
        }


class ListCasesTool(BaseTool):
    name = "list_cases"
    description = "查询测试用例列表，支持按状态、优先级筛选，返回最近的用例"
    category = "test_case"
    parameters = ToolParameter(properties={
        "status": {"type": "string", "description": "用例状态: pending/passed/failed/blocked"},
        "priority": {"type": "string", "description": "优先级: P0/P1/P2/P3"},
        "limit": {"type": "integer", "description": "返回数量，默认10，最大50"},
    }, required=[])

    async def execute(self, args: Dict[str, Any], db: Session, project_id: Optional[int] = None, user_id: Optional[int] = None) -> Any:
        from app.models.test_case import TestCase
        if not project_id:
            return {"error": "未指定项目"}
        limit = min(args.get("limit", 10), 50)
        query = db.query(TestCase).filter(TestCase.project_id == project_id, TestCase.is_deleted == False)
        if args.get("status"):
            query = query.filter(TestCase.status == args["status"])
        if args.get("priority"):
            query = query.filter(TestCase.priority == args["priority"])
        total = query.count()
        cases = query.order_by(TestCase.created_at.desc()).limit(limit).all()
        return {"total": total, "cases": [{"id": c.id, "title": c.title, "priority": c.priority, "status": c.status, "module": c.module} for c in cases]}
