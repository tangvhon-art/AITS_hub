FROM python:3.13-slim

WORKDIR /app

# 安装系统依赖（MySQL 客户端 + Playwright 浏览器依赖 + curl 用于健康检查）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    wget \
    gnupg \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Playwright 浏览器（chromium）
RUN playwright install chromium

# 复制项目代码
COPY . .

# 创建日志和上传目录
RUN mkdir -p /app/logs /app/uploads /app/data

EXPOSE 8000

# 默认启动后端服务，可通过 command 覆盖为 celery worker/beat/flower
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
