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
]
