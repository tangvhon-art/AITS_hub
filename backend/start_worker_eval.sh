#!/bin/bash
# AI 测评任务 Worker 启动脚本
# 处理：AI 模型五维综合测评（AI裁判/Agent交互/业务落地/对抗红队/测评报告/问题台账）
# 全部测评任务统一路由到 eval 队列，独立 Worker 消费，便于按测评负载单独扩缩容
# 用法: ./start_worker_eval.sh [concurrency]

cd "$(dirname "$0")"
source venv/bin/activate

CONCURRENCY=${1:-2}

echo "========================================="
echo "  AITS AI 测评 Worker 启动"
echo "  队列: eval"
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
    --hostname=eval-worker@%h \
    -Q eval \
    --max-tasks-per-child=100 \
    --time-limit=600
