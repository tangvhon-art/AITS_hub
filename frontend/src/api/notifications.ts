/**
 * 通知中心 API 封装
 */
import request from './request'

// ==================== 类型定义 ====================

export interface EventTypeInfo {
  code: string
  name: string
  category: string
  level: string
  color: string
  description: string
}

export interface NotificationChannel {
  id: number
  name: string
  channel_type: string
  webhook_url: string
  sign_enabled: boolean
  enabled: boolean
  description?: string
  created_by?: number
  created_at?: string
  updated_at?: string
  secret_masked?: string
  has_secret: boolean
}

export interface NotificationChannelCreate {
  name: string
  channel_type: string
  webhook_url: string
  sign_enabled: boolean
  secret?: string
  enabled: boolean
  description?: string
}

export interface NotificationChannelUpdate {
  name?: string
  channel_type?: string
  webhook_url?: string
  sign_enabled?: boolean
  secret?: string
  enabled?: boolean
  description?: string
}

export interface NotificationRule {
  id: number
  name: string
  event_code: string
  channel_id: number
  conditions?: Record<string, any>
  receivers?: Record<string, any>
  enabled: boolean
  created_by?: number
  created_at?: string
  updated_at?: string
  channel_name?: string
}

export interface NotificationRuleCreate {
  name: string
  event_code: string
  channel_id: number
  conditions?: Record<string, any>
  receivers?: Record<string, any>
  enabled: boolean
}

export interface NotificationRuleUpdate {
  name?: string
  event_code?: string
  channel_id?: number
  conditions?: Record<string, any>
  receivers?: Record<string, any>
  enabled?: boolean
}

export interface NotificationRecord {
  id: number
  project_id?: number
  channel_id?: number
  rule_id?: number
  event_code: string
  title: string
  content?: string
  status: string
  response_code?: number
  response_body?: string
  error_message?: string
  retry_count: number
  sent_at?: string
  created_at?: string
  channel_name?: string
  event_name?: string
  duration_ms?: number
}

export interface PaginatedResponse<T> {
  total: number
  page: number
  page_size: number
  items: T[]
}

export interface TestSendResult {
  success: boolean
  status_code?: number
  message: string
  response?: any
}

// ==================== 事件类型 ====================

export const notificationApi = {
  /** 获取通知事件类型列表 */
  getEvents() {
    return request.get<EventTypeInfo[]>('/notifications/events')
  },

  // ==================== 渠道 ====================

  /** 获取渠道列表 */
  getChannels(params?: { keyword?: string; channel_type?: string; enabled?: boolean }) {
    return request.post<NotificationChannel[]>('/notifications/channels/search', params)
  },

  /** 创建渠道 */
  createChannel(data: NotificationChannelCreate) {
    return request.post<NotificationChannel>('/notifications/channels', data)
  },

  /** 更新渠道 */
  updateChannel(id: number, data: NotificationChannelUpdate) {
    return request.put<NotificationChannel>(`/notifications/channels/${id}`, data)
  },

  /** 删除渠道 */
  deleteChannel(id: number) {
    return request.delete(`/notifications/channels/${id}`)
  },

  /** 测试发送渠道消息 */
  testChannel(id: number) {
    return request.post<TestSendResult>(`/notifications/channels/${id}/test`)
  },

  // ==================== 规则 ====================

  /** 获取规则列表 */
  getRules(params?: {
    event_code?: string
    channel_id?: number
    enabled?: boolean
    keyword?: string
    page?: number
    page_size?: number
  }) {
    return request.post<PaginatedResponse<NotificationRule>>('/notifications/rules/search', params)
  },

  /** 创建规则 */
  createRule(data: NotificationRuleCreate) {
    return request.post<NotificationRule>('/notifications/rules', data)
  },

  /** 更新规则 */
  updateRule(id: number, data: NotificationRuleUpdate) {
    return request.put<NotificationRule>(`/notifications/rules/${id}`, data)
  },

  /** 删除规则 */
  deleteRule(id: number) {
    return request.delete(`/notifications/rules/${id}`)
  },

  // ==================== 记录 ====================

  /** 获取通知记录列表 */
  getRecords(params?: {
    project_id?: number
    event_code?: string
    status?: string
    channel_id?: number
    start_date?: string
    end_date?: string
    page?: number
    page_size?: number
  }) {
    return request.post<PaginatedResponse<NotificationRecord>>('/notifications/records/search', params)
  },

  /** 获取通知记录详情 */
  getRecord(id: number) {
    return request.get<NotificationRecord>(`/notifications/records/${id}`)
  },

  /** 重试发送通知 */
  retryRecord(id: number) {
    return request.post<NotificationRecord>(`/notifications/records/${id}/retry`)
  },
}

export default notificationApi
