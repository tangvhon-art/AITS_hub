/**
 * 接口调试 API
 */
import request from './request'

export const apiDebugApi = {
  send: (projectId: number, data: any) =>
    request.post<any>(`/projects/${projectId}/api-debug/send`, data),
  history: (projectId: number, limit?: number) =>
    request.get<any[]>(`/projects/${projectId}/api-debug/history`, { params: { limit } }),
  clearHistory: (projectId: number) =>
    request.delete(`/projects/${projectId}/api-debug/history`),
}
