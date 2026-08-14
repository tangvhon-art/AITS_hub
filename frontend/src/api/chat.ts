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
  },
  signal?: AbortSignal,
): Promise<void> {
  try {
    const token = localStorage.getItem('token')
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : '',
      },
      body: JSON.stringify({ ...data, stream: true }),
      signal,
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `请求失败: ${response.status}`)
    }

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            if (data.type === 'content') {
              callbacks.onContent?.(data.content)
            } else if (data.type === 'metadata') {
              callbacks.onMetadata?.(data)
            } else if (data.type === 'tool_call') {
              callbacks.onToolCall?.(data.tool_call)
            } else if (data.type === 'tool_result') {
              callbacks.onToolResult?.(data.tool_call)
            } else if (data.type === 'done') {
              callbacks.onDone?.()
            } else if (data.type === 'error') {
              callbacks.onError?.(data.message)
            }
          } catch (e) {
            // 忽略解析错误
          }
        }
      }
    }
    callbacks.onDone?.()
  } catch (error: any) {
    if (error.name === 'AbortError') {
      callbacks.onDone?.()
    } else {
      callbacks.onError?.(error.message || '网络错误')
    }
  }
}
