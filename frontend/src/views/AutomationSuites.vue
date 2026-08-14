<template>
  <div class="suites-page">
    <div class="page-header">
      <h2>自动化编排</h2>
      <a-button type="primary" @click="showCreateModal = true">
        <PlusOutlined /> 新建编排
      </a-button>
    </div>

    <div class="content-wrapper">
      <!-- 左侧套件列表 -->
      <div class="suite-list">
        <a-card title="编排套件" :bordered="false">
          <div class="suite-items">
            <div
              v-for="suite in suites"
              :key="suite.id"
              class="suite-item"
              :class="{ active: currentSuite?.id === suite.id }"
              @click="selectSuite(suite)"
            >
              <div class="suite-item-header">
                <span class="suite-name">{{ suite.name }}</span>
                <a-tag :color="getSuiteStatusColor(suite.last_run_status)" size="small" v-if="suite.last_run_status">
                  {{ getRunStatusText(suite.last_run_status) }}
                </a-tag>
              </div>
              <div class="suite-item-meta">
                <span>{{ suite.total_steps || 0 }} 步骤</span>
                <span v-if="suite.plan_id">关联计划 #{{ suite.plan_id }}</span>
              </div>
              <div class="suite-item-time">{{ $formatDateTime(suite.updated_at) }}</div>
            </div>
            <a-empty v-if="suites.length === 0" description="暂无编排套件" />
          </div>
        </a-card>
      </div>

      <!-- 右侧详情/编辑器 -->
      <div class="suite-detail">
        <a-card v-if="currentSuite" :bordered="false">
          <template #title>
            <div class="detail-title">
              <span>{{ currentSuite.name }}</span>
              <a-tag :color="getStatusColor(currentSuite.status)">{{ getStatusText(currentSuite.status) }}</a-tag>
            </div>
          </template>
          <template #extra>
            <a-space>
              <a-button @click="openEditModal">编辑</a-button>
              <a-tooltip title="关闭后将以可视化浏览器窗口运行">
                <a-space size="small" style="margin-right: 8px">
                  <a-switch v-model:checked="headlessEnabled" size="small" :disabled="executing" />
                  <span style="font-size: 12px; color: #666">无头模式</span>
                </a-space>
              </a-tooltip>
              <a-button type="primary" @click="handleExecute" :loading="executing">
                <PlayCircleOutlined /> 执行编排
              </a-button>
              <a-popconfirm title="确定删除该编排？" @confirm="handleDelete">
                <a-button danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>

          <a-descriptions :column="3" size="small" bordered style="margin-bottom: 16px">
            <a-descriptions-item label="描述" :span="3">{{ currentSuite.description || '-' }}</a-descriptions-item>
            <a-descriptions-item label="关联计划">
              {{ getPlanName(currentSuite.plan_id) }}
            </a-descriptions-item>
            <a-descriptions-item label="步骤数">{{ currentSuite.total_steps || 0 }}</a-descriptions-item>
            <a-descriptions-item label="调度类型">{{ getScheduleText(currentSuite.schedule_type) }}</a-descriptions-item>
            <a-descriptions-item label="最近执行" :span="3">
              <span v-if="currentSuite.last_run_at">
                {{ getRunStatusText(currentSuite.last_run_status) }} · {{ $formatDateTime(currentSuite.last_run_at) }}
              </span>
              <span v-else>从未执行</span>
            </a-descriptions-item>
          </a-descriptions>

          <a-divider>
            <span>编排步骤（{{ steps.length }}）</span>
            <a-button type="link" size="small" @click="openAddStep">添加步骤</a-button>
          </a-divider>

          <div class="steps-list">
            <div
              v-for="(step, index) in steps"
              :key="step.id || index"
              class="step-item"
            >
              <div class="step-order">{{ index + 1 }}</div>
              <div class="step-content">
                <div class="step-header">
                  <span class="step-name">{{ step.step_name }}</span>
                  <a-tag :color="getStepTypeColor(step.step_type)" size="small">{{ getStepTypeText(step.step_type) }}</a-tag>
                  <a-tag v-if="step.continue_on_failure" color="orange" size="small">失败继续</a-tag>
                  <a-tag v-if="step.max_retries" color="blue" size="small">重试{{ step.max_retries }}次</a-tag>
                </div>
                <div class="step-meta">
                  <span v-if="step.script_id">脚本 #{{ step.script_id }}</span>
                  <span v-if="step.case_id">用例 #{{ step.case_id }}</span>
                  <span>超时 {{ step.timeout }}s</span>
                </div>
              </div>
              <div class="step-actions">
                <a-button size="small" @click="moveStep(index, -1)" :disabled="index === 0">↑</a-button>
                <a-button size="small" @click="moveStep(index, 1)" :disabled="index === steps.length - 1">↓</a-button>
                <a-button size="small" @click="openEditStep(index)">编辑</a-button>
                <a-button size="small" danger @click="removeStep(index)">删除</a-button>
              </div>
            </div>
            <a-empty v-if="steps.length === 0" description="暂无步骤，点击添加步骤开始编排" />
          </div>

          <div v-if="steps.length > 0" style="margin-top: 16px; text-align: right">
            <a-button type="primary" @click="saveSteps" :loading="savingSteps">保存步骤</a-button>
          </div>
        </a-card>

        <a-empty v-else description="请选择左侧编排套件查看详情" />
      </div>
    </div>

    <!-- 新建编排弹窗 -->
    <a-modal v-model:open="showCreateModal" title="新建编排套件" @ok="handleCreate" :confirm-loading="creating">
      <a-form layout="vertical" :model="createForm">
        <a-form-item label="套件名称" required>
          <a-input v-model:value="createForm.name" placeholder="请输入套件名称" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="createForm.description" :rows="2" placeholder="请输入描述" />
        </a-form-item>
        <a-form-item label="关联测试计划">
          <a-select v-model:value="createForm.plan_id" placeholder="选择测试计划（可选）" allow-clear>
            <a-select-option v-for="plan in testPlans" :key="plan.id" :value="plan.id">
              {{ plan.name }}
            </a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 编辑编排弹窗 -->
    <a-modal v-model:open="showEditModal" title="编辑编排套件" @ok="handleUpdate" :confirm-loading="updating">
      <a-form layout="vertical" :model="editForm">
        <a-form-item label="套件名称" required>
          <a-input v-model:value="editForm.name" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="editForm.description" :rows="2" />
        </a-form-item>
        <a-form-item label="关联测试计划">
          <a-select v-model:value="editForm.plan_id" placeholder="选择测试计划（可选）" allow-clear>
            <a-select-option v-for="plan in testPlans" :key="plan.id" :value="plan.id">
              {{ plan.name }}
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="状态">
          <a-select v-model:value="editForm.status">
            <a-select-option value="active">可用</a-select-option>
            <a-select-option value="draft">草稿</a-select-option>
            <a-select-option value="archived">已归档</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 添加/编辑步骤弹窗 -->
    <a-modal v-model:open="showStepModal" :title="editingStepIndex >= 0 ? '编辑步骤' : '添加步骤'" @ok="saveStep" :confirm-loading="addingStep">
      <a-form layout="vertical" :model="stepForm">
        <a-form-item label="步骤名称" required>
          <a-input v-model:value="stepForm.step_name" placeholder="请输入步骤名称" />
        </a-form-item>
        <a-form-item label="步骤类型" required>
          <a-select v-model:value="stepForm.step_type">
            <a-select-option value="script">脚本</a-select-option>
            <a-select-option value="case">用例</a-select-option>
            <a-select-option value="wait">等待</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item v-if="stepForm.step_type === 'script'" label="选择脚本" required>
          <a-select v-model:value="stepForm.script_id" show-search placeholder="选择脚本">
            <a-select-option v-for="s in scriptList" :key="s.id" :value="s.id">{{ s.name }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item v-if="stepForm.step_type === 'case'" label="选择用例" required>
          <a-select v-model:value="stepForm.case_id" show-search placeholder="选择用例">
            <a-select-option v-for="c in caseList" :key="c.id" :value="c.id">{{ c.title }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item v-if="stepForm.step_type === 'wait'" label="等待时间（秒）">
          <a-input-number v-model:value="waitSeconds" :min="1" :max="60" />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="失败后继续">
              <a-switch v-model:checked="stepForm.continue_on_failure" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="AI自动修复">
              <a-switch v-model:checked="stepForm.auto_fix" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="最大重试次数">
              <a-input-number v-model:value="stepForm.max_retries" :min="0" :max="5" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="超时时间（秒）">
              <a-input-number v-model:value="stepForm.timeout" :min="1" :max="3600" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </a-modal>

    <!-- 执行结果弹窗 -->
    <a-modal v-model:open="showRunResult" title="编排执行结果" :footer="null" :width="700">
      <a-result
        :status="runResult.status === 'passed' ? 'success' : runResult.status === 'failed' ? 'error' : 'warning'"
        :title="getRunStatusText(runResult.status)"
        :sub-title="`通过 ${runResult.passed_steps || 0} / 失败 ${runResult.failed_steps || 0} / 跳过 ${runResult.skipped_steps || 0}，耗时 ${runResult.total_duration || 0}s`"
      />
      <a-divider>步骤详情</a-divider>
      <a-table :columns="resultColumns" :data-source="runResults" :pagination="false" size="small" row-key="id">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="getRunStatusColor(record.status)">{{ getRunStatusText(record.status) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'error'">
            <span style="color: #ff4d4f; font-size: 12px">{{ record.error_message || '-' }}</span>
          </template>
        </template>
      </a-table>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined, PlayCircleOutlined } from '@ant-design/icons-vue'
import {
  getSuites, createSuite, updateSuite, deleteSuite,
  getSuiteSteps, batchUpdateSteps, executeSuite,
  getSuiteRun, getSuiteRunResults,
  type AutomationSuite, type SuiteStep, type SuiteRun, type SuiteRunResult
} from '@/api/automationSuites'
import { getScripts, type AutomationScript } from '@/api/automationScripts'
import { getPlans, type TestPlan } from '@/api/testPlans'
import { getCases, type TestCase } from '@/api/cases'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)

const suites = ref<AutomationSuite[]>([])
const currentSuite = ref<AutomationSuite | null>(null)
const steps = ref<SuiteStep[]>([])
const scriptList = ref<AutomationScript[]>([])
const testPlans = ref<TestPlan[]>([])
const caseList = ref<TestCase[]>([])

const showCreateModal = ref(false)
const creating = ref(false)
const createForm = ref({ name: '', description: '', plan_id: undefined as number | undefined })

const showEditModal = ref(false)
const updating = ref(false)
const editForm = ref({ name: '', description: '', plan_id: undefined as number | undefined, status: 'active' })

const showStepModal = ref(false)
const addingStep = ref(false)
const editingStepIndex = ref(-1)
const stepForm = ref({
  step_name: '',
  step_type: 'script',
  script_id: undefined as number | undefined,
  case_id: undefined as number | undefined,
  continue_on_failure: false,
  auto_fix: false,
  max_retries: 0,
  timeout: 300,
})
const waitSeconds = ref(5)

const savingSteps = ref(false)
const executing = ref(false)
const headlessEnabled = ref(true)  // 无头模式开关
const showRunResult = ref(false)
const runResult = ref<SuiteRun>({ suite_id: 0, project_id: 0 })
const runResults = ref<SuiteRunResult[]>([])

const resultColumns = [
  { title: '序号', dataIndex: 'sort_order', width: 60 },
  { title: '步骤名称', dataIndex: 'step_name' },
  { title: '状态', key: 'status', width: 100 },
  { title: '耗时(s)', dataIndex: 'duration', width: 80 },
  { title: '错误信息', key: 'error' },
]

async function loadSuites() {
  try {
    suites.value = await getSuites(projectId)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载失败')
  }
}

async function loadScripts() {
  try {
    scriptList.value = await getScripts(projectId)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载脚本失败')
  }
}

async function loadCases() {
  try {
    caseList.value = await getCases(projectId)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载用例失败')
  }
}

async function selectSuite(suite: AutomationSuite) {
  currentSuite.value = suite
  try {
    steps.value = await getSuiteSteps(projectId, suite.id!)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载步骤失败')
  }
}

async function handleCreate() {
  if (!createForm.value.name) {
    message.warning('请输入套件名称')
    return
  }
  creating.value = true
  try {
    const newSuite = await createSuite(projectId, createForm.value)
    message.success('创建成功')
    showCreateModal.value = false
    createForm.value = { name: '', description: '', plan_id: undefined }
    await loadSuites()
    await selectSuite(newSuite)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

function openEditModal() {
  if (!currentSuite.value) return
  editForm.value = {
    name: currentSuite.value.name,
    description: currentSuite.value.description || '',
    plan_id: currentSuite.value.plan_id || undefined,
    status: currentSuite.value.status || 'active',
  }
  showEditModal.value = true
}

async function handleUpdate() {
  if (!currentSuite.value) return
  updating.value = true
  try {
    const updated = await updateSuite(projectId, currentSuite.value.id!, editForm.value)
    message.success('更新成功')
    showEditModal.value = false
    currentSuite.value = updated
    await loadSuites()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '更新失败')
  } finally {
    updating.value = false
  }
}

async function handleDelete() {
  if (!currentSuite.value) return
  try {
    await deleteSuite(projectId, currentSuite.value.id!)
    message.success('删除成功')
    currentSuite.value = null
    steps.value = []
    await loadSuites()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '删除失败')
  }
}

function openAddStep() {
  resetStepForm()
  showStepModal.value = true
}

function openEditStep(index: number) {
  const step = steps.value[index]
  if (!step) return
  editingStepIndex.value = index
  stepForm.value = {
    step_name: step.step_name,
    step_type: step.step_type || 'script',
    script_id: step.script_id || undefined,
    case_id: step.case_id || undefined,
    continue_on_failure: step.continue_on_failure || false,
    auto_fix: step.auto_fix || false,
    max_retries: step.max_retries || 0,
    timeout: step.timeout || 300,
  }
  if (step.step_type === 'wait' && step.params?.seconds) {
    waitSeconds.value = step.params.seconds
  } else {
    waitSeconds.value = 5
  }
  showStepModal.value = true
}

function resetStepForm() {
  editingStepIndex.value = -1
  stepForm.value = {
    step_name: '',
    step_type: 'script',
    script_id: undefined,
    case_id: undefined,
    continue_on_failure: false,
    auto_fix: false,
    max_retries: 0,
    timeout: 300,
  }
  waitSeconds.value = 5
}

function saveStep() {
  if (!stepForm.value.step_name) {
    message.warning('请输入步骤名称')
    return
  }
  const stepData: SuiteStep = {
    step_name: stepForm.value.step_name,
    step_type: stepForm.value.step_type,
    script_id: stepForm.value.step_type === 'script' ? stepForm.value.script_id : null,
    case_id: stepForm.value.step_type === 'case' ? stepForm.value.case_id : null,
    sort_order: editingStepIndex.value >= 0 ? steps.value[editingStepIndex.value].sort_order : steps.value.length,
    continue_on_failure: stepForm.value.continue_on_failure,
    auto_fix: stepForm.value.auto_fix,
    max_retries: stepForm.value.max_retries,
    timeout: stepForm.value.timeout,
    params: stepForm.value.step_type === 'wait' ? { seconds: waitSeconds.value } : {},
  }
  if (editingStepIndex.value >= 0) {
    steps.value[editingStepIndex.value] = { ...steps.value[editingStepIndex.value], ...stepData }
    message.success('步骤已更新，记得点击"保存步骤"')
  } else {
    steps.value.push(stepData)
    message.success('步骤已添加，记得点击"保存步骤"')
  }
  showStepModal.value = false
  resetStepForm()
}

function removeStep(index: number) {
  steps.value.splice(index, 1)
  steps.value.forEach((s, i) => { s.sort_order = i })
}

function moveStep(index: number, direction: number) {
  const newIndex = index + direction
  if (newIndex < 0 || newIndex >= steps.value.length) return
  const temp = steps.value[index]
  steps.value[index] = steps.value[newIndex]
  steps.value[newIndex] = temp
  steps.value.forEach((s, i) => { s.sort_order = i })
}

async function saveSteps() {
  if (!currentSuite.value) return
  savingSteps.value = true
  try {
    const saved = await batchUpdateSteps(projectId, currentSuite.value.id!, steps.value)
    steps.value = saved
    message.success('步骤保存成功')
    await loadSuites()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '保存失败')
  } finally {
    savingSteps.value = false
  }
}

async function handleExecute() {
  if (!currentSuite.value) return
  if (steps.value.length === 0) {
    message.warning('请先添加步骤')
    return
  }
  executing.value = true
  try {
    const result = await executeSuite(projectId, currentSuite.value.id!, { headless: headlessEnabled.value })
    message.success(`编排执行已提交（运行ID: ${result.run_id}）`)
    // 跳转到执行详情页
    router.push(`/projects/${projectId}/suite-runs/${result.run_id}`)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '执行失败')
  } finally {
    executing.value = false
  }
}

async function loadRunResult(runId: number) {
  try {
    runResult.value = await getSuiteRun(projectId, runId)
    runResults.value = await getSuiteRunResults(projectId, runId)
    showRunResult.value = true
    await loadSuites()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载结果失败')
  }
}

// 辅助函数
function getStatusColor(status?: string) {
  const map: Record<string, string> = { active: 'green', draft: 'orange', archived: 'default' }
  return map[status || ''] || 'default'
}
function getStatusText(status?: string) {
  const map: Record<string, string> = { active: '可用', draft: '草稿', archived: '已归档' }
  return map[status || ''] || status
}
function getSuiteStatusColor(status?: string | null) {
  return getRunStatusColor(status)
}
function getRunStatusColor(status?: string | null) {
  const map: Record<string, string> = { passed: 'green', failed: 'red', partial: 'orange', running: 'blue', pending: 'default' }
  return map[status || ''] || 'default'
}
function getRunStatusText(status?: string | null) {
  const map: Record<string, string> = { passed: '通过', failed: '失败', partial: '部分通过', running: '执行中', pending: '等待中', skipped: '已跳过' }
  return map[status || ''] || status
}
function getStepTypeColor(type?: string) {
  const map: Record<string, string> = { script: 'blue', case: 'green', wait: 'orange' }
  return map[type || ''] || 'default'
}
function getStepTypeText(type?: string) {
  const map: Record<string, string> = { script: '脚本', case: '用例', wait: '等待' }
  return map[type || ''] || type
}
function getScheduleText(type?: string) {
  const map: Record<string, string> = { manual: '手动', once: '一次性', cron: '定时' }
  return map[type || ''] || type
}

function getPlanName(planId?: number | null) {
  if (!planId) return '无'
  const plan = testPlans.value.find(p => p.id === planId)
  return plan ? plan.name : `#${planId}`
}

onMounted(() => {
  loadSuites()
  loadScripts()
  loadCases()
  loadTestPlans()
})

async function loadTestPlans() {
  try {
    const res = await getPlans(projectId, { page_size: 100 })
    testPlans.value = res.items || []
  } catch (e) {
    // 忽略
  }
}
</script>

<style scoped>
.suites-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 20px; }

.content-wrapper { display: flex; gap: 16px; align-items: flex-start; }
.suite-list { width: 300px; flex-shrink: 0; }
.suite-detail { flex: 1; min-width: 0; }

.suite-items { max-height: calc(100vh - 200px); overflow-y: auto; }
.suite-item {
  padding: 12px;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s;
}
.suite-item:hover { border-color: #1677ff; background: #f5f9ff; }
.suite-item.active { border-color: #1677ff; background: #e6f4ff; }
.suite-item-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.suite-name { font-weight: 500; font-size: 14px; }
.suite-item-meta { display: flex; gap: 12px; font-size: 12px; color: #666; margin-bottom: 4px; }
.suite-item-time { font-size: 11px; color: #999; }

.detail-title { display: flex; align-items: center; gap: 8px; }

.steps-list { margin-top: 8px; }
.step-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  margin-bottom: 8px;
  background: #fafafa;
}
.step-order {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #1677ff;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 500;
  flex-shrink: 0;
}
.step-content { flex: 1; min-width: 0; }
.step-header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.step-name { font-weight: 500; font-size: 14px; }
.step-meta { font-size: 12px; color: #666; display: flex; gap: 12px; }
.step-actions { display: flex; gap: 4px; flex-shrink: 0; }
</style>
