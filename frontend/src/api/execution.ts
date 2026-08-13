import request from './request'

export function runExecution(projectId: number, data: {
  instruction: string
  target_url: string
  case_id?: number
  llm_config_id?: number
  headless?: boolean
}) {
  return request.post(`/projects/${projectId}/execution/run`, data)
}

export function getExecutionRuns(projectId: number, caseId?: number) {
  return request.get(`/projects/${projectId}/execution/runs`, { params: { case_id: caseId } })
}

export function getExecutionRun(projectId: number, runId: number) {
  return request.get(`/projects/${projectId}/execution/runs/${runId}`)
}

// SSE 流式执行
export function streamExecution(
  projectId: number,
  data: { instruction: string; target_url: string; headless?: boolean; llm_config_id?: number; case_id?: number },
  onMessage: (event: any) => void,
  onError?: (error: any) => void,
  onDone?: () => void
) {
  const token = localStorage.getItem('token')
  const evtSource = new EventSourcePolyfill(
    `/api/projects/${projectId}/execution/run`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(data)
    }
  )

  evtSource.onmessage = (e: any) => {
    try {
      const data = JSON.parse(e.data)
      onMessage(data)
      if (data.type === 'done') {
        evtSource.close()
        onDone?.()
      }
    } catch (err) {
      console.error('解析 SSE 消息失败', err)
    }
  }

  evtSource.onerror = (err: any) => {
    onError?.(err)
    evtSource.close()
  }

  return evtSource
}

// 简单的 EventSource Polyfill 支持 POST（简化实现）
class EventSourcePolyfill {
  private xhr: XMLHttpRequest
  onmessage: ((e: any) => void) | null = null
  onerror: ((e: any) => void) | null = null
  private readyState: number = 0

  constructor(url: string, options: any) {
    this.xhr = new XMLHttpRequest()
    this.xhr.open(options.method || 'GET', url)
    Object.entries(options.headers || {}).forEach(([k, v]) => {
      this.xhr.setRequestHeader(k, v as string)
    })
    this.xhr.responseType = 'text'

    let lastIndex = 0
    this.xhr.onprogress = () => {
      const text = this.xhr.responseText
      const lines = text.substring(lastIndex).split('\n')
      lastIndex = text.length

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          this.onmessage?.({ data: line.substring(6) })
        }
      }
    }
    this.xhr.onload = () => {
      this.readyState = 2
    }
    this.xhr.onerror = (err) => {
      this.onerror?.(err)
    }

    this.xhr.send(options.body)
    this.readyState = 1
  }

  close() {
    this.xhr.abort()
    this.readyState = 2
  }
}
