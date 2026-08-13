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

          <div class="script-items">
            <div
              v-for="script in filteredScripts"
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
          <template #extra>
            <a-space>
              <a-button v-if="currentScript.status === 'generating'" @click="refreshCurrentScript" :loading="refreshing">
                <ReloadOutlined /> 刷新
              </a-button>
              <a-button @click="openEditInfo" :disabled="currentScript.status === 'generating'">
                <EditOutlined /> 编辑信息
              </a-button>
              <a-button @click="handleDuplicate">复制</a-button>
              <a-button type="primary" @click="handleRun" :loading="running" :disabled="currentScript.status === 'generating'">
                <PlayCircleOutlined /> 运行
              </a-button>
              <a-popconfirm title="确定删除该脚本？" @confirm="handleDelete">
                <a-button danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>

          <a-descriptions :column="3" size="small" bordered style="margin-bottom: 16px">
            <a-descriptions-item label="脚本类型">{{ getTypeText(currentScript.script_type) }}</a-descriptions-item>
            <a-descriptions-item label="语言">{{ currentScript.language }}</a-descriptions-item>
            <a-descriptions-item label="版本">v{{ currentScript.version }}</a-descriptions-item>
            <a-descriptions-item label="目标URL" :span="3">{{ currentScript.target_url || '-' }}</a-descriptions-item>
            <a-descriptions-item label="关联用例">{{ currentScript.case_id || '无' }}</a-descriptions-item>
            <a-descriptions-item label="来源执行">{{ currentScript.source_run_id || '手动创建' }}</a-descriptions-item>
            <a-descriptions-item label="标签">{{ currentScript.tags || '-' }}</a-descriptions-item>
            <a-descriptions-item label="累计运行">{{ currentScript.total_runs || 0 }} 次</a-descriptions-item>
            <a-descriptions-item label="通过/失败">{{ currentScript.pass_count || 0 }} / {{ currentScript.fail_count || 0 }}</a-descriptions-item>
            <a-descriptions-item label="最近运行" :span="3">
              <span v-if="currentScript.last_run_at">
                {{ currentScript.last_run_status }} · {{ $formatDateTime(currentScript.last_run_at) }}
              </span>
              <span v-else>从未运行</span>
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
        <a-form-item :label="createForm.ai_generate ? '测试需求描述（必填）' : '描述'">
          <a-textarea
            v-model:value="createForm.description"
            :rows="4"
            :placeholder="createForm.ai_generate ? '请描述测试需求，例如：打开登录页，输入用户名admin，不输入密码，点击登录按钮，验证错误提示' : '请输入描述'"
          />
        </a-form-item>
        <a-form-item label="目标URL">
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
        :status="runResult.status === 'passed' ? 'success' : 'error'"
        :title="runResult.status === 'passed' ? '执行成功' : '执行失败'"
        :sub-title="`耗时: ${runResult.duration}s`"
      >
        <template v-if="runResult.error" #extra>
          <a-alert message="错误信息" :description="runResult.error" type="error" show-icon />
        </template>
      </a-result>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  PlusOutlined, SearchOutlined, PlayCircleOutlined, ReloadOutlined, EditOutlined
} from '@ant-design/icons-vue'
import {
  getScripts, createScript, updateScript, deleteScript,
  duplicateScript, runScript,
  type AutomationScript
} from '@/api/automationScripts'

const route = useRoute()
const projectId = Number(route.params.id)

const loading = ref(false)
const scripts = ref<AutomationScript[]>([])
const currentScript = ref<AutomationScript | null>(null)
const searchKeyword = ref('')
const filterStatus = ref<string | undefined>(undefined)

const showCreateModal = ref(false)
const creating = ref(false)
const createForm = ref({
  name: '',
  description: '',
  target_url: '',
  ai_generate: false,
})

const editing = ref(false)
const editContent = ref('')
const saving = ref(false)

const running = ref(false)
const showRunResult = ref(false)
const runResult = ref<{ status: string; duration: number; error?: string }>({ status: '', duration: 0, error: '' })
const refreshing = ref(false)

const showEditInfoModal = ref(false)
const savingInfo = ref(false)
const editInfoForm = ref({
  name: '',
  description: '',
  target_url: '',
  tags: '',
  status: 'active',
})

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

function selectScript(script: AutomationScript) {
  currentScript.value = script
  editing.value = false
  editContent.value = script.script_content || ''
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
    createForm.value = { name: '', description: '', target_url: '', ai_generate: false }
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
  try {
    const result = await runScript(projectId, currentScript.value.id!, { headless: true })
    runResult.value = result
    showRunResult.value = true
    await loadScripts()
    if (currentScript.value) {
      const updated = scripts.value.find(s => s.id === currentScript.value!.id)
      if (updated) currentScript.value = updated
    }
  } catch (e: any) {
    message.error(e.response?.data?.detail || '执行失败')
  } finally {
    running.value = false
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
  loadScripts()
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

.detail-title { display: flex; align-items: center; gap: 8px; }
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
</style>
