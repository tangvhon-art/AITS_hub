/**
 * 接口导入 API（Swagger/Postman/HAR/JMeter/Apifox）
 */
import request from './request'

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
