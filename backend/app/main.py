import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
from app.core.error_handlers import register_exception_handlers
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
    performance_tests_router,
    performance_run_router,
    coverage_router,
    data_pools_router,
    env_variables_router,
    env_compare_router,
    prompts_router,
    notifications_router,
    mcp_router,
    skills_router,
)

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
# 生产环境关闭 SQLAlchemy SQL 日志
if settings.APP_ENV == "production":
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def _auto_migrate(engine):
    """轻量级自动迁移：为已有表补充新增列（create_all 不会修改已有表结构）"""
    from sqlalchemy import text, inspect
    inspector = inspect(engine)
    migrations = [
        ("test_cases", "needs_update", "BOOLEAN DEFAULT 0"),
        ("performance_tests", "data_pool_id", "INTEGER"),
        ("api_test_cases", "data_pool_id", "INTEGER"),
        ("api_scenarios", "data_pool_id", "INTEGER"),
        ("knowledge_docs", "source_type", "VARCHAR(30) DEFAULT 'manual'"),
        ("knowledge_docs", "source_id", "INTEGER"),
        ("llm_configs", "supports_function_calling", "TINYINT DEFAULT 1"),
        ("llm_configs", "tool_call_strategy", "VARCHAR(20) DEFAULT 'auto'"),
        ("llm_configs", "api_format", "VARCHAR(30) DEFAULT 'chat_completions'"),
        ("llm_configs", "capabilities", "JSON"),
        ("skills", "files", "JSON"),
        ("performance_tests", "targets", "JSON"),
        ("performance_test_runs", "endpoint_stats", "JSON"),
        ("test_requirements", "feature_split_status", "VARCHAR(20) DEFAULT 'pending'"),
        ("test_cases", "feature_id", "INTEGER"),
    ]
    with engine.begin() as conn:
        for table, column, ddl in migrations:
            if table not in inspector.get_table_names():
                continue
            existing_cols = [c["name"] for c in inspector.get_columns(table)]
            if column not in existing_cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
                logger.info(f"自动迁移：{table}.{column} 已添加")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时创建数据库表"""
    logger.info("正在初始化数据库表...")
    # 导入所有模型确保 Base.metadata 包含所有表
    from app.models import (
        User, Project, TestRequirement, RequirementFeature, TestCase, TestRun,
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
        PerformanceTest, PerformanceTestRun,
        CoverageConfig, CoverageSnapshot,
        TestDataPool, EnvironmentVariableOverride,
        Prompt,
        NotificationChannel, NotificationRule, NotificationRecord,
        MCPConnector, Skill,
    )
    Base.metadata.create_all(bind=engine)
    _auto_migrate(engine)
    logger.info("数据库表初始化完成")

    # 注册内置工具
    try:
        from app.agents.tools.builtin import register_builtin_tools
        register_builtin_tools()
        from app.agents.tools.registry import tool_registry
        logger.info(f"内置工具注册完成，共 {len(tool_registry.list_tools())} 个工具")
    except Exception as e:
        logger.warning(f"内置工具注册失败: {e}")

    # 后台异步重连已启用的 MCP 连接器（不阻塞启动）
    async def _reconnect_mcp_connectors():
        await asyncio.sleep(2)  # 等待应用完全启动
        try:
            from app.models.mcp_connector import MCPConnector
            from app.mcp.client import MCPClient
            from app.database import SessionLocal
            db = SessionLocal()
            try:
                connectors = db.query(MCPConnector).filter(
                    MCPConnector.is_active == True,
                    MCPConnector.is_deleted == False,
                ).all()
                if connectors:
                    logger.info(f"发现 {len(connectors)} 个已启用 MCP 连接器，开始重连...")
                for conn in connectors:
                    try:
                        client = MCPClient(
                            connector_id=conn.id, name=conn.name, transport=conn.transport,
                            url=conn.url or "", command=conn.command or "",
                            args=conn.args or [], env_vars=conn.env_vars or {},
                        )
                        tools = await client.connect()
                        logger.info(f"MCP 连接器 [{conn.name}] 重连成功，注册 {len(tools)} 个工具")
                    except Exception as e:
                        logger.warning(f"MCP 连接器 [{conn.name}] 重连失败: {e}")
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"MCP 自动重连异常: {e}")

    asyncio.create_task(_reconnect_mcp_connectors())

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
register_exception_handlers(app)

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
app.include_router(performance_tests_router)
app.include_router(performance_run_router)
app.include_router(coverage_router)
app.include_router(data_pools_router)
app.include_router(env_variables_router)
app.include_router(env_compare_router)
app.include_router(prompts_router)
app.include_router(notifications_router)
app.include_router(mcp_router)
app.include_router(skills_router)


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
