<template>
  <div class="notification-rules-page">
    <a-card :bordered="false" class="page-card">
      <div class="page-header">
        <div class="header-left">
          <h2 class="page-title">通知规则</h2>
          <span class="page-desc">配置事件触发条件与通知渠道的映射关系</span>
        </div>
        <div class="header-right">
          <a-select
            v-model:value="filterEvent"
            placeholder="按事件类型筛选"
            style="width: 200px; margin-right: 12px"
            allow-clear
            @change="loadRules"
          >
            <a-select-option v-for="e in eventTypes" :key="e.code" :value="e.code">
              {{ e.name }}
            </a-select-option>
          </a-select>
          <a-button type="primary" @click="openCreateModal">
            <template #icon><plus-outlined /></template>
            新建规则
          </a-button>
        </div>
      </div>

      <a-table
        :columns="columns"
        :data-source="rules"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        size="middle"
        @change="handleTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <span class="rule-name">{{ record.name }}</span>
          </template>
          <template v-else-if="column.key === 'event_code'">
            <a-tag :color="eventColor(record.event_code)">{{ eventName(record.event_code) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'channel_name'">
            {{ record.channel_name || '-' }}
          </template>
          <template v-else-if="column.key === 'conditions'">
            <span class="conditions-text">{{ conditionsSummary(record.conditions) }}</span>
          </template>
          <template v-else-if="column.key === 'enabled'">
            <a-switch
              :checked="record.enabled"
              size="small"
              @change="(val: boolean) => handleToggleEnabled(record, val)"
            />
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space>
              <a-button type="link" size="small" @click="openEditModal(record)">编辑</a-button>
              <a-popconfirm
                title="确定删除该规则吗？"
                ok-text="确定"
                cancel-text="取消"
                @confirm="handleDelete(record)"
              >
                <a-button type="link" size="small" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 新建/编辑弹窗 -->
    <a-modal
      v-model:open="modalVisible"
      :title="isEdit ? '编辑规则' : '新建规则'"
      width="600px"
      :confirm-loading="saving"
      ok-text="保存"
      cancel-text="取消"
      @ok="handleSave"
    >
      <a-form :model="formData" layout="vertical">
        <a-form-item label="规则名称" required>
          <a-input v-model:value="formData.name" placeholder="请输入规则名称，如：测试失败通知" />
        </a-form-item>
        <a-form-item label="事件类型" required>
          <a-select
            v-model:value="formData.event_code"
            placeholder="请选择触发事件类型"
            show-search
            option-filter-prop="label"
            @change="onEventChange"
          >
            <a-select-option v-for="e in eventTypes" :key="e.code" :value="e.code" :label="e.name">
              <span>{{ e.name }}</span>
              <a-tag :color="e.color" style="margin-left: 8px">{{ e.category }}</a-tag>
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="通知渠道" required>
          <a-select v-model:value="formData.channel_id" placeholder="请选择通知渠道">
            <a-select-option v-for="c in channels" :key="c.id" :value="c.id">
              {{ c.name }}（{{ typeLabel(c.channel_type) }}）
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-divider orientation="left" style="font-size: 13px">触发条件（可选）</a-divider>

        <a-form-item v-if="showFailureCondition" label="仅失败时通知">
          <a-switch v-model:checked="condOnlyFailure" />
          <span class="form-hint">开启后仅在存在失败项时发送通知</span>
        </a-form-item>
        <a-form-item v-if="showMinFailures" label="最小失败数">
          <a-input-number
            v-model:value="condMinFailures"
            :min="1"
            :max="9999"
            placeholder="失败数达到该值才通知"
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item v-if="showSeverities" label="缺陷严重程度">
          <a-select
            v-model:value="condSeverities"
            mode="multiple"
            placeholder="选择需要通知的严重程度（不选则全部通知）"
            allow-clear
          >
            <a-select-option value="致命">致命</a-select-option>
            <a-select-option value="严重">严重</a-select-option>
            <a-select-option value="一般">一般</a-select-option>
            <a-select-option value="轻微">轻微</a-select-option>
            <a-select-option value="建议">建议</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="限定项目ID">
          <a-input
            v-model:value="condProjectIds"
            placeholder="留空表示全部项目；多个ID用英文逗号分隔，如 1,2,3"
          />
        </a-form-item>

        <a-form-item label="启用规则">
          <a-switch v-model:checked="formData.enabled" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import {
  notificationApi,
  type NotificationRule,
  type NotificationChannel,
  type EventTypeInfo,
} from '@/api/notifications'

const loading = ref(false)
const saving = ref(false)
const rules = ref<NotificationRule[]>([])
const channels = ref<NotificationChannel[]>([])
const eventTypes = ref<EventTypeInfo[]>([])
const filterEvent = ref<string | undefined>(undefined)

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showTotal: (total: number) => `共 ${total} 条`,
})

const modalVisible = ref(false)
const isEdit = ref(false)
const editingId = ref<number | null>(null)

const formData = reactive({
  name: '',
  event_code: undefined as string | undefined,
  channel_id: undefined as number | undefined,
  enabled: true,
})

// 条件表单
const condOnlyFailure = ref(false)
const condMinFailures = ref<number | null>(null)
const condSeverities = ref<string[]>([])
const condProjectIds = ref('')

const columns = [
  { title: '规则名称', key: 'name', dataIndex: 'name', width: 180 },
  { title: '事件类型', key: 'event_code', dataIndex: 'event_code', width: 180 },
  { title: '通知渠道', key: 'channel_name', dataIndex: 'channel_name', width: 160 },
  { title: '触发条件', key: 'conditions', dataIndex: 'conditions' },
  { title: '启用', key: 'enabled', dataIndex: 'enabled', width: 80 },
  { title: '操作', key: 'action', width: 150 },
]

// 执行类事件显示失败条件
const executionEvents = ['plan.execution.completed', 'plan.execution.failed', 'api.scenario.completed', 'ui.suite.completed']
const defectEvents = ['defect.created', 'defect.assigned', 'defect.resolved', 'defect.closed', 'defect.reopened']

const showFailureCondition = computed(() => executionEvents.includes(formData.event_code || ''))
const showMinFailures = computed(() => executionEvents.includes(formData.event_code || ''))
const showSeverities = computed(() => defectEvents.includes(formData.event_code || ''))

function typeLabel(type: string): string {
  const map: Record<string, string> = { feishu: '飞书', dingtalk: '钉钉', wecom: '企业微信', webhook: 'Webhook' }
  return map[type] || type
}

function eventName(code: string): string {
  return eventTypes.value.find((e) => e.code === code)?.name || code
}

function eventColor(code: string): string {
  return eventTypes.value.find((e) => e.code === code)?.color || 'blue'
}

function conditionsSummary(conditions: any): string {
  if (!conditions || typeof conditions !== 'object') return '全部'
  const parts: string[] = []
  if (conditions.only_on_failure) parts.push('仅失败时')
  if (conditions.min_failures) parts.push(`失败≥${conditions.min_failures}`)
  if (conditions.severities?.length) parts.push(`严重程度:${conditions.severities.join('/')}`)
  if (conditions.project_ids?.length) parts.push(`项目:${conditions.project_ids.join(',')}`)
  return parts.length ? parts.join('；') : '全部'
}

async function loadRules() {
  loading.value = true
  try {
    const params: any = {
      page: pagination.current,
      page_size: pagination.pageSize,
    }
    if (filterEvent.value) params.event_code = filterEvent.value
    const res = await notificationApi.getRules(params)
    rules.value = res.items
    pagination.total = res.total
  } catch (e) {
    // 错误已由拦截器处理
  } finally {
    loading.value = false
  }
}

async function loadChannels() {
  try {
    channels.value = await notificationApi.getChannels()
  } catch (e) {
    // 错误已由拦截器处理
  }
}

async function loadEvents() {
  try {
    eventTypes.value = await notificationApi.getEvents()
  } catch (e) {
    // 错误已由拦截器处理
  }
}

function handleTableChange(pag: any) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadRules()
}

function resetForm() {
  formData.name = ''
  formData.event_code = undefined
  formData.channel_id = undefined
  formData.enabled = true
  condOnlyFailure.value = false
  condMinFailures.value = null
  condSeverities.value = []
  condProjectIds.value = ''
  editingId.value = null
}

function onEventChange() {
  // 切换事件时重置不相关条件
  condMinFailures.value = null
  condSeverities.value = []
}

function openCreateModal() {
  resetForm()
  isEdit.value = false
  modalVisible.value = true
}

function openEditModal(record: NotificationRule) {
  resetForm()
  isEdit.value = true
  editingId.value = record.id
  formData.name = record.name
  formData.event_code = record.event_code
  formData.channel_id = record.channel_id
  formData.enabled = record.enabled
  const cond = record.conditions || {}
  condOnlyFailure.value = !!cond.only_on_failure
  condMinFailures.value = cond.min_failures ?? null
  condSeverities.value = cond.severities || []
  condProjectIds.value = Array.isArray(cond.project_ids) ? cond.project_ids.join(',') : ''
  modalVisible.value = true
}

function buildConditions(): Record<string, any> {
  const cond: Record<string, any> = {}
  if (condOnlyFailure.value) cond.only_on_failure = true
  if (condMinFailures.value != null) cond.min_failures = condMinFailures.value
  if (condSeverities.value.length) cond.severities = condSeverities.value
  if (condProjectIds.value.trim()) {
    const ids = condProjectIds.value
      .split(',')
      .map((s) => parseInt(s.trim(), 10))
      .filter((n) => !isNaN(n))
    if (ids.length) cond.project_ids = ids
  }
  return cond
}

async function handleSave() {
  if (!formData.name.trim()) {
    message.warning('请输入规则名称')
    return
  }
  if (!formData.event_code) {
    message.warning('请选择事件类型')
    return
  }
  if (!formData.channel_id) {
    message.warning('请选择通知渠道')
    return
  }

  saving.value = true
  try {
    const payload = {
      name: formData.name,
      event_code: formData.event_code,
      channel_id: formData.channel_id,
      conditions: buildConditions(),
      enabled: formData.enabled,
    }
    if (isEdit.value && editingId.value) {
      await notificationApi.updateRule(editingId.value, payload)
      message.success('规则更新成功')
    } else {
      await notificationApi.createRule(payload)
      message.success('规则创建成功')
    }
    modalVisible.value = false
    loadRules()
  } catch (e) {
    // 错误已由拦截器处理
  } finally {
    saving.value = false
  }
}

async function handleToggleEnabled(record: NotificationRule, val: boolean) {
  try {
    await notificationApi.updateRule(record.id, { enabled: val })
    record.enabled = val
    message.success(val ? '规则已启用' : '规则已禁用')
  } catch (e) {
    // 错误已由拦截器处理
  }
}

async function handleDelete(record: NotificationRule) {
  try {
    await notificationApi.deleteRule(record.id)
    message.success('规则已删除')
    loadRules()
  } catch (e) {
    // 错误已由拦截器处理
  }
}

onMounted(() => {
  loadEvents()
  loadChannels()
  loadRules()
})
</script>

<style scoped>
.notification-rules-page {
  padding: 0;
}
.page-card {
  min-height: calc(100vh - 120px);
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}
.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #1f1f1f;
}
.page-desc {
  font-size: 13px;
  color: #8c8c8c;
  margin-left: 12px;
}
.header-left {
  display: flex;
  align-items: baseline;
}
.rule-name {
  font-weight: 500;
  color: #1f1f1f;
}
.conditions-text {
  font-size: 13px;
  color: #595959;
}
.form-hint {
  margin-left: 8px;
  font-size: 12px;
  color: #8c8c8c;
}
</style>
