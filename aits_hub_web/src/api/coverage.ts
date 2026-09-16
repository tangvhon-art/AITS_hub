import request from './request'

export interface CoverageData {
  id?: number
  total_apis: number
  covered_apis: number
  api_coverage_rate: number
  uncovered_apis: any[]
  total_scenarios: number
  covered_scenarios: number
  scenario_coverage_rate: number
  total_cases: number
  cases_with_api: number
  calculated_at: string | null
}

export interface CoverageConfig {
  id: number
  project_id: number
  excluded_paths: string[]
  excluded_methods: string[]
  critical_scenario_ids: number[]
  version_id: number | null
}

export const coverageApi = {
  get: (projectId: number, versionId?: number) =>
    request.get<CoverageData>(`/projects/${projectId}/coverage`, { params: versionId ? { version_id: versionId } : {} }),
  getMatrix: (projectId: number) =>
    request.get(`/projects/${projectId}/coverage/matrix`),
  getTrend: (projectId: number, days: number = 30) =>
    request.get(`/projects/${projectId}/coverage/trend`, { params: { days } }),
  recalculate: (projectId: number, versionId?: number) =>
    request.post(`/projects/${projectId}/coverage/recalculate`, {}, { params: versionId ? { version_id: versionId } : {} }),
  getUncovered: (projectId: number) =>
    request.get(`/projects/${projectId}/coverage/uncovered`),
  getConfig: (projectId: number) =>
    request.get<CoverageConfig>(`/projects/${projectId}/coverage/config`),
  updateConfig: (projectId: number, data: any) =>
    request.put<CoverageConfig>(`/projects/${projectId}/coverage/config`, data),
}
