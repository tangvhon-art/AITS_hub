import request from './request'

export interface AuditLog {
  id: number
  user_id?: number
  username?: string
  action: string
  resource_type: string
  resource_id?: number
  resource_name?: string
  detail?: Record<string, any>
  ip_address?: string
  status: string
  error_message?: string
  created_at: string
}

export interface AuditLogListResponse {
  total: number
  page: number
  page_size: number
  items: AuditLog[]
}

export function getAuditLogs(params?: {
  user_id?: number
  action?: string
  resource_type?: string
  status?: string
  page?: number
  page_size?: number
}) {
  return request.post<AuditLogListResponse>('/audit-logs/search', params)
}

export function getAuditLog(logId: number) {
  return request.get<AuditLog>(`/audit-logs/${logId}`)
}
