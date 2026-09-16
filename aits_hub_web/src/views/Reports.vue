<template>
  <div class="reports-page">
    <PageHeader title="测试报告">
      <template #extra>
        <a-button type="primary" @click="showGenerateModal" :loading="generating">
          <template #icon><FileTextOutlined /></template>
          AI 生成报告
        </a-button>
      </template>
    </PageHeader>

    <a-card>
      <SearchBar @search="handleSearch" @reset="handleReset">
      <a-form layout="inline">
        <a-form-item label="标题">
          <a-input v-model:value="filterTitle" placeholder="标题" allow-clear style="width: 180px" />
        </a-form-item>
        <a-form-item label="类型">
          <a-select v-model:value="filterType" placeholder="类型" allow-clear style="width: 120px">
            <a-select-option value="summary">汇总</a-select-option>
            <a-select-option value="execution">执行</a-select-option>
            <a-select-option value="defect">缺陷</a-select-option>
            <a-select-option value="full">完整</a-select-option>
            <a-select-option value="performance">性能报告</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="状态">
          <a-select v-model:value="filterStatus" placeholder="状态" allow-clear style="width: 120px">
            <a-select-option value="generating">生成中</a-select-option>
            <a-select-option value="completed">已完成</a-select-option>
            <a-select-option value="failed">失败</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="所属版本">
          <a-select v-model:value="filterVersionId" placeholder="所属版本" allow-clear style="width: 150px">
            <a-select-option v-for="v in versions" :key="v.id" :value="v.id">{{ v.name }}</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </SearchBar>

    <DataTable
      :columns="columns"
      :data-source="list"
      :loading="loading"
      row-key="id"
      @change="handleTableChange"
    >
        :page="pagination.current"
        :page-size="pagination.pageSize"
        :total="pagination.total"
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'report_type'">
          <a-tag>{{ reportTypeText(record.report_type) }}</a-tag>
        </template>
        <template v-else-if="column.key === 'status'">
          <a-tag :color="statusColor(record.status)">{{ statusText(record.status) }}</a-tag>
        </template>
        <template v-else-if="column.key === 'pass_rate'">
          <template v-if="record.report_type === 'performance'">
            <span class="text-success">{{ getPerfSuccessRate(record) }}%</span>
          </template>
          <template v-else>
            <span :class="{ 'text-success': (record.pass_rate || 0) >= 80, 'text-warning': (record.pass_rate || 0) >= 50 && (record.pass_rate || 0) < 80, 'text-danger': (record.pass_rate || 0) < 50 }">
              {{ record.pass_rate }}%
            </span>
          </template>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="viewReport(record)">查看</a-button>
            <a-button type="link" size="small" danger @click="confirmDeleteReport(record)">删除</a-button>
          </a-space>
        </template>
      </template>
    </DataTable>
    </a-card>

    <!-- 生成报告弹窗 -->
    <a-modal v-model:open="generateVisible" title="AI 生成测试报告" @ok="handleGenerate" :confirm-loading="generating" :ok-button-props="{ disabled: !generateForm.version_id }">
      <a-form layout="vertical">
        <a-form-item label="所属版本" required>
          <a-select v-model:value="generateForm.version_id" placeholder="请选择版本（必选）">
            <a-select-option v-for="v in versions" :key="v.id" :value="v.id">{{ v.name }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="报告标题">
          <a-input v-model:value="generateForm.title" placeholder="留空则自动生成" />
        </a-form-item>
        <a-form-item label="报告类型">
          <a-select v-model:value="generateForm.report_type">
            <a-select-option value="summary">汇总报告</a-select-option>
            <a-select-option value="execution">执行报告</a-select-option>
            <a-select-option value="defect">缺陷报告</a-select-option>
            <a-select-option value="full">完整报告</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="Prompt 模板">
          <a-select
            v-model:value="generateForm.prompt_id"
            placeholder="使用默认 Prompt"
            allow-clear
            :options="reportPrompts.map(p => ({ label: p.name, value: p.id }))"
          />
        </a-form-item>
        <a-form-item label="模型配置">
          <a-select
            v-model:value="generateForm.llm_config_id"
            placeholder="使用默认模型"
            allow-clear
            :options="llmConfigs.map(cfg => ({ label: cfg.name, value: cfg.id }))"
          />
        </a-form-item>
        <a-form-item v-if="showReportBackend" label="执行方式">
          <a-radio-group v-model:value="reportBackend" :options="AI_BACKEND_OPTIONS" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 报告详情弹窗 -->
    <a-modal v-model:open="detailVisible" title="报告详情" :footer="null" width="900px">
      <div v-if="currentReport" class="report-detail">
        <a-descriptions v-if="currentReport.report_type === 'performance'" :column="3" bordered size="small" class="report-stats">
          <a-descriptions-item label="总请求数">{{ perfSummary.total_requests || 0 }}</a-descriptions-item>
          <a-descriptions-item label="失败数">{{ perfSummary.total_failures || 0 }}</a-descriptions-item>
          <a-descriptions-item label="失败率">
            <span :class="{ 'text-danger': (perfSummary.failure_rate || 0) > 5 }">{{ perfSummary.failure_rate || 0 }}%</span>
          </a-descriptions-item>
          <a-descriptions-item label="成功率">{{ (100 - (perfSummary.failure_rate || 0)).toFixed(2) }}%</a-descriptions-item>
          <a-descriptions-item label="RPS">{{ perfSummary.rps || 0 }}</a-descriptions-item>
          <a-descriptions-item label="平均响应">{{ perfSummary.avg_response_time || 0 }} ms</a-descriptions-item>
          <a-descriptions-item label="P95响应">{{ perfSummary.p95_response_time || 0 }} ms</a-descriptions-item>
          <a-descriptions-item label="执行ID">#{{ perfSummary.run_id || '-' }}</a-descriptions-item>
          <a-descriptions-item label="类型">性能报告</a-descriptions-item>
        </a-descriptions>
        <a-descriptions v-else :column="3" bordered size="small" class="report-stats">
          <a-descriptions-item label="用例总数">{{ currentReport.total_cases }}</a-descriptions-item>
          <a-descriptions-item label="通过">{{ currentReport.passed_cases }}</a-descriptions-item>
          <a-descriptions-item label="失败">{{ currentReport.failed_cases }}</a-descriptions-item>
          <a-descriptions-item label="通过率">
            <span :class="{ 'text-success': (currentReport.pass_rate || 0) >= 80, 'text-danger': (currentReport.pass_rate || 0) < 50 }">
              {{ currentReport.pass_rate }}%
            </span>
          </a-descriptions-item>
          <a-descriptions-item label="缺陷总数">{{ currentReport.total_defects }}</a-descriptions-item>
          <a-descriptions-item label="未解决缺陷">{{ currentReport.open_defects }}</a-descriptions-item>
          <a-descriptions-item label="执行次数">{{ currentReport.total_runs }}</a-descriptions-item>
          <a-descriptions-item label="平均耗时">{{ currentReport.avg_duration }}s</a-descriptions-item>
          <a-descriptions-item label="类型">{{ reportTypeText(currentReport.report_type || '') }}</a-descriptions-item>
        </a-descriptions>
        <MdView :content="currentReport?.content" />
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { formatDateTime } from '@/utils/date'
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { FileTextOutlined } from '@ant-design/icons-vue'
import { getReports, generateReport, deleteReport as deleteReportApi, type TestReport } from '@/api/reports'
import { getVersions, type ProjectVersion } from '@/api/projectVersions'
import { promptsApi, type Prompt } from '@/api/prompts'
import { getLLMConfigs } from '@/api/llm'
import MdView from '@/components/MdView.vue'
import PageHeader from '@/components/PageHeader.vue'
import SearchBar from '@/components/SearchBar.vue'
import DataTable from '@/components/DataTable.vue'
import { useList } from '@/composables/useList'
import { useWorkflowBackend } from '@/composables/useWorkflowBackend'
import { AI_BACKEND_OPTIONS } from '@/constants/enums'

const { showBackendOption: showReportBackend, defaultBackend: reportDefaultBackend, fetch: fetchReportBackend } = useWorkflowBackend()
const reportBackend = ref('local')

const route = useRoute()
const projectId = Number(route.params.id)
const generating = ref(false)
const versions = ref<ProjectVersion[]>([])
const filterTitle = ref('')
const filterType = ref<string | undefined>(undefined)
const filterStatus = ref<string | undefined>(undefined)
const filterVersionId = ref<number | undefined>(undefined)
const reportPrompts = ref<Prompt[]>([])
const llmConfigs = ref<any[]>([])

// ── 列表（后端服务端分页接口）──
const { loading, list, total, pagination, loadData, handleTableChange } = useList<TestReport>(
  (params) =>
    getReports(projectId, {
      page: params.page,
      page_size: params.page_size,
      title: filterTitle.value || undefined,
      report_type: filterType.value,
      status: filterStatus.value,
      version_id: filterVersionId.value,
    }),
  { onError: (e: any) => message.error(e?.response?.data?.detail || '加载失败') },
)

function handleSearch() {
  pagination.current = 1
  loadData()
}

function handleReset() {
  filterTitle.value = ''
  filterType.value = undefined
  filterStatus.value = undefined
  filterVersionId.value = undefined
  pagination.current = 1
  loadData()
}

/** 删除报告：统一确认弹窗 */
function confirmDeleteReport(record: TestReport) {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除报告「${record.title}」吗？`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      await deleteReportApi(projectId, record.id!)
      message.success('删除成功')
      loadData()
    },
  })
}

const detailVisible = ref(false)
const currentReport = ref<TestReport | null>(null)

const generateVisible = ref(false)
const generateForm = ref({ title: '', report_type: 'full', version_id: undefined as number | undefined, prompt_id: undefined as number | undefined, llm_config_id: undefined as number | undefined })

const perfSummary = computed(() => {
  const s = currentReport.value?.summary
  if (!s) return {}
  if (typeof s === 'string') {
    try { return JSON.parse(s) } catch { return {} }
  }
  return s
})

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '标题', dataIndex: 'title', key: 'title', ellipsis: true },
  { title: '类型', dataIndex: 'report_type', key: 'report_type', width: 100, customRender: ({ record }: { record: any }) => reportTypeText(record.report_type) },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '用例数', dataIndex: 'total_cases', key: 'total_cases', width: 80, customRender: ({ record }: { record: any }) => record.report_type === 'performance' ? '-' : (record.total_cases ?? 0) },
  { title: '通过率', dataIndex: 'pass_rate', key: 'pass_rate', width: 90, customRender: ({ record }: { record: any }) => {
      if (record.report_type === 'performance') {
        const s = typeof record.summary === 'string' ? (() => { try { return JSON.parse(record.summary) } catch { return {} } })() : (record.summary || {})
        return `${(100 - (s.failure_rate || 0)).toFixed(1)}%`
      }
      return `${record.pass_rate ?? 0}%`
    } },
  { title: '缺陷数', dataIndex: 'total_defects', key: 'total_defects', width: 80, customRender: ({ record }: { record: any }) => record.report_type === 'performance' ? '-' : (record.total_defects ?? 0) },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170, customRender: ({ text }: { text: string }) => formatDateTime(text) },
  { title: '操作', key: 'action', width: 140, fixed: 'right' as const },
]

function reportTypeText(t: string) {
  const map: Record<string, string> = { summary: '汇总', execution: '执行', defect: '缺陷', full: '完整', performance: '性能报告' }
  return map[t] || t
}

function statusColor(s: string) {
  const map: Record<string, string> = { generating: 'processing', completed: 'success', failed: 'error' }
  return map[s] || 'default'
}

function statusText(s: string) {
  const map: Record<string, string> = { generating: '生成中', completed: '已完成', failed: '失败' }
  return map[s] || s
}

function getPerfSuccessRate(record: TestReport): number {
  const s = typeof record.summary === 'string' ? (() => { try { return JSON.parse(record.summary) } catch { return {} } })() : (record.summary || {})
  return Math.max(0, (100 - (s.failure_rate || 0)).toFixed(1) as unknown as number)
}

function viewReport(record: TestReport) {
  currentReport.value = record
  detailVisible.value = true
}

function showGenerateModal() {
  generateForm.value = { title: '', report_type: 'full', version_id: undefined, prompt_id: undefined, llm_config_id: undefined }
  generateVisible.value = true
}

async function handleGenerate() {
  if (!generateForm.value.version_id) {
    message.warning('请先选择版本')
    return
  }
  generating.value = true
  try {
    await generateReport(projectId, generateForm.value as any)
    message.success('报告生成任务已提交')
    generateVisible.value = false
    setTimeout(() => loadData(), 5000)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '生成失败')
  } finally {
    generating.value = false
  }
}

getVersions(projectId).then(data => { versions.value = ((data as any).items ?? data) as ProjectVersion[] })
promptsApi.list('report_generation').then(data => { reportPrompts.value = data }).catch(() => {})
getLLMConfigs().then(data => { llmConfigs.value = data })
fetchReportBackend('report.generate', projectId).then(() => {
  reportBackend.value = reportDefaultBackend.value || 'local'
})
</script>

<style scoped>
.reports-page { padding: 20px; }
.text-success { color: #52c41a; }
.text-warning { color: #faad14; }
.text-danger { color: #ff4d4f; }
.report-stats { margin-bottom: 16px; }
</style>
