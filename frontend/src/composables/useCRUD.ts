/**
 * 通用 CRUD Composable
 *
 * 封装管理页面的重复逻辑：弹窗状态、表单数据、新增/编辑切换、提交 loading、删除确认、成功提示。
 * 与 useList 配合使用可快速搭建标准管理页面。
 *
 * 用法 - 项目级资源::
 *
 *   import { useCRUD } from '@/composables/useCRUD'
 *   import { versionApi } from '@/api/projectVersions'
 *
 *   const { modalVisible, modalLoading, editingId, formData, openCreate, openEdit, closeModal, submit, handleDelete } = useCRUD({
 *     api: {
 *       create: (data) => versionApi.create(projectId, data),
 *       update: (id, data) => versionApi.update(projectId, id, data),
 *       remove: (id) => versionApi.remove(projectId, id),
 *     },
 *     resourceName: '版本',
 *     onSuccess: loadVersions,
 *   })
 *
 *   // 模板中
 *   // <a-modal v-model:open="modalVisible" :confirm-loading="modalLoading" @ok="submit">
 *   //   <a-form :model="formData">...</a-form>
 *   // </a-modal>
 */
import { ref, reactive, type Ref } from 'vue'
import { message, Modal } from 'ant-design-vue'

/** useCRUD 所需的 API 接口（已适配为统一签名） */
export interface CRUDApi<T = any> {
  create: (data: any) => Promise<T>
  update: (id: number, data: any) => Promise<T>
  remove: (id: number) => Promise<void>
}

/** useCRUD 选项 */
export interface UseCRUDOptions<T = any> {
  /** 适配后的 API 对象 */
  api: CRUDApi<T>
  /** 操作成功回调（如刷新列表） */
  onSuccess?: () => void
  /** 资源中文名称，用于提示信息 */
  resourceName?: string
  /** 提交前校验，返回 false 则阻止提交 */
  beforeSubmit?: () => boolean | Promise<boolean>
  /** 删除前确认，返回 false 则阻止删除 */
  beforeDelete?: (id: number, record?: any) => boolean | Promise<boolean>
}

/** useCRUD 返回值 */
export interface UseCRUDReturn {
  modalVisible: Ref<boolean>
  modalLoading: Ref<boolean>
  editingId: Ref<number | null>
  formData: Record<string, any>
  openCreate: (initial?: Record<string, any>) => void
  openEdit: (id: number, data: Record<string, any>) => void
  closeModal: () => void
  submit: () => Promise<void>
  handleDelete: (id: number, name?: string, record?: any) => void
}

export function useCRUD<T = any>(options: UseCRUDOptions<T>): UseCRUDReturn {
  const { api, onSuccess, resourceName = '数据', beforeSubmit, beforeDelete } = options

  const modalVisible = ref(false)
  const modalLoading = ref(false)
  const editingId = ref<number | null>(null)
  const formData = reactive<Record<string, any>>({})

  function openCreate(initial: Record<string, any> = {}) {
    editingId.value = null
    Object.keys(formData).forEach(key => delete formData[key])
    Object.assign(formData, initial)
    modalVisible.value = true
  }

  function openEdit(id: number, data: Record<string, any>) {
    editingId.value = id
    Object.keys(formData).forEach(key => delete formData[key])
    Object.assign(formData, data)
    modalVisible.value = true
  }

  function closeModal() {
    modalVisible.value = false
    editingId.value = null
  }

  async function submit() {
    if (beforeSubmit) {
      const ok = await beforeSubmit()
      if (!ok) return
    }

    modalLoading.value = true
    try {
      if (editingId.value !== null) {
        await api.update(editingId.value, { ...formData })
        message.success(`${resourceName}更新成功`)
      } else {
        await api.create({ ...formData })
        message.success(`${resourceName}创建成功`)
      }
      closeModal()
      onSuccess?.()
    } finally {
      modalLoading.value = false
    }
  }

  function handleDelete(id: number, name?: string, record?: any) {
    Modal.confirm({
      title: `确认删除${resourceName}`,
      content: name ? `确定要删除「${name}」吗？` : '确定要删除吗？此操作不可恢复。',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        if (beforeDelete) {
          const ok = await beforeDelete(id, record)
          if (!ok) return
        }
        await api.remove(id)
        message.success(`${resourceName}已删除`)
        onSuccess?.()
      },
    })
  }

  return {
    modalVisible,
    modalLoading,
    editingId,
    formData,
    openCreate,
    openEdit,
    closeModal,
    submit,
    handleDelete,
  }
}
