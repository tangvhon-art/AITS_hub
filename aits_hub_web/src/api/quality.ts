import request from './request'

export interface QualityMetrics {
  total_cases: number
  active_cases: number
  total_runs: number
  passed_runs: number
  failed_runs: number
  pass_rate: number
  total_defects: number
  open_defects: number
  resolved_defects: number
  defect_density: number
  avg_duration: number
  total_plans: number
  completed_plans: number
}

export interface TrendDataPoint {
  date: string
  value: number
}

export interface QualityTrend {
  pass_rate_trend: TrendDataPoint[]
  defect_trend: TrendDataPoint[]
  execution_trend: TrendDataPoint[]
}

export interface DefectDistributionItem {
  category: string
  count: number
}

export interface QualityDashboard {
  metrics: QualityMetrics
  trend: QualityTrend
  severity_distribution: DefectDistributionItem[]
  category_distribution: DefectDistributionItem[]
  module_pass_rate: Array<{
    module: string
    total_cases: number
    total_runs: number
    passed_runs: number
    pass_rate: number
  }>
}

export interface RiskAlertItem {
  id: string
  level: string
  title: string
  description: string
  module?: string
  metric?: string
  current_value?: number
  threshold?: number
  created_at: string
}

export interface RiskAlertResponse {
  total: number
  high: number
  medium: number
  low: number
  items: RiskAlertItem[]
}

export interface InsightResponse {
  project_id: number
  insights: string[]
  metrics: QualityMetrics
  alerts: RiskAlertResponse
  generated_at: string
}

export function getQualityMetrics(projectId: number, versionId?: number) {
  return request.get<QualityMetrics>(`/projects/${projectId}/quality/metrics`, { params: { version_id: versionId } })
}

export function getQualityTrend(projectId: number, days: number = 7, versionId?: number) {
  return request.get<QualityTrend>(`/projects/${projectId}/quality/trend`, { params: { days, version_id: versionId } })
}

export function getQualityDashboard(projectId: number, days: number = 7, versionId?: number) {
  return request.get<QualityDashboard>(`/projects/${projectId}/quality/dashboard`, { params: { days, version_id: versionId } })
}

export function getRiskAlerts(projectId: number, versionId?: number) {
  return request.get<RiskAlertResponse>(`/projects/${projectId}/quality/alerts`, { params: { version_id: versionId } })
}

export function generateInsight(projectId: number, versionId?: number) {
  return request.post<InsightResponse>(`/projects/${projectId}/quality/insight`, null, { params: { version_id: versionId } })
}
