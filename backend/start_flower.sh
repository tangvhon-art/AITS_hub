#!/bin/bash
# Flower 监控面板启动脚本
# 用法: ./start_flower.sh [port]

cd "$(dirname "$0")"
source venv/bin/activate

PORT=${1:-5555}

echo "========================================="
echo "  AITS Celery Flower 监控面板"
echo "  端口: $PORT"
echo "  访问: http://localhost:$PORT"
echo "========================================="
echo ""

# 检查 Redis 是否运行
if ! redis-cli ping > /dev/null 2>&1; then
    echo "警告: Redis 未运行，请先启动 Redis"
    echo ""
fi

exec env FLOWER_UNAUTHENTICATED_API=true \
    celery -A app.celery_app.celery_app flower \
    --port=$PORT \
    --conf=flowerconfig.py \
    --auto_refresh=true \
    --debug=false
