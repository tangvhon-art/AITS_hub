from app.api.auth import router as auth_router
from app.api.projects import router as projects_router
from app.api.requirements import router as requirements_router
from app.api.cases import router as cases_router
from app.api.execution import router as execution_router
from app.api.llm_configs import router as llm_configs_router

__all__ = [
    "auth_router",
    "projects_router",
    "requirements_router",
    "cases_router",
    "execution_router",
    "llm_configs_router",
]
