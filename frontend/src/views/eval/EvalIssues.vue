<template>
  <div>
    <a-alert type="error" show-icon message="问题台账" description="P0（安全越狱/违规输出/业务核心失效/严重幻觉）与 P1 必须修复并复测通过后才能上线；P2/P3 纳入长期优化清单。" style="margin-bottom: 12px" />
    <a-card size="small">
      <div class="toolbar">
        <a-select v-model:value="filterLevel" style="width: 120px" allow-clear placeholder="全部级别" @change="load">
          <a-select-option value="P0">P0</a-select-option>
          <a-select-option value="P1">P1</a-select-option>
          <a-select-option value="P2">P2</a-select-option>
          <a-select-option value="P3">P3</a-select-option>
        </a-select>
        <a-select v-model:value="filterStatus" style="width: 130px" allow-clear placeholder="全部状态" @change="load">
          <a-select-option value="open">待处理</a-select-option>
          <a-select-option value="fixing">修复中</a-select-option>
          <a-select-option value="fixed">已修复</a-select-option>
          <a-select-option value="closed">已关闭</a-select-option>
        </a-select>
        <div style="flex: 1"></div>
        <a-button @click="load">刷新</a-button>
      </div>
      <a-table :data-source="list" row-key="id" :loading="loading" size="small" :pagination="{ pageSize: 10 }">
        <a-table-column title="ID" data-index="id" width="60" />
        <a-table-column title="级别" data-index="issue_level" width="70">
          <template #default="{ text }"><a-tag :color="levelColor(text)">{{ text }}</a-tag></template>
        </a-table-column>
        <a-table-column title="类型" data-index="issue_type" width="120" />
        <a-table-column title="问题" data-index="title" ellipsis />
        <a-table-column title="状态" data-index="status" width="100">
          <template #default="{ text }"><a-tag :color="statusColor(text)">{{ statusText(text) }}</a-tag></template>
        </a-table-column>
        <a-table-column title="任务ID" data-index="eval_task_id" width="80" />
        <a-table-column title="操作" width="150">
          <template #default="{ record }">
            <a-space>
              <a-button type="link" size="small" @click="open(record)">处理</a-button>
              <a-button type="link" size="small" @click="closeIssue(record)">关闭</a-button>
            </a-space>
          </template>
        </a-table-column>
      </a-table>
    </a-card>

    <a-modal v-model:open="editOpen" title="问题处理" @ok="save" :confirm-loading="saving" width="560">
      <a-form :model="current" layout="vertical">
        <a-form-item label="问题标题"><a-input v-model:value="current.title" /></a-form-item>
        <a-form-item label="问题描述"><a-textarea v-model:value="current.description" :rows="2" /></a-form-item>
        <a-form-item label="修复建议"><a-textarea v-model:value="current.fix_suggestion" :rows="2" /></a-form-item>
        <a-form-item label="复测结果"><a-textarea v-model:value="current.retest_result" :rows="2" /></a-form-item>
        <a-form-item label="状态">
          <a-select v-model:value="current.status">
            <a-select-option value="open">待处理</a-select-option>
            <a-select-option value="fixing">修复中</a-select-option>
            <a-select-option value="fixed">已修复</a-select-option>
            <a-select-option value="closed">已关闭</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { evalIssueApi } from '@/api/eval'

const list = ref<any[]>([])
const loading = ref(false)
const filterLevel = ref<string>()
const filterStatus = ref<string>()
const editOpen = ref(false)
const saving = ref(false)
const current = ref<any>({})

const levelColor = (l: string) => ({ P0: 'red', P1: 'orange', P2: 'gold', P3: 'default' } as any)[l] || 'default'
const statusText = (s: string) => ({ open: '待处理', fixing: '修复中', fixed: '已修复', closed: '已关闭', archived: '已归档' } as any)[s] || s
const statusColor = (s: string) => ({ open: 'red', fixing: 'orange', fixed: 'blue', closed: 'green', archived: 'default' } as any)[s] || 'default'

const load = async () => {
  loading.value = true
  try { list.value = await evalIssueApi.list({ issue_level: filterLevel.value, status: filterStatus.value }) } finally { loading.value = false }
}
const open = (record: any) => { current.value = { ...record }; editOpen.value = true }
const save = async () => {
  saving.value = true
  try {
    await evalIssueApi.updateStatus(current.value.id, {
      status: current.value.status, fix_suggestion: current.value.fix_suggestion, retest_result: current.value.retest_result,
    })
    message.success('已更新'); editOpen.value = false; load()
  } finally { saving.value = false }
}
const closeIssue = async (record: any) => {
  await evalIssueApi.updateStatus(record.id, { status: 'closed' })
  message.success('已关闭'); load()
}
onMounted(load)
</script>

<style scoped>
.toolbar { display: flex; gap: 8px; margin-bottom: 12px; align-items: center; }
</style>
