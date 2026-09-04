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
          <a-col :span="8">
            <a-form-item label="接口名称">
              <a-input v-model:value="form.name" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
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
          <a-col :span="8">
            <a-form-item label="状态">
              <a-select v-model:value="form.status" placeholder="选择状态">
                <a-select-option value="draft">草稿</a-select-option>
                <a-select-option value="active">已启用</a-select-option>
                <a-select-option value="deprecated">已废弃</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="接口描述">
          <div style="margin-bottom: 8px">
            <a-radio-group v-model:value="descEditMode" size="small" button-style="solid">
              <a-radio-button value="edit"><EditOutlined /> 编辑</a-radio-button>
              <a-radio-button value="preview"><EyeOutlined /> 预览</a-radio-button>
            </a-radio-group>
          </div>
          <a-textarea v-if="descEditMode === 'edit'" v-model:value="form.description" :rows="6" placeholder="支持 Markdown 格式，可点击上方「AI 生成文档」自动生成" />
          <MdView v-else :content="form.value.description" />
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
            <div class="kv-actions">
              <a-button type="dashed" @click="addParam('headers')">+ 添加 Header</a-button>
              <a-button @click="openBatchEdit('headers')">批量编辑</a-button>
            </div>
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
            <div class="kv-actions">
              <a-button type="dashed" @click="addParam('query_params')">+ 添加参数</a-button>
              <a-button @click="openBatchEdit('query_params')">批量编辑</a-button>
            </div>
          </a-tab-pane>
          <a-tab-pane key="body" tab="Body">
            <div style="display: flex; align-items: center; gap: 16px; margin-bottom: 12px">
              <a-radio-group v-model:value="form.body_type">
                <a-radio value="none">none</a-radio>
                <a-radio value="json">JSON</a-radio>
                <a-radio value="form-data">form-data</a-radio>
                <a-radio value="x-www-form-urlencoded">x-www-form-urlencoded</a-radio>
                <a-radio value="raw">raw</a-radio>
              </a-radio-group>
              <a-select
                v-if="form.body_type === 'raw'"
                v-model:value="form.raw_language"
                style="width: 120px"
                size="small"
                :options="[
                  { value: 'Text', label: 'Text' },
                  { value: 'JSON', label: 'JSON' },
                  { value: 'XML', label: 'XML' },
                  { value: 'HTML', label: 'HTML' },
                  { value: 'JavaScript', label: 'JavaScript' },
                ]"
              />
            </div>
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
            <div v-if="form.body_type !== 'none'" class="kv-actions">
              <a-button type="dashed" @click="addBodyParam">+ 添加字段</a-button>
              <a-button @click="openBatchEdit('body')">批量编辑</a-button>
            </div>
          </a-tab-pane>
          <a-tab-pane key="pre-script" tab="前置脚本">
            <a-textarea
              v-model:value="form.pre_script"
              :rows="10"
              placeholder="// 请求前执行的 JS 脚本，例如：&#10;// pm.environment.set('timestamp', Date.now())&#10;// pm.request.headers.add({ key: 'X-Token', value: pm.environment.get('token') })"
              style="font-family: monospace"
            />
          </a-tab-pane>
          <a-tab-pane key="post-script" tab="后置脚本">
            <a-textarea
              v-model:value="form.post_script"
              :rows="10"
              placeholder="// 请求后执行的 JS 脚本，可访问响应数据，例如：&#10;// const data = pm.response.json()&#10;// pm.environment.set('token', data.token)"
              style="font-family: monospace"
            />
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
      width="500px"
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
        <a-form-item label="补充信息（可选）">
          <a-textarea
            v-model:value="aiDocConfig.supplement_info"
            :rows="4"
            placeholder="输入需要补充说明的信息，如业务背景、特殊逻辑、注意事项等，AI 将结合接口定义和补充信息生成文档"
          />
        </a-form-item>
        <a-alert
          message="点击生成后弹窗将关闭，文档将在后台异步生成，完成后自动写入接口描述字段。"
          type="info"
          show-icon
        />
      </a-form>
      <div style="text-align: right; margin-top: 16px">
        <a-button @click="showAiDocModal = false">取消</a-button>
        <a-button type="primary" style="margin-left: 8px" :loading="aiGenerating" @click="handleAiGenerateDoc">
          <template #icon><RobotOutlined /></template>
          生成文档
        </a-button>
      </div>
    </a-modal>

    <!-- 批量编辑弹窗 -->
    <BatchEditModal
      v-model:open="batchEditOpen"
      :show-description="true"
      :title="batchEditTitle"
      @confirm="handleBatchConfirm"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { ArrowLeftOutlined, RobotOutlined, EyeOutlined, EditOutlined } from '@ant-design/icons-vue'
import { apiDefinitionsApi, apiModulesApi, type ApiDefinition, type ApiModule } from '@/api/apiTest'
import { getLLMConfigs } from '@/api/llm'
import { promptsApi, type Prompt } from '@/api/prompts'
import MdView from '@/components/MdView.vue'
import BatchEditModal from '@/components/BatchEditModal.vue'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)
const apiId = route.params.apiId
const isEdit = computed(() => apiId && apiId !== 'new')

const formRef = ref()
const saving = ref(false)
const activeTab = ref('headers')
const descEditMode = ref<'edit' | 'preview'>('edit')
const moduleTree = ref<any[]>([])
const showAiDocModal = ref(false)
const aiGenerating = ref(false)
const llmConfigs = ref<any[]>([])
const apiDocPrompts = ref<Prompt[]>([])
const aiDocConfig = ref({ llm_config_id: null as number | null, prompt_id: null as number | null, supplement_info: '' })

const form = ref<any>({
  name: '',
  method: 'GET',
  path: '',
  description: '',
  module_id: null,
  status: 'draft',
  headers: [],
  query_params: [],
  path_params: [],
  body_type: 'none',
  body_content: null,
  raw_language: 'Text',
  pre_script: '',
  post_script: '',
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

const batchEditOpen = ref(false)
const batchEditType = ref<string | null>(null)
const batchEditTitle = computed(() => {
  const titles: Record<string, string> = {
    headers: '批量编辑 Headers',
    query_params: '批量编辑 Query 参数',
    body: '批量编辑 Body 参数',
  }
  return batchEditType.value ? titles[batchEditType.value] : '批量编辑'
})

const openBatchEdit = (type: string) => {
  batchEditType.value = type
  batchEditOpen.value = true
}

const handleBatchConfirm = (data: any[]) => {
  if (!batchEditType.value) return
  if (batchEditType.value === 'body') {
    bodyParams.value = data
  } else {
    form.value[batchEditType.value] = data
  }
}

const mapModuleTree = (modules: any[]): any[] => {
  return modules.map((m: any) => ({
    title: m.name,
    value: m.id,
    children: m.children?.length ? mapModuleTree(m.children) : undefined,
  }))
}

const loadModules = async () => {
  try {
    const modules = await apiModulesApi.getTree(projectId)
    moduleTree.value = mapModuleTree(modules)
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
  try {
    const res = await apiDefinitionsApi.aiGenerateDoc(
      projectId,
      Number(apiId),
      aiDocConfig.value.llm_config_id || undefined,
      aiDocConfig.value.prompt_id || undefined,
      aiDocConfig.value.supplement_info || undefined,
    )
    const taskId = res.task_id
    showAiDocModal.value = false
    aiDocConfig.value.supplement_info = ''
    aiGenerating.value = false
    message.info('文档生成中，完成后将自动写入接口描述...')

    const poll = setInterval(async () => {
      try {
        const status = await apiDefinitionsApi.aiGenerateDocStatus(projectId, Number(apiId), taskId)
        if (status.status === 'success') {
          clearInterval(poll)
          form.value.description = status.documentation
          message.success('接口文档已生成并写入描述字段')
        } else if (status.status === 'failed') {
          clearInterval(poll)
          message.error('文档生成失败：' + (status.error || '未知错误'))
        }
      } catch {
        // 轮询中忽略错误
      }
    }, 2000)
  } catch (e: any) {
    aiGenerating.value = false
    message.error('启动文档生成失败：' + (e.message || '未知错误'))
  }
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
  promptsApi.list('api_doc_generation').then(data => { apiDocPrompts.value = data }).catch(() => {})
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
.kv-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
.form-actions {
  margin-top: 24px;
  text-align: right;
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.md-preview {
  min-height: 120px;
  max-height: 500px;
  overflow-y: auto;
  padding: 12px 16px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  background: #fafafa;
  line-height: 1.8;
  color: #1f2329;
  font-size: 14px;
}
.md-preview :deep(h1) { font-size: 20px; margin: 16px 0 8px; font-weight: 600; border-bottom: 1px solid #e8e8e8; padding-bottom: 6px; }
.md-preview :deep(h2) { font-size: 17px; margin: 14px 0 8px; font-weight: 600; color: #1677ff; border-left: 3px solid #1677ff; padding-left: 8px; }
.md-preview :deep(h3) { font-size: 15px; margin: 12px 0 6px; font-weight: 600; }
.md-preview :deep(p) { margin: 8px 0; }
.md-preview :deep(ul), .md-preview :deep(ol) { margin: 8px 0; padding-left: 24px; }
.md-preview :deep(li) { margin: 4px 0; }
.md-preview :deep(strong) { font-weight: 600; }
.md-preview :deep(code) { background: #f0f0f0; padding: 2px 6px; border-radius: 4px; font-size: 13px; color: #d63384; }
.md-preview :deep(pre) { background: #f6f8fa; padding: 12px 16px; border-radius: 6px; overflow-x: auto; margin: 10px 0; }
.md-preview :deep(pre code) { background: none; padding: 0; color: #1f2329; }
.md-preview :deep(blockquote) { border-left: 4px solid #d9d9d9; margin: 10px 0; padding: 8px 16px; color: #606266; background: #fff; }
.md-preview :deep(table) { border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 13px; }
.md-preview :deep(th), .md-preview :deep(td) { border: 1px solid #e8e8e8; padding: 8px 12px; text-align: left; }
.md-preview :deep(th) { background: #f0f0f0; font-weight: 600; }
.md-preview :deep(hr) { border: none; border-top: 1px solid #e8e8e8; margin: 16px 0; }
</style>
