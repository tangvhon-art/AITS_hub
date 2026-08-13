import request from './request'

export interface TestEnvironment {
  id?: number
  project_id: number
  name: string
  base_url: string
  description?: string
  config?: Record<string, any>
  is_default?: boolean
  status?: string
  created_by?: number
  created_at?: string
  updated_at?: string
}

export interface TestPlan {
  id?: number
  project_id: number
  name: string
  description?: string
  status?: string
  priority?: string
  start_date?: string
  end_date?: string
  environment_id?: number | null
  config?: Record<string, any>
  total_cases?: number
  passed_cases?: number
  failed_cases?: number
  pass_rate?: number
  schedule_type?: string
  schedule_cron?: string
  next_run_time?: string
  created_by?: number
  created_at?: string
  updated_at?: string
}

export interface TestPlanCase {
  id: number
  plan_id: number
  case_id: number
  sort_order: number
  status: string
  run_id?: number | null
  case_title?: string
  case_priority?: string
}

export interface TestPlanListResponse {
  total: number
  page: number
  page_size: number
  items: TestPlan[]
}

// 测试环境
export function getEnvironments(projectId: number) {
  return request.get<TestEnvironment[]>(`/projects/${projectId}/environments`)
}

export function createEnvironment(projectId: number, data: Partial<TestEnvironment>) {
  return request.post<TestEnvironment>(`/projects/${projectId}/environments`, data)
}

export function updateEnvironment(projectId: number, envId: number, data: Partial<TestEnvironment>) {
  return request.put<TestEnvironment>(`/projects/${projectId}/environments/${envId}`, data)
}

export function deleteEnvironment(projectId: number, envId: number) {
  return request.delete(`/projects/${projectId}/environments/${envId}`)
}

// 测试计划
export function getPlans(projectId: number, params?: { status?: string; page?: number; page_size?: number }) {
  return request.get<TestPlanListResponse>(`/projects/${projectId}/plans`, { params })
}

export function getPlan(projectId: number, planId: number) {
  return request.get<TestPlan>(`/projects/${projectId}/plans/${planId}`)
}

export function createPlan(projectId: number, data: Partial<TestPlan> & { case_ids?: number[] }) {
  return request.post<TestPlan>(`/projects/${projectId}/plans`, data)
}

export function updatePlan(projectId: number, planId: number, data: Partial<TestPlan>) {
  return request.put<TestPlan>(`/projects/${projectId}/plans/${planId}`, data)
}

export function deletePlan(projectId: number, planId: number) {
  return request.delete(`/projects/${projectId}/plans/${planId}`)
}

export function getPlanCases(projectId: number, planId: number) {
  return request.get<TestPlanCase[]>(`/projects/${projectId}/plans/${planId}/cases`)
}

export function updatePlanCases(projectId: number, planId: number, caseIds: number[]) {
  return request.post<TestPlan>(`/projects/${projectId}/plans/${planId}/cases`, { case_ids: caseIds })
}

export function executePlan(projectId: number, planId: number) {
  return request.post(`/projects/${projectId}/plans/${planId}/execute`)
}
