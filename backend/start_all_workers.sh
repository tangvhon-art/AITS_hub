#!/bin/bash
# 一键启动所有 Worker + Beat + Flower
# 用法: ./start_all_workers.sh
# 停止: killall celery (或使用 stop_all_workers.sh)

cd "$(dirname "$0")"
source venv/bin/activate

echo "========================================="
echo "  AITS 全部 Worker 启动"
echo "  队列: ai / execution / default"
echo "  包含: Beat 定时任务 + Flower 监控"
echo "========================================="
echo ""

# 检查 Redis 是否运行
if ! redis-cli ping > /dev/null 2>&1; then
    echo "错误: Redis 未运行，请先启动 Redis"
    echo "启动命令: redis-server --daemonize yes"
    exit 1
fi

# 启动 Beat（只有一个实例）
echo "[1/5] 启动 Celery Beat..."
celery -A app.celery_app.celery_app beat \
    --loglevel=info \
    > logs/beat.log 2>&1 &
BEAT_PID=$!
echo "  Beat PID: $BEAT_PID"

# 启动 AI Worker
echo "[2/5] 启动 AI Worker (队列: ai, 并发: 2)..."
celery -A app.celery_app.celery_app worker \
    --loglevel=info \
    --concurrency=2 \
    --hostname=ai-worker@%h \
    -Q ai \
    --max-tasks-per-child=100 \
    > logs/worker-ai.log 2>&1 &
AI_PID=$!
echo "  AI Worker PID: $AI_PID"

# 启动 Execution Worker
echo "[3/5] 启动 Execution Worker (队列: execution, 并发: 4)..."
celery -A app.celery_app.celery_app worker \
    --loglevel=info \
    --concurrency=4 \
    --hostname=execution-worker@%h \
    -Q execution \
    --max-tasks-per-child=100 \
    > logs/worker-execution.log 2>&1 &
EXEC_PID=$!
echo "  Execution Worker PID: $EXEC_PID"

# 启动 Default Worker
echo "[4/5] 启动 Default Worker (队列: default, 并发: 2)..."
celery -A app.celery_app.celery_app worker \
    --loglevel=info \
    --concurrency=2 \
    --hostname=default-worker@%h \
    -Q default \
    --max-tasks-per-child=100 \
    > logs/worker-default.log 2>&1 &
DEFAULT_PID=$!
echo "  Default Worker PID: $DEFAULT_PID"

# 启动 Flower
sleep 2
echo "[5/5] 启动 Flower 监控面板..."
env FLOWER_UNAUTHENTICATED_API=true \
    celery -A app.celery_app.celery_app flower \
    --port=5555 \
    --conf=flowerconfig.py \
    --auto_refresh=true \
    > logs/flower.log 2>&1 &
FLOWER_PID=$!
echo "  Flower PID: $FLOWER_PID"

# 保存 PID 以便停止
mkdir -p logs
echo "$BEAT_PID" > logs/beat.pid
echo "$AI_PID" > logs/worker-ai.pid
echo "$EXEC_PID" > logs/worker-execution.pid
echo "$DEFAULT_PID" > logs/worker-default.pid
echo "$FLOWER_PID" > logs/flower.pid

echo ""
echo "========================================="
echo "  全部服务已启动"
echo "  Flower 监控: http://localhost:5555"
echo ""
echo "  日志文件:"
echo "    logs/beat.log"
echo "    logs/worker-ai.log"
echo "    logs/worker-execution.log"
echo "    logs/worker-default.log"
echo "    logs/flower.log"
echo ""
echo "  停止: ./stop_all_workers.sh"
echo "========================================="
