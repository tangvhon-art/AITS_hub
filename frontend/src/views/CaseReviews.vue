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
          <template v-else-if="column.key === 'scope'">
            <div v-if="record.input_params?.groups?.length">
              <a @click="openScopeModal(record)" style="cursor: pointer">
                <a-tag v-for="(g, i) in record.input_params.groups.slice(0, 2)" :key="i" color="blue" style="margin-bottom: 2px">
                  {{ g.requirement_title }}/{{ g.module }}
                </a-tag>
                <div v-if="record.input_params.groups.length > 2" style="font-size: 12px; color: #1677ff">
                  等 {{ record.input_params.groups.length }} 组，点击查看
                </div>
              </a>
            </div>
            <a v-else style="color: #999; cursor: pointer" @click="openScopeModal(record)">全部</a>
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
        <a-form-item label="选择需求（可多选，不选则评审全部需求的用例）">
          <a-select
            v-model:value="reviewForm.requirement_ids"
            mode="multiple"
            placeholder="选择需求（可多选）"
            allow-clear
            show-search
            :options="requirements.map(r => ({ label: r.title, value: r.id }))"
            :max-tag-count="3"
          />
        </a-form-item>

        <a-form-item label="选择模块（可多选，不选则评审所有模块）">
          <a-select
            v-model:value="reviewForm.modules"
            mode="multiple"
            placeholder="选择模块（可多选）"
            allow-clear
            show-search
            :options="moduleOptions"
            :max-tag-count="3"
          />
        </a-form-item>

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

        <a-alert
          type="info"
          show-icon
          :message="`将根据选中的需求和模块自动查询关联用例进行评审，用例与需求和模块保持关联。`"
          style="margin-bottom: 16px"
        />

        <div class="modal-actions">
          <a-button @click="handleCloseReviewModal">取消</a-button>
          <a-button
            type="primary"
            :loading="reviewing"
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

          <!-- 分组评价 -->
          <a-card v-if="currentDetail.output_result?.group_reviews?.length" size="small" title="分组评价（按需求+模块）" style="margin-bottom: 16px">
            <a-table
              :columns="groupReviewColumns"
              :data-source="currentDetail.output_result.group_reviews"
              :pagination="false"
              row-key="(_r: any, i: number) => i"
              size="small"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'coverage'">
                  <a-tag :color="coverageColor(record.coverage)">{{ record.coverage }}</a-tag>
                </template>
                <template v-else-if="column.key === 'requirement_title'">
                  <a-tooltip placement="topLeft" :overlay-style="{ maxWidth: '400px' }">
                    <template #title>{{ record.requirement_title }}</template>
                    <span class="cell-ellipsis">{{ record.requirement_title }}</span>
                  </a-tooltip>
                </template>
                <template v-else-if="column.key === 'module'">
                  <a-tooltip placement="topLeft" :overlay-style="{ maxWidth: '300px' }">
                    <template #title>{{ record.module }}</template>
                    <span class="cell-ellipsis">{{ record.module }}</span>
                  </a-tooltip>
                </template>
                <template v-else-if="column.key === 'comment'">
                  <a-tooltip placement="topLeft" :overlay-style="{ maxWidth: '500px' }">
                    <template #title>
                      <div style="white-space: pre-wrap">{{ record.comment }}</div>
                    </template>
                    <span class="cell-ellipsis">{{ record.comment }}</span>
                  </a-tooltip>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- 遗漏场景 -->
          <a-card v-if="currentDetail.output_result?.missing_scenarios?.length" size="small" title="遗漏场景（建议补充）" style="margin-bottom: 16px">
            <a-list size="small" :data-source="currentDetail.output_result.missing_scenarios">
              <template #renderItem="{ item, index }">
                <a-list-item>
                  <a-list-item-meta>
                    <template #avatar>
                      <a-avatar :size="24" style="background: #faad14">{{ index + 1 }}</a-avatar>
                    </template>
                    <template #description>{{ item }}</template>
                  </a-list-item-meta>
                </a-list-item>
              </template>
            </a-list>
          </a-card>

          <!-- 问题列表 -->
          <a-card size="small" title="问题列表" style="margin-bottom: 16px">
            <a-empty v-if="!currentDetail.output_result?.issues?.length" description="无问题" />
            <a-table
              v-else
              :columns="issueColumns"
              :data-source="currentDetail.output_result.issues"
              :pagination="false"
              row-key="case_id"
              size="small"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'case_id'">
                  <div>用例 #{{ record.case_id }}</div>
                  <div v-if="record.case_title" style="font-size: 12px; color: #666">{{ record.case_title }}</div>
                </template>
                <template v-else-if="column.key === 'requirement_title'">
                  {{ record.requirement_title || '-' }}
                </template>
                <template v-else-if="column.key === 'module'">
                  {{ record.module || '-' }}
                </template>
                <template v-else-if="column.key === 'severity'">
                  <a-tag :color="severityColor(record.severity)">{{ record.severity }}</a-tag>
                </template>
                <template v-else-if="column.key === 'issue_type'">
                  <a-tag>{{ record.issue_type }}</a-tag>
                </template>
                <template v-else-if="column.key === 'description'">
                  <a-tooltip placement="topLeft" :overlay-style="{ maxWidth: '500px' }">
                    <template #title>
                      <div style="white-space: pre-wrap">{{ record.description }}</div>
                    </template>
                    <span class="cell-ellipsis">{{ record.description }}</span>
                  </a-tooltip>
                </template>
                <template v-else-if="column.key === 'suggestion'">
                  <a-tooltip placement="topLeft" :overlay-style="{ maxWidth: '500px' }">
                    <template #title>
                      <div style="white-space: pre-wrap">{{ record.suggestion }}</div>
                    </template>
                    <span class="cell-ellipsis">{{ record.suggestion }}</span>
                  </a-tooltip>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- 改进建议 -->
          <a-card size="small" title="整体改进建议" style="margin-bottom: 16px">
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

          <!-- 优化用例按钮 -->
          <div style="text-align: center; padding: 8px 0">
            <template v-if="currentDetail.output_result?.optimized">
              <a-alert
                message="用例已优化，请前往用例管理中检查或重新创建评审"
                type="success"
                show-icon
                style="max-width: 480px; margin: 0 auto"
              />
            </template>
            <a-button v-else type="primary" size="large" @click="openOptimizeModal">
              <template #icon><ThunderboltOutlined /></template>
              根据评审结果优化/补充用例
            </a-button>
          </div>
        </div>
      </a-spin>
    </a-drawer>

    <!-- 评审范围查看弹窗 -->
    <a-modal
      v-model:open="scopeModalVisible"
      title="评审范围详情"
      width="720px"
      :footer="null"
    >
      <div class="scope-filter-bar">
        <a-input
          v-model:value="scopeSearch"
          placeholder="搜索需求或模块"
          allow-clear
          style="width: 240px"
          @pressEnter="scopePage = 1"
        />
        <a-space>
          <a-button type="primary" @click="scopePage = 1">查询</a-button>
          <a-button @click="handleScopeReset">重置</a-button>
        </a-space>
      </div>
      <a-table
        :columns="scopeColumns"
        :data-source="scopeFilteredData"
        :pagination="scopePagination"
        :loading="false"
        row-key="(_r: any, i: number) => i"
        size="small"
        @change="handleScopeTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'requirement_title'">
            <a-tooltip placement="topLeft" :overlay-style="{ maxWidth: '400px' }">
              <template #title>{{ record.requirement_title }}</template>
              <span class="cell-ellipsis">{{ record.requirement_title }}</span>
            </a-tooltip>
          </template>
          <template v-else-if="column.key === 'module'">
            <a-tooltip placement="topLeft" :overlay-style="{ maxWidth: '300px' }">
              <template #title>{{ record.module }}</template>
              <span class="cell-ellipsis">{{ record.module }}</span>
            </a-tooltip>
          </template>
        </template>
      </a-table>
    </a-modal>

    <!-- 优化用例弹窗 -->
    <a-modal
      v-model:open="optimizeVisible"
      title="根据评审结果优化/补充用例"
      width="680px"
      :footer="null"
    >
      <a-spin :spinning="optimizing">
        <a-alert
          v-if="!optimizeResult"
          message="将根据评审报告中的问题列表和整体改进建议，AI 自动优化有问题的用例并补充缺失场景。生成的用例将自动关联评审时选择的需求和模块。"
          type="info"
          show-icon
          style="margin-bottom: 16px"
        />

        <div v-if="!optimizeResult">
          <a-form layout="vertical">
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="优化模式">
                  <a-select v-model:value="optimizeForm.optimize_mode" placeholder="选择优化模式">
                    <a-select-option value="both">优化问题用例 + 补充缺失用例</a-select-option>
                    <a-select-option value="optimize">仅优化问题用例</a-select-option>
                    <a-select-option value="supplement">仅补充缺失用例</a-select-option>
                  </a-select>
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="模型配置">
                  <a-select
                    v-model:value="optimizeForm.llm_config_id"
                    placeholder="使用默认模型"
                    allow-clear
                    :options="llmConfigs.map(cfg => ({ label: cfg.name, value: cfg.id }))"
                  />
                </a-form-item>
              </a-col>
            </a-row>

            <a-form-item label="Prompt 模板（用例生成）">
              <a-select
                v-model:value="optimizeForm.prompt_id"
                placeholder="使用默认优化模板"
                allow-clear
                :options="caseGenPrompts.map(p => ({ label: p.name, value: p.id }))"
              />
            </a-form-item>

            <a-form-item label="自定义 Prompt（可选，覆盖模板）">
              <a-textarea
                v-model:value="optimizeForm.system_prompt"
                :rows="6"
                placeholder="留空则使用默认优化模板或上方选择的 Prompt 模板"
              />
            </a-form-item>

            <div style="text-align: right">
              <a-space>
                <a-button @click="optimizeVisible = false">取消</a-button>
                <a-button type="primary" @click="handleOptimize">开始生成</a-button>
              </a-space>
            </div>
          </a-form>
        </div>

        <!-- 生成结果 -->
        <div v-else class="optimize-result">
          <a-result
            :status="optimizeResult.error ? 'error' : 'success'"
            :title="optimizeResult.error ? '生成失败' : '用例优化完成'"
            :sub-title="optimizeResult.error || `优化 ${optimizeResult.optimized_count || 0} 条用例，新增 ${optimizeResult.created_count || 0} 条用例`"
          >
            <template #extra v-if="!optimizeResult.error">
              <a-space>
                <a-button type="primary" @click="optimizeVisible = false">关闭</a-button>
                <a-button @click="goToCases">查看用例列表</a-button>
              </a-space>
            </template>
          </a-result>
        </div>
      </a-spin>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUrlSearch } from '@/composables/useUrlSearch'
import { message } from 'ant-design-vue'
import { AuditOutlined, ThunderboltOutlined } from '@ant-design/icons-vue'
import { listCaseReviews, getCaseReviewDetail, reviewCases, optimizeCasesFromReview, type CaseReviewItem } from '@/api/caseReviews'
import { getCases, getRequirements, type TestCase } from '@/api/cases'
import { promptsApi, type Prompt } from '@/api/prompts'
import { getLLMConfigs } from '@/api/llm'
import { getAgentTask } from '@/api/agentTasks'

const route = useRoute()
const router = useRouter()
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
  { title: '评审范围', key: 'scope', width: 160 },
  { title: '评审时间', dataIndex: 'created_at', key: 'created_at', customRender: ({ text }: any) => text ? formatDateTime(text) : '-' },
  { title: '操作', key: 'action', width: 100 },
]

const issueColumns = [
  { title: '用例', key: 'case_id', width: 80 },
  { title: '需求', key: 'requirement_title', width: 120, ellipsis: true },
  { title: '模块', key: 'module', width: 100, ellipsis: true },
  { title: '问题类型', key: 'issue_type', width: 100 },
  { title: '严重程度', key: 'severity', width: 90 },
  { title: '问题描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '修改建议', dataIndex: 'suggestion', key: 'suggestion', ellipsis: true },
]

const groupReviewColumns = [
  { title: '需求', dataIndex: 'requirement_title', key: 'requirement_title', ellipsis: true },
  { title: '模块', dataIndex: 'module', key: 'module', width: 120 },
  { title: '用例数', dataIndex: 'case_count', key: 'case_count', width: 80 },
  { title: '覆盖度', key: 'coverage', width: 100 },
  { title: '评价', dataIndex: 'comment', key: 'comment', ellipsis: true },
]

function coverageColor(coverage: string) {
  const map: Record<string, string> = { '完整': 'green', '部分': 'orange', '不足': 'red' }
  return map[coverage] || 'default'
}

function formatDateTime(dt: string) {
  if (!dt) return '-'
  const d = new Date(dt)
  return d.toLocaleString('zh-CN', { hour12: false })
}

function statusColor(status: string) {
  const map: Record<string, string> = { success: 'success', failed: 'error', running: 'processing', pending: 'processing' }
  return map[status] || 'default'
}

function statusText(status: string) {
  const map: Record<string, string> = { success: '已完成', failed: '失败', running: '评审中', pending: '排队中' }
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
const requirements = ref<any[]>([])
const moduleOptions = ref<{ label: string; value: string }[]>([])
const reviewPrompts = ref<Prompt[]>([])
const llmConfigs = ref<any[]>([])

const reviewForm = ref({
  requirement_ids: [] as number[],
  modules: [] as string[],
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

async function handleReview() {
  reviewing.value = true
  try {
    await reviewCases(projectId, {
      requirement_ids: reviewForm.value.requirement_ids,
      modules: reviewForm.value.modules,
      llm_config_id: reviewForm.value.llm_config_id || undefined,
      prompt_id: reviewForm.value.prompt_id || undefined,
    })
    message.success('评审任务已提交，正在异步处理中')
    handleCloseReviewModal()
    loadReviews()
    startReviewPolling()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '评审失败')
  } finally {
    reviewing.value = false
  }
}

// 轮询评审状态，直到没有 running 的记录
let reviewPollTimer: ReturnType<typeof setInterval> | null = null
function startReviewPolling() {
  stopReviewPolling()
  reviewPollTimer = setInterval(async () => {
    const hasRunning = reviews.value.some(r => r.status === 'pending' || r.status === 'running')
    if (hasRunning) {
      await loadReviews()
    } else {
      stopReviewPolling()
    }
  }, 3000)
}
function stopReviewPolling() {
  if (reviewPollTimer) {
    clearInterval(reviewPollTimer)
    reviewPollTimer = null
  }
}

function handleCloseReviewModal() {
  showReviewModal.value = false
  reviewForm.value = { requirement_ids: [], modules: [], prompt_id: null, llm_config_id: null }
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

// ===== 评审范围弹窗 =====
const scopeModalVisible = ref(false)
const scopeSearch = ref('')
const scopePage = ref(1)
const scopePageSize = ref(10)
const scopeGroups = ref<any[]>([])

const scopeColumns = [
  { title: '需求名称', dataIndex: 'requirement_title', key: 'requirement_title', ellipsis: true },
  { title: '模块', dataIndex: 'module', key: 'module', width: 160 },
  { title: '用例数', dataIndex: 'case_count', key: 'case_count', width: 80 },
]

const scopeFilteredData = computed(() => {
  if (!scopeSearch.value) return scopeGroups.value
  const kw = scopeSearch.value.toLowerCase()
  return scopeGroups.value.filter((g: any) =>
    (g.requirement_title || '').toLowerCase().includes(kw) ||
    (g.module || '').toLowerCase().includes(kw)
  )
})

const scopePagination = computed(() => ({
  current: scopePage.value,
  pageSize: scopePageSize.value,
  total: scopeFilteredData.value.length,
  showSizeChanger: true,
  showTotal: (total: number) => `共 ${total} 组`,
}))

function openScopeModal(record: any) {
  scopeGroups.value = record.input_params?.groups || []
  scopeSearch.value = ''
  scopePage.value = 1
  scopeModalVisible.value = true
}

function handleScopeReset() {
  scopeSearch.value = ''
  scopePage.value = 1
}

function handleScopeTableChange(pag: any) {
  scopePage.value = pag.current
  scopePageSize.value = pag.pageSize
}

// ===== 评审优化用例 =====
const optimizeVisible = ref(false)
const optimizing = ref(false)
const optimizeResult = ref<{ optimized_count: number; created_count: number; error?: string } | null>(null)
const caseGenPrompts = ref<Prompt[]>([])
const optimizeForm = ref({
  optimize_mode: 'both' as 'both' | 'optimize' | 'supplement',
  llm_config_id: null as number | null,
  prompt_id: null as number | null,
  system_prompt: '',
})
let optimizeTaskId: number | null = null
let optimizePollTimer: ReturnType<typeof setInterval> | null = null

function openOptimizeModal() {
  optimizeResult.value = null
  optimizeForm.value = { optimize_mode: 'both', llm_config_id: null, prompt_id: null, system_prompt: '' }
  optimizeVisible.value = true
  // 加载用例生成 Prompt 模板
  if (caseGenPrompts.value.length === 0) {
    promptsApi.list('case_generation').then(data => { caseGenPrompts.value = data }).catch(() => {})
  }
}

async function handleOptimize() {
  if (!currentDetail.value) return
  optimizing.value = true
  try {
    const res = await optimizeCasesFromReview(projectId, currentDetail.value.id, {
      llm_config_id: optimizeForm.value.llm_config_id || undefined,
      prompt_id: optimizeForm.value.prompt_id || undefined,
      system_prompt: optimizeForm.value.system_prompt || undefined,
      optimize_mode: optimizeForm.value.optimize_mode,
    })
    optimizeTaskId = res.task_id
    optimizeVisible.value = false
    message.success('优化任务已提交，正在后台生成中...')
    startOptimizePolling()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '提交优化任务失败')
    optimizing.value = false
  }
}

function startOptimizePolling() {
  stopOptimizePolling()
  optimizePollTimer = setInterval(async () => {
    if (!optimizeTaskId) return
    try {
      const task = await getAgentTask(optimizeTaskId)
      if (task.status === 'success') {
        const r = task.output_result || {}
        optimizeResult.value = {
          optimized_count: r.optimized_count || 0,
          created_count: r.created_count || 0,
        }
        optimizing.value = false
        stopOptimizePolling()
        message.success(`用例优化完成：优化 ${r.optimized_count || 0} 条，新增 ${r.created_count || 0} 条`)
        // 刷新评审详情，标记已优化后隐藏按钮
        if (currentDetail.value) {
          try {
            currentDetail.value = await getCaseReviewDetail(projectId, currentDetail.value.id)
          } catch { /* ignore */ }
        }
      } else if (task.status === 'failed') {
        optimizeResult.value = { optimized_count: 0, created_count: 0, error: task.error_message || '生成失败' }
        optimizing.value = false
        stopOptimizePolling()
      }
    } catch {
      // 轮询中忽略错误
    }
  }, 3000)
}

function stopOptimizePolling() {
  if (optimizePollTimer) {
    clearInterval(optimizePollTimer)
    optimizePollTimer = null
  }
}

function goToCases() {
  optimizeVisible.value = false
  router.push(`/projects/${projectId}/cases`)
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

onUnmounted(() => {
  stopReviewPolling()
  stopOptimizePolling()
})
</script>

<style scoped>
.case-reviews-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 20px; }

.scope-filter-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  align-items: center;
}

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

.cell-ellipsis {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: default;
}
</style>
