/**
 * AI 模型五维综合测评 API 封装
 * 统一前缀：/projects/{projectId}/eval
 */
import request from './request'

export interface EvalTarget {
  id: number
  project_id: number
  name: string
  target_type: string
  llm_config_id?: number
  agent_type?: string
  // 外部工作流：服务地址 / 调用路径 / 鉴权方式
  service_url?: string
  call_path?: string
  auth_type?: string
  auth_token?: string
  auth_header?: string
  business_scene?: string
  version_tag?: string
  description?: string
  status: string
}

export interface EvalDataset {
  id: number
  project_id: number
  name: string
  eval_type: string
  source: string
  version?: string
  case_count: number
  description?: string
  status: string
}

export interface EvalCase {
  id: number
  dataset_id: number
  project_id: number
  eval_type: string
  title: string
  prompt: string
  expected_output?: string
  ref_answer?: string
  category?: string
  difficulty: string
  tags?: string[]
  attack_type?: string
  constraints?: string
  status: string
}

export interface EvalTask {
  id: number
  project_id: number
  name: string
  target_id: number
  compare_target_id?: number
  version_id?: number
  modes?: Record<string, any>
  dataset_ids?: Record<string, number[]>
  judge_config_ids?: number[]
  settings?: Record<string, any>
  status: string
  progress: number
  summary?: Record<string, any>
  conclusion?: string
  backend: string
  agent_task_id?: number
  started_at?: string
  completed_at?: string
  created_at?: string
}

export interface EvalRun {
  id: number
  eval_task_id: number
  mode: string
  dataset_id?: number
  status: string
  total_cases: number
  passed_cases: number
  failed_cases: number
  pass_rate?: number
  score_avg?: number
  metrics?: Record<string, any>
  progress: number
}

export interface EvalResult {
  id: number
  eval_task_id: number
  eval_run_id: number
  case_id: number
  target_id?: number
  model_output?: string
  judge_scores?: any[]
  score?: number
  dimension_scores?: Record<string, number>
  manual_score?: number
  manual_comment?: string
  review_status: string
  agent_metrics?: Record<string, any>
  business_result?: Record<string, any>
  redteam_result?: string
  risk_level?: string
  trace?: any
  latency?: number
  status: string
  created_at?: string
}

export interface EvalReport {
  id: number
  eval_task_id: number
  project_id: number
  report_type: string
  title: string
  content?: string
  summary?: Record<string, any>
  conclusion?: string
  status: string
  created_at?: string
}

export interface EvalIssue {
  id: number
  eval_task_id: number
  project_id: number
  issue_level: string
  issue_type?: string
  title: string
  description?: string
  evidence?: Record<string, any>
  status: string
  owner_id?: number
  fix_suggestion?: string
  retest_result?: string
  created_at?: string
}

export interface EvalBaseline {
  id: number
  project_id: number
  target_id: number
  version_id?: number
  baseline_name: string
  eval_task_id?: number
  metrics?: Record<string, any>
}

// ═══════════ 被测对象 ═══════════
export const evalTargetApi = {
  list: (target_type?: string) =>
    request.get(`/eval/targets`, { params: { target_type } }),
  create: (data: Partial<EvalTarget>) =>
    request.post(`/eval/targets`, data),
  update: (id: number, data: Partial<EvalTarget>) =>
    request.put(`/eval/targets/${id}`, data),
  remove: (id: number) =>
    request.delete(`/eval/targets/${id}`),
}

// ═══════════ 数据集 ═══════════
export const evalDatasetApi = {
  list: (eval_type?: string) =>
    request.get(`/eval/datasets`, { params: { eval_type } }),
  create: (data: Partial<EvalDataset>) =>
    request.post(`/eval/datasets`, data),
  update: (id: number, data: Partial<EvalDataset>) =>
    request.put(`/eval/datasets/${id}`, data),
  remove: (id: number) =>
    request.delete(`/eval/datasets/${id}`),
  cases: (datasetId: number, params?: any) =>
    request.get(`/eval/datasets/${datasetId}/cases`, { params }),
  createCase: (datasetId: number, data: Partial<EvalCase>) =>
    request.post(`/eval/datasets/${datasetId}/cases`, data),
  updateCase: (id: number, data: Partial<EvalCase>) =>
    request.put(`/eval/cases/${id}`, data),
  removeCase: (id: number) =>
    request.delete(`/eval/cases/${id}`),
  importCases: (datasetId: number, cases: Partial<EvalCase>[]) =>
    request.post(`/eval/datasets/import`, { dataset_id: datasetId, cases }),
}

// ═══════════ 测评任务 ═══════════
export const evalTaskApi = {
  list: (params?: any) =>
    request.get(`/eval/tasks`, { params }),
  get: (id: number) =>
    request.get(`/eval/tasks/${id}`),
  create: (data: Partial<EvalTask>) =>
    request.post(`/eval/tasks`, data),
  run: (id: number) =>
    request.post(`/eval/tasks/${id}/run`),
  cancel: (id: number) =>
    request.post(`/eval/tasks/${id}/cancel`),
  runs: (id: number) =>
    request.get(`/eval/tasks/${id}/runs`),
  results: (id: number, params?: any) =>
    request.get(`/eval/tasks/${id}/results`, { params }),
  genReport: (id: number, report_type = 'overall') =>
    request.post(`/eval/tasks/${id}/report`, { report_type }),
  compare: (id: number, compareTaskId?: number) =>
    request.post(`/eval/tasks/${id}/compare`, { compare_task_id: compareTaskId }),
}

// ═══════════ 结果 / 人工打分 ═══════════
export const evalResultApi = {
  get: (id: number) =>
    request.get(`/eval/results/${id}`),
  manualScore: (id: number, data: { manual_score: number; manual_comment?: string; review_status?: string }) =>
    request.post(`/eval/results/${id}/manual-score`, data),
  manualQueue: () =>
    request.get(`/eval/manual-queue`),
}

// ═══════════ 红队 ═══════════
export const evalRedteamApi = {
  run: (data: { dataset_id: number; target_id?: number; concurrency?: number; settings?: any }) =>
    request.post(`/eval/redteam/run`, data),
  logs: (params?: any) =>
    request.get(`/eval/redteam/logs`, { params }),
}

// ═══════════ 报告 / 问题 / 基线 ═══════════
export const evalReportApi = {
  list: (params?: any) =>
    request.get(`/eval/reports`, { params }),
  get: (id: number) =>
    request.get(`/eval/reports/${id}`),
}

export const evalIssueApi = {
  list: (params?: any) =>
    request.get(`/eval/issues`, { params }),
  create: (data: any) =>
    request.post(`/eval/issues`, data),
  updateStatus: (id: number, data: any) =>
    request.put(`/eval/issues/${id}/status`, data),
}

export const evalBaselineApi = {
  list: (target_id?: number) =>
    request.get(`/eval/baselines`, { params: { target_id } }),
  create: (data: Partial<EvalBaseline>) =>
    request.post(`/eval/baselines`, data),
  remove: (id: number) =>
    request.delete(`/eval/baselines/${id}`),
}

// ═══════════ 看板 ═══════════
export const evalDashboardApi = {
  get: () =>
    request.get(`/eval/dashboard`),
}

// ═══════════ SSE 进度（全局） ═══════════
export function evalProgressUrl(taskId: number, token: string): string {
  return `/api/eval/tasks/${taskId}/progress?token=${token}`
}

export const EVAL_MODE_TEXT: Record<string, string> = {
  ai_judge: 'AI裁判', manual: '人工', agent: 'Agent交互',
  business: '业务落地', redteam: '对抗红队',
}

export const EVAL_MODE_COLOR: Record<string, string> = {
  ai_judge: 'blue', manual: 'purple', agent: 'cyan',
  business: 'green', redteam: 'red',
}

export const EVAL_TYPE_TEXT: Record<string, string> = {
  llm: '大模型', agent: '内置Agent', external_agent: '外部工作流', business: '业务入口',
}
