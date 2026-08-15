/**
 * Mock 服务 API
 */
import request from './request'
import type { PaginatedResponse } from './types'

export interface ApiMockExpectation {
  id: number
  project_id: number
  api_id: number | null
  name: string
  method: string
  path: string
  match_rules: any
  response_status: number
  response_headers: any
  response_body: string
  delay_ms: number
  enabled: boolean
  hit_count: number
}

export const apiMockApi = {
  list: (projectId: number, params?: any) =>
    request.get<PaginatedResponse<ApiMockExpectation>>(`/projects/${projectId}/api-mock/expectations`, { params }),
  create: (projectId: number, data: any) =>
    request.post<ApiMockExpectation>(`/projects/${projectId}/api-mock/expectations`, data),
  update: (projectId: number, id: number, data: any) =>
    request.put<ApiMockExpectation>(`/projects/${projectId}/api-mock/expectations/${id}`, data),
  delete: (projectId: number, id: number) =>
    request.delete(`/projects/${projectId}/api-mock/expectations/${id}`),
}
