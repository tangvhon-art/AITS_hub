# AITS 智能测试管理平台

基于 LangChain + Agent 的下一代智能测试管理平台，覆盖测试全流程（需求解析 → 用例生成 → UI 自动化执行 → 缺陷分析 → 报告生成）。

## 技术栈

- **前端**: Vue 3 + TypeScript + Ant Design Vue 4.x + Pinia + Vite + dayjs
- **后端**: FastAPI + Python 3.12+ + SQLAlchemy 2.0 + Pydantic v2
- **数据库**: MySQL 8.0 + Redis
- **Agent 框架**: LangChain 0.3 + LangGraph（MVP-2 引入）
- **UI 自动化**: Playwright
- **大模型**: 支持 DeepSeek / Claude / 自部署 vLLM-TGI / 本地 Ollama（四种接入模式）

## 快速开始

### 方式一：Docker Compose（推荐）

```bash
# 1. 克隆项目
cd AITS_hub

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入数据库密码和 LLM API Key（可选）

# 3. 启动所有服务
docker-compose up -d

# 4. 查看服务状态
docker-compose ps

# 5. 访问
# 前端: http://localhost:5173
# 后端 API: http://localhost:8000
# API 文档: http://localhost:8000/docs
```

### 方式二：本地开发

#### 前置要求

- Python 3.12+
- Node.js 18+
- MySQL 8.0
- Redis（可选，MVP-1 未强制依赖）

#### 1. 启动 MySQL

```bash
docker run -d --name aits-mysql \
  -e MYSQL_ROOT_PASSWORD=root123 \
  -e MYSQL_DATABASE=AITS_hub \
  -p 3306:3306 \
  mysql:8.0 --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci
```

#### 2. 后端启动

```bash
cd backend

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入数据库连接信息

# 启动服务（首次启动自动创建数据库表）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 3. 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

访问 http://localhost:5173

## 使用指南

### 演示流程

1. **注册登录**：访问 http://localhost:5173，注册账号并登录
2. **创建项目**：在项目管理页面创建一个测试项目
3. **添加需求**：进入项目 → 需求管理，手动创建或上传需求文档（支持 Word/PDF/TXT/MD）
4. **AI 生成用例**：在需求列表点击「AI生成用例」，选择生成数量，自动生成结构化测试用例
5. **编辑用例**：在用例管理页面查看、编辑、筛选生成的用例
6. **执行用例**：点击用例操作列的「执行」按钮，自动跳转到 UI 自动化执行页面，用例步骤已转换为执行指令
7. **查看结果**：实时查看执行日志、截图和最终结果

### 大模型配置

平台支持四种大模型接入模式，在「模型配置」页面管理：

| 模式 | 说明 | 示例 |
|------|------|------|
| OpenAI 兼容协议 | DeepSeek、自部署 vLLM/TGI、Doubao 等 | base_url=https://api.deepseek.com/v1 |
| Anthropic Claude | Claude 官方 API | model=claude-3-5-sonnet-20241022 |
| 本地 Ollama | 本地运行的开源模型 | base_url=http://localhost:11434 |

#### 配置步骤

1. 登录后进入「模型配置」页面
2. 点击「新建模型配置」
3. 选择提供商，填入 Base URL、API Key、模型名称
4. 可选择是否启用流式输出（自部署模型建议关闭）
5. 点击「测试连接」验证可用性
6. 设为默认模型

#### 降级策略

当主模型调用失败时，系统会按 `priority` 字段自动降级到备用模型，每个模型最多重试 2 次，确保服务可用性。

## 核心功能

### MVP-1 已实现（当前版本）

- [x] 用户注册 / 登录 / JWT 鉴权
- [x] 项目管理（创建、编辑、删除、按项目隔离数据）
- [x] 需求管理（手动创建、文档上传解析 Word/PDF/TXT/MD）
- [x] AI 用例生成（基于需求自动生成结构化测试用例，支持 P0-P3 优先级）
- [x] 用例管理（CRUD、批量创建、优先级/模块筛选、步骤编辑器）
- [x] **用例→执行打通**（从用例列表一键发起 UI 自动化执行，自动转换步骤为指令）
- [x] UI 自动化执行（Playwright + Agent，SSE 实时日志流，截图记录）
- [x] 执行历史记录（按项目/用例筛选）
- [x] 大模型统一抽象层（4 种 provider、自动降级、Token 统计）
- [x] 模型配置管理（CRUD、测试连接、设默认、流式开关）
- [x] 全局异常处理（统一错误响应格式）
- [x] 多标签页导航（打开的页面以标签页形式展示，可切换/关闭）
- [x] Ant Design 纯净白色调 UI

### MVP-2 规划中

- [ ] Supervisor 多 Agent 编排（LangGraph）
- [ ] 用例评审 Agent（完整性/覆盖率/可执行性评分）
- [ ] 缺陷分析 Agent（失败日志→根因推断→自动提单）
- [ ] 报告生成 Agent（通过率/缺陷分布/覆盖率）
- [ ] 通知 Agent（邮件 + 飞书 Webhook）
- [ ] BDD Gherkin 用例生成
- [ ] RAG 知识库（FAISS 向量检索）
- [ ] RabbitMQ 异步任务队列
- [ ] Agent 任务监控面板
- [ ] Token 消耗统计与成本分析

## API 文档

启动后端后访问 http://localhost:8000/docs 查看完整 API 文档（Swagger UI）。

### 主要接口

| 模块 | 接口 | 说明 |
|------|------|------|
| 认证 | POST /api/auth/register | 用户注册 |
| 认证 | POST /api/auth/login | 用户登录（OAuth2 表单） |
| 认证 | GET /api/auth/me | 获取当前用户 |
| 项目 | GET/POST /api/projects | 项目列表/创建 |
| 项目 | GET/PUT/DELETE /api/projects/{id} | 项目详情/更新/删除 |
| 需求 | /api/projects/{id}/requirements | 需求 CRUD + 文档上传 |
| 用例 | /api/projects/{id}/cases | 用例 CRUD + 批量创建 |
| 用例 | POST /api/projects/{id}/cases/generate | AI 生成用例 |
| 执行 | POST /api/projects/{id}/execution/run | SSE 流式执行 |
| 执行 | GET /api/projects/{id}/execution/runs | 执行历史 |
| 模型 | GET/POST /api/llm-configs | 模型配置 CRUD |
| 模型 | POST /api/llm-configs/{id}/test | 测试连接 |
| 模型 | POST /api/llm-configs/{id}/set-default | 设为默认 |
| 系统 | GET /api/health | 健康检查 |

## 项目结构

```
AITS_hub/
├── backend/
│   ├── app/
│   │   ├── agents/              # Agent 实现
│   │   │   ├── llm_factory.py        # 统一大模型抽象层（核心）
│   │   │   ├── case_generator.py     # 用例生成 Agent
│   │   │   └── execution_agent.py    # UI 执行 Agent
│   │   ├── api/                 # API 路由（6 个模块，37 个端点）
│   │   │   ├── auth.py
│   │   │   ├── projects.py
│   │   │   ├── requirements.py
│   │   │   ├── cases.py
│   │   │   ├── execution.py
│   │   │   └── llm_configs.py
│   │   ├── core/                # 安全、依赖注入、异常处理
│   │   │   ├── security.py
│   │   │   ├── deps.py
│   │   │   └── exceptions.py
│   │   ├── models/              # SQLAlchemy 模型（7 张表）
│   │   ├── schemas/             # Pydantic 请求/响应模型
│   │   ├── config.py            # Pydantic Settings 配置
│   │   ├── database.py          # 数据库连接
│   │   └── main.py              # FastAPI 入口
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── views/               # 页面组件（Ant Design Vue）
│   │   │   ├── Login.vue        # 登录/注册
│   │   │   ├── Layout.vue       # 主布局（侧边栏+多标签页）
│   │   │   ├── Projects.vue     # 项目管理
│   │   │   ├── Requirements.vue # 需求管理
│   │   │   ├── Cases.vue        # 用例管理
│   │   │   ├── Execution.vue    # UI 自动化执行
│   │   │   └── LLMConfig.vue    # 模型配置
│   │   ├── api/                 # API 封装（axios）
│   │   ├── stores/              # Pinia 状态管理
│   │   ├── router/              # Vue Router 路由
│   │   ├── assets/main.css      # 全局样式
│   │   └── main.ts              # 入口
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
├── LangChain+Agent智能测试管理平台设计方案.md
├── MVP执行计划.md
└── README.md
```

## 数据库表

| 表名 | 说明 | 关键字段 |
|------|------|---------|
| users | 用户表 | username, email, hashed_password, is_admin |
| test_projects | 项目表 | name, description, owner_id |
| test_requirements | 需求表 | project_id, title, content, source, status |
| test_cases | 测试用例表 | project_id, req_id, title, module, priority, steps(JSON), expected_result |
| test_runs | 执行记录表 | project_id, case_id, status, execution_log(JSON), screenshot_url, duration |
| agent_tasks | Agent 任务表 | agent_type, status, input_params, output_result, token_usage |
| llm_configs | 模型配置表 | name, provider, base_url, api_key(加密), model_name, streaming, is_default, priority |

## 环境变量配置

### 后端（backend/.env）

```env
APP_NAME=AITS 智能测试管理平台
APP_ENV=development
DEBUG=true
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# 数据库
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your-password
DB_NAME=AITS_hub

# Redis（可选）
REDIS_URL=redis://localhost:6379/0

# CORS
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# 默认大模型（可选，也可在界面配置）
DEFAULT_LLM_PROVIDER=openai_compatible
DEFAULT_LLM_BASE_URL=https://api.deepseek.com/v1
DEFAULT_LLM_API_KEY=
DEFAULT_LLM_MODEL=deepseek-chat
```

## 常见问题

### 1. 数据库连接失败（密码含特殊字符）

如果数据库密码包含 `@`、`!`、`#` 等特殊字符，系统会自动进行 URL 编码，无需手动处理。

### 2. 自部署模型测试连接报错

如果使用自部署模型（如 vLLM/TGI）测试连接时报错 "No generations found in stream"，请在模型配置中关闭「流式输出」开关。部分自部署模型的流式响应格式与标准 OpenAI 不完全兼容。

### 3. Playwright 浏览器安装失败

在 Linux 服务器上安装 Playwright 时，可能需要先安装系统依赖：
```bash
# Ubuntu/Debian
sudo apt-get install -y libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2

# 或使用 playwright 自带的依赖安装
playwright install-deps chromium
```

### 4. bcrypt 相关报错

如果遇到 `ValueError: password cannot be longer than 72 bytes`，这是 bcrypt 5.x 与 passlib 不兼容导致的。项目已锁定 bcrypt==4.0.1，确保使用项目的 requirements.txt 安装依赖。

## 许可证

MIT License
