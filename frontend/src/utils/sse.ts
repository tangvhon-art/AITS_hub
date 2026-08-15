/**
 * SSE（Server-Sent Events）统一封装
 *
 * 统一处理流式响应的连接、认证、消息解析和错误处理，
 * 消除 chat.ts / execution.ts 中重复的 fetch+reader / XHR polyfill 代码。
 *
 * 支持 POST 请求（原生 EventSource 仅支持 GET），自动携带 Authorization 头。
 */

export interface SSEOptions {
  method?: 'GET' | 'POST'
  headers?: Record<string, string>
  body?: any
  signal?: AbortSignal
}

export interface SSEHandlers<T = any> {
  onMessage: (data: T) => void
  onError?: (error: string) => void
  onDone?: () => void
}

/**
 * 发起 SSE 流式请求并逐行解析 data: 消息。
 *
 * @param url 请求地址（相对路径，自动加 /api 前缀）
 * @param handlers 消息回调
 * @param options 请求选项
 * @returns 用于关闭连接的 controller（调用 .abort()）
 */
export function streamSSE<T = any>(
  url: string,
  handlers: SSEHandlers<T>,
  options: SSEOptions = {},
): AbortController {
  const controller = new AbortController()
  const token = localStorage.getItem('token')
  const fullUrl = url.startsWith('http') ? url : `/api${url}`

  const fetchOptions: RequestInit = {
    method: options.method || 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
    signal: options.signal || controller.signal,
  }

  if (options.body !== undefined) {
    fetchOptions.body = typeof options.body === 'string' ? options.body : JSON.stringify(options.body)
  }

  fetch(fullUrl, fetchOptions)
    .then(async (response) => {
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `SSE 连接失败: ${response.status}`)
      }
      if (!response.body) {
        throw new Error('响应不支持流式读取')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data:')) continue
          const payload = trimmed.slice(5).trim()
          if (!payload) continue
          try {
            const data = JSON.parse(payload) as T
            handlers.onMessage(data)
            // 约定：data.type === 'done' 表示流结束
            if ((data as any)?.type === 'done') {
              handlers.onDone?.()
              controller.abort()
              return
            }
            if ((data as any)?.type === 'error') {
              handlers.onError?.((data as any).message || '服务器返回错误')
            }
          } catch {
            // 非 JSON 数据，作为原始文本传递
            handlers.onMessage(payload as unknown as T)
          }
        }
      }
      handlers.onDone?.()
    })
    .catch((err: Error) => {
      if (err.name === 'AbortError') return
      handlers.onError?.(err.message || 'SSE 连接异常')
    })

  return controller
}
