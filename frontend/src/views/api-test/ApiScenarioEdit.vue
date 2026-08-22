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
          <a-form layout="vertical">
          <a-row :gutter="16" align="top">
            <a-col :span="8">
              <a-form-item label="场景名称" style="margin-bottom: 0">
                <a-input v-model:value="form.name" size="middle" />
              </a-form-item>
            </a-col>
            <a-col :span="8">
              <a-form-item label="环境" style="margin-bottom: 0">
                <a-select v-model:value="form.environment_id" allow-clear placeholder="选择环境" size="middle">
                  <a-select-option v-for="env in environments" :key="env.id" :value="env.id">{{ env.name }}</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
            <a-col :span="8">
              <a-form-item label="测试数据池" style="margin-bottom: 0">
                <a-select
                  v-model:value="form.data_pool_id"
                  show-search
                  allow-clear
                  placeholder="选择数据池（可选）"
                  size="middle"
                  :filter-option="(input: string, option: any) => (option?.label ?? '').toLowerCase().includes(input.toLowerCase())"
                  :options="poolOptions"
                />
              </a-form-item>
            </a-col>
          </a-row>
          <a-form-item label="描述" style="margin-top: 8px; margin-bottom: 0">
            <a-textarea v-model:value="form.description" :rows="2" />
          </a-form-item>
          </a-form>
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
                  <!-- 可用变量（前面步骤提取的变量，点击复制） -->
                  <div v-if="['api', 'case'].includes(step.step_type) && getAvailableVars(index).length > 0" class="available-vars">
                    <span class="av-label">可用变量：</span>
                    <a-tag
                      v-for="v in getAvailableVars(index)"
                      :key="v"
                      color="blue"
                      style="cursor: pointer"
                      @click="copyVar(v)"
                    >${{ '{' }}{{ v }}{{ '}' }}</a-tag>
                    <span class="av-tip">点击复制到剪贴板</span>
                  </div>
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

                  <!-- 等待步骤 -->
                  <a-form-item v-if="step.step_type === 'wait'" label="等待秒数">
                    <a-input-number v-model:value="step.wait_seconds" :min="0" style="width: 100%" size="small" />
                  </a-form-item>

                  <!-- 脚本步骤 -->
                  <a-form-item v-if="step.step_type === 'script'" label="脚本内容">
                    <div class="script-header">
                      <span class="script-tip">支持 JavaScript，可使用 <code>variables.get/set</code>、<code>response</code> 等对象</span>
                      <a-button size="small" @click="handleAiGenerateScript(step, 'script_content')" :loading="step._aiLoading">
                        <template #icon><RobotOutlined /></template>AI 生成
                      </a-button>
                    </div>
                    <a-textarea v-model:value="step.script_content" :rows="5" style="font-family: monospace" placeholder="// 编写 JavaScript 脚本" />
                  </a-form-item>

                  <!-- 条件步骤 - 工作流分支 -->
                  <template v-if="step.step_type === 'condition'">
                    <a-form-item label="条件表达式">
                      <div style="display: flex; gap: 4px; align-items: flex-start">
                        <a-textarea v-model:value="step.condition_expr" :rows="2" placeholder="{{var}} == 'value' 或 {{status}} >= 200，支持 {{$mock函数}}" style="flex: 1" />
                        <MockDataInserter v-model="step.condition_expr" />
                      </div>
                    </a-form-item>
                    <a-row :gutter="16">
                      <a-col :span="12">
                        <a-form-item label="条件成立时执行">
                          <a-select v-model:value="step.loop_config.true_next" allow-clear placeholder="选择后续步骤（跳过则顺序执行）">
                            <a-select-option v-for="(s, i) in steps" :key="i" :value="i" :disabled="i <= index">
                              步骤 {{ i + 1 }}: {{ s.step_name }}
                            </a-select-option>
                          </a-select>
                        </a-form-item>
                      </a-col>
                      <a-col :span="12">
                        <a-form-item label="条件不成立时执行">
                          <a-select v-model:value="step.loop_config.false_next" allow-clear placeholder="选择后续步骤（跳过则顺序执行）">
                            <a-select-option v-for="(s, i) in steps" :key="i" :value="i" :disabled="i <= index">
                              步骤 {{ i + 1 }}: {{ s.step_name }}
                            </a-select-option>
                          </a-select>
                        </a-form-item>
                      </a-col>
                    </a-row>
                    <a-alert type="info" show-icon :banner="false" style="margin-bottom: 8px"
                      message="条件分支说明"
                      description="条件成立时跳转到指定步骤，不成立时跳转到另一个步骤。不选择则按顺序执行下一步。" />
                  </template>

                  <!-- 循环步骤 - 遍历参数 -->
                  <template v-if="step.step_type === 'loop'">
                    <a-row :gutter="16">
                      <a-col :span="12">
                        <a-form-item label="循环变量名">
                          <a-input v-model:value="step.loop_config.var_name" placeholder="如 page、item" />
                        </a-form-item>
                      </a-col>
                      <a-col :span="12">
                        <a-form-item label="遍历值列表">
                          <a-input v-model:value="step.loop_config.values" placeholder="如 1,2,3 或 a,b,c" />
                        </a-form-item>
                      </a-col>
                    </a-row>
                    <a-form-item label="循环体起始步骤">
                      <a-select v-model:value="step.loop_config.body_start" allow-clear placeholder="选择循环体内第一个步骤">
                        <a-select-option v-for="(s, i) in steps" :key="i" :value="i" :disabled="i <= index">
                          步骤 {{ i + 1 }}: {{ s.step_name }}
                        </a-select-option>
                      </a-select>
                    </a-form-item>
                    <a-form-item label="循环体结束步骤（执行完回到循环）">
                      <a-select v-model:value="step.loop_config.body_end" allow-clear placeholder="选择循环体内最后一个步骤">
                        <a-select-option v-for="(s, i) in steps" :key="i" :value="i" :disabled="i <= index">
                          步骤 {{ i + 1 }}: {{ s.step_name }}
                        </a-select-option>
                      </a-select>
                    </a-form-item>
                    <a-alert type="info" show-icon style="margin-bottom: 8px"
                      message="循环说明"
                      description="遍历值列表中的每个值，依次执行循环体步骤。循环变量可通过 {{变量名}} 引用。" />
                  </template>

                  <!-- API/用例步骤：参数覆盖 + 脚本 + 响应提取 -->
                  <template v-if="['api', 'case'].includes(step.step_type)">
                    <a-form-item label="请求参数覆盖（可选，深度合并到原请求体）" style="margin-bottom: 12px">
                      <a-textarea
                        v-model:value="step.request_config.body_override"
                        :rows="3"
                        style="font-family: monospace"
                        placeholder='输入 JSON，如 {"data":{"name":"${name}"}}，将与接口原参数深度合并，支持变量引用'
                      />
                      <div class="override-tip">原参数中未覆盖的字段保持不变，覆盖字段以本输入为准</div>
                    </a-form-item>
                    <a-form-item label="Query Params 覆盖（可选，合并到原查询参数）" style="margin-bottom: 12px">
                      <a-textarea
                        v-model:value="step.request_config.query_params_override"
                        :rows="2"
                        style="font-family: monospace"
                        placeholder='输入 JSON，如 {"name":"${name}","page":"1"}，已存在的参数更新值，不存在的新增'
                      />
                      <div class="override-tip">GET 请求的查询参数用此方式覆盖，支持变量引用</div>
                    </a-form-item>
                    <a-tabs size="small">
                      <a-tab-pane key="pre" tab="前置脚本">
                        <div class="script-header">
                          <span class="script-tip">支持 JavaScript，<code>variables.set('key','val')</code> 设置变量</span>
                          <a-button size="small" @click="handleAiGenerateScript(step, 'pre_script')" :loading="step._aiLoading">
                            <template #icon><RobotOutlined /></template>AI 生成
                          </a-button>
                        </div>
                        <a-textarea v-model:value="step.pre_script" :rows="4" style="font-family: monospace" placeholder="// 请求前执行" />
                      </a-tab-pane>
                      <a-tab-pane key="post" tab="后置脚本">
                        <div class="script-header">
                          <span class="script-tip">支持 JavaScript，<code>response</code> 访问响应，<code>tests.assert()</code> 断言</span>
                          <a-button size="small" @click="handleAiGenerateScript(step, 'post_script')" :loading="step._aiLoading">
                            <template #icon><RobotOutlined /></template>AI 生成
                          </a-button>
                        </div>
                        <a-textarea v-model:value="step.post_script" :rows="4" style="font-family: monospace" placeholder="// 响应后执行" />
                      </a-tab-pane>
                      <a-tab-pane key="extract" tab="响应变量提取">
                        <div class="extract-header">
                          <span class="extract-tip">从响应中提取变量，后续步骤可通过 <code>${变量名}</code> 引用</span>
                          <a-button type="dashed" size="small" @click="addExtractVar(step)">+ 添加提取</a-button>
                        </div>
                        <a-table
                          :data-source="step._extract_vars || []"
                          :columns="extractColumns"
                          :row-key="(_r: any, i: number) => i"
                          size="small"
                          pagination="false"
                        >
                          <template #bodyCell="{ column, record, idx }">
                            <template v-if="column.key === 'var_name'">
                              <a-input v-model:value="record.var_name" size="small" placeholder="变量名，如 user_id" />
                            </template>
                            <template v-else-if="column.key === 'extract_type'">
                              <a-select v-model:value="record.extract_type" size="small" placeholder="类型">
                                <a-select-option value="jsonpath">JSONPath</a-select-option>
                                <a-select-option value="regex">正则</a-select-option>
                                <a-select-option value="header">响应头</a-select-option>
                                <a-select-option value="cookie">Cookie</a-select-option>
                              </a-select>
                            </template>
                            <template v-else-if="column.key === 'extract_expr'">
                              <a-input v-model:value="record.extract_expr" size="small" :placeholder="getExtractPlaceholder(record.extract_type)" />
                            </template>
                            <template v-else-if="column.key === 'default_value'">
                              <div style="display: flex; gap: 4px; align-items: center">
                                <a-input v-model:value="record.default_value" size="small" placeholder="默认值（可选）" style="flex: 1" />
                                <MockDataInserter v-model="record.default_value" />
                              </div>
                            </template>
                            <template v-else-if="column.key === 'scope'">
                              <a-select v-model:value="record.scope" size="small" placeholder="范围">
                                <a-select-option value="scenario">场景</a-select-option>
                                <a-select-option value="global">全局</a-select-option>
                              </a-select>
                            </template>
                            <template v-else-if="column.key === 'action'">
                              <a-button type="link" danger size="small" @click="step._extract_vars.splice(idx, 1)">删除</a-button>
                            </template>
                          </template>
                        </a-table>
                        <div v-if="step._extract_vars && step._extract_vars.length > 0" class="extract-preview">
                          <span class="preview-label">可引用变量：</span>
                          <a-tag v-for="v in step._extract_vars.filter((x:any)=>x.var_name)" :key="v.var_name" color="blue">
                            ${{ '{' }}{{ v.var_name }}{{ '}' }}
                          </a-tag>
                        </div>
                      </a-tab-pane>
                    </a-tabs>
                  </template>
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
  ArrowDownOutlined, DeleteOutlined, RobotOutlined
} from '@ant-design/icons-vue'
import { apiScenariosApi, apiDefinitionsApi, apiCasesApi, type ApiScenarioStep } from '@/api/apiTest'
import { environmentsApi } from '@/api/environments'
import { dataPoolsApi } from '@/api/dataPools'
import { chat } from '@/api/chat'
import MockDataInserter from './MockDataInserter.vue'

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
const poolOptions = ref<{ label: string; value: number }[]>([])

async function loadPoolOptions() {
  try {
    const res = await dataPoolsApi.list(projectId, { page: 1, page_size: 100 })
    poolOptions.value = res.items.map((p: any) => ({ label: `${p.name} (${p.data_type})`, value: p.id }))
  } catch { poolOptions.value = [] }
}

const form = ref<any>({
  name: '',
  description: '',
  environment_id: null,
  config: {},
  data_pool_id: null as number | null,
  pre_script: '',
  post_script: '',
})

const steps = ref<any[]>([])
const expandedSteps = ref(new Set<number>())

const allCollapsed = computed(() => expandedSteps.value.size === 0)

const extractColumns = [
  { title: '变量名', dataIndex: 'var_name', key: 'var_name', width: 120 },
  { title: '提取类型', dataIndex: 'extract_type', key: 'extract_type', width: 100 },
  { title: '提取表达式', dataIndex: 'extract_expr', key: 'extract_expr' },
  { title: '默认值', dataIndex: 'default_value', key: 'default_value', width: 100 },
  { title: '范围', dataIndex: 'scope', key: 'scope', width: 80 },
  { title: '操作', key: 'action', width: 60 },
]

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

const getExtractPlaceholder = (type: string) => {
  const map: Record<string, string> = {
    jsonpath: '$.data.id',
    regex: '"id":(\\d+)',
    header: 'X-Token',
    cookie: 'session_id',
  }
  return map[type] || '提取表达式'
}

const createStep = (type: string, extra: any = {}) => ({
  id: 0,
  scenario_id: 0,
  step_type: type,
  step_name: getStepTypeName(type) + '步骤',
  sort_order: 0,
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
  _extract_vars: [],
  _aiLoading: false,
  ...extra,
})

const addApiStep = (api: any) => {
  steps.value.push(createStep('api', {
    step_name: api.name,
    api_id: api.id,
    request_config: {},
  }))
  const newIdx = steps.value.length - 1
  selectedStepIndex.value = newIdx
  expandedSteps.value = new Set([...expandedSteps.value, newIdx])
}

const addCaseStep = (caseItem: any) => {
  steps.value.push(createStep('case', {
    step_name: caseItem.name,
    case_id: caseItem.id,
  }))
  const newIdx = steps.value.length - 1
  selectedStepIndex.value = newIdx
  expandedSteps.value = new Set([...expandedSteps.value, newIdx])
}

const addStep = (type: string) => {
  steps.value.push(createStep(type))
  const newIdx = steps.value.length - 1
  selectedStepIndex.value = newIdx
  expandedSteps.value = new Set([...expandedSteps.value, newIdx])
}

const addExtractVar = (step: any) => {
  if (!step._extract_vars) step._extract_vars = []
  step._extract_vars.push({
    var_name: '',
    extract_type: 'jsonpath',
    extract_expr: '',
    default_value: '',
    scope: 'scenario',
  })
}

// 获取当前步骤之前所有步骤提取的变量名（去重）
const getAvailableVars = (currentIndex: number): string[] => {
  const vars: string[] = []
  for (let i = 0; i < currentIndex; i++) {
    const step = steps.value[i]
    if (step && step._extract_vars) {
      for (const v of step._extract_vars) {
        if (v.var_name && !vars.includes(v.var_name)) {
          vars.push(v.var_name)
        }
      }
    }
  }
  return vars
}

// 复制变量引用到剪贴板
const copyVar = (varName: string) => {
  const text = '${' + varName + '}'
  navigator.clipboard.writeText(text).then(() => {
    message.success('已复制 ' + text)
  }).catch(() => {
    // 兜底：用临时 textarea
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    message.success('已复制 ' + text)
  })
}

const handleAiGenerateScript = async (step: any, field: string) => {
  step._aiLoading = true
  try {
    const fieldName = field === 'pre_script' ? '前置脚本' : field === 'post_script' ? '后置脚本' : '脚本'
    const prompt = `请为接口测试场景步骤生成${fieldName}（JavaScript）：

步骤名称：${step.step_name}
步骤类型：${getStepTypeName(step.step_type)}
${step.api_id ? '接口ID：' + step.api_id : ''}
${step.case_id ? '用例ID：' + step.case_id : ''}

要求：
1. 代码简洁，有中文注释
2. 可使用 variables.set('key', 'value') 设置变量，variables.get('key') 获取变量
3. 后置脚本可使用 response.statusCode、response.body、response.headers 访问响应
4. 可使用 tests.assert('名称', 条件) 添加测试断言
5. 只输出代码，不要解释`
    const res = await chat({ message: prompt, project_id: projectId })
    step[field] = res.content || ''
    message.success('脚本生成成功')
  } catch (e: any) {
    message.error('脚本生成失败：' + (e.message || '未知错误'))
  } finally {
    step._aiLoading = false
  }
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
    const [apis, cases, envs] = await Promise.all([
      apiDefinitionsApi.list(projectId, { page_size: 100 }),
      apiCasesApi.list(projectId, { page_size: 100 }),
      environmentsApi.list(projectId),
    ])
    apiList.value = apis.items
    caseList.value = cases.items
    environments.value = envs
  } catch {}

  if (isEdit.value) {
    try {
      const data = await apiScenariosApi.get(projectId, Number(scenarioId))
      Object.assign(form.value, data)
      const stepList = await apiScenariosApi.listSteps(projectId, Number(scenarioId))
      steps.value = stepList.map((s: any) => {
        const base = createStep(s.step_type || 'api', s)
        return {
          ...base,
          id: s.id ?? base.id,
          scenario_id: s.scenario_id ?? base.scenario_id,
          request_config: s.request_config || {},
          loop_config: s.loop_config || {},
          _extract_vars: [],
        }
      })
      // 加载所有步骤的提取变量，按 step_id 分组
      if (steps.value.length > 0) {
        try {
          const allVars = await apiScenariosApi.listVariables(projectId, Number(scenarioId))
          const varsByStep: Record<number, any[]> = {}
          for (const v of allVars) {
            if (!varsByStep[v.step_id]) varsByStep[v.step_id] = []
            varsByStep[v.step_id].push(v)
          }
          for (let i = 0; i < steps.value.length; i++) {
            if (steps.value[i].id && steps.value[i].id > 0) {
              steps.value[i]._extract_vars = varsByStep[steps.value[i].id] || []
            }
          }
        } catch {}
      }
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
    // 删除已移除的步骤：对比数据库中已有步骤与当前步骤列表
    if (isEdit.value) {
      try {
        const existingSteps = await apiScenariosApi.listSteps(projectId, savedScenario.id)
        const currentStepIds = new Set(steps.value.filter(s => s.id && s.id > 0).map(s => s.id))
        for (const existing of existingSteps) {
          if (!currentStepIds.has(existing.id)) {
            await apiScenariosApi.deleteStep(projectId, existing.id)
          }
        }
      } catch {}
    }
    // 保存步骤
    for (let i = 0; i < steps.value.length; i++) {
      const step = steps.value[i]
      step.sort_order = i
      // 移除内部字段
      const { _extract_vars, _aiLoading, ...stepData } = step
      if (step.id && step.id > 0) {
        await apiScenariosApi.updateStep(projectId, step.id, stepData)
      } else {
        const savedStep = await apiScenariosApi.createStep(projectId, savedScenario.id, stepData)
        step.id = savedStep.id
      }
      // 保存提取变量：先清空该步骤已有变量，再重建，避免重复
      if (step.id && step.id > 0) {
        try {
          await apiScenariosApi.clearStepVariables(projectId, savedScenario.id, step.id)
        } catch {}
      }
      if (_extract_vars && _extract_vars.length > 0) {
        for (const v of _extract_vars) {
          if (v.var_name) {
            try {
              await apiScenariosApi.createVariable(projectId, savedScenario.id, step.id, v)
            } catch {}
          }
        }
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
        router.push(`/projects/${projectId}/api-test/executions/${res.execution_id}`)
      }
    } catch {}
  }
}

onMounted(() => {
  loadData()
  loadPoolOptions()
})
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
.script-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.script-tip {
  font-size: 12px;
  color: #8c8c8c;
}
.script-tip code {
  background: #f5f5f5;
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 11px;
}
.extract-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.extract-tip {
  font-size: 12px;
  color: #8c8c8c;
}
.extract-tip code {
  background: #f5f5f5;
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 11px;
}
.extract-preview {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.preview-label {
  font-size: 12px;
  color: #8c8c8c;
}
.available-vars {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 12px;
  padding: 6px 10px;
  background: #f6ffed;
  border: 1px solid #b7eb8f;
  border-radius: 4px;
}
.av-label {
  font-size: 12px;
  color: #52c41a;
  font-weight: 500;
}
.av-tip {
  font-size: 11px;
  color: #8c8c8c;
}
.override-tip {
  font-size: 11px;
  color: #8c8c8c;
  margin-top: 4px;
}
</style>
