#!/bin/bash
# AI 任务 Worker 启动脚本
# 处理：用例生成/评审/优化、需求生成、API文档生成、报告生成、知识处理
# 用法: ./start_worker_ai.sh [concurrency]

cd "$(dirname "$0")"
source venv/bin/activate

CONCURRENCY=${1:-2}

echo "========================================="
echo "  AITS AI Worker 启动"
echo "  队列: ai"
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
    --hostname=ai-worker@%h \
    -Q ai \
    --max-tasks-per-child=100 \
    --time-limit=600
