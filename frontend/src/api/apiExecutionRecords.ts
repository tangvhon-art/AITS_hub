/**
 * 接口执行记录 API
 */
import request from './request'
import type { PaginatedResponse } from './types'

export interface ApiExecution {
  id: number
  project_id: number
  execution_type: string
  ref_id: number
  ref_name: string
  environment_id: number | null
  status: string
  total_steps: number
  passed_steps: number
  failed_steps: number
  skipped_steps: number
  pass_rate: number
  total_duration: number
  avg_duration: number
  report_id: number | null
  trigger_type: string
  executed_by: number
  started_at: string
  completed_at: string
  error_message: string
}

export interface ApiExecutionResult {
  id: number
  execution_id: number
  step_id: number | null
  step_name: string
  sort_order: number
  status: string
  request_method: string
  request_url: string
  request_headers: any
  request_body: string
  response_status: number
  response_time: number
  response_size: number
  response_headers: any
  response_body: string
  assertions: any[]
  console_log: string
  error_message: string
  retry_count: number
  started_at: string
  completed_at: string
}

export const apiExecutionsApi = {
  list: (projectId: number, params?: any) =>
    request.post<PaginatedResponse<ApiExecution>>(`/projects/${projectId}/api-executions/search`, params),
  get: (projectId: number, id: number) =>
    request.get<ApiExecution>(`/projects/${projectId}/api-executions/${id}`),
  getResults: (projectId: number, id: number) =>
    request.get<ApiExecutionResult[]>(`/projects/${projectId}/api-executions/${id}/results`),
  getReport: (projectId: number, id: number) =>
    request.get<any>(`/projects/${projectId}/api-executions/${id}/report`),
}
