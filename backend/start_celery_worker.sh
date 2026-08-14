#!/bin/bash
# Celery Worker 启动脚本
# 用法: ./start_celery_worker.sh [concurrency]

cd "$(dirname "$0")"
source venv/bin/activate

CONCURRENCY=${1:-4}

echo "========================================="
echo "  AITS Celery Worker 启动"
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
    --hostname=aits-worker@%h \
    -Q celery \
    --max-tasks-per-child=100 \
    --time-limit=600
