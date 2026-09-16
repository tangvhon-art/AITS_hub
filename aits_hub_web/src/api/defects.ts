import request from './request'
import { BaseAPI } from './base'

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

/** 缺陷标准 CRUD 统一走 BaseAPI（URL 拼接样板消除） */
const defectApi = new BaseAPI<Defect>('/defects')

export function getDefects(projectId: number, params?: { status?: string; severity?: string; version_id?: number; title?: string; priority?: string; root_cause_category?: string; page?: number; page_size?: number }) {
  return defectApi.list(projectId, params)
}

export function getDefect(projectId: number, defectId: number) {
  return defectApi.get(projectId, defectId)
}

export function createDefect(projectId: number, data: Partial<Defect>) {
  return defectApi.create(projectId, data)
}

export function updateDefect(projectId: number, defectId: number, data: Partial<Defect>) {
  return defectApi.update(projectId, defectId, data)
}

export function deleteDefect(projectId: number, defectId: number) {
  return defectApi.remove(projectId, defectId)
}

export function updateDefectStatus(projectId: number, defectId: number, status: string) {
  return request.post<Defect>(`/projects/${projectId}/defects/${defectId}/status`, null, { params: { status } })
}
