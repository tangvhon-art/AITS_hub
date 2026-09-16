"""
MCP 工具注册系统

将各模块能力封装为可被大模型调用的工具（Function Calling）
"""
import json
import logging
from typing import Dict, Any, Callable, Optional, List
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class MCPTool:
    """MCP 工具定义"""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        execute: Callable,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.execute = execute

    def to_function_schema(self) -> Dict[str, Any]:
        """转换为 OpenAI Function Calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class MCPToolRegistry:
    """MCP 工具注册表"""

    def __init__(self):
        self._tools: Dict[str, MCPTool] = {}

    def register(self, tool: MCPTool):
        """注册工具"""
        self._tools[tool.name] = tool
        logger.info(f"注册 MCP 工具: {tool.name}")

    def get(self, name: str) -> Optional[MCPTool]:
        """获取工具"""
        return self._tools.get(name)

    def list_tools(self) -> List[MCPTool]:
        """列出所有工具"""
        return list(self._tools.values())

    def get_function_schemas(self) -> List[Dict[str, Any]]:
        """获取所有工具的 Function Calling schema"""
        return [tool.to_function_schema() for tool in self._tools.values()]

    async def execute_tool(
        self,
        name: str,
        args: Dict[str, Any],
        db: Session,
        project_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        执行工具

        Returns:
            {"success": True/False, "result": ... or "error": ...}
        """
        tool = self._tools.get(name)
        if not tool:
            return {"success": False, "error": f"工具不存在: {name}"}

        try:
            # 注入 user_id 到 args 中
            if user_id and "user_id" not in args:
                args = {**args, "user_id": user_id}

            result = await tool.execute(args, db, project_id)

            # 检查工具返回是否包含 error
            if isinstance(result, dict) and result.get("error"):
                return {"success": False, "error": result["error"]}

            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"工具执行失败: {name}, error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}


# 全局工具注册表
mcp_registry = MCPToolRegistry()


# ==================== 工具实现 ====================

async def tool_query_project_stats(args: Dict[str, Any], db: Session, project_id: Optional[int]) -> Dict[str, Any]:
    """查询项目统计数据"""
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
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": failed_cases,
        "pass_rate": f"{pass_rate}%",
        "total_defects": total_defects,
        "open_defects": open_defects,
        "total_runs": total_runs,
        "total_plans": total_plans,
    }


async def tool_list_cases(args: Dict[str, Any], db: Session, project_id: Optional[int]) -> Dict[str, Any]:
    """查询用例列表"""
    from app.models.test_case import TestCase

    if not project_id:
        return {"error": "未指定项目"}

    limit = min(args.get("limit", 10), 50)
    status = args.get("status")
    priority = args.get("priority")

    query = db.query(TestCase).filter(TestCase.project_id == project_id, TestCase.is_deleted == False)
    if status:
        query = query.filter(TestCase.status == status)
    if priority:
        query = query.filter(TestCase.priority == priority)

    total = query.count()
    cases = query.order_by(TestCase.created_at.desc()).limit(limit).all()

    return {
        "total": total,
        "cases": [
            {
                "id": c.id,
                "title": c.title,
                "priority": c.priority,
                "status": c.status,
                "module": c.module,
            }
            for c in cases
        ],
    }


async def tool_list_defects(args: Dict[str, Any], db: Session, project_id: Optional[int]) -> Dict[str, Any]:
    """查询缺陷列表"""
    from app.models.defect import Defect

    if not project_id:
        return {"error": "未指定项目"}

    limit = min(args.get("limit", 10), 50)
    status = args.get("status")
    severity = args.get("severity")

    query = db.query(Defect).filter(Defect.project_id == project_id, Defect.is_deleted == False)
    if status:
        query = query.filter(Defect.status == status)
    if severity:
        query = query.filter(Defect.severity == severity)

    total = query.count()
    defects = query.order_by(Defect.created_at.desc()).limit(limit).all()

    return {
        "total": total,
        "defects": [
            {
                "id": d.id,
                "title": d.title,
                "severity": d.severity,
                "priority": d.priority,
                "status": d.status,
            }
            for d in defects
        ],
    }


async def tool_analyze_defects(args: Dict[str, Any], db: Session, project_id: Optional[int]) -> Dict[str, Any]:
    """缺陷分析统计"""
    from app.models.defect import Defect

    if not project_id:
        return {"error": "未指定项目"}

    defects = db.query(Defect).filter(Defect.project_id == project_id, Defect.is_deleted == False).all()

    # 按严重程度统计
    severity_stats = {}
    for d in defects:
        severity_stats[d.severity] = severity_stats.get(d.severity, 0) + 1

    # 按状态统计
    status_stats = {}
    for d in defects:
        status_stats[d.status] = status_stats.get(d.status, 0) + 1

    # 按根因分类统计
    root_cause_stats = {}
    for d in defects:
        if d.root_cause_category:
            root_cause_stats[d.root_cause_category] = root_cause_stats.get(d.root_cause_category, 0) + 1

    return {
        "total": len(defects),
        "by_severity": severity_stats,
        "by_status": status_stats,
        "by_root_cause": root_cause_stats,
        "open_count": status_stats.get("open", 0),
        "resolved_count": status_stats.get("resolved", 0),
    }


async def tool_search_knowledge(args: Dict[str, Any], db: Session, project_id: Optional[int]) -> Dict[str, Any]:
    """知识库检索"""
    from app.services.knowledge_base import knowledge_base_service

    if not project_id:
        return {"error": "未指定项目"}

    query = args.get("query", "")
    top_k = min(args.get("top_k", 5), 10)

    if not query:
        return {"error": "查询内容不能为空"}

    try:
        results = knowledge_base_service.search(db=db, project_id=project_id, query=query, top_k=top_k)
    except Exception as e:
        return {"error": f"知识库检索失败: {str(e)}"}

    return {
        "query": query,
        "total": len(results) if isinstance(results, list) else 0,
        "results": [
            {
                "title": r.get("title", ""),
                "content": r.get("content", r.get("text", ""))[:300],
                "score": r.get("score", r.get("similarity")),
            }
            for r in (results if isinstance(results, list) else [])
        ],
    }


async def tool_create_defect(args: Dict[str, Any], db: Session, project_id: Optional[int]) -> Dict[str, Any]:
    """创建缺陷"""
    from app.models.defect import Defect

    if not project_id:
        return {"error": "未指定项目"}

    title = args.get("title", "").strip()
    if not title:
        return {"error": "缺陷标题不能为空"}

    # 校验 severity
    valid_severity = ["blocker", "critical", "major", "minor", "trivial"]
    severity = args.get("severity", "major")
    if severity not in valid_severity:
        # 尝试映射常见错误值
        severity_map = {
            "high": "critical",
            "medium": "major",
            "low": "minor",
            "critical": "critical",
            "major": "major",
            "minor": "minor",
        }
        severity = severity_map.get(severity.lower(), "major")

    # 校验 priority
    valid_priority = ["P0", "P1", "P2", "P3"]
    priority = args.get("priority", "P2")
    if priority not in valid_priority:
        priority_map = {
            "high": "P0",
            "medium": "P2",
            "low": "P3",
            "p0": "P0",
            "p1": "P1",
            "p2": "P2",
            "p3": "P3",
        }
        priority = priority_map.get(priority.lower(), "P2")

    defect = Defect(
        project_id=project_id,
        title=title,
        description=args.get("description", ""),
        severity=severity,
        priority=priority,
        status="open",
        reproduce_steps=args.get("reproduce_steps", ""),
        expected_result=args.get("expected_result", ""),
        actual_result=args.get("actual_result", ""),
        created_by=args.get("user_id"),
    )
    db.add(defect)
    db.commit()
    db.refresh(defect)

    logger.info(f"MCP 创建缺陷成功: id={defect.id}, title={defect.title}")

    return {
        "id": defect.id,
        "title": defect.title,
        "severity": defect.severity,
        "priority": defect.priority,
        "status": defect.status,
        "message": "缺陷创建成功",
    }


# ==================== 注册工具 ====================

# P2-10: 补齐接口测试/计划/脚本/版本/需求/报告工具

async def tool_list_api_cases(args, db, project_id):
    """查询接口测试用例列表"""
    from app.models.api_test import ApiTestCase
    if not project_id:
        return {"error": "未指定项目"}
    limit = min(args.get("limit", 10), 50)
    query = db.query(ApiTestCase).filter(ApiTestCase.project_id == project_id, ApiTestCase.is_deleted == False)
    cases = query.order_by(ApiTestCase.created_at.desc()).limit(limit).all()
    return {"total": query.count(), "cases": [{"id": c.id, "name": c.name, "method": c.method, "path": c.path, "priority": c.priority} for c in cases]}

async def tool_list_test_plans(args, db, project_id):
    """查询测试计划列表"""
    from app.models.test_plan import TestPlan
    if not project_id:
        return {"error": "未指定项目"}
    limit = min(args.get("limit", 10), 50)
    query = db.query(TestPlan).filter(TestPlan.project_id == project_id, TestPlan.is_deleted == False)
    plans = query.order_by(TestPlan.created_at.desc()).limit(limit).all()
    return {"total": query.count(), "plans": [{"id": p.id, "name": p.name, "status": p.status, "pass_rate": p.pass_rate} for p in plans]}

async def tool_list_scripts(args, db, project_id):
    """查询自动化脚本列表"""
    from app.models.automation_script import AutomationScript
    if not project_id:
        return {"error": "未指定项目"}
    limit = min(args.get("limit", 10), 50)
    query = db.query(AutomationScript).filter(AutomationScript.project_id == project_id, AutomationScript.is_deleted == False)
    scripts = query.order_by(AutomationScript.created_at.desc()).limit(limit).all()
    return {"total": query.count(), "scripts": [{"id": s.id, "name": s.name, "script_type": s.script_type, "status": s.status} for s in scripts]}

async def tool_list_versions(args, db, project_id):
    """查询项目版本列表"""
    from app.models.project import ProjectVersion
    if not project_id:
        return {"error": "未指定项目"}
    versions = db.query(ProjectVersion).filter(ProjectVersion.project_id == project_id, ProjectVersion.is_deleted == False).order_by(ProjectVersion.release_date.desc()).all()
    return {"total": len(versions), "versions": [{"id": v.id, "name": v.name, "status": v.status, "release_date": str(v.release_date) if v.release_date else None} for v in versions]}

async def tool_list_requirements(args, db, project_id):
    """查询需求列表"""
    from app.models.requirement import TestRequirement
    if not project_id:
        return {"error": "未指定项目"}
    limit = min(args.get("limit", 10), 50)
    query = db.query(TestRequirement).filter(TestRequirement.project_id == project_id, TestRequirement.is_deleted == False)
    reqs = query.order_by(TestRequirement.created_at.desc()).limit(limit).all()
    return {"total": query.count(), "requirements": [{"id": r.id, "title": r.title, "status": r.status, "source": r.source} for r in reqs]}

async def tool_list_reports(args, db, project_id):
    """查询测试报告列表"""
    from app.models.report import TestReport
    if not project_id:
        return {"error": "未指定项目"}
    limit = min(args.get("limit", 10), 50)
    query = db.query(TestReport).filter(TestReport.project_id == project_id, TestReport.is_deleted == False)
    reports = query.order_by(TestReport.created_at.desc()).limit(limit).all()
    return {"total": query.count(), "reports": [{"id": r.id, "title": r.title, "report_type": r.report_type, "status": r.status, "pass_rate": r.pass_rate} for r in reports]}


async def tool_list_api_definitions(args, db, project_id):
    """查询 API 接口定义列表"""
    from app.models.api_test import ApiDefinition
    if not project_id:
        return {"error": "未指定项目"}
    limit = min(args.get("limit", 10), 50)
    query = db.query(ApiDefinition).filter(ApiDefinition.project_id == project_id, ApiDefinition.is_deleted == False)
    method = args.get("method")
    if method:
        query = query.filter(ApiDefinition.method == method.upper())
    defs = query.order_by(ApiDefinition.path).limit(limit).all()
    return {"total": query.count(), "definitions": [{"id": d.id, "name": d.name, "method": d.method, "path": d.path, "module_id": d.module_id} for d in defs]}


async def tool_list_api_scenarios(args, db, project_id):
    """查询接口测试场景列表"""
    from app.models.api_test import ApiScenario
    if not project_id:
        return {"error": "未指定项目"}
    limit = min(args.get("limit", 10), 50)
    query = db.query(ApiScenario).filter(ApiScenario.project_id == project_id, ApiScenario.is_deleted == False)
    scenarios = query.order_by(ApiScenario.created_at.desc()).limit(limit).all()
    return {"total": query.count(), "scenarios": [{"id": s.id, "name": s.name, "description": s.description, "status": s.status} for s in scenarios]}


async def tool_list_api_executions(args, db, project_id):
    """查询接口测试执行记录"""
    from app.models.api_test import ApiExecution
    if not project_id:
        return {"error": "未指定项目"}
    limit = min(args.get("limit", 10), 50)
    status = args.get("status")
    query = db.query(ApiExecution).filter(ApiExecution.project_id == project_id, ApiExecution.is_deleted == False)
    if status:
        query = query.filter(ApiExecution.status == status)
    execs = query.order_by(ApiExecution.created_at.desc()).limit(limit).all()
    return {"total": query.count(), "executions": [{"id": e.id, "status": e.status, "pass_rate": e.pass_rate, "total_duration": e.total_duration, "created_at": str(e.created_at) if e.created_at else None} for e in execs]}


async def tool_query_quality_metrics(args, db, project_id):
    """查询项目质量指标"""
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

    open_defects = db.query(Defect).filter(
        Defect.project_id == project_id,
        Defect.status.in_(["open", "confirmed", "reopened"]),
        Defect.is_deleted == False,
    ).count()

    return {
        "total_runs": total_runs,
        "passed_runs": total_passed,
        "pass_rate": f"{pass_rate}%",
        "ui_test_runs": total_ui,
        "api_test_runs": total_api,
        "open_defects": open_defects,
    }

mcp_registry.register(MCPTool(
    name="query_project_stats",
    description="查询项目的统计数据，包括用例数量、缺陷数量、执行记录、测试计划等概览信息",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
    execute=tool_query_project_stats,
))

mcp_registry.register(MCPTool(
    name="list_cases",
    description="查询测试用例列表，支持按状态、优先级筛选，返回最近的用例",
    parameters={
        "type": "object",
        "properties": {
            "status": {"type": "string", "description": "用例状态: pending/passed/failed/blocked"},
            "priority": {"type": "string", "description": "优先级: P0/P1/P2/P3"},
            "limit": {"type": "integer", "description": "返回数量，默认10，最大50"},
        },
        "required": [],
    },
    execute=tool_list_cases,
))

mcp_registry.register(MCPTool(
    name="list_defects",
    description="查询缺陷列表，支持按状态、严重程度筛选",
    parameters={
        "type": "object",
        "properties": {
            "status": {"type": "string", "description": "缺陷状态: open/confirmed/resolved/closed/reopened"},
            "severity": {"type": "string", "description": "严重程度: blocker/critical/major/minor/trivial"},
            "limit": {"type": "integer", "description": "返回数量，默认10，最大50"},
        },
        "required": [],
    },
    execute=tool_list_defects,
))

mcp_registry.register(MCPTool(
    name="analyze_defects",
    description="分析项目缺陷情况，按严重程度、状态、根因分类统计",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
    execute=tool_analyze_defects,
))

mcp_registry.register(MCPTool(
    name="search_knowledge",
    description="在项目知识库中检索相关文档和内容",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "检索查询内容"},
            "top_k": {"type": "integer", "description": "返回结果数量，默认5，最大10"},
        },
        "required": ["query"],
    },
    execute=tool_search_knowledge,
))

mcp_registry.register(MCPTool(
    name="create_defect",
    description="创建一个新的缺陷记录",
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "缺陷标题"},
            "description": {"type": "string", "description": "缺陷描述"},
            "severity": {"type": "string", "description": "严重程度: blocker/critical/major/minor/trivial"},
            "priority": {"type": "string", "description": "优先级: P0/P1/P2/P3"},
            "reproduce_steps": {"type": "string", "description": "复现步骤"},
            "expected_result": {"type": "string", "description": "预期结果"},
            "actual_result": {"type": "string", "description": "实际结果"},
        },
        "required": ["title"],
    },
    execute=tool_create_defect,
))

# P2-10: 扩展工具注册
for _tool_def in [
    ("list_api_cases", "查询接口测试用例列表，返回用例名称、请求方法、路径和优先级", tool_list_api_cases,
     {"limit": {"type": "integer", "description": "返回数量，默认10，最大50"}}),
    ("list_test_plans", "查询测试计划列表，返回计划名称、状态和通过率", tool_list_test_plans,
     {"limit": {"type": "integer", "description": "返回数量，默认10，最大50"}}),
    ("list_scripts", "查询UI自动化脚本列表，返回脚本名称、类型和状态", tool_list_scripts,
     {"limit": {"type": "integer", "description": "返回数量，默认10，最大50"}}),
    ("list_versions", "查询项目版本列表，返回版本名称、状态和发布日期", tool_list_versions, {}),
    ("list_requirements", "查询需求列表，返回需求标题、状态和来源", tool_list_requirements,
     {"limit": {"type": "integer", "description": "返回数量，默认10，最大50"}}),
    ("list_reports", "查询测试报告列表，返回报告标题、类型、状态和通过率", tool_list_reports,
     {"limit": {"type": "integer", "description": "返回数量，默认10，最大50"}}),
    ("list_api_definitions", "查询API接口定义列表，支持按请求方法筛选，返回接口名称、方法、路径和模块", tool_list_api_definitions,
     {"method": {"type": "string", "description": "请求方法筛选: GET/POST/PUT/DELETE/PATCH"},
      "limit": {"type": "integer", "description": "返回数量，默认10，最大50"}}),
    ("list_api_scenarios", "查询接口测试场景列表，返回场景名称、描述和状态", tool_list_api_scenarios,
     {"limit": {"type": "integer", "description": "返回数量，默认10，最大50"}}),
    ("list_api_executions", "查询接口测试执行记录，支持按状态筛选，返回执行状态、通过率和耗时", tool_list_api_executions,
     {"status": {"type": "string", "description": "执行状态筛选: passed/failed/error/running"},
      "limit": {"type": "integer", "description": "返回数量，默认10，最大50"}}),
    ("query_quality_metrics", "查询项目质量指标，合并UI和接口测试执行数据，返回通过率、执行次数和未解决缺陷数", tool_query_quality_metrics, {}),
]:
    _name, _desc, _fn, _props = _tool_def
    mcp_registry.register(MCPTool(
        name=_name, description=_desc,
        parameters={"type": "object", "properties": _props, "required": []},
        execute=_fn,
    ))
