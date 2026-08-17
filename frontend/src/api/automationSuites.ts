import request from './request'

export interface AutomationSuite {
  id?: number
  project_id: number
  name: string
  description?: string
  plan_id?: number | null
  environment_id?: number | null
  status?: string
  total_steps?: number
  schedule_type?: string
  schedule_cron?: string
  next_run_time?: string | null
  last_run_status?: string | null
  last_run_at?: string | null
  config?: Record<string, any>
  created_by?: number
  created_at?: string
  updated_at?: string
}

export interface SuiteStep {
  id?: number
  suite_id?: number
  step_name: string
  script_id?: number | null
  case_id?: number | null
  sort_order?: number
  step_type?: string
  params?: Record<string, any>
  continue_on_failure?: boolean
  max_retries?: number
  timeout?: number
  auto_fix?: boolean
  status?: string
  created_at?: string
}

export interface SuiteRun {
  id?: number
  suite_id: number
  project_id: number
  plan_id?: number | null
  status?: string
  total_steps?: number
  passed_steps?: number
  failed_steps?: number
  skipped_steps?: number
  pass_rate?: number
  total_duration?: number
  trigger_type?: string
  executed_by?: number
  started_at?: string | null
  completed_at?: string | null
  error_message?: string
  created_at?: string
}

export interface SuiteRunResult {
  id?: number
  suite_run_id: number
  step_id?: number | null
  script_id?: number | null
  case_id?: number | null
  run_id?: number | null
  step_name?: string
  sort_order?: number
  status?: string
  duration?: number
  retry_count?: number
  error_message?: string
  screenshot_url?: string
  execution_log?: string
  started_at?: string | null
  completed_at?: string | null
}

// 套件管理
export function getSuites(projectId: number, params?: { status?: string; plan_id?: number }) {
  return request.post<AutomationSuite[]>(`/projects/${projectId}/suites/search`, params)
}

export function getSuite(projectId: number, suiteId: number) {
  return request.get<AutomationSuite>(`/projects/${projectId}/suites/${suiteId}`)
}

export function createSuite(projectId: number, data: Partial<AutomationSuite>) {
  return request.post<AutomationSuite>(`/projects/${projectId}/suites`, data)
}

export function updateSuite(projectId: number, suiteId: number, data: Partial<AutomationSuite>) {
  return request.put<AutomationSuite>(`/projects/${projectId}/suites/${suiteId}`, data)
}

export function deleteSuite(projectId: number, suiteId: number) {
  return request.delete(`/projects/${projectId}/suites/${suiteId}`)
}

// 步骤管理
export function getSuiteSteps(projectId: number, suiteId: number) {
  return request.get<SuiteStep[]>(`/projects/${projectId}/suites/${suiteId}/steps`)
}

export function batchUpdateSteps(projectId: number, suiteId: number, steps: Partial<SuiteStep>[]) {
  return request.post<SuiteStep[]>(`/projects/${projectId}/suites/${suiteId}/steps`, { steps })
}

// 执行编排
export function executeSuite(projectId: number, suiteId: number, params?: { headless?: boolean }) {
  return request.post<{ run_id: number; status: string; message: string }>(
    `/projects/${projectId}/suites/${suiteId}/execute`,
    params || {}
  )
}

// 执行记录
export function getSuiteRuns(projectId: number, suiteId: number) {
  return request.get<SuiteRun[]>(`/projects/${projectId}/suites/${suiteId}/runs`)
}

export function getSuiteRun(projectId: number, runId: number) {
  return request.get<SuiteRun>(`/projects/${projectId}/suites/runs/${runId}`)
}

export function getSuiteRunResults(projectId: number, runId: number) {
  return request.get<SuiteRunResult[]>(`/projects/${projectId}/suites/runs/${runId}/results`)
}

export function getAllSuiteRuns(projectId: number, params?: { status?: string }) {
  return request.post<SuiteRun[]>(`/projects/${projectId}/suite-runs/search`, params)
}
