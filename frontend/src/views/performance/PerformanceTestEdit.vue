<template>
  <div class="perf-test-edit">
    <div class="page-header">
      <a-button @click="$router.back()"><ArrowLeftOutlined /> 返回</a-button>
      <h2>{{ isEdit ? '编辑性能测试' : '新建性能测试' }}</h2>
    </div>
    <a-form :model="form" layout="vertical">
      <a-card title="基本信息" style="margin-bottom: 16px">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="测试名称" required>
              <a-input v-model:value="form.name" placeholder="请输入测试名称" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="目标类型">
              <a-select v-model:value="form.target_type" @change="onTargetTypeChange">
                <a-select-option value="api_definition">接口定义</a-select-option>
                <a-select-option value="api_case">接口用例</a-select-option>
                <a-select-option value="api_scenario">接口场景</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="目标ID">
              <a-select
                v-model:value="form.target_id"
                style="width: 100%"
                placeholder="请选择目标（可选）"
                allow-clear
                show-search
                :filter-option="filterTargetOption"
                :loading="targetLoading"
                :options="targetOptions"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="覆盖URL">
              <a-input v-model:value="form.target_url" placeholder="可留空，自动从环境获取" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="2" placeholder="测试描述" />
        </a-form-item>
      </a-card>

      <a-card title="负载配置" style="margin-bottom: 16px">
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="并发用户数">
              <a-input-number v-model:value="form.users" :min="1" :max="10000" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="每秒启动用户数">
              <a-input-number v-model:value="form.spawn_rate" :min="1" :max="1000" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="持续时间(秒)">
              <a-input-number v-model:value="form.duration" :min="1" :max="3600" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-card>

      <a-card title="高级配置" style="margin-bottom: 16px">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="测试数据池">
              <a-select
                v-model:value="form.data_pool_id"
                style="width: 100%"
                placeholder="选择数据池进行参数化（可选）"
                allow-clear
                show-search
                :filter-option="filterPoolOption"
                :loading="poolLoading"
                :options="poolOptions"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="测试环境">
              <a-select
                v-model:value="form.environment_id"
                style="width: 100%"
                placeholder="选择测试环境（可选）"
                allow-clear
                :loading="envLoading"
                :options="envOptions"
              />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="自定义请求头 (JSON)">
          <a-textarea v-model:value="headersText" :rows="4" placeholder='{"Authorization": "Bearer xxx"}' />
        </a-form-item>
        <a-form-item label="请求体模板">
          <a-textarea v-model:value="form.body_template" :rows="4" placeholder="请求体内容，支持 {{变量名}} 占位符（从数据池取值）" />
        </a-form-item>
      </a-card>

      <div style="text-align: right">
        <a-button @click="$router.back()" style="margin-right: 8px">取消</a-button>
        <a-button type="primary" :loading="saving" @click="handleSave">保存</a-button>
      </div>
    </a-form>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { ArrowLeftOutlined } from '@ant-design/icons-vue'
import { performanceTestsApi } from '@/api/performanceTests'
import { apiDefinitionsApi } from '@/api/apiDefinitions'
import { apiCasesApi } from '@/api/apiCaseTests'
import { apiScenariosApi } from '@/api/apiScenarioTests'
import { dataPoolsApi } from '@/api/dataPools'
import { environmentsApi } from '@/api/environments'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)
const testId = route.params.testId as string
const isEdit = computed(() => testId && testId !== 'new')
const saving = ref(false)

const form = ref({
  name: '',
  description: '',
  target_type: 'api_case',
  target_id: null as number | null,
  target_url: '',
  users: 10,
  spawn_rate: 1,
  duration: 60,
  headers: {} as Record<string, any>,
  body_template: '',
  variable_config: {} as Record<string, any>,
  data_pool_id: null as number | null,
  environment_id: null as number | null,
})

const headersText = ref('{}')

const targetOptions = ref<{ label: string; value: number }[]>([])
const targetLoading = ref(false)

async function loadTargetOptions() {
  targetLoading.value = true
  try {
    const params = { page: 1, page_size: 100 }
    let items: { id: number; name: string; method?: string; path?: string }[] = []
    if (form.value.target_type === 'api_definition') {
      const res = await apiDefinitionsApi.list(projectId, params)
      items = res.items
    } else if (form.value.target_type === 'api_case') {
      const res = await apiCasesApi.list(projectId, params)
      items = res.items
    } else if (form.value.target_type === 'api_scenario') {
      const res = await apiScenariosApi.list(projectId, params)
      items = res.items
    }
    targetOptions.value = items.map(item => ({
      label: item.method || item.path
        ? `${item.name} [${item.method || ''} ${item.path || ''}]`
        : item.name,
      value: item.id,
    }))
  } catch {
    targetOptions.value = []
  } finally {
    targetLoading.value = false
  }
}

function onTargetTypeChange() {
  form.value.target_id = null
  loadTargetOptions()
}

function filterTargetOption(input: string, option: any) {
  return (option?.label as string)?.toLowerCase().includes(input.toLowerCase())
}

const poolOptions = ref<{ label: string; value: number }[]>([])
const poolLoading = ref(false)

async function loadPoolOptions() {
  poolLoading.value = true
  try {
    const res = await dataPoolsApi.list(projectId, { page: 1, page_size: 100 })
    poolOptions.value = res.items.map((p: any) => ({
      label: `${p.name} (${p.data_type})`,
      value: p.id,
    }))
  } catch {
    poolOptions.value = []
  } finally {
    poolLoading.value = false
  }
}

function filterPoolOption(input: string, option: any) {
  return (option?.label as string)?.toLowerCase().includes(input.toLowerCase())
}

const envOptions = ref<{ label: string; value: number }[]>([])
const envLoading = ref(false)

async function loadEnvOptions() {
  envLoading.value = true
  try {
    const res = await environmentsApi.list(projectId)
    envOptions.value = (res || []).map((e: any) => ({
      label: e.name,
      value: e.id,
    }))
  } catch {
    envOptions.value = []
  } finally {
    envLoading.value = false
  }
}

async function loadData() {
  if (!isEdit.value) return
  try {
    const res = await performanceTestsApi.get(projectId, Number(testId))
    Object.assign(form.value, res)
    headersText.value = JSON.stringify(res.headers || {}, null, 2)
    await loadTargetOptions()
  } catch { }
}

async function handleSave() {
  if (!form.value.name) {
    message.warning('请输入测试名称')
    return
  }
  saving.value = true
  try {
    form.value.headers = JSON.parse(headersText.value || '{}')
    if (isEdit.value) {
      await performanceTestsApi.update(projectId, Number(testId), form.value)
    } else {
      await performanceTestsApi.create(projectId, form.value)
    }
    message.success('保存成功')
    router.push(`/projects/${projectId}/performance-tests`)
  } catch (e: any) {
    if (e instanceof SyntaxError) {
      message.error('请求头 JSON 格式错误')
    }
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadData()
  loadPoolOptions()
  loadEnvOptions()
  if (!isEdit.value) {
    loadTargetOptions()
  }
})
</script>

<style scoped>
.perf-test-edit { padding: 0; }
.page-header { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; }
.page-header h2 { margin: 0; }
</style>
