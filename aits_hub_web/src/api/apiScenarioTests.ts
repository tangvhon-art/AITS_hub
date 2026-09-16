/**
 * 场景编排 API
 */
import request from './request'
import type { PaginatedResponse } from './types'

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

export const apiScenariosApi = {
  list: (projectId: number, params?: any) =>
    request.post<PaginatedResponse<ApiScenario>>(`/projects/${projectId}/api-scenarios/search`, params),
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
  clearStepVariables: (projectId: number, scenarioId: number, stepId: number) =>
    request.delete(`/projects/${projectId}/api-scenarios/${scenarioId}/steps/${stepId}/variables`),
  // 执行
  run: (projectId: number, id: number, data: any) =>
    request.post<any>(`/projects/${projectId}/api-scenarios/${id}/run`, data),
}
