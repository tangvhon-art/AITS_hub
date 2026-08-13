import request from './request'

export interface LLMConfig {
  id: number
  name: string
  provider: string
  base_url: string
  model_name: string
  max_tokens: number
  temperature: number
  streaming: boolean
  is_default: boolean
  status: string
  priority: number
  description: string
  has_api_key: boolean
  created_at: string
}

export function getLLMConfigs() {
  return request.get<LLMConfig[]>('/llm-configs')
}

export function createLLMConfig(data: {
  name: string
  provider: string
  base_url: string
  api_key: string
  model_name: string
  max_tokens?: number
  temperature?: number
  streaming?: boolean
  is_default?: boolean
  status?: string
  priority?: number
  description?: string
}) {
  return request.post<LLMConfig>('/llm-configs', data)
}

export function updateLLMConfig(id: number, data: any) {
  return request.put<LLMConfig>(`/llm-configs/${id}`, data)
}

export function deleteLLMConfig(id: number) {
  return request.delete(`/llm-configs/${id}`)
}

export function testLLMConfig(id: number, prompt: string = '你好') {
  return request.post(`/llm-configs/${id}/test`, { prompt })
}

export function setDefaultLLMConfig(id: number) {
  return request.post<LLMConfig>(`/llm-configs/${id}/set-default`)
}
