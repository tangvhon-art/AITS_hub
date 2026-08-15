import request from './request'

// ==================== 类型定义 ====================
export interface ApiModule {
  id: number
  project_id: number
  parent_id: number | null
  name: string
  sort_order: number
  children?: ApiModule[]
}

export interface ApiDefinition {
  id: number
  project_id: number
  module_id: number | null
  name: string
  method: string
  path: string
  description: string
  tags: string
  status: string
  headers: any[]
  query_params: any[]
  path_params: any[]
  body_type: string
  body_content: any
  response_examples: any[]
  created_by: number
  created_at: string
  updated_at: string
}

export interface ApiTestCase {
  id: number
  project_id: number
  module_id: number | null
  api_id: number | null
  name: string
  description: string
  priority: string
  tags: string
  method: string
  path: string
  headers: any[]
  query_params: any[]
  body_type: string
  body_content: any
  pre_script: string
  post_script: string
  param_source: string
  param_data: any
  created_by: number
  created_at: string
  updated_at: string
}

export interface ApiCaseAssertion {
  id: number
  case_id: number
  assert_type: string
  assert_target: string
  operator: string
  expected_value: string
  sort_order: number
  enabled: boolean
}

export interface ApiScenario {
  id: number
  project_id: number
  module_id: number | null
  plan_id: number | null
  name: string
  description: string
  environment_id: number | null
  config: any
  pre_script: string
  post_script: string
  created_by: number
  created_at: string
  updated_at: string
}

export interface ApiScenarioStep {
  id: number
  scenario_id: number
  step_type: string
  step_name: string
  sort_order: number
  enabled: boolean
  api_id: number | null
  case_id: number | null
  request_config: any
  script_content: string
  wait_seconds: number
  condition_expr: string
  loop_config: any
  pre_script: string
  post_script: string
  continue_on_failure: boolean
  max_retries: number
}

export interface ApiExecution {
  id: number
  project_id: number
  execution_type: string
  ref_id: number
  ref_name: string
  environment_id: number | null
  status: string
  total_steps: number
  passed_steps: number
  failed_steps: number
  skipped_steps: number
  pass_rate: number
  total_duration: number
  avg_duration: number
  report_id: number | null
  trigger_type: string
  executed_by: number
  started_at: string
  completed_at: string
  error_message: string
}

export interface ApiExecutionResult {
  id: number
  execution_id: number
  step_id: number | null
  step_name: string
  sort_order: number
  status: string
  request_method: string
  request_url: string
  request_headers: any
  request_body: string
  response_status: number
  response_time: number
  response_size: number
  response_headers: any
  response_body: string
  assertions: any[]
  console_log: string
  error_message: string
  retry_count: number
  started_at: string
  completed_at: string
}

export interface ApiMockExpectation {
  id: number
  project_id: number
  api_id: number | null
  name: string
  method: string
  path: string
  match_rules: any
  response_status: number
  response_headers: any
  response_body: string
  delay_ms: number
  enabled: boolean
  hit_count: number
}

export interface PaginatedResponse<T> {
  total: number
  page: number
  page_size: number
  items: T[]
}

// ==================== 目录管理 ====================
export const apiModulesApi = {
  getTree: (projectId: number) =>
    request.get<ApiModule[]>(`/projects/${projectId}/api-modules`),
  create: (projectId: number, data: Partial<ApiModule>) =>
    request.post<ApiModule>(`/projects/${projectId}/api-modules`, data),
  update: (projectId: number, id: number, data: Partial<ApiModule>) =>
    request.put<ApiModule>(`/projects/${projectId}/api-modules/${id}`, data),
  delete: (projectId: number, id: number) =>
    request.delete(`/projects/${projectId}/api-modules/${id}`),
}

// ==================== 接口定义 ====================
export const apiDefinitionsApi = {
  list: (projectId: number, params?: any) =>
    request.get<PaginatedResponse<ApiDefinition>>(`/projects/${projectId}/api-definitions`, { params }),
  get: (projectId: number, id: number) =>
    request.get<ApiDefinition>(`/projects/${projectId}/api-definitions/${id}`),
  create: (projectId: number, data: Partial<ApiDefinition>) =>
    request.post<ApiDefinition>(`/projects/${projectId}/api-definitions`, data),
  update: (projectId: number, id: number, data: Partial<ApiDefinition>) =>
    request.put<ApiDefinition>(`/projects/${projectId}/api-definitions/${id}`, data),
  delete: (projectId: number, id: number) =>
    request.delete(`/projects/${projectId}/api-definitions/${id}`),
}

// ==================== 接口调试 ====================
export const apiDebugApi = {
  send: (projectId: number, data: any) =>
    request.post<any>(`/projects/${projectId}/api-debug/send`, data),
  history: (projectId: number, limit?: number) =>
    request.get<any[]>(`/projects/${projectId}/api-debug/history`, { params: { limit } }),
  clearHistory: (projectId: number) =>
    request.delete(`/projects/${projectId}/api-debug/history`),
}

// ==================== 测试用例 ====================
export const apiCasesApi = {
  list: (projectId: number, params?: any) =>
    request.get<PaginatedResponse<ApiTestCase>>(`/projects/${projectId}/api-cases`, { params }),
  get: (projectId: number, id: number) =>
    request.get<ApiTestCase>(`/projects/${projectId}/api-cases/${id}`),
  create: (projectId: number, data: any) =>
    request.post<ApiTestCase>(`/projects/${projectId}/api-cases`, data),
  update: (projectId: number, id: number, data: any) =>
    request.put<ApiTestCase>(`/projects/${projectId}/api-cases/${id}`, data),
  delete: (projectId: number, id: number) =>
    request.delete(`/projects/${projectId}/api-cases/${id}`),
  run: (projectId: number, id: number, data: any) =>
    request.post<any>(`/projects/${projectId}/api-cases/${id}/run`, data),
  batchRun: (projectId: number, caseIds: number[]) =>
    request.post<any>(`/projects/${projectId}/api-cases/batch-run`, caseIds),
  // 断言
  listAssertions: (projectId: number, caseId: number) =>
    request.get<ApiCaseAssertion[]>(`/projects/${projectId}/api-cases/${caseId}/assertions`),
  createAssertion: (projectId: number, caseId: number, data: any) =>
    request.post<ApiCaseAssertion>(`/projects/${projectId}/api-cases/${caseId}/assertions`, data),
  updateAssertion: (projectId: number, id: number, data: any) =>
    request.put<ApiCaseAssertion>(`/projects/${projectId}/api-cases/assertions/${id}`, data),
  deleteAssertion: (projectId: number, id: number) =>
    request.delete(`/projects/${projectId}/api-cases/assertions/${id}`),
  // AI生成
  aiGenerate: (projectId: number, data: any) =>
    request.post<any>(`/projects/${projectId}/api-cases/ai-generate`, data),
  aiGenerateStatus: (projectId: number, taskId: number) =>
    request.get<any>(`/projects/${projectId}/api-cases/ai-generate/${taskId}`),
  aiGenerateSave: (projectId: number, taskId: number, data: any) =>
    request.post<any>(`/projects/${projectId}/api-cases/ai-generate/${taskId}/save`, data),
  aiGenerateBatch: (projectId: number, apiIds: number[]) =>
    request.post<any>(`/projects/${projectId}/api-cases/ai-generate/batch`, apiIds),
}

// ==================== 场景编排 ====================
export const apiScenariosApi = {
  list: (projectId: number, params?: any) =>
    request.get<PaginatedResponse<ApiScenario>>(`/projects/${projectId}/api-scenarios`, { params }),
  get: (projectId: number, id: number) =>
    request.get<ApiScenario>(`/projects/${projectId}/api-scenarios/${id}`),
  create: (projectId: number, data: any) =>
    request.post<ApiScenario>(`/projects/${projectId}/api-scenarios`, data),
  update: (projectId: number, id: number, data: any) =>
    request.put<ApiScenario>(`/projects/${projectId}/api-scenarios/${id}`, data),
  delete: (projectId: number, id: number) =>
    request.delete(`/projects/${projectId}/api-scenarios/${id}`),
  // 步骤
  listSteps: (projectId: number, scenarioId: number) =>
    request.get<ApiScenarioStep[]>(`/projects/${projectId}/api-scenarios/${scenarioId}/steps`),
  createStep: (projectId: number, scenarioId: number, data: any) =>
    request.post<ApiScenarioStep>(`/projects/${projectId}/api-scenarios/${scenarioId}/steps`, data),
  updateStep: (projectId: number, stepId: number, data: any) =>
    request.put<ApiScenarioStep>(`/projects/${projectId}/api-scenarios/steps/${stepId}`, data),
  deleteStep: (projectId: number, stepId: number) =>
    request.delete(`/projects/${projectId}/api-scenarios/steps/${stepId}`),
  reorderSteps: (projectId: number, scenarioId: number, stepIds: number[]) =>
    request.post(`/projects/${projectId}/api-scenarios/${scenarioId}/steps/reorder`, stepIds),
  // 变量
  listVariables: (projectId: number, scenarioId: number) =>
    request.get<any[]>(`/projects/${projectId}/api-scenarios/${scenarioId}/variables`),
  createVariable: (projectId: number, scenarioId: number, stepId: number, data: any) =>
    request.post<any>(`/projects/${projectId}/api-scenarios/${scenarioId}/steps/${stepId}/variables`, data),
  updateVariable: (projectId: number, variableId: number, data: any) =>
    request.put<any>(`/projects/${projectId}/api-scenarios/variables/${variableId}`, data),
  deleteVariable: (projectId: number, variableId: number) =>
    request.delete(`/projects/${projectId}/api-scenarios/variables/${variableId}`),
  // 执行
  run: (projectId: number, id: number, data: any) =>
    request.post<any>(`/projects/${projectId}/api-scenarios/${id}/run`, data),
}

// ==================== 执行记录 ====================
export const apiExecutionsApi = {
  list: (projectId: number, params?: any) =>
    request.get<PaginatedResponse<ApiExecution>>(`/projects/${projectId}/api-executions`, { params }),
  get: (projectId: number, id: number) =>
    request.get<ApiExecution>(`/projects/${projectId}/api-executions/${id}`),
  getResults: (projectId: number, id: number) =>
    request.get<ApiExecutionResult[]>(`/projects/${projectId}/api-executions/${id}/results`),
  getReport: (projectId: number, id: number) =>
    request.get<any>(`/projects/${projectId}/api-executions/${id}/report`),
}

// ==================== Mock服务 ====================
export const apiMockApi = {
  list: (projectId: number, params?: any) =>
    request.get<PaginatedResponse<ApiMockExpectation>>(`/projects/${projectId}/api-mock/expectations`, { params }),
  create: (projectId: number, data: any) =>
    request.post<ApiMockExpectation>(`/projects/${projectId}/api-mock/expectations`, data),
  update: (projectId: number, id: number, data: any) =>
    request.put<ApiMockExpectation>(`/projects/${projectId}/api-mock/expectations/${id}`, data),
  delete: (projectId: number, id: number) =>
    request.delete(`/projects/${projectId}/api-mock/expectations/${id}`),
}

// ==================== 接口导入 ====================
export const apiImportApi = {
  getFormats: (projectId: number) =>
    request.get<any>(`/projects/${projectId}/api-import/formats`),
  preview: (projectId: number, formData: FormData) =>
    request.post<any>(`/projects/${projectId}/api-import/preview`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  import: (projectId: number, formData: FormData) =>
    request.post<any>(`/projects/${projectId}/api-import`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
}

// ==================== 模型配置 ====================
export const llmConfigsApi = {
  list: () =>
    request.get<any[]>('/llm-configs'),
}

// ==================== 测试环境 ====================
export const environmentsApi = {
  list: (projectId: number) =>
    request.get<any[]>(`/projects/${projectId}/environments`),
  create: (projectId: number, data: any) =>
    request.post<any>(`/projects/${projectId}/environments`, data),
  update: (projectId: number, id: number, data: any) =>
    request.put<any>(`/projects/${projectId}/environments/${id}`, data),
  delete: (projectId: number, id: number) =>
    request.delete(`/projects/${projectId}/environments/${id}`),
}

// ==================== AI 对话（用于生成文档/脚本） ====================
export const chatApi = {
  send: (data: { message: string; project_id?: number; llm_config_id?: number; stream?: boolean }) =>
    request.post<any>('/chat', { ...data, stream: false }),
}
