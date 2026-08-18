#!/bin/bash
# AITS 后端启动脚本
# 用法: ./start_backend.sh [--no-reload] [--port PORT]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
VENV_DIR="$BACKEND_DIR/venv"
PORT=8000
RELOAD="--reload"

# 解析参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-reload)
            RELOAD=""
            shift
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        *)
            echo "未知参数: $1"
            echo "用法: $0 [--no-reload] [--port PORT]"
            exit 1
            ;;
    esac
done

cd "$BACKEND_DIR"

# 检查 venv
if [ ! -d "$VENV_DIR" ]; then
    echo "[后端] 虚拟环境不存在，正在创建..."
    python3 -m venv "$VENV_DIR"
fi

# 激活 venv
source "$VENV_DIR/bin/activate"

# 安装依赖（如果 requirements.txt 比 venv 新）
if [ "requirements.txt" -nt "$VENV_DIR/.deps_installed" ] 2>/dev/null || [ ! -f "$VENV_DIR/.deps_installed" ]; then
    echo "[后端] 安装/更新 Python 依赖..."
    pip install -r requirements.txt -q
    touch "$VENV_DIR/.deps_installed"
fi

# 安装 Playwright 浏览器（如未安装）
if ! playwright install --dry-run chromium &>/dev/null 2>&1; then
    echo "[后端] 安装 Playwright Chromium 浏览器..."
    playwright install chromium
fi

echo "[后端] 检查并初始化数据库..."
python -c "
from app.main import engine, _auto_migrate
from app.models import *
from app.database import Base
Base.metadata.create_all(bind=engine)
_auto_migrate(engine)
print('[后端] 数据库初始化完成')
" 2>&1 | grep -v "UserWarning\|warnings.warn\|protected_namespaces\|sqlalchemy.engine\|注册工具" || echo "[后端] [警告] 数据库初始化失败，将继续启动（运行时会自动重试）"

echo "[后端] 启动 uvicorn (port=$PORT, reload=$([ -n "$RELOAD" ] && echo "开" || echo "关"))"
echo "[后端] API 地址: http://localhost:$PORT"
echo "[后端] 文档地址: http://localhost:$PORT/docs"
echo "─────────────────────────────────────────"

uvicorn app.main:app $RELOAD --host 0.0.0.0 --port "$PORT"
