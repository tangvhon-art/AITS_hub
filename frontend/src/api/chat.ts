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
