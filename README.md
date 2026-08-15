# AITS 智能测试管理平台

基于 LangChain + Agent 的下一代智能测试管理平台，覆盖测试全流程：**需求解析 → 用例生成 → UI 自动化执行 → 接口自动化测试 → 缺陷分析 → 报告生成 → 质量看板**。

## 功能概览

| 模块 | 功能 | 说明 |
|------|------|------|
| 项目管理 | 创建/编辑/删除项目 | 数据按项目隔离，支持多租户 |
| 版本管理 | 版本生命周期管理 | draft → active → released → archived |
| 需求管理 | 手动创建 + 文档上传 | 支持 Word/PDF/TXT/MD 格式自动解析 |
| 用例管理 | CRUD + AI 生成 + 批量操作 | 基于需求自动生成结构化测试用例（P0-P3） |
| 测试计划 | 计划编排 + 环境管理 + 调度 | 关联用例、支持手动/定时/一次性执行 |
| UI 自动化 | Playwright + Agent 驱动执行 | SSE 实时日志流、截图记录、步骤转指令 |
| 自动化脚本 | 脚本库管理 + 单步执行 | 自动保存执行成功的脚本，支持版本追溯与 AI 自动修复 |
| 自动化编排 | 套件管理 + 批量执行 | 编排多脚本/用例顺序执行，支持重试、AI 自动修复、无头模式切换 |
| 缺陷管理 | 缺陷全生命周期 | 状态流转、严重程度/根因分类、版本关联 |
| 测试报告 | AI 生成 + 版本关联 | 按版本聚合计划/需求/缺陷数据生成报告 |
| 质量看板 | 核心指标 + 趋势图表 + 风险预警 | 通过率/缺陷分布/模块覆盖率，支持版本筛选 |
| 知识库 | RAG 向量检索 | FAISS + Sentence-Transformer，辅助用例生成 |
| 模型配置 | 多 LLM 接入 + 自动降级 | DeepSeek / Claude / vLLM / Ollama 四种模式 |
| Agent 任务 | 异步任务监控 | 查看任务状态、日志、Token 消耗 |
| 审计日志 | 操作审计追踪 | 记录关键操作日志 |
| 数据导入导出 | 批量数据管理 | 导入/导出用例、缺陷等数据 |
| 智能助手 | AI 对话 + 工具调用 | SSE 流式对话，支持知识库检索、项目数据查询 |
| 接口管理 | 接口目录 + 接口定义 | 接口模块化管理、CRUD 维护 |
| 接口调试 | 在线调试 + 历史记录 | 发送请求调试，支持变量/脚本，保存调试历史 |
| 接口用例 | 用例 CRUD + AI 生成 | 断言管理，多策略 AI 生成（正常/异常/边界/全面） |
| 接口场景 | 场景编排 + 变量提取 | 6 种步骤类型（API/用例/脚本/等待/条件/循环） |
| Mock 服务 | Mock 期望 + 数据生成 | 按请求匹配返回 Mock 数据，支持 `{{$function()}}` 语法 |
| 接口导入 | 多格式导入 | Postman / Swagger / JMeter / HAR / Apifox 五种格式 |
| 环境变量 | 接口测试环境管理 | 环境级变量配置与引用 |

## 技术栈

```
前端  Vue 3.4 + TypeScript 5.5 + Ant Design Vue 4.x + Pinia + Vite 5 + ECharts 5.5
后端  FastAPI 0.115 + Python 3.13+ + SQLAlchemy 2.0 + Pydantic v2
数据  MySQL 8.0 + Redis 7（Celery 消息队列，必填）
异步  Celery 5.6 + Redis（异步任务队列，脚本/编排执行）
Agent LangChain 0.3 + LangGraph 0.3 + Playwright 1.49
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

**前置要求**: Python 3.13+ / Node.js 18+ / MySQL 8.0 / Redis 7

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

> Celery Worker 用于异步执行自动化脚本、自动化编排等任务，使用 Redis 作为消息队列。
> 不启动 Worker 会导致脚本执行、编排执行等异步任务无法处理。
> 修改 `suite_executor.py` 或 `script_tasks.py` 等任务代码后，必须重启 Celery Worker 才能生效。

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
│   │   │   ├── chat_agent.py         #   智能助手 Agent（SSE 流式对话）
│   │   │   ├── mcp_tools.py          #   Agent 工具集（项目数据查询等）
│   │   │   └── supervisor.py         #   Supervisor 多 Agent 编排
│   │   ├── api/                      # API 路由（27 个模块）
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
│   │   │   ├── llm_configs.py        #   LLM 模型配置
│   │   │   ├── chat.py               #   智能助手（SSE 流式对话）
│   │   │   ├── api_modules.py        #   接口目录管理
│   │   │   ├── api_definitions.py    #   接口定义管理
│   │   │   ├── api_debug.py          #   接口调试 + 历史记录
│   │   │   ├── api_cases.py          #   接口测试用例 + AI 生成
│   │   │   ├── api_scenarios.py      #   接口场景编排 + 变量提取
│   │   │   ├── api_executions.py     #   接口执行记录
│   │   │   ├── api_mock.py           #   Mock 服务
│   │   │   ├── api_import.py         #   接口多格式导入
│   │   │   └── mock_data.py          #   Mock 数据生成
│   │   ├── models/                   # SQLAlchemy 数据模型（34 张表）
│   │   │   └── api_test.py           #   接口测试模型（模块/定义/用例/场景/Mock 等 11 张表）
│   │   ├── schemas/                  # Pydantic 请求/响应模型
│   │   ├── core/                     # 核心模块（安全/依赖注入/异常处理/审计）
│   │   ├── services/                 # 业务服务（知识库 RAG + 接口测试引擎）
│   │   │   ├── http_client.py        #   HTTP 请求客户端
│   │   │   ├── variable_engine.py    #   变量引擎（环境/全局变量）
│   │   │   ├── assertion_engine.py   #   断言引擎
│   │   │   ├── script_engine.py      #   脚本引擎（前置/后置脚本）
│   │   │   ├── scenario_executor.py  #   接口场景执行引擎（6 种步骤类型）
│   │   │   ├── api_case_generator.py #   接口用例 AI 生成器（多策略）
│   │   │   ├── mock_data_generator.py#   Mock 数据生成器（{{$function()}} 语法）
│   │   │   └── importers/            #   接口导入解析器（Postman/Swagger/JMeter/HAR/Apifox）
│   │   ├── config.py                 # Pydantic Settings 配置
│   │   ├── database.py               # 数据库连接（SQLAlchemy Engine）
│   │   ├── celery_app.py             # Celery 实例配置
│   │   ├── tasks/                    # Celery 异步任务
│   │   │   └── script_tasks.py       #   脚本/编排执行任务
│   │   └── main.py                   # FastAPI 入口 + 路由注册
│   ├── alembic/                      # 数据库迁移脚本目录
│   ├── migrations/                   # 手动 SQL 迁移脚本
│   ├── start_celery_worker.sh        # Celery Worker 启动脚本
│   ├── requirements.txt              # Python 依赖
│   └── Dockerfile
├── frontend/                         # 前端应用
│   ├── src/
│   │   ├── views/                    # 页面组件（38 个 Vue 页面）
│   │   │   ├── Login.vue             #   登录/注册
│   │   │   ├── Layout.vue            #   主布局（侧边栏 + 多标签页）
│   │   │   ├── Dashboard.vue         #   智能助手（AI 对话）
│   │   │   ├── Projects.vue          #   项目管理
│   │   │   ├── Versions.vue          #   版本管理
│   │   │   ├── Requirements.vue      #   需求管理
│   │   │   ├── Cases.vue             #   用例管理
│   │   │   ├── TestPlans.vue         #   测试计划
│   │   │   ├── TestPlanEdit.vue      #   测试计划编排（用例/场景混合选择）
│   │   │   ├── TestPlanRun.vue       #   测试计划执行
│   │   │   ├── TestPlanReport.vue    #   测试计划报告
│   │   │   ├── Execution.vue         #   UI 自动化执行
│   │   │   ├── Scripts.vue           #   自动化脚本库
│   │   │   ├── AutomationSuites.vue  #   自动化编排
│   │   │   ├── SuiteRunDetail.vue    #   编排执行详情
│   │   │   ├── Defects.vue           #   缺陷管理
│   │   │   ├── Reports.vue           #   测试报告
│   │   │   ├── QualityDashboard.vue  #   质量看板
│   │   │   ├── Knowledge.vue         #   知识库
│   │   │   ├── AgentTasks.vue        #   Agent 任务监控
│   │   │   ├── TaskMonitor.vue       #   Celery 任务监控
│   │   │   ├── AuditLogs.vue         #   审计日志
│   │   │   ├── ImportExport.vue      #   数据导入导出
│   │   │   ├── LLMConfig.vue         #   LLM 模型配置
│   │   │   └── api-test/             #   接口自动化测试页面（14 个）
│   │   │       ├── ApiTestLayout.vue #     接口测试布局
│   │   │       ├── ApiDefinitions.vue / ApiDefinitionEdit.vue   #   接口管理
│   │   │       ├── ApiDebug.vue      #     接口调试
│   │   │       ├── ApiCases.vue / ApiCaseEdit.vue / AiGenerateCasesModal.vue  #   接口用例 + AI 生成
│   │   │       ├── ApiScenarios.vue / ApiScenarioEdit.vue       #   场景编排
│   │   │       ├── ApiExecutions.vue / ApiExecutionDetail.vue   #   执行记录
│   │   │       ├── ApiMock.vue / MockDataInserter.vue           #   Mock 服务
│   │   │       └── ApiEnvironments.vue #   环境变量
│   │   ├── api/                      # API 封装（18 个 TypeScript 模块）
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
- **脚本生成 Agent**：将用例步骤转换为可执行的 Playwright Python 脚本
- **报告生成 Agent**：按版本聚合测试计划、需求、缺陷数据，调用 LLM 生成分析报告
- **智能助手 Agent**：SSE 流式对话，支持知识库检索与项目数据查询（工具调用）
- **Supervisor 编排**：多 Agent 流水线协作（需求解析 → 用例生成 → 评审 → 执行）

### 版本管理

版本是项目的核心组织维度，贯穿整个测试流程：
- 需求、测试计划、缺陷均可关联版本
- 测试报告**必须选择版本**后生成，按版本聚合数据
- 质量看板支持按版本筛选数据查看

### 测试计划

支持计划编排、环境管理与执行调度：
- 计划节点支持**用例与场景混合编排**（UI 用例 / 接口场景），可批量勾选添加
- 关联接口测试用例与场景编排，支持手动 / 定时 / 一次性执行
- 执行结果按节点展示，支持生成计划报告

### 质量看板

提供项目级质量数据可视化：
- **核心指标**: 用例总数、执行次数、通过率、缺陷数、缺陷密度、测试计划完成率
- **趋势图表**: 通过率趋势、执行次数趋势、缺陷趋势（ECharts）
- **分布图表**: 缺陷严重程度分布、根因分类分布、模块通过率
- **风险预警**: 基于阈值自动生成高/中/低危预警
- **AI 洞察**: 调用 LLM 分析数据生成质量洞察建议
<img width="3018" height="1444" alt="image" src="https://github.com/user-attachments/assets/789fadf2-eb78-49aa-824c-b6bb11aefae0" />


### UI 自动化执行
<img width="2424" height="1436" alt="image" src="https://github.com/user-attachments/assets/5765aff9-f771-495f-9528-9f7ba22c24ef" />


```
用例步骤 → 转换为执行指令 → Playwright Agent 驱动浏览器
                ↓
        SSE 实时流推送日志 → 前端实时展示
                ↓
        执行结束 → 保存截图/日志/状态 → 更新用例执行记录
```

支持功能：
- 无头/可视化浏览器模式切换
- 执行失败时 AI 自动修复脚本并重试
- 执行日志持久化，支持历史记录查看
- 脚本自动版本升级
<img width="3000" height="1438" alt="image" src="https://github.com/user-attachments/assets/c0353459-8540-4bfb-9bb2-e2ca27c36745" />

### 自动化编排
<img width="3012" height="1378" alt="image" src="https://github.com/user-attachments/assets/1fd629be-b085-4d2d-b81c-6ecde42cb0fd" />


```
套件步骤1（脚本/用例/等待） → 步骤2 → ... → 步骤N
         ↓ 共享浏览器上下文
    顺序执行，支持失败继续/重试/AI修复
```

支持功能：
- 编排步骤添加、编辑、删除、排序
- 步骤类型：脚本 / 用例 / 等待
- 步骤级配置：失败后继续、最大重试次数、超时时间、AI 自动修复
- 套件级配置：无头模式开关
- 执行导航操作保留，方便直接路由到对应页面
- 执行结果按步骤展示，包含日志、错误信息、耗时

### 接口自动化测试

覆盖接口测试全流程：**接口管理 → 调试 → 用例 → 场景编排 → 执行 → Mock**：

```
接口定义 → 调试验证 → 用例/场景编排 → 批量执行 → 执行记录
                ↓
        Mock 服务 / 环境变量 / 断言引擎
```

支持功能：
- **接口管理**：接口目录（模块）与接口定义 CRUD，支持请求参数、请求头、响应体配置
- **接口调试**：在线发送请求调试，支持变量与脚本，保存调试历史
- **接口用例**：用例 CRUD + 断言管理，支持 AI 多策略生成（正常 / 异常 / 边界 / 全面）
- **场景编排**：6 种步骤类型（API / 用例 / 脚本 / 等待 / 条件 / 循环），支持变量提取与传递
- **执行记录**：批量执行与历史记录，按步骤展示请求、响应、断言结果与耗时
- **Mock 服务**：按请求匹配返回 Mock 数据，支持 `{{$function()}}` 语法生成随机数据
- **接口导入**：支持 Postman / Swagger / OpenAPI / JMeter / HAR / Apifox 五种格式导入
- **环境变量**：环境级变量配置与引用，贯穿调试、用例、场景执行

### 智能助手

AI 驱动的测试管理助手，支持 SSE 流式对话：
- 知识库检索增强回答（RAG）
- 工具调用查询项目数据（用例统计、项目统计等）
- 对话历史上下文保持

## API 概览

启动后访问 http://localhost:8000/docs 查看完整 Swagger 文档。



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

## 数据库迁移

项目未启用 Alembic 自动迁移，新增字段需手动执行 SQL 迁移脚本：

```bash
# 示例：执行自动化编排步骤 AI 修复开关迁移
mysql -h localhost -P 3306 -u root -p'your-password' AITS_hub < backend/migrations/add_suite_step_auto_fix.sql
```

新增模型字段后，如果数据库表已存在，需要对应创建 ALTER TABLE 迁移脚本并执行。

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
`create_all()` 只创建新表不会修改已有表。需手动执行 `backend/migrations/` 下的对应 SQL 迁移脚本，或重新建库。

**Q: Celery 任务报错 `NotRegistered`？**
Celery Worker 不会自动热加载代码。修改任务代码后，必须停止并重启 Worker：
```bash
ps aux | grep "celery.*worker" | grep -v grep | awk '{print $2}' | xargs kill -9
cd backend && ./start_celery_worker.sh 4
```

## 许可证

MIT License
