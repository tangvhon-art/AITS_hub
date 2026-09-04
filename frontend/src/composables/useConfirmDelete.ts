import { Modal } from 'ant-design-vue'

/**
 * 统一删除确认（五件套 · ConfirmDelete）
 *
 * 用法::
 *
 *   const { confirmDelete } = useConfirmDelete('需求')
 *   // 模板：<a-button danger @click="confirmDelete(record, () => deleteReq(record))">删除</a-button>
 *
 * 弹窗文案统一：确认删除{resourceName} / 确定要删除「{name}」吗？
 * 按钮：删除（danger） / 取消；loading 时按钮不抖动（依赖全局 CSS）。
 */
export function useConfirmDelete(resourceName: string) {
  function confirmDelete(record: any, onOk: () => void) {
    const name = record?.title || record?.name || record?.keyword || record?.label || record?.id
    Modal.confirm({
      title: `确认删除${resourceName}`,
      content: `确定要删除「${name}」吗？`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk,
    })
  }

  return { confirmDelete }
}
