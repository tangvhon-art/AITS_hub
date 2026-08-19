# AITS 智能测试管理平台

基于 LangChain + Agent 的下一代智能测试管理平台，覆盖测试全流程：**需求解析 → 用例生成 → 用例评审与优化 → UI 自动化执行 → 接口自动化测试 → 性能测试 → 测试计划编排 → 缺陷分析 → 报告生成 → 质量看板 → 事件通知**。

## 功能概览

| 模块 | 功能 | 说明 |
|------|------|------|
| 项目管理 | 创建/编辑/删除项目 | 数据按项目隔离，支持多项目管理，卡片式列表分页 |
| 版本管理 | 版本生命周期管理 | draft → active → released → archived |
| 需求管理 | 手动创建 + 文档上传 + 功能点拆分 + 变更传导 + 同步知识库 | 支持 Word/PDF/TXT/MD 自动解析，AI 异步拆分功能点（按模块分组），用户勾选功能点后 AI 自主生成用例，需求变更标记关联用例，一键同步到知识库向量检索 |
| 用例管理 | CRUD + AI 生成 + 关联需求筛选 + 批量操作 | 基于需求功能点自动生成结构化测试用例（P0-P3），支持按关联需求下拉筛选，用例与需求/模块强关联，覆盖率统计 |
| 用例评审 | 多选需求/模块 + AI 评审 + 优化补充 + 评审范围查看 | 支持多选需求和模块自动查询关联用例，7 维度评审（需求覆盖度/完整性/场景覆盖/可执行性/规范性/冗余性/数据合理），分组评价+遗漏场景，基于评审报告一键优化/补充用例，评审范围弹窗支持查询翻页 |
| 测试计划 | 混合编排 + 异步执行 + 完整报告 | 接口用例与 UI 场景混合编排，Celery 异步执行，自动生成测试报告 |
| UI 自动化 | Playwright + Agent 驱动执行 | SSE 实时日志流、截图记录、步骤转指令、AI 自动修复 |
| 自动化脚本 | 脚本库管理 + 单步执行 | 自动保存执行成功的脚本，支持版本追溯与 AI 自动修复，脚本列表分页 |
| 自动化编排 | 套件管理 + 批量执行 | 编排多脚本/用例顺序执行，支持重试、AI 自动修复、无头模式，套件列表分页 |
| 接口管理 | 接口目录 + 接口定义 | 接口模块化管理、CRUD 维护、AI 生成接口文档、树形分组 |
| 接口调试 | 在线调试 + 历史记录 | 发送请求调试，支持 Pre-request/Tests JS 脚本（AI 生成）、Mock 数据、保存历史 |
| 接口用例 | 用例 CRUD + AI 生成 | 关联接口自动获取 URL，断言管理（9 种类型），多策略 AI 生成（正常/异常/边界/全面） |
| 接口场景 | 场景编排 + 变量提取 | 6 种步骤类型（API/用例/脚本/等待/条件/循环），可视化变量提取与传递，条件分支/循环遍历 |
| 接口执行 | 批量执行 + 执行记录 | 按步骤展示请求、响应、断言结果与耗时 |
| Mock 服务 | Mock 期望 + 数据生成 | 按请求匹配返回 Mock 数据，支持 13 种 `{{$function()}}` 动态数据生成 |
| 接口导入 | 多格式导入 | Postman / Swagger / JMeter / HAR / Apifox 五种格式 |
| 环境变量 | 多环境管理 + 变量配置 | 环境级变量配置，贯穿调试、用例、场景执行，4 级变量优先级 |
| 性能测试 | Locust 压测 + 多接口 + 聚合报告 + AI 分析 | 支持多接口混合压测，JMeter 风格聚合报告，响应时间趋势图，异步 AI 性能分析生成性能报告 |
| 数据池 | 测试数据管理 | 数据工厂生成测试数据，支持环境变量覆盖 |
| 覆盖率分析 | API 覆盖率统计 | 分析已测/未测接口，覆盖率趋势，支持排除配置 |
| 缺陷管理 | 缺陷全生命周期 | 状态流转、严重程度/根因分类、版本关联、执行失败自动创建 |
| 测试报告 | AI 生成 + 版本关联 + 多源聚合 | 按版本聚合 UI/接口/计划执行数据，支持 Markdown 渲染、HTML/JUnit 导出，性能报告独立展示性能指标 |
| 质量看板 | 核心指标 + 趋势图表 + 风险预警 | 通过率/缺陷分布/模块覆盖率，纳入接口测试数据，AI 洞察 |
| 知识库 | RAG 向量检索 + 内容管理 + 需求同步 | FAISS + Sentence-Transformer，文档管理 + 知识内容（切片）列表页，需求一键同步，辅助用例生成与 AI 回答 |
| 智能助手 | AI 对话 + 工具调用 + 知识库引用 | 沉浸式问答界面，SSE 流式对话，支持 Function Calling / MCP / Skill 三种工具调用方式，执行进度实时展示，模型能力检测与降级提醒 |
| MCP 管理 | MCP 连接器管理 | 支持 SSE 类型 MCP 服务器连接，JSON 配置导入，工具发现与状态监控 |
| Skill 管理 | Skill 包导入与管理 | 支持 ZIP 包导入（SKILL.md 规范），多级目录文件存储，文件浏览器查看，导出，匹配测试 |
| 事件通知 | 飞书/钉钉机器人 + 多事件触发 | 全局公共模块，18 种事件（测试执行/AI任务/缺陷协作/数据处理），19 种卡片模板，HMAC-SHA256 验签，异步发送+重试 |
| Prompt 管理 | System Prompt 模板库 | 按场景分类管理（用例生成/评审/接口文档/性能分析等），支持设为默认模板，各 AI 功能可选择模板 |
| 模型配置 | 多 LLM 接入 + 能力检测 + 自动降级 | DeepSeek / Claude / vLLM / Ollama，支持 Function Calling / MCP / Skill 能力检测，按 Agent 类型路由模型 |
| 任务监控 | Celery + Flower 监控面板 | Worker 节点状态、任务执行记录、成功/失败统计，Flower 实时监控 |
| 审计日志 | 操作审计追踪 | 记录关键操作日志 |
| 数据导入导出 | 批量数据管理 | 导入/导出用例、缺陷等数据 |

## 技术栈

```
前端  Vue 3.4 + TypeScript 5.5 + Ant Design Vue 4.x + Pinia + Vite 5 + ECharts 5.5 + marked
后端  FastAPI 0.115 + Python 3.13+ + SQLAlchemy 2.0 + Pydantic v2
数据  MySQL 8.0 + Redis 7（Celery 消息队列 + 缓存）
异步  Celery 5.6 + Flower 2.0（异步任务队列 + 实时监控，脚本/编排/计划/性能测试/通知执行）
Agent LangChain 0.3 + LangGraph 0.3 + Playwright 1.49
向量  FAISS + sentence-transformers（知识库 RAG 向量检索）
压测  Locust（性能测试执行引擎，多接口混合压测）
MCP   MCP Python SDK（SSE 连接器，工具发现与调用）
通知  飞书/钉钉机器人 Webhook（HMAC-SHA256 验签，actionCard 卡片）
AI    DeepSeek / Claude / vLLM-TGI / Ollama（4 种接入模式，自动降级 + 模型路由 + 能力检测）
```

## 快速开始

### 方式一：一键启动脚本（推荐本地开发）

```bash
# 同时启动后端 + 前端 + Celery Worker + Flower（全部服务）
./start.sh

# 仅启动后端
./start_backend.sh --port 8000

# 仅启动前端
./start_frontend.sh --port 5173

# 仅启动 Celery Worker（4 并发）
cd backend && ./start_celery_worker.sh 4
```

`start.sh` 会按顺序启动：后端（自动建表/迁移）→ Celery Worker（就绪检测）→ Flower 监控 → 前端。脚本自动检测并安装依赖（Python venv / Node.js node_modules / Playwright Chromium）。

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

# ─── 3. 启动 Celery Worker + Flower（另一个终端）───
cd backend && source venv/bin/activate
celery -A app.celery_app.celery_app worker --loglevel=info --concurrency=4 --events --heartbeat-interval=5
FLOWER_UNAUTHENTICATED_API=true celery -A app.celery_app.celery_app flower --port=5555 --conf=flowerconfig.py

# ─── 4. 前端 ───
cd frontend
npm install
npm run dev
```

**访问地址**:
- 前端页面: http://localhost:5173
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs
- Flower 监控: http://localhost:5555/flower
- 默认账号: admin / admin123

## 项目结构

```
AITS_hub/
├── backend/                          # 后端服务
│   ├── app/
│   │   ├── agents/                   # AI Agent 实现（17 个业务 Agent + 5 个基础设施）
│   │   │   ├── base_agent.py         #   Agent 基类（LLM调用/日志/RAG/模型路由/知识库检索）
│   │   │   ├── llm_factory.py        #   LLM 统一抽象层
│   │   │   ├── model_router.py       #   模型路由与降级策略
│   │   │   ├── utils.py              #   Agent 公共工具（JSON解析等）
│   │   │   ├── case_generator.py     #   用例生成 Agent
│   │   │   ├── case_reviewer.py      #   用例评审 Agent（SYSTEM/HUMAN分离+JSON重试）
│   │   │   ├── feature_splitter.py   #   需求功能点拆分 Agent
│   │   │   ├── api_doc_generator.py  #   接口文档生成 Agent
│   │   │   ├── execution_agent.py    #   UI 执行 Agent（Playwright）
│   │   │   ├── suite_executor.py     #   套件批量执行 Agent
│   │   │   ├── script_generator.py   #   脚本生成 Agent
│   │   │   ├── bdd_generator.py      #   BDD Gherkin 生成 Agent
│   │   │   ├── defect_analyzer.py    #   缺陷分析 Agent
│   │   │   ├── report_generator.py   #   报告生成 Agent
│   │   │   ├── notification_agent.py #   通知 Agent
│   │   │   ├── chat_agent.py         #   智能助手 Agent（SSE 流式 + Function Calling + MCP + Skill）
│   │   │   ├── mcp_tools.py          #   Agent 工具集（18+ MCP 工具）
│   │   │   └── supervisor.py         #   Supervisor 多 Agent 编排
│   │   ├── api/                      # API 路由（36 个模块，271 个端点）
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
│   │   │   ├── knowledge.py          #   知识库（RAG + 切片列表 + 需求同步）
│   │   │   ├── notifications.py      #   事件通知（渠道/规则/记录）
│   │   │   ├── agent_tasks.py        #   Agent 任务 + 用例评审 + 评审优化
│   │   │   ├── audit_logs.py         #   审计日志
│   │   │   ├── import_export.py      #   数据导入导出
│   │   │   ├── llm_configs.py        #   LLM 模型配置 + 能力检测
│   │   │   ├── prompts.py            #   Prompt 模板管理
│   │   │   ├── chat.py               #   智能助手（SSE + 工具调用）
│   │   │   ├── mcp.py                #   MCP 连接器管理
│   │   │   ├── skills.py             #   Skill 包管理（导入/导出/匹配测试）
│   │   │   ├── coverage.py           #   覆盖率分析
│   │   │   ├── data_pools.py         #   数据池管理
│   │   │   ├── env_variables.py      #   环境变量管理
│   │   │   ├── performance_tests.py  #   性能测试（多接口+聚合报告+AI分析）
│   │   │   ├── mock_data.py          #   Mock 数据生成
│   │   │   └── api-test/             #   接口测试模块（8 个路由文件）
│   │   │       ├── api_modules.py    #     接口目录
│   │   │       ├── api_definitions.py#     接口定义
│   │   │       ├── api_debug.py      #     接口调试
│   │   │       ├── api_cases.py      #     接口用例 + AI 生成
│   │   │       ├── api_scenarios.py  #     场景编排
│   │   │       ├── api_executions.py #     执行记录
│   │   │       ├── api_mock.py       #     Mock 服务
│   │   │       └── api_import.py     #     多格式导入
│   │   ├── mcp/                      # MCP 模块
│   │   │   ├── client.py             #   MCP SSE 客户端（连接/握手/工具发现/调用）
│   │   │   └── server.py             #   MCP 服务端（内置工具暴露）
│   │   ├── models/                   # SQLAlchemy 数据模型（47 张表）
│   │   │   ├── api_test.py           #   接口测试（11 张表）
│   │   │   ├── test_plan.py          #   测试计划（4 张表）
│   │   │   ├── automation_suite.py   #   自动化编排（5 张表）
│   │   │   ├── performance_test.py   #   性能测试（2 张表，含多接口 targets/endpoint_stats）
│   │   │   ├── test_coverage.py      #   覆盖率（2 张表）
│   │   │   ├── test_data_pool.py     #   数据池（2 张表）
│   │   │   ├── knowledge_doc.py      #   知识库（文档+切片 2 张表）
│   │   │   ├── notification.py       #   事件通知（渠道/规则/记录 3 张表）
│   │   │   ├── mcp_connector.py      #   MCP 连接器
│   │   │   ├── skill.py              #   Skill 包（文件树/脚本/提示词）
│   │   │   ├── prompt.py             #   Prompt 模板
│   │   │   └── execution_base.py     #   执行记录公共基类
│   │   ├── schemas/                  # Pydantic 请求/响应模型
│   │   │   ├── common.py             #   通用分页响应（泛型）
│   │   │   ├── notification.py       #   通知模块 Schema
│   │   │   └── knowledge.py          #   知识库 Schema
│   │   ├── core/                     # 核心模块
│   │   │   ├── security.py           #   密码哈希/JWT
│   │   │   ├── deps.py               #   依赖注入（统一权限校验）
│   │   │   ├── audit.py              #   审计日志（便捷封装 + 装饰器）
│   │   │   ├── pagination.py         #   分页工具
│   │   │   ├── crud.py               #   CRUDBase 泛型基类
│   │   │   ├── query_builder.py      #   QueryBuilder 查询构建器
│   │   │   ├── task_base.py          #   BaseTask 任务基类
│   │   │   ├── file_handler.py       #   FileHandler 文件处理
│   │   │   ├── tasks.py              #   统一任务分发降级（Celery→线程）
│   │   │   ├── exceptions.py         #   业务异常
│   │   │   └── timezone.py           #   中国时区
│   │   ├── services/                 # 业务服务（15+ 个）
│   │   │   ├── http_client.py        #   HTTP 请求客户端（httpx）
│   │   │   ├── variable_engine.py    #   变量引擎（4 级作用域）
│   │   │   ├── assertion_engine.py   #   断言引擎（9 种类型）
│   │   │   ├── script_engine.py      #   JS 脚本引擎（前后置脚本）
│   │   │   ├── scenario_executor.py  #   接口场景执行引擎
│   │   │   ├── api_case_generator.py #   接口用例 AI 生成器
│   │   │   ├── mock_data_generator.py#   Mock 数据生成器（13 种函数）
│   │   │   ├── script_runner.py      #   脚本执行统一服务（AI修复重试）
│   │   │   ├── performance_runner.py #   Locust 性能测试执行器（多接口+聚合统计）
│   │   │   ├── coverage_analyzer.py  #   覆盖率分析器
│   │   │   ├── data_factory.py       #   测试数据工厂
│   │   │   ├── environment_manager.py#   环境变量管理器
│   │   │   ├── defect_helper.py      #   缺陷自动创建
│   │   │   ├── knowledge_base.py     #   知识库 RAG（FAISS 向量检索）
│   │   │   ├── feishu_bot.py         #   飞书机器人客户端（HMAC-SHA256 验签）
│   │   │   ├── dingtalk_bot.py       #   钉钉机器人客户端（加签验签，actionCard 卡片）
│   │   │   ├── dingtalk_card_builder.py # 钉钉卡片构建器（适配器，飞书卡片→钉钉格式）
│   │   │   ├── card_builder.py       #   通知卡片构建器（19 种模板）
│   │   │   ├── notification_service.py#  通知服务（规则匹配+异步派发）
│   │   │   ├── ai_creation_service.py#  AI 用例批量创建服务
│   │   │   └── importers/            #   接口导入解析器（5 种格式）
│   │   ├── tasks/                    # Celery 异步任务（18 个）
│   │   │   ├── script_tasks.py       #   脚本/编排执行
│   │   │   ├── test_plan_tasks.py    #   测试计划异步执行
│   │   │   ├── api_case_tasks.py     #   AI 生成用例
│   │   │   ├── case_tasks.py         #   需求功能点拆分 + 功能点驱动用例生成
│   │   │   ├── performance_tasks.py  #   性能测试执行 + AI 性能分析
│   │   │   ├── report_tasks.py       #   报告生成
│   │   │   ├── knowledge_tasks.py    #   知识库处理
│   │   │   ├── review_tasks.py       #   用例评审 + 评审优化用例
│   │   │   ├── requirement_tasks.py  #   AI 需求生成
│   │   │   ├── api_doc_tasks.py      #   AI 接口文档生成
│   │   │   └── notification_tasks.py #   通知异步发送（重试2次）
│   │   ├── config.py                 # Pydantic Settings 配置
│   │   ├── database.py               # 数据库连接 + Mixin（SoftDelete/Timestamp/ProjectScoped/CreatedBy）
│   │   ├── celery_app.py             # Celery 实例
│   │   ├── flowerconfig.py           # Flower 监控配置
│   │   └── main.py                   # FastAPI 入口（自动建表+迁移，271 路由）
│   ├── start_celery_worker.sh
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                         # 前端应用
│   ├── src/
│   │   ├── views/                    # 页面组件（51 个页面）
│   │   │   ├── Layout.vue            #   主布局（菜单从路由派生+多标签页）
│   │   │   ├── Login.vue             #   登录/注册
│   │   │   ├── Dashboard.vue         #   智能助手（沉浸式问答+工具调用进度+知识库引用）
│   │   │   ├── Projects.vue          #   项目管理（卡片分页）
│   │   │   ├── Requirements.vue      #   需求管理（同步知识库）
│   │   │   ├── Cases.vue             #   用例管理
│   │   │   ├── CaseReviews.vue       #   用例评审（评审报告+优化用例）
│   │   │   ├── TestPlans.vue         #   测试计划列表
│   │   │   ├── TestPlanEdit.vue      #   计划编排（左右分栏节点编排）
│   │   │   ├── TestPlanRun.vue       #   计划执行进度
│   │   │   ├── TestPlanReport.vue    #   计划测试报告
│   │   │   ├── Scripts.vue           #   自动化脚本库（列表+历史分页）
│   │   │   ├── AutomationSuites.vue  #   自动化编排（套件+历史分页）
│   │   │   ├── Execution.vue         #   UI 自动化执行（历史记录分页）
│   │   │   ├── Defects.vue           #   缺陷管理
│   │   │   ├── Reports.vue           #   测试报告（Markdown 渲染+性能报告独立指标）
│   │   │   ├── QualityDashboard.vue  #   质量看板
│   │   │   ├── Knowledge.vue         #   知识库（文档管理+知识内容Tab）
│   │   │   ├── LLMConfig.vue         #   模型配置（能力检测+分页）
│   │   │   ├── Prompts.vue           #   Prompt 模板管理
│   │   │   ├── McpConnectors.vue     #   MCP 连接器管理
│   │   │   ├── Skills.vue            #   Skill 管理（导入/导出/文件浏览/匹配测试）
│   │   │   ├── TaskMonitor.vue       #   任务监控（Flower Worker 状态）
│   │   │   ├── performance/          #   性能测试页面（多接口配置+聚合报告+AI分析）
│   │   │   ├── data/                 #   数据池页面
│   │   │   ├── notification/         #   事件通知（3 个页面）
│   │   │   │   ├── NotificationChannels.vue
│   │   │   │   ├── NotificationRules.vue
│   │   │   │   └── NotificationRecords.vue
│   │   │   └── api-test/             #   接口测试（14 个页面）
│   │   │       ├── ApiTestLayout.vue #     布局（子菜单收起展开）
│   │   │       ├── ApiDefinitions.vue#     接口管理（树形分组）
│   │   │       ├── ApiDefinitionEdit.vue
│   │   │       ├── ApiDebug.vue      #     接口调试
│   │   │       ├── ApiCases.vue      #     接口用例（执行环境选择）
│   │   │       ├── ApiCaseEdit.vue
│   │   │       ├── AiGenerateCasesModal.vue
│   │   │       ├── ApiScenarios.vue  #     场景编排
│   │   │       ├── ApiScenarioEdit.vue
│   │   │       ├── ApiExecutions.vue #     执行记录
│   │   │       ├── ApiExecutionDetail.vue
│   │   │       ├── ApiMock.vue       #     Mock 服务
│   │   │       ├── ApiEnvironments.vue#    环境变量
│   │   │       └── MockDataInserter.vue
│   │   ├── components/               # 公共组件
│   │   │   ├── DataTable.vue         #   数据表格（分页+loading封装）
│   │   │   ├── FormModal.vue         #   表单弹窗
│   │   │   ├── SearchBar.vue         #   搜索栏
│   │   │   ├── DetailDrawer.vue      #   详情抽屉
│   │   │   ├── PageHeader.vue        #   页头
│   │   │   ├── StatusTag.vue         #   状态标签
│   │   │   └── ConfirmDelete.vue     #   删除确认
│   │   ├── api/                      # API 封装（按资源拆分，40 个模块）
│   │   │   ├── base.ts               #   BaseAPI 泛型基类
│   │   │   ├── types.ts              #   共享类型定义
│   │   │   ├── knowledge.ts          #   知识库 API
│   │   │   ├── notifications.ts      #   通知 API
│   │   │   ├── caseReviews.ts        #   用例评审 API
│   │   │   ├── agentTasks.ts         #   Agent 任务 API
│   │   │   ├── mcp.ts                #   MCP 连接器 API
│   │   │   ├── skills.ts             #   Skill 管理 API
│   │   │   └── ...
│   │   ├── stores/                   # Pinia 状态管理
│   │   │   ├── project.ts            #   项目全局状态
│   │   │   └── user.ts               #   用户状态
│   │   ├── composables/
│   │   │   ├── useMenu.ts            #   路由派生菜单
│   │   │   ├── useList.ts            #   列表数据 composable（分页+搜索）
│   │   │   ├── useCRUD.ts            #   CRUD 操作 composable
│   │   │   └── useUrlSearch.ts       #   URL 参数同步
│   │   ├── utils/
│   │   │   ├── date.ts               #   日期格式化
│   │   │   ├── sse.ts                #   SSE 统一封装
│   │   │   ├── format.ts             #   格式化工具
│   │   │   ├── download.ts           #   下载工具
│   │   │   └── copy.ts               #   复制工具
│   │   ├── constants/index.ts        # 枚举常量
│   │   ├── router/index.ts           # Vue Router（60+ 条路由）
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
                            ↓               ↓
                     Playwright（UI）    MCP/Skill 工具调用
                            ↓               ↓
                     FAISS 向量检索    Function Calling 协议
```

- **LLM 统一抽象层**：封装 OpenAI/Claude/Ollama 等协议，统一调用接口
- **模型路由**：按 Agent 类型和数据敏感度路由模型，主模型失败自动降级
- **能力检测**：自动检测模型是否支持 Function Calling / MCP / Skill，不支持时降级普通问答并提示
- **BaseAgent 基类**：所有 Agent 统一继承，复用 LLM 调用、日志、token 统计、RAG 检索、知识库搜索
- **15 个专业 Agent**：用例生成、用例评审、UI 执行、脚本生成、缺陷分析、报告生成、智能助手等
- **Supervisor 编排**：多 Agent 流水线协作
- **MCP 工具集**：智能助手可调用 18+ 内置工具查询全模块数据，也可连接外部 MCP 服务器

### 智能助手（Function Calling / MCP / Skill）

智能助手支持三种工具调用方式，根据模型能力自动选择：

1. **Function Calling**：通过 OpenAI Chat Completions `tools` 参数传递工具定义，模型返回结构化 `tool_calls`，后端执行后回传结果
2. **MCP（Model Context Protocol）**：连接外部 MCP 服务器（SSE 协议），自动发现工具并调用
3. **Skill**：导入 Skill 包（ZIP + SKILL.md），匹配用户意图后加载 Skill 提示词和脚本执行

- **沉浸式问答界面**：隐藏快捷功能和常用提问，专注对话
- **执行进度展示**：意图识别中 → 调用工具 → 结果生成 → 问答整理，实时反馈
- **知识库引用**：开启知识库后展示引用来源文档和内容片段，默认收起可展开
- **降级提醒**：模型不支持工具调用时提示"已降级为普通问答，如需调用工具请切换其他模型"

### MCP 连接器管理

- 支持 SSE 类型 MCP 服务器连接
- JSON 配置导入（`{"mcpServers": {"name": {"type": "sse", "url": "..."}}}`）
- 自动握手发现工具列表
- 连接状态监控（已连接/错误/断开）
- 工具列表查看与测试

### Skill 管理

- **ZIP 包导入**：遵循业界 Skill 包规范，第一层为 Skill 名称文件夹，内含 `SKILL.md`（frontmatter: name/description）及其他资源文件
- **多级目录存储**：所有文件（.md/.py/.json 等）完整存入数据库，支持文件夹层级浏览
- **文件浏览器**：类似文件管理器的界面，文件夹/文件图标颜色区分，点击查看文件内容
- **导出**：将 Skill 重新打包为 ZIP 下载
- **匹配测试**：输入用户问题，测试 Skill 匹配效果
- **去重更新**：相同 package_hash 的 Skill 导入时自动更新而非重复创建

### 用例评审与优化

```
多选需求/模块 → 后端自动查询关联用例 → AI 7维度评审 → 评审报告（评分+分组评价+问题列表+遗漏场景+改进建议）
                                                          ↓
                                              点击「优化/补充用例」
                                                          ↓
                                    选择模式/模型/Prompt → AI 生成优化用例
                                                          ↓
                                    自动关联原需求和模块 → 批量入库
```

- **多选需求/模块**：新建评审时支持多选需求和模块，后端自动查询关联用例，无需手动选择
- **评审维度**：需求覆盖度、完整性、场景覆盖、可执行性、规范性、冗余性、数据合理性（7 维度）
- **分组评价**：按需求+模块分组给出覆盖度评价（完整/部分/不足）
- **遗漏场景**：AI 自动识别未覆盖的需求功能点
- **评审范围查看**：列表页点击评审范围弹窗查看完整分组列表，支持搜索和翻页
- **评分标准**：90+ 优秀，80-89 良好，70-79 合格，<70 不合格
- **优化模式**：优化问题用例 + 补充缺失用例 / 仅优化 / 仅补充
- **Prompt 模板**：可选择用例生成 Prompt 模板或自定义 System Prompt
- **自动关联**：生成的用例自动继承评审时选择的需求 ID 和模块
- **完成后隐藏按钮**：优化补充完成后按钮隐藏，提示"用例已优化，请前往用例管理检查或重新创建评审"
- **SYSTEM/HUMAN 分离**：评审 Prompt 采用结构规则与数据分离设计，低 temperature，JSON 输出失败自动重试格式化

### 需求功能点拆分

```
需求创建/上传/AI生成 → 异步触发功能点拆分 → AI 按模块分组拆分功能点
                                      ↓
                        用户勾选需要生成用例的功能点
                                      ↓
                AI 基于完整需求 + 选中功能点自主判断用例数量并生成
```

- **异步拆分**：需求创建后自动后台拆分功能点，不阻塞页面
- **模块分组**：功能点按模块分组展示，支持折叠/全选/反选
- **智能生成**：AI 基于需求详情和选中功能点，自主判断用例数量，按等价类/边界值/场景法等专业方法生成
- **状态追踪**：需求列表展示功能点拆分状态（未拆分/拆分中/已完成/失败），失败可重新拆分
- **用例关联**：生成的用例自动关联需求 ID 和功能点 ID

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

- **接口管理**：目录树管理（树形连接线、hover 操作按钮），AI 生成接口文档（异步处理，支持补充信息）
- **接口调试**：Postman 风格工作台，支持 Pre-request/Tests JS 脚本（AI 生成）、Mock 数据插入、保存为接口时自动去除域名
- **接口用例**：关联接口自动获取 URL，无需重复输入路径；请求配置（Headers/Query/Body）与接口定义一致；AI 多策略生成用例
- **场景编排**：6 种步骤类型，可视化变量提取（`${var}` 语法，支持 JSONPath），条件分支（true/false 跳转）和循环遍历（遍历参数列表）
- **Mock 服务**：按请求匹配返回，13 种动态数据函数（手机号/UUID/随机数/邮箱/身份证等）
- **环境变量**：4 级变量优先级（用例 > 场景 > 环境 > 全局），执行时弹窗选择环境，变量名支持连字符（如 `{{xp-authorization}}`），Mock 函数用 `$` 前缀区分（如 `{{$uuid()}}`）
- **5 种格式导入**：Postman / Swagger / JMeter / HAR / Apifox

### 性能测试（多接口 + 聚合报告 + AI 分析）

基于 Locust 的性能测试，支持多接口混合压测：

```
配置多接口目标（接口/用例/URL + 权重）→ Locust 分布式压测
    ↓
实时指标（RPS/响应时间/失败率）→ 统计趋势
    ↓
执行结果：JMeter 风格聚合报告 + 响应时间趋势图（多接口叠加）
    ↓
AI 性能分析（异步）→ 生成性能报告（写入 TestReport）
```

- **多接口执行**：一次压测可配置多个目标接口，每个接口可设置权重
- **JMeter 风格聚合报告**：Label/#Samples/Average/Min/Max/StdDev/Error%/Throughput/P50/P90/P95/P99
- **响应时间趋势**：聚合趋势 + 各接口独立趋势叠加图（ECharts）
- **AI 性能分析**：基于整体指标、聚合报告、趋势数据、错误汇总，生成 6 维度专业分析报告（整体评估/聚合分析/趋势分析/瓶颈识别/根因与优化/风险提示）
- **性能报告**：独立展示性能指标（总请求数/失败率/成功率/RPS/平均/P95），Markdown 渲染

### 知识库与 RAG

```
文档上传/需求同步 → 文本切分（500字符+50重叠）→ Sentence-Transformer 向量化
        ↓
    存入 MySQL（JSON 向量）→ 内存 FAISS 索引
        ↓
智能助手提问 → FAISS 相似度检索 Top-5 → 注入 System Prompt → LLM 基于知识库回答
```

- **文档管理**：手动创建 / 文件上传（md/txt/docx/pdf）/ 需求一键同步
- **知识内容页**：Tab 切换查看所有向量切片，支持关键词搜索、按文档筛选、分页、查看全文
- **需求同步**：需求管理页一键同步到知识库，自动创建文档并后台生成向量切片
- **智能助手集成**：开启知识库开关后，对话中展示引用的知识库来源文档和内容片段
- **向量模型**：paraphrase-multilingual-MiniLM-L12-v2（384 维，支持中英文）

### 事件通知

全局公共模块（不绑定特定项目），支持飞书/钉钉机器人通知：

- **通知渠道**：飞书机器人（Webhook + HMAC-SHA256 验签）、钉钉机器人（Webhook + 加签验签，actionCard 卡片），支持启用/禁用、测试发送
- **通知规则**：按事件类型、渠道、条件（仅失败/最小失败数/严重程度/项目限定）配置
- **18 种事件**：测试执行完成/失败、AI 任务完成/失败、缺陷创建/分配/状态变更、知识库处理完成、接口导入完成、性能分析完成等
- **19 种卡片模板**：统一 header + column_set + markdown + hr + action 结构，钉钉通过适配器自动转换为 actionCard 格式
- **异步发送**：Celery 任务，失败重试 2 次（10s/30s 间隔），通知失败不影响业务主流程
- **通知记录**：完整记录发送状态、响应内容，支持失败重试、10 秒自动刷新

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

### 任务监控

基于 Celery + Flower 的任务监控面板：
- **Worker 节点**：在线状态、并发数、已处理任务数、负载
- **任务统计**：成功/失败/等待中的任务数量
- **Flower 集成**：通过 Vite 代理访问 Flower API，实时刷新
- **启动保障**：start.sh 启动 Worker 后自动 ping 检测就绪，再启动 Flower

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

# 前端基础 URL（通知卡片跳转链接）
FRONTEND_BASE_URL=http://localhost:5173

# 默认 LLM（可在界面修改）
DEFAULT_LLM_PROVIDER=openai_compatible
DEFAULT_LLM_BASE_URL=https://api.deepseek.com/v1
DEFAULT_LLM_API_KEY=
DEFAULT_LLM_MODEL=deepseek-chat
```

## 数据库说明

- 后端启动时通过 `Base.metadata.create_all()` 自动创建新表
- 新增字段通过 main.py 中的轻量自动迁移逻辑（ALTER TABLE ADD COLUMN IF NOT EXISTS）
- 47 张数据表覆盖全部业务模块
- 所有表包含软删除字段（`is_deleted`/`deleted_at`）和时间戳（`created_at`/`updated_at`）

## 常见问题

**Q: 默认登录账号是什么？**
admin / admin123

**Q: 后端新增字段后数据库报错 Unknown column？**
重启后端服务，main.py 启动时会自动执行 ALTER TABLE 添加缺失字段。

**Q: Celery 任务不执行？**
确保 Redis 已启动且 Celery Worker 正在运行：`cd backend && ./start_celery_worker.sh 4`。修改任务代码后必须重启 Worker。

**Q: 任务监控页显示 Flower 离线 / Worker 进程 0？**
确保 Flower 已启动（`start.sh` 会自动启动）。手动启动需设置环境变量：`FLOWER_UNAUTHENTICATED_API=true celery -A app.celery_app.celery_app flower --port=5555`。Worker 需加 `--events --heartbeat-interval=5` 参数。

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
测试用例关联接口后自动使用接口的 URL，无需在用例中输入路径。执行时弹窗选择环境，确保环境变量中配置了正确的 base_url。

**Q: 接口测试执行时 {{变量名}} 没有被替换？**
确认已选择环境且环境变量中配置了对应变量。变量名支持字母、数字、下划线、连字符和点（如 `{{xp-authorization}}`、`{{user.id}}`）。Mock 函数需加 `$` 前缀（如 `{{$uuid()}}`）。未定义的变量会保留原样不替换。

**Q: 知识库向量检索不生效？**
确保文档已点击「生成切片」且状态为「就绪」。智能助手需选择项目并开启「知识库」开关。首次使用需下载 sentence-transformers 模型（约 470MB）。

**Q: 飞书通知发送失败？**
检查渠道 Webhook 地址是否正确，如开启验签需确认密钥与飞书机器人配置一致。可在通知记录中查看失败原因并重试。

**Q: 智能助手提示"当前模型不支持工具调用"？**
在模型配置中点击「能力检测」确认模型支持 Function Calling。部分自部署模型虽然兼容 OpenAI 接口但后端不处理 tools 参数，需切换支持工具调用的模型。

**Q: MCP 连接器连接失败？**
确认 MCP 服务器 URL 可访问且为 SSE 类型。SSE 端点返回 200 后会自动解析 endpoint 事件获取 POST 地址。部分 MCP 服务器路径为 `/sse` 或 `/mcp`，按实际配置填写。

**Q: Skill ZIP 包导入失败？**
确保 ZIP 包第一层为 Skill 名称文件夹，内含 `SKILL.md`（frontmatter 必须包含 name 和 description 字段）。多级目录和其他资源文件（.py/.json 等）会完整存入库中。

**Q: 性能测试 AI 分析报告内容乱码？**
删除旧报告后重新点击「AI性能分析」。新版 prompt 采用 System/Human 分离设计，数据预处理为纯文本格式，temperature 降至 0.3，避免 LLM 编造数据。

## 许可证

MIT License
