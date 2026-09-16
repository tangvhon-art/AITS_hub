/**
 * 格式化工具函数
 */

/**
 * 格式化数字（千分位）
 */
export function formatNumber(value: number | string | undefined | null, decimals = 0): string {
  if (value === null || value === undefined || value === '') return '-'
  const num = Number(value)
  if (isNaN(num)) return '-'
  return num.toLocaleString('zh-CN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

/**
 * 格式化文件大小
 */
export function formatFileSize(bytes: number | undefined | null): string {
  if (bytes === null || bytes === undefined || bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  const size = bytes / Math.pow(1024, i)
  return `${size.toFixed(i === 0 ? 0 : 2)} ${units[i]}`
}

/**
 * 格式化耗时（秒 → 可读文本）
 */
export function formatDuration(seconds: number | undefined | null): string {
  if (seconds === null || seconds === undefined) return '-'
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const minutes = Math.floor(seconds / 60)
  const secs = Math.round(seconds % 60)
  if (minutes < 60) return `${minutes}m ${secs}s`
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  return `${hours}h ${mins}m ${secs}s`
}

/**
 * 格式化百分比
 */
export function formatPercent(value: number | undefined | null, decimals = 1): string {
  if (value === null || value === undefined || isNaN(Number(value))) return '-'
  return `${(Number(value) * 100).toFixed(decimals)}%`
}

/**
 * 截断文本
 */
export function truncate(text: string | undefined | null, maxLength = 50): string {
  if (!text) return ''
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text
}
