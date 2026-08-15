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
export const DEFECT_STATUS_COLOR: Record<string, string> = {
  open: 'red',
  in_progress: 'orange',
  resolved: 'green',
  closed: 'default',
  reopened: 'volcano',
}

export const DEFECT_STATUS_TEXT: Record<string, string> = {
  open: '待处理',
  in_progress: '处理中',
  resolved: '已解决',
  closed: '已关闭',
  reopened: '已重开',
}

export const DEFECT_STATUS_OPTIONS = [
  { label: '待处理', value: 'open' },
  { label: '处理中', value: 'in_progress' },
  { label: '已解决', value: 'resolved' },
  { label: '已关闭', value: 'closed' },
  { label: '已重开', value: 'reopened' },
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
  cancelled: 'default',
}

export const AGENT_TASK_STATUS_TEXT: Record<string, string> = {
  pending: '等待中',
  running: '执行中',
  success: '成功',
  failed: '失败',
  cancelled: '已取消',
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

// ─── 辅助函数 ───
export function colorOf(map: Record<string, string>, key: string): string {
  return map[key] || 'default'
}

export function labelOf(map: Record<string, string>, key: string): string {
  return map[key] || key
}
