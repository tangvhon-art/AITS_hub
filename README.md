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
| agent配置 | 外部工作流平台接入配置（平台连接 + Webhook + 模块后端），支持系统级/项目级配置，异步调用 + 固定 Webhook 回调 + uuid 路由 |
| 事件通知 | 飞书/钉钉机器人通知，18 种事件触发，19 种卡片模板，HMAC-SHA256 验签，异步发送+重试 |
| 任务监控 | Celery + Flower 监控面板，Worker 节点状态、任务执行记录、成功/失败统计 |
| 数据池 | 测试数据管理，数据工厂生成，支持环境变量覆盖 |
| 审计日志 | 操作审计追踪 |
| 数据导入导出 | Excel 导入/导出用例，XMind 导图导出 |
| 团队协作 | 项目成员管理 + 权限控制，用户仅见参与的项目 |

---

## 外部 Agent 接入

AITS 支持将 AI 生成类任务（需求生成、功能点拆分、用例生成、用例评审、测试报告生成）委派给**外部工作流平台的 Agent** 执行，通过**异步调用 + 固定 Webhook 回调 + uuid 路由**的方式实现与本地 LLM 执行完全一致的写库闭环。

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

在 **系统管理 → agent配置** 页面进行配置：

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
- `secret`：在 AITS **agent配置 → Webhook 配置** 中生成的签名密钥

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

**Q: 外部 Agent 回调后任务一直是"等待回调"？**
检查：1) Webhook 全局开关是否启用；2) 回调请求的 uuid 是否与 AITS 调用时的 uuid 一致；3) 回调签名是否正确（X-Aits-Signature 头）；4) 回调请求体的 content 字段是否为字符串格式。

**Q: 外部 Agent 返回的 content 解析失败？**
确认 content 格式符合对应模块的要求（见上方"各模块 content 格式要求"）。需求生成支持 JSON/Markdown，功能点拆分必须为 JSON，用例生成支持 JSON/Markdown，用例评审支持 Markdown/JSON。

---

## 许可证

MIT License