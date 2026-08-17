/**
 * 通用 API 基类
 *
 * 提供项目级资源和全局资源的标准 CRUD 方法，消除各 API 文件中的重复样板代码。
 *
 * 用法 - 项目级资源::
 *
 *   import { BaseAPI } from './base'
 *   import type { TestCase } from './types'
 *
 *   export const caseApi = new BaseAPI<TestCase>('/cases')
 *   caseApi.list(projectId, { page: 1 })           // POST /projects/{id}/cases/search
 *   caseApi.get(projectId, 1)                      // GET  /projects/{id}/cases/1
 *   caseApi.create(projectId, data)                // POST /projects/{id}/cases
 *   caseApi.update(projectId, 1, data)             // PUT  /projects/{id}/cases/1
 *   caseApi.remove(projectId, 1)                   // DELETE /projects/{id}/cases/1
 *
 * 用法 - 全局资源（不绑定项目）::
 *
 *   export const promptApi = new BaseAPI<Prompt>('/prompts', { global: true })
 *   promptApi.listGlobal({ category: 'x' })        // POST /prompts/search
 *   promptApi.getGlobal(1)                         // GET  /prompts/1
 *   promptApi.createGlobal(data)                   // POST /prompts
 *   promptApi.updateGlobal(1, data)                // PUT  /prompts/1
 *   promptApi.removeGlobal(1)                      // DELETE /prompts/1
 */
import request from './request'
import type { PaginatedResponse } from './types'
import type { AxiosRequestConfig } from 'axios'

/** 分页查询参数 */
export interface PageParams {
  page?: number
  page_size?: number
  [key: string]: unknown
}

/** 分页结果 */
export type PageResult<T> = PaginatedResponse<T>

/** BaseAPI 构造选项 */
export interface BaseAPIOptions {
  /** 是否为全局资源（不绑定 project_id），默认 false */
  global?: boolean
}

export class BaseAPI<T = any, CreateDTO = Partial<T>, UpdateDTO = Partial<T>> {
  /** 资源路径，如 '/cases'、'/data-pools' */
  protected resourcePath: string
  /** 是否为全局资源 */
  protected isGlobal: boolean

  constructor(resourcePath: string, options: BaseAPIOptions = {}) {
    this.resourcePath = resourcePath
    this.isGlobal = options.global ?? false
  }

  /** 构建项目级资源的完整路径 */
  protected projectUrl(projectId: number, suffix = ''): string {
    return `/projects/${projectId}${this.resourcePath}${suffix}`
  }

  /** 构建全局资源的完整路径 */
  protected globalUrl(suffix = ''): string {
    return `${this.resourcePath}${suffix}`
  }

  // ──────────── 项目级资源方法 ────────────

  /** 分页查询（POST search） */
  list(projectId: number, params?: PageParams): Promise<PageResult<T>> {
    return request.post<PageResult<T>>(this.projectUrl(projectId, '/search'), params ?? {})
  }

  /** 获取单条详情 */
  get(projectId: number, id: number): Promise<T> {
    return request.get<T>(this.projectUrl(projectId, `/${id}`))
  }

  /** 创建 */
  create(projectId: number, data: CreateDTO): Promise<T> {
    return request.post<T>(this.projectUrl(projectId), data)
  }

  /** 更新 */
  update(projectId: number, id: number, data: UpdateDTO): Promise<T> {
    return request.put<T>(this.projectUrl(projectId, `/${id}`), data)
  }

  /** 删除 */
  remove(projectId: number, id: number): Promise<void> {
    return request.delete<void>(this.projectUrl(projectId, `/${id}`))
  }

  // ──────────── 全局资源方法 ────────────

  /** 全局资源分页查询（POST search） */
  listGlobal(params?: PageParams): Promise<PageResult<T>> {
    return request.post<PageResult<T>>(this.globalUrl('/search'), params ?? {})
  }

  /** 全局资源获取单条 */
  getGlobal(id: number): Promise<T> {
    return request.get<T>(this.globalUrl(`/${id}`))
  }

  /** 全局资源创建 */
  createGlobal(data: CreateDTO): Promise<T> {
    return request.post<T>(this.globalUrl(), data)
  }

  /** 全局资源更新 */
  updateGlobal(id: number, data: UpdateDTO): Promise<T> {
    return request.put<T>(this.globalUrl(`/${id}`), data)
  }

  /** 全局资源删除 */
  removeGlobal(id: number): Promise<void> {
    return request.delete<void>(this.globalUrl(`/${id}`))
  }

  // ──────────── 自定义请求 ────────────

  /** 自定义 POST 请求 */
  post<R = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<R> {
    return request.post<R>(url, data, config)
  }

  /** 自定义 GET 请求 */
  getCustom<R = any>(url: string, config?: AxiosRequestConfig): Promise<R> {
    return request.get<R>(url, config)
  }

  /** 自定义 PUT 请求 */
  put<R = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<R> {
    return request.put<R>(url, data, config)
  }

  /** 自定义 DELETE 请求 */
  delete<R = any>(url: string, config?: AxiosRequestConfig): Promise<R> {
    return request.delete<R>(url, config)
  }
}
