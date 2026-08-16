<template>
  <div class="data-pool-edit">
    <div class="page-header">
      <a-button @click="$router.back()"><ArrowLeftOutlined /> 返回</a-button>
      <h2>{{ isEdit ? '编辑数据池' : '新建数据池' }}</h2>
    </div>
    <a-form :model="form" layout="vertical">
      <a-card title="基本信息" style="margin-bottom: 16px">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="数据池名称" required>
              <a-input v-model:value="form.name" placeholder="请输入名称" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="数据类型">
              <a-select v-model:value="form.data_type">
                <a-select-option value="static">静态数据</a-select-option>
                <a-select-option value="dynamic">动态生成</a-select-option>
                <a-select-option value="generated">自动生成</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="2" placeholder="数据池描述" />
        </a-form-item>
      </a-card>

      <a-card title="字段定义" style="margin-bottom: 16px">
        <a-table :columns="schemaColumns" :data-source="form.schema" :pagination="false" row-key="(_r: any, i: number) => i" size="small">
          <template #bodyCell="{ column, record, index }">
            <template v-if="column.key === 'name'">
              <a-input v-model:value="record.name" placeholder="字段名" size="small" />
            </template>
            <template v-if="column.key === 'type'">
              <a-select v-model:value="record.type" size="small" style="width: 100%">
                <a-select-option value="string">string</a-select-option>
                <a-select-option value="integer">integer</a-select-option>
                <a-select-option value="float">float</a-select-option>
                <a-select-option value="boolean">boolean</a-select-option>
              </a-select>
            </template>
            <template v-if="column.key === 'generator'">
              <a-select v-model:value="record.generator" size="small" style="width: 100%" allow-clear placeholder="无">
                <a-select-option value="name">姓名</a-select-option>
                <a-select-option value="email">邮箱</a-select-option>
                <a-select-option value="phone">手机号</a-select-option>
                <a-select-option value="uuid">UUID</a-select-option>
                <a-select-option value="random_int">随机整数</a-select-option>
                <a-select-option value="random_string">随机字符串</a-select-option>
                <a-select-option value="sequential">递增序号</a-select-option>
                <a-select-option value="timestamp">时间戳</a-select-option>
                <a-select-option value="address">地址</a-select-option>
                <a-select-option value="company">公司名</a-select-option>
                <a-select-option value="boolean">随机布尔</a-select-option>
              </a-select>
            </template>
            <template v-if="column.key === 'default_value'">
              <a-input v-model:value="record.default_value" placeholder="默认值" size="small" />
            </template>
            <template v-if="column.key === 'action'">
              <a-button size="small" type="link" danger @click="form.schema.splice(index, 1)">删除</a-button>
            </template>
          </template>
        </a-table>
        <a-button type="dashed" block style="margin-top: 8px" @click="form.schema.push({ name: '', type: 'string', generator: '', default_value: '' })">+ 添加字段</a-button>
      </a-card>

      <a-card v-if="form.data_type === 'static'" title="静态数据" style="margin-bottom: 16px">
        <a-textarea v-model:value="staticDataText" :rows="8" placeholder='[{"name": "张三", "age": 25}]' />
      </a-card>

      <a-card v-if="form.data_type !== 'static'" title="生成配置" style="margin-bottom: 16px">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="生成数量">
              <a-input-number v-model:value="genCount" :min="1" :max="10000" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-button @click="handlePreview" :loading="previewing">预览生成数据</a-button>
      </a-card>

      <div style="text-align: right">
        <a-button @click="$router.back()" style="margin-right: 8px">取消</a-button>
        <a-button type="primary" :loading="saving" @click="handleSave">保存</a-button>
      </div>
    </a-form>

    <a-modal v-model:open="previewVisible" title="预览数据" width="700px" :footer="null">
      <pre style="max-height: 400px; overflow: auto">{{ JSON.stringify(previewData, null, 2) }}</pre>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { ArrowLeftOutlined } from '@ant-design/icons-vue'
import { dataPoolsApi } from '@/api/dataPools'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)
const poolId = route.params.poolId as string
const isEdit = computed(() => poolId && poolId !== 'new')
const saving = ref(false)
const previewing = ref(false)
const previewVisible = ref(false)
const previewData = ref<any[]>([])
const genCount = ref(10)
const staticDataText = ref('[]')

const form = ref({
  name: '',
  description: '',
  data_type: 'static',
  schema: [] as any[],
  data: [] as any[],
  generator_config: {} as Record<string, any>,
  environment_id: null as number | null,
})

const schemaColumns = [
  { title: '字段名', key: 'name', width: 150 },
  { title: '类型', key: 'type', width: 120 },
  { title: '生成器', key: 'generator', width: 150 },
  { title: '默认值', key: 'default_value', width: 150 },
  { title: '操作', key: 'action', width: 80 },
]

async function loadData() {
  if (!isEdit.value) return
  try {
    const res = await dataPoolsApi.get(projectId, Number(poolId))
    Object.assign(form.value, res)
    staticDataText.value = JSON.stringify(res.data || [], null, 2)
    genCount.value = res.generator_config?.count || 10
  } catch { }
}

async function handlePreview() {
  if (!form.value.schema.length) {
    message.warning('请先添加字段')
    return
  }
  previewing.value = true
  try {
    if (isEdit.value) {
      const res = await dataPoolsApi.preview(projectId, Number(poolId), genCount.value)
      previewData.value = res.data
    } else {
      message.info('保存后可预览生成数据')
      return
    }
    previewVisible.value = true
  } catch { } finally {
    previewing.value = false
  }
}

async function handleSave() {
  if (!form.value.name) {
    message.warning('请输入数据池名称')
    return
  }
  saving.value = true
  try {
    if (form.value.data_type === 'static') {
      form.value.data = JSON.parse(staticDataText.value || '[]')
    } else {
      form.value.generator_config = { count: genCount.value }
    }
    if (isEdit.value) {
      await dataPoolsApi.update(projectId, Number(poolId), form.value)
    } else {
      await dataPoolsApi.create(projectId, form.value)
    }
    message.success('保存成功')
    router.push(`/projects/${projectId}/data-pools`)
  } catch (e: any) {
    if (e instanceof SyntaxError) {
      message.error('静态数据 JSON 格式错误')
    }
  } finally {
    saving.value = false
  }
}

onMounted(() => loadData())
</script>

<style scoped>
.data-pool-edit { padding: 0; }
.page-header { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; }
.page-header h2 { margin: 0; }
</style>
