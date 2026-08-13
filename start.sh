#!/bin/bash
# AITS 一键启动脚本（前端 + 后端）
# 用法: ./start.sh [--backend-only] [--frontend-only] [--port-backend PORT] [--port-frontend PORT]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
START_BACKEND=true
START_FRONTEND=true
PORT_BACKEND=8000
PORT_FRONTEND=5173

# 解析参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --backend-only)
            START_FRONTEND=false
            shift
            ;;
        --frontend-only)
            START_BACKEND=false
            shift
            ;;
        --port-backend)
            PORT_BACKEND="$2"
            shift 2
            ;;
        --port-frontend)
            PORT_FRONTEND="$2"
            shift 2
            ;;
        *)
            echo "未知参数: $1"
            echo "用法: $0 [--backend-only] [--frontend-only] [--port-backend PORT] [--port-frontend PORT]"
            exit 1
            ;;
    esac
done

PIDS=()

cleanup() {
    echo ""
    echo "正在停止所有服务..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null
    echo "已停止"
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "╔═══════════════════════════════════════╗"
echo "║    AITS 智能测试管理平台 - 启动中     ║"
echo "╚═══════════════════════════════════════╝"
echo ""

# 启动后端
if [ "$START_BACKEND" = true ]; then
    echo ">>> 启动后端 (port=$PORT_BACKEND)..."
    bash "$SCRIPT_DIR/start_backend.sh" --port "$PORT_BACKEND" &
    PIDS+=($!)
fi

# 启动前端
if [ "$START_FRONTEND" = true ]; then
    echo ">>> 启动前端 (port=$PORT_FRONTEND)..."
    bash "$SCRIPT_DIR/start_frontend.sh" --port "$PORT_FRONTEND" &
    PIDS+=($!)
fi

echo ""
echo "服务已启动:"
[ "$START_BACKEND" = true ]  && echo "  后端 API:  http://localhost:$PORT_BACKEND"
[ "$START_BACKEND" = true ]  && echo "  API 文档:  http://localhost:$PORT_BACKEND/docs"
[ "$START_FRONTEND" = true ] && echo "  前端页面:  http://localhost:$PORT_FRONTEND"
echo ""
echo "按 Ctrl+C 停止所有服务"
echo "─────────────────────────────────────────"

wait
