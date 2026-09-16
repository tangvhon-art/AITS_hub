"""接口测试相关工具"""
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from app.agents.tools.base import BaseTool, ToolParameter


class ListApiCasesTool(BaseTool):
    name = "list_api_cases"
    description = "查询接口测试用例列表，返回用例名称、请求方法、路径和优先级"
    category = "api_test"
    parameters = ToolParameter(properties={"limit": {"type": "integer", "description": "返回数量，默认10，最大50"}}, required=[])

    async def execute(self, args, db, project_id=None, user_id=None):
        from app.models.api_test import ApiTestCase
        if not project_id:
            return {"error": "未指定项目"}
        limit = min(args.get("limit", 10), 50)
        query = db.query(ApiTestCase).filter(ApiTestCase.project_id == project_id, ApiTestCase.is_deleted == False)
        cases = query.order_by(ApiTestCase.created_at.desc()).limit(limit).all()
        return {"total": query.count(), "cases": [{"id": c.id, "name": c.name, "method": c.method, "path": c.path, "priority": c.priority} for c in cases]}


class ListApiDefinitionsTool(BaseTool):
    name = "list_api_definitions"
    description = "查询API接口定义列表，支持按请求方法筛选，返回接口名称、方法、路径和模块"
    category = "api_test"
    parameters = ToolParameter(properties={
        "method": {"type": "string", "description": "请求方法筛选: GET/POST/PUT/DELETE/PATCH"},
        "limit": {"type": "integer", "description": "返回数量，默认10，最大50"},
    }, required=[])

    async def execute(self, args, db, project_id=None, user_id=None):
        from app.models.api_test import ApiDefinition
        if not project_id:
            return {"error": "未指定项目"}
        limit = min(args.get("limit", 10), 50)
        query = db.query(ApiDefinition).filter(ApiDefinition.project_id == project_id, ApiDefinition.is_deleted == False)
        if args.get("method"):
            query = query.filter(ApiDefinition.method == args["method"].upper())
        defs = query.order_by(ApiDefinition.path).limit(limit).all()
        return {"total": query.count(), "definitions": [{"id": d.id, "name": d.name, "method": d.method, "path": d.path, "module_id": d.module_id} for d in defs]}


class ListApiScenariosTool(BaseTool):
    name = "list_api_scenarios"
    description = "查询接口测试场景列表，返回场景名称、描述和状态"
    category = "api_test"
    parameters = ToolParameter(properties={"limit": {"type": "integer", "description": "返回数量，默认10，最大50"}}, required=[])

    async def execute(self, args, db, project_id=None, user_id=None):
        from app.models.api_test import ApiScenario
        if not project_id:
            return {"error": "未指定项目"}
        limit = min(args.get("limit", 10), 50)
        query = db.query(ApiScenario).filter(ApiScenario.project_id == project_id, ApiScenario.is_deleted == False)
        scenarios = query.order_by(ApiScenario.created_at.desc()).limit(limit).all()
        return {"total": query.count(), "scenarios": [{"id": s.id, "name": s.name, "description": s.description, "status": s.status} for s in scenarios]}


class ListApiExecutionsTool(BaseTool):
    name = "list_api_executions"
    description = "查询接口测试执行记录，支持按状态筛选，返回执行状态、通过率和耗时"
    category = "api_test"
    parameters = ToolParameter(properties={
        "status": {"type": "string", "description": "执行状态筛选: passed/failed/error/running"},
        "limit": {"type": "integer", "description": "返回数量，默认10，最大50"},
    }, required=[])

    async def execute(self, args, db, project_id=None, user_id=None):
        from app.models.api_test import ApiExecution
        if not project_id:
            return {"error": "未指定项目"}
        limit = min(args.get("limit", 10), 50)
        query = db.query(ApiExecution).filter(ApiExecution.project_id == project_id, ApiExecution.is_deleted == False)
        if args.get("status"):
            query = query.filter(ApiExecution.status == args["status"])
        execs = query.order_by(ApiExecution.created_at.desc()).limit(limit).all()
        return {"total": query.count(), "executions": [{"id": e.id, "status": e.status, "pass_rate": e.pass_rate, "total_duration": e.total_duration, "created_at": str(e.created_at) if e.created_at else None} for e in execs]}
