import request from './request'

export interface TestCase {
  id: number
  project_id: number
  req_id: number | null
  title: string
  module: string
  priority: string
  case_type: string
  preconditions: string
  steps: any
  expected_result: string
  bdd_content: string
  status: string
  created_at: string
}

export function getCases(projectId: number, params?: { module?: string; priority?: string; status?: string }) {
  return request.post<TestCase[]>(`/projects/${projectId}/cases/search`, params)
}

export function createCase(projectId: number, data: Partial<TestCase>) {
  return request.post<TestCase>(`/projects/${projectId}/cases`, data)
}

export function batchCreateCases(projectId: number, cases: any[]) {
  return request.post<TestCase[]>(`/projects/${projectId}/cases/batch`, { cases })
}

export function batchUpdateStatus(projectId: number, caseIds: number[], status: string) {
  return request.post<{ updated: number }>(`/projects/${projectId}/cases/batch-update-status`, { case_ids: caseIds, status })
}

export function updateCase(projectId: number, caseId: number, data: Partial<TestCase>) {
  return request.put<TestCase>(`/projects/${projectId}/cases/${caseId}`, data)
}

export function deleteCase(projectId: number, caseId: number) {
  return request.delete(`/projects/${projectId}/cases/${caseId}`)
}

export function generateCases(projectId: number, data: { requirement_id?: number; content?: string; count?: number; feature_ids?: number[]; version_id?: number; llm_config_id?: number; prompt_id?: number; backend?: string }) {
  return request.post<{ task_id: number; status: string; message: string }>(`/projects/${projectId}/cases/generate`, data)
}

export function generateCasesStatus(projectId: number, taskId: number) {
  return request.get<{ status: string; case_count: number; cases_saved: number; error: string }>(
    `/projects/${projectId}/cases/generate/${taskId}`,
  )
}

// ── 需求功能点 ──────────────────────────────────────────

export interface RequirementFeature {
  id: number
  name: string
  description: string
  priority: string
  design_methods: string[]
  preconditions: string
  module_name: string
  sort_order: number
}

export interface FeatureModuleGroup {
  module_name: string
  module_desc: string
  features: RequirementFeature[]
}

export function getFeatures(projectId: number, reqId: number) {
  return request.get<{ split_status: string; modules: FeatureModuleGroup[]; total: number }>(
    `/projects/${projectId}/cases/requirements/${reqId}/features`,
  )
}

export function splitFeatures(projectId: number, reqId: number, data?: { backend?: string; llm_config_id?: number }) {
  return request.post<{ message: string; status: string }>(
    `/projects/${projectId}/cases/requirements/${reqId}/split-features`,
    data || {},
  )
}

export function updateFeature(projectId: number, featureId: number, data: Partial<RequirementFeature>) {
  return request.put(`/projects/${projectId}/cases/requirement-features/${featureId}`, data)
}

export function deleteFeature(projectId: number, featureId: number) {
  return request.delete(`/projects/${projectId}/cases/requirement-features/${featureId}`)
}

// 需求相关
export function getRequirements(projectId: number, params?: { version_id?: number; page?: number; page_size?: number; keyword?: string }) {
  return request.post(`/projects/${projectId}/requirements/search`, params)
}

export function createRequirement(projectId: number, data: { title: string; content: string; version_id?: number }) {
  return request.post(`/projects/${projectId}/requirements`, data)
}

export function updateRequirement(projectId: number, reqId: number, data: { title?: string; content?: string; status?: string; version_id?: number }) {
  return request.put(`/projects/${projectId}/requirements/${reqId}`, data)
}

export function uploadRequirement(projectId: number, file: File) {
  const form = new FormData()
  form.append('file', file)
  return request.post(`/projects/${projectId}/requirements/upload`, form, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export function deleteRequirement(projectId: number, reqId: number) {
  return request.delete(`/projects/${projectId}/requirements/${reqId}`)
}

export function generateRequirement(projectId: number, data: { description: string; llm_config_id?: number; prompt_id?: number; version_id?: number; backend?: string }) {
  return request.post<{ task_id: number; status: string; message: string }>(`/projects/${projectId}/requirements/generate`, data)
}

export function generateRequirementStatus(projectId: number, taskId: number) {
  return request.get<{ status: string; requirement_id: number | null; title: string; error: string }>(
    `/projects/${projectId}/requirements/generate/${taskId}`,
  )
}
