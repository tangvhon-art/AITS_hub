<template>
  <a-modal
    :open="open"
    title="AI 生成测试用例"
    width="800px"
    :footer="null"
    @cancel="handleCancel"
    @update:open="(v: boolean) => emit('update:open', v)"
  >
    <!-- 配置区 -->
    <div v-if="!generating && generatedCases.length === 0">
      <a-form layout="vertical">
        <a-form-item label="选择接口">
          <a-select
            v-model:value="config.api_id"
            show-search
            placeholder="选择要生成用例的接口（可输入名称搜索）"
            :filter-option="false"
            :loading="apiSearching"
            :not-found-content="apiSearching ? '搜索中...' : '未找到匹配的接口'"
            @search="handleApiSearch"
          >
            <a-select-option v-for="api in apiList" :key="api.id" :value="api.id">
              [{{ api.method }}] {{ api.name }} - {{ api.path }}
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="生成策略">
              <a-select v-model:value="config.strategy" placeholder="选择策略">
                <a-select-option value="normal">正常流程</a-select-option>
                <a-select-option value="abnormal">异常场景</a-select-option>
                <a-select-option value="boundary">边界值</a-select-option>
                <a-select-option value="comprehensive">全面覆盖</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="用例数量">
              <a-input-number v-model:value="config.case_count" :min="1" :max="20" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="断言深度">
              <a-select v-model:value="config.assertion_depth" placeholder="选择深度">
                <a-select-option value="basic">基础（仅状态码）</a-select-option>
                <a-select-option value="standard">标准（状态码+关键字段）</a-select-option>
                <a-select-option value="deep">深度（全字段+业务规则）</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="模型配置">
          <a-select v-model:value="config.llm_config_id" placeholder="使用默认模型" allow-clear>
            <a-select-option v-for="cfg in llmConfigs" :key="cfg.id" :value="cfg.id">{{ cfg.name }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="Prompt 模板">
          <a-select
            v-model:value="config.prompt_id"
            placeholder="使用默认 Prompt"
            allow-clear
            :options="apiTestPrompts.map(p => ({ label: p.name, value: p.id }))"
          />
        </a-form-item>
      </a-form>
      <div class="modal-actions">
        <a-button @click="handleCancel">取消</a-button>
        <a-button type="primary" :loading="generating" :disabled="!config.api_id" @click="handleGenerate">
          开始生成
        </a-button>
      </div>
    </div>

    <!-- 生成中 -->
    <div v-else-if="generating" class="generating">
      <a-spin size="large" />
      <p style="margin-top: 16px">AI 正在生成用例，请稍候...</p>
      <a-progress :percent="progress" status="active" style="margin-top: 16px" />
    </div>

    <!-- 生成结果 -->
    <div v-else class="result-area">
      <div class="result-header">
        <span v-if="autoSaved">共生成 {{ generatedCases.length }} 个用例，已自动保存至用例列表</span>
        <span v-else>共生成 {{ generatedCases.length }} 个用例，已选 {{ selectedCases.length }} 个</span>
        <a-space>
          <a-button @click="handleRegenerate">重新生成</a-button>
        </a-space>
      </div>
      <div class="case-list">
        <div v-for="(caseItem, index) in generatedCases" :key="index" class="case-item">
          <a-checkbox v-model:checked="caseItem._selected" />
          <div class="case-content">
            <div class="case-title">
              <a-tag :color="getPriorityColor(caseItem.priority)">{{ caseItem.priority }}</a-tag>
              <span>{{ caseItem.name }}</span>
            </div>
            <div class="case-desc">{{ caseItem.description }}</div>
            <div class="case-assertions">
              <a-tag v-for="(assertion, idx) in (caseItem.assertions || []).slice(0, 3)" :key="idx" color="blue">
                {{ assertion.type }}
              </a-tag>
              <span v-if="(caseItem.assertions || []).length > 3" class="more">
                +{{ (caseItem.assertions || []).length - 3 }}
              </span>
            </div>
          </div>
        </div>
      </div>
      <div class="modal-actions">
        <a-button @click="handleCancel">取消</a-button>
        <a-button
          v-if="!autoSaved"
          type="primary"
          :loading="saving"
          :disabled="selectedCases.length === 0"
          @click="handleSave"
        >
          保存选中 ({{ selectedCases.length }})
        </a-button>
        <a-button v-else type="primary" @click="handleDone">完成</a-button>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { message } from 'ant-design-vue'
import { apiCasesApi, apiDefinitionsApi } from '@/api/apiTest'
import { getLLMConfigs } from '@/api/llm'
import { promptsApi, type Prompt } from '@/api/prompts'

const props = defineProps<{
  open: boolean
  projectId: number
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'saved'): void
}>()

const generating = ref(false)
const saving = ref(false)
const autoSaved = ref(false)
const progress = ref(0)
const taskId = ref<number | null>(null)
const apiList = ref<any[]>([])
const llmConfigs = ref<any[]>([])
const apiTestPrompts = ref<Prompt[]>([])
const generatedCases = ref<any[]>([])
let pollTimer: any = null

const config = ref({
  api_id: null as number | null,
  strategy: 'comprehensive',
  case_count: 5,
  assertion_depth: 'standard',
  llm_config_id: null as number | null,
  prompt_id: null as number | null,
  coverage_scenarios: [] as string[],
})

const selectedCases = computed(() => generatedCases.value.filter(c => c._selected))

const getPriorityColor = (priority: string) => {
  const colors: Record<string, string> = { P0: 'red', P1: 'orange', P2: 'blue', P3: 'default' }
  return colors[priority] || 'default'
}

const loadApis = async (keyword?: string) => {
  try {
    const res = await apiDefinitionsApi.list(props.projectId, {
      keyword: keyword || undefined,
      page_size: keyword ? 20 : 100,
    })
    apiList.value = res.items
  } catch {}
}

// 远程按名称/路径搜索接口（防抖 300ms）
let apiSearchTimer: any = null
const apiSearching = ref(false)
const handleApiSearch = (keyword: string) => {
  if (apiSearchTimer) clearTimeout(apiSearchTimer)
  apiSearchTimer = setTimeout(() => {
    apiSearching.value = true
    loadApis(keyword.trim() || undefined)
      .catch(() => {})
      .finally(() => {
        apiSearching.value = false
      })
  }, 300)
}

const loadLlmConfigs = async () => {
  try {
    llmConfigs.value = await getLLMConfigs()
  } catch {}
}

const loadPrompts = async () => {
  try {
    apiTestPrompts.value = await promptsApi.list('api_case_generation')
  } catch {}
}

const handleGenerate = async () => {
  if (!config.value.api_id) {
    message.warning('请选择接口')
    return
  }
  generating.value = true
  progress.value = 10
  try {
    const res = await apiCasesApi.aiGenerate(props.projectId, config.value)
    taskId.value = res.task_id
    startPolling()
  } catch {
    generating.value = false
  }
}

const startPolling = () => {
  pollTimer = setInterval(async () => {
    if (!taskId.value) return
    try {
      const status = await apiCasesApi.aiGenerateStatus(props.projectId, taskId.value)
      progress.value = Math.min(90, progress.value + 10)
      if (status.status === 'success') {
        clearInterval(pollTimer)
        generating.value = false
        progress.value = 100
        const cases = status.output_result?.cases || []
        generatedCases.value = cases.map((c: any) => ({ ...c, _selected: true }))
        // 生成任务已在后端自动落库（api_test_cases），无需再手动保存
        autoSaved.value = true
      } else if (status.status === 'failed') {
        clearInterval(pollTimer)
        generating.value = false
        message.error(status.error_message || '生成失败')
      }
    } catch {}
  }, 2000)
}

const handleRegenerate = () => {
  generatedCases.value = []
  taskId.value = null
  progress.value = 0
  autoSaved.value = false
}

const handleDone = () => {
  if (pollTimer) clearInterval(pollTimer)
  emit('saved')
  emit('update:open', false)
}

const handleSave = async () => {
  if (!taskId.value || selectedCases.value.length === 0) return
  saving.value = true
  try {
    const indices = selectedCases.value.map((c: any) => generatedCases.value.indexOf(c))
    const res = await apiCasesApi.aiGenerateSave(props.projectId, taskId.value, { selected_indices: indices })
    message.success(res.already_saved ? '用例已自动保存' : `已保存 ${res.saved_count} 个用例`)
    emit('saved')
    emit('update:open', false)
  } catch (e) {
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}

const handleCancel = () => {
  if (pollTimer) clearInterval(pollTimer)
  generatedCases.value = []
  taskId.value = null
  progress.value = 0
  autoSaved.value = false
  emit('update:open', false)
}

watch(() => props.open, (val) => {
  if (val) {
    loadApis()
    loadLlmConfigs()
    loadPrompts()
  }
})

onMounted(() => {
  if (props.open) {
    loadApis()
    loadLlmConfigs()
    loadPrompts()
  }
})
</script>

<style scoped>
.generating {
  text-align: center;
  padding: 40px 0;
}
.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.case-list {
  max-height: 400px;
  overflow: auto;
  border: 1px solid #f0f0f0;
  border-radius: 4px;
}
.case-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  border-bottom: 1px solid #f0f0f0;
}
.case-item:last-child {
  border-bottom: none;
}
.case-content {
  flex: 1;
}
.case-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.case-desc {
  color: #8c8c8c;
  font-size: 13px;
  margin-bottom: 4px;
}
.case-assertions {
  display: flex;
  gap: 4px;
  align-items: center;
}
.more {
  color: #8c8c8c;
  font-size: 12px;
}
.modal-actions {
  margin-top: 16px;
  text-align: right;
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
</style>
