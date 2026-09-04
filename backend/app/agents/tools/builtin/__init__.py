"""内置工具注册"""
from app.agents.tools.registry import tool_registry
from app.agents.tools.builtin.test_case_tools import QueryProjectStatsTool, ListCasesTool
from app.agents.tools.builtin.defect_tools import ListDefectsTool, AnalyzeDefectsTool, CreateDefectTool
from app.agents.tools.builtin.knowledge_tools import SearchKnowledgeTool
from app.agents.tools.builtin.api_test_tools import (
    ListApiCasesTool, ListApiDefinitionsTool, ListApiScenariosTool, ListApiExecutionsTool,
)
from app.agents.tools.builtin.project_tools import (
    ListProjectsTool, ListTestPlansTool, ListScriptsTool, ListVersionsTool, ListRequirementsTool,
    ListReportsTool, QueryQualityMetricsTool,
)
from app.agents.tools.builtin.data_factory_tools import DATA_FACTORY_TOOLS

# 所有内置工具类
BUILTIN_TOOLS = [
    QueryProjectStatsTool(), ListCasesTool(),
    ListDefectsTool(), AnalyzeDefectsTool(), CreateDefectTool(),
    SearchKnowledgeTool(),
    ListApiCasesTool(), ListApiDefinitionsTool(), ListApiScenariosTool(), ListApiExecutionsTool(),
    ListProjectsTool(), ListTestPlansTool(), ListScriptsTool(), ListVersionsTool(), ListRequirementsTool(),
    ListReportsTool(), QueryQualityMetricsTool(),
] + DATA_FACTORY_TOOLS


def register_builtin_tools():
    """注册所有内置工具到全局 Registry"""
    for tool in BUILTIN_TOOLS:
        tool_registry.register(tool)
