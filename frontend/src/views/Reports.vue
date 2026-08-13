<template>
  <div class="reports-page">
    <div class="page-header">
      <h2>测试报告</h2>
      <div>
        <a-select
          v-model:value="filterVersionId"
          placeholder="全部版本"
          allow-clear
          style="width: 150px; margin-right: 8px"
          @change="loadReports"
        >
          <a-select-option v-for="v in versions" :key="v.id" :value="v.id">{{ v.name }}</a-select-option>
        </a-select>
        <a-button type="primary" @click="showGenerateModal" :loading="generating">
          <template #icon><FileTextOutlined /></template>
          AI 生成报告
        </a-button>
      </div>
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
          <template v-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">{{ statusText(record.status) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'pass_rate'">
            <span :class="{ 'text-success': (record.pass_rate || 0) >= 80, 'text-warning': (record.pass_rate || 0) >= 50 && (record.pass_rate || 0) < 80, 'text-danger': (record.pass_rate || 0) < 50 }">
              {{ record.pass_rate }}%
            </span>
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
      </a-form>
    </a-modal>

    <!-- 报告详情弹窗 -->
    <a-modal v-model:open="detailVisible" title="报告详情" :footer="null" width="900px">
      <div v-if="currentReport" class="report-detail">
        <a-descriptions :column="3" bordered size="small" class="report-stats">
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
import { message } from 'ant-design-vue'
import { FileTextOutlined } from '@ant-design/icons-vue'
import { getReports, generateReport, deleteReport as deleteReportApi, type TestReport } from '@/api/reports'
import { getVersions, type ProjectVersion } from '@/api/projectVersions'

const route = useRoute()
const projectId = Number(route.params.id)

const loading = ref(false)
const generating = ref(false)
const reports = ref<TestReport[]>([])
const pagination = ref({ current: 1, pageSize: 20, total: 0 })
const versions = ref<ProjectVersion[]>([])
const filterVersionId = ref<number | undefined>(undefined)

const generateVisible = ref(false)
const detailVisible = ref(false)
const currentReport = ref<TestReport | null>(null)

const generateForm = ref({ title: '', report_type: 'full', version_id: undefined as number | undefined })

const renderedContent = computed(() => {
  if (!currentReport.value?.content) return ''
  // 简单的 Markdown 渲染（替换基本语法）
  let html = currentReport.value.content
    .replace(/^### (.*$)/gm, '<h3>$1</h3>')
    .replace(/^## (.*$)/gm, '<h2>$1</h2>')
    .replace(/^# (.*$)/gm, '<h1>$1</h1>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/^- (.*$)/gm, '<li>$1</li>')
    .replace(/\n/g, '<br>')
  return html
})

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '标题', dataIndex: 'title', key: 'title', ellipsis: true },
  { title: '类型', dataIndex: 'report_type', key: 'report_type', width: 100 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '用例数', dataIndex: 'total_cases', key: 'total_cases', width: 80 },
  { title: '通过率', dataIndex: 'pass_rate', key: 'pass_rate', width: 90 },
  { title: '缺陷数', dataIndex: 'total_defects', key: 'total_defects', width: 80 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170, customRender: ({ text }: { text: string }) => formatDateTime(text) },
  { title: '操作', key: 'action', width: 140, fixed: 'right' as const },
]

async function loadReports() {
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

function handleTableChange(pag: any) {
  pagination.value.current = pag.current
  pagination.value.pageSize = pag.pageSize
  loadReports()
}

function showGenerateModal() {
  generateForm.value = { title: '', report_type: 'full', version_id: undefined }
  generateVisible.value = true
}

async function handleGenerate() {
  if (!generateForm.value.version_id) {
    message.warning('请先选择版本')
    return
  }
  generating.value = true
  try {
    await generateReport(projectId, { ...generateForm.value, version_id: generateForm.value.version_id! })
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
  const map: Record<string, string> = { summary: '汇总', execution: '执行', defect: '缺陷', full: '完整' }
  return map[t || ''] || t
}

onMounted(() => {
  if (projectId) {
    loadReports()
    getVersions(projectId, { page_size: 200 }).then(data => { versions.value = data.items }).catch(() => {})
  }
})
</script>

<style scoped>
.reports-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 20px; font-weight: 600; }
.report-detail { max-height: 600px; overflow-y: auto; }
.report-stats { margin-bottom: 16px; }
.report-content { line-height: 1.8; }
.report-content :deep(h1) { font-size: 20px; margin: 16px 0 8px; }
.report-content :deep(h2) { font-size: 18px; margin: 14px 0 6px; }
.report-content :deep(h3) { font-size: 16px; margin: 12px 0 4px; }
.text-success { color: #52c41a; font-weight: 600; }
.text-warning { color: #faad14; font-weight: 600; }
.text-danger { color: #ff4d4f; font-weight: 600; }
</style>
