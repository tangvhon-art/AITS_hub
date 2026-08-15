/**
 * 接口测试用例 API
 */
import request from './request'
import type { PaginatedResponse } from './types'

export interface ApiTestCase {
  id: number
  project_id: number
  module_id: number | null
  api_id: number | null
  name: string
  description: string
  priority: string
  tags: string
  method: string
  path: string
  headers: any[]
  query_params: any[]
  body_type: string
  body_content: any
  pre_script: string
  post_script: string
  param_source: string
  param_data: any
  created_by: number
  created_at: string
  updated_at: string
}

export interface ApiCaseAssertion {
  id: number
  case_id: number
  assert_type: string
  assert_target: string
  operator: string
  expected_value: string
  sort_order: number
  enabled: boolean
}

export const apiCasesApi = {
  list: (projectId: number, params?: any) =>
    request.get<PaginatedResponse<ApiTestCase>>(`/projects/${projectId}/api-cases`, { params }),
  get: (projectId: number, id: number) =>
    request.get<ApiTestCase>(`/projects/${projectId}/api-cases/${id}`),
  create: (projectId: number, data: any) =>
    request.post<ApiTestCase>(`/projects/${projectId}/api-cases`, data),
  update: (projectId: number, id: number, data: any) =>
    request.put<ApiTestCase>(`/projects/${projectId}/api-cases/${id}`, data),
  delete: (projectId: number, id: number) =>
    request.delete(`/projects/${projectId}/api-cases/${id}`),
  run: (projectId: number, id: number, data: any) =>
    request.post<any>(`/projects/${projectId}/api-cases/${id}/run`, data),
  batchRun: (projectId: number, caseIds: number[]) =>
    request.post<any>(`/projects/${projectId}/api-cases/batch-run`, caseIds),
  // 断言
  listAssertions: (projectId: number, caseId: number) =>
    request.get<ApiCaseAssertion[]>(`/projects/${projectId}/api-cases/${caseId}/assertions`),
  createAssertion: (projectId: number, caseId: number, data: any) =>
    request.post<ApiCaseAssertion>(`/projects/${projectId}/api-cases/${caseId}/assertions`, data),
  updateAssertion: (projectId: number, id: number, data: any) =>
    request.put<ApiCaseAssertion>(`/projects/${projectId}/api-cases/assertions/${id}`, data),
  deleteAssertion: (projectId: number, id: number) =>
    request.delete(`/projects/${projectId}/api-cases/assertions/${id}`),
  // AI生成
  aiGenerate: (projectId: number, data: any) =>
    request.post<any>(`/projects/${projectId}/api-cases/ai-generate`, data),
  aiGenerateStatus: (projectId: number, taskId: number) =>
    request.get<any>(`/projects/${projectId}/api-cases/ai-generate/${taskId}`),
  aiGenerateSave: (projectId: number, taskId: number, data: any) =>
    request.post<any>(`/projects/${projectId}/api-cases/ai-generate/${taskId}/save`, data),
  aiGenerateBatch: (projectId: number, apiIds: number[]) =>
    request.post<any>(`/projects/${projectId}/api-cases/ai-generate/batch`, apiIds),
}
