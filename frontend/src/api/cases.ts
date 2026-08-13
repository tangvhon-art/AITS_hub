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
  return request.get<TestCase[]>(`/projects/${projectId}/cases`, { params })
}

export function createCase(projectId: number, data: Partial<TestCase>) {
  return request.post<TestCase>(`/projects/${projectId}/cases`, data)
}

export function batchCreateCases(projectId: number, cases: any[]) {
  return request.post<TestCase[]>(`/projects/${projectId}/cases/batch`, { cases })
}

export function updateCase(projectId: number, caseId: number, data: Partial<TestCase>) {
  return request.put<TestCase>(`/projects/${projectId}/cases/${caseId}`, data)
}

export function deleteCase(projectId: number, caseId: number) {
  return request.delete(`/projects/${projectId}/cases/${caseId}`)
}

export function generateCases(projectId: number, data: { requirement_id?: number; content: string; count: number; llm_config_id?: number }) {
  return request.post(`/projects/${projectId}/cases/generate`, data)
}

// 需求相关
export function getRequirements(projectId: number) {
  return request.get(`/projects/${projectId}/requirements`)
}

export function createRequirement(projectId: number, data: { title: string; content: string }) {
  return request.post(`/projects/${projectId}/requirements`, data)
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
