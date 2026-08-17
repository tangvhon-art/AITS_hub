import request from './request'
import type { PaginatedResponse } from './types'

export interface PerformanceTest {
  id: number
  project_id: number
  name: string
  description: string | null
  target_type: string
  target_id: number | null
  target_url: string | null
  users: number
  spawn_rate: number
  duration: number
  headers: Record<string, any>
  body_template: string | null
  variable_config: Record<string, any>
  data_pool_id: number | null
  status: string
  environment_id: number | null
  created_by: number | null
  created_at: string | null
  updated_at: string | null
}

export interface PerformanceTestRun {
  id: number
  test_id: number
  project_id: number
  config_snapshot: Record<string, any> | null
  status: string
  started_at: string | null
  finished_at: string | null
  total_requests: number
  total_failures: number
  avg_response_time: number
  min_response_time: number
  max_response_time: number
  p50_response_time: number
  p95_response_time: number
  p99_response_time: number
  requests_per_second: number
  failure_rate: number
  stats_history: any[] | null
  error_summary: Record<string, any> | null
  triggered_by: number | null
  created_at: string | null
}

export const performanceTestsApi = {
  list: (projectId: number, params?: any) =>
    request.post<PaginatedResponse<PerformanceTest>>(`/projects/${projectId}/performance-tests/search`, params),
  get: (projectId: number, id: number) =>
    request.get<PerformanceTest>(`/projects/${projectId}/performance-tests/${id}`),
  create: (projectId: number, data: any) =>
    request.post<PerformanceTest>(`/projects/${projectId}/performance-tests`, data),
  update: (projectId: number, id: number, data: any) =>
    request.put<PerformanceTest>(`/projects/${projectId}/performance-tests/${id}`, data),
  delete: (projectId: number, id: number) =>
    request.delete(`/projects/${projectId}/performance-tests/${id}`),
  run: (projectId: number, id: number) =>
    request.post(`/projects/${projectId}/performance-tests/${id}/run`),
  stop: (projectId: number, id: number) =>
    request.post(`/projects/${projectId}/performance-tests/${id}/stop`),
  listRuns: (projectId: number, id: number, params?: any) =>
    request.get<PaginatedResponse<PerformanceTestRun>>(`/projects/${projectId}/performance-tests/${id}/runs`, { params }),
  getRun: (runId: number) =>
    request.get<PerformanceTestRun>(`/performance-test-runs/${runId}`),
  convertPreview: (projectId: number, targetType: string, targetId: number) =>
    request.get(`/projects/${projectId}/performance-tests/convert/preview`, { params: { target_type: targetType, target_id: targetId } }),
}
