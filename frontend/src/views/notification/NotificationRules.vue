<template>
  <div class="notification-rules-page">
    <PageHeader title="通知规则">
      <template #extra>
        <a-button type="primary" @click="openCreateModal">
          <template #icon><plus-outlined /></template>
          新建规则
        </a-button>
      </template>
    </PageHeader>
    <a-card :bordered="false" class="page-card">
      <SearchBar @search="handleSearch" @reset="handleReset">
        <a-form layout="inline">
          <a-form-item label="事件类型">
            <a-select
              v-model:value="filterEvent"
              placeholder="按事件类型筛选"
              style="width: 200px"
              allow-clear
            >
              <a-select-option v-for="e in eventTypes" :key="e.code" :value="e.code">
                {{ e.name }}
              </a-select-option>
            </a-select>
          </a-form-item>
        </a-form>
      </SearchBar>

      <DataTable
        :columns="columns"
        :data-source="rules"
        :loading="loading"
        row-key="id"
        size="middle"
        @change="handleTableChange"
      >
        :page="pagination.current"
        :page-size="pagination.pageSize"
        :total="pagination.total"
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <span class="rule-name">{{ record.name }}</span>
          </template>
          <template v-else-if="column.key === 'event_code'">
            <div class="event-tags-cell">
              <a-tag
                v-for="code in displayEvents(record.event_code)"
                :key="code"
                :color="eventColor(code)"
              >{{ eventName(code) }}</a-tag>
              <span v-if="extraEventCount(record.event_code) > 0" class="more-count">+{{ extraEventCount(record.event_code) }}</span>
            </div>
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
              <a-button type="link" size="small" danger @click="confirmDelete(record, () => handleDelete(record))">删除</a-button>
            </a-space>
          </template>
        </template>
      </DataTable>
    </a-card>

    <!-- 新建/编辑弹窗 -->
    <FormModal
      v-model:visible="modalVisible"
      title="isEdit ? '编辑规则' : '新建规则'"
      :loading="saving"
      width="600px"
      @ok="handleSave"
    >
      <a-form-item label="规则名称" required>
          <a-input v-model:value="formData.name" placeholder="请输入规则名称，如：测试失败通知" />
        </a-form-item>
        <a-form-item label="事件类型" required>
          <a-select
            v-model:value="formData.event_code"
            mode="multiple"
            :max-tag-count="3"
            placeholder="请选择触发事件类型（支持多选）"
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
        <a-form-item label="限定项目">
          <a-select
            v-model:value="condProjectIds"
            mode="multiple"
            :max-tag-count="5"
            placeholder="不选表示全部项目"
            show-search
            option-filter-prop="label"
            allow-clear
          >
            <a-select-option v-for="p in projectOptions" :key="p.id" :value="p.id" :label="p.name">
              {{ p.name }}
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="启用规则">
          <a-switch v-model:checked="formData.enabled" />
        </a-form-item>
    </FormModal>
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
import { getProjects } from '@/api/projects'
import DataTable from '@/components/DataTable.vue'
import FormModal from '@/components/FormModal.vue'
import { useConfirmDelete } from '@/composables/useConfirmDelete'
import PageHeader from '@/components/PageHeader.vue'
import SearchBar from '@/components/SearchBar.vue'
const { confirmDelete } = useConfirmDelete('通知规则')
const loading = ref(false)
const saving = ref(false)
const rules = ref<NotificationRule[]>([])
const channels = ref<NotificationChannel[]>([])
const eventTypes = ref<EventTypeInfo[]>([])
const projectOptions = ref<{ id: number; name: string }[]>([])
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
  event_code: [] as string[],
  channel_id: undefined as number | undefined,
  enabled: true,
})

// 条件表单
const condOnlyFailure = ref(false)
const condMinFailures = ref<number | null>(null)
const condSeverities = ref<string[]>([])
const condProjectIds = ref<number[]>([])

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

const showFailureCondition = computed(() => formData.event_code.some(e => executionEvents.includes(e)))
const showMinFailures = computed(() => formData.event_code.some(e => executionEvents.includes(e)))
const showSeverities = computed(() => formData.event_code.some(e => defectEvents.includes(e)))

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

function toEventArray(codes: string[] | string): string[] {
  return Array.isArray(codes) ? codes : [codes]
}

function displayEvents(codes: string[] | string): string[] {
  return toEventArray(codes).slice(0, 2)
}

function extraEventCount(codes: string[] | string): number {
  return Math.max(0, toEventArray(codes).length - 2)
}

function conditionsSummary(conditions: any): string {
  if (!conditions || typeof conditions !== 'object') return '全部'
  const parts: string[] = []
  if (conditions.only_on_failure) parts.push('仅失败时')
  if (conditions.min_failures) parts.push(`失败≥${conditions.min_failures}`)
  if (conditions.severities?.length) parts.push(`严重程度:${conditions.severities.join('/')}`)
  if (conditions.project_ids?.length) {
    const names = conditions.project_ids.map((id: number) => {
      const p = projectOptions.value.find(p => p.id === id)
      return p ? p.name : id
    })
    parts.push(`项目:${names.join(',')}`)
  }
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

async function loadProjects() {
  try {
    projectOptions.value = await getProjects()
  } catch (e) {
    // 错误已由拦截器处理
  }
}

function handleTableChange(pag: any) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadRules()
}

function handleSearch() {
  pagination.current = 1
  loadRules()
}

function handleReset() {
  filterEvent.value = undefined
  pagination.current = 1
  loadRules()
}

function resetForm() {
  formData.name = ''
  formData.event_code = []
  formData.channel_id = undefined
  formData.enabled = true
  condOnlyFailure.value = false
  condMinFailures.value = null
  condSeverities.value = []
  condProjectIds.value = []
  editingId.value = null
}

function onEventChange() {
  // 多选模式下条件表单根据选中事件动态显示，无需重置
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
  formData.event_code = Array.isArray(record.event_code) ? record.event_code : [record.event_code]
  formData.channel_id = record.channel_id
  formData.enabled = record.enabled
  const cond = record.conditions || {}
  condOnlyFailure.value = !!cond.only_on_failure
  condMinFailures.value = cond.min_failures ?? null
  condSeverities.value = cond.severities || []
  condProjectIds.value = Array.isArray(cond.project_ids) ? cond.project_ids : []
  modalVisible.value = true
}

function buildConditions(): Record<string, any> {
  const cond: Record<string, any> = {}
  if (condOnlyFailure.value) cond.only_on_failure = true
  if (condMinFailures.value != null) cond.min_failures = condMinFailures.value
  if (condSeverities.value.length) cond.severities = condSeverities.value
  if (condProjectIds.value.length) cond.project_ids = condProjectIds.value
  return cond
}

async function handleSave() {
  if (!formData.name.trim()) {
    message.warning('请输入规则名称')
    return
  }
  if (!formData.event_code.length) {
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
  const params = { event: undefined }
  filterEvent.value = params.event
  loadEvents()
  loadChannels()
  loadProjects()
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
.event-tags-cell {
  display: flex;
  align-items: center;
  gap: 2px;
  overflow: hidden;
  white-space: nowrap;
}
.more-count {
  font-size: 12px;
  color: #8c8c8c;
  flex-shrink: 0;
}
</style>
