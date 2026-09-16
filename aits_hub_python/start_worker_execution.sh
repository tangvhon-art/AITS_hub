#!/bin/bash
# 执行任务 Worker 启动脚本
# 处理：UI自动化执行、脚本执行、套件执行、性能测试、测试计划执行
# 用法: ./start_worker_execution.sh [concurrency]

cd "$(dirname "$0")"
source venv/bin/activate

CONCURRENCY=${1:-4}

echo "========================================="
echo "  AITS Execution Worker 启动"
echo "  队列: execution"
echo "  并发数: $CONCURRENCY"
echo "  Broker: Redis"
echo "========================================="
echo ""

# 检查 Redis 是否运行
if ! redis-cli ping > /dev/null 2>&1; then
    echo "警告: Redis 未运行，请先启动 Redis"
    echo "启动命令: redis-server"
    echo ""
fi

exec celery -A app.celery_app.celery_app worker \
    --loglevel=info \
    --concurrency=$CONCURRENCY \
    --hostname=execution-worker@%h \
    -Q execution \
    --max-tasks-per-child=100 \
    --time-limit=600
