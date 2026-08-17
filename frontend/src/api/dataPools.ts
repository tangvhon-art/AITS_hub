import request from './request'
import type { PaginatedResponse } from './types'

export interface TestDataPool {
  id: number
  project_id: number
  name: string
  description: string | null
  data_type: string
  schema: any[]
  data: any[]
  generator_config: Record<string, any>
  environment_id: number | null
  created_by: number | null
  created_at: string | null
  updated_at: string | null
}

export interface EnvironmentVariable {
  id: number
  project_id: number
  environment_id: number
  key: string
  value: string | null
  description: string | null
  is_sensitive: boolean
}

export const dataPoolsApi = {
  list: (projectId: number, params?: any) =>
    request.post<PaginatedResponse<TestDataPool>>(`/projects/${projectId}/data-pools/search`, params),
  get: (projectId: number, id: number) =>
    request.get<TestDataPool>(`/projects/${projectId}/data-pools/${id}`),
  create: (projectId: number, data: any) =>
    request.post<TestDataPool>(`/projects/${projectId}/data-pools`, data),
  update: (projectId: number, id: number, data: any) =>
    request.put<TestDataPool>(`/projects/${projectId}/data-pools/${id}`, data),
  delete: (projectId: number, id: number) =>
    request.delete(`/projects/${projectId}/data-pools/${id}`),
  generate: (projectId: number, id: number, count: number = 10) =>
    request.post(`/projects/${projectId}/data-pools/${id}/generate`, {}, { params: { count } }),
  preview: (projectId: number, id: number, count: number = 5) =>
    request.get(`/projects/${projectId}/data-pools/${id}/preview`, { params: { count } }),
}

export const envVariablesApi = {
  list: (projectId: number, envId: number) =>
    request.get<EnvironmentVariable[]>(`/projects/${projectId}/environments/${envId}/variables`),
  upsert: (projectId: number, envId: number, data: any) =>
    request.post(`/projects/${projectId}/environments/${envId}/variables`, data),
  delete: (projectId: number, envId: number, varId: number) =>
    request.delete(`/projects/${projectId}/environments/${envId}/variables/${varId}`),
  compare: (projectId: number, envIds: number[]) =>
    request.get(`/projects/${projectId}/environments/compare`, { params: { env_ids: envIds.join(',') } }),
  clone: (projectId: number, envId: number, targetEnvId: number) =>
    request.post(`/projects/${projectId}/environments/${envId}/clone`, {}, { params: { target_env_id: targetEnvId } }),
  sync: (projectId: number, envId: number, targetEnvIds: number[], keys?: string[]) =>
    request.post(`/projects/${projectId}/environments/${envId}/sync-variables`, {}, {
      params: {
        target_env_ids: targetEnvIds.join(','),
        keys: keys?.join(','),
      },
    }),
}
