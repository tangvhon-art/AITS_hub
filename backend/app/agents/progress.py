"""进度事件推送辅助函数"""
from typing import Any, Dict, Optional


def progress(node: str, label: str, status: str = "running", detail: Optional[str] = None) -> Dict[str, Any]:
    """构建进度事件"""
    event = {"type": "progress", "node": node, "label": label, "status": status}
    if detail:
        event["detail"] = detail
    return event


# 标准进度节点常量
class ProgressNode:
    INTENT_RECOGNITION = "intent_recognition"
    KNOWLEDGE_SEARCH = "knowledge_search"
    SKILL_MATCHED = "skill_matched"
    THINKING = "thinking"
    TOOL_CALLING = "tool_calling"
    TOOL_DONE = "tool_done"
    GENERATING = "generating"
    ORGANIZING = "organizing"
    DONE = "done"


# 工具中文名映射（用于进度展示）
TOOL_LABELS = {
    "query_project_stats": "项目统计",
    "list_projects": "查询项目列表",
    "list_cases": "查询用例",
    "list_defects": "查询缺陷",
    "analyze_defects": "缺陷分析",
    "search_knowledge": "知识库检索",
    "create_defect": "创建缺陷",
    "list_api_cases": "查询接口用例",
    "list_test_plans": "查询测试计划",
    "list_scripts": "查询脚本",
    "list_versions": "查询版本",
    "list_requirements": "查询需求",
    "list_reports": "查询报告",
    "list_api_definitions": "查询接口定义",
    "list_api_scenarios": "查询接口场景",
    "list_api_executions": "查询执行记录",
    "query_quality_metrics": "质量指标",
}


def get_tool_label(tool_name: str) -> str:
    """获取工具中文名，MCP 工具显示来源标签"""
    if "__" in tool_name:
        connector, name = tool_name.split("__", 1)
        return f"[{connector}] {TOOL_LABELS.get(name, name)}"
    return TOOL_LABELS.get(tool_name, tool_name)
