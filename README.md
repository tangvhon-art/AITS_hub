# AITS 智能测试管理平台

基于 LangChain + Agent 的下一代智能测试管理平台，覆盖测试全流程：**需求解析 → 用例生成 → UI 自动化执行 → 缺陷分析 → 报告生成 → 质量看板**。

## 功能概览

| 模块 | 功能 | 说明 |
|------|------|------|
| 项目管理 | 创建/编辑/删除项目 | 数据按项目隔离，支持多租户 |
| 版本管理 | 版本生命周期管理 | draft → active → released → archived |
| 需求管理 | 手动创建 + 文档上传 | 支持 Word/PDF/TXT/MD 格式自动解析 |
| 用例管理 | CRUD + AI 生成 + 批量操作 | 基于需求自动生成结构化测试用例（P0-P3） |
| 测试计划 | 计划编排 + 环境管理 + 调度 | 关联用例、支持手动/定时/一次性执行 |
| UI 自动化 | Playwright + Agent 驱动执行 | SSE 实时日志流、截图记录、步骤转指令 |
| 自动化编排 | 套件管理 + 批量执行 | 编排多脚本顺序执行，支持重试策略 |
| 自动化脚本 | 脚本库管理 | 自动保存执行成功的脚本，支持版本追溯 |
| 缺陷管理 | 缺陷全生命周期 | 状态流转、严重程度/根因分类、版本关联 |
| 测试报告 | AI 生成 + 版本关联 | 按版本聚合计划/需求/缺陷数据生成报告 |
| 质量看板 | 核心指标 + 趋势图表 + 风险预警 | 通过率/缺陷分布/模块覆盖率，支持版本筛选 |
| 知识库 | RAG 向量检索 | FAISS + Sentence-Transformer，辅助用例生成 |
| 模型配置 | 多 LLM 接入 + 自动降级 | DeepSeek / Claude / vLLM / Ollama 四种模式 |
| Agent 任务 | 异步任务监控 | 查看任务状态、日志、Token 消耗 |
| 审计日志 | 操作审计追踪 | 记录关键操作日志 |
| 数据导入导出 | 批量数据管理 | 导入/导出用例、缺陷等数据 |

## 技术栈

```
前端  Vue 3.4 + TypeScript 5.5 + Ant Design Vue 4.x + Pinia + Vite 5 + ECharts 5.5
后端  FastAPI 0.115 + Python 3.12+ + SQLAlchemy 2.0 + Pydantic v2
数据  MySQL 8.0 + Redis 7（Celery 消息队列）
异步  Celery 5.6 + Redis（异步任务队列，脚本生成等耗时任务）
Agent LangChain 0.3 + LangGraph 0.2 + Playwright 1.49
AI    DeepSeek / Claude / vLLM-TGI / Ollama（4 种接入模式，自动降级）
```

## 快速开始

### 方式一：一键启动脚本（推荐本地开发）

```bash
# 同时启动前后端
./start.sh

# 仅启动后端
./start_backend.sh --port 8000

# 仅启动前端
./start_frontend.sh --port 5173

# 前端构建生产版本
./start_frontend.sh --build
```

脚本自动检测并安装依赖（Python venv / Node.js node_modules / Playwright Chromium）。

> **注意**: 启动前请确保 Redis 已运行（`redis-server --daemonize yes`），Celery Worker 依赖 Redis 作为消息队列。

### 方式二：Docker Compose

```bash
cp .env.example .env    # 编辑填入数据库密码和 LLM API Key
docker-compose up -d
```

### 方式三：手动启动

**前置要求**: Python 3.12+ / Node.js 18+ / MySQL 8.0 / Redis 7

```bash
# ─── 1. 启动 Redis（如未运行）───
redis-server --daemonize yes

# ─── 2. 后端 ───
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env   # 编辑数据库连接信息和 Redis 地址
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# ─── 3. 启动 Celery Worker（另一个终端）───
cd backend
source venv/bin/activate
./start_celery_worker.sh 4  # 4个并发worker

# ─── 4. 前端 ───
cd frontend
npm install
npm run dev
```

> Celery Worker 用于异步执行自动化脚本生成等耗时任务，使用 Redis 作为消息队列。
> 不启动 Worker 会导致脚本执行等异步任务无法处理。

**访问地址**:
- 前端页面: http://localhost:5173
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/api/health

## 项目结构

```
AITS_hub/
├── backend/                          # 后端服务
│   ├── app/
│   │   ├── agents/                   # AI Agent 实现
│   │   │   ├── base_agent.py         #   Agent 基类
│   │   │   ├── llm_factory.py        #   LLM 统一抽象层（核心）
│   │   │   ├── model_router.py       #   模型路由与降级策略
│   │   │   ├── case_generator.py     #   用例生成 Agent
│   │   │   ├── case_reviewer.py      #   用例评审 Agent
│   │   │   ├── execution_agent.py    #   UI 执行 Agent（Playwright）
│   │   │   ├── suite_executor.py     #   套件批量执行 Agent
│   │   │   ├── script_generator.py   #   脚本生成 Agent
│   │   │   ├── bdd_generator.py      #   BDD Gherkin 生成 Agent
│   │   │   ├── defect_analyzer.py    #   缺陷分析 Agent
│   │   │   ├── report_generator.py   #   报告生成 Agent（版本聚合）
│   │   │   ├── notification_agent.py #   通知 Agent
│   │   │   └── supervisor.py         #   Supervisor 多 Agent 编排
│   │   ├── api/                      # API 路由（18 个模块）
│   │   │   ├── auth.py               #   用户认证（注册/登录/JWT）
│   │   │   ├── projects.py           #   项目管理
│   │   │   ├── project_versions.py   #   版本管理（CRUD）
│   │   │   ├── requirements.py       #   需求管理 + 文档上传
│   │   │   ├── cases.py              #   用例管理 + AI 生成
│   │   │   ├── test_plans.py         #   测试计划 + 环境管理
│   │   │   ├── execution.py          #   UI 自动化执行（SSE 流）
│   │   │   ├── defects.py            #   缺陷管理
│   │   │   ├── reports.py            #   测试报告 + AI 生成
│   │   │   ├── quality.py            #   质量看板（指标/趋势/预警）
│   │   │   ├── knowledge.py          #   知识库（RAG 向量检索）
│   │   │   ├── agent_tasks.py        #   Agent 任务 + Supervisor
│   │   │   ├── audit_logs.py         #   审计日志
│   │   │   ├── import_export.py      #   数据导入导出
│   │   │   ├── automation_scripts.py #   自动化脚本库
│   │   │   ├── automation_suites.py  #   自动化编排套件
│   │   │   └── llm_configs.py        #   LLM 模型配置
│   │   ├── models/                   # SQLAlchemy 数据模型（16 张表）
│   │   ├── schemas/                  # Pydantic 请求/响应模型
│   │   ├── core/                     # 核心模块（安全/依赖注入/异常处理）
│   │   ├── services/                 # 业务服务（知识库 RAG）
│   │   ├── config.py                 # Pydantic Settings 配置
│   │   ├── database.py               # 数据库连接（SQLAlchemy Engine）
│   │   ├── celery_app.py             # Celery 实例配置
│   │   ├── tasks/                    # Celery 异步任务
│   │   │   └── script_tasks.py       #   脚本执行任务
│   │   └── main.py                   # FastAPI 入口 + 路由注册
│   ├── alembic/                      # 数据库迁移脚本
│   ├── start_celery_worker.sh        # Celery Worker 启动脚本
│   ├── requirements.txt              # Python 依赖
│   └── Dockerfile
├── frontend/                         # 前端应用
│   ├── src/
│   │   ├── views/                    # 页面组件（19 个 Vue 页面）
│   │   │   ├── Login.vue             #   登录/注册
│   │   │   ├── Layout.vue            #   主布局（侧边栏 + 多标签页）
│   │   │   ├── Projects.vue          #   项目管理
│   │   │   ├── Versions.vue          #   版本管理
│   │   │   ├── Requirements.vue      #   需求管理
│   │   │   ├── Cases.vue             #   用例管理
│   │   │   ├── TestPlans.vue         #   测试计划
│   │   │   ├── Execution.vue         #   UI 自动化执行
│   │   │   ├── Scripts.vue           #   自动化脚本库
│   │   │   ├── AutomationSuites.vue  #   自动化编排
│   │   │   ├── SuiteRunDetail.vue    #   编排执行详情
│   │   │   ├── Defects.vue           #   缺陷管理
│   │   │   ├── Reports.vue           #   测试报告
│   │   │   ├── QualityDashboard.vue  #   质量看板
│   │   │   ├── Knowledge.vue         #   知识库
│   │   │   ├── AgentTasks.vue        #   Agent 任务监控
│   │   │   ├── AuditLogs.vue         #   审计日志
│   │   │   ├── ImportExport.vue      #   数据导入导出
│   │   │   └── LLMConfig.vue         #   LLM 模型配置
│   │   ├── api/                      # API 封装（17 个 TypeScript 模块）
│   │   ├── stores/user.ts            # Pinia 用户状态
│   │   ├── router/index.ts           # Vue Router 路由配置
│   │   ├── utils/date.ts             # 日期工具函数
│   │   └── main.ts                   # 应用入口
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── docker-compose.yml
├── start.sh / start_backend.sh / start_frontend.sh
└── .env.example
```

## 核心模块说明

### AI Agent 体系

```
用户请求 → API 层 → Agent 调度 → LLM 抽象层 → 大模型 API
                            ↓
                     Playwright（UI 自动化）
```

- **LLM 统一抽象层** (`llm_factory.py`)：封装 OpenAI/Claude/Ollama 等协议，统一调用接口
- **模型路由与降级** (`model_router.py`)：主模型失败时自动降级到备用模型（按 priority 排序，最多重试 2 次）
- **用例生成 Agent**：基于需求内容生成结构化测试用例，支持 P0-P3 优先级和步骤拆分
- **UI 执行 Agent**：驱动 Playwright 浏览器执行用例步骤，SSE 流式返回实时日志和截图
- **报告生成 Agent**：按版本聚合测试计划、需求、缺陷数据，调用 LLM 生成分析报告
- **Supervisor 编排**：多 Agent 流水线协作（需求解析 → 用例生成 → 评审 → 执行）

### 版本管理

版本是项目的核心组织维度，贯穿整个测试流程：
- 需求、测试计划、缺陷均可关联版本
- 测试报告**必须选择版本**后生成，按版本聚合数据
- 质量看板支持按版本筛选数据查看

### 质量看板

提供项目级质量数据可视化：
- **核心指标**: 用例总数、执行次数、通过率、缺陷数、缺陷密度、测试计划完成率
- **趋势图表**: 通过率趋势、执行次数趋势、缺陷趋势（ECharts）
- **分布图表**: 缺陷严重程度分布、根因分类分布、模块通过率
- **风险预警**: 基于阈值自动生成高/中/低危预警
- **AI 洞察**: 调用 LLM 分析数据生成质量洞察建议

### UI 自动化执行

```
用例步骤 → 转换为执行指令 → Playwright Agent 驱动浏览器
                ↓
        SSE 实时流推送日志 → 前端实时展示
                ↓
        执行结束 → 保存截图/日志/状态 → 更新用例执行记录
```

### 大模型配置

支持四种 LLM 接入模式，在平台「模型配置」页面管理：

| 模式 | Provider | 适用场景 |
|------|----------|----------|
| OpenAI 兼容协议 | `openai_compatible` | DeepSeek、vLLM、TGI、Doubao 等 |
| Anthropic Claude | `anthropic` | Claude 官方 API |
| 本地 Ollama | `ollama` | 本地运行的开源模型 |

支持测试连接、设为默认、流式开关、优先级排序和自动降级。

## 数据库设计

共 16 张表，启动时自动创建（`Base.metadata.create_all`）：

| 表名 | 说明 | 关键字段 |
|------|------|---------|
| `users` | 用户 | username, email, hashed_password, is_admin |
| `test_projects` | 项目 | name, description, owner_id |
| `project_versions` | 版本 | project_id, name, status, start_date, end_date |
| `test_requirements` | 需求 | project_id, **version_id**, title, content, source, status |
| `test_cases` | 测试用例 | project_id, req_id, title, module, priority, steps(JSON) |
| `test_plans` | 测试计划 | project_id, **version_id**, name, status, priority, case_ids |
| `test_plan_cases` | 计划-用例关联 | plan_id, case_id, sort_order, status |
| `test_environments` | 测试环境 | project_id, name, base_url, is_default |
| `test_runs` | 执行记录 | project_id, case_id, status, execution_log(JSON), screenshot_url |
| `defects` | 缺陷 | project_id, **version_id**, title, severity, status, root_cause |
| `test_reports` | 测试报告 | project_id, **version_id**, report_type, content, pass_rate |
| `agent_tasks` | Agent 任务 | agent_type, status, input_params, output_result, token_usage |
| `llm_configs` | LLM 配置 | provider, base_url, api_key(加密), model_name, priority |
| `knowledge_docs` | 知识库文档 | project_id, title, content, embedding |
| `audit_logs` | 审计日志 | user_id, action, resource_type, resource_id |
| `automation_scripts` | 自动化脚本 | project_id, name, script_type, content |
| `automation_suites` | 编排套件 | project_id, name, plan_id, steps(JSON) |
| `automation_suite_runs` | 套件执行记录 | suite_id, status, duration, results |

> 加粗字段 `version_id` 表示版本关联外键，nullable 设计向后兼容。

## API 概览

启动后访问 http://localhost:8000/docs 查看完整 Swagger 文档。

| 模块 | 路由前缀 | 主要端点 |
|------|----------|----------|
| 认证 | `/api/auth` | register, login, me |
| 项目 | `/api/projects` | CRUD |
| 版本 | `/api/projects/{id}/versions` | CRUD + status 筛选 |
| 需求 | `/api/projects/{id}/requirements` | CRUD + upload + generate |
| 用例 | `/api/projects/{id}/cases` | CRUD + batch + generate |
| 计划 | `/api/projects/{id}/plans` | CRUD + execute + cases |
| 环境 | `/api/projects/{id}/environments` | CRUD |
| 执行 | `/api/projects/{id}/execution` | run (SSE) + runs 历史 |
| 缺陷 | `/api/projects/{id}/defects` | CRUD + 状态流转 |
| 报告 | `/api/projects/{id}/reports` | list + **generate（必选版本）** |
| 质量 | `/api/projects/{id}/quality` | metrics + trend + dashboard + alerts + insight |
| 知识库 | `/api/projects/{id}/knowledge` | CRUD + search (RAG) |
| 脚本 | `/api/projects/{id}/scripts` | CRUD + execute |
| 套件 | `/api/projects/{id}/suites` | CRUD + execute + runs |
| Agent | `/api/agent-tasks` | list + detail + supervisor |
| LLM | `/api/llm-configs` | CRUD + test + set-default |
| 审计 | `/api/audit-logs` | list + detail |
| 导入导出 | `/api/projects/{id}/import-export` | import + export |

## 环境变量

### 后端 (`backend/.env`)

```env
APP_NAME=AITS 智能测试管理平台
APP_ENV=development
DEBUG=true
SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# 数据库（必填）
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your-password
DB_NAME=aits_platform

# Redis（必填，Celery 消息队列依赖）
REDIS_URL=redis://localhost:6379/0

# CORS
CORS_ORIGINS=http://localhost:5173

# 默认 LLM（可在界面修改）
DEFAULT_LLM_PROVIDER=openai_compatible
DEFAULT_LLM_BASE_URL=https://api.deepseek.com/v1
DEFAULT_LLM_API_KEY=
DEFAULT_LLM_MODEL=deepseek-chat

# 邮件通知（可选）
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=

# RabbitMQ（可选）
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
RABBITMQ_ENABLED=false
```

## 常见问题

**Q: 数据库密码含特殊字符连接失败？**
密码中的 `@`、`!`、`#` 等字符系统会自动 URL 编码，无需手动处理。

**Q: 自部署模型测试连接报错？**
使用 vLLM/TGI 等自部署模型时，建议关闭「流式输出」开关，部分模型的流式响应格式与标准 OpenAI 不完全兼容。

**Q: Playwright 浏览器安装失败？**
Linux 服务器需先安装系统依赖：
```bash
sudo apt-get install -y libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
  libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
  libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2
# 或使用 playwright 自带安装
playwright install-deps chromium
```

**Q: bcrypt 报错 `password cannot be longer than 72 bytes`？**
bcrypt 5.x 与 passlib 不兼容，项目已锁定 `bcrypt==4.0.1`，使用项目的 requirements.txt 安装即可。

**Q: 后端新增字段后数据库报错 `Unknown column`？**
`create_all()` 只创建新表不会修改已有表。需手动执行 ALTER TABLE 或重新建库。

## 许可证

MIT License
