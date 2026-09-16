"""缺陷相关工具"""
import logging
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from app.agents.tools.base import BaseTool, ToolParameter

logger = logging.getLogger(__name__)


class ListDefectsTool(BaseTool):
    name = "list_defects"
    description = "查询缺陷列表，支持按状态、严重程度筛选"
    category = "defect"
    parameters = ToolParameter(properties={
        "status": {"type": "string", "description": "缺陷状态: open/confirmed/resolved/closed/reopened"},
        "severity": {"type": "string", "description": "严重程度: blocker/critical/major/minor/trivial"},
        "limit": {"type": "integer", "description": "返回数量，默认10，最大50"},
    }, required=[])

    async def execute(self, args, db, project_id=None, user_id=None):
        from app.models.defect import Defect
        if not project_id:
            return {"error": "未指定项目"}
        limit = min(args.get("limit", 10), 50)
        query = db.query(Defect).filter(Defect.project_id == project_id, Defect.is_deleted == False)
        if args.get("status"):
            query = query.filter(Defect.status == args["status"])
        if args.get("severity"):
            query = query.filter(Defect.severity == args["severity"])
        total = query.count()
        defects = query.order_by(Defect.created_at.desc()).limit(limit).all()
        return {"total": total, "defects": [{"id": d.id, "title": d.title, "severity": d.severity, "priority": d.priority, "status": d.status} for d in defects]}


class AnalyzeDefectsTool(BaseTool):
    name = "analyze_defects"
    description = "分析项目缺陷情况，按严重程度、状态、根因分类统计"
    category = "defect"
    parameters = ToolParameter(properties={}, required=[])

    async def execute(self, args, db, project_id=None, user_id=None):
        from app.models.defect import Defect
        if not project_id:
            return {"error": "未指定项目"}
        defects = db.query(Defect).filter(Defect.project_id == project_id, Defect.is_deleted == False).all()
        severity_stats = {}
        status_stats = {}
        root_cause_stats = {}
        for d in defects:
            severity_stats[d.severity] = severity_stats.get(d.severity, 0) + 1
            status_stats[d.status] = status_stats.get(d.status, 0) + 1
            if d.root_cause_category:
                root_cause_stats[d.root_cause_category] = root_cause_stats.get(d.root_cause_category, 0) + 1
        return {
            "total": len(defects), "by_severity": severity_stats, "by_status": status_stats,
            "by_root_cause": root_cause_stats, "open_count": status_stats.get("open", 0),
            "resolved_count": status_stats.get("resolved", 0),
        }


class CreateDefectTool(BaseTool):
    name = "create_defect"
    description = "创建一个新的缺陷记录"
    category = "defect"
    parameters = ToolParameter(properties={
        "title": {"type": "string", "description": "缺陷标题"},
        "description": {"type": "string", "description": "缺陷描述"},
        "severity": {"type": "string", "description": "严重程度: blocker/critical/major/minor/trivial"},
        "priority": {"type": "string", "description": "优先级: P0/P1/P2/P3"},
        "reproduce_steps": {"type": "string", "description": "复现步骤"},
        "expected_result": {"type": "string", "description": "预期结果"},
        "actual_result": {"type": "string", "description": "实际结果"},
    }, required=["title"])

    async def execute(self, args, db, project_id=None, user_id=None):
        from app.models.defect import Defect
        if not project_id:
            return {"error": "未指定项目"}
        title = args.get("title", "").strip()
        if not title:
            return {"error": "缺陷标题不能为空"}
        severity_map = {"high": "critical", "medium": "major", "low": "minor", "critical": "critical", "major": "major", "minor": "minor"}
        severity = severity_map.get(args.get("severity", "major").lower(), "major")
        priority_map = {"high": "P0", "medium": "P2", "low": "P3", "p0": "P0", "p1": "P1", "p2": "P2", "p3": "P3"}
        priority = priority_map.get(args.get("priority", "P2").lower(), "P2")
        defect = Defect(
            project_id=project_id, title=title, description=args.get("description", ""),
            severity=severity, priority=priority, status="open",
            reproduce_steps=args.get("reproduce_steps", ""),
            expected_result=args.get("expected_result", ""),
            actual_result=args.get("actual_result", ""),
            created_by=user_id,
        )
        db.add(defect)
        db.commit()
        db.refresh(defect)
        logger.info(f"创建缺陷成功: id={defect.id}")
        return {"id": defect.id, "title": defect.title, "severity": defect.severity, "priority": defect.priority, "status": defect.status, "message": "缺陷创建成功"}
