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
from app.api.quality import router as quality_router
from app.api.quality import project_router as quality_project_router
from app.api.audit_logs import router as audit_logs_router
from app.api.import_export import router as import_export_router
from app.api.import_export import project_router as import_export_project_router
from app.api.automation_scripts import router as automation_scripts_router
from app.api.automation_suites import router as automation_suites_router
from app.api.automation_suites import run_router as suite_runs_router

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
    "quality_router",
    "quality_project_router",
    "audit_logs_router",
    "import_export_router",
    "import_export_project_router",
    "automation_scripts_router",
    "automation_suites_router",
    "suite_runs_router",
]
