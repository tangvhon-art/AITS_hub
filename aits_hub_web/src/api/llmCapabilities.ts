import request from './request'

export interface ModelCapabilities {
  function_calling: boolean
  streaming: boolean
  skill_supported: boolean
  mcp_supported: boolean
  detected_at: number
  probe_error?: string
}

export const llmCapabilitiesApi = {
  get: (configId: number, force = false) =>
    request.get<ModelCapabilities>(`/llm-configs/${configId}/capabilities${force ? '?force=true' : ''}`),
}
