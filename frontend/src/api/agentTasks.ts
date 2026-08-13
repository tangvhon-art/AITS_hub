import request from './request'

export interface AgentTask {
  id: number
  project_id: number | null
  agent_type: string
  status: string
  input_params: Record<string, any>
  output_result: Record<string, any>
  llm_config_id: number | null
  token_usage: Record<string, any>
  error_message: string
  retry_count: number
  created_by: number | null
  created_at: string
  completed_at: string | null
}

export interface AgentTaskListResponse {
  total: number
  page: number
  page_size: number
  items: AgentTask[]
}

export interface TokenUsageStats {
  project_id: number
  total_prompt_tokens: number
  total_completion_tokens: number
  total_tokens: number
  estimated_cost_usd: number
  by_agent_type: Record<string, {
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
    task_count: number
  }>
  total_tasks: number
}

export function getAgentTasks(params?: {
  project_id?: number
  agent_type?: string
  status?: string
  page?: number
  page_size?: number
}) {
  return request.get<AgentTaskListResponse>('/agent-tasks', { params })
}

export function getAgentTask(taskId: number) {
  return request.get<AgentTask>(`/agent-tasks/${taskId}`)
}

export function runSupervisor(projectId: number, data: {
  requirement_content: string
  requirement_title?: string
  generate_count?: number
  target_url?: string
  llm_config_id?: number
  auto_execute?: boolean
  notification_config?: Record<string, any>
}) {
  return request.post(`/projects/${projectId}/supervisor/run`, data)
}

export function reviewCases(projectId: number, data: {
  cases: Array<Record<string, any>>
  requirement?: string
  llm_config_id?: number
}) {
  return request.post(`/projects/${projectId}/cases/review`, data)
}

export function generateBDD(projectId: number, data: {
  requirement?: string
  cases?: Array<Record<string, any>>
  feature_name?: string
  llm_config_id?: number
}) {
  return request.post(`/projects/${projectId}/cases/bdd-generate`, data)
}

export function getTokenUsage(projectId: number) {
  return request.get<TokenUsageStats>(`/projects/${projectId}/token-usage`)
}
