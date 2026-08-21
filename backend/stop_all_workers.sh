#!/bin/bash
# 停止所有 Worker + Beat + Flower
# 用法: ./stop_all_workers.sh

cd "$(dirname "$0")"

echo "========================================="
echo "  停止 AITS 全部 Worker 服务"
echo "========================================="
echo ""

# 停止 PID 文件中的进程
for pid_file in logs/flower.pid logs/worker-default.pid logs/worker-execution.pid logs/worker-ai.pid logs/beat.pid; do
    if [ -f "$pid_file" ]; then
        PID=$(cat "$pid_file")
        if kill -0 "$PID" 2>/dev/null; then
            echo "停止 $pid_file (PID: $PID)..."
            kill "$PID"
            sleep 1
            # 强制终止
            if kill -0 "$PID" 2>/dev/null; then
                kill -9 "$PID"
            fi
        fi
        rm -f "$pid_file"
    fi
done

# 兜底：杀所有 celery 进程
if pgrep -f "celery -A app.celery_app" > /dev/null 2>&1; then
    echo "清理剩余 celery 进程..."
    pkill -f "celery -A app.celery_app"
    sleep 1
    pkill -9 -f "celery -A app.celery_app" 2>/dev/null
fi

echo ""
echo "所有服务已停止"
echo "========================================="
