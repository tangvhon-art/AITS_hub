import request from './request'
import { BaseAPI } from './base'

export interface LLMConfig {
  id: number
  name: string
  provider: string
  base_url: string
  model_name: string
  max_tokens: number
  temperature: number
  streaming: boolean
  api_format?: string
  is_default: boolean
  status: string
  priority: number
  description: string
  has_api_key: boolean
  created_at: string
}

export interface LLMConfigCreate {
  name: string
  provider: string
  base_url: string
  api_key: string
  model_name: string
  max_tokens?: number
  temperature?: number
  streaming?: boolean
  api_format?: string
  is_default?: boolean
  status?: string
  priority?: number
  description?: string
}

export interface LLMConfigUpdate {
  name?: string
  provider?: string
  base_url?: string
  api_key?: string
  model_name?: string
  max_tokens?: number
  temperature?: number
  streaming?: boolean
  api_format?: string
  is_default?: boolean
  status?: string
  priority?: number
  description?: string
}

/** BaseAPI 实例：全局模型配置资源 */
export const llmConfigApi = new BaseAPI<LLMConfig, LLMConfigCreate, LLMConfigUpdate>('/llm-configs', { global: true })

/** 模型配置查询参数 */
export interface LLMConfigQuery {
  name?: string
  provider?: string
  model_name?: string
  streaming?: boolean
  priority?: number
  status?: string
}

/** 获取模型配置列表（非分页，后端返回数组，支持筛选） */
export function getLLMConfigs(params?: LLMConfigQuery) {
  return request.get<LLMConfig[]>('/llm-configs', { params })
}

/** 创建模型配置 */
export function createLLMConfig(data: LLMConfigCreate) {
  return llmConfigApi.createGlobal(data)
}

/** 更新模型配置 */
export function updateLLMConfig(id: number, data: LLMConfigUpdate) {
  return llmConfigApi.updateGlobal(id, data)
}

/** 删除模型配置 */
export function deleteLLMConfig(id: number) {
  return llmConfigApi.removeGlobal(id)
}

/** 测试模型配置连接 */
export function testLLMConfig(id: number, prompt: string = '你好') {
  return request.post(`/llm-configs/${id}/test`, { prompt })
}

/** 设置为默认模型 */
export function setDefaultLLMConfig(id: number) {
  return request.post<LLMConfig>(`/llm-configs/${id}/set-default`)
}
