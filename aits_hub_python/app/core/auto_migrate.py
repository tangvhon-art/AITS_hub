"""
数据库自动迁移与初始化工具

将原本散落在 main.py 启动流程中的硬编码迁移逻辑集中到本模块：
- auto_migrate：为已有表补充新增列（轻量级增量迁移）
- drop_eval_project_columns：AI 测评系统级化，移除 eval_* 表 project_id
- migrate_project_members：存量项目 owner 迁移到 project_members

说明：当前为保持行为一致的前置收敛步骤，长期建议迁移至 Alembic 统一管理。
"""
import logging

from sqlalchemy import text, inspect

logger = logging.getLogger(__name__)


def auto_migrate(engine):
    """轻量级自动迁移：为已有表补充新增列（create_all 不会修改已有表结构）"""
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
        ("automation_scripts", "heal_enabled", "BOOLEAN DEFAULT 1"),
        ("automation_scripts", "heal_count", "INTEGER DEFAULT 0"),
        ("automation_scripts", "last_healed_at", "DATETIME"),
        ("env_variable_overrides", "value_type", "VARCHAR(20) DEFAULT 'static'"),
        ("env_variable_overrides", "script", "TEXT"),
        # ── 外部工作流接入：agent_tasks 扩展字段 ──
        ("agent_tasks", "backend", "VARCHAR(20) DEFAULT 'local'"),
        ("agent_tasks", "uuid", "VARCHAR(64)"),
        ("agent_tasks", "external_task_id", "VARCHAR(128)"),
        # ── 模块后端配置软删：agent_backend_configs 补软删字段 ──
        ("agent_backend_configs", "is_deleted", "BOOLEAN DEFAULT 0"),
        ("agent_backend_configs", "deleted_at", "DATETIME"),
        # ── AI 测评：eval_targets 外部工作流接入字段（服务地址/调用路径/鉴权方式）──
        ("eval_targets", "service_url", "VARCHAR(500)"),
        ("eval_targets", "call_path", "VARCHAR(200)"),
        ("eval_targets", "auth_type", "VARCHAR(30) DEFAULT 'none'"),
        ("eval_targets", "auth_token", "TEXT"),
        ("eval_targets", "auth_header", "VARCHAR(100) DEFAULT 'Authorization'"),
    ]
    with engine.begin() as conn:
        for table, column, ddl in migrations:
            if table not in inspector.get_table_names():
                continue
            existing_cols = [c["name"] for c in inspector.get_columns(table)]
            if column not in existing_cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
                logger.info(f"自动迁移：{table}.{column} 已添加")


def drop_eval_project_columns(engine):
    """AI 测评系统级化：移除 eval_* 表中 project_id 列（先删外键约束再删列）"""
    inspector = inspect(engine)
    tables = ["eval_targets", "eval_datasets", "eval_cases", "eval_tasks",
              "eval_reports", "eval_issues", "eval_baselines"]
    with engine.begin() as conn:
        for t in tables:
            if t not in inspector.get_table_names():
                continue
            cols = [c["name"] for c in inspector.get_columns(t)]
            if "project_id" not in cols:
                continue
            fks = conn.execute(text(
                "SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t "
                "AND COLUMN_NAME = 'project_id' AND REFERENCED_TABLE_NAME IS NOT NULL"
            ), {"t": t}).fetchall()
            for (fk,) in fks:
                conn.execute(text(f"ALTER TABLE `{t}` DROP FOREIGN KEY `{fk}`"))
            conn.execute(text(f"ALTER TABLE `{t}` DROP COLUMN project_id"))
            logger.info(f"系统级迁移：{t}.project_id 已移除（AI 测评不归属项目）")


def migrate_project_members(engine):
    """将存量项目的 owner 迁移到 project_members 表"""
    inspector = inspect(engine)
    if "project_members" not in inspector.get_table_names():
        return
    with engine.begin() as conn:
        count = conn.execute(text(
            "SELECT COUNT(*) FROM project_members"
        )).scalar()
        if count > 0:
            return
        result = conn.execute(text(
            "INSERT INTO project_members (project_id, user_id, role, joined_at, created_at) "
            "SELECT id, owner_id, 'owner', created_at, created_at "
            "FROM test_projects WHERE is_deleted = 0"
        ))
        if result.rowcount > 0:
            logger.info(f"数据迁移：已将 {result.rowcount} 个项目的 owner 迁移到 project_members 表")


def run_all_migrations(engine):
    """执行全部启动期迁移（保持与旧 main.py 行为一致）。"""
    auto_migrate(engine)
    drop_eval_project_columns(engine)
    migrate_project_members(engine)
