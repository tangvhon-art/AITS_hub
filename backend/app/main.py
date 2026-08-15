import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.config import settings
from app.database import engine, Base
from app.core.exceptions import (
    http_exception_handler,
    validation_exception_handler,
    general_exception_handler,
)
from app.api import (
    auth_router,
    projects_router,
    requirements_router,
    cases_router,
    execution_router,
    llm_configs_router,
    defects_router,
    reports_router,
    knowledge_router,
    agent_tasks_router,
    agent_tasks_project_router,
    test_plans_router,
    test_plans_project_router,
    test_plan_executions_router,
    quality_router,
    quality_project_router,
    audit_logs_router,
    import_export_router,
    import_export_project_router,
    automation_scripts_router,
    automation_suites_router,
    suite_runs_router,
    project_versions_router,
    chat_router,
    api_modules_router,
    api_definitions_router,
    api_debug_router,
    api_cases_router,
    api_scenarios_router,
    api_executions_router,
    api_mock_router,
    api_import_router,
    mock_data_router,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时创建数据库表"""
    logger.info("正在初始化数据库表...")
    # 导入所有模型确保 Base.metadata 包含所有表
    from app.models import (
        User, Project, TestRequirement, TestCase, TestRun,
        AgentTask, LLMConfig, Defect, TestReport, KnowledgeDoc,
        TestPlan, TestPlanCase, TestEnvironment, AuditLog,
        TestPlanItem, TestPlanExecution, TestPlanExecutionResult,
        AutomationScript, AutomationSuite, AutomationSuiteStep,
        AutomationSuiteRun, AutomationSuiteRunResult,
        ProjectVersion,
        ApiModule, ApiDefinition, ApiTestCase, ApiCaseAssertion,
        ApiScenario, ApiScenarioStep, ApiScenarioVariable,
        ApiExecution, ApiExecutionResult, ApiMockExpectation,
        ApiDebugHistory,
    )
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表初始化完成")
    yield
    logger.info("应用关闭")


app = FastAPI(
    title=settings.APP_NAME,
    description="LangChain + Agent 智能测试管理平台 API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册全局异常处理器
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# 注册路由
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(requirements_router)
app.include_router(cases_router)
app.include_router(execution_router)
app.include_router(llm_configs_router)
app.include_router(defects_router)
app.include_router(reports_router)
app.include_router(knowledge_router)
app.include_router(agent_tasks_router)
app.include_router(agent_tasks_project_router)
app.include_router(test_plans_router)
app.include_router(test_plans_project_router)
app.include_router(test_plan_executions_router)
app.include_router(quality_router)
app.include_router(quality_project_router)
app.include_router(audit_logs_router)
app.include_router(import_export_router)
app.include_router(import_export_project_router)
app.include_router(automation_scripts_router)
app.include_router(automation_suites_router)
app.include_router(suite_runs_router)
app.include_router(project_versions_router)
app.include_router(chat_router)
app.include_router(api_modules_router)
app.include_router(api_definitions_router)
app.include_router(api_debug_router)
app.include_router(api_cases_router)
app.include_router(api_scenarios_router)
app.include_router(api_executions_router)
app.include_router(api_mock_router)
app.include_router(api_import_router)
app.include_router(mock_data_router)


@app.get("/api/health", tags=["系统"])
def health_check():
    """健康检查"""
    return {"status": "ok", "app": settings.APP_NAME, "version": "1.0.0"}


@app.get("/", tags=["系统"])
def root():
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "docs": "/docs",
        "api_prefix": "/api",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
