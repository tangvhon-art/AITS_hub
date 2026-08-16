import axios, { AxiosRequestConfig } from 'axios'
import { message } from 'ant-design-vue'
import router from '@/router'

const instance = axios.create({
  baseURL: '/api',
  timeout: 60000
})

// 请求拦截器
instance.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器
instance.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const status = error.response?.status
    const errorMsg = error.response?.data?.detail || error.message

    if (status === 401) {
      localStorage.removeItem('token')
      import('@/stores/user').then(({ useUserStore }) => useUserStore().logout())
      message.error('登录已过期，请重新登录')
      router.push('/login')
    } else if (status === 403) {
      message.error('没有权限执行此操作')
    } else if (status >= 500) {
      message.error(`服务器错误: ${errorMsg}`)
    } else {
      message.error(errorMsg || '请求失败')
    }

    return Promise.reject(error)
  }
)

// 类型化的请求封装，自动解包 response.data
const request = {
  get<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return instance.get(url, config) as unknown as Promise<T>
  },
  post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return instance.post(url, data, config) as unknown as Promise<T>
  },
  put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return instance.put(url, data, config) as unknown as Promise<T>
  },
  delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return instance.delete(url, config) as unknown as Promise<T>
  }
}

export default request
