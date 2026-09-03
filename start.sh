#!/bin/bash
# AITS 一键启动脚本（先启动项目：后端 + 前端，再启动 Worker：Redis + Celery多队列 + Beat + Flower）
# 用法:
#   ./start.sh                                    # 启动全部（前端+后端+Celery+Flower）
#   ./start.sh stop                               # 停止全部服务（同 Ctrl+C，可作显式兜底）
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
ACTION="start"
while [[ $# -gt 0 ]]; do
    case "$1" in
        stop)
            ACTION="stop"
            shift
            ;;
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
            echo "用法: $0 [stop] [--backend-only] [--frontend-only] [--no-celery] [--no-flower] [--all]"
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

# 停止所有 AITS 相关进程并确认端口释放（供启动前清理与 Ctrl+C 退出共用）
stop_all_aits() {
    local found=false

    # Celery Worker / Beat / Flower（含 prefork 子进程 / eventlet）
    if pgrep -f "celery.*app\.celery_app\.celery_app" > /dev/null 2>&1; then
        pkill -9 -f "celery.*app\.celery_app\.celery_app" 2>/dev/null || true
        found=true
        echo "    已停止 Celery Worker / Beat / Flower"
    fi

    # 后端 uvicorn（含 --reload 的 reloader 与 worker 子进程）
    if pgrep -f "uvicorn.*app\.main:app" > /dev/null 2>&1 || pgrep -f "app\.main:app" > /dev/null 2>&1; then
        pkill -9 -f "uvicorn.*app\.main:app" 2>/dev/null || true
        pkill -9 -f "app\.main:app" 2>/dev/null || true
        found=true
        echo "    已停止后端 (uvicorn)"
    fi

    # 前端 vite
    if pgrep -f "vite" > /dev/null 2>&1; then
        pkill -9 -f "vite" 2>/dev/null || true
        found=true
        echo "    已停止前端 (vite)"
    fi

    sleep 2

    # 再次检查端口是否释放，未释放则强制结束占用进程
    for port in "${PORT_BACKEND}" "${PORT_FRONTEND}" "${PORT_FLOWER}"; do
        if lsof -nP -iTCP:"$port" -sTCP:LISTEN > /dev/null 2>&1; then
            echo "    [警告] 端口 $port 仍被占用，强制结束占用进程..."
            lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | awk 'NR>1 {print $2}' | sort -u | xargs kill -9 2>/dev/null || true
            sleep 2
        fi
    done

    if [ "$found" = true ]; then
        echo "    旧进程已全部终止，端口已释放"
    else
        echo "    无残留进程"
    fi
}

stop_existing() {
    echo ">>> 检查并停止已有 AITS 进程..."
    stop_all_aits
}

cleanup() {
    echo ""
    echo "正在停止所有服务..."
    stop_all_aits
    # 停止本脚本启动的 Redis（daemonize 模式）
    if pgrep -f "redis-server" > /dev/null 2>&1; then
        pkill -9 -f "redis-server" 2>/dev/null || true
        echo "    已停止 Redis"
    fi
    echo "已停止"
    exit 0
}

trap cleanup SIGINT SIGTERM

# 显式停止入口：./start.sh stop
# （Ctrl+C 已通过 trap cleanup 处理；此处提供命令行显式停止，作为可靠兜底）
if [ "$ACTION" = "stop" ]; then
    echo ">>> 停止所有 AITS 服务..."
    stop_all_aits
    # 停止本脚本启动的 Redis（daemonize 模式）
    if pgrep -f "redis-server" > /dev/null 2>&1; then
        pkill -9 -f "redis-server" 2>/dev/null || true
        echo "    已停止 Redis"
    fi
    echo "已停止"
    exit 0
fi

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

    # 平台检测
    if [ "$(uname -s)" = "Darwin" ]; then
        # Mac开发环境：eventlet协程池，避开fork问题，支持并发
        SCALE_NOTE="macOS eventlet 协程池，公平调度，并发=2"
        POOL_ARG="-P eventlet"
        DEFAULT_SCALE="-c 2"
        AI_SCALE="-c 2"
        EXEC_SCALE="-c 2"
        FAIR_ARGS="-O fair --prefetch-multiplier=1"
    else
        # Linux生产环境：prefork + autoscale 动态扩缩容
        SCALE_NOTE="Linux prefork + autoscale 动态扩缩容"
        POOL_ARG=""
        DEFAULT_SCALE="--autoscale=4,2"
        AI_SCALE="--autoscale=6,2"
        EXEC_SCALE="--autoscale=12,2"
        FAIR_ARGS="-O fair --prefetch-multiplier=1"
    fi
    echo "    并发模式: $SCALE_NOTE"

    # --- AI 队列 Worker ---
    AI_LOG="$SCRIPT_DIR/logs/worker-ai.log"
    nohup ./venv/bin/celery -A app.celery_app.celery_app worker \
        --loglevel=info \
        $AI_SCALE \
        $POOL_ARG \
        $FAIR_ARGS \
        --hostname=ai-worker@%h \
        -Q ai \
        --events \
        --heartbeat-interval=5 \
        --max-tasks-per-child=100 \
        > "$AI_LOG" 2>&1 &
    AI_PID=$!
    PIDS+=($AI_PID)
    echo "    AI Worker 启动 (PID=$AI_PID, 队列=ai, $AI_SCALE)"

    # --- Execution 队列 Worker ---
    EXEC_LOG="$SCRIPT_DIR/logs/worker-execution.log"
    nohup ./venv/bin/celery -A app.celery_app.celery_app worker \
        --loglevel=info \
        $EXEC_SCALE \
        $POOL_ARG \
        $FAIR_ARGS \
        --hostname=execution-worker@%h \
        -Q execution \
        --events \
        --heartbeat-interval=5 \
        --max-tasks-per-child=100 \
        > "$EXEC_LOG" 2>&1 &
    EXEC_PID=$!
    PIDS+=($EXEC_PID)
    echo "    Execution Worker 启动 (PID=$EXEC_PID, 队列=execution, $EXEC_SCALE)"

    # --- Default 队列 Worker ---
    DEFAULT_LOG="$SCRIPT_DIR/logs/worker-default.log"
    nohup ./venv/bin/celery -A app.celery_app.celery_app worker \
        --loglevel=info \
        $DEFAULT_SCALE \
        $POOL_ARG \
        $FAIR_ARGS \
        --hostname=default-worker@%h \
        -Q default \
        --events \
        --heartbeat-interval=5 \
        --max-tasks-per-child=100 \
        > "$DEFAULT_LOG" 2>&1 &
    DEFAULT_PID=$!
    PIDS+=($DEFAULT_PID)
    echo "    Default Worker 启动 (PID=$DEFAULT_PID, 队列=default, $DEFAULT_SCALE)"

    # --- Eval（AI 测评）队列 Worker ---
    EVAL_LOG="$SCRIPT_DIR/logs/worker-eval.log"
    nohup ./venv/bin/celery -A app.celery_app.celery_app worker \
        --loglevel=info \
        $AI_SCALE \
        $POOL_ARG \
        $FAIR_ARGS \
        --hostname=eval-worker@%h \
        -Q eval \
        --events \
        --heartbeat-interval=5 \
        --max-tasks-per-child=100 \
        > "$EVAL_LOG" 2>&1 &
    EVAL_PID=$!
    PIDS+=($EVAL_PID)
    echo "    Eval Worker 启动 (PID=$EVAL_PID, 队列=eval, $AI_SCALE)"

    # --- Beat 定时任务调度器 ---
    # ⚠️ Beat 必须单实例运行（多个 beat 会重复派发任务），--pidfile 防止重复启动
    BEAT_LOG="$SCRIPT_DIR/logs/beat.log"
    nohup ./venv/bin/celery -A app.celery_app.celery_app beat \
        --loglevel=info \
        --pidfile="$SCRIPT_DIR/logs/beat.pid" \
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
        if cd "$SCRIPT_DIR/backend" && ./venv/bin/celery -A app.celery_app.celery_app inspect ping -d "ai-worker@$(hostname)" > /dev/null 2>&1; then
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
if [ "$START_CELERY" = true ]; then
    if [ "$(uname -s)" = "Darwin" ]; then
        echo "  Celery Worker: 4个队列已启动（macOS eventlet协程池, 每队列并发=2）"
        echo "    - ai        (IO协程并发2, AI生成类任务)"
        echo "    - execution (IO协程并发2, 执行类任务)"
        echo "    - default   (IO协程并发2, 后台轻量任务)"
        echo "    - eval      (IO协程并发2, AI模型测评任务)"
    else
        echo "  Celery Worker: 4个队列已启动（Linux prefork + autoscale 动态扩缩容）"
        echo "    - ai        (autoscale=6,2, AI生成类任务)"
        echo "    - execution (autoscale=12,2, 执行类任务, 扩容上限最高)"
        echo "    - default   (autoscale=4,2, 后台轻量任务)"
        echo "    - eval      (autoscale=4,2, AI模型测评任务)"
    fi
fi
[ "$START_CELERY" = true ]   && echo "  Beat:          定时任务调度器已启动"
[ "$START_FLOWER" = true ]   && echo "  Flower:        http://localhost:$PORT_FLOWER/flower/"
[ "$START_FLOWER" = true ]   && echo "  任务监控:      http://localhost:$PORT_FRONTEND/task-monitor"
[ "$START_CELERY" = true ]   && echo ""
[ "$START_CELERY" = true ]   && echo "  日志文件:"
[ "$START_CELERY" = true ]   && echo "    logs/worker-ai.log / worker-execution.log / worker-default.log / worker-eval.log / beat.log"
echo ""
echo "按 Ctrl+C 停止所有服务"
echo "─────────────────────────────────────────"

# 保持前台运行，并确保 Ctrl+C / SIGTERM 能立即触发 cleanup
# （不使用 wait：bash 在 wait 内置命令中会阻塞信号处理，导致 trap 延迟）
while true; do
    sleep 1
done
