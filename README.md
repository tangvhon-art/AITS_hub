# AITS 智能测试管理平台

基于 LangChain + Agent 的下一代智能测试管理平台，覆盖测试全流程：**需求解析 → 用例生成 → 用例评审与优化 → UI 自动化执行 → 接口自动化测试 → 性能测试 → 测试计划编排 → 缺陷分析 → 报告生成 → 质量看板 → 事件通知**，并内置 **AI 模型五维综合测评**（AI 裁判 / 人工校准 / Agent 交互 / 业务落地 / 对抗红队），支持对内置 Agent 与外部工作流 Agent 进行标准化、可量化、可复现的能力测评。

## 技术栈

| 端 | 技术 |
|----|------|
| 后端 | Python 3.13+ · FastAPI 0.115 · SQLAlchemy 2.0 · Celery 5.6 · Redis 5 · MySQL 8 |
| AI 框架 | LangChain 0.3 · langchain-openai / anthropic / community |
| 前端 | Vue 3 · Vite · Ant Design Vue 4 · Pinia · ECharts 5 · marked（Markdown 渲染） |
| 测试执行 | Playwright 1.49（UI 自动化）· Locust 2.31（性能测试）|
| 智能能力 | Sentence-Transformers + FAISS（知识库 RAG）· MCP · Skill 规范 |

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
| 环境变量 | 多环境管理 + 变量配置 + JS 脚本变量，4 级变量优先级（用例 > 场景 > 环境 > 全局），支持静态值和 JS 脚本两种变量类型，脚本在环境加载时执行（`pm.environment.set()`），5秒超时沙箱隔离 |

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

### AI 模型五维综合测评

系统级主入口（**不关联项目**），进入后按页面菜单组织：**测评总览 / 被测对象 / 数据集与用例 / 测评任务 / 人工校准 / 对抗红队 / 测评报告 / 问题台账 / 版本对比**。默认支持对 AITS 内置 Agent 测评，可接入**外部工作流 Agent** 进行测评。

| 子页面 | 功能说明 |
|--------|---------|
| 测评总览 | 五维模式执行情况、指标看板（命中率/通过率/平均分等，中文展示 + Markdown 渲染）、任务进度 |
| 被测对象 | 四类被测对象：`llm`（绑定模型）/ `agent`（内置 Agent）/ `external_agent`（外部工作流）/ `business`（业务场景）；外部工作流需配置**服务地址 + 调用路径 + 鉴权方式**（none/bearer/apikey/custom） |
| 数据集与用例 | 数据集管理 + 评测用例维护，支持批量导入 |
| 测评任务 | 创建/运行测评任务，可勾选五维模式，执行进度 SSE 实时推送，支持取消 |
| 人工校准 | 抽样复核 AI 裁判结果，修正误判/漏判，双向校准 |
| 对抗红队 | 越狱攻击、提示注入、隐私探测等高危用例专项测评，风险定级 |
| 测评报告 | 分模块/综合报告，Markdown 渲染，版本准入结论 |
| 问题台账 | P0-P3 问题分级、闭环跟踪、复测结果 |
| 版本对比 | 新旧版本/被测对象横向对比，指标升降级定位 |

**五维测评模式**：

| 模式 | 代码 | 说明 |
|------|------|------|
| AI 裁判自动测评 | `ai_judge` | 高阶裁判模型批量打分（事实准确性/相关性/逻辑/指令遵循/流畅度，1-5 分）+ 成对胜负对比，多裁判投票 |
| 人工专家测评 | `manual` | 双人打分 + 第三人仲裁，校准 AI 裁判结果（Cohen's Kappa ≥ 0.75） |
| Agent 交互式测评 | `agent` | 多轮交互/任务拆解/工具调用/规划反思专项，任务完成率/工具调用正确率/闭环率/纠错成功率 |
| 业务落地测评 | `business` | 业务黄金测试集（高频/复杂/边界/差评/行业专属），业务成功率/NPS/幻觉率等 |
| 对抗红队测评 | `redteam` | 越狱/提示注入/偏见诱导/隐私探测，攻击拦截率/有害内容拒绝率/风险定级（高危零容忍） |

> 详见 [docs/AI模型五维综合测评-需求文档.html](docs/AI模型五维综合测评-需求文档.html) 与 [docs/AI模型五维综合测评-概要设计.html](docs/AI模型五维综合测评-概要设计.html)。

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
| Agent 配置 | 外部工作流平台接入配置（平台连接 + Webhook + 模块后端），支持系统级/项目级配置，**配置项支持软删除**（不物理删除，可恢复）；异步调用 + 固定 Webhook 回调 + uuid 路由 |
| 事件通知 | 飞书/钉钉机器人通知，18 种事件触发，19 种卡片模板，HMAC-SHA256 验签，异步发送+重试 |
| 任务监控 | Celery + Flower 监控面板；Worker 节点统计（**活跃任务/排队中/已处理/负载/进程 PID**，基于 DB + Redis 权威统计，不依赖失效的事件流）；任务状态筛选；**手动取消**（pending/running → canceled，取消防护防止被 worker 收尾覆盖）；**孤儿任务回收**（超过 30 分钟仍 running 自动标记 failed，worker 启动兜底 + Beat 每 5 分钟周期回收） |
| 任务调度 | 系统定时任务管理（sys_crontab 驱动动态 Beat），支持 interval/cron 两种调度 |
| 造数工厂 | 数据池升级：Mock 数据池（原数据池，功能保留）+ 通用造数工具（32 个工具，Schema 驱动，支持 MCP 注册调用） |
| 审计日志 | 操作审计追踪 |
| 数据导入导出 | Excel 导入/导出用例，XMind 导图导出 |
| 团队协作 | 项目成员管理 + 权限控制，用户仅见参与的项目 |

### 造数工厂

双 Tab 结构：

- **Mock 数据池**：原数据池能力保持不变（测试数据管理、环境变量覆盖）
- **通用造数工具**：32 个在线工具，Schema 驱动表单，支持 MCP 注册调用

**统一契约**：生成类工具输入生成数量（默认 1，上限 1000），返回 `{"count": n, "result": [...]}`；结果支持一键复制、导出 CSV（带 BOM）、一键导入 Mock 数据池。

| 分类 | 工具 |
|------|------|
| 测试数据（6） | 中文姓名、手机号、邮箱（可固定后缀）、地址、身份证、银行卡号 |
| JSON（5） | 格式化、校验、对比、JSONPath 查询、结构转换（JSON/XML/YAML 互转） |
| 字符（2） | 文本对比、正则工具 |
| 编码（6） | 二维码、条形码、时间戳转换（自动输出本地/UTC/ISO）、JWT 解码、Base64 ↔ 图片、Base64 编码 |
| 随机（8） | UUID（连字符/大写勾选）、IP、MAC、整数、浮点数、日期（日期组件）、颜色（色块渲染）、密码 |
| 加解密（5） | MD5、SHA 摘要、HMAC 签名（密钥 + MD5/SHA1/SHA256/SHA512 等算法）、AES 加密、AES 解密 |

**平台化能力**：

- 全部 32 个工具按 `SERVICE_REGISTRY` 注册表动态分发，统一参数校验（`count` 裁切 1~1000）与错误码体系（404/400/422/504/500）；
- 通过 **MCP（Model Context Protocol）** 动态注册（`GET /mcp/sse` 握手 + `POST /mcp/messages` JSON-RPC），智能助手等 MCP 客户端可直接调用 32 个造数工具；
---

## 外部 Agent 接入

AITS 支持将 AI 生成类任务（需求生成、功能点拆分、用例生成、用例评审、测试报告生成）委派给**外部工作流平台的 Agent** 执行，通过**异步调用 + 固定 Webhook 回调 + uuid 路由**的方式实现与本地 LLM 执行完全一致的写库闭环。AI 模型测评模块同样支持将**外部工作流 Agent 作为被测对象**进行测评。

### 接入架构

```
前端页面（选择执行方式：本地默认 / 外部工作流）
        │
        ▼
AITS 创建 AgentTask，生成 uuid，backend=workflow
        │
        ▼ ① 异步调用外部 Agent（携带 uuid + 回调地址）
外部工作流平台 Agent（异步处理，耗时长）
        │
        ▼ ② 立即受理返回 task_id（AITS 不阻塞）
AITS 保存 task_id，任务置为"等待回调"
        │
        ▼ ③ 外部 Agent 完成，携带 uuid 回调 AITS 固定 Webhook
AITS 校验签名 → 按 uuid 定位 AgentTask/模块 → 幂等检查
        │
        ▼ ④ raw = content（跳过 LLM）→ 复用原解析 → 写库
AITS 写入各业务数据库（需求/功能点/用例/评审/报告）
        │
        ▼
AgentTask 完成 · 事件通知 · 审计日志
```

### 配置方式

在 **系统管理 → Agent 配置** 页面进行配置：

1. **平台连接**：配置外部工作流平台的连接信息（Base URL、鉴权方式、凭证等）
2. **Webhook 配置**：启用固定 Webhook 端点，配置回调超时和签名密钥
3. **模块后端**：为每个 AI 模块配置执行后端
   - **项目**：可选，选择具体项目则为项目级配置（优先于系统级），不选则为系统级默认
   - **默认执行后端**：本地执行（调用本地 LLM）/ 外部工作流
   - **绑定平台连接**：选择已配置的外部平台连接
   - **外部 Agent 标识**：外部平台的 agent/workflow ID
   - **允许页面切换**：开启后业务页面提交时可临时选择执行后端

**配置优先级**：页面临时选择 > 项目级配置 > 系统级默认

### 支持的模块

| 模块 ID | 模块名称 | agent_type | 说明 |
|---------|---------|-----------|------|
| `requirement.generate` | 需求生成 | `requirement_generator` | 从描述生成需求文档 |
| `requirement.split_features` | 功能点拆分 | `feature_splitter` | 从需求拆分功能点（按模块分组） |
| `case.generate` | 用例生成 | `case_generator` | 从需求/功能点生成测试用例 |
| `case.review` | 用例评审 | `case_reviewer` | 对用例进行7维度AI评审 |
| `report.generate` | 测试报告生成 | `report_generator` | 生成测试报告 |

### 外部 Agent 返回结果结构

外部 Agent 处理完成后，需携带原 `uuid` 回调 AITS 的固定 Webhook 端点。回调请求结构如下：

**请求头：**
```
POST /api/workflow/webhook
Content-Type: application/json
X-Aits-Signature: hmac_sha256(payload, secret)   # 回调签名（防伪造）
```

**请求体：**
```json
{
  "uuid": "wf_3f9a2c...",
  "content": "...",
  "status": "success",
  "error": null
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `uuid` | string | ✅ | AITS 调用时生成的 uuid，回调原样带回，用于定位任务和模块 |
| `content` | string | ✅ | Agent 生成内容，**与本地 LLM 的 `response.content` 完全同构的字符串**。AITS 将其作为原始输出，复用原有解析器进行解析和写库 |
| `status` | string | ✅ | 执行状态：`success` / `failed` / `timeout` |
| `error` | string | ❌ | 失败时的错误原因，status=success 时为 null |

**AITS 应答（快速确认，随后异步处理）：**
```json
{ "code": 0, "message": "received" }
```

### 各模块 content 格式要求

外部 Agent 返回的 `content` 字段必须符合对应模块的格式要求，AITS 会复用原有解析器进行解析。以下是各模块的格式规范：

#### 1. 需求生成（requirement.generate）

`content` 为需求文档内容，支持以下格式（按优先级解析）：

**格式 A：JSON（推荐）**
```json
{
  "title": "用户登录模块需求文档",
  "content": "## 需求背景\n\n随着系统上线...\n\n## 功能描述\n\n- 用户身份验证...\n\n## 验收标准\n\n1. 输入有效用户名和密码..."
}
```

**格式 B：Markdown**
```markdown
# 用户登录模块需求文档

## 需求背景
随着系统上线...

## 功能描述
- 用户身份验证...

## 验收标准
1. 输入有效用户名和密码...
```

**解析结果**：`{"title": "需求标题", "content": "需求正文"}` → 写入 `test_requirements` 表

#### 2. 功能点拆分（requirement.split_features）

`content` 为功能点拆分结果，**必须为 JSON 格式**：

```json
{
  "modules": [
    {
      "module_name": "账号密码认证模块",
      "module_desc": "处理用户账号密码的身份验证",
      "features": [
        {
          "name": "有效用户名密码登录",
          "description": "输入正确的用户名和密码，系统验证通过后生成JWT令牌",
          "priority": "P0",
          "design_methods": ["等价类划分", "边界值分析"],
          "preconditions": "用户已完成系统注册，账号未处于冻结状态"
        },
        {
          "name": "连续5次密码错误触发锁定",
          "description": "连续输入错误密码5次后，账户被锁定并发送告警通知",
          "priority": "P0",
          "design_methods": ["错误推测"],
          "preconditions": "用户已完成系统注册"
        }
      ]
    },
    {
      "module_name": "多渠道验证码模块",
      "module_desc": "支持手机短信和邮箱两种验证码渠道",
      "features": [
        {
          "name": "验证码发送渠道有效性校验",
          "description": "仅支持手机和邮箱渠道发送验证码，无效渠道提示不可用",
          "priority": "P1",
          "design_methods": ["等价类划分"],
          "preconditions": "用户账号已绑定对应手机号/邮箱"
        }
      ]
    }
  ]
}
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `modules` | array | ✅ | 模块列表 |
| `modules[].module_name` | string | ✅ | 模块名称 |
| `modules[].module_desc` | string | ❌ | 模块描述 |
| `modules[].features` | array | ✅ | 功能点列表 |
| `features[].name` | string | ✅ | 功能点名称 |
| `features[].description` | string | ❌ | 功能点描述 |
| `features[].priority` | string | ❌ | 优先级：P0/P1/P2/P3，默认 P1 |
| `features[].design_methods` | array/string | ❌ | 设计方法列表，字符串会按逗号/分号/顿号拆分 |
| `features[].preconditions` | string | ❌ | 前置条件 |

**解析结果**：按模块分组写入 `requirement_features` 表

#### 3. 用例生成（case.generate）

`content` 为测试用例列表，支持以下格式（按优先级解析）：

**格式 A：JSON 对象（推荐）**
```json
{
  "cases": [
    {
      "title": "有效用户名密码登录",
      "module": "账号密码认证模块",
      "priority": "P0",
      "case_type": "正常场景",
      "preconditions": "用户已完成系统注册，账号未处于冻结状态",
      "steps": [
        {"action": "输入正确用户名和密码", "expected": "系统2秒内返回登录成功状态"},
        {"action": "检查响应时间", "expected": "登录响应时间≤500ms"}
      ],
      "expected_result": "用户成功登录并生成JWT令牌"
    },
    {
      "title": "连续5次密码错误触发锁定",
      "module": "账号密码认证模块",
      "priority": "P0",
      "case_type": "异常场景",
      "preconditions": "用户已完成系统注册",
      "steps": [
        {"action": "输入错误密码5次", "expected": "第5次失败后账户被锁定"},
        {"action": "尝试第6次登录", "expected": "系统拒绝登录并提示账户锁定"}
      ],
      "expected_result": "账户在连续5次错误后被锁定并发送告警"
    }
  ]
}
```

**格式 B：JSON 数组**
```json
[
  {"title": "用例1", "module": "模块A", "priority": "P0", "steps": [...], "expected_result": "..."},
  {"title": "用例2", "module": "模块A", "priority": "P1", "steps": [...], "expected_result": "..."}
]
```

**格式 C：Markdown 表格**
```markdown
| 用例标题 | 模块 | 优先级 | 前置条件 | 步骤 | 预期结果 |
|---------|------|--------|---------|------|---------|
| 有效登录 | 认证模块 | P0 | 已注册 | 1.输入正确账号密码 | 登录成功 |
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `title` | string | ✅ | 用例标题 |
| `module` | string | ❌ | 所属模块名称 |
| `priority` | string | ❌ | 优先级：P0/P1/P2/P3 |
| `case_type` | string | ❌ | 用例类型：正常场景/异常场景/边界场景等 |
| `preconditions` | string | ❌ | 前置条件 |
| `steps` | array | ❌ | 测试步骤列表 |
| `steps[].action` | string | ✅ | 操作描述 |
| `steps[].expected` | string | ❌ | 预期结果 |
| `expected_result` | string | ❌ | 最终预期结果 |
| `bdd_content` | string | ❌ | BDD 格式内容（Given/When/Then） |

**解析结果**：写入 `test_cases` 表，自动关联需求和功能点

#### 4. 用例评审（case.review）

`content` 为用例评审结果，支持以下两种格式：

**格式 A：Markdown（推荐，新格式）**
```markdown
## 评分
85

## 评审结论
通过

## 问题列表
1. **用例ID=101** | 模块=账号密码认证 | 问题类型=覆盖度不足 | 严重程度=高
   问题描述：缺少密码长度边界（6字符/20字符）的测试用例
   改进建议：补充密码长度为5、6、20、21的边界测试用例

2. **用例ID=105** | 模块=多渠道验证码 | 问题类型=可执行性 | 严重程度=中
   问题描述：验证码发送步骤未指定具体测试数据
   改进建议：补充有效手机号和邮箱的测试数据

## 遗漏场景
- 密码包含特殊字符的场景
- 用户名大小写不敏感的场景
- 登录成功后JWT令牌过期的场景

## 整体改进建议
1. 补充边界值测试用例，提升覆盖度
2. 统一用例步骤的描述规范，确保可执行性
3. 增加异常场景的测试用例比例

## 分组评价
### 账号密码认证模块
- 覆盖度：80分，缺少边界值测试
- 完整性：85分，主要场景已覆盖
- 可执行性：90分，步骤描述清晰

### 多渠道验证码模块
- 覆盖度：70分，缺少无效渠道测试
- 完整性：75分，部分场景遗漏
- 可执行性：80分，需补充测试数据
```

**格式 B：JSON（旧格式，向后兼容）**
```json
{
  "score": 85,
  "passed": true,
  "summary": "整体评审通过，存在少量改进空间",
  "issues": [
    {
      "case_id": 101,
      "module": "账号密码认证",
      "issue_type": "覆盖度不足",
      "severity": "高",
      "description": "缺少密码长度边界测试用例",
      "suggestion": "补充密码长度为5、6、20、21的边界测试用例"
    }
  ],
  "overall_suggestions": [
    "补充边界值测试用例，提升覆盖度",
    "统一用例步骤的描述规范"
  ],
  "group_reviews": [
    {
      "module": "账号密码认证模块",
      "coverage_score": 80,
      "completeness_score": 85,
      "executability_score": 90,
      "comments": "主要场景已覆盖，缺少边界值"
    }
  ],
  "missing_scenarios": [
    "密码包含特殊字符的场景",
    "用户名大小写不敏感的场景"
  ]
}
```

**Markdown 格式章节说明**：

| 章节 | 必填 | 说明 |
|------|------|------|
| `## 评分` | ✅ | 0-100 的整数评分 |
| `## 评审结论` | ❌ | 通过/不通过，不填则根据评分≥70自动判断 |
| `## 问题列表` | ❌ | 每条问题包含用例ID、模块、问题类型、严重程度、问题描述、改进建议 |
| `## 遗漏场景` | ❌ | 未覆盖的测试场景列表 |
| `## 整体改进建议` | ❌ | 整体改进建议列表 |
| `## 分组评价` | ❌ | 按模块分组的评价，包含各维度评分和评论 |

**解析结果**：存入 `agent_tasks.output_result`，前端展示评审报告，支持一键优化/补充用例

#### 5. 测试报告生成（report.generate）

`content` 为测试报告内容，支持 Markdown 或 JSON 格式。AITS 会将其作为报告正文写入测试报告表。

**格式 A：Markdown（推荐）**
```markdown
# 测试报告

## 概述
本次测试覆盖了用户登录模块的全部功能点...

## 测试结果汇总
- 总用例数：50
- 通过：45
- 失败：3
- 跳过：2
- 通过率：90%

## 缺陷分析
1. 缺陷 #1：登录响应时间超过500ms
   - 严重程度：中
   - 状态：已修复

## 风险与建议
- 建议补充性能测试场景
- 建议增加安全测试用例
```

**格式 B：JSON**
```json
{
  "title": "用户登录模块测试报告",
  "content": "## 概述\n本次测试...",
  "summary": {
    "total": 50,
    "passed": 45,
    "failed": 3,
    "skipped": 2,
    "pass_rate": 0.9
  }
}
```

### 回调签名验证

为防止伪造回调请求，AITS 要求外部 Agent 在回调时携带 HMAC-SHA256 签名：

**签名计算方式：**
```
signature = HMAC-SHA256(payload_body, secret)
```

- `payload_body`：请求体的原始 JSON 字符串
- `secret`：在 AITS **Agent 配置 → Webhook 配置** 中生成的签名密钥

**请求头：**
```
X-Aits-Signature: <hmac_sha256_hex>
```

AITS 收到回调后会验证签名，签名不匹配的请求将被拒绝。

### 失败与降级

- **受理失败**：外部平台未受理或返回错误，任务标记 failed
- **回调超时**：超过配置的回调超时时间（默认30分钟）未收到回调，任务标记 failed
- **回调校验失败**：签名不匹配或 uuid 不存在，请求被拒绝
- **解析失败**：content 格式不符合要求导致解析失败，任务标记 failed
- **自动降级**：外部执行失败时，AITS 会自动降级为本地 LLM 执行（可配置开关）

---

## AI 模型五维综合测评

### 定位

AI 测评是**系统级功能，不归属任何项目**，从侧边栏「AI 模型测评」主入口进入后按页面菜单组织。它解决单一测评方式结果失真、学术跑分与业务落地脱节、能力测评与安全测评割裂的行业痛点，为模型/Agent 版本迭代、上线准入、性能优化与风险管控提供**标准化、可量化、可复现**的依据。

### 被测对象

| 类型 | 代码 | 配置内容 |
|------|------|---------|
| LLM 模型 | `llm` | 绑定已有模型配置（llm_config） |
| 内置 Agent | `agent` | 绑定 AITS 内置 Agent 类型 |
| 外部工作流 Agent | `external_agent` | **服务地址（Base URL）+ 调用路径 + 鉴权方式**（`none` / `bearer` / `apikey` / `custom`）+ 鉴权凭证（加密存储）与 Header 名 |
| 业务场景 | `business` | 业务场景标识与预期输出约束 |

> **外部工作流被测对象**：被测对象类型选择「外部工作流」时，填入的是外部 Agent 的调用服务地址、调用路径与鉴权方式，AITS 作为测评方直接发起调用并收集输出，无需走 Webhook 回调链路。

### 测评任务与执行

1. 在「被测对象」维护被测对象（内部 Agent 默认即可，外部工作流按需接入）；
2. 在「数据集与用例」维护评测用例（按 eval_type 组织，支持批量导入）；
3. 在「测评任务」创建任务，勾选五维模式（`ai_judge` / `manual` / `agent` / `business` / `redteam`），绑定被测对象与数据集；
4. 运行后由 **AI 测评 Worker（eval 队列）** 异步执行，SSE 实时推送进度；
5. 完成后在「测评报告」「问题台账」「版本对比」查看结果，报告与模型输出均支持 **Markdown 渲染**，指标（如命中率、通过率、平均分等）以**中文**展示。

### 准入结论

| 结论 | 条件 |
|------|------|
| 准入通过 | 无 P0/P1 问题，核心指标达标，业务效果不降级，安全零高危风险 |
| 条件通过 | 无 P0 问题，少量 P2 问题，核心指标达标，可上线并限期优化 |
| 准入驳回 | 存在 P0/P1 问题、核心指标大幅降级、存在高危安全风险，禁止上线 |

---

## 快速开始

### 前置要求

- Python 3.13+
- Node.js 18+
- MySQL 8.0
- Redis 7

### 方式一：一键启动（推荐）

```bash
# 启动全部服务（前端 + 后端 + 4个队列Worker + Beat + Flower）
./start.sh
```

`start.sh` 会按顺序启动：后端（自动建表/迁移）→ 4 个队列 Worker（AI/Execution/Eval/Default + 就绪检测）→ Beat 定时调度器 → Flower 监控 → 前端。脚本自动检测并安装依赖（Python venv / Node.js node_modules / Playwright Chromium）。

### 方式二：单独启动

```bash
# 仅启动后端
./start_backend.sh --port 8000

# 仅启动前端
./start_frontend.sh --port 5173

# 一键启动全部 Worker + Beat + Flower（含 AI 测评 Worker）
cd backend && ./start_all_workers.sh

# 停止全部
cd backend && ./stop_all_workers.sh
```

`start_all_workers.sh` 启动的 4 个队列 Worker：

| Worker | 队列 | 并发 | 职责 |
|--------|------|------|------|
| AI Worker | `ai` | 2 | AI 生成类任务（需求/用例/评审/报告生成等） |
| Execution Worker | `execution` | 4 | 执行类任务（UI 自动化/接口执行/性能压测） |
| AI 测评 Worker | `eval` | 2 | AI 模型五维综合测评任务 |
| Default Worker | `default` | 2 | 后台轻量任务（通知/清理/孤儿回收等） |

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

# 3. Celery Worker（按队列分终端启动）
cd backend && source venv/bin/activate
celery -A app.celery_app.celery_app worker -Q ai --loglevel=info --concurrency=2
celery -A app.celery_app.celery_app worker -Q execution --loglevel=info --concurrency=4
celery -A app.celery_app.celery_app worker -Q eval --loglevel=info --concurrency=2
celery -A app.celery_app.celery_app worker -Q default --loglevel=info --concurrency=2

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

---

## 任务监控与任务治理

任务监控页面（系统管理 → 任务监控）提供以下能力：

- **统计卡片**：执行中/排队中/已完成/失败/已取消任务数，以 DB `agent_tasks` + Redis 队列积压为准，实时反映真实状态；
- **Worker 节点**：在线 Worker 列表（基于 `celery control inspect` 主动探测，不依赖已失效的 Celery 事件流），展示队列、活跃任务、排队中、已处理、负载、进程 PID；
- **状态筛选**：与 AgentTask 状态全集一致（执行中/排队中/已完成/失败/已取消）；
- **手动取消**：对执行中/排队中的任务点击「取消」，任务置为 `canceled`；任务完成后不能被取消（返回明确提示）。已实现**取消防护**：任务被取消后，即使 Worker 仍在执行，其收尾逻辑也不会覆盖 canceled 状态；
- **孤儿任务回收**：超过 30 分钟仍处于执行中的任务（如进程崩溃、Worker 宕机残留的僵尸任务）由 `recycle_orphan_tasks` 自动标记为 `failed`。触发方式：Worker 启动时兜底执行一次 + Beat 每 5 分钟周期调度（`sys_crontab` 中「孤儿任务回收」记录，可在任务调度页面查看）。

---

## 环境变量 JS 脚本

环境变量支持两种值类型：**静态值**（`static`）和 **JS 脚本**（`script`）。脚本类型变量在环境加载时自动执行，结果作为变量值参与后续 `{{var}}` 替换。

```
选择环境 → VariableEngine.load_environment()
                ↓
         先加载所有 static 变量
                ↓
         再执行 script 变量（可读取已加载的 static 变量）
                ↓
         pm.environment.set("key", value) → 写入 environment_vars
                ↓
         后续 {{key}} 替换使用脚本生成的值
```

**脚本可用 API（兼容 Postman pm.*）：**

```javascript
// 读取其他静态环境变量
var baseUrl = pm.environment.get("base_url");

// 设置当前变量值
pm.environment.set("token", "Bearer " + rawToken);

// 控制台日志
console.log("生成 token 完成");

// 常见场景：动态时间戳
pm.environment.set("ts", String(Date.now()));

// 常见场景：依赖其他变量拼接
var apiUrl = pm.environment.get("base_url") + "/v1/api";
pm.environment.set("api_url", apiUrl);
```

**限制：** 脚本超时 5 秒，沙箱隔离（不能访问文件系统/网络），只能通过 `pm.environment.set()` 写入变量。

---

## 项目结构

```
AITS_hub/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── api/             # 路由层（含 eval.py AI测评、workflow.py、agent_tasks.py 任务监控、data_factory.py 造数工厂等）
│   │   ├── agents/          # 智能体（Supervisor / BDD 生成器等；tools/builtin 含 data_factory_tools.py MCP 动态注册）
│   │   ├── models/          # SQLAlchemy 模型（含 eval.py 测评模型、agent_task.py）
│   │   ├── schemas/         # Pydantic 校验
│   │   ├── services/        # 业务服务（eval_service / orphan_recycle / agent_task_status / workflow_* / data_tools 造数工具等）
│   │   │   └── data_tools/  # 造数工厂 32 个工具（base.py 注册分发 + test_data/json/text/encoding/random/crypto 六模块）
│   │   ├── tasks/           # Celery 任务（eval_tasks / case_tasks / recycle_tasks 等）
│   │   ├── mcp/             # MCP 服务（SSE + JSON-RPC 端点，tools/list、tools/call）
│   │   ├── celery_app.py    # Celery 实例（4 队列：ai/execution/eval/default）
│   │   └── main.py          # 应用入口（自动建表/迁移）
│   ├── start_all_workers.sh # 启动 Beat + 4 Worker + Flower
│   ├── stop_all_workers.sh
│   └── requirements.txt
├── frontend/                # Vue 3 前端
│   └── src/
│       ├── views/data/      # 造数工厂页面（DataFactory 双Tab / DataTools 六类导航 / DataSchemaForm / ToolPanel / ResultViewer / DataPools / DataPoolEdit）
│       ├── views/eval/      # AI 模型测评页面（EvalLayout/Dashboard/Targets/Tasks/Reports...）
│       ├── views/           # 其他业务页面（TaskMonitor.vue 任务监控等）
│       ├── api/             # 接口封装（dataFactory.ts 等）
│       └── router/          # 路由（/eval/* 测评路由、/projects/:id/data-factory 造数工厂）
├── docs/                    # 需求/概设文档（含 AI 模型五维综合测评、造数工厂 HTML）
├── docker-compose.yml       # 容器编排（MySQL/Redis 等）
├── start.sh                 # 一键启动脚本
├── start_backend.sh / start_frontend.sh
└── README.md
```

---

## 常见问题

**Q: 后端新增字段后数据库报错 Unknown column？**
重启后端服务，main.py 启动时会自动执行 ALTER TABLE 添加缺失字段。

**Q: Celery 任务不执行？**
确保 Redis 已启动且对应队列的 Celery Worker 正在运行。修改任务代码后必须重启对应队列的 Worker（AI 生成类 → ai，执行类 → execution，测评类 → eval，后台任务 → default）。

**Q: AI 测评任务一直排队不执行？**
确认 AI 测评 Worker（eval 队列）已启动（`start_all_workers.sh` 或手动 `celery ... -Q eval`），并确认 Redis 连接正常。

**Q: 任务监控中 Worker 节点/执行中数量显示为 0？**
Worker 节点列表与统计基于后端实时探测（`celery control inspect` + DB/Redis 权威统计），不依赖 Celery 事件流。若显示异常，确认后端与 Worker 均已启动、Redis 正常。

**Q: 如何清理卡死的"执行中"任务？**
无需手动清理：孤儿任务回收机制会每 5 分钟自动把超过 30 分钟仍执行中的任务标记为失败；也可在任务监控页面手动点击「取消」。

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

**Q: 外部 Agent 回调后任务一直是"等待回调"？**
检查：1) Webhook 全局开关是否启用；2) 回调请求的 uuid 是否与 AITS 调用时的 uuid 一致；3) 回调签名是否正确（X-Aits-Signature 头）；4) 回调请求体的 content 字段是否为字符串格式。

**Q: 外部 Agent 返回的 content 解析失败？**
确认 content 格式符合对应模块的要求（见上方"各模块 content 格式要求"）。需求生成支持 JSON/Markdown，功能点拆分必须为 JSON，用例生成支持 JSON/Markdown，用例评审支持 Markdown/JSON。

**Q: AI 测评的外部工作流被测对象无法调用？**
确认被测对象配置了正确的服务地址（Base URL）、调用路径与鉴权方式（none/bearer/apikey/custom），且目标服务对 AITS 可达。

**Q: 智能助手无法调用造数工厂工具？**
确认后端已启动且 MCP 端点可用（`GET /mcp/sse` 可握手）。造数工厂 32 个工具随内置工具动态注册（`tools/list` 中可见，共 49 个内置工具），智能助手需选择支持 MCP 工具调用的模型。

---

## 后端开发约定（异步执行）

> macOS 上 Celery Worker 使用 **eventlet 协程池**（`-P eventlet`），monkey-patch 后
> `threading.Thread` / `ThreadPoolExecutor` / `asyncio.to_thread` 都会被替换成 greenlet，
> 所有任务挤在同一 OS 线程。若某任务的事件循环正在运行，同线程内其它任务再调用
> `asyncio.run()` / `loop.run_until_complete()` 会抛
> `Cannot run the event loop while another loop is running`。

**统一规则：所有「在同步代码里把 async 函数跑到完」的入口，一律使用 `app/core/async_runner.py` 的 `run_async()`，禁止直接写 `asyncio.run()` / `new_event_loop() + run_until_complete()`。**

```python
from app.core.async_runner import run_async

# 正确：传 async 函数 + 参数（协程工厂）
result = run_async(api_case_generator.generate, api_dict, strategy="comprehensive")

# 错误：传协程对象会报 TypeError（已内置拦截提示）
# result = run_async(api_case_generator.generate(api_dict))
```

- `run_async` 会自动判断：当前线程无 running loop → 直接在当前线程执行（最快）；
  已有 running loop（并发 greenlet 撞车）→ 调度到真实 OS 线程 + 全新事件循环隔离执行，永不报错。
- Worker 已通过 `worker_init` / `worker_process_init` 信号自动安装 `asyncio.run` 兜底保护
  （`app/core/async_runner.py: install_worker_asyncio_guard`），即使遗漏直接调用 `asyncio.run()` 也不会再崩。
- 相关既有入口已统一改造：`api_case_tasks` / `api_doc_tasks` / `execution_tasks` / `test_plan_tasks` /
  `automation_suites` / `automation_scripts` / `supervisor` / `agents/tools/registry` / `mcp/server` / `responses_chat`。

---

## 许可证

MIT License
