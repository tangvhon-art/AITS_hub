import request from './request'

export interface AutomationScript {
  id?: number
  project_id: number
  name?: string
  description?: string
  case_id?: number | null
  source_run_id?: number | null
  script_content?: string
  script_type?: string
  target_url?: string
  language?: string
  status?: string
  version?: number
  tags?: string
  last_run_status?: string | null
  last_run_at?: string | null
  total_runs?: number
  pass_count?: number
  fail_count?: number
  created_by?: number
  created_at?: string
  updated_at?: string
  ai_generate?: boolean
  llm_config_id?: number | null
}

export interface ScriptRunResult {
  run_id: number
  status: string
  duration: number
  error?: string
}

export function getScripts(projectId: number, params?: { status?: string; case_id?: number; keyword?: string }) {
  return request.get<AutomationScript[]>(`/projects/${projectId}/scripts`, { params })
}

export function getScript(projectId: number, scriptId: number) {
  return request.get<AutomationScript>(`/projects/${projectId}/scripts/${scriptId}`)
}

export function createScript(projectId: number, data: Partial<AutomationScript>) {
  return request.post<AutomationScript>(`/projects/${projectId}/scripts`, data)
}

export function updateScript(projectId: number, scriptId: number, data: Partial<AutomationScript>) {
  return request.put<AutomationScript>(`/projects/${projectId}/scripts/${scriptId}`, data)
}

export function deleteScript(projectId: number, scriptId: number) {
  return request.delete(`/projects/${projectId}/scripts/${scriptId}`)
}

export function duplicateScript(projectId: number, scriptId: number) {
  return request.post<AutomationScript>(`/projects/${projectId}/scripts/${scriptId}/duplicate`)
}

export function runScript(projectId: number, scriptId: number, params?: { headless?: boolean }) {
  return request.post<ScriptRunResult>(`/projects/${projectId}/scripts/${scriptId}/run`, params || {})
}

export function getScriptRuns(projectId: number, scriptId: number) {
  return request.get<any[]>(`/projects/${projectId}/scripts/${scriptId}/runs`)
}

export function getScriptsByCase(projectId: number, caseId: number) {
  return request.get<AutomationScript[]>(`/projects/${projectId}/scripts/by-case/${caseId}`)
}
