<template>
  <div class="case-reviews-page">
    <div class="page-header">
      <h2>用例评审</h2>
      <a-button type="primary" @click="showReviewModal = true">
        <template #icon><AuditOutlined /></template>
        新建评审
      </a-button>
    </div>

    <a-card>
      <a-form layout="inline" style="margin-bottom: 16px">
        <a-form-item label="状态">
          <a-select v-model:value="filterStatus" allow-clear placeholder="全部" style="width: 150px">
            <a-select-option value="running">评审中</a-select-option>
            <a-select-option value="success">已完成</a-select-option>
            <a-select-option value="failed">失败</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-space>
            <a-button type="primary" @click="loadReviews">查询</a-button>
            <a-button @click="handleReset">重置</a-button>
          </a-space>
        </a-form-item>
      </a-form>
      <a-table
        :columns="columns"
        :data-source="reviews"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        @change="handleTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">{{ statusText(record.status) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'score'">
            <span v-if="record.output_result?.score != null" :class="scoreClass(record.output_result.score)">
              {{ record.output_result.score }}
            </span>
            <span v-else>-</span>
          </template>
          <template v-else-if="column.key === 'passed'">
            <a-tag v-if="record.output_result?.passed === true" color="success">通过</a-tag>
            <a-tag v-else-if="record.output_result?.passed === false" color="error">未通过</a-tag>
            <span v-else>-</span>
          </template>
          <template v-else-if="column.key === 'case_count'">
            {{ record.input_params?.case_count || 0 }}
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button type="link" size="small" @click="viewDetail(record)">查看详情</a-button>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 新建评审弹窗 -->
    <a-modal
      v-model:open="showReviewModal"
      title="新建用例评审"
      width="720px"
      :footer="null"
      @cancel="handleCloseReviewModal"
    >
      <a-form layout="vertical">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="选择需求">
              <a-select
                v-model:value="reviewForm.requirement_id"
                placeholder="选择需求（可选）"
                allow-clear
                show-search
                :options="requirements.map(r => ({ label: r.title, value: r.id }))"
                @change="onRequirementChange"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="模块筛选">
              <a-select
                v-model:value="reviewForm.module"
                placeholder="选择模块（可选）"
                allow-clear
                show-search
                :options="moduleOptions"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="Prompt 模板">
              <a-select
                v-model:value="reviewForm.prompt_id"
                placeholder="使用默认 Prompt"
                allow-clear
                :options="reviewPrompts.map(p => ({ label: p.name, value: p.id }))"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="模型配置">
              <a-select
                v-model:value="reviewForm.llm_config_id"
                placeholder="使用默认模型"
                allow-clear
                :options="llmConfigs.map(cfg => ({ label: cfg.name, value: cfg.id }))"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item>
          <a-space>
            <a-button @click="fetchCasesForReview" :loading="fetchingCases">
              获取用例
            </a-button>
            <span v-if="selectedCases.length > 0" style="color: #52c41a">
              已获取 {{ selectedCases.length }} 条用例
            </span>
            <span v-else-if="fetchDone" style="color: #999">
              未找到匹配的用例
            </span>
          </a-space>
        </a-form-item>

        <div v-if="selectedCases.length > 0" class="case-preview">
          <a-table
            :columns="caseColumns"
            :data-source="selectedCases"
            :pagination="{ pageSize: 5 }"
            row-key="id"
            size="small"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'priority'">
                <a-tag :color="priorityColor(record.priority)">{{ record.priority }}</a-tag>
              </template>
              <template v-else-if="column.key === 'steps'">
                {{ Array.isArray(record.steps) ? record.steps.length : 0 }} 步
              </template>
            </template>
          </a-table>
        </div>

        <div class="modal-actions">
          <a-button @click="handleCloseReviewModal">取消</a-button>
          <a-button
            type="primary"
            :loading="reviewing"
            :disabled="selectedCases.length === 0"
            @click="handleReview"
          >
            开始评审
          </a-button>
        </div>
      </a-form>
    </a-modal>

    <!-- 评审详情抽屉 -->
    <a-drawer
      v-model:open="detailVisible"
      title="评审报告详情"
      width="720px"
    >
      <a-spin :spinning="detailLoading">
        <div v-if="currentDetail" class="review-detail">
          <!-- 评分概览 -->
          <a-card size="small" title="评审概览" style="margin-bottom: 16px">
            <a-descriptions :column="3" size="small">
              <a-descriptions-item label="评分">
                <span :class="scoreClass(currentDetail.output_result?.score || 0)" style="font-size: 20px; font-weight: bold">
                  {{ currentDetail.output_result?.score ?? '-' }}
                </span>
              </a-descriptions-item>
              <a-descriptions-item label="结果">
                <a-tag :color="currentDetail.output_result?.passed ? 'success' : 'error'">
                  {{ currentDetail.output_result?.passed ? '通过' : '未通过' }}
                </a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="用例数">
                {{ currentDetail.input_params?.case_count || 0 }}
              </a-descriptions-item>
              <a-descriptions-item label="评审时间" :span="3">
                {{ $formatDateTime(currentDetail.created_at) }}
              </a-descriptions-item>
              <a-descriptions-item label="总体评价" :span="3">
                {{ currentDetail.output_result?.summary || '-' }}
              </a-descriptions-item>
            </a-descriptions>
          </a-card>

          <!-- 问题列表 -->
          <a-card size="small" title="问题列表" style="margin-bottom: 16px">
            <a-empty v-if="!currentDetail.output_result?.issues?.length" description="无问题" />
            <a-table
              v-else
              :columns="issueColumns"
              :data-source="currentDetail.output_result.issues"
              :pagination="false"
              row-key="case_index"
              size="small"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'case_index'">
                  用例 #{{ record.case_index + 1 }}
                </template>
                <template v-else-if="column.key === 'severity'">
                  <a-tag :color="severityColor(record.severity)">{{ record.severity }}</a-tag>
                </template>
                <template v-else-if="column.key === 'issue_type'">
                  <a-tag>{{ record.issue_type }}</a-tag>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- 改进建议 -->
          <a-card size="small" title="整体改进建议">
            <a-empty v-if="!currentDetail.output_result?.overall_suggestions?.length" description="无建议" />
            <a-list v-else size="small" :data-source="currentDetail.output_result.overall_suggestions">
              <template #renderItem="{ item, index }">
                <a-list-item>
                  <a-list-item-meta>
                    <template #avatar>
                      <a-avatar :size="24" style="background: #1677ff">{{ index + 1 }}</a-avatar>
                    </template>
                    <template #description>{{ item }}</template>
                  </a-list-item-meta>
                </a-list-item>
              </template>
            </a-list>
          </a-card>
        </div>
      </a-spin>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useUrlSearch } from '@/composables/useUrlSearch'
import { message } from 'ant-design-vue'
import { AuditOutlined } from '@ant-design/icons-vue'
import { listCaseReviews, getCaseReviewDetail, reviewCases, type CaseReviewItem } from '@/api/caseReviews'
import { getCases, getRequirements, type TestCase } from '@/api/cases'
import { promptsApi, type Prompt } from '@/api/prompts'
import { getLLMConfigs } from '@/api/llm'

const route = useRoute()
const { loadFromUrl, syncToUrl } = useUrlSearch()
const projectId = Number(route.params.id)

const loading = ref(false)
const reviews = ref<CaseReviewItem[]>([])
const pagination = ref({ current: 1, pageSize: 20, total: 0 })
const filterStatus = ref<string>()

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
  { title: '状态', key: 'status', width: 90 },
  { title: '评分', key: 'score', width: 80 },
  { title: '结果', key: 'passed', width: 90 },
  { title: '用例数', key: 'case_count', width: 80 },
  { title: '评审时间', dataIndex: 'created_at', key: 'created_at', customRender: ({ text }: any) => text ? formatDateTime(text) : '-' },
  { title: '操作', key: 'action', width: 100 },
]

const caseColumns = [
  { title: '用例名称', dataIndex: 'title', key: 'title', ellipsis: true },
  { title: '模块', dataIndex: 'module', key: 'module', width: 120 },
  { title: '优先级', key: 'priority', width: 80 },
  { title: '步骤', key: 'steps', width: 70 },
]

const issueColumns = [
  { title: '用例', key: 'case_index', width: 80 },
  { title: '问题类型', key: 'issue_type', width: 100 },
  { title: '严重程度', key: 'severity', width: 90 },
  { title: '问题描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '修改建议', dataIndex: 'suggestion', key: 'suggestion', ellipsis: true },
]

function formatDateTime(dt: string) {
  if (!dt) return '-'
  const d = new Date(dt)
  return d.toLocaleString('zh-CN', { hour12: false })
}

function statusColor(status: string) {
  const map: Record<string, string> = { success: 'success', failed: 'error', running: 'processing' }
  return map[status] || 'default'
}

function statusText(status: string) {
  const map: Record<string, string> = { success: '已完成', failed: '失败', running: '评审中' }
  return map[status] || status
}

function scoreClass(score: number) {
  if (score >= 80) return 'text-success'
  if (score >= 60) return 'text-warning'
  return 'text-danger'
}

function priorityColor(priority: string) {
  const map: Record<string, string> = { P0: 'red', P1: 'orange', P2: 'blue', P3: 'default' }
  return map[priority] || 'default'
}

function severityColor(severity: string) {
  const map: Record<string, string> = { high: 'error', medium: 'warning', low: 'default' }
  return map[severity] || 'default'
}

async function loadReviews() {
  loading.value = true
  syncToUrl({ status: filterStatus.value })
  try {
    const params: any = { page: pagination.value.current, page_size: pagination.value.pageSize }
    if (filterStatus.value) params.status = filterStatus.value
    const data = await listCaseReviews(projectId, params)
    reviews.value = data.items
    pagination.value.total = data.total
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

function handleTableChange(pag: any) {
  pagination.value.current = pag.current
  loadReviews()
}

function handleReset() {
  filterStatus.value = undefined
  loadReviews()
}

// ===== 新建评审 =====
const showReviewModal = ref(false)
const reviewing = ref(false)
const fetchingCases = ref(false)
const fetchDone = ref(false)
const requirements = ref<any[]>([])
const moduleOptions = ref<{ label: string; value: string }[]>([])
const reviewPrompts = ref<Prompt[]>([])
const llmConfigs = ref<any[]>([])
const selectedCases = ref<TestCase[]>([])

const reviewForm = ref({
  requirement_id: null as number | null,
  module: null as string | null,
  prompt_id: null as number | null,
  llm_config_id: null as number | null,
})

async function loadRequirements() {
  try {
    requirements.value = await getRequirements(projectId)
  } catch {}
}

async function loadModuleOptions() {
  try {
    const allCases = await getCases(projectId)
    const modules = [...new Set(allCases.map((c: TestCase) => c.module).filter(Boolean))]
    moduleOptions.value = modules.map(m => ({ label: m, value: m }))
  } catch {}
}

async function onRequirementChange() {
  selectedCases.value = []
  fetchDone.value = false
}

async function fetchCasesForReview() {
  fetchingCases.value = true
  fetchDone.value = false
  try {
    const params: any = {}
    if (reviewForm.value.module) params.module = reviewForm.value.module
    const cases = await getCases(projectId, params)

    let filtered = cases
    if (reviewForm.value.requirement_id) {
      filtered = cases.filter((c: TestCase) => c.req_id === reviewForm.value.requirement_id)
    }

    selectedCases.value = filtered
    fetchDone.value = true

    if (filtered.length === 0) {
      message.warning('未找到匹配的用例')
    } else {
      message.success(`已获取 ${filtered.length} 条用例`)
    }
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '获取用例失败')
  } finally {
    fetchingCases.value = false
  }
}

async function handleReview() {
  if (selectedCases.value.length === 0) {
    message.warning('请先获取用例')
    return
  }

  const requirement = requirements.value.find(r => r.id === reviewForm.value.requirement_id)
  const requirementText = requirement ? `${requirement.title}\n${requirement.content || ''}` : ''

  reviewing.value = true
  try {
    const result = await reviewCases(projectId, {
      cases: selectedCases.value.map(c => ({
        title: c.title,
        module: c.module,
        priority: c.priority,
        preconditions: c.preconditions,
        steps: typeof c.steps === 'string' ? JSON.parse(c.steps) : c.steps,
        expected_result: c.expected_result,
      })),
      requirement: requirementText,
      llm_config_id: reviewForm.value.llm_config_id || undefined,
      prompt_id: reviewForm.value.prompt_id || undefined,
    })
    message.success(`评审完成，评分：${result.result?.score ?? '-'}`)
    handleCloseReviewModal()
    loadReviews()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '评审失败')
  } finally {
    reviewing.value = false
  }
}

function handleCloseReviewModal() {
  showReviewModal.value = false
  reviewForm.value = { requirement_id: null, module: null, prompt_id: null, llm_config_id: null }
  selectedCases.value = []
  fetchDone.value = false
}

// ===== 评审详情 =====
const detailVisible = ref(false)
const detailLoading = ref(false)
const currentDetail = ref<CaseReviewItem | null>(null)

async function viewDetail(record: CaseReviewItem) {
  detailVisible.value = true
  detailLoading.value = true
  currentDetail.value = null
  try {
    currentDetail.value = await getCaseReviewDetail(projectId, record.id)
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '加载详情失败')
  } finally {
    detailLoading.value = false
  }
}

onMounted(() => {
  const params = loadFromUrl({ status: undefined })
  filterStatus.value = params.status
  loadReviews()
  loadRequirements()
  loadModuleOptions()
  promptsApi.list('case_review').then(data => { reviewPrompts.value = data }).catch(() => {})
  getLLMConfigs().then(data => { llmConfigs.value = data }).catch(() => {})
})
</script>

<style scoped>
.case-reviews-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 20px; }

.text-success { color: #52c41a; }
.text-warning { color: #faad14; }
.text-danger { color: #ff4d4f; }

.case-preview {
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  padding: 8px;
  margin-bottom: 16px;
  max-height: 300px;
  overflow-y: auto;
}

.modal-actions {
  margin-top: 16px;
  text-align: right;
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.review-detail { padding-bottom: 24px; }
</style>
