/**
 * Mock 数据生成器 API
 */
import request from './request'

export interface MockFunction {
  name: string
  description: string
  syntax: string
  example: string
  args: string[]
}

export const mockDataApi = {
  functions: () =>
    request.get<{ functions: MockFunction[]; total: number }>('/mock-data/functions'),
  preview: (text: string) =>
    request.get<{ original: string; result: string }>('/mock-data/preview', { params: { text } }),
}
