/**
 * 剪贴板工具
 */
import { message } from 'ant-design-vue'

/**
 * 复制文本到剪贴板
 * @param text 要复制的文本
 * @param showMessage 是否显示成功提示
 * @returns 是否复制成功
 */
export async function copyToClipboard(text: string, showMessage = true): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
    } else {
      // 降级方案
      const textarea = document.createElement('textarea')
      textarea.value = text
      textarea.style.position = 'fixed'
      textarea.style.left = '-9999px'
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
    }
    if (showMessage) {
      message.success('已复制到剪贴板')
    }
    return true
  } catch (e) {
    if (showMessage) {
      message.error('复制失败')
    }
    return false
  }
}
