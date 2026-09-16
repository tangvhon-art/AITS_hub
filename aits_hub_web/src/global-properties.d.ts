import { formatDateTime, formatDate, formatRelativeTime } from './utils/date'

declare module 'vue' {
  interface ComponentCustomProperties {
    $formatDateTime: typeof formatDateTime
    $formatDate: typeof formatDate
    $formatRelativeTime: typeof formatRelativeTime
  }
}

export {}
