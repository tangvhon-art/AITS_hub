<template>
  <div class="profiles-page">
    <div class="filter-bar">
      <a-input v-model:value="keyword" placeholder="搜索页面名称/URL" allow-clear style="width: 300px" @pressEnter="loadProfiles">
        <template #prefix><SearchOutlined /></template>
      </a-input>
      <a-button @click="loadProfiles"><SearchOutlined /> 查询</a-button>
      <a-button @click="resetFilter">重置</a-button>
      <a-button type="primary" :loading="aggregating" @click="triggerAggregate" style="margin-left: auto">
        <ThunderboltOutlined /> 手动聚合
      </a-button>
    </div>

    <a-table
      :columns="columns"
      :data-source="profiles"
      :loading="loading"
      :pagination="pagination"
      @change="handleTableChange"
      row-key="id"
      size="middle"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'success_rate'">
          <a-progress :percent="Math.round((record.success_rate || 0) * 100)" size="small" :stroke-color="rateColor(record.success_rate)" />
        </template>
        <template v-else-if="column.key === 'key_elements'">
          <a-tag v-for="el in (record.key_elements || []).slice(0, 3)" :key="el.text" size="small">
            {{ el.tag }}: {{ el.text || el.attributes?.id || el.attributes?.['aria-label'] || '...' }}
          </a-tag>
          <span v-if="(record.key_elements || []).length > 3" class="text-muted">+{{ record.key_elements.length - 3 }}</span>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-button type="link" size="small" @click="viewDetail(record)">详情</a-button>
        </template>
      </template>
    </a-table>

    <a-modal v-model:open="detailVisible" title="页面画像详情" width="800px" :footer="null">
      <div v-if="currentProfile" class="detail-content">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="页面标识" :span="2">{{ currentProfile.page_identifier }}</a-descriptions-item>
          <a-descriptions-item label="页面名称">{{ currentProfile.page_name || '-' }}</a-descriptions-item>
          <a-descriptions-item label="访问次数">{{ currentProfile.visit_count }}</a-descriptions-item>
          <a-descriptions-item label="成功率" :span="2">
            <a-progress :percent="Math.round((currentProfile.success_rate || 0) * 100)" size="small" />
          </a-descriptions-item>
          <a-descriptions-item label="功能描述" :span="2">{{ currentProfile.page_description || '-' }}</a-descriptions-item>
          <a-descriptions-item label="最后聚合" :span="2">{{ formatTime(currentProfile.last_aggregated_at) }}</a-descriptions-item>
        </a-descriptions>

        <div v-if="currentProfile.key_elements?.length" class="detail-section">
          <h4>关键元素 ({{ currentProfile.key_elements.length }})</h4>
          <a-table :data-source="currentProfile.key_elements" :columns="elementColumns" size="small" :pagination="false" row-key="text">
            <template #bodyCell="{ column, record: el }">
              <template v-if="column.key === 'selectors'">
                <div v-for="s in (el.selectors || []).slice(0, 2)" :key="s.value">
                  <code class="selector-code">{{ s.value }}</code>
                </div>
              </template>
              <template v-else-if="column.key === 'frequency'">
                <a-progress :percent="Math.round((el.frequency || 0) * 100)" size="small" style="width: 80px" />
              </template>
            </template>
          </a-table>
        </div>

        <div v-if="currentProfile.failure_patterns?.length" class="detail-section">
          <h4>常见失败模式</h4>
          <div v-for="(fp, i) in currentProfile.failure_patterns.slice(0, 5)" :key="i" class="failure-item">
            <code class="selector-code">{{ fp.selector }}</code>
            <span class="fail-reason">{{ fp.reason }}</span>
          </div>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { SearchOutlined, ThunderboltOutlined } from '@ant-design/icons-vue'
import { useRoute } from 'vue-router'
import { listPageProfiles, getPageProfile, triggerAggregation, type PageProfile } from '@/api/uiHealing'

const route = useRoute()
const projectId = Number(route.params.id)

const loading = ref(false)
const aggregating = ref(false)
const profiles = ref<PageProfile[]>([])
const keyword = ref('')

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: (t: number) => `共 ${t} 条`,
})

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
  { title: '页面名称', dataIndex: 'page_name', key: 'page_name', width: 180, ellipsis: true },
  { title: '页面标识', dataIndex: 'page_identifier', key: 'page_identifier', ellipsis: true },
  { title: '关键元素', key: 'key_elements', width: 280 },
  { title: '访问次数', dataIndex: 'visit_count', key: 'visit_count', width: 90 },
  { title: '成功率', key: 'success_rate', width: 140 },
  { title: '最后聚合', dataIndex: 'last_aggregated_at', key: 'last_aggregated_at', width: 160 },
  { title: '操作', key: 'action', width: 80 },
]

const elementColumns = [
  { title: '标签', dataIndex: 'tag', key: 'tag', width: 80 },
  { title: '文本', dataIndex: 'text', key: 'text', width: 150, ellipsis: true },
  { title: '定位器', key: 'selectors' },
  { title: '出现率', key: 'frequency', width: 100 },
]

const detailVisible = ref(false)
const currentProfile = ref<PageProfile | null>(null)

function rateColor(rate: number) {
  if (rate >= 0.9) return '#52c41a'
  if (rate >= 0.7) return '#faad14'
  return '#ff4d4f'
}

async function loadProfiles() {
  loading.value = true
  try {
    const res = await listPageProfiles({
      project_id: projectId,
      keyword: keyword.value,
      page: pagination.current,
      page_size: pagination.pageSize,
    })
    profiles.value = res.items
    pagination.total = res.total
  } catch (e) {
    message.error('加载失败')
  } finally {
    loading.value = false
  }
}

function resetFilter() {
  keyword.value = ''
  pagination.current = 1
  loadProfiles()
}

function handleTableChange(pag: any) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadProfiles()
}

async function viewDetail(record: PageProfile) {
  try {
    currentProfile.value = await getPageProfile(record.id)
    detailVisible.value = true
  } catch (e) {
    message.error('加载详情失败')
  }
}

async function triggerAggregate() {
  aggregating.value = true
  try {
    const res = await triggerAggregation(projectId)
    message.success(res.message || '聚合任务已提交')
    setTimeout(loadProfiles, 2000)
  } catch (e) {
    message.error('触发失败')
  } finally {
    aggregating.value = false
  }
}

function formatTime(dt?: string) {
  if (!dt) return '-'
  return new Date(dt).toLocaleString('zh-CN')
}

onMounted(loadProfiles)
</script>

<style scoped>
.profiles-page { padding: 20px; }
.filter-bar { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; }
.selector-code {
  background: #f5f5f5;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 11px;
  word-break: break-all;
}
.text-muted { color: #bfbfbf; font-size: 12px; }
.detail-content { max-height: 65vh; overflow-y: auto; }
.detail-section { margin-top: 20px; }
.detail-section h4 { margin-bottom: 12px; font-size: 14px; }
.failure-item { margin-bottom: 8px; display: flex; gap: 8px; align-items: center; }
.fail-reason { font-size: 12px; color: #ff4d4f; }
</style>
