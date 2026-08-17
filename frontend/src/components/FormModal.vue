<template>
  <a-modal
    :open="visible"
    :title="title"
    :confirm-loading="loading"
    :width="width"
    :ok-text="okText"
    :cancel-text="cancelText"
    :destroy-on-close="destroyOnClose"
    :mask-closable="maskClosable"
    @ok="handleOk"
    @cancel="handleCancel"
  >
    <a-form
      ref="formRef"
      :model="modelValue"
      :layout="formLayout"
      :label-col="labelCol"
      :wrapper-col="wrapperCol"
    >
      <slot />
    </a-form>
    <template #footer v-if="$slots.footer">
      <slot name="footer" />
    </template>
  </a-modal>
</template>

<script setup lang="ts">
/**
 * 通用表单弹窗组件
 *
 * 封装 a-modal + a-form，统一新增/编辑弹窗的交互模式。
 * 与 useCRUD 配合使用可快速搭建标准管理页面。
 *
 * 用法::
 *
 *   <FormModal
 *     v-model:visible="modalVisible"
 *     :title="editingId ? '编辑' : '新建'"
 *     :loading="modalLoading"
 *     :model="formData"
 *     @ok="submit"
 *   >
 *     <a-form-item label="名称" required>
 *       <a-input v-model:value="formData.name" />
 *     </a-form-item>
 *   </FormModal>
 */
import { ref, watch } from 'vue'
import type { FormInstance } from 'ant-design-vue'

const props = withDefaults(
  defineProps<{
    visible: boolean
    title?: string
    loading?: boolean
    width?: string | number
    okText?: string
    cancelText?: string
    modelValue?: Record<string, any>
    formLayout?: 'horizontal' | 'vertical' | 'inline'
    labelCol?: Record<string, number>
    wrapperCol?: Record<string, number>
    destroyOnClose?: boolean
    maskClosable?: boolean
  }>(),
  {
    title: '',
    loading: false,
    width: 600,
    okText: '确定',
    cancelText: '取消',
    modelValue: () => ({}),
    formLayout: 'vertical',
    labelCol: () => ({ span: 6 }),
    wrapperCol: () => ({ span: 18 }),
    destroyOnClose: true,
    maskClosable: false,
  },
)

const emit = defineEmits<{
  'update:visible': [value: boolean]
  ok: []
  cancel: []
}>()

const formRef = ref<FormInstance>()

function handleOk() {
  emit('ok')
}

function handleCancel() {
  emit('update:visible', false)
  emit('cancel')
}

// 弹窗打开时重置表单校验状态
watch(
  () => props.visible,
  (val) => {
    if (val) {
      // 延迟到下一帧，确保表单已渲染
      setTimeout(() => formRef.value?.clearValidate(), 0)
    }
  },
)
</script>

<style scoped>
/* 继承 Ant Design 默认样式，无需额外覆盖 */
</style>
