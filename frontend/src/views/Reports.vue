<template>
  <div class="reports-page">
    <div class="page-header">
      <h2>测试报告</h2>
      <a-button type="primary" @click="showGenerateModal" :loading="generating">
        <template #icon><FileTextOutlined /></template>
        AI 生成报告
      </a-button>
    </div>

    <div class="filter-bar">
      <a-input v-model:value="filterTitle" placeholder="标题" allow-clear style="width: 180px" />
      <a-select v-model:value="filterType" placeholder="类型" allow-clear style="width: 120px">
        <a-select-option value="summary">汇总</a-select-option>
        <a-select-option value="execution">执行</a-select-option>
        <a-select-option value="defect">缺陷</a-select-option>
        <a-select-option value="full">完整</a-select-option>
        <a-select-option value="performance">性能报告</a-select-option>
      </a-select>
      <a-select v-model:value="filterStatus" placeholder="状态" allow-clear style="width: 120px">
        <a-select-option value="generating">生成中</a-select-option>
        <a-select-option value="completed">已完成</a-select-option>
        <a-select-option value="failed">失败</a-select-option>
      </a-select>
      <a-select v-model:value="filterVersionId" placeholder="所属版本" allow-clear style="width: 150px">
        <a-select-option v-for="v in versions" :key="v.id" :value="v.id">{{ v.name }}</a-select-option>
      </a-select>
      <a-button type="primary" @click="loadReports">查询</a-button>
      <a-button @click="handleReset">重置</a-button>
    </div>

    <a-card>
      <a-table
        :columns="columns"
        :data-source="reports"
        :loading="loading"
        :pagination="pagination"
        @change="handleTableChange"
        row-key="id"
      >
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
              <a-popconfirm title="确定删除此报告？" @confirm="deleteReport(record.id)">
                <a-button type="link" size="small" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
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
        <!-- 性能报告统计 -->
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
        <!-- 通用报告统计 -->
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
          <a-descriptions-item label="类型">{{ reportTypeText(currentReport.report_type) }}</a-descriptions-item>
        </a-descriptions>
        <div class="report-content" v-html="renderedContent"></div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { formatDateTime } from '@/utils/date'
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useUrlSearch } from '@/composables/useUrlSearch'
import { message } from 'ant-design-vue'
import { FileTextOutlined } from '@ant-design/icons-vue'
import { getReports, generateReport, deleteReport as deleteReportApi, type TestReport } from '@/api/reports'
import { getVersions, type ProjectVersion } from '@/api/projectVersions'
import { promptsApi, type Prompt } from '@/api/prompts'
import { getLLMConfigs } from '@/api/llm'
import { marked } from 'marked'
import { useWorkflowBackend } from '@/composables/useWorkflowBackend'
import { AI_BACKEND_OPTIONS } from '@/constants/enums'

const { showBackendOption: showReportBackend, defaultBackend: reportDefaultBackend, fetch: fetchReportBackend } = useWorkflowBackend()
const reportBackend = ref('local')

const route = useRoute()
const projectId = Number(route.params.id)
const { loadFromUrl, syncToUrl } = useUrlSearch()

const loading = ref(false)
const generating = ref(false)
const reports = ref<TestReport[]>([])
const pagination = ref({ current: 1, pageSize: 20, total: 0 })
const versions = ref<ProjectVersion[]>([])
const filterTitle = ref('')
const filterType = ref<string | undefined>(undefined)
const filterStatus = ref<string | undefined>(undefined)
const filterVersionId = ref<number | undefined>(undefined)
const reportPrompts = ref<Prompt[]>([])
const llmConfigs = ref<any[]>([])

const generateVisible = ref(false)
const detailVisible = ref(false)
const currentReport = ref<TestReport | null>(null)

const generateForm = ref({ title: '', report_type: 'full', version_id: undefined as number | undefined, prompt_id: undefined as number | undefined, llm_config_id: undefined as number | undefined })

const renderedContent = computed(() => {
  if (!currentReport.value?.content) return ''
  try {
    return marked.parse(currentReport.value.content) as string
  } catch {
    return currentReport.value.content.replace(/\n/g, '<br>')
  }
})

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

async function loadReports() {
  syncToUrl({ title: filterTitle.value, report_type: filterType.value, status: filterStatus.value, version_id: filterVersionId.value })
  loading.value = true
  if (!projectId) {
    loading.value = false
    message.error('缺少项目 ID，无法加载报告')
    return
  }
  try {
    const res = await getReports(projectId, {
      page: pagination.value.current,
      page_size: pagination.value.pageSize,
      title: filterTitle.value || undefined,
      report_type: filterType.value,
      status: filterStatus.value,
      version_id: filterVersionId.value,
    })
    reports.value = res.items
    pagination.value.total = res.total
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

function handleReset() {
  filterTitle.value = ''
  filterType.value = undefined
  filterStatus.value = undefined
  filterVersionId.value = undefined
  loadReports()
}

function handleTableChange(pag: any) {
  pagination.value.current = pag.current
  pagination.value.pageSize = pag.pageSize
  loadReports()
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
    await generateReport(projectId, {
      ...generateForm.value,
      version_id: generateForm.value.version_id!,
      backend: showReportBackend.value ? reportBackend.value : undefined,
    })
    message.success('报告生成成功')
    generateVisible.value = false
    loadReports()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '生成失败')
  } finally {
    generating.value = false
  }
}

function viewReport(record: TestReport) {
  currentReport.value = record
  detailVisible.value = true
}

async function deleteReport(id: number) {
  try {
    await deleteReportApi(projectId, id)
    message.success('删除成功')
    loadReports()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '删除失败')
  }
}

function statusColor(s?: string) {
  const map: Record<string, string> = { generating: 'orange', completed: 'green', failed: 'red' }
  return map[s || ''] || 'default'
}
function statusText(s?: string) {
  const map: Record<string, string> = { generating: '生成中', completed: '已完成', failed: '失败' }
  return map[s || ''] || s
}
function reportTypeText(t?: string) {
  const map: Record<string, string> = { summary: '汇总', execution: '执行', defect: '缺陷', full: '完整', performance: '性能报告' }
  return map[t || ''] || t
}

function getPerfSuccessRate(record: any) {
  const s = typeof record.summary === 'string' ? (() => { try { return JSON.parse(record.summary) } catch { return {} } })() : (record.summary || {})
  return (100 - (s.failure_rate || 0)).toFixed(1)
}

onMounted(() => {
  if (projectId) {
    const params = loadFromUrl({ title: '', report_type: undefined, status: undefined, version_id: undefined as number | undefined })
    filterTitle.value = params.title || ''
    filterType.value = params.report_type
    filterStatus.value = params.status
    filterVersionId.value = params.version_id ? Number(params.version_id) : undefined
    loadReports()
    getVersions(projectId, { page_size: 200 }).then(data => { versions.value = data.items }).catch(() => {})
    promptsApi.list('report_generation').then(data => { reportPrompts.value = data }).catch(() => {})
    getLLMConfigs().then(data => { llmConfigs.value = data })
    // 查询"测试报告生成"模块的执行后端有效配置
    fetchReportBackend('report.generate', projectId).then(() => {
      reportBackend.value = reportDefaultBackend.value || 'local'
    })
  }
})
</script>

<style scoped>
.reports-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 20px; font-weight: 600; }
.filter-bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 16px; }
.report-detail { max-height: 600px; overflow-y: auto; }
.report-stats { margin-bottom: 16px; }
.report-content { line-height: 1.8; color: #1f2329; font-size: 14px; }
.report-content :deep(h1) { font-size: 20px; margin: 16px 0 8px; font-weight: 600; border-bottom: 1px solid #e8e8e8; padding-bottom: 6px; }
.report-content :deep(h2) { font-size: 17px; margin: 14px 0 8px; font-weight: 600; color: #1677ff; border-left: 3px solid #1677ff; padding-left: 8px; }
.report-content :deep(h3) { font-size: 15px; margin: 12px 0 6px; font-weight: 600; }
.report-content :deep(p) { margin: 8px 0; }
.report-content :deep(ul), .report-content :deep(ol) { margin: 8px 0; padding-left: 24px; }
.report-content :deep(li) { margin: 4px 0; }
.report-content :deep(strong) { font-weight: 600; color: #1f2329; }
.report-content :deep(em) { font-style: italic; }
.report-content :deep(code) { background: #f5f5f5; padding: 2px 6px; border-radius: 4px; font-size: 13px; color: #d63384; font-family: 'SF Mono', Monaco, monospace; }
.report-content :deep(pre) { background: #f6f8fa; padding: 12px 16px; border-radius: 6px; overflow-x: auto; margin: 10px 0; }
.report-content :deep(pre code) { background: none; padding: 0; color: #1f2329; }
.report-content :deep(blockquote) { border-left: 4px solid #d9d9d9; margin: 10px 0; padding: 8px 16px; color: #606266; background: #fafafa; border-radius: 0 4px 4px 0; }
.report-content :deep(table) { border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 13px; }
.report-content :deep(th), .report-content :deep(td) { border: 1px solid #e8e8e8; padding: 8px 12px; text-align: left; }
.report-content :deep(th) { background: #fafafa; font-weight: 600; }
.report-content :deep(tr:nth-child(even)) { background: #fcfcfc; }
.report-content :deep(hr) { border: none; border-top: 1px solid #e8e8e8; margin: 16px 0; }
.text-success { color: #52c41a; font-weight: 600; }
.text-warning { color: #faad14; font-weight: 600; }
.text-danger { color: #ff4d4f; font-weight: 600; }
</style>
