from pydantic_settings import BaseSettings
from typing import List
from urllib.parse import quote_plus


class Settings(BaseSettings):
    APP_NAME: str = "AITS 智能测试管理平台"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    ALGORITHM: str = "HS256"

    # LLM API Key 独立加密密钥（32 字节 urlsafe base64）。
    # 生产环境必须配置，避免与 JWT 共用一个密钥源；留空时从 SECRET_KEY 哈希派生（向后兼容）。
    FERNET_KEY: str = ""

    # 数据库类型：mysql 或 sqlite。sqlite 适合本地开发/单机部署，无需外部服务
    DB_TYPE: str = "mysql"

    # MySQL 配置（DB_TYPE=mysql 时使用）
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "root"
    DB_NAME: str = "aits_platform"

    # SQLite 配置（DB_TYPE=sqlite 时使用）
    # 相对路径以 backend 目录为根；推荐放在 data/ 下便于持久化
    DB_PATH: str = "data/aits.db"

    REDIS_URL: str = "redis://localhost:6379/0"

    CORS_ORIGINS: str = "http://localhost:5173"

    # 前端基础地址（用于通知卡片按钮跳转链接）
    FRONTEND_BASE_URL: str = "http://localhost:5173"

    DEFAULT_LLM_PROVIDER: str = "openai_compatible"
    DEFAULT_LLM_BASE_URL: str = "https://api.deepseek.com/v1"
    DEFAULT_LLM_API_KEY: str = ""
    DEFAULT_LLM_MODEL: str = "deepseek-chat"

    # SMTP 邮件配置
    SMTP_HOST: str = "smtp.example.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "aits@example.com"
    SMTP_USE_TLS: bool = True

    # RabbitMQ 配置（可选）
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    RABBITMQ_ENABLED: bool = False

    @property
    def database_url(self) -> str:
        db_type = (self.DB_TYPE or "mysql").strip().lower()
        if db_type == "sqlite":
            # SQLite URL 形式：sqlite:///<相对路径> 或 sqlite:////<绝对路径>
            # 内存库可用 DB_PATH=:memory: 表示
            path = self.DB_PATH or "data/aits.db"
            if path == ":memory:":
                return "sqlite://"
            if path.startswith("/"):
                return f"sqlite:///{path}"
            return f"sqlite:///{path}"
        # 默认 MySQL
        encoded_password = quote_plus(self.DB_PASSWORD)
        return f"mysql+pymysql://{self.DB_USER}:{encoded_password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"

    @property
    def is_sqlite(self) -> bool:
        return (self.DB_TYPE or "").strip().lower() == "sqlite"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
