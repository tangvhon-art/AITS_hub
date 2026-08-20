<template>
  <div class="healing-page">
    <!-- 查询栏 -->
    <div class="filter-bar">
      <a-select v-model:value="filterLevel" placeholder="自愈等级" allow-clear style="width: 120px" @change="loadRecords">
        <a-select-option value="L1">L1 属性回退</a-select-option>
        <a-select-option value="L2">L2 AI推理</a-select-option>
        <a-select-option value="L3">L3 视觉定位</a-select-option>
        <a-select-option value="L4">L4 修复失败</a-select-option>
      </a-select>
      <a-select v-model:value="filterResult" placeholder="修复结果" allow-clear style="width: 120px" @change="loadRecords">
        <a-select-option value="success">成功</a-select-option>
        <a-select-option value="fail">失败</a-select-option>
        <a-select-option value="pending_review">待确认</a-select-option>
      </a-select>
      <a-button @click="loadRecords"><SearchOutlined /> 查询</a-button>
      <a-button @click="resetFilter">重置</a-button>
      <a-button type="primary" @click="loadStats" style="margin-left: auto">
        <ReloadOutlined /> 刷新统计
      </a-button>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-row" v-if="stats">
      <div class="stat-card">
        <div class="stat-value">{{ stats.total }}</div>
        <div class="stat-label">总自愈次数</div>
      </div>
      <div class="stat-card success">
        <div class="stat-value">{{ stats.success }}</div>
        <div class="stat-label">成功</div>
      </div>
      <div class="stat-card fail">
        <div class="stat-value">{{ stats.failed }}</div>
        <div class="stat-label">失败</div>
      </div>
      <div class="stat-card pending">
        <div class="stat-value">{{ stats.pending_review }}</div>
        <div class="stat-label">待确认</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ (stats.success_rate * 100).toFixed(1) }}%</div>
        <div class="stat-label">成功率</div>
      </div>
      <div class="stat-card l1">
        <div class="stat-value">{{ stats.l1_count }}</div>
        <div class="stat-label">L1 属性回退</div>
      </div>
      <div class="stat-card l2">
        <div class="stat-value">{{ stats.l2_count }}</div>
        <div class="stat-label">L2 AI推理</div>
      </div>
      <div class="stat-card l3">
        <div class="stat-value">{{ stats.l3_count }}</div>
        <div class="stat-label">L3 视觉定位</div>
      </div>
      <div class="stat-card applied">
        <div class="stat-value">{{ stats.applied_count }}</div>
        <div class="stat-label">已回写脚本</div>
      </div>
    </div>

    <!-- 记录列表 -->
    <a-table
      :columns="columns"
      :data-source="records"
      :loading="loading"
      :pagination="pagination"
      @change="handleTableChange"
      row-key="id"
      size="middle"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'healing_level'">
          <a-tag :color="levelColor[record.healing_level]">{{ record.healing_level }}</a-tag>
        </template>
        <template v-else-if="column.key === 'healing_result'">
          <a-tag :color="resultColor[record.healing_result]">{{ resultText[record.healing_result] || record.healing_result }}</a-tag>
        </template>
        <template v-else-if="column.key === 'original_selector'">
          <a-tooltip :title="record.original_selector">
            <code class="selector-code">{{ record.original_selector }}</code>
          </a-tooltip>
        </template>
        <template v-else-if="column.key === 'suggested_selector'">
          <a-tooltip v-if="record.suggested_selector" :title="record.suggested_selector">
            <code class="selector-code success-code">{{ record.suggested_selector }}</code>
          </a-tooltip>
          <span v-else class="text-muted">-</span>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-button type="link" size="small" @click="viewDetail(record)">详情</a-button>
          <template v-if="isPending(record) || isUnconfirmedSuccess(record)">
            <a-popconfirm
              title="确认该修复有效并回写到脚本？"
              ok-text="确认回写"
              cancel-text="取消"
              @confirm="confirmRecord(record)"
            >
              <a-button type="link" size="small">确认</a-button>
            </a-popconfirm>
            <a-popconfirm
              title="确认该修复无效？标记为失败"
              ok-text="拒绝"
              ok-type="danger"
              cancel-text="取消"
              @confirm="rejectRecord(record)"
            >
              <a-button type="link" size="small" danger>拒绝</a-button>
            </a-popconfirm>
          </template>
        </template>
      </template>
    </a-table>

    <!-- 详情弹窗 -->
    <a-modal v-model:open="detailVisible" title="自愈记录详情" width="800px" :footer="null">
      <div v-if="currentRecord" class="detail-content">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="自愈等级">
            <a-tag :color="levelColor[currentRecord.healing_level]">{{ currentRecord.healing_level }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="修复结果">
            <a-tag :color="resultColor[currentRecord.healing_result]">{{ resultText[currentRecord.healing_result] }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="操作类型">{{ currentRecord.action_type }}</a-descriptions-item>
          <a-descriptions-item label="时间">{{ formatTime(currentRecord.created_at) }}</a-descriptions-item>
          <a-descriptions-item label="页面URL" :span="2">{{ currentRecord.page_url }}</a-descriptions-item>
          <a-descriptions-item label="原定位器" :span="2">
            <code class="selector-code">{{ currentRecord.original_selector }}</code>
          </a-descriptions-item>
          <a-descriptions-item label="修复后定位器" :span="2">
            <code class="selector-code success-code">{{ currentRecord.suggested_selector || '-' }}</code>
          </a-descriptions-item>
          <a-descriptions-item label="失败原因" :span="2">{{ currentRecord.fail_reason }}</a-descriptions-item>
          <a-descriptions-item label="自愈策略" :span="2">{{ currentRecord.healing_strategy }}</a-descriptions-item>
        </a-descriptions>

        <div v-if="currentRecord.screenshot_before || currentRecord.screenshot_after" class="detail-section">
          <h4>截图对比</h4>
          <div class="screenshot-compare">
            <div v-if="currentRecord.screenshot_before" class="screenshot-item">
              <div class="screenshot-label">失败时</div>
              <a-image :src="'/api/' + currentRecord.screenshot_before" :width="360" />
            </div>
            <div v-if="currentRecord.screenshot_after" class="screenshot-item">
              <div class="screenshot-label">修复后</div>
              <a-image :src="'/api/' + currentRecord.screenshot_after" :width="360" />
            </div>
          </div>
        </div>

        <div v-if="currentRecord.candidates && currentRecord.candidates.length" class="detail-section">
          <h4>候选定位器</h4>
          <a-table :data-source="currentRecord.candidates" :columns="candidateColumns" size="small" :pagination="false" row-key="selector">
            <template #bodyCell="{ column, record: c }">
              <template v-if="column.key === 'confidence'">
                <a-progress :percent="Math.round((c.confidence || 0) * 100)" size="small" style="width: 100px" />
              </template>
            </template>
          </a-table>
        </div>

        <div v-if="currentRecord.ai_reasoning" class="detail-section">
          <h4>AI 推理过程</h4>
          <pre class="reasoning-block">{{ currentRecord.ai_reasoning }}</pre>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { SearchOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import { useRoute } from 'vue-router'
import {
  listHealingRecords, getHealingRecord, confirmHealing, rejectHealing, getHealingStats,
  type HealingRecord, type HealingStats,
} from '@/api/uiHealing'

const route = useRoute()
const projectId = Number(route.params.id)

const loading = ref(false)
const records = ref<HealingRecord[]>([])
const stats = ref<HealingStats | null>(null)
const filterLevel = ref<string>()
const filterResult = ref<string>()
const filterScriptId = ref<number | undefined>(route.query.script_id ? Number(route.query.script_id) : undefined)

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: (t: number) => `共 ${t} 条`,
})

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
  { title: '等级', dataIndex: 'healing_level', key: 'healing_level', width: 80 },
  { title: '结果', dataIndex: 'healing_result', key: 'healing_result', width: 90 },
  { title: '操作', dataIndex: 'action_type', key: 'action_type', width: 80 },
  { title: '原定位器', dataIndex: 'original_selector', key: 'original_selector', ellipsis: true },
  { title: '修复后', dataIndex: 'suggested_selector', key: 'suggested_selector', ellipsis: true },
  { title: '策略', dataIndex: 'healing_strategy', key: 'healing_strategy', width: 200, ellipsis: true },
  { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 160 },
  { title: '操作', key: 'action', width: 140 },
]

const candidateColumns = [
  { title: '定位器', dataIndex: 'selector', key: 'selector' },
  { title: '类型', dataIndex: 'type', key: 'type', width: 80 },
  { title: '置信度', dataIndex: 'confidence', key: 'confidence', width: 120 },
  { title: '理由', dataIndex: 'reason', key: 'reason', ellipsis: true },
]

const levelColor: Record<string, string> = { L1: 'blue', L2: 'purple', L3: 'orange', L4: 'red' }
const resultColor: Record<string, string> = { success: 'green', fail: 'red', pending: 'gold', pending_review: 'gold' }
const resultText: Record<string, string> = { success: '成功', fail: '失败', pending: '待处理', pending_review: '待确认' }

const detailVisible = ref(false)
const currentRecord = ref<HealingRecord | null>(null)

async function loadRecords() {
  loading.value = true
  try {
    const res = await listHealingRecords({
      project_id: projectId,
      script_id: filterScriptId.value,
      healing_level: filterLevel.value,
      healing_result: filterResult.value,
      page: pagination.current,
      page_size: pagination.pageSize,
    })
    records.value = res.items
    pagination.total = res.total
  } catch (e) {
    message.error('加载失败')
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    stats.value = await getHealingStats(projectId)
  } catch (e) {
    console.error(e)
  }
}

function resetFilter() {
  filterLevel.value = undefined
  filterResult.value = undefined
  pagination.current = 1
  loadRecords()
}

function handleTableChange(pag: any) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadRecords()
}

async function viewDetail(record: HealingRecord) {
  try {
    currentRecord.value = await getHealingRecord(record.id)
    detailVisible.value = true
  } catch (e) {
    message.error('加载详情失败')
  }
}

async function confirmRecord(record: HealingRecord) {
  try {
    await confirmHealing(record.id, true)
    message.success('已确认并回写到脚本')
    loadRecords()
    loadStats()
  } catch (e) {
    message.error('操作失败')
  }
}

async function rejectRecord(record: HealingRecord) {
  try {
    await rejectHealing(record.id)
    message.success('已标记为失败')
    loadRecords()
    loadStats()
  } catch (e) {
    message.error('操作失败')
  }
}

function isPending(record: HealingRecord) {
  return record.healing_result === 'pending_review' && !record.confirmed_by
}

function isUnconfirmedSuccess(record: HealingRecord) {
  return record.healing_result === 'success' && !record.confirmed_by && record.healing_level !== 'L1'
}

function formatTime(dt?: string) {
  if (!dt) return '-'
  return new Date(dt).toLocaleString('zh-CN')
}

onMounted(() => {
  loadRecords()
  loadStats()
})
</script>

<style scoped>
.healing-page { padding: 20px; }
.filter-bar {
  display: flex; gap: 12px; margin-bottom: 16px; align-items: center;
}
.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.stat-card {
  background: #fff;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
}
.stat-card.success { border-top: 3px solid #52c41a; }
.stat-card.fail { border-top: 3px solid #ff4d4f; }
.stat-card.pending { border-top: 3px solid #faad14; }
.stat-card.l1 { border-top: 3px solid #1677ff; }
.stat-card.l2 { border-top: 3px solid #722ed1; }
.stat-card.l3 { border-top: 3px solid #fa8c16; }
.stat-card.applied { border-top: 3px solid #13c2c2; }
.stat-value { font-size: 24px; font-weight: 600; color: #1f2329; }
.stat-label { font-size: 12px; color: #86909c; margin-top: 4px; }
.selector-code {
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 12px;
  word-break: break-all;
}
.success-code { background: #f6ffed; color: #389e0d; }
.text-muted { color: #bfbfbf; }
.detail-content { max-height: 60vh; overflow-y: auto; }
.detail-section { margin-top: 20px; }
.detail-section h4 { margin-bottom: 12px; font-size: 14px; }
.reasoning-block {
  background: #f5f5f5;
  padding: 12px;
  border-radius: 6px;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
}
.screenshot-compare {
  display: flex;
  gap: 16px;
}
.screenshot-item {
  flex: 1;
}
.screenshot-label {
  font-size: 12px;
  color: #86909c;
  margin-bottom: 8px;
  font-weight: 500;
}
</style>
