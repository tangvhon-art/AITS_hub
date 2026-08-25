#!/bin/bash
# AITS 一键启动脚本（先启动项目：后端 + 前端，再启动 Worker：Redis + Celery多队列 + Beat + Flower）
# 用法:
#   ./start.sh                                    # 启动全部（前端+后端+Celery+Flower）
#   ./start.sh --backend-only                     # 仅启动后端+Celery
#   ./start.sh --frontend-only                    # 仅启动前端
#   ./start.sh --no-celery                        # 不启动 Celery
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
        --no-celery)
            START_CELERY=false
            START_FLOWER=false
            shift
            ;;
        --no-flower)
            START_FLOWER=false
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
        *)
            echo "未知参数: $1"
            echo "用法: $0 [--backend-only] [--frontend-only] [--no-celery] [--no-flower] [--all]"
            echo "          [--port-backend PORT] [--port-frontend PORT] [--port-flower PORT]"
            exit 1
            ;;
    esac
done

# Flower 依赖 Celery，自动启用
if [ "$START_FLOWER" = true ]; then
    START_CELERY=true
fi

PIDS=()

# 停止所有 AITS 相关进程（Celery worker/子进程、Flower、uvicorn、vite）
stop_existing() {
    echo ">>> 检查并停止已有 AITS 进程..."
    local found=false

    # Celery worker 及其 fork 子进程
    if pgrep -f "celery.*app\.celery_app\.celery_app worker" > /dev/null 2>&1; then
        pkill -f "celery.*app\.celery_app\.celery_app worker" 2>/dev/null || true
        found=true
        echo "    已停止 Celery Worker"
    fi

    # Celery Beat
    if pgrep -f "celery.*app\.celery_app\.celery_app beat" > /dev/null 2>&1; then
        pkill -f "celery.*app\.celery_app\.celery_app beat" 2>/dev/null || true
        found=true
        echo "    已停止 Celery Beat"
    fi

    # Flower
    if pgrep -f "celery.*app\.celery_app\.celery_app flower" > /dev/null 2>&1; then
        pkill -f "celery.*app\.celery_app\.celery_app flower" 2>/dev/null || true
        found=true
        echo "    已停止 Flower"
    fi

    # 后端 uvicorn
    if pgrep -f "uvicorn app\.main:app" > /dev/null 2>&1; then
        pkill -f "uvicorn app\.main:app" 2>/dev/null || true
        found=true
        echo "    已停止后端 (uvicorn)"
    fi

    # 前端 vite
    if pgrep -f "vite" > /dev/null 2>&1; then
        pkill -f "vite" 2>/dev/null || true
        found=true
        echo "    已停止前端 (vite)"
    fi

    if [ "$found" = true ]; then
        sleep 2
        echo "    旧进程已全部终止"
    else
        echo "    无残留进程"
    fi
}

cleanup() {
    echo ""
    echo "正在停止所有服务..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    # 确保子进程也被清理
    pkill -f "celery.*app\.celery_app\.celery_app" 2>/dev/null || true
    pkill -f "uvicorn app\.main:app" 2>/dev/null || true
    pkill -f "vite" 2>/dev/null || true
    pkill -f "redis-server" 2>/dev/null || true
    wait 2>/dev/null
    echo "已停止"
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "╔═══════════════════════════════════════╗"
echo "║    AITS 智能测试管理平台 - 启动中     ║"
echo "╚═══════════════════════════════════════╝"
echo ""

# 先停止所有已有进程，避免端口冲突和重复 worker
stop_existing

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

# 启动后端（先启动项目，再启动 Celery Worker）
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

# 启动 Celery 多队列 Worker + Beat
if [ "$START_CELERY" = true ]; then
    echo ">>> 启动 Celery 多队列 Worker..."
    cd "$SCRIPT_DIR/backend"
    unset PYTHONHOME PYTHONPATH
    mkdir -p "$SCRIPT_DIR/logs"

    # --- AI 队列 Worker ---
    AI_LOG="$SCRIPT_DIR/logs/worker-ai.log"
    nohup ./venv/bin/celery -A app.celery_app.celery_app worker \
        --loglevel=info \
        --concurrency=2 \
        --hostname=ai-worker@%h \
        -Q ai \
        --events \
        --heartbeat-interval=5 \
        --max-tasks-per-child=100 \
        --time-limit=600 \
        > "$AI_LOG" 2>&1 &
    AI_PID=$!
    PIDS+=($AI_PID)
    echo "    AI Worker 启动 (PID=$AI_PID, 队列=ai, 并发=2)"

    # --- Execution 队列 Worker ---
    EXEC_LOG="$SCRIPT_DIR/logs/worker-execution.log"
    nohup ./venv/bin/celery -A app.celery_app.celery_app worker \
        --loglevel=info \
        --concurrency=4 \
        --hostname=execution-worker@%h \
        -Q execution \
        --events \
        --heartbeat-interval=5 \
        --max-tasks-per-child=100 \
        --time-limit=600 \
        > "$EXEC_LOG" 2>&1 &
    EXEC_PID=$!
    PIDS+=($EXEC_PID)
    echo "    Execution Worker 启动 (PID=$EXEC_PID, 队列=execution, 并发=4)"

    # --- Default 队列 Worker ---
    DEFAULT_LOG="$SCRIPT_DIR/logs/worker-default.log"
    nohup ./venv/bin/celery -A app.celery_app.celery_app worker \
        --loglevel=info \
        --concurrency=2 \
        --hostname=default-worker@%h \
        -Q default \
        --events \
        --heartbeat-interval=5 \
        --max-tasks-per-child=100 \
        --time-limit=600 \
        > "$DEFAULT_LOG" 2>&1 &
    DEFAULT_PID=$!
    PIDS+=($DEFAULT_PID)
    echo "    Default Worker 启动 (PID=$DEFAULT_PID, 队列=default, 并发=2)"

    # --- Beat 定时任务调度器 ---
    BEAT_LOG="$SCRIPT_DIR/logs/beat.log"
    nohup ./venv/bin/celery -A app.celery_app.celery_app beat \
        --loglevel=info \
        > "$BEAT_LOG" 2>&1 &
    BEAT_PID=$!
    PIDS+=($BEAT_PID)
    echo "    Beat 调度器 启动 (PID=$BEAT_PID)"

    cd "$SCRIPT_DIR"

    # 等待 Worker 就绪
    echo "    等待 Worker 就绪..."
    sleep 3
    WORKER_READY=false
    for i in $(seq 1 10); do
        if cd "$SCRIPT_DIR/backend" && ./venv/bin/celery -A app.celery_app.celery_app inspect ping -d "celery@ai-worker@$(hostname)" > /dev/null 2>&1; then
            WORKER_READY=true
        fi
        cd "$SCRIPT_DIR"
        if [ "$WORKER_READY" = true ]; then
            break
        fi
        sleep 2
    done
    if [ "$WORKER_READY" = true ]; then
        echo "    所有 Worker 已就绪"
    else
        echo "    [警告] Worker 就绪检测超时（进程可能仍在启动中）"
    fi
fi

# 启动 Flower 监控面板
if [ "$START_FLOWER" = true ]; then
    echo ">>> 启动 Flower 监控面板 (port=$PORT_FLOWER)..."
    cd "$SCRIPT_DIR/backend"
    unset PYTHONHOME PYTHONPATH
    export FLOWER_UNAUTHENTICATED_API=true
    FLOWER_LOG="$SCRIPT_DIR/logs/flower.log"
    mkdir -p "$SCRIPT_DIR/logs"
    nohup ./venv/bin/celery \
        -A app.celery_app.celery_app flower \
        --port="$PORT_FLOWER" \
        --conf=flowerconfig.py \
        --auto_refresh=true \
        > "$FLOWER_LOG" 2>&1 &
    PIDS+=($!)
    cd "$SCRIPT_DIR"
fi

echo ""
echo "服务已启动:"
[ "$START_BACKEND" = true ]  && echo "  后端 API:      http://localhost:$PORT_BACKEND"
[ "$START_BACKEND" = true ]  && echo "  API 文档:      http://localhost:$PORT_BACKEND/docs"
[ "$START_FRONTEND" = true ] && echo "  前端页面:      http://localhost:$PORT_FRONTEND"
[ "$START_CELERY" = true ]   && echo "  Celery Worker: 3个队列已启动"
[ "$START_CELERY" = true ]   && echo "    - ai        (并发2, AI生成类任务)"
[ "$START_CELERY" = true ]   && echo "    - execution (并发4, 执行类任务)"
[ "$START_CELERY" = true ]   && echo "    - default   (并发2, 后台轻量任务)"
[ "$START_CELERY" = true ]   && echo "  Beat:          定时任务调度器已启动"
[ "$START_FLOWER" = true ]   && echo "  Flower:        http://localhost:$PORT_FLOWER/flower/"
[ "$START_FLOWER" = true ]   && echo "  任务监控:      http://localhost:$PORT_FRONTEND/task-monitor"
[ "$START_CELERY" = true ]   && echo ""
[ "$START_CELERY" = true ]   && echo "  日志文件:"
[ "$START_CELERY" = true ]   && echo "    logs/worker-ai.log / worker-execution.log / worker-default.log / beat.log"
echo ""
echo "按 Ctrl+C 停止所有服务"
echo "─────────────────────────────────────────"

wait
