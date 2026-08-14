#!/bin/bash
# AITS 一键启动脚本（前端 + 后端 + Redis + Celery + Flower）
# 用法:
#   ./start.sh                                    # 启动前端+后端
#   ./start.sh --with-celery                      # 启动前端+后端+Celery Worker
#   ./start.sh --with-celery --with-flower        # 启动前端+后端+Celery+Flower
#   ./start.sh --backend-only --with-celery       # 仅启动后端+Celery
#   ./start.sh --port-backend 8000 --port-frontend 5173

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
START_BACKEND=true
START_FRONTEND=true
START_CELERY=true
START_FLOWER=true
PORT_BACKEND=8000
PORT_FRONTEND=5173
PORT_FLOWER=5555
CELERY_CONCURRENCY=4

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
        --with-celery)
            START_CELERY=true
            shift
            ;;
        --with-flower)
            START_FLOWER=true
            shift
            ;;
        --all)
            START_CELERY=true
            START_FLOWER=true
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
        --port-flower)
            PORT_FLOWER="$2"
            shift 2
            ;;
        --celery-concurrency)
            CELERY_CONCURRENCY="$2"
            shift 2
            ;;
        *)
            echo "未知参数: $1"
            echo "用法: $0 [--backend-only] [--frontend-only] [--with-celery] [--with-flower] [--all]"
            echo "          [--port-backend PORT] [--port-frontend PORT] [--port-flower PORT]"
            echo "          [--celery-concurrency N]"
            exit 1
            ;;
    esac
done

# Flower 依赖 Celery，自动启用
if [ "$START_FLOWER" = true ]; then
    START_CELERY=true
fi

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

# 检查并启动 Redis（Celery 依赖）
if [ "$START_CELERY" = true ]; then
    if redis-cli ping > /dev/null 2>&1; then
        echo ">>> Redis 已在运行"
    else
        echo ">>> 启动 Redis..."
        redis-server --daemonize yes
        sleep 1
        if redis-cli ping > /dev/null 2>&1; then
            echo "    Redis 启动成功"
        else
            echo "    [警告] Redis 启动失败，Celery 将无法工作"
        fi
    fi
fi

# 启动 Celery Worker
if [ "$START_CELERY" = true ]; then
    echo ">>> 启动 Celery Worker (concurrency=$CELERY_CONCURRENCY)..."
    cd "$SCRIPT_DIR/backend"
    source venv/bin/activate
    celery -A app.celery_app.celery_app worker \
        --loglevel=info \
        --concurrency="$CELERY_CONCURRENCY" \
        --hostname=aits-worker@%h \
        -Q celery \
        --max-tasks-per-child=100 \
        --time-limit=600 &
    PIDS+=($!)
    deactivate
    cd "$SCRIPT_DIR"
fi

# 启动 Flower 监控面板
if [ "$START_FLOWER" = true ]; then
    echo ">>> 启动 Flower 监控面板 (port=$PORT_FLOWER)..."
    cd "$SCRIPT_DIR/backend"
    source venv/bin/activate
    FLOWER_UNAUTHENTICATED_API=true celery -A app.celery_app.celery_app flower \
        --port="$PORT_FLOWER" \
        --conf=flowerconfig.py \
        --auto_refresh=true &
    PIDS+=($!)
    deactivate
    cd "$SCRIPT_DIR"
fi

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
[ "$START_BACKEND" = true ]  && echo "  后端 API:    http://localhost:$PORT_BACKEND"
[ "$START_BACKEND" = true ]  && echo "  API 文档:    http://localhost:$PORT_BACKEND/docs"
[ "$START_FRONTEND" = true ] && echo "  前端页面:    http://localhost:$PORT_FRONTEND"
[ "$START_CELERY" = true ]   && echo "  Celery:      Worker 已启动 (concurrency=$CELERY_CONCURRENCY)"
[ "$START_FLOWER" = true ]   && echo "  Flower:      http://localhost:$PORT_FLOWER/flower/"
[ "$START_FLOWER" = true ]   && echo "  任务监控:    http://localhost:$PORT_FRONTEND/task-monitor"
echo ""
echo "按 Ctrl+C 停止所有服务"
echo "─────────────────────────────────────────"

wait
