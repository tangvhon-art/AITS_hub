/**
 * 接口目录（模块）管理 API
 */
import request from './request'

export interface ApiModule {
  id: number
  project_id: number
  parent_id: number | null
  name: string
  sort_order: number
  children?: ApiModule[]
}

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
