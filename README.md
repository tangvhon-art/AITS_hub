# AITS 智能测试管理平台

基于 LangChain + Agent 的下一代智能测试管理平台，覆盖测试全流程：**需求解析 → 用例生成 → 用例评审与优化 → UI 自动化执行 → 接口自动化测试 → 性能测试 → 测试计划编排 → 缺陷分析 → 报告生成 → 质量看板 → 事件通知**。

## 功能模块

### 项目与需求

| 模块 | 功能说明 |
|------|---------|
| 项目管理 | 创建/编辑/删除项目，数据按项目隔离，卡片式列表分页 |
| 版本管理 | 版本生命周期管理（draft → active → released → archived） |
| 需求管理 | 手动创建 + 文档上传（Word/PDF/TXT/MD）+ AI 功能点拆分（按模块分组）+ 用户勾选功能点后 AI 自主生成用例 + 变更传导 + 一键同步知识库 |

### 用例与评审

| 模块 | 功能说明 |
|------|---------|
| 用例管理 | CRUD + AI 生成 + 关联需求筛选 + 批量操作，用例与需求/模块强关联 |
| 用例评审 | 多选需求/模块自动查询关联用例，7 维度 AI 评审（覆盖度/完整性/场景/可执行性/规范性/冗余性/数据合理），分组评价 + 遗漏场景 + 改进建议，基于评审报告一键优化/补充用例 |

### UI 自动化

| 模块 | 功能说明 |
|------|---------|
| UI 自动化执行 | Playwright + Agent 驱动，SSE 实时日志流、截图记录、AI 自动修复，执行中页面知识采集 |
| 自动化脚本库 | 脚本管理 + 单步执行，自动保存执行成功的脚本，版本追溯 + AI 自动修复，自愈开关/自愈次数统计 |
| 自动化编排 | 套件管理 + 批量执行，多脚本/用例顺序执行，支持重试、AI 自动修复、无头模式 |
| 自愈能力 | 元素定位失败时 L1 同属性回退/L2 AI 推理/L3 视觉坐标三级自愈，L1 自动回写脚本，L2/L3 人工确认，自愈记录管理 + 前后截图对比 |
| 页面知识 | 执行中自动采集页面元素特征，聚合为页面画像和元素指纹库，辅助自愈定位，支持手动触发聚合 |

### 接口测试

| 模块 | 功能说明 |
|------|---------|
| 接口管理 | 目录树管理（树形分组），AI 生成接口文档（异步，支持补充信息），接口状态中文枚举，可编辑状态 |
| 接口调试 | Postman 风格工作台，Pre-request/Tests JS 脚本（AI 生成），Mock 数据，保存历史，环境变量 `{{var}}` 替换 |
| 接口用例 | 关联接口自动获取 URL，断言管理（9 种类型），AI 多策略生成（正常/异常/边界/全面），批量执行选择环境 |
| 接口场景 | 6 种步骤类型（API/用例/脚本/等待/条件/循环），可视化变量提取与传递（`${var}` + JSONPath），条件分支/循环遍历 |
| 接口执行 | 按步骤展示请求/响应/断言结果与耗时 |
| Mock 服务 | 按请求匹配返回 Mock 数据，13 种 `{{$function()}}` 动态数据生成 |
| 接口导入 | Postman / Swagger / JMeter / HAR / Apifox 五种格式 |
| 环境变量 | 多环境管理 + 变量配置，4 级变量优先级（用例 > 场景 > 环境 > 全局） |

### 性能测试

| 模块 | 功能说明 |
|------|---------|
| 性能测试 | 基于 Locust，支持多接口混合压测，Spawn rate 配置，JMeter 风格聚合报告 |
| 执行详情 | 4 张趋势图（运行趋势/QPS/响应时间 P50/P95/P99/虚拟用户数），性能指标汇总 |
| AI 性能分析 | 异步生成性能分析报告（整体评估/聚合分析/趋势分析/瓶颈识别/根因优化/风险提示），写入测试报告 |

### 测试质量

| 模块 | 功能说明 |
|------|---------|
| 测试计划 | 接口用例与 UI 场景混合编排，Celery 异步执行，自动生成测试报告 |
| 缺陷管理 | 缺陷全生命周期，状态流转、严重程度/根因分类、版本关联、执行失败自动创建 |
| 测试报告 | AI 生成 + 版本关联 + 多源聚合，Markdown 渲染，HTML/JUnit 导出，性能报告独立展示 |
| 质量看板 | 核心指标 + 趋势图表 + 风险预警，UI 与接口数据统一聚合，AI 洞察 |
| 覆盖率分析 | API 覆盖率统计，已测/未测接口分析，覆盖率趋势，支持排除配置 |

### 知识库与智能助手

| 模块 | 功能说明 |
|------|---------|
| 知识库 | RAG 向量检索（FAISS + Sentence-Transformer），文档管理 + 知识内容列表页，需求一键同步 |
| 智能助手 | 沉浸式问答界面，SSE 流式对话，支持 Function Calling / MCP / Skill 三种工具调用，执行进度实时展示，对话历史记录，模型能力检测与降级提醒，支持不选项目通用问答 |
| MCP 管理 | MCP 连接器管理，支持 SSE 类型，JSON 配置导入，工具发现与状态监控 |
| Skill 管理 | Skill 包导入（ZIP + SKILL.md 规范），多级目录文件存储，文件浏览器查看，导出，匹配测试 |

### 系统管理

| 模块 | 功能说明 |
|------|---------|
| 模型配置 | 多 LLM 接入（DeepSeek/Claude/vLLM/Ollama），能力检测（Function Calling/MCP/Skill），自动降级，按 Agent 类型路由 |
| Prompt 管理 | System Prompt 模板库，按场景分类，支持设为默认模板 |
| 事件通知 | 飞书/钉钉机器人通知，18 种事件触发，19 种卡片模板，HMAC-SHA256 验签，异步发送+重试 |
| 任务监控 | Celery + Flower 监控面板，Worker 节点状态、任务执行记录、成功/失败统计 |
| 数据池 | 测试数据管理，数据工厂生成，支持环境变量覆盖 |
| 审计日志 | 操作审计追踪 |
| 数据导入导出 | Excel 导入/导出用例，XMind 导图导出 |
| 团队协作 | 项目成员管理 + 权限控制，用户仅见参与的项目 |

## 快速开始

### 前置要求

- Python 3.13+
- Node.js 18+
- MySQL 8.0
- Redis 7

### 方式一：一键启动（推荐）

```bash
# 启动全部服务（前端 + 后端 + 3个队列Worker + Beat + Flower）
./start.sh
```

`start.sh` 会按顺序启动：后端（自动建表/迁移）→ 3个队列Worker（AI/Execution/Default + 就绪检测）→ Beat定时调度器 → Flower 监控 → 前端。脚本自动检测并安装依赖（Python venv / Node.js node_modules / Playwright Chromium）。

### 方式二：单独启动

```bash
# 仅启动后端
./start_backend.sh --port 8000

# 仅启动前端
./start_frontend.sh --port 5173

# 按队列单独启动 Worker
cd backend
./start_worker_ai.sh 2          # AI生成类任务（并发2）
./start_worker_execution.sh 4    # 执行类任务（并发4）
./start_worker_default.sh 2      # 后台轻量任务（并发2）

# 一键启动全部 Worker + Beat + Flower
cd backend && ./start_all_workers.sh
```

### 方式三：手动启动

```bash
# 1. 启动 Redis
redis-server --daemonize yes

# 2. 后端
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env   # 编辑数据库连接信息和 Redis 地址
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 3. Celery Worker（另一个终端）
cd backend && source venv/bin/activate
celery -A app.celery_app.celery_app worker --loglevel=info --concurrency=4 --events --heartbeat-interval=5

# 4. Beat 定时调度（另一个终端）
cd backend && source venv/bin/activate
celery -A app.celery_app.celery_app beat --loglevel=info

# 5. 前端
cd frontend
npm install
npm run dev
```

### 访问地址

| 服务 | 地址 |
|------|------|
| 前端页面 | http://localhost:5173 |
| 后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |
| Flower 监控 | http://localhost:5555/flower |
| 默认账号 | admin / admin123 |

> **注意**：启动前请确保 MySQL 和 Redis 已运行。后端启动时会自动创建数据表和新增字段。

## 常见问题

**Q: 后端新增字段后数据库报错 Unknown column？**
重启后端服务，main.py 启动时会自动执行 ALTER TABLE 添加缺失字段。

**Q: Celery 任务不执行？**
确保 Redis 已启动且 Celery Worker 正在运行。修改任务代码后必须重启对应队列的 Worker。

**Q: Playwright 浏览器安装失败？**
```bash
playwright install chromium
playwright install-deps chromium  # Linux
```

**Q: 智能助手提示"当前模型不支持工具调用"？**
在模型配置中点击「能力检测」确认模型支持 Function Calling。部分自部署模型虽然兼容 OpenAI 接口但不处理 tools 参数，需切换支持工具调用的模型。

**Q: 知识库向量检索不生效？**
确保文档已点击「生成切片」且状态为「就绪」。智能助手需选择项目并开启「知识库」开关。首次使用需下载 sentence-transformers 模型（约 470MB）。

**Q: 自愈不生效？**
确认：1) Celery Worker 已重启加载最新代码；2) 脚本的「自愈」开关已开启；3) 页面知识已采集（执行后自动采集）。

## 许可证

MIT License
