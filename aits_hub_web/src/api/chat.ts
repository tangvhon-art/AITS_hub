import request from './request'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatRequest {
  message: string
  project_id?: number
  llm_config_id?: number
  history?: ChatMessage[]
  use_knowledge?: boolean
  stream?: boolean
  session_id?: number
}

export interface ChatSession {
  id: number
  user_id: number
  project_id?: number
  title: string
  llm_config_id?: number
  use_knowledge: boolean
  message_count: number
  last_message_at?: string
  created_at?: string
  updated_at?: string
}

export interface ChatSessionMessage {
  id: number
  session_id: number
  role: string
  content?: string
  tool_calls?: any
  knowledge_results?: any
  progress?: any
  token_usage?: any
  sort_order: number
  created_at?: string
}

export interface KnowledgeResult {
  title: string
  content: string
  score?: number
  doc_id?: number
}

export interface ToolCall {
  name: string
  args: any
  result?: any
  status?: 'running' | 'success' | 'failed'
  duration?: number
}

export interface ChatResponse {
  content: string
  knowledge_results?: KnowledgeResult[]
  tool_calls?: ToolCall[]
}

/**
 * 非流式对话
 */
export function chat(data: ChatRequest): Promise<ChatResponse> {
  return request.post('/chat', { ...data, stream: false })
}

/**
 * 流式对话（支持中断和工具调用事件）
 * 统一走 utils/sse.ts
 */
export async function chatStream(
  data: ChatRequest,
  callbacks: {
    onContent?: (chunk: string) => void
    onDone?: () => void
    onError?: (error: string) => void
    onMetadata?: (metadata: any) => void
    onToolCall?: (toolCall: ToolCall) => void
    onToolResult?: (toolCall: ToolCall) => void
    onKnowledge?: (results: KnowledgeResult[]) => void
    onProgress?: (progress: { node: string; label: string; status: string; detail?: string }) => void
    onProgressPlan?: (steps: any[]) => void
    onSession?: (sessionId: number) => void
  },
  signal?: AbortSignal,
): Promise<void> {
  const { streamSSE } = await import('@/utils/sse')
  return new Promise<void>((resolve) => {
    streamSSE(
      '/chat',
      {
        onMessage: (data: any) => {
          if (data.type === 'content') {
            callbacks.onContent?.(data.content)
          } else if (data.type === 'session') {
            callbacks.onSession?.(data.session_id)
          } else if (data.type === 'metadata') {
            callbacks.onMetadata?.(data)
          } else if (data.type === 'tool_call') {
            callbacks.onToolCall?.(data.tool_call)
          } else if (data.type === 'tool_result') {
            callbacks.onToolResult?.(data.tool_call)
          } else if (data.type === 'knowledge') {
            callbacks.onKnowledge?.(data.results || [])
          } else if (data.type === 'progress') {
            callbacks.onProgress?.({ node: data.node, label: data.label, status: data.status, detail: data.detail })
          } else if (data.type === 'progress_plan') {
            callbacks.onProgressPlan?.(data.steps || [])
          }
        },
        onError: (err) => {
          callbacks.onError?.(err)
          resolve()
        },
        onDone: () => {
          callbacks.onDone?.()
          resolve()
        },
      },
      { method: 'POST', body: { ...data, stream: true }, signal },
    )
  })
}

// ==================== 聊天历史记录 API ====================

export function listChatSessions(projectId?: number, page = 1, pageSize = 50): Promise<{ total: number; items: ChatSession[] }> {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (projectId !== undefined) params.set('project_id', String(projectId))
  return request.get(`/chat/sessions?${params.toString()}`)
}

export function getChatSession(sessionId: number): Promise<{ session: ChatSession; messages: ChatSessionMessage[] }> {
  return request.get(`/chat/sessions/${sessionId}`)
}

export function createChatSession(data: { project_id?: number; title?: string; llm_config_id?: number; use_knowledge?: boolean }): Promise<ChatSession> {
  return request.post('/chat/sessions', data)
}

export function renameChatSession(sessionId: number, title: string): Promise<ChatSession> {
  return request.put(`/chat/sessions/${sessionId}`, { title })
}

export function deleteChatSession(sessionId: number): Promise<{ message: string }> {
  return request.delete(`/chat/sessions/${sessionId}`)
}

// ==================== Skill 刷新 API ====================

export function reloadSkills(): Promise<{ success: boolean; message: string; count: number }> {
  return request.post('/skills/reload')
}
