/**
 * 测试环境 API
 * 统一入口，消除 apiTest.ts 与 testPlans.ts 中的重复定义。
 */
import request from './request'

export interface TestEnvironment {
  id: number
  project_id: number
  name: string
  base_url: string
  description: string
  config: Record<string, any>
  is_default: boolean
  status: string
  created_by: number | null
  created_at: string
  updated_at: string
}

export const environmentsApi = {
  list: (projectId: number) =>
    request.get<TestEnvironment[]>(`/projects/${projectId}/environments`),

  create: (projectId: number, data: Partial<TestEnvironment>) =>
    request.post<TestEnvironment>(`/projects/${projectId}/environments`, data),

  update: (projectId: number, id: number, data: Partial<TestEnvironment>) =>
    request.put<TestEnvironment>(`/projects/${projectId}/environments/${id}`, data),

  delete: (projectId: number, id: number) =>
    request.delete(`/projects/${projectId}/environments/${id}`),
}

// 函数式导出（与 testPlans.ts 原有风格兼容）
export const getEnvironments = environmentsApi.list
export const createEnvironment = environmentsApi.create
export const updateEnvironment = environmentsApi.update
export const deleteEnvironment = environmentsApi.delete
