<template>
  <div class="api-environments">
    <div class="page-header">
      <h2>环境变量</h2>
      <a-button type="primary" @click="showCreateEnv = true">
        <template #icon><PlusOutlined /></template>
        新建环境
      </a-button>
    </div>

    <a-row :gutter="16">
      <!-- 左侧：环境列表 -->
      <a-col :span="8">
        <a-card title="环境列表" size="small">
          <div class="env-filter-bar">
            <a-input v-model:value="keyword" placeholder="搜索环境名称" allow-clear style="flex: 1" @pressEnter="handleSearch" />
            <a-button type="primary" @click="handleSearch">查询</a-button>
            <a-button @click="handleReset">重置</a-button>
          </div>
          <div v-if="filteredEnvironments.length === 0" class="empty">
            <a-empty description="暂无环境" />
          </div>
          <div v-else class="env-list">
            <div
              v-for="env in filteredEnvironments"
              :key="env.id"
              class="env-item"
              :class="{ active: selectedEnvId === env.id }"
              @click="selectEnv(env)"
            >
              <div class="env-name">
                <span>{{ env.name }}</span>
                <a-tag v-if="env.is_default" color="blue" size="small">默认</a-tag>
              </div>
              <div class="env-url">{{ env.base_url || '未配置 base_url' }}</div>
            </div>
          </div>
        </a-card>
      </a-col>

      <!-- 右侧：变量配置 -->
      <a-col :span="16">
        <a-card v-if="selectedEnv" size="small">
          <template #title>
            <div style="display: flex; align-items: center; justify-content: space-between; width: 100%">
              <span>{{ selectedEnv.name }} - 变量配置</span>
              <a-space>
                <a-button size="small" @click="openEditEnv">编辑环境</a-button>
                <a-popconfirm title="确定删除该环境？" @confirm="handleDeleteEnv">
                  <a-button size="small" danger>删除</a-button>
                </a-popconfirm>
              </a-space>
            </div>
          </template>

          <a-descriptions :column="2" size="small" style="margin-bottom: 16px">
            <a-descriptions-item label="环境名称">{{ selectedEnv.name }}</a-descriptions-item>
            <a-descriptions-item label="Base URL">{{ selectedEnv.base_url || '-' }}</a-descriptions-item>
            <a-descriptions-item label="描述" :span="2">{{ selectedEnv.description || '-' }}</a-descriptions-item>
          </a-descriptions>

          <a-divider style="margin: 8px 0 16px" />

          <div class="vars-header">
            <span class="vars-title">环境变量</span>
            <a-button type="dashed" size="small" @click="addVar">+ 添加变量</a-button>
          </div>

          <a-table
            :data-source="variables"
            :columns="varColumns"
            :row-key="(_r: any, index: number) => index"
            size="small"
            pagination="false"
          >
            <template #bodyCell="{ column, record, index }">
              <template v-if="column.key === 'key'">
                <a-input v-model:value="record.key" placeholder="变量名" size="small" />
              </template>
              <template v-else-if="column.key === 'value_type'">
                <a-select v-model:value="record.value_type" size="small" style="width: 100%" :placeholder="'静态值'">
                  <a-select-option value="static">静态值</a-select-option>
                  <a-select-option value="script">JS脚本</a-select-option>
                </a-select>
              </template>
              <template v-else-if="column.key === 'value'">
                <a-input
                  v-if="(record.value_type || 'static') === 'static'"
                  v-model:value="record.value"
                  placeholder="变量值"
                  size="small"
                />
                <div v-else class="script-cell">
                  <a-button size="small" type="dashed" @click="openScriptEditor(record)">
                    <template #icon><CodeOutlined /></template>
                    编辑脚本
                  </a-button>
                  <span v-if="record.script" class="script-preview">{{ record.script.substring(0, 60) }}{{ record.script.length > 60 ? '...' : '' }}</span>
                  <span v-else class="script-empty">未编辑</span>
                </div>
              </template>
              <template v-else-if="column.key === 'description'">
                <a-input v-model:value="record.description" placeholder="描述" size="small" />
              </template>
              <template v-else-if="column.key === 'action'">
                <a-button type="link" danger size="small" @click="variables.splice(index, 1)">删除</a-button>
              </template>
            </template>
          </a-table>

          <div class="save-bar">
            <a-button type="primary" :loading="saving" @click="handleSaveVars">保存变量</a-button>
          </div>

          <a-alert
            style="margin-top: 16px"
            type="info"
            show-icon
            message="变量优先级：用例变量 > 场景变量 > 环境变量 > 全局变量"
          >
            <template #description>
              <p v-pre>在接口调试、测试用例、场景编排中选择此环境后，未配置的变量将自动从环境变量中取值。变量引用格式：<code>{{变量名}}</code></p>
              <p style="margin-top: 4px" v-pre><b>JS脚本类型变量</b>：在每次接口请求前自动执行（相当于前置脚本），可通过 <code>pm.environment.set("key", value)</code> 设置结果值，在请求头/参数/body 中用 <code>{{key}}</code> 引用。</p>
              <p style="margin-top: 4px">脚本中可访问完整请求上下文：<code>pm.request.method</code>、<code>pm.request.headers</code>、<code>pm.request.url.query</code>、<code>pm.request.body.raw</code>，以及 <code>CryptoJS</code>（MD5/HMAC-SHA256等）和 <code>console.log()</code>。</p>
            </template>
          </a-alert>
        </a-card>
        <a-card v-else>
          <a-empty description="请选择左侧环境进行配置" />
        </a-card>
      </a-col>
    </a-row>

    <!-- 脚本编辑弹窗 -->
    <a-modal
      :open="showScriptEditor"
      title="编辑 JS 脚本"
      width="800px"
      :footer="null"
      @cancel="showScriptEditor = false"
    >
      <div class="script-editor-header">
        <a-tag color="blue">{{ editingVar?.key || '未命名' }}</a-tag>
        <span class="script-hint">通过 pm.environment.set("变量名", 值) 设置结果，脚本在每次接口请求前执行</span>
      </div>
      <a-textarea
        v-model:value="editingScript"
        :rows="20"
        style="font-family: monospace; font-size: 13px"
        placeholder="// 可访问 pm.request（headers/body/query/method）、CryptoJS、console.log()&#10;pm.environment.set('变量名', '值');"
      />
      <div class="script-editor-footer">
        <a-button @click="showScriptEditor = false">取消</a-button>
        <a-button type="primary" style="margin-left: 8px" @click="saveScript">保存脚本</a-button>
      </div>
    </a-modal>

    <!-- 新建/编辑环境弹窗 -->
    <a-modal
      :open="showCreateEnv || showEditEnv"
      :title="showCreateEnv ? '新建环境' : '编辑环境'"
      :footer="null"
      @cancel="showCreateEnv = showEditEnv = false"
    >
      <a-form layout="vertical">
        <a-form-item label="环境名称">
          <a-input v-model:value="envForm.name" placeholder="如：测试环境、生产环境" />
        </a-form-item>
        <a-form-item label="Base URL">
          <a-input v-model:value="envForm.base_url" placeholder="https://api.example.com" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="envForm.description" :rows="2" placeholder="环境描述" />
        </a-form-item>
        <a-form-item label="设为默认环境">
          <a-switch v-model:checked="envForm.is_default" />
        </a-form-item>
      </a-form>
      <div style="text-align: right">
        <a-button @click="showCreateEnv = showEditEnv = false">取消</a-button>
        <a-button type="primary" :loading="envSaving" style="margin-left: 8px" @click="handleSaveEnv">
          保存
        </a-button>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined, CodeOutlined } from '@ant-design/icons-vue'
import { environmentsApi } from '@/api/environments'
const route = useRoute()
const projectId = Number(route.params.id)
const environments = ref<any[]>([])
const keyword = ref('')
const appliedKeyword = ref('')
const filteredEnvironments = computed(() => {
  if (!appliedKeyword.value) return environments.value
  const kw = appliedKeyword.value.toLowerCase()
  return environments.value.filter(env =>
    (env.name || '').toLowerCase().includes(kw) ||
    (env.base_url || '').toLowerCase().includes(kw)
  )
})
const selectedEnvId = ref<number | null>(null)
const selectedEnv = ref<any>(null)
const variables = ref<any[]>([])
const saving = ref(false)
const envSaving = ref(false)
const showCreateEnv = ref(false)
const showEditEnv = ref(false)
const showScriptEditor = ref(false)
const editingScript = ref('')
const editingVar = ref<any>(null)

const envForm = ref({
  name: '',
  base_url: '',
  description: '',
  is_default: false,
})

const varColumns = [
  { title: '变量名', dataIndex: 'key', key: 'key', width: 140 },
  { title: '类型', dataIndex: 'value_type', key: 'value_type', width: 90 },
  { title: '值 / 脚本', dataIndex: 'value', key: 'value' },
  { title: '描述', dataIndex: 'description', key: 'description', width: 100 },
  { title: '操作', key: 'action', width: 60 },
]

const loadEnvironments = async () => {
  try {
    environments.value = await environmentsApi.list(projectId)
    if (environments.value.length > 0 && !selectedEnvId.value) {
      selectEnv(environments.value[0])
    }
  } catch {}
}

const selectEnv = (env: any) => {
  selectedEnvId.value = env.id
  selectedEnv.value = env
  // 从 config 中读取变量
  const config = env.config || {}
  const vars = config.variables || []
  variables.value = JSON.parse(JSON.stringify(vars)).map((v: any) => ({
    ...v,
    value_type: v.value_type || 'static',
    script: v.script || '',
  }))
}

const addVar = () => {
  variables.value.push({ key: '', value: '', value_type: 'static', script: '', description: '' })
}

// 直接持有行对象引用定位，避免依赖表格 slot index（分页/排序时 index 是页内下标，会写错行）
const openScriptEditor = (record: any) => {
  editingVar.value = record
  editingScript.value = record.script || ''
  showScriptEditor.value = true
}

const saveScript = () => {
  if (editingVar.value) {
    editingVar.value.script = editingScript.value
  }
  showScriptEditor.value = false
  message.success('脚本已保存，请点击「保存变量」生效')
}

const handleSaveVars = async () => {
  if (!selectedEnv.value) return
  saving.value = true
  try {
    const config = selectedEnv.value.config || {}
    config.variables = variables.value.filter(v => v.key)
    await environmentsApi.update(projectId, selectedEnv.value.id, {
      config,
    })
    message.success('变量保存成功')
    await loadEnvironments()
    // 重新选中
    const env = environments.value.find(e => e.id === selectedEnvId.value)
    if (env) selectEnv(env)
  } finally {
    saving.value = false
  }
}

const openEditEnv = () => {
  if (selectedEnv.value) {
    envForm.value = {
      name: selectedEnv.value.name || '',
      base_url: selectedEnv.value.base_url || '',
      description: selectedEnv.value.description || '',
      is_default: selectedEnv.value.is_default || false,
    }
  }
  showEditEnv.value = true
}

const handleSaveEnv = async () => {
  envSaving.value = true
  try {
    if (showCreateEnv.value) {
      await environmentsApi.create(projectId, envForm.value)
      message.success('环境创建成功')
    } else {
      await environmentsApi.update(projectId, selectedEnv.value.id, envForm.value)
      message.success('环境更新成功')
    }
    showCreateEnv.value = showEditEnv.value = false
    await loadEnvironments()
  } finally {
    envSaving.value = false
  }
}

const handleDeleteEnv = async () => {
  if (!selectedEnv.value) return
  try {
    await environmentsApi.delete(projectId, selectedEnv.value.id)
    message.success('删除成功')
    selectedEnvId.value = null
    selectedEnv.value = null
    variables.value = []
    await loadEnvironments()
  } catch {}
}

function handleSearch() {
  appliedKeyword.value = keyword.value
}

function handleReset() {
  keyword.value = ''
  appliedKeyword.value = ''
}

onMounted(() => {
  const params = { keyword: '' }
  keyword.value = params.keyword
  appliedKeyword.value = params.keyword
  loadEnvironments()
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-header h2 {
  margin: 0;
}
.env-filter-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.env-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.env-item {
  padding: 10px 12px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s;
}
.env-item:hover {
  background: #f5f5f5;
}
.env-item.active {
  background: #e6f7ff;
  border: 1px solid #91d5ff;
}
.env-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  margin-bottom: 2px;
}
.env-url {
  font-size: 12px;
  color: #8c8c8c;
  word-break: break-all;
}
.empty {
  padding: 20px 0;
}
.vars-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.vars-title {
  font-weight: 500;
}
.save-bar {
  margin-top: 16px;
  text-align: right;
}
.script-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
.script-preview {
  font-family: monospace;
  font-size: 11px;
  color: #8c8c8c;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}
.script-empty {
  font-size: 11px;
  color: #bfbfbf;
}
.script-editor-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.script-hint {
  font-size: 12px;
  color: #8c8c8c;
}
.script-editor-footer {
  margin-top: 12px;
  text-align: right;
}
</style>
