import request from './request'

export interface TestReport {
  id?: number
  project_id: number
  title: string
  report_type?: string
  status?: string
  content?: string
  summary?: Record<string, any>
  total_cases?: number
  passed_cases?: number
  failed_cases?: number
  pass_rate?: number
  total_defects?: number
  open_defects?: number
  total_runs?: number
  avg_duration?: number
  file_url?: string
  version_id?: number | null
  created_by?: number
  created_at?: string
  updated_at?: string
}

export interface ReportListResponse {
  total: number
  page: number
  page_size: number
  items: TestReport[]
}

export function getReports(
  projectId: number,
  params?: { version_id?: number; title?: string; report_type?: string; status?: string; page?: number; page_size?: number }
) {
  return request.post<ReportListResponse>(`/projects/${projectId}/reports/search`, params)
}

export function getReport(projectId: number, reportId: number) {
  return request.get<TestReport>(`/projects/${projectId}/reports/${reportId}`)
}

export function generateReport(projectId: number, data: { title?: string; report_type?: string; version_id: number; llm_config_id?: number; prompt_id?: number }) {
  return request.post<TestReport>(`/projects/${projectId}/reports/generate`, data)
}

export function updateReport(projectId: number, reportId: number, data: Partial<TestReport>) {
  return request.put<TestReport>(`/projects/${projectId}/reports/${reportId}`, data)
}

export function deleteReport(projectId: number, reportId: number) {
  return request.delete(`/projects/${projectId}/reports/${reportId}`)
}
