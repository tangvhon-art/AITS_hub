/**
 * 通用枚举/常量统一管理
 *
 * 提供 STATUS_MAP / PRIORITY_MAP / SEVERITY_MAP 等统一结构的映射表，
 * 每个值包含 { label, color }，便于在 a-tag、a-select 等组件中直接使用。
 *
 * 用法::
 *
 *   import { STATUS_MAP, PRIORITY_MAP, SEVERITY_MAP } from '@/constants'
 *
 *   // a-tag 颜色
 *   <a-tag :color="STATUS_MAP[record.status]?.color">{{ STATUS_MAP[record.status]?.label }}</a-tag>
 *
 *   // a-select 选项
 *   <a-select-option v-for="(v, k) in PRIORITY_MAP" :key="k" :value="k">{{ v.label }}</a-select-option>
 */

// ─── 通用执行状态 ───
export interface EnumItem {
  label: string
  color: string
}

export const STATUS_MAP: Record<string, EnumItem> = {
  pending: { label: '待执行', color: 'default' },
  running: { label: '执行中', color: 'processing' },
  success: { label: '成功', color: 'success' },
  failed: { label: '失败', color: 'error' },
  skipped: { label: '已跳过', color: 'warning' },
  cancelled: { label: '已取消', color: 'default' },
  error: { label: '错误', color: 'error' },
}

// ─── 优先级 ───
export const PRIORITY_MAP: Record<string, EnumItem> = {
  P0: { label: 'P0 紧急', color: 'red' },
  P1: { label: 'P1 高', color: 'orange' },
  P2: { label: 'P2 中', color: 'blue' },
  P3: { label: 'P3 低', color: 'default' },
}

// ─── 严重程度 ───
export const SEVERITY_MAP: Record<string, EnumItem> = {
  blocker: { label: '致命', color: 'red' },
  critical: { label: '严重', color: 'orange' },
  major: { label: '一般', color: 'blue' },
  minor: { label: '轻微', color: 'default' },
  // 兼容现有缺陷模块的严重程度命名
  high: { label: '高', color: 'orange' },
  medium: { label: '中', color: 'blue' },
  low: { label: '低', color: 'default' },
}

// ─── 辅助函数 ───

/** 获取枚举标签，不存在时返回原值 */
export function getEnumLabel(map: Record<string, EnumItem>, key: string): string {
  return map[key]?.label ?? key
}

/** 获取枚举颜色，不存在时返回 'default' */
export function getEnumColor(map: Record<string, EnumItem>, key: string): string {
  return map[key]?.color ?? 'default'
}

/** 将枚举映射转换为 a-select 选项数组 */
export function enumToOptions(map: Record<string, EnumItem>) {
  return Object.entries(map).map(([value, item]) => ({
    label: item.label,
    value,
  }))
}
