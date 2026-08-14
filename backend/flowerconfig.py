"""
Flower 监控面板配置
"""

# Broker 地址
broker_api = "redis://localhost:6379/0"

# 调试模式
debug = False

# 自动刷新
auto_refresh = True

# URL 前缀
url_prefix = "flower"

# 任务刷新间隔（毫秒）
tasks_refresh_interval = 2000
worker_refresh_interval = 5000

# 认证（开发环境关闭，生产环境建议开启）
# basic_auth = ["admin:your-password"]

# 允许的来源（CORS）
# Flower 默认允许所有来源访问 API
