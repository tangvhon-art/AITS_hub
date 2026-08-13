#!/bin/bash
# AITS 前端启动脚本
# 用法: ./start_frontend.sh [--port PORT] [--build]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
PORT=5173
MODE="dev"

# 解析参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)
            PORT="$2"
            shift 2
            ;;
        --build)
            MODE="build"
            shift
            ;;
        *)
            echo "未知参数: $1"
            echo "用法: $0 [--port PORT] [--build]"
            exit 1
            ;;
    esac
done

cd "$FRONTEND_DIR"

# 安装依赖
if [ ! -d "node_modules" ] || [ "package.json" -nt "node_modules/.package-lock.json" ] 2>/dev/null; then
    echo "[前端] 安装 Node.js 依赖..."
    npm install
fi

if [ "$MODE" = "build" ]; then
    echo "[前端] 构建生产版本..."
    npm run build
    echo "[前端] 构建完成，输出目录: dist/"
    echo "[前端] 预览: npm run preview -- --port $PORT"
    npm run preview -- --port "$PORT" --host 0.0.0.0
else
    echo "[前端] 启动开发服务器 (port=$PORT)"
    echo "[前端] 访问地址: http://localhost:$PORT"
    echo "─────────────────────────────────────────"
    npm run dev -- --port "$PORT" --host 0.0.0.0
fi
