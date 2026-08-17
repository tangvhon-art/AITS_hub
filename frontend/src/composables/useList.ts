/**
 * 通用列表 Composable
 *
 * 封装列表页的重复逻辑：loading 状态、分页、筛选、数据加载、页码/每页条数切换。
 * 适用于服务端分页接口（返回 { items, total, page, page_size }）。
 *
 * 用法::
 *
 *   import { useList } from '@/composables/useList'
 *   import { dataPoolApi } from '@/api/dataPools'
 *
 *   const { loading, list, total, pagination, filters, loadData, refresh, reset, handleTableChange } = useList(
 *     (params) => dataPoolApi.list(projectId, params),
 *     { defaultParams: { keyword: '', data_type: undefined } }
 *   )
 *
 *   // 模板中
 *   // <a-table :data-source="list" :loading="loading" :pagination="{ current: pagination.current, pageSize: pagination.pageSize, total }" @change="handleTableChange" />
 */
import { ref, reactive, onMounted, type Ref } from 'vue'

/** 列表数据 fetch 函数参数 */
export interface ListFetchParams {
  page: number
  page_size: number
  [key: string]: unknown
}

/** 列表 fetch 函数返回值 */
export interface ListFetchResult<T> {
  items: T[]
  total: number
  page?: number
  page_size?: number
}

/** useList 选项 */
export interface UseListOptions<T> {
  /** 是否在 onMounted 时自动加载，默认 true */
  immediate?: boolean
  /** 默认筛选参数，reset 时恢复到此值 */
  defaultParams?: Record<string, unknown>
  /** 加载成功回调 */
  onSuccess?: (data: T[]) => void
  /** 加载失败回调 */
  onError?: (error: unknown) => void
}

/** useList 返回值 */
export interface UseListReturn<T> {
  loading: Ref<boolean>
  list: Ref<T[]>
  total: Ref<number>
  pagination: { current: number; pageSize: number }
  filters: Record<string, unknown>
  loadData: () => Promise<void>
  refresh: () => Promise<void>
  reset: () => Promise<void>
  handlePageChange: (page: number) => void
  handleSizeChange: (size: number) => void
  /** a-table @change 事件处理器，接收 { current, pageSize } 对象 */
  handleTableChange: (pag: { current: number; pageSize: number }) => void
}

export function useList<T = any>(
  fetchFn: (params: ListFetchParams) => Promise<ListFetchResult<T>>,
  options: UseListOptions<T> = {},
): UseListReturn<T> {
  const { immediate = true, defaultParams = {}, onSuccess, onError } = options

  const loading = ref(false)
  const list = ref<T[]>([]) as Ref<T[]>
  const total = ref(0)
  const pagination = reactive({ current: 1, pageSize: 20 })
  const filters = reactive<Record<string, unknown>>({ ...defaultParams })

  // 保存默认参数的深拷贝，用于 reset
  const _defaultParams = { ...defaultParams }

  async function loadData() {
    loading.value = true
    try {
      const res = await fetchFn({
        page: pagination.current,
        page_size: pagination.pageSize,
        ...filters,
      })
      list.value = res.items || []
      total.value = res.total || 0
      onSuccess?.(list.value)
    } catch (error) {
      onError?.(error)
    } finally {
      loading.value = false
    }
  }

  function handlePageChange(page: number) {
    pagination.current = page
    loadData()
  }

  function handleSizeChange(size: number) {
    pagination.pageSize = size
    pagination.current = 1
    loadData()
  }

  function handleTableChange(pag: { current: number; pageSize: number }) {
    const pageChanged = pag.current !== pagination.current
    const sizeChanged = pag.pageSize !== pagination.pageSize
    pagination.current = pag.current
    pagination.pageSize = pag.pageSize
    if (sizeChanged) {
      pagination.current = 1
    }
    if (pageChanged || sizeChanged) {
      loadData()
    }
  }

  async function reset() {
    Object.keys(filters).forEach(key => delete filters[key])
    Object.assign(filters, _defaultParams)
    pagination.current = 1
    await loadData()
  }

  function refresh() {
    return loadData()
  }

  if (immediate) {
    onMounted(loadData)
  }

  return {
    loading,
    list,
    total,
    pagination,
    filters,
    loadData,
    refresh,
    reset,
    handlePageChange,
    handleSizeChange,
    handleTableChange,
  }
}
