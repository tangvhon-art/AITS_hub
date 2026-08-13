import request from './request'

export interface Defect {
  id?: number
  project_id: number
  title: string
  description?: string
  severity?: string
  priority?: string
  status?: string
  root_cause?: string
  root_cause_category?: string
  reproduce_steps?: string
  expected_result?: string
  actual_result?: string
  screenshot_url?: string
  error_log?: string
  version_id?: number | null
  run_id?: number | null
  case_id?: number | null
  assignee_id?: number | null
  created_by?: number
  created_at?: string
  updated_at?: string
}

export interface DefectListResponse {
  total: number
  page: number
  page_size: number
  items: Defect[]
}

export function getDefects(projectId: number, params?: { status?: string; severity?: string; version_id?: number; page?: number; page_size?: number }) {
  return request.get<DefectListResponse>(`/projects/${projectId}/defects`, { params })
}

export function getDefect(projectId: number, defectId: number) {
  return request.get<Defect>(`/projects/${projectId}/defects/${defectId}`)
}

export function createDefect(projectId: number, data: Partial<Defect>) {
  return request.post<Defect>(`/projects/${projectId}/defects`, data)
}

export function updateDefect(projectId: number, defectId: number, data: Partial<Defect>) {
  return request.put<Defect>(`/projects/${projectId}/defects/${defectId}`, data)
}

export function deleteDefect(projectId: number, defectId: number) {
  return request.delete(`/projects/${projectId}/defects/${defectId}`)
}

export function updateDefectStatus(projectId: number, defectId: number, status: string) {
  return request.post<Defect>(`/projects/${projectId}/defects/${defectId}/status`, null, { params: { status } })
}
