<template>
  <a-modal
    :open="open"
    title="生成测试用例"
    :width="720"
    :confirm-loading="submitting"
    :ok-text="submitting ? '生成中...' : '生成用例'"
    @ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-spin :spinning="loading">
      <div v-if="requirement" class="req-info">
        <span class="label">需求：</span>
        <span class="value">{{ requirement.title }}</span>
      </div>

      <!-- 未拆分 / 拆分失败 -->
      <div v-if="splitStatus === 'pending' || splitStatus === 'failed'" class="split-prompt">
        <a-empty :description="splitStatus === 'failed' ? '功能点拆分失败，请重新拆分' : '该需求尚未拆分功能点'">
          <a-button type="primary" :loading="splitting" @click="handleSplit">
            {{ splitting ? '拆分中...' : '立即拆分功能点' }}
          </a-button>
        </a-empty>
      </div>

      <!-- 拆分中 -->
      <div v-else-if="splitStatus === 'splitting'" class="split-prompt">
        <a-spin tip="正在拆分功能点，请稍候...">
          <div style="height: 120px"></div>
        </a-spin>
      </div>

      <!-- 功能点选择 -->
      <div v-else>
        <div class="select-toolbar">
          <a-space>
            <a-button size="small" @click="selectAll">全选</a-button>
            <a-button size="small" @click="invertSelect">反选</a-button>
            <a-button size="small" @click="selectedIds = []">清空</a-button>
            <a-button size="small" type="link" @click="handleSplit" :loading="splitting">重新拆分</a-button>
          </a-space>
          <span class="selected-count">已选 <strong>{{ selectedIds.length }}</strong> / {{ totalFeatures }} 个功能点</span>
        </div>

        <a-collapse v-model:activeKey="activeModules" class="feature-collapse">
          <a-collapse-panel v-for="mod in modules" :key="mod.module_name">
            <template #header>
              <span class="module-header">
                <span class="module-name">{{ mod.module_name }}</span>
                <a-tag color="blue">{{ mod.features.length }} 个功能点</a-tag>
                <span class="module-selected-count">
                  已选 {{ getModuleSelectedCount(mod) }}
                </span>
              </span>
            </template>
            <div
              v-for="feat in mod.features"
              :key="feat.id"
              class="feature-item"
              :class="{ selected: selectedIds.includes(feat.id) }"
            >
              <a-checkbox
                :checked="selectedIds.includes(feat.id)"
                @change="(e: any) => toggleFeature(feat.id, e.target.checked)"
              >
                <span class="feat-name">{{ feat.name }}</span>
              </a-checkbox>
              <a-tag :color="priorityColor(feat.priority)" class="feat-priority">{{ feat.priority }}</a-tag>
              <div class="feat-desc" v-if="feat.description">{{ feat.description }}</div>
              <div class="feat-meta" v-if="feat.design_methods?.length">
                <span class="meta-label">建议方法：</span>
                <a-tag v-for="m in feat.design_methods" :key="m" size="small" color="cyan">{{ m }}</a-tag>
              </div>
            </div>
          </a-collapse-panel>
        </a-collapse>
      </div>

      <div class="form-footer">
        <a-form layout="inline">
          <a-form-item label="Prompt 模板">
            <a-select
              v-model:value="promptId"
              placeholder="使用默认 Prompt"
              allow-clear
              style="width: 200px"
              :options="prompts.map(p => ({ label: p.name, value: p.id }))"
            />
          </a-form-item>
          <a-form-item label="模型配置">
            <a-select
              v-model:value="llmConfigId"
              placeholder="使用默认模型"
              allow-clear
              style="width: 200px"
              :options="llmConfigs.map(c => ({ label: c.name, value: c.id }))"
            />
          </a-form-item>
        </a-form>
      </div>
    </a-spin>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import { getFeatures, splitFeatures, generateCases, generateCasesStatus, type FeatureModuleGroup } from '@/api/cases'
import { getLLMConfigs } from '@/api/llm'
import { promptsApi, type Prompt } from '@/api/prompts'

const props = defineProps<{
  open: boolean
  projectId: number
  requirement: any
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'success'): void
}>()

const loading = ref(false)
const splitting = ref(false)
const submitting = ref(false)
const modules = ref<FeatureModuleGroup[]>([])
const splitStatus = ref('pending')
const selectedIds = ref<number[]>([])
const activeModules = ref<string[]>([])
const prompts = ref<Prompt[]>([])
const llmConfigs = ref<any[]>([])
const promptId = ref<number | undefined>()
const llmConfigId = ref<number | undefined>()
let pollTimer: any = null

const totalFeatures = computed(() =>
  modules.value.reduce((sum, m) => sum + m.features.length, 0)
)

function priorityColor(p: string) {
  return { P0: 'red', P1: 'orange', P2: 'blue', P3: 'default' }[p] || 'default'
}

function getModuleSelectedCount(mod: FeatureModuleGroup) {
  return mod.features.filter(f => selectedIds.value.includes(f.id)).length
}

function selectAll() {
  selectedIds.value = modules.value.flatMap(m => m.features.map(f => f.id))
}

function invertSelect() {
  const all = modules.value.flatMap(m => m.features.map(f => f.id))
  selectedIds.value = all.filter(id => !selectedIds.value.includes(id))
}

function toggleFeature(id: number, checked: boolean) {
  if (checked) {
    if (!selectedIds.value.includes(id)) selectedIds.value.push(id)
  } else {
    selectedIds.value = selectedIds.value.filter(i => i !== id)
  }
}

async function loadFeatures() {
  if (!props.requirement) return
  loading.value = true
  try {
    const res: any = await getFeatures(props.projectId, props.requirement.id)
    splitStatus.value = res.split_status || 'pending'
    modules.value = res.modules || []
    activeModules.value = modules.value.map(m => m.module_name)
    // 默认全选
    selectedIds.value = modules.value.flatMap(m => m.features.map(f => f.id))
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载功能点失败')
  } finally {
    loading.value = false
  }
}

async function handleSplit() {
  splitting.value = true
  try {
    await splitFeatures(props.projectId, props.requirement.id)
    message.success('功能点拆分任务已提交')
    splitStatus.value = 'splitting'
    // 轮询拆分状态
    pollSplitStatus()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '拆分失败')
  } finally {
    splitting.value = false
  }
}

function pollSplitStatus() {
  if (pollTimer) clearInterval(pollTimer)
  let attempts = 0
  pollTimer = setInterval(async () => {
    attempts++
    try {
      const res: any = await getFeatures(props.projectId, props.requirement.id)
      if (res.split_status === 'split') {
        clearInterval(pollTimer)
        splitStatus.value = 'split'
        modules.value = res.modules || []
        activeModules.value = modules.value.map(m => m.module_name)
        selectedIds.value = modules.value.flatMap(m => m.features.map(f => f.id))
        message.success('功能点拆分完成')
      } else if (res.split_status === 'failed') {
        clearInterval(pollTimer)
        splitStatus.value = 'failed'
        message.error('功能点拆分失败，请重试')
      }
    } catch {
      // ignore
    }
    if (attempts > 60) {
      clearInterval(pollTimer)
      message.warning('拆分超时，请稍后刷新查看')
    }
  }, 3000)
}

async function loadPromptsAndConfigs() {
  try {
    const [pRes, cRes]: any = await Promise.all([
      promptsApi.list('case_generation').catch(() => []),
      getLLMConfigs().catch(() => []),
    ])
    prompts.value = Array.isArray(pRes) ? pRes : (pRes?.data || [])
    llmConfigs.value = Array.isArray(cRes) ? cRes : (cRes?.data || [])
  } catch {
    // ignore
  }
}

async function handleSubmit() {
  if (splitStatus.value !== 'split') {
    message.warning('请先拆分功能点')
    return
  }
  if (selectedIds.value.length === 0) {
    message.warning('请至少选择一个功能点')
    return
  }

  submitting.value = true
  try {
    const res: any = await generateCases(props.projectId, {
      requirement_id: props.requirement.id,
      feature_ids: selectedIds.value,
      prompt_id: promptId.value,
      llm_config_id: llmConfigId.value,
    })
    message.success('用例生成任务已提交，正在后台生成...')
    emit('update:open', false)
    emit('success')
    // 轮询生成状态
    pollGenerateStatus(res.task_id)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '提交失败')
  } finally {
    submitting.value = false
  }
}

function pollGenerateStatus(taskId: number) {
  let attempts = 0
  const timer = setInterval(async () => {
    attempts++
    try {
      const res: any = await generateCasesStatus(props.projectId, taskId)
      if (res.status === 'success') {
        clearInterval(timer)
        message.success(`用例生成完成，共生成 ${res.cases_saved} 条用例`)
      } else if (res.status === 'failed') {
        clearInterval(timer)
        message.error(res.error || '用例生成失败')
      }
    } catch {
      // ignore
    }
    if (attempts > 100) clearInterval(timer)
  }, 3000)
}

function handleCancel() {
  if (pollTimer) clearInterval(pollTimer)
  emit('update:open', false)
}

watch(() => props.open, (val) => {
  if (val && props.requirement) {
    selectedIds.value = []
    promptId.value = undefined
    llmConfigId.value = undefined
    loadFeatures()
    loadPromptsAndConfigs()
  }
})
</script>

<style scoped>
.req-info {
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 6px;
  margin-bottom: 16px;
}
.req-info .label { color: #606266; }
.req-info .value { font-weight: 500; }
.split-prompt { padding: 40px 0; text-align: center; }
.select-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.selected-count { color: #606266; font-size: 13px; }
.selected-count strong { color: #1677ff; font-size: 15px; }
.feature-collapse { margin-bottom: 16px; }
.module-header { display: flex; align-items: center; gap: 8px; }
.module-name { font-weight: 500; }
.module-selected-count { margin-left: auto; font-size: 12px; color: #1677ff; }
.feature-item {
  padding: 10px 12px;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  margin-bottom: 8px;
  transition: all 0.2s;
}
.feature-item:hover { border-color: #91caff; background: #fafcff; }
.feature-item.selected { border-color: #1677ff; background: #f0f7ff; }
.feat-name { font-weight: 500; }
.feat-priority { margin-left: 8px; }
.feat-desc {
  margin: 6px 0 4px 24px;
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
}
.feat-meta {
  margin-left: 24px;
  font-size: 12px;
}
.meta-label { color: #909399; }
.form-footer {
  border-top: 1px solid #f0f0f0;
  padding-top: 12px;
}
</style>
