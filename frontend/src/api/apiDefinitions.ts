/**
 * 接口定义管理 API
 */
import request from './request'
import type { PaginatedResponse } from './types'

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

export const apiDefinitionsApi = {
  list: (projectId: number, params?: any) =>
    request.post<PaginatedResponse<ApiDefinition>>(`/projects/${projectId}/api-definitions/search`, params),
  get: (projectId: number, id: number) =>
    request.get<ApiDefinition>(`/projects/${projectId}/api-definitions/${id}`),
  create: (projectId: number, data: Partial<ApiDefinition>) =>
    request.post<ApiDefinition>(`/projects/${projectId}/api-definitions`, data),
  update: (projectId: number, id: number, data: Partial<ApiDefinition>) =>
    request.put<ApiDefinition>(`/projects/${projectId}/api-definitions/${id}`, data),
  delete: (projectId: number, id: number) =>
    request.delete(`/projects/${projectId}/api-definitions/${id}`),
  aiGenerateDoc: (projectId: number, definitionId: number, llmConfigId?: number, promptId?: number, supplementInfo?: string) => {
    const params: Record<string, number> = {}
    if (llmConfigId) params.llm_config_id = llmConfigId
    if (promptId) params.prompt_id = promptId
    return request.post<{ task_id: number; status: string }>(
      `/projects/${projectId}/api-definitions/${definitionId}/ai-generate-doc`,
      supplementInfo || null,
      { params },
    )
  },
  aiGenerateDocStatus: (projectId: number, definitionId: number, taskId: number) =>
    request.get<{ status: string; documentation: string; error: string }>(
      `/projects/${projectId}/api-definitions/${definitionId}/ai-generate-doc/${taskId}`,
    ),
}
