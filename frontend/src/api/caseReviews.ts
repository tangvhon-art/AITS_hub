import request from './request'

export interface CaseReviewItem {
  id: number
  status: string
  input_params: Record<string, any>
  output_result: Record<string, any>
  llm_config_id: number | null
  token_usage: Record<string, any>
  error_message: string | null
  created_by: number | null
  created_at: string
  completed_at: string | null
}

export interface CaseReviewListResponse {
  total: number
  page: number
  page_size: number
  items: CaseReviewItem[]
}

export function listCaseReviews(projectId: number, params?: { page?: number; page_size?: number }) {
  return request.post<CaseReviewListResponse>(`/projects/${projectId}/case-reviews/search`, params)
}

export function getCaseReviewDetail(projectId: number, taskId: number) {
  return request.get<CaseReviewItem>(`/projects/${projectId}/case-reviews/${taskId}`)
}

export function reviewCases(
  projectId: number,
  data: { cases: any[]; requirement: string; llm_config_id?: number; prompt_id?: number },
) {
  return request.post<{ task_id: number; result: any }>(`/projects/${projectId}/cases/review`, data)
}
