import request from './request'

// ==================== 类型定义 ====================

export interface TestEnvironment {
  id: number
  project_id: number
  name: string
  base_url: string
  description: string
  config: Record<string, any>
  is_default: boolean
  status: string
  created_by: number | null
  created_at: string
  updated_at: string
}

export interface TestPlanCase {
  id: number
  plan_id: number
  case_id: number
  sort_order: number
  status: string
  run_id: number | null
  case_title: string | null
  case_priority: string | null
}

export interface TestPlan {
  id: number
  project_id: number
  name: string
  description: string
  status: string
  priority: string
  start_date: string | null
  end_date: string | null
  environment_id: number | null
  config: Record<string, any>
  execution_config: Record<string, any>
  total_cases: number
  passed_cases: number
  failed_cases: number
  pass_rate: number
  last_execution_id: number | null
  last_pass_rate: number
  schedule_type: string
  schedule_cron: string | null
  version_id: number | null
  created_by: number | null
  created_at: string
  updated_at: string
}

export interface TestPlanItem {
  id: number
  plan_id: number
  item_type: string
  ref_id: number
  item_name: string
  sort_order: number
  enabled: boolean
  fail_strategy: string
  timeout: number
  max_retries: number
  config: Record<string, any>
  created_at: string
  updated_at: string
}

export interface TestPlanExecution {
  id: number
  plan_id: number
  plan_name: string
  environment_id: number | null
  environment_name: string
  status: string
  triggered_by: number | null
  started_at: string | null
  finished_at: string | null
  total_items: number
  passed_count: number
  failed_count: number
  skipped_count: number
  pass_rate: number
  error_message: string
  report_data: Record<string, any>
  created_at: string
}

export interface TestPlanExecutionResult {
  id: number
  execution_id: number
  item_id: number | null
  item_type: string
  ref_id: number | null
  item_name: string
  sort_order: number
  status: string
  started_at: string | null
  finished_at: string | null
  duration_ms: number
  request_data: Record<string, any>
  response_data: Record<string, any>
  assertions: any[]
  extracted_vars: Record<string, any>
  error_message: string
  retry_count: number
  created_at: string
}

export interface AvailableItem {
  id: number
  name: string
  method?: string
  path?: string
  priority?: string
  description?: string
  target_url?: string
  language?: string
  version?: number
  total_steps?: number
  added: boolean
}

// ==================== 节点类型工具 ====================

export function getItemTypeLabel(type: string): string {
  const map: Record<string, string> = {
    case: '用例', scenario: '场景', script: 'UI脚本', suite: '套件'
  }
  return map[type] || type
}

export function getItemTypeColor(type: string): string {
  const map: Record<string, string> = {
    case: 'blue', scenario: 'purple', script: 'magenta', suite: 'cyan'
  }
  return map[type] || 'default'
}

export function getItemTypeDetailLabel(type: string): string {
  const map: Record<string, string> = {
    case: '接口用例', scenario: '场景编排', script: 'UI自动化脚本', suite: '编排套件'
  }
  return map[type] || type
}

// ==================== 测试计划 API ====================

export const testPlansApi = {
  list: (projectId: number, params?: { status?: string; version_id?: number; keyword?: string; page?: number; page_size?: number }) =>
    request.get<{ total: number; page: number; page_size: number; items: TestPlan[] }>(`/projects/${projectId}/plans`, { params }),

  get: (projectId: number, planId: number) =>
    request.get<TestPlan>(`/projects/${projectId}/plans/${planId}`),

  create: (projectId: number, data: Partial<TestPlan> & { case_ids?: number[] }) =>
    request.post<TestPlan>(`/projects/${projectId}/plans`, data),

  update: (projectId: number, planId: number, data: Partial<TestPlan> & { case_ids?: number[] }) =>
    request.put<TestPlan>(`/projects/${projectId}/plans/${planId}`, data),

  delete: (projectId: number, planId: number) =>
    request.delete(`/projects/${projectId}/plans/${planId}`),

  // 兼容旧版用例关联
  getCases: (projectId: number, planId: number) =>
    request.get<any[]>(`/projects/${projectId}/plans/${planId}/cases`),

  updateCases: (projectId: number, planId: number, caseIds: number[]) =>
    request.post<TestPlan>(`/projects/${projectId}/plans/${planId}/cases`, { case_ids: caseIds }),
}

// ==================== 计划节点管理 API ====================

export const testPlanItemsApi = {
  list: (projectId: number, planId: number) =>
    request.get<TestPlanItem[]>(`/projects/${projectId}/plans/${planId}/items`),

  add: (projectId: number, planId: number, data: Partial<TestPlanItem>) =>
    request.post<TestPlanItem>(`/projects/${projectId}/plans/${planId}/items`, data),

  update: (projectId: number, planId: number, itemId: number, data: Partial<TestPlanItem>) =>
    request.put<TestPlanItem>(`/projects/${projectId}/plans/${planId}/items/${itemId}`, data),

  delete: (projectId: number, planId: number, itemId: number) =>
    request.delete(`/projects/${projectId}/plans/${planId}/items/${itemId}`),

  reorder: (projectId: number, planId: number, itemIds: number[]) =>
    request.post(`/projects/${projectId}/plans/${planId}/items/reorder`, { item_ids: itemIds }),

  available: (projectId: number, planId: number, params?: { item_type?: string; keyword?: string; page?: number; page_size?: number }) =>
    request.get<{ cases: AvailableItem[]; scenarios: AvailableItem[]; scripts: AvailableItem[]; suites: AvailableItem[]; total: number }>(
      `/projects/${projectId}/plans/${planId}/available-items`, { params }
    ),
}

// ==================== 执行管理 API ====================

export const testPlanExecutionsApi = {
  run: (projectId: number, planId: number) =>
    request.post<{ execution_id: number; status: string; detail: string }>(`/projects/${projectId}/plans/${planId}/run`),

  list: (projectId: number, planId: number, params?: { page?: number; page_size?: number }) =>
    request.get<{ total: number; page: number; page_size: number; items: TestPlanExecution[] }>(
      `/projects/${projectId}/plans/${planId}/executions`, { params }
    ),

  detail: (executionId: number) =>
    request.get<{ execution: TestPlanExecution; results: TestPlanExecutionResult[] }>(
      `/test-plan-executions/${executionId}`
    ),

  status: (executionId: number) =>
    request.get<{
      id: number; status: string; total_items: number; passed_count: number;
      failed_count: number; skipped_count: number; pass_rate: number;
      started_at: string | null; finished_at: string | null
    }>(`/test-plan-executions/${executionId}/status`),

  cancel: (executionId: number) =>
    request.post(`/test-plan-executions/${executionId}/cancel`),

  // 报告导出（携带鉴权 token 的下载，window.open 无法带 header）
  downloadHtml: (executionId: number) =>
    request.get<Blob>(
      `/test-plan-executions/${executionId}/report/html`,
      { responseType: 'blob' }
    ).then((blob) => triggerDownload(blob, `test_report_${executionId}.html`)),

  downloadJunit: (executionId: number) =>
    request.get<Blob>(
      `/test-plan-executions/${executionId}/report/junit`,
      { responseType: 'blob' }
    ).then((blob) => triggerDownload(blob, `test_report_${executionId}.xml`)),
}

/** 触发浏览器下载 */
function triggerDownload(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

// ==================== 测试环境 API ====================

export const getEnvironments = (projectId: number) =>
  request.get<TestEnvironment[]>(`/projects/${projectId}/environments`)

export const createEnvironment = (projectId: number, data: Partial<TestEnvironment>) =>
  request.post<TestEnvironment>(`/projects/${projectId}/environments`, data)

export const updateEnvironment = (projectId: number, id: number, data: Partial<TestEnvironment>) =>
  request.put<TestEnvironment>(`/projects/${projectId}/environments/${id}`, data)

export const deleteEnvironment = (projectId: number, id: number) =>
  request.delete(`/projects/${projectId}/environments/${id}`)
