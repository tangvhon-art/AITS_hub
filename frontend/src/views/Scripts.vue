<template>
  <div class="scripts-page">
    <div class="page-header">
      <h2>自动化脚本库</h2>
      <a-button type="primary" @click="showCreateModal = true">
        <PlusOutlined /> 新建脚本
      </a-button>
    </div>

    <div class="content-wrapper">
      <!-- 左侧脚本列表 -->
      <div class="script-list">
        <a-card title="脚本列表" :bordered="false">
          <a-input
            v-model:value="searchKeyword"
            placeholder="搜索脚本名称"
            allow-clear
            style="margin-bottom: 12px"
          >
            <template #prefix><SearchOutlined /></template>
          </a-input>
          <a-select
            v-model:value="filterStatus"
            placeholder="筛选状态"
            allow-clear
            style="width: 100%; margin-bottom: 12px"
          >
            <a-select-option value="active">可用</a-select-option>
            <a-select-option value="draft">草稿</a-select-option>
            <a-select-option value="deprecated">已废弃</a-select-option>
          </a-select>
          <a-space style="width: 100%; margin-bottom: 12px">
            <a-button type="primary" @click="handleSearch">查询</a-button>
            <a-button @click="handleReset">重置</a-button>
          </a-space>

          <div class="script-items">
            <div
              v-for="script in pagedScripts"
              :key="script.id"
              class="script-item"
              :class="{ active: currentScript?.id === script.id }"
              @click="selectScript(script)"
            >
              <div class="script-item-header">
                <span class="script-name">{{ script.name }}</span>
                <a-tag :color="getTypeColor(script.script_type)" size="small">
                  {{ getTypeText(script.script_type) }}
                </a-tag>
              </div>
              <div class="script-item-meta">
                <span>v{{ script.version }}</span>
                <span v-if="script.last_run_status" :class="`status-${script.last_run_status}`">
                  {{ script.last_run_status }}
                </span>
                <span>运行 {{ script.total_runs || 0 }} 次</span>
              </div>
              <div class="script-item-time">{{ $formatDateTime(script.updated_at) }}</div>
            </div>
            <a-empty v-if="filteredScripts.length === 0" description="暂无脚本" />
          </div>
          <div class="script-pagination" v-if="filteredScripts.length > scriptPageSize">
            <a-pagination
              v-model:current="scriptPageCurrent"
              :page-size="scriptPageSize"
              :total="filteredScripts.length"
              size="small"
              simple
            />
          </div>
        </a-card>
      </div>

      <!-- 右侧详情/编辑器 -->
      <div class="script-detail">
        <a-card v-if="currentScript" :bordered="false">
          <template #title>
            <div class="detail-title">
              <span>{{ currentScript.name }}</span>
              <a-tag :color="getStatusColor(currentScript.status)">{{ getStatusText(currentScript.status) }}</a-tag>
            </div>
          </template>
          <div class="detail-actions">
            <a-space wrap>
              <a-button v-if="currentScript.status === 'generating'" @click="refreshCurrentScript" :loading="refreshing">
                <ReloadOutlined /> 刷新
              </a-button>
              <a-button @click="openEditInfo" :disabled="currentScript.status === 'generating'">
                <EditOutlined /> 编辑信息
              </a-button>
              <a-button @click="goHealingRecords">
                <MedicineBoxOutlined /> 自愈记录
              </a-button>
              <a-button @click="handleDuplicate">复制</a-button>
              <a-tooltip title="执行失败时自动调用AI重写整个脚本并重试（脚本级修复，自愈无法解决时兜底）">
                <a-space size="small">
                  <a-switch v-model:checked="autoFixEnabled" size="small" :disabled="running" />
                  <span style="font-size: 12px; color: #666">自动修复</span>
                </a-space>
              </a-tooltip>
              <a-tooltip title="关闭后将以可视化浏览器窗口运行">
                <a-space size="small">
                  <a-switch v-model:checked="headlessEnabled" size="small" :disabled="running" />
                  <span style="font-size: 12px; color: #666">无头模式</span>
                </a-space>
              </a-tooltip>
              <a-tooltip title="执行中元素定位失败时自动尝试备选定位器/AI推理/视觉定位（元素级修复，优先于自动修复）">
                <a-space size="small">
                  <a-switch v-model:checked="healEnabled" size="small" :disabled="running" @change="toggleHealEnabled" />
                  <span style="font-size: 12px; color: #666">自愈</span>
                </a-space>
              </a-tooltip>
              <a-button type="primary" @click="handleRun" :loading="running" :disabled="currentScript.status === 'generating'">
                <PlayCircleOutlined /> 运行
              </a-button>
              <a-button @click="showHistoryModal = true; loadScriptRuns()">
                <HistoryOutlined /> 历史
              </a-button>
              <a-popconfirm title="确定删除该脚本？" @confirm="handleDelete">
                <a-button danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </div>

          <a-descriptions :column="3" size="small" bordered style="margin-bottom: 16px">
            <a-descriptions-item label="脚本类型">{{ getTypeText(currentScript.script_type) }}</a-descriptions-item>
            <a-descriptions-item label="语言">{{ currentScript.language }}</a-descriptions-item>
            <a-descriptions-item label="版本">v{{ currentScript.version }}</a-descriptions-item>
            <a-descriptions-item label="目标URL" :span="3">{{ currentScript.target_url || '-' }}</a-descriptions-item>
            <a-descriptions-item label="关联用例">{{ currentScript.case_id || '无' }}</a-descriptions-item>
            <a-descriptions-item label="来源执行">{{ currentScript.source_run_id || '手动创建' }}</a-descriptions-item>
            <a-descriptions-item label="标签">{{ currentScript.tags || '-' }}</a-descriptions-item>
            <a-descriptions-item label="累计运行">{{ currentScript.total_runs || 0 }} 次</a-descriptions-item>
            <a-descriptions-item label="自愈次数">{{ currentScript.heal_count || 0 }} 次</a-descriptions-item>
            <a-descriptions-item label="通过/失败">{{ currentScript.pass_count || 0 }} / {{ currentScript.fail_count || 0 }}</a-descriptions-item>
            <a-descriptions-item label="最近运行" :span="3">
              <span v-if="currentScript.last_run_at">
                {{ currentScript.last_run_status }} · {{ $formatDateTime(currentScript.last_run_at) }}
              </span>
              <span v-else>从未运行</span>
            </a-descriptions-item>
            <a-descriptions-item label="所属编排" :span="3">
              <template v-if="scriptSuites.length > 0">
                <a-tag
                  v-for="suite in scriptSuites"
                  :key="suite.suite_id"
                  color="blue"
                  style="margin-bottom: 4px"
                >
                  {{ suite.suite_name }}（{{ suite.step_names.join(', ') }}）
                </a-tag>
              </template>
              <span v-else style="color: #999">未被任何编排套件引用</span>
            </a-descriptions-item>
            <a-descriptions-item label="描述" :span="3">{{ currentScript.description || '-' }}</a-descriptions-item>
          </a-descriptions>

          <a-divider>脚本内容</a-divider>

          <a-alert
            v-if="currentScript.status === 'generating'"
            message="AI正在生成脚本内容，请稍候..."
            description="生成完成后状态将自动变为可用，可点击右上角刷新按钮查看最新内容"
            type="info"
            show-icon
            style="margin-bottom: 12px"
          />

          <div class="editor-toolbar">
            <a-space>
              <a-button size="small" @click="editing = !editing" :disabled="currentScript.status === 'generating'">
                {{ editing ? '取消编辑' : '编辑脚本' }}
              </a-button>
              <a-button v-if="editing" type="primary" size="small" @click="handleSave" :loading="saving">
                保存
              </a-button>
            </a-space>
          </div>

          <textarea
            v-if="editing"
            v-model="editContent"
            class="script-editor"
            spellcheck="false"
          ></textarea>
          <pre v-else class="script-content">{{ currentScript.script_content }}</pre>
        </a-card>

        <a-empty v-else description="请选择左侧脚本查看详情" />
      </div>
    </div>

    <!-- 新建脚本弹窗 -->
    <a-modal
      v-model:open="showCreateModal"
      title="新建脚本"
      @ok="handleCreate"
      :confirm-loading="creating"
    >
      <a-form layout="vertical" :model="createForm">
        <a-form-item :label="createForm.ai_generate ? '脚本名称（可选）' : '脚本名称'">
          <a-input v-model:value="createForm.name" placeholder="请输入脚本名称，AI生成模式可不填" />
          <span v-if="createForm.ai_generate" style="color: #666; font-size: 12px">不填写将由AI根据描述自动生成</span>
        </a-form-item>
        <a-form-item label="AI生成脚本">
          <a-switch v-model:checked="createForm.ai_generate" />
          <span style="margin-left: 8px; color: #666; font-size: 12px">开启后将根据描述自动生成Playwright脚本（异步）</span>
        </a-form-item>
        <template v-if="createForm.ai_generate">
          <a-form-item :label="createForm.ai_generate ? '测试需求描述（必填）' : '描述'">
            <a-textarea
              v-model:value="createForm.description"
              :rows="4"
              :placeholder="createForm.ai_generate ? '请描述测试需求，例如：打开登录页，输入用户名admin，不输入密码，点击登录按钮，验证错误提示' : '请输入描述'"
            />
          </a-form-item>
          <a-form-item label="Prompt 模板">
            <a-select
              v-model:value="createForm.prompt_id"
              placeholder="使用默认 Prompt"
              allow-clear
              :options="scriptPrompts.map(p => ({ label: p.name, value: p.id }))"
            />
          </a-form-item>
          <a-form-item label="模型配置">
            <a-select
              v-model:value="createForm.llm_config_id"
              placeholder="使用默认模型"
              allow-clear
              :options="llmConfigs.map(cfg => ({ label: cfg.name, value: cfg.id }))"
            />
          </a-form-item>
        </template>
        <a-form-item v-if="!createForm.ai_generate" label="目标URL">
          <a-input v-model:value="createForm.target_url" placeholder="https://example.com" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 编辑脚本信息弹窗 -->
    <a-modal
      v-model:open="showEditInfoModal"
      title="编辑脚本信息"
      @ok="handleSaveInfo"
      :confirm-loading="savingInfo"
    >
      <a-form layout="vertical" :model="editInfoForm">
        <a-form-item label="脚本名称" required>
          <a-input v-model:value="editInfoForm.name" placeholder="请输入脚本名称" :maxlength="200" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="editInfoForm.description" :rows="3" placeholder="请输入描述" />
        </a-form-item>
        <a-form-item label="目标URL">
          <a-input v-model:value="editInfoForm.target_url" placeholder="https://example.com" />
        </a-form-item>
        <a-form-item label="标签">
          <a-input v-model:value="editInfoForm.tags" placeholder="多个标签用逗号分隔" />
        </a-form-item>
        <a-form-item label="状态">
          <a-select v-model:value="editInfoForm.status">
            <a-select-option value="active">可用</a-select-option>
            <a-select-option value="draft">草稿</a-select-option>
            <a-select-option value="deprecated">已废弃</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 运行结果弹窗 -->
    <a-modal v-model:open="showRunResult" title="脚本执行结果" :footer="null">
      <a-result
        v-if="runResult.status === 'running'"
        status="info"
        title="执行中..."
        sub-title="脚本正在后台执行，请稍候..."
      >
        <template #extra>
          <a-spin />
          <p style="margin-top: 12px; color: #999">已耗时: {{ runResult.duration }}s</p>
          <p v-if="autoFixEnabled" style="color: #1890ff">已开启自动修复，失败后将自动重试</p>
        </template>
      </a-result>
      <a-result
        v-else
        :status="runResult.status === 'passed' ? 'success' : 'error'"
        :title="runResult.status === 'passed' ? (runResult.auto_fixed ? '执行成功（已自动修复）' : '执行成功') : '执行失败'"
        :sub-title="`耗时: ${runResult.duration}s`"
      >
        <template #extra>
          <div v-if="runResult.auto_fixed" style="margin-bottom: 12px">
            <a-alert message="AI自动修复" :description="`脚本执行失败后已自动修复并重试成功，共重试 ${runResult.retry_count} 次，脚本已更新至新版本`" type="success" show-icon />
          </div>
          <a-alert v-if="runResult.error" message="错误信息" :description="runResult.error" type="error" show-icon />
        </template>
      </a-result>
    </a-modal>

    <!-- 历史执行记录弹窗 -->
    <a-modal
      v-model:open="showHistoryModal"
      :title="`历史执行记录 - ${currentScript?.name || ''}`"
      :footer="null"
      width="700px"
    >
      <a-spin :spinning="historyLoading">
        <a-table
          :columns="historyColumns"
          :data-source="scriptRuns"
          :pagination="historyPagination"
          @change="handleHistoryTableChange"
          row-key="id"
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'status'">
              <a-tag :color="record.status === 'passed' ? 'success' : 'error'">
                {{ record.status === 'passed' ? '通过' : '失败' }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'duration'">
              {{ record.duration ? record.duration + 's' : '-' }}
            </template>
            <template v-else-if="column.key === 'action'">
              <a-button type="link" size="small" @click="viewRunLog(record)">查看日志</a-button>
            </template>
          </template>
        </a-table>
        <a-empty v-if="scriptRuns.length === 0" description="暂无执行记录" />
      </a-spin>
    </a-modal>

    <!-- 执行日志详情弹窗 -->
    <a-modal
      v-model:open="showLogDetailModal"
      :title="`执行日志 #${selectedRunId}`"
      :footer="null"
      width="760px"
    >
      <a-spin :spinning="logDetailLoading">
        <div v-if="selectedRunDetail" style="margin-bottom: 12px">
          <a-descriptions :column="3" size="small">
            <a-descriptions-item label="状态">
              <a-tag :color="selectedRunDetail.status === 'passed' ? 'success' : 'error'">
                {{ selectedRunDetail.status === 'passed' ? '通过' : '失败' }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="耗时">{{ selectedRunDetail.duration }}s</a-descriptions-item>
            <a-descriptions-item label="执行时间">{{ selectedRunDetail.started_at || selectedRunDetail.created_at }}</a-descriptions-item>
          </a-descriptions>
          <a-alert
            v-if="selectedRunDetail.error_message"
            type="error"
            :message="selectedRunDetail.error_message"
            show-icon
            style="margin-top: 8px"
          />
        </div>
        <div class="log-container">
          <div v-if="logDetailList.length === 0" class="empty-log">
            <a-empty description="无执行日志" :image-style="{ height: 60 }" />
          </div>
          <div v-for="(log, idx) in logDetailList" :key="idx" class="log-item" :class="log.status">
            <div class="log-header">
              <span class="log-step">步骤 {{ idx + 1 }}</span>
              <span class="log-action">{{ log.action }}</span>
              <span v-if="log.duration != null" class="log-duration">{{ log.duration }}s</span>
            </div>
            <div class="log-detail">{{ log.detail || log.observation || JSON.stringify(log.params || {}) }}</div>
            <div v-if="log.error" class="log-error">{{ log.error }}</div>
          </div>
        </div>
      </a-spin>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUrlSearch } from '@/composables/useUrlSearch'
import { message } from 'ant-design-vue'
import {
  PlusOutlined, SearchOutlined, PlayCircleOutlined, ReloadOutlined, EditOutlined, HistoryOutlined, MedicineBoxOutlined
} from '@ant-design/icons-vue'
import {
  getScripts, createScript, updateScript, deleteScript,
  duplicateScript, runScript, getScriptRuns, getScriptSuites,
  type AutomationScript, type ScriptSuiteInfo
} from '@/api/automationScripts'
import { getExecutionRun } from '@/api/execution'
import { promptsApi, type Prompt } from '@/api/prompts'
import { getLLMConfigs } from '@/api/llm'

const route = useRoute()
const router = useRouter()
const { loadFromUrl, syncToUrl } = useUrlSearch()
const projectId = Number(route.params.id)

function goHealingRecords() {
  if (currentScript.value?.id) {
    router.push({ name: 'UiHealingRecords', params: { id: projectId }, query: { script_id: currentScript.value.id } })
  } else {
    router.push({ name: 'UiHealingRecords', params: { id: projectId } })
  }
}

const loading = ref(false)
const scripts = ref<AutomationScript[]>([])
const currentScript = ref<AutomationScript | null>(null)
const searchKeyword = ref('')
const filterStatus = ref<string | undefined>(undefined)
const scriptSuites = ref<ScriptSuiteInfo[]>([])

const showCreateModal = ref(false)
const creating = ref(false)
const createForm = ref({
  name: '',
  description: '',
  target_url: '',
  ai_generate: false,
  prompt_id: null as number | null,
  llm_config_id: null as number | null,
})
const scriptPrompts = ref<Prompt[]>([])
const llmConfigs = ref<any[]>([])

const editing = ref(false)
const editContent = ref('')
const saving = ref(false)

const running = ref(false)
const showRunResult = ref(false)
const runResult = ref<{ status: string; duration: number; error?: string; auto_fixed?: boolean; retry_count?: number }>({ status: '', duration: 0, error: '' })
const refreshing = ref(false)
const autoFixEnabled = ref(true)  // 自动修复开关
const headlessEnabled = ref(true)  // 无头模式开关
const healEnabled = ref(true)  // 自愈开关
const currentRunId = ref<number | null>(null)  // 当前后台执行的run_id
let runPollingTimer: any = null  // 轮询定时器

const showEditInfoModal = ref(false)
const savingInfo = ref(false)
const editInfoForm = ref({
  name: '',
  description: '',
  target_url: '',
  tags: '',
  status: 'active',
})

// 历史执行记录
const showHistoryModal = ref(false)
const historyLoading = ref(false)
const scriptRuns = ref<any[]>([])

const historyPagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  showTotal: (total: number) => `共 ${total} 条`,
})

function handleHistoryTableChange(pag: any) {
  historyPagination.current = pag.current
  historyPagination.pageSize = pag.pageSize
}
const historyColumns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
  { title: '状态', key: 'status', width: 90 },
  { title: '耗时', key: 'duration', width: 90 },
  { title: '执行时间', dataIndex: 'started_at', key: 'started_at', width: 180 },
  { title: '操作', key: 'action', width: 100 },
]

// 日志详情
const showLogDetailModal = ref(false)
const logDetailLoading = ref(false)
const selectedRunId = ref<number>(0)
const selectedRunDetail = ref<any>(null)
const logDetailList = ref<any[]>([])

const filteredScripts = computed(() => {
  let result = scripts.value
  if (searchKeyword.value) {
    result = result.filter(s => s.name?.includes(searchKeyword.value))
  }
  if (filterStatus.value) {
    result = result.filter(s => s.status === filterStatus.value)
  }
  return result
})

const scriptPageCurrent = ref(1)
const scriptPageSize = 15
const pagedScripts = computed(() => {
  const start = (scriptPageCurrent.value - 1) * scriptPageSize
  return filteredScripts.value.slice(start, start + scriptPageSize)
})

// 筛选条件变化时重置分页
watch([searchKeyword, filterStatus], () => { scriptPageCurrent.value = 1 })

function handleSearch() {
  syncToUrl({ keyword: searchKeyword.value, status: filterStatus.value })
}

function handleReset() {
  searchKeyword.value = ''
  filterStatus.value = undefined
  syncToUrl({ keyword: searchKeyword.value, status: filterStatus.value })
}

async function loadScripts() {
  loading.value = true
  try {
    scripts.value = await getScripts(projectId)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

async function selectScript(script: AutomationScript) {
  currentScript.value = script
  editing.value = false
  editContent.value = script.script_content || ''
  healEnabled.value = script.heal_enabled !== false
  // 获取关联的编排套件信息
  try {
    scriptSuites.value = await getScriptSuites(projectId, script.id!)
  } catch (e) {
    scriptSuites.value = []
  }
}

async function handleCreate() {
  if (!createForm.value.ai_generate && !createForm.value.name) {
    message.warning('请输入脚本名称')
    return
  }
  if (createForm.value.ai_generate && !createForm.value.description) {
    message.warning('AI生成模式下，请填写测试需求描述')
    return
  }
  creating.value = true
  try {
    const newScript = await createScript(projectId, createForm.value)
    if (createForm.value.ai_generate) {
      message.success(`脚本已创建，AI正在后台生成脚本内容（ID: ${newScript.id}），请稍候刷新查看`)
    } else {
      message.success('创建成功')
    }
    showCreateModal.value = false
    createForm.value = { name: '', description: '', target_url: '', ai_generate: false, prompt_id: null, llm_config_id: null }
    await loadScripts()
    selectScript(newScript)
    // AI生成模式下，3秒后自动刷新
    if (newScript.status === 'generating') {
      setTimeout(async () => {
        await loadScripts()
        const updated = scripts.value.find(s => s.id === newScript.id)
        if (updated) {
          selectScript(updated)
        }
      }, 3000)
    }
  } catch (e: any) {
    message.error(e.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

async function handleSave() {
  if (!currentScript.value) return
  saving.value = true
  try {
    const updated = await updateScript(projectId, currentScript.value.id!, {
      script_content: editContent.value
    })
    message.success('保存成功')
    currentScript.value = updated
    editing.value = false
    await loadScripts()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete() {
  if (!currentScript.value) return
  try {
    await deleteScript(projectId, currentScript.value.id!)
    message.success('删除成功')
    currentScript.value = null
    await loadScripts()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '删除失败')
  }
}

async function refreshCurrentScript() {
  if (!currentScript.value) return
  refreshing.value = true
  try {
    await loadScripts()
    const updated = scripts.value.find(s => s.id === currentScript.value!.id)
    if (updated) {
      currentScript.value = updated
      editContent.value = updated.script_content || ''
    }
    if (currentScript.value?.status === 'generating') {
      message.info('AI仍在生成中，请稍后再刷新')
    } else if (currentScript.value?.status === 'active') {
      message.success('脚本生成完成')
    }
  } catch (e: any) {
    message.error(e.response?.data?.detail || '刷新失败')
  } finally {
    refreshing.value = false
  }
}

async function toggleHealEnabled(checked: boolean) {
  if (!currentScript.value?.id) return
  try {
    await updateScript(projectId, currentScript.value.id, { heal_enabled: checked })
    currentScript.value.heal_enabled = checked
    message.success(checked ? '已开启自愈' : '已关闭自愈')
  } catch (e) {
    healEnabled.value = !checked
    message.error('设置失败')
  }
}

function openEditInfo() {
  if (!currentScript.value) return
  editInfoForm.value = {
    name: currentScript.value.name || '',
    description: currentScript.value.description || '',
    target_url: currentScript.value.target_url || '',
    tags: currentScript.value.tags || '',
    status: currentScript.value.status || 'active',
  }
  showEditInfoModal.value = true
}

async function handleSaveInfo() {
  if (!currentScript.value) return
  if (!editInfoForm.value.name) {
    message.warning('请输入脚本名称')
    return
  }
  savingInfo.value = true
  try {
    const updated = await updateScript(projectId, currentScript.value.id!, {
      name: editInfoForm.value.name,
      description: editInfoForm.value.description,
      target_url: editInfoForm.value.target_url,
      tags: editInfoForm.value.tags,
      status: editInfoForm.value.status,
    })
    message.success('保存成功')
    currentScript.value = updated
    showEditInfoModal.value = false
    await loadScripts()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '保存失败')
  } finally {
    savingInfo.value = false
  }
}

async function handleDuplicate() {
  if (!currentScript.value) return
  try {
    const newScript = await duplicateScript(projectId, currentScript.value.id!)
    message.success('复制成功')
    await loadScripts()
    selectScript(newScript)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '复制失败')
  }
}

async function handleRun() {
  if (!currentScript.value) return
  running.value = true
  showRunResult.value = true
  runResult.value = { status: 'running', duration: 0, error: '' }
  try {
    const result = await runScript(projectId, currentScript.value.id!, {
      headless: headlessEnabled.value,
      auto_fix: autoFixEnabled.value,
      max_retries: 2,
    })
    currentRunId.value = result.run_id
    // 开始轮询执行状态
    startRunPolling(result.run_id)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '执行失败')
    running.value = false
    runResult.value.status = 'failed'
    runResult.value.error = e.response?.data?.detail || '执行失败'
  }
}

function startRunPolling(runId: number) {
  // 清除之前的定时器
  if (runPollingTimer) {
    clearInterval(runPollingTimer)
  }
  // 每2秒轮询一次
  runPollingTimer = setInterval(async () => {
    try {
      const run = await getExecutionRun(projectId, runId)
      if (run.status === 'passed' || run.status === 'failed') {
        // 执行完成
        clearInterval(runPollingTimer)
        runPollingTimer = null
        running.value = false
        currentRunId.value = null

        // 解析执行日志，判断是否自动修复
        let autoFixed = false
        let retryCount = 0
        try {
          const logs = JSON.parse(run.execution_log || '[]')
          autoFixed = logs.some((l: any) => l.action === 'script_updated')
          retryCount = logs.filter((l: any) => l.action === 'ai_fix' && l.status === 'success').length
        } catch (e) {
          // ignore
        }

        runResult.value = {
          status: run.status,
          duration: run.duration || 0,
          error: run.error_message || '',
          auto_fixed: autoFixed,
          retry_count: retryCount,
        }

        // 刷新脚本列表
        await loadScripts()
        if (currentScript.value) {
          const updated = scripts.value.find(s => s.id === currentScript.value!.id)
          if (updated) currentScript.value = updated
        }
      } else {
        // 仍在执行中，更新耗时显示
        runResult.value.duration = run.duration || 0
      }
    } catch (e) {
      // 轮询出错，忽略
    }
  }, 2000)
}

async function loadScriptRuns() {
  if (!currentScript.value) return
  historyLoading.value = true
  try {
    scriptRuns.value = await getScriptRuns(projectId, currentScript.value.id!)
    historyPagination.total = scriptRuns.value.length
  } catch (e: any) {
    scriptRuns.value = []
    historyPagination.total = 0
  } finally {
    historyLoading.value = false
  }
}

async function viewRunLog(record: any) {
  selectedRunId.value = record.id
  showLogDetailModal.value = true
  logDetailLoading.value = true
  logDetailList.value = []
  selectedRunDetail.value = null
  try {
    const detail = await getExecutionRun(projectId, record.id)
    selectedRunDetail.value = detail
    let logData = detail.execution_log
    if (typeof logData === 'string' && logData) {
      try {
        logData = JSON.parse(logData)
      } catch {
        logData = []
      }
    }
    logDetailList.value = Array.isArray(logData) ? logData : []
  } catch (e: any) {
    message.error('加载执行日志失败')
  } finally {
    logDetailLoading.value = false
  }
}

function getTypeColor(type?: string) {
  const map: Record<string, string> = {
    ai_generated: 'blue',
    manual: 'green'
  }
  return map[type || ''] || 'default'
}

function getTypeText(type?: string) {
  const map: Record<string, string> = {
    ai_generated: 'AI生成',
    manual: '手动'
  }
  return map[type || ''] || type
}

function getStatusColor(status?: string) {
  const map: Record<string, string> = {
    active: 'green',
    draft: 'orange',
    deprecated: 'default',
    generating: 'blue',
    failed: 'red'
  }
  return map[status || ''] || 'default'
}

function getStatusText(status?: string) {
  const map: Record<string, string> = {
    active: '可用',
    draft: '草稿',
    deprecated: '已废弃',
    generating: 'AI生成中',
    failed: '生成失败'
  }
  return map[status || ''] || status
}

onMounted(() => {
  const params = loadFromUrl({ keyword: '', status: undefined })
  searchKeyword.value = params.keyword
  filterStatus.value = params.status
  loadScripts()
  promptsApi.list('script_generation').then(data => { scriptPrompts.value = data }).catch(() => {})
  getLLMConfigs().then(data => { llmConfigs.value = data }).catch(() => {})
})

onUnmounted(() => {
  if (runPollingTimer) {
    clearInterval(runPollingTimer)
  }
})
</script>

<style scoped>
.scripts-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 20px; }

.content-wrapper { display: flex; gap: 16px; align-items: flex-start; }
.script-list { width: 320px; flex-shrink: 0; }
.script-detail { flex: 1; min-width: 0; }

.script-items { max-height: calc(100vh - 280px); overflow-y: auto; }
.script-item {
  padding: 12px;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s;
}
.script-item:hover { border-color: #1677ff; background: #f5f9ff; }
.script-item.active { border-color: #1677ff; background: #e6f4ff; }
.script-item-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.script-name { font-weight: 500; font-size: 14px; }
.script-item-meta { display: flex; gap: 10px; font-size: 12px; color: #666; margin-bottom: 4px; }
.script-item-meta .status-passed { color: #52c41a; }
.script-item-meta .status-failed { color: #ff4d4f; }
.script-item-time { font-size: 11px; color: #999; }
.script-pagination { margin-top: 12px; text-align: center; }

.detail-title { display: flex; align-items: center; gap: 8px; }
.detail-actions { margin-bottom: 16px; }
.editor-toolbar { margin-bottom: 8px; }
.script-editor {
  width: 100%;
  min-height: 400px;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 13px;
  padding: 12px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  resize: vertical;
  line-height: 1.6;
}
.script-content {
  background: #fafafa;
  padding: 16px;
  border-radius: 6px;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 500px;
  overflow-y: auto;
  margin: 0;
}

.log-container {
  max-height: 500px;
  overflow-y: auto;
  background: #1e1e1e;
  border-radius: 8px;
  padding: 16px;
  min-height: 120px;
}
.empty-log {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 120px;
}
.log-item {
  margin-bottom: 10px;
  padding: 10px 12px;
  background: #2d2d2d;
  border-radius: 6px;
  border-left: 3px solid #1677ff;
}
.log-item.passed { border-left-color: #52c41a; }
.log-item.failed { border-left-color: #ff4d4f; }
.log-header {
  display: flex;
  gap: 12px;
  margin-bottom: 6px;
  align-items: center;
}
.log-step { color: #569cd6; font-weight: 600; font-size: 13px; }
.log-action { color: #6a9955; font-size: 13px; }
.log-duration { color: #dcdcaa; font-size: 12px; margin-left: auto; }
.log-detail { color: #d4d4d4; font-size: 13px; word-break: break-all; line-height: 1.6; }
.log-error { color: #f48771; font-size: 13px; margin-top: 4px; }
</style>
