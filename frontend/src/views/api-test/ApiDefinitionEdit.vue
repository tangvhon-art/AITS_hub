<template>
  <div class="api-definition-edit">
    <div class="page-header">
      <a-button @click="$router.back()">
        <template #icon><ArrowLeftOutlined /></template>
        返回
      </a-button>
      <h2>{{ isEdit ? '编辑接口' : '新建接口' }}</h2>
      <a-button @click="showAiDocModal = true">
        <template #icon><RobotOutlined /></template>
        AI 生成文档
      </a-button>
    </div>

    <a-form :model="form" layout="vertical" ref="formRef">
      <a-card title="基本信息">
        <a-row :gutter="16">
          <a-col :span="6">
            <a-form-item label="请求方法">
              <a-select v-model:value="form.method" placeholder="选择方法">
                <a-select-option value="GET">GET</a-select-option>
                <a-select-option value="POST">POST</a-select-option>
                <a-select-option value="PUT">PUT</a-select-option>
                <a-select-option value="DELETE">DELETE</a-select-option>
                <a-select-option value="PATCH">PATCH</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="18">
            <a-form-item label="接口路径">
              <a-input v-model:value="form.path" placeholder="/api/users" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="接口名称">
              <a-input v-model:value="form.name" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="所属分组">
              <a-tree-select
                v-model:value="form.module_id"
                :tree-data="moduleTree"
                placeholder="选择分组"
                allow-clear
                tree-default-expand-all
              />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="接口描述">
          <a-textarea v-model:value="form.description" :rows="2" />
        </a-form-item>
      </a-card>

      <a-card title="请求参数" style="margin-top: 16px">
        <a-tabs v-model:activeKey="activeTab">
          <a-tab-pane key="headers" tab="Headers">
            <a-table :data-source="form.headers" :columns="paramColumns" :row-key="(_r: any, index: number) => index" size="small" pagination="false">
              <template #bodyCell="{ column, record, index }">
                <template v-if="column.key === 'enabled'">
                  <a-checkbox v-model:checked="record.enabled" />
                </template>
                <template v-else-if="column.key === 'key'">
                  <a-input v-model:value="record.key" placeholder="Header名" size="small" />
                </template>
                <template v-else-if="column.key === 'value'">
                  <a-input v-model:value="record.value" placeholder="Header值" size="small" />
                </template>
                <template v-else-if="column.key === 'description'">
                  <a-input v-model:value="record.description" placeholder="描述" size="small" />
                </template>
                <template v-else-if="column.key === 'action'">
                  <a-button type="link" danger size="small" @click="removeParam('headers', index)">删除</a-button>
                </template>
              </template>
            </a-table>
            <a-button type="dashed" block style="margin-top: 8px" @click="addParam('headers')">+ 添加 Header</a-button>
          </a-tab-pane>
          <a-tab-pane key="query" tab="Query Params">
            <a-table :data-source="form.query_params" :columns="paramColumns" :row-key="(_r: any, index: number) => index" size="small" pagination="false">
              <template #bodyCell="{ column, record, index }">
                <template v-if="column.key === 'enabled'">
                  <a-checkbox v-model:checked="record.enabled" />
                </template>
                <template v-else-if="column.key === 'key'">
                  <a-input v-model:value="record.key" placeholder="参数名" size="small" />
                </template>
                <template v-else-if="column.key === 'value'">
                  <a-input v-model:value="record.value" placeholder="参数值" size="small" />
                </template>
                <template v-else-if="column.key === 'description'">
                  <a-input v-model:value="record.description" placeholder="描述" size="small" />
                </template>
                <template v-else-if="column.key === 'action'">
                  <a-button type="link" danger size="small" @click="removeParam('query_params', index)">删除</a-button>
                </template>
              </template>
            </a-table>
            <a-button type="dashed" block style="margin-top: 8px" @click="addParam('query_params')">+ 添加参数</a-button>
          </a-tab-pane>
          <a-tab-pane key="body" tab="Body">
            <a-radio-group v-model:value="form.body_type" style="margin-bottom: 12px">
              <a-radio value="none">none</a-radio>
              <a-radio value="json">JSON</a-radio>
              <a-radio value="form-data">form-data</a-radio>
              <a-radio value="x-www-form-urlencoded">x-www-form-urlencoded</a-radio>
              <a-radio value="raw">raw</a-radio>
            </a-radio-group>
            <a-textarea
              v-if="form.body_type === 'json' || form.body_type === 'raw'"
              v-model:value="bodyContent"
              :rows="8"
              placeholder='{"key": "value"}'
              style="font-family: monospace"
            />
            <a-table
              v-else-if="form.body_type === 'form-data' || form.body_type === 'x-www-form-urlencoded'"
              :data-source="bodyParams"
              :columns="paramColumns"
              :row-key="(_r: any, index: number) => index"
              size="small"
              pagination="false"
            >
              <template #bodyCell="{ column, record, index }">
                <template v-if="column.key === 'enabled'">
                  <a-checkbox v-model:checked="record.enabled" />
                </template>
                <template v-else-if="column.key === 'key'">
                  <a-input v-model:value="record.key" placeholder="参数名" size="small" />
                </template>
                <template v-else-if="column.key === 'value'">
                  <a-input v-model:value="record.value" placeholder="参数值" size="small" />
                </template>
                <template v-else-if="column.key === 'description'">
                  <a-input v-model:value="record.description" placeholder="描述" size="small" />
                </template>
                <template v-else-if="column.key === 'action'">
                  <a-button type="link" danger size="small" @click="removeBodyParam(index)">删除</a-button>
                </template>
              </template>
            </a-table>
            <a-button v-if="form.body_type !== 'none'" type="dashed" block style="margin-top: 8px" @click="addBodyParam">+ 添加字段</a-button>
          </a-tab-pane>
        </a-tabs>
      </a-card>

      <div class="form-actions">
        <a-button @click="$router.back()">取消</a-button>
        <a-button type="primary" :loading="saving" @click="handleSave">保存</a-button>
      </div>
    </a-form>

    <!-- AI 生成接口文档弹窗 -->
    <a-modal
      v-model:open="showAiDocModal"
      title="AI 生成接口文档"
      width="700px"
      :footer="null"
    >
      <a-form layout="vertical">
        <a-form-item label="选择模型">
          <a-select v-model:value="aiDocConfig.llm_config_id" placeholder="使用默认模型" allow-clear>
            <a-select-option v-for="cfg in llmConfigs" :key="cfg.id" :value="cfg.id">{{ cfg.name }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="Prompt 模板">
          <a-select
            v-model:value="aiDocConfig.prompt_id"
            placeholder="使用默认 Prompt"
            allow-clear
            :options="apiDocPrompts.map(p => ({ label: p.name, value: p.id }))"
          />
        </a-form-item>
        <a-form-item label="接口描述（AI 生成）">
          <a-textarea
            v-model:value="aiDocResult"
            :rows="10"
            placeholder="点击下方按钮生成接口文档..."
            style="font-family: monospace"
          />
        </a-form-item>
      </a-form>
      <div style="display: flex; justify-content: space-between">
        <a-button :loading="aiGenerating" @click="handleAiGenerateDoc">
          <template #icon><RobotOutlined /></template>
          生成文档
        </a-button>
        <div>
          <a-button @click="showAiDocModal = false">取消</a-button>
          <a-button type="primary" style="margin-left: 8px" @click="handleApplyAiDoc">应用到接口</a-button>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { ArrowLeftOutlined, RobotOutlined } from '@ant-design/icons-vue'
import { apiDefinitionsApi, apiModulesApi, type ApiDefinition, type ApiModule } from '@/api/apiTest'
import { getLLMConfigs } from '@/api/llm'
import { promptsApi, type Prompt } from '@/api/prompts'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)
const apiId = route.params.apiId
const isEdit = computed(() => apiId && apiId !== 'new')

const formRef = ref()
const saving = ref(false)
const activeTab = ref('headers')
const moduleTree = ref<any[]>([])
const showAiDocModal = ref(false)
const aiGenerating = ref(false)
const llmConfigs = ref<any[]>([])
const apiDocPrompts = ref<Prompt[]>([])
const aiDocResult = ref('')
const aiDocConfig = ref({ llm_config_id: null as number | null, prompt_id: null as number | null })

const form = ref<any>({
  name: '',
  method: 'GET',
  path: '',
  description: '',
  module_id: null,
  headers: [],
  query_params: [],
  path_params: [],
  body_type: 'none',
  body_content: null,
  response_examples: [],
})

const bodyContent = computed({
  get: () => typeof form.value.body_content === 'string' ? form.value.body_content : JSON.stringify(form.value.body_content, null, 2),
  set: (val: string) => {
    try { form.value.body_content = JSON.parse(val) } catch { form.value.body_content = val }
  }
})

const bodyParams = computed({
  get: () => Array.isArray(form.value.body_content) ? form.value.body_content : [],
  set: (val) => { form.value.body_content = val }
})

const paramColumns = [
  { title: '启用', key: 'enabled', width: 60 },
  { title: '参数名', dataIndex: 'key', key: 'key' },
  { title: '参数值', dataIndex: 'value', key: 'value' },
  { title: '描述', dataIndex: 'description', key: 'description' },
  { title: '操作', key: 'action', width: 60 },
]

const addParam = (type: string) => {
  form.value[type].push({ key: '', value: '', description: '', enabled: true })
}

const removeParam = (type: string, index: number) => {
  form.value[type].splice(index, 1)
}

const addBodyParam = () => {
  if (!Array.isArray(form.value.body_content)) {
    form.value.body_content = []
  }
  form.value.body_content.push({ key: '', value: '', description: '', enabled: true })
}

const removeBodyParam = (index: number) => {
  if (Array.isArray(form.value.body_content)) {
    form.value.body_content.splice(index, 1)
  }
}

const loadModules = async () => {
  try {
    const modules = await apiModulesApi.getTree(projectId)
    moduleTree.value = modules.map((m: any) => ({ title: m.name, value: m.id, children: m.children }))
  } catch {}
}

const loadLlmConfigs = async () => {
  try {
    llmConfigs.value = await getLLMConfigs()
  } catch {}
}

const handleAiGenerateDoc = async () => {
  if (!isEdit.value) {
    message.warning('请先保存接口定义后再生成文档')
    return
  }
  aiGenerating.value = true
  aiDocResult.value = ''
  try {
    const res = await apiDefinitionsApi.aiGenerateDoc(
      projectId,
      Number(apiId),
      aiDocConfig.value.llm_config_id || undefined,
      aiDocConfig.value.prompt_id || undefined,
    )
    const taskId = res.task_id
    message.info('AI 文档生成中...')

    const poll = setInterval(async () => {
      try {
        const status = await apiDefinitionsApi.aiGenerateDocStatus(projectId, Number(apiId), taskId)
        if (status.status === 'success') {
          clearInterval(poll)
          aiDocResult.value = status.documentation
          form.value.description = status.documentation
          aiGenerating.value = false
          message.success('文档已生成并写入接口描述')
        } else if (status.status === 'failed') {
          clearInterval(poll)
          aiGenerating.value = false
          message.error('文档生成失败：' + (status.error || '未知错误'))
        }
      } catch {
        clearInterval(poll)
        aiGenerating.value = false
        message.error('查询生成状态失败')
      }
    }, 2000)
  } catch (e: any) {
    aiGenerating.value = false
    message.error('启动文档生成失败：' + (e.message || '未知错误'))
  }
}

const handleApplyAiDoc = () => {
  if (!aiDocResult.value) {
    message.warning('请先生成文档')
    return
  }
  form.value.description = aiDocResult.value
  message.success('已应用到接口描述')
  showAiDocModal.value = false
}

const loadData = async () => {
  if (!isEdit.value) return
  const data = await apiDefinitionsApi.get(projectId, Number(apiId))
  Object.assign(form.value, data)
}

const handleSave = async () => {
  saving.value = true
  try {
    if (isEdit.value) {
      await apiDefinitionsApi.update(projectId, Number(apiId), form.value)
      message.success('更新成功')
    } else {
      await apiDefinitionsApi.create(projectId, form.value)
      message.success('创建成功')
    }
    router.back()
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadModules()
  loadData()
  loadLlmConfigs()
  promptsApi.list('api_test').then(data => { apiDocPrompts.value = data }).catch(() => {})
  // 新建时从 query 参数读取默认分组
  if (!isEdit.value && route.query.module_id) {
    form.value.module_id = Number(route.query.module_id)
  }
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
}
.form-actions {
  margin-top: 24px;
  text-align: right;
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
</style>
