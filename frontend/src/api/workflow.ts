/**
 * 外部工作流平台接入 — 前端 API
 *
 * 覆盖：平台连接 CRUD、Webhook 全局配置、模块执行后端配置、input 字段映射、调用回调日志、
 *       模块 effective 配置查询（供业务页面决定是否展示"执行方式"选项）。
 */
import request from './request'

// ── 平台连接 ──────────────────────────────────────────────

export interface WorkflowConnector {
  id: number
  name: string
  platform_type: string
  base_url: string
  auth_type: string
  auth_token_masked?: string | null
  auth_header: string
  accept_timeout: number
  status: string
  run_path: string
  created_at?: string
  updated_at?: string
}

export interface WorkflowConnectorCreate {
  name: string
  platform_type: string
  base_url: string
  auth_type?: string
  auth_token?: string
  auth_header?: string
  accept_timeout?: number
  status?: string
  run_path?: string
}

export type WorkflowConnectorUpdate = Partial<WorkflowConnectorCreate>

export function listConnectors() {
  return request.post<{ items: WorkflowConnector[]; total: number }>('/workflow/connectors/list')
}

export function createConnector(data: WorkflowConnectorCreate) {
  return request.post<WorkflowConnector>('/workflow/connectors', data)
}

export function updateConnector(id: number, data: WorkflowConnectorUpdate) {
  return request.put<WorkflowConnector>(`/workflow/connectors/${id}`, data)
}

export function deleteConnector(id: number) {
  return request.delete<{ message: string }>(`/workflow/connectors/${id}`)
}

export function getConnector(id: number) {
  return request.get<WorkflowConnector>(`/workflow/connectors/${id}`)
}

// ── Webhook 全局配置 ─────────────────────────────────────

export interface WorkflowWebhookConfig {
  id: number
  webhook_url: string
  enabled: boolean
  secret_masked?: string | null
  secret_plain?: string | null
  callback_timeout: number
  updated_at?: string
}

export interface WorkflowWebhookConfigUpdate {
  webhook_url?: string
  enabled?: boolean
  secret?: string
  regenerate_secret?: boolean
  callback_timeout?: number
}

export function getWebhookConfig() {
  return request.get<WorkflowWebhookConfig>('/workflow/webhook-config')
}

export function updateWebhookConfig(data: WorkflowWebhookConfigUpdate) {
  return request.put<WorkflowWebhookConfig>('/workflow/webhook-config', data)
}

// ── 模块执行后端配置 ─────────────────────────────────────

export interface AgentBackendConfig {
  id: number
  module_id: string
  project_id?: number | null
  default_backend: string
  connector_id?: number | null
  external_agent_id?: string | null
  page_selectable: boolean
  updated_at?: string
}

export interface AgentBackendConfigCreate {
  module_id: string
  project_id?: number | null
  default_backend?: string
  connector_id?: number | null
  external_agent_id?: string
  page_selectable?: boolean
}

export type AgentBackendConfigUpdate = Partial<AgentBackendConfigCreate>

export function listModuleConfigs() {
  return request.post<{ items: AgentBackendConfig[]; total: number }>('/workflow/module-configs/list')
}

export function upsertModuleConfig(data: AgentBackendConfigCreate) {
  return request.post<AgentBackendConfig>('/workflow/module-configs', data)
}

export function updateModuleConfig(id: number, data: AgentBackendConfigUpdate) {
  return request.put<AgentBackendConfig>(`/workflow/module-configs/${id}`, data)
}

export function deleteModuleConfig(id: number) {
  return request.delete<{ message: string }>(`/workflow/module-configs/${id}`)
}

// ── input 字段映射 ───────────────────────────────────────

export interface WorkflowInputMapping {
  id: number
  module_id: string
  aits_field: string
  external_field: string
  required: boolean
  default_value?: string | null
  updated_at?: string
}

export interface WorkflowInputMappingCreate {
  module_id: string
  aits_field: string
  external_field: string
  required?: boolean
  default_value?: string
}

export type WorkflowInputMappingUpdate = Partial<WorkflowInputMappingCreate>

export function listInputMappings(module_id?: string) {
  return request.post<{ items: WorkflowInputMapping[]; total: number }>('/workflow/mappings/list', { module_id })
}

export function upsertInputMapping(data: WorkflowInputMappingCreate) {
  return request.post<WorkflowInputMapping>('/workflow/mappings', data)
}

export function updateInputMapping(id: number, data: WorkflowInputMappingUpdate) {
  return request.put<WorkflowInputMapping>(`/workflow/mappings/${id}`, data)
}

export function deleteInputMapping(id: number) {
  return request.delete<{ message: string }>(`/workflow/mappings/${id}`)
}

// ── 调用回调日志 ─────────────────────────────────────────

export interface WorkflowCallLog {
  id: number
  agent_task_id: number
  module_id: string
  connector_id?: number | null
  uuid?: string | null
  request_json?: Record<string, any> | null
  response_json?: Record<string, any> | null
  external_task_id?: string | null
  phase: string
  status: string
  cost_ms?: number | null
  retry_times: number
  fallback_used: boolean
  error_msg?: string | null
  created_at?: string
}

export interface WorkflowCallLogListResponse {
  total: number
  page: number
  page_size: number
  items: WorkflowCallLog[]
}

export interface WorkflowCallLogQuery {
  page?: number
  page_size?: number
  agent_task_id?: number
  module_id?: string
  uuid?: string
  phase?: string
  status?: string
}

export function listCallLogs(params: WorkflowCallLogQuery = {}) {
  return request.post<WorkflowCallLogListResponse>('/workflow/call-logs/list', params)
}

// ── 模块 effective 配置（业务页面查询） ────────────────

export interface WorkflowEffectiveConfig {
  webhook_enabled: boolean
  page_selectable: boolean
  workflow_available: boolean
  default_backend: string
  module_id: string
  project_id?: number | null
}

/** 查询模块的执行后端有效配置（仅需登录，非管理员） */
export function getEffectiveBackend(module_id: string, project_id?: number) {
  return request.get<WorkflowEffectiveConfig>('/workflow/effective', {
    params: { module_id, project_id },
  })
}

// ── 项目级模块执行后端配置 ───────────────────────────────

export interface ProjectModuleEffectiveConfig {
  module_id: string
  /** 配置来源：project=项目级覆盖 / system=继承系统默认 */
  source: 'project' | 'system'
  webhook_enabled: boolean
  /** 生效配置（项目级优先，无则系统级） */
  effective: AgentBackendConfig | null
  /** 项目级配置（无则 null，表示继承系统默认） */
  project_config: AgentBackendConfig | null
  /** 系统级配置 */
  system_config: AgentBackendConfig | null
  /** 是否具备 workflow 执行条件 */
  workflow_ready: boolean
}

export interface ProjectModuleConfigListResponse {
  items: AgentBackendConfig[]
  total: number
  project_id: number
}

export interface ProjectModuleEffectiveListResponse {
  items: ProjectModuleEffectiveConfig[]
  total: number
  project_id: number
}

/** 获取项目级各模块配置（仅项目级行） */
export function listProjectModuleConfigs(projectId: number) {
  return request.get<ProjectModuleConfigListResponse>(`/projects/${projectId}/agent-backend-configs`)
}

/** 获取项目生效配置（合并系统级+项目级，供配置页展示） */
export function getProjectEffectiveConfigs(projectId: number) {
  return request.get<ProjectModuleEffectiveListResponse>(`/projects/${projectId}/agent-backend-configs/effective`)
}

/** 更新项目级某模块配置（不存在则创建） */
export function upsertProjectModuleConfig(
  projectId: number,
  moduleId: string,
  data: AgentBackendConfigUpdate,
) {
  return request.put<AgentBackendConfig>(`/projects/${projectId}/agent-backend-configs/${moduleId}`, data)
}

/** 删除项目级某模块配置（恢复继承系统级默认） */
export function deleteProjectModuleConfig(projectId: number, moduleId: string) {
  return request.delete<{ message: string }>(`/projects/${projectId}/agent-backend-configs/${moduleId}`)
}
