<template>
  <div class="api-scenario-edit">
    <div class="page-header">
      <a-button @click="$router.back()">
        <template #icon><ArrowLeftOutlined /></template>
        返回
      </a-button>
      <h2>{{ isEdit ? '编辑场景' : '新建场景' }}</h2>
      <div class="header-actions">
        <a-button type="primary" :loading="saving" @click="handleSave">保存</a-button>
        <a-button @click="handleRun">
          <template #icon><PlayCircleOutlined /></template>
          执行
        </a-button>
      </div>
    </div>

    <a-row :gutter="16">
      <!-- 左侧：接口/用例库 -->
      <a-col :span="6">
        <a-card title="步骤库" size="small">
          <a-input-search v-model:value="searchKeyword" placeholder="搜索" style="margin-bottom: 8px" />
          <a-tabs v-model:activeKey="libraryTab">
            <a-tab-pane key="api" tab="接口">
              <div v-for="api in filteredApis" :key="api.id" class="library-item" @click="addApiStep(api)">
                <a-tag :color="getMethodColor(api.method)" style="margin-right: 4px">{{ api.method }}</a-tag>
                <span class="item-name">{{ api.name }}</span>
              </div>
              <a-empty v-if="filteredApis.length === 0" description="暂无接口" />
            </a-tab-pane>
            <a-tab-pane key="case" tab="用例">
              <div v-for="caseItem in filteredCases" :key="caseItem.id" class="library-item" @click="addCaseStep(caseItem)">
                <a-tag color="blue" style="margin-right: 4px">用例</a-tag>
                <span class="item-name">{{ caseItem.name }}</span>
              </div>
              <a-empty v-if="filteredCases.length === 0" description="暂无用例" />
            </a-tab-pane>
            <a-tab-pane key="other" tab="其他">
              <div class="library-item" @click="addStep('script')">
                <a-tag color="purple">脚本</a-tag>
                <span class="item-name">执行脚本</span>
              </div>
              <div class="library-item" @click="addStep('wait')">
                <a-tag color="orange">等待</a-tag>
                <span class="item-name">等待时间</span>
              </div>
              <div class="library-item" @click="addStep('condition')">
                <a-tag color="cyan">条件</a-tag>
                <span class="item-name">条件判断</span>
              </div>
              <div class="library-item" @click="addStep('loop')">
                <a-tag color="green">循环</a-tag>
                <span class="item-name">循环执行</span>
              </div>
            </a-tab-pane>
          </a-tabs>
        </a-card>
      </a-col>

      <!-- 右侧：步骤编排区 -->
      <a-col :span="18">
        <a-card title="基本信息" size="small" style="margin-bottom: 16px">
          <a-row :gutter="16">
            <a-col :span="12">
              <a-form-item label="场景名称" style="margin-bottom: 0">
                <a-input v-model:value="form.name" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="环境" style="margin-bottom: 0">
                <a-select v-model:value="form.environment_id" allow-clear placeholder="选择环境">
                  <a-select-option v-for="env in environments" :key="env.id" :value="env.id">{{ env.name }}</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
          </a-row>
          <a-form-item label="描述" style="margin-top: 8px; margin-bottom: 0">
            <a-textarea v-model:value="form.description" :rows="2" />
          </a-form-item>
        </a-card>

        <a-card size="small">
          <template #title>
            <div style="display: flex; align-items: center; justify-content: space-between; width: 100%">
              <span>步骤编排</span>
              <a-button v-if="steps.length > 0" type="link" size="small" @click.stop="toggleCollapseAll">
                {{ allCollapsed ? '展开全部' : '收起全部' }}
              </a-button>
            </div>
          </template>
          <div v-if="steps.length === 0" class="empty-steps">
            <a-empty description="从左侧添加步骤" />
          </div>
          <div v-else class="steps-list">
            <div
              v-for="(step, index) in steps"
              :key="step.id || index"
              class="step-item"
              :class="{ active: selectedStepIndex === index }"
            >
              <div class="step-header" @click="toggleStep(index)">
                <span class="expand-icon">{{ expandedSteps.has(index) ? '▾' : '▸' }}</span>
                <span class="step-order">{{ index + 1 }}</span>
                <a-tag :color="getStepTypeColor(step.step_type)">{{ getStepTypeName(step.step_type) }}</a-tag>
                <span class="step-name">{{ step.step_name }}</span>
                <div class="step-actions">
                  <a-button type="text" size="small" @click.stop="moveStep(index, -1)" :disabled="index === 0">
                    <ArrowUpOutlined />
                  </a-button>
                  <a-button type="text" size="small" @click.stop="moveStep(index, 1)" :disabled="index === steps.length - 1">
                    <ArrowDownOutlined />
                  </a-button>
                  <a-button type="text" size="small" danger @click.stop="removeStep(index)">
                    <DeleteOutlined />
                  </a-button>
                </div>
              </div>

              <!-- 展开的步骤配置 -->
              <div v-if="expandedSteps.has(index)" class="step-config" @click.stop>
                <a-form layout="vertical" size="small">
                  <a-form-item label="步骤名称">
                    <a-input v-model:value="step.step_name" />
                  </a-form-item>
                  <a-row :gutter="16">
                    <a-col :span="8">
                      <a-form-item label="启用">
                        <a-switch v-model:checked="step.enabled" size="small" />
                      </a-form-item>
                    </a-col>
                    <a-col :span="8">
                      <a-form-item label="失败继续">
                        <a-switch v-model:checked="step.continue_on_failure" size="small" />
                      </a-form-item>
                    </a-col>
                    <a-col :span="8">
                      <a-form-item label="最大重试">
                        <a-input-number v-model:value="step.max_retries" :min="0" :max="5" style="width: 100%" size="small" />
                      </a-form-item>
                    </a-col>
                  </a-row>

                  <a-form-item v-if="step.step_type === 'wait'" label="等待秒数">
                    <a-input-number v-model:value="step.wait_seconds" :min="0" style="width: 100%" size="small" />
                  </a-form-item>

                  <a-form-item v-if="step.step_type === 'script'" label="脚本内容">
                    <a-textarea v-model:value="step.script_content" :rows="5" style="font-family: monospace" />
                  </a-form-item>

                  <a-form-item v-if="step.step_type === 'condition'" label="条件表达式">
                    <a-textarea v-model:value="step.condition_expr" :rows="3" placeholder="{{var}} == 'value'" />
                  </a-form-item>

                  <a-tabs v-if="['api', 'case'].includes(step.step_type)" size="small">
                    <a-tab-pane key="pre" tab="前置脚本">
                      <a-textarea v-model:value="step.pre_script" :rows="4" style="font-family: monospace" />
                    </a-tab-pane>
                    <a-tab-pane key="post" tab="后置脚本">
                      <a-textarea v-model:value="step.post_script" :rows="4" style="font-family: monospace" />
                    </a-tab-pane>
                  </a-tabs>
                </a-form>
              </div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  ArrowLeftOutlined, PlayCircleOutlined, ArrowUpOutlined,
  ArrowDownOutlined, DeleteOutlined
} from '@ant-design/icons-vue'
import { apiScenariosApi, apiDefinitionsApi, apiCasesApi, type ApiScenarioStep } from '@/api/apiTest'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)
const scenarioId = route.params.scenarioId
const isEdit = computed(() => scenarioId && scenarioId !== 'new')

const saving = ref(false)
const searchKeyword = ref('')
const libraryTab = ref('api')
const selectedStepIndex = ref(-1)
const environments = ref<any[]>([])
const apiList = ref<any[]>([])
const caseList = ref<any[]>([])

const form = ref<any>({
  name: '',
  description: '',
  environment_id: null,
  config: {},
  pre_script: '',
  post_script: '',
})

const steps = ref<ApiScenarioStep[]>([])
const expandedSteps = ref(new Set<number>())

const allCollapsed = computed(() => expandedSteps.value.size === 0)

function toggleStep(index: number) {
  const s = new Set(expandedSteps.value)
  if (s.has(index)) {
    s.delete(index)
  } else {
    s.add(index)
  }
  expandedSteps.value = s
  selectedStepIndex.value = s.has(index) ? index : -1
}

function toggleCollapseAll() {
  if (expandedSteps.value.size > 0) {
    expandedSteps.value = new Set()
  } else {
    expandedSteps.value = new Set(steps.value.map((_, i) => i))
  }
  selectedStepIndex.value = -1
}

const filteredApis = computed(() => {
  if (!searchKeyword.value) return apiList.value
  const kw = searchKeyword.value.toLowerCase()
  return apiList.value.filter(a => a.name.toLowerCase().includes(kw) || a.path.toLowerCase().includes(kw))
})

const filteredCases = computed(() => {
  if (!searchKeyword.value) return caseList.value
  const kw = searchKeyword.value.toLowerCase()
  return caseList.value.filter(c => c.name.toLowerCase().includes(kw))
})

const getMethodColor = (method: string) => {
  const colors: Record<string, string> = { GET: 'green', POST: 'blue', PUT: 'orange', DELETE: 'red' }
  return colors[method] || 'default'
}

const getStepTypeColor = (type: string) => {
  const colors: Record<string, string> = {
    api: 'blue', case: 'cyan', script: 'purple', wait: 'orange', condition: 'gold', loop: 'green'
  }
  return colors[type] || 'default'
}

const getStepTypeName = (type: string) => {
  const names: Record<string, string> = {
    api: '接口', case: '用例', script: '脚本', wait: '等待', condition: '条件', loop: '循环'
  }
  return names[type] || type
}

const addApiStep = (api: any) => {
  steps.value.push({
    id: 0,
    scenario_id: 0,
    step_type: 'api',
    step_name: api.name,
    sort_order: steps.value.length,
    enabled: true,
    api_id: api.id,
    case_id: null,
    request_config: { method: api.method, path: api.path },
    script_content: '',
    wait_seconds: 0,
    condition_expr: '',
    loop_config: {},
    pre_script: '',
    post_script: '',
    continue_on_failure: false,
    max_retries: 0,
  })
  const newIdx = steps.value.length - 1
  selectedStepIndex.value = newIdx
  expandedSteps.value = new Set([...expandedSteps.value, newIdx])
}

const addCaseStep = (caseItem: any) => {
  steps.value.push({
    id: 0,
    scenario_id: 0,
    step_type: 'case',
    step_name: caseItem.name,
    sort_order: steps.value.length,
    enabled: true,
    api_id: null,
    case_id: caseItem.id,
    request_config: {},
    script_content: '',
    wait_seconds: 0,
    condition_expr: '',
    loop_config: {},
    pre_script: '',
    post_script: '',
    continue_on_failure: false,
    max_retries: 0,
  })
  const newIdx = steps.value.length - 1
  selectedStepIndex.value = newIdx
  expandedSteps.value = new Set([...expandedSteps.value, newIdx])
}

const addStep = (type: string) => {
  steps.value.push({
    id: 0,
    scenario_id: 0,
    step_type: type,
    step_name: getStepTypeName(type) + '步骤',
    sort_order: steps.value.length,
    enabled: true,
    api_id: null,
    case_id: null,
    request_config: {},
    script_content: '',
    wait_seconds: 1,
    condition_expr: '',
    loop_config: {},
    pre_script: '',
    post_script: '',
    continue_on_failure: false,
    max_retries: 0,
  })
  const newIdx = steps.value.length - 1
  selectedStepIndex.value = newIdx
  expandedSteps.value = new Set([...expandedSteps.value, newIdx])
}

const moveStep = (index: number, direction: number) => {
  const newIndex = index + direction
  if (newIndex < 0 || newIndex >= steps.value.length) return
  const temp = steps.value[index]
  steps.value[index] = steps.value[newIndex]
  steps.value[newIndex] = temp
  steps.value.forEach((s, i) => s.sort_order = i)
  selectedStepIndex.value = newIndex
}

const removeStep = (index: number) => {
  steps.value.splice(index, 1)
  steps.value.forEach((s, i) => s.sort_order = i)
  if (selectedStepIndex.value >= steps.value.length) {
    selectedStepIndex.value = steps.value.length - 1
  }
}

const loadData = async () => {
  try {
    const [apis, cases] = await Promise.all([
      apiDefinitionsApi.list(projectId, { page_size: 100 }),
      apiCasesApi.list(projectId, { page_size: 100 }),
    ])
    apiList.value = apis.items
    caseList.value = cases.items
  } catch {}

  if (isEdit.value) {
    try {
      const data = await apiScenariosApi.get(projectId, Number(scenarioId))
      Object.assign(form.value, data)
      steps.value = await apiScenariosApi.listSteps(projectId, Number(scenarioId))
    } catch {}
  }
}

const handleSave = async () => {
  saving.value = true
  try {
    let savedScenario: any
    if (isEdit.value) {
      savedScenario = await apiScenariosApi.update(projectId, Number(scenarioId), form.value)
    } else {
      savedScenario = await apiScenariosApi.create(projectId, form.value)
    }
    // 保存步骤
    for (let i = 0; i < steps.value.length; i++) {
      const step = steps.value[i]
      step.sort_order = i
      if (step.id && step.id > 0) {
        await apiScenariosApi.updateStep(projectId, step.id, step)
      } else {
        await apiScenariosApi.createStep(projectId, savedScenario.id, step)
      }
    }
    message.success('保存成功')
    router.back()
  } finally {
    saving.value = false
  }
}

const handleRun = async () => {
  await handleSave()
  if (isEdit.value) {
    try {
      const res = await apiScenariosApi.run(projectId, Number(scenarioId), {})
      if (res.execution_id) {
        router.push(`/projects/${projectId}/api-executions/${res.execution_id}`)
      }
    } catch {}
  }
}

onMounted(() => loadData())
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}
.page-header h2 {
  margin: 0;
  flex: 1;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.library-item {
  padding: 8px;
  cursor: pointer;
  border-radius: 4px;
  transition: background 0.2s;
}
.library-item:hover {
  background: #f5f5f5;
}
.item-name {
  font-size: 13px;
}
.empty-steps {
  padding: 40px 0;
}
.steps-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.step-item {
  border: 1px solid #f0f0f0;
  border-radius: 4px;
  padding: 8px 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.step-item:hover {
  border-color: #1890ff;
}
.step-item.active {
  border-color: #1890ff;
  background: #e6f7ff;
}
.step-header {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}
.expand-icon {
  width: 14px;
  font-size: 10px;
  color: #999;
  flex-shrink: 0;
  text-align: center;
}
.step-order {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #1890ff;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}
.step-name {
  flex: 1;
}
.step-actions {
  display: flex;
  gap: 4px;
}
.step-config {
  border-top: 1px solid #f0f0f0;
  padding: 12px 0 4px;
  margin-top: 8px;
}
</style>
