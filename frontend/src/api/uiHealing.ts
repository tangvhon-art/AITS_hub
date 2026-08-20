import request from './request'

// ==================== 自愈记录 ====================

export interface HealingRecord {
  id: number
  project_id: number
  script_id?: number
  run_id?: number
  step_index?: number
  page_url: string
  page_identifier: string
  original_selector: string
  action_type: string
  fail_reason: string
  healing_level: string
  healing_strategy: string
  suggested_selector: string
  ai_reasoning: string
  candidates?: any
  healing_result: string
  applied_to_script: boolean
  confirmed_by?: number
  confirmed_at?: string
  screenshot_before?: string
  screenshot_after?: string
  created_at?: string
}

export interface HealingStats {
  total: number
  success: number
  failed: number
  pending_review: number
  l1_count: number
  l2_count: number
  l3_count: number
  l4_count: number
  applied_count: number
  success_rate: number
}

export function listHealingRecords(params: {
  project_id: number
  script_id?: number
  run_id?: number
  healing_level?: string
  healing_result?: string
  page?: number
  page_size?: number
}) {
  return request.get('/ui-healing/records', { params })
}

export function getHealingRecord(id: number) {
  return request.get(`/ui-healing/records/${id}`)
}

export function confirmHealing(id: number, apply_to_script = true) {
  return request.post(`/ui-healing/records/${id}/confirm`, { apply_to_script })
}

export function getHealingStats(project_id: number): Promise<HealingStats> {
  return request.get('/ui-healing/stats', { params: { project_id } })
}

// ==================== 页面画像 ====================

export interface PageProfile {
  id: number
  project_id: number
  page_identifier: string
  page_name: string
  page_description: string
  key_elements?: any
  success_paths?: any
  failure_patterns?: any
  reachable_from?: any
  visit_count: number
  success_rate: number
  last_aggregated_at?: string
  created_at?: string
  updated_at?: string
}

export function listPageProfiles(params: {
  project_id: number
  keyword?: string
  page?: number
  page_size?: number
}) {
  return request.get('/ui-healing/page-profiles', { params })
}

export function getPageProfile(id: number): Promise<PageProfile> {
  return request.get(`/ui-healing/page-profiles/${id}`)
}

// ==================== 元素指纹 ====================

export function listElementFingerprints(params: {
  project_id: number
  page_identifier?: string
  keyword?: string
  page?: number
  page_size?: number
}) {
  return request.get('/ui-healing/element-fingerprints', { params })
}

// ==================== 手动聚合 ====================

export function triggerAggregation(project_id: number) {
  return request.post('/ui-healing/aggregate', null, { params: { project_id } })
}
