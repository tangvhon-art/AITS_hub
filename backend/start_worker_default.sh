#!/bin/bash
# 后台任务 Worker 启动脚本
# 处理：页面知识聚合、上传文件清理、通知发送、定时任务
# 用法: ./start_worker_default.sh [concurrency]

cd "$(dirname "$0")"
source venv/bin/activate

CONCURRENCY=${1:-2}

echo "========================================="
echo "  AITS Default Worker 启动"
echo "  队列: default"
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
    --hostname=default-worker@%h \
    -Q default \
    --max-tasks-per-child=100 \
    --time-limit=600
