import request from './request'
import { BaseAPI } from './base'
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

/** BaseAPI 实例：项目级数据池资源 */
export const dataPoolApi = new BaseAPI<TestDataPool>('/data-pools')

/**
 * 兼容旧接口：dataPoolsApi 对象
 * 标准 CRUD 方法委托给 BaseAPI，自定义方法（generate/preview）保留。
 */
export const dataPoolsApi = {
  list: (projectId: number, params?: any) =>
    dataPoolApi.list(projectId, params) as Promise<PaginatedResponse<TestDataPool>>,
  get: (projectId: number, id: number) =>
    dataPoolApi.get(projectId, id),
  create: (projectId: number, data: any) =>
    dataPoolApi.create(projectId, data),
  update: (projectId: number, id: number, data: any) =>
    dataPoolApi.update(projectId, id, data),
  delete: (projectId: number, id: number) =>
    dataPoolApi.remove(projectId, id),
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
