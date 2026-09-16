/**
 * 全局枚举常量定义
 * 统一管理所有状态/优先级/颜色映射，消除各页面重复定义
 */

// ─── 用例优先级 ───
export const PRIORITY_COLOR: Record<string, string> = {
  P0: 'red',
  P1: 'orange',
  P2: 'blue',
  P3: 'default',
}

export const PRIORITY_OPTIONS = [
  { label: 'P0', value: 'P0' },
  { label: 'P1', value: 'P1' },
  { label: 'P2', value: 'P2' },
  { label: 'P3', value: 'P3' },
]

// ─── HTTP 方法 ───
export const METHOD_COLOR: Record<string, string> = {
  GET: 'green',
  POST: 'blue',
  PUT: 'orange',
  DELETE: 'red',
  PATCH: 'purple',
}

// ─── 执行/运行状态 ───
export const RUN_STATUS_COLOR: Record<string, string> = {
  passed: 'green',
  failed: 'red',
  partial: 'orange',
  running: 'blue',
  pending: 'default',
  skipped: 'default',
  error: 'red',
}

export const RUN_STATUS_TEXT: Record<string, string> = {
  passed: '通过',
  failed: '失败',
  partial: '部分通过',
  running: '执行中',
  pending: '等待中',
  skipped: '跳过',
  error: '错误',
}

// ─── 缺陷严重程度 ───
export const DEFECT_SEVERITY_COLOR: Record<string, string> = {
  critical: 'red',
  high: 'volcano',
  medium: 'orange',
  low: 'blue',
}

export const DEFECT_SEVERITY_TEXT: Record<string, string> = {
  critical: '严重',
  high: '高',
  medium: '中',
  low: '低',
}

export const DEFECT_SEVERITY_OPTIONS = [
  { label: '严重', value: 'critical' },
  { label: '高', value: 'high' },
  { label: '中', value: 'medium' },
  { label: '低', value: 'low' },
]

// ─── 缺陷状态 ───
// 与后端 app/models/defect.py 保持一致：open/confirmed/resolved/closed/reopened
export const DEFECT_STATUS_COLOR: Record<string, string> = {
  open: 'red',
  confirmed: 'orange',
  resolved: 'green',
  closed: 'default',
  reopened: 'volcano',
}

export const DEFECT_STATUS_TEXT: Record<string, string> = {
  open: '新建',
  confirmed: '已确认',
  resolved: '已解决',
  closed: '已关闭',
  reopened: '重新打开',
}

export const DEFECT_STATUS_OPTIONS = [
  { label: '新建', value: 'open' },
  { label: '已确认', value: 'confirmed' },
  { label: '已解决', value: 'resolved' },
  { label: '已关闭', value: 'closed' },
  { label: '重新打开', value: 'reopened' },
]

// ─── 测试计划状态 ───
export const PLAN_STATUS_COLOR: Record<string, string> = {
  draft: 'default',
  active: 'blue',
  running: 'processing',
  completed: 'green',
  archived: 'default',
}

export const PLAN_STATUS_TEXT: Record<string, string> = {
  draft: '草稿',
  active: '活跃',
  running: '执行中',
  completed: '已完成',
  archived: '已归档',
}

// ─── 通用用例状态 ───
export const CASE_STATUS_COLOR: Record<string, string> = {
  active: 'green',
  draft: 'default',
  deprecated: 'red',
}

export const CASE_STATUS_TEXT: Record<string, string> = {
  active: '活跃',
  draft: '草稿',
  deprecated: '已废弃',
}

// ─── Agent 任务状态 ───
export const AGENT_TASK_STATUS_COLOR: Record<string, string> = {
  pending: 'default',
  running: 'processing',
  success: 'green',
  failed: 'red',
  retrying: 'orange',
  canceled: 'default',
}

export const AGENT_TASK_STATUS_TEXT: Record<string, string> = {
  pending: '等待中',
  running: '执行中',
  success: '成功',
  failed: '失败',
  retrying: '重试中',
  canceled: '已取消',
}

// ─── 知识库文档状态 ───
export const KNOWLEDGE_STATUS_COLOR: Record<string, string> = {
  pending: 'default',
  indexing: 'processing',
  ready: 'green',
  failed: 'red',
}

export const KNOWLEDGE_STATUS_TEXT: Record<string, string> = {
  pending: '待处理',
  indexing: '索引中',
  ready: '就绪',
  failed: '失败',
}

// ─── 版本状态 ───
export const VERSION_STATUS_COLOR: Record<string, string> = {
  draft: 'default',
  active: 'blue',
  released: 'green',
  archived: 'default',
}

export const VERSION_STATUS_TEXT: Record<string, string> = {
  draft: '草稿',
  active: '活跃',
  released: '已发布',
  archived: '已归档',
}

// ─── AI 执行后端（local/workflow） ───
export const AI_BACKEND_COLOR: Record<string, string> = {
  local: 'default',
  workflow: 'purple',
}

export const AI_BACKEND_TEXT: Record<string, string> = {
  local: '本地',
  workflow: '外部工作流',
}

export const AI_BACKEND_OPTIONS = [
  { label: '本地执行', value: 'local' },
  { label: '外部工作流', value: 'workflow' },
]

// ─── 工作流调用阶段（phase） ───
export const WORKFLOW_PHASE_TEXT: Record<string, string> = {
  invoke: '调用',
  accept: '受理',
  callback: '回调',
  complete: '完成',
  timeout: '超时',
  fallback: '降级',
}

export const WORKFLOW_PHASE_COLOR: Record<string, string> = {
  invoke: 'blue',
  accept: 'processing',
  callback: 'cyan',
  complete: 'green',
  timeout: 'orange',
  fallback: 'volcano',
}

// ─── 工作流调用状态 ───
export const WORKFLOW_CALL_STATUS_TEXT: Record<string, string> = {
  success: '成功',
  failed: '失败',
  pending: '进行中',
}

export const WORKFLOW_CALL_STATUS_COLOR: Record<string, string> = {
  success: 'green',
  failed: 'red',
  pending: 'processing',
}

// ─── 工作流平台类型 ───
export const WORKFLOW_PLATFORM_TEXT: Record<string, string> = {
  openai_compat: 'OpenAI 兼容',
  coze: 'Coze',
  dify: 'Dify',
  n8n: 'n8n',
  custom: '自定义',
}

export const WORKFLOW_PLATFORM_COLOR: Record<string, string> = {
  openai_compat: 'blue',
  coze: 'purple',
  dify: 'green',
  n8n: 'orange',
  custom: 'default',
}

export const WORKFLOW_PLATFORM_OPTIONS = [
  { label: 'OpenAI 兼容协议', value: 'openai_compat' },
  { label: 'Coze', value: 'coze' },
  { label: 'Dify', value: 'dify' },
  { label: 'n8n', value: 'n8n' },
  { label: '自定义', value: 'custom' },
]

// ─── 工作流接入模块 ID ───
export const WORKFLOW_MODULE_TEXT: Record<string, string> = {
  'requirement.generate': '需求生成',
  'requirement.split_features': '功能点拆分',
  'case.generate': '用例生成',
  'case.review': '用例评审',
  'report.generate': '测试报告生成',
}

export const WORKFLOW_MODULE_OPTIONS = [
  { label: '需求生成', value: 'requirement.generate' },
  { label: '功能点拆分', value: 'requirement.split_features' },
  { label: '用例生成', value: 'case.generate' },
  { label: '用例评审', value: 'case.review' },
  { label: '测试报告生成', value: 'report.generate' },
]

// ─── 辅助函数 ───
export function colorOf(map: Record<string, string>, key: string): string {
  return map[key] || 'default'
}

export function labelOf(map: Record<string, string>, key: string): string {
  return map[key] || key
}
