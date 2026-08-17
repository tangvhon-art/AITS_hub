# AITS 智能测试管理平台

基于 LangChain + Agent 的下一代智能测试管理平台，覆盖测试全流程：**需求解析 → 用例生成 → UI 自动化执行 → 接口自动化测试 → 性能测试 → 测试计划编排 → 缺陷分析 → 报告生成 → 质量看板**。

## 功能概览

| 模块 | 功能 | 说明 |
|------|------|------|
| 项目管理 | 创建/编辑/删除项目 | 数据按项目隔离，支持多项目管理 |
| 版本管理 | 版本生命周期管理 | draft → active → released → archived |
| 需求管理 | 手动创建 + 文档上传 + 变更传导 | 支持 Word/PDF/TXT/MD 自动解析，需求变更标记关联用例 |
| 用例管理 | CRUD + AI 生成 + 批量操作 | 基于需求自动生成结构化测试用例（P0-P3），支持覆盖率统计 |
| 测试计划 | 混合编排 + 异步执行 + 完整报告 | 接口用例与 UI 场景混合编排，Celery 异步执行，自动生成测试报告 |
| UI 自动化 | Playwright + Agent 驱动执行 | SSE 实时日志流、截图记录、步骤转指令、AI 自动修复 |
| 自动化脚本 | 脚本库管理 + 单步执行 | 自动保存执行成功的脚本，支持版本追溯与 AI 自动修复 |
| 自动化编排 | 套件管理 + 批量执行 | 编排多脚本/用例顺序执行，支持重试、AI 自动修复、无头模式 |
| 接口管理 | 接口目录 + 接口定义 | 接口模块化管理、CRUD 维护、AI 生成接口文档 |
| 接口调试 | 在线调试 + 历史记录 | 发送请求调试，支持 Pre-request/Tests 脚本、Mock 数据、保存历史 |
| 接口用例 | 用例 CRUD + AI 生成 | 关联接口自动获取 URL，断言管理，多策略 AI 生成（正常/异常/边界/全面） |
| 接口场景 | 场景编排 + 变量提取 | 6 种步骤类型（API/用例/脚本/等待/条件/循环），可视化变量提取与传递 |
| 接口执行 | 批量执行 + 执行记录 | 按步骤展示请求、响应、断言结果与耗时 |
| Mock 服务 | Mock 期望 + 数据生成 | 按请求匹配返回 Mock 数据，支持 13 种 `{{$function()}}` 动态数据生成 |
| 接口导入 | 多格式导入 | Postman / Swagger / JMeter / HAR / Apifox 五种格式 |
| 环境变量 | 多环境管理 + 变量配置 | 环境级变量配置，贯穿调试、用例、场景执行，4 级变量优先级 |
| 性能测试 | Locust 压测 + 实时指标 | 基于接口/用例一键转换压测场景，支持并发用户、渐进加压、P50/P95/P99 |
| 数据池 | 测试数据管理 | 数据工厂生成测试数据，支持环境变量覆盖 |
| 覆盖率分析 | API 覆盖率统计 | 分析已测/未测接口，覆盖率趋势，支持排除配置 |
| 缺陷管理 | 缺陷全生命周期 | 状态流转、严重程度/根因分类、版本关联、执行失败自动创建 |
| 测试报告 | AI 生成 + 版本关联 + 多源聚合 | 按版本聚合 UI/接口/计划执行数据，支持 HTML/JUnit 导出 |
| 质量看板 | 核心指标 + 趋势图表 + 风险预警 | 通过率/缺陷分布/模块覆盖率，纳入接口测试数据，AI 洞察 |
| 知识库 | RAG 向量检索 | FAISS + Sentence-Transformer，辅助用例生成与 AI 回答 |
| 智能助手 | AI 对话 + 工具调用 | SSE 流式对话，18+ MCP 工具覆盖全模块数据查询 |
| 模型配置 | 多 LLM 接入 + 自动降级 | DeepSeek / Claude / vLLM / Ollama，按 Agent 类型路由模型 |
| Agent 任务 | 异步任务监控 | 查看任务状态、日志、Token 消耗 |
| 审计日志 | 操作审计追踪 | 记录关键操作日志 |
| 数据导入导出 | 批量数据管理 | 导入/导出用例、缺陷等数据 |

## 技术栈

```
前端  Vue 3.4 + TypeScript 5.5 + Ant Design Vue 4.x + Pinia + Vite 5 + ECharts 5.5
后端  FastAPI 0.115 + Python 3.13+ + SQLAlchemy 2.0 + Pydantic v2
数据  MySQL 8.0 + Redis 7（Celery 消息队列 + 缓存）
异步  Celery 5.6 + Redis（异步任务队列，脚本/编排/计划/性能测试执行）
Agent LangChain 0.3 + LangGraph 0.3 + Playwright 1.49
压测  Locust（性能测试执行引擎）
AI    DeepSeek / Claude / vLLM-TGI / Ollama（4 种接入模式，自动降级 + 模型路由）
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

# 启动 Celery Worker（异步任务必需）
cd backend && ./start_celery_worker.sh 4
```

脚本自动检测并安装依赖（Python venv / Node.js node_modules / Playwright Chromium）。

> **注意**: 启动前请确保 MySQL 和 Redis 已运行。后端启动时会自动创建数据表和新增字段。

### 方式二：手动启动

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
cd backend && source venv/bin/activate
./start_celery_worker.sh 4

# ─── 4. 前端 ───
cd frontend
npm install
npm run dev
```

**访问地址**:
- 前端页面: http://localhost:5173
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs
- 默认账号: admin / admin123

## 项目结构

```
AITS_hub/
├── backend/                          # 后端服务
│   ├── app/
│   │   ├── agents/                   # AI Agent 实现（15 个）
│   │   │   ├── base_agent.py         #   Agent 基类（LLM调用/日志/RAG/模型路由）
│   │   │   ├── llm_factory.py        #   LLM 统一抽象层
│   │   │   ├── model_router.py       #   模型路由与降级策略
│   │   │   ├── utils.py              #   Agent 公共工具（JSON解析等）
│   │   │   ├── case_generator.py     #   用例生成 Agent
│   │   │   ├── case_reviewer.py      #   用例评审 Agent
│   │   │   ├── execution_agent.py    #   UI 执行 Agent（Playwright）
│   │   │   ├── suite_executor.py     #   套件批量执行 Agent
│   │   │   ├── script_generator.py   #   脚本生成 Agent
│   │   │   ├── bdd_generator.py      #   BDD Gherkin 生成 Agent
│   │   │   ├── defect_analyzer.py    #   缺陷分析 Agent
│   │   │   ├── report_generator.py   #   报告生成 Agent
│   │   │   ├── notification_agent.py #   通知 Agent
│   │   │   ├── chat_agent.py         #   智能助手 Agent（SSE 流式对话）
│   │   │   ├── mcp_tools.py          #   Agent 工具集（18+ MCP 工具）
│   │   │   └── supervisor.py         #   Supervisor 多 Agent 编排
│   │   ├── api/                      # API 路由（30 个模块）
│   │   │   ├── auth.py               #   用户认证（注册/登录/JWT）
│   │   │   ├── projects.py           #   项目管理
│   │   │   ├── project_versions.py   #   版本管理
│   │   │   ├── requirements.py       #   需求管理 + 变更传导
│   │   │   ├── cases.py              #   用例管理 + AI 生成
│   │   │   ├── test_plans.py         #   测试计划（混合编排+异步执行+报告）
│   │   │   ├── execution.py          #   UI 自动化执行（SSE 流）
│   │   │   ├── automation_scripts.py #   自动化脚本库
│   │   │   ├── automation_suites.py  #   自动化编排套件
│   │   │   ├── defects.py            #   缺陷管理
│   │   │   ├── reports.py            #   测试报告
│   │   │   ├── quality.py            #   质量看板（UI+接口数据聚合）
│   │   │   ├── knowledge.py          #   知识库（RAG）
│   │   │   ├── agent_tasks.py        #   Agent 任务
│   │   │   ├── audit_logs.py         #   审计日志
│   │   │   ├── import_export.py      #   数据导入导出
│   │   │   ├── llm_configs.py        #   LLM 模型配置
│   │   │   ├── chat.py               #   智能助手（SSE）
│   │   │   ├── coverage.py           #   覆盖率分析
│   │   │   ├── data_pools.py         #   数据池管理
│   │   │   ├── env_variables.py      #   环境变量管理
│   │   │   ├── performance_tests.py  #   性能测试
│   │   │   ├── mock_data.py          #   Mock 数据生成
│   │   │   └── api-test/             #   接口测试模块（10 个路由文件）
│   │   │       ├── api_modules.py    #     接口目录
│   │   │       ├── api_definitions.py#     接口定义
│   │   │       ├── api_debug.py      #     接口调试
│   │   │       ├── api_cases.py      #     接口用例 + AI 生成
│   │   │       ├── api_scenarios.py  #     场景编排
│   │   │       ├── api_executions.py #     执行记录
│   │   │       ├── api_mock.py       #     Mock 服务
│   │   │       └── api_import.py     #     多格式导入
│   │   ├── models/                   # SQLAlchemy 数据模型（40 张表）
│   │   │   ├── api_test.py           #   接口测试（11 张表）
│   │   │   ├── test_plan.py          #   测试计划（4 张表）
│   │   │   ├── automation_suite.py   #   自动化编排（5 张表）
│   │   │   ├── performance_test.py   #   性能测试（2 张表）
│   │   │   ├── test_coverage.py      #   覆盖率（2 张表）
│   │   │   ├── test_data_pool.py     #   数据池（2 张表）
│   │   │   └── execution_base.py     #   执行记录公共基类
│   │   ├── schemas/                  # Pydantic 请求/响应模型
│   │   │   └── common.py             #   通用分页响应（泛型）
│   │   ├── core/                     # 核心模块
│   │   │   ├── security.py           #   密码哈希/JWT
│   │   │   ├── deps.py               #   依赖注入（统一权限校验）
│   │   │   ├── audit.py              #   审计日志（便捷封装）
│   │   │   ├── pagination.py         #   分页工具
│   │   │   ├── tasks.py              #   统一任务分发降级
│   │   │   ├── exceptions.py         #   业务异常
│   │   │   └── timezone.py           #   中国时区
│   │   ├── services/                 # 业务服务（15 个）
│   │   │   ├── http_client.py        #   HTTP 请求客户端（httpx）
│   │   │   ├── variable_engine.py    #   变量引擎（4 级作用域）
│   │   │   ├── assertion_engine.py   #   断言引擎（9 种类型）
│   │   │   ├── script_engine.py      #   JS 脚本引擎（前后置脚本）
│   │   │   ├── scenario_executor.py  #   接口场景执行引擎
│   │   │   ├── api_case_generator.py #   接口用例 AI 生成器
│   │   │   ├── mock_data_generator.py#   Mock 数据生成器（13 种函数）
│   │   │   ├── script_runner.py      #   脚本执行统一服务（AI修复重试）
│   │   │   ├── performance_runner.py #   Locust 性能测试执行器
│   │   │   ├── coverage_analyzer.py  #   覆盖率分析器
│   │   │   ├── data_factory.py       #   测试数据工厂
│   │   │   ├── environment_manager.py#   环境变量管理器
│   │   │   ├── defect_helper.py      #   缺陷自动创建
│   │   │   ├── knowledge_base.py     #   知识库 RAG
│   │   │   └── importers/            #   接口导入解析器（5 种格式）
│   │   ├── tasks/                    # Celery 异步任务（7 个）
│   │   │   ├── script_tasks.py       #   脚本/编排执行
│   │   │   ├── test_plan_tasks.py    #   测试计划异步执行
│   │   │   ├── api_case_tasks.py     #   AI 生成用例
│   │   │   ├── performance_tasks.py  #   性能测试执行
│   │   │   ├── report_tasks.py       #   报告生成
│   │   │   └── knowledge_tasks.py    #   知识库处理
│   │   ├── config.py                 # Pydantic Settings 配置
│   │   ├── database.py               # 数据库连接 + Mixin（SoftDelete/Timestamp）
│   │   ├── celery_app.py             # Celery 实例
│   │   └── main.py                   # FastAPI 入口（自动建表+迁移）
│   ├── start_celery_worker.sh
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                         # 前端应用
│   ├── src/
│   │   ├── views/                    # 页面组件
│   │   │   ├── Layout.vue            #   主布局（菜单从路由派生+多标签页）
│   │   │   ├── Login.vue             #   登录/注册
│   │   │   ├── Dashboard.vue         #   智能助手
│   │   │   ├── Projects.vue          #   项目管理
│   │   │   ├── Requirements.vue      #   需求管理
│   │   │   ├── Cases.vue             #   用例管理
│   │   │   ├── TestPlans.vue         #   测试计划列表
│   │   │   ├── TestPlanEdit.vue      #   计划编排（左右分栏节点编排）
│   │   │   ├── TestPlanRun.vue       #   计划执行进度
│   │   │   ├── TestPlanReport.vue    #   计划测试报告
│   │   │   ├── Scripts.vue           #   自动化脚本库
│   │   │   ├── AutomationSuites.vue  #   自动化编排
│   │   │   ├── Execution.vue         #   UI 自动化执行
│   │   │   ├── Defects.vue           #   缺陷管理
│   │   │   ├── Reports.vue           #   测试报告
│   │   │   ├── QualityDashboard.vue  #   质量看板
│   │   │   ├── Knowledge.vue         #   知识库
│   │   │   ├── performance/          #   性能测试页面
│   │   │   ├── data/                 #   数据池页面
│   │   │   └── api-test/             #   接口测试（14 个页面）
│   │   ├── components/               # 公共组件
│   │   │   ├── DataTable.vue         #   数据表格（分页+loading封装）
│   │   │   ├── PageHeader.vue        #   页头
│   │   │   ├── StatusTag.vue         #   状态标签
│   │   │   └── ConfirmDelete.vue     #   删除确认
│   │   ├── api/                      # API 封装（按资源拆分，30 个模块）
│   │   ├── stores/                   # Pinia 状态管理
│   │   │   ├── project.ts            #   项目全局状态
│   │   │   └── user.ts               #   用户状态
│   │   ├── composables/
│   │   │   └── useMenu.ts            #   路由派生菜单
│   │   ├── utils/
│   │   │   ├── date.ts               #   日期格式化
│   │   │   └── sse.ts                #   SSE 统一封装
│   │   ├── router/index.ts           # Vue Router（53 条路由）
│   │   └── main.ts
│   ├── package.json
│   └── vite.config.ts
├── docs/                             # 项目文档
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

- **LLM 统一抽象层**：封装 OpenAI/Claude/Ollama 等协议，统一调用接口
- **模型路由**：按 Agent 类型和数据敏感度路由模型，主模型失败自动降级
- **BaseAgent 基类**：所有 Agent 统一继承，复用 LLM 调用、日志、token 统计、RAG 检索
- **15 个专业 Agent**：用例生成、用例评审、UI 执行、脚本生成、缺陷分析、报告生成、智能助手等
- **Supervisor 编排**：多 Agent 流水线协作
- **MCP 工具集**：智能助手可调用 18+ 工具查询全模块数据

### 测试计划（混合编排 + 异步执行）

```
测试计划 → 节点编排（接口用例 + 接口场景 + UI脚本，混合排序）
    ↓ 点击执行
Celery 异步执行 → 逐节点执行 → 实时记录结果
    ↓ 完成
生成 TestReport + HTML/JUnit 报告
```

- 节点类型：接口用例、接口场景、UI 自动化脚本
- 节点配置：失败策略（停止/继续）、超时、重试次数
- 异步执行：Celery 任务，支持线程降级
- 执行进度：轮询实时状态
- 完整报告：概览统计 + 节点详情（请求/响应/断言）+ 导出

### 接口自动化测试

覆盖接口测试全流程：**接口管理 → 调试 → 用例 → 场景编排 → 执行 → Mock**

- **接口管理**：目录树管理，AI 生成接口文档
- **接口调试**：Postman 风格工作台，支持 Pre-request/Tests JS 脚本、Mock 数据插入
- **接口用例**：关联接口自动获取 URL，无需重复输入路径；AI 多策略生成用例
- **场景编排**：6 种步骤类型，可视化变量提取（`${var}` 语法），条件分支和循环遍历
- **Mock 服务**：按请求匹配返回，13 种动态数据函数（手机号/UUID/随机数/邮箱/身份证等）
- **环境变量**：4 级变量优先级（用例 > 场景 > 环境 > 全局）
- **5 种格式导入**：Postman / Swagger / JMeter / HAR / Apifox

### 性能测试

基于 Locust 的性能测试，可从接口定义/用例一键转换：
- 负载配置：并发用户数、每秒启动速率、持续时间、渐进加压
- 实时指标：RPS、平均/P50/P95/P99 响应时间、失败率
- 执行历史与统计对比

### UI 自动化执行

```
用例步骤 → 转换为执行指令 → Playwright Agent 驱动浏览器
                ↓
        SSE 实时流推送日志 → 前端实时展示
                ↓
        执行结束 → 保存截图/日志/状态 → 失败自动创建缺陷
```

- 无头/可视化浏览器模式切换
- 执行失败时 AI 自动修复脚本并重试
- 执行日志持久化，脚本自动版本升级

### 质量看板

提供项目级质量数据可视化，UI 自动化与接口测试数据统一聚合：
- **核心指标**：用例总数、执行次数、通过率、缺陷数、缺陷密度
- **趋势图表**：通过率趋势、执行次数趋势、缺陷趋势（ECharts）
- **风险预警**：基于阈值自动生成高/中/低危预警
- **AI 洞察**：调用 LLM 分析数据生成质量建议

## Mock 数据生成器

在接口调试、用例、场景的请求参数中使用 `{{$function()}}` 语法，执行时自动替换：

| 函数 | 说明 | 示例 |
|------|------|------|
| `{{$randomPhone}}` | 随机手机号 | 13812345678 |
| `{{$randomInt(1,100)}}` | 随机整数 | 42 |
| `{{$randomFloat(0,1)}}` | 随机浮点数 | 0.73 |
| `{{$randomString(8)}}` | 随机字符串 | a3Kx9mP2 |
| `{{$uuid}}` | UUID | a1b2c3d4-... |
| `{{$randomEmail}}` | 随机邮箱 | test_xxx@example.com |
| `{{$randomName}}` | 随机中文名 | 张三 |
| `{{$timestamp}}` | 当前时间戳 | 1700000000 |
| `{{$datetime}}` | 当前日期时间 | 2024-01-15 10:30:00 |
| `{{$randomBoolean}}` | 随机布尔值 | true |
| `{{$randomIP}}` | 随机IP | 192.168.1.100 |
| `{{$randomIdCard}}` | 随机身份证 | 110101199001011234 |
| `{{$randomDate(start,end)}}` | 随机日期 | 2024-06-15 |

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
DB_NAME=aits_hub

# Redis（必填，Celery 消息队列）
REDIS_URL=redis://localhost:6379/0

# CORS
CORS_ORIGINS=http://localhost:5173

# 默认 LLM（可在界面修改）
DEFAULT_LLM_PROVIDER=openai_compatible
DEFAULT_LLM_BASE_URL=https://api.deepseek.com/v1
DEFAULT_LLM_API_KEY=
DEFAULT_LLM_MODEL=deepseek-chat
```

## 数据库说明

- 后端启动时通过 `Base.metadata.create_all()` 自动创建新表
- 新增字段通过 main.py 中的轻量自动迁移逻辑（ALTER TABLE ADD COLUMN IF NOT EXISTS）
- 40 张数据表覆盖全部业务模块
- 所有表包含软删除字段（`is_deleted`/`deleted_at`）和时间戳

## 常见问题

**Q: 默认登录账号是什么？**
admin / admin123

**Q: 后端新增字段后数据库报错 Unknown column？**
重启后端服务，main.py 启动时会自动执行 ALTER TABLE 添加缺失字段。

**Q: Celery 任务不执行？**
确保 Redis 已启动且 Celery Worker 正在运行：`cd backend && ./start_celery_worker.sh 4`。修改任务代码后必须重启 Worker。

**Q: Playwright 浏览器安装失败？**
```bash
playwright install chromium
playwright install-deps chromium  # Linux
```

**Q: bcrypt 报错 password cannot be longer than 72 bytes？**
项目已锁定 `bcrypt==4.0.1`，使用 requirements.txt 安装即可。

**Q: 自部署模型测试连接报错？**
建议关闭「流式输出」开关，部分自部署模型的流式响应格式与标准 OpenAI 不完全兼容。

**Q: 接口测试执行时 URL 不正确？**
测试用例关联接口后自动使用接口的 URL，无需在用例中输入路径。请确保环境变量中配置了正确的 base_url。

## 许可证

MIT License
