from app.api.auth import router as auth_router
from app.api.projects import router as projects_router
from app.api.requirements import router as requirements_router
from app.api.cases import router as cases_router
from app.api.execution import router as execution_router
from app.api.llm_configs import router as llm_configs_router
from app.api.defects import router as defects_router
from app.api.reports import router as reports_router
from app.api.knowledge import router as knowledge_router
from app.api.agent_tasks import router as agent_tasks_router
from app.api.agent_tasks import project_router as agent_tasks_project_router
from app.api.test_plans import router as test_plans_router
from app.api.test_plans import project_router as test_plans_project_router
from app.api.test_plans import execution_router as test_plan_executions_router
from app.api.quality import router as quality_router
from app.api.quality import project_router as quality_project_router
from app.api.audit_logs import router as audit_logs_router
from app.api.import_export import router as import_export_router
from app.api.import_export import project_router as import_export_project_router
from app.api.project_versions import router as project_versions_router
from app.api.automation_scripts import router as automation_scripts_router
from app.api.automation_suites import router as automation_suites_router
from app.api.automation_suites import run_router as suite_runs_router
from app.api.chat import router as chat_router
from app.api.chat_history import router as chat_history_router
from app.api.api_modules import router as api_modules_router
from app.api.api_definitions import router as api_definitions_router
from app.api.api_debug import router as api_debug_router
from app.api.api_cases import router as api_cases_router
from app.api.api_scenarios import router as api_scenarios_router
from app.api.api_executions import router as api_executions_router
from app.api.api_mock import router as api_mock_router
from app.api.api_import import router as api_import_router
from app.api.mock_data import router as mock_data_router
from app.api.performance_tests import router as performance_tests_router
from app.api.performance_tests import run_router as performance_run_router
from app.api.coverage import router as coverage_router
from app.api.data_pools import router as data_pools_router
from app.api.env_variables import router as env_variables_router
from app.api.env_variables import compare_router as env_compare_router
from app.api.prompts import router as prompts_router
from app.api.notifications import router as notifications_router
from app.api.mcp import router as mcp_router
from app.api.skills import router as skills_router

__all__ = [
    "auth_router",
    "projects_router",
    "requirements_router",
    "cases_router",
    "execution_router",
    "llm_configs_router",
    "defects_router",
    "reports_router",
    "knowledge_router",
    "agent_tasks_router",
    "agent_tasks_project_router",
    "test_plans_router",
    "test_plans_project_router",
    "test_plan_executions_router",
    "quality_router",
    "quality_project_router",
    "audit_logs_router",
    "import_export_router",
    "import_export_project_router",
    "project_versions_router",
    "automation_scripts_router",
    "automation_suites_router",
    "suite_runs_router",
    "chat_router",
    "chat_history_router",
    "api_modules_router",
    "api_definitions_router",
    "api_debug_router",
    "api_cases_router",
    "api_scenarios_router",
    "api_executions_router",
    "api_mock_router",
    "api_import_router",
    "mock_data_router",
    "performance_tests_router",
    "performance_run_router",
    "coverage_router",
    "data_pools_router",
    "env_variables_router",
    "env_compare_router",
    "prompts_router",
    "notifications_router",
    "mcp_router",
    "skills_router",
]
