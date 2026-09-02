#!/bin/bash
# Celery Worker 启动脚本（兼容模式 - 消费所有队列）
# 生产环境建议使用按队列分离的 worker:
#   ./start_worker_ai.sh         - AI 生成类任务
#   ./start_worker_execution.sh  - 执行类任务
#   ./start_worker_eval.sh       - AI 测评类任务
#   ./start_worker_default.sh    - 后台轻量任务
#   ./start_all_workers.sh       - 一键启动全部
#
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
    -Q celery,ai,execution,eval,default \
    --max-tasks-per-child=100 \
    --time-limit=600
