<template>
  <a-popconfirm
    :title="title"
    :ok-text="okText"
    cancel-text="取消"
    @confirm="handleConfirm"
  >
    <a-button type="link" danger size="small">{{ buttonText }}</a-button>
  </a-popconfirm>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  title?: string
  buttonText?: string
  okText?: string
}>(), {
  title: '确定删除吗？',
  buttonText: '删除',
  okText: '确定',
})

const emit = defineEmits<{
  confirm: []
}>()

function handleConfirm() {
  emit('confirm')
}
</script>
