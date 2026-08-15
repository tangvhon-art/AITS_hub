<template>
  <div class="test-plan-edit">
    <a-page-header title="测试计划编辑" @back="goBack">
      <template #extra>
        <a-button @click="goBack">取消</a-button>
        <a-button type="primary" :loading="saving" @click="handleSave">保存</a-button>
      </template>
    </a-page-header>

    <a-row :gutter="16" style="margin-top: 16px">
      <!-- 左侧：基本信息 -->
      <a-col :span="6">
        <a-card title="基本信息" size="small">
          <a-form layout="vertical" :model="form">
            <a-form-item label="计划名称" required>
              <a-input v-model:value="form.name" placeholder="请输入计划名称" />
            </a-form-item>
            <a-form-item label="描述">
              <a-textarea v-model:value="form.description" :rows="3" placeholder="计划描述" />
            </a-form-item>
            <a-form-item label="测试环境">
              <a-select v-model:value="form.environment_id" placeholder="选择环境" allow-clear>
                <a-select-option v-for="env in environments" :key="env.id" :value="env.id">
                  {{ env.name }} ({{ env.base_url }})
                </a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item label="优先级">
              <a-select v-model:value="form.priority" placeholder="选择优先级">
                <a-select-option value="P0">P0 - 紧急</a-select-option>
                <a-select-option value="P1">P1 - 高</a-select-option>
                <a-select-option value="P2">P2 - 中</a-select-option>
                <a-select-option value="P3">P3 - 低</a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item label="全局超时(秒)">
              <a-input-number v-model:value="globalTimeout" :min="0" style="width: 100%" placeholder="0表示不限制" />
            </a-form-item>
            <a-form-item label="全局最大重试">
              <a-input-number v-model:value="globalRetries" :min="0" :max="10" style="width: 100%" />
            </a-form-item>
          </a-form>
        </a-card>
      </a-col>

      <!-- 右侧：节点编排 -->
      <a-col :span="18">
        <a-card title="节点编排" size="small">
          <a-row :gutter="16">
            <!-- 节点库 -->
            <a-col :span="10">
              <div class="node-library">
                <div class="library-header">
                  <a-input
                    v-model:value="searchKeyword"
                    placeholder="搜索用例/场景"
                    size="small"
                    allow-clear
                  >
                    <template #prefix><SearchOutlined /></template>
                  </a-input>
                  <a-radio-group v-model:value="filterType" size="small" style="margin-top: 8px">
                    <a-radio-button value="">全部</a-radio-button>
                    <a-radio-button value="case">用例</a-radio-button>
                    <a-radio-button value="scenario">场景</a-radio-button>
                  </a-radio-group>
                </div>
                <div class="library-list">
                  <div v-if="filterType !== 'scenario'" class="library-group">
                    <div class="group-title">接口用例 ({{ availableCases.length }})</div>
                    <div
                      v-for="item in availableCases"
                      :key="'case-' + item.id"
                      class="library-item"
                      :class="{ disabled: item.added }"
                      @click="!item.added && addItem('case', item)"
                    >
                      <div class="item-name">
                        <ApiOutlined /> {{ item.name }}
                      </div>
                      <div class="item-meta">
                        <a-tag :color="getMethodColor(item.method)" size="small">{{ item.method }}</a-tag>
                        <span class="item-path">{{ item.path }}</span>
                      </div>
                    </div>
                  </div>
                  <div v-if="filterType !== 'case'" class="library-group">
                    <div class="group-title">场景编排 ({{ availableScenarios.length }})</div>
                    <div
                      v-for="item in availableScenarios"
                      :key="'scenario-' + item.id"
                      class="library-item"
                      :class="{ disabled: item.added }"
                      @click="!item.added && addItem('scenario', item)"
                    >
                      <div class="item-name">
                        <NodeIndexOutlined /> {{ item.name }}
                      </div>
                      <div class="item-meta">
                        <span class="item-path">{{ item.description || '场景编排' }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </a-col>

            <!-- 已选节点 -->
            <a-col :span="14">
              <div class="selected-nodes">
                <div class="selected-header">
                  <span>已选节点 ({{ selectedItems.length }})</span>
                  <a-button size="small" @click="clearAll" :disabled="selectedItems.length === 0">
                    清空
                  </a-button>
                </div>
                <div class="selected-list">
                  <div v-if="selectedItems.length === 0" class="empty-tip">
                    从左侧选择节点添加到测试计划
                  </div>
                  <div
                    v-for="(item, index) in selectedItems"
                    :key="item.id || item.tempId"
                    class="selected-item"
                  >
                    <div class="item-drag">
                      <HolderOutlined />
                    </div>
                    <div class="item-index">{{ index + 1 }}</div>
                    <div class="item-content">
                      <div class="item-title">
                        <a-tag :color="item.item_type === 'case' ? 'blue' : 'purple'" size="small">
                          {{ item.item_type === 'case' ? '用例' : '场景' }}
                        </a-tag>
                        <span class="item-name">{{ item.item_name }}</span>
                      </div>
                      <div class="item-config">
                        <a-select
                          v-model:value="item.fail_strategy"
                          size="small"
                          style="width: 100px"
                          @change="updateItem(item)"
                        >
                          <a-select-option value="stop">失败停止</a-select-option>
                          <a-select-option value="continue">失败继续</a-select-option>
                        </a-select>
                        <a-input-number
                          v-model:value="item.timeout"
                          size="small"
                          :min="0"
                          style="width: 80px"
                          placeholder="超时"
                          @change="updateItem(item)"
                        />
                        <span class="config-label">秒</span>
                        <a-input-number
                          v-model:value="item.max_retries"
                          size="small"
                          :min="0"
                          :max="10"
                          style="width: 70px"
                          placeholder="重试"
                          @change="updateItem(item)"
                        />
                        <span class="config-label">次</span>
                        <a-switch
                          v-model:checked="item.enabled"
                          size="small"
                          checked-children="启用"
                          un-checked-children="禁用"
                          @change="updateItem(item)"
                        />
                      </div>
                    </div>
                    <div class="item-actions">
                      <a-button type="text" size="small" @click="moveUp(index)" :disabled="index === 0">
                        <ArrowUpOutlined />
                      </a-button>
                      <a-button type="text" size="small" @click="moveDown(index)" :disabled="index === selectedItems.length - 1">
                        <ArrowDownOutlined />
                      </a-button>
                      <a-button type="text" size="small" danger @click="removeItem(index)">
                        <DeleteOutlined />
                      </a-button>
                    </div>
                  </div>
                </div>
              </div>
            </a-col>
          </a-row>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  SearchOutlined, ApiOutlined, NodeIndexOutlined, HolderOutlined,
  ArrowUpOutlined, ArrowDownOutlined, DeleteOutlined
} from '@ant-design/icons-vue'
import {
  testPlansApi, testPlanItemsApi, getEnvironments,
  type TestPlan, type TestPlanItem, type TestEnvironment, type AvailableItem
} from '@/api/testPlans'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.projectId)
const planId = Number(route.params.planId)

const saving = ref(false)
const loading = ref(false)
const searchKeyword = ref('')
const filterType = ref('')
const environments = ref<TestEnvironment[]>([])
const availableCases = ref<AvailableItem[]>([])
const availableScenarios = ref<AvailableItem[]>([])
const selectedItems = ref<(TestPlanItem & { tempId?: string })[]>([])
const globalTimeout = ref(0)
const globalRetries = ref(0)

const form = ref<Partial<TestPlan>>({
  name: '',
  description: '',
  environment_id: null,
  priority: 'P2',
  execution_config: {},
})

function getMethodColor(method?: string) {
  const colors: Record<string, string> = {
    GET: 'green', POST: 'blue', PUT: 'orange', DELETE: 'red',
    PATCH: 'purple', HEAD: 'cyan', OPTIONS: 'default',
  }
  return colors[method || ''] || 'default'
}

async function loadEnvironments() {
  try {
    environments.value = await getEnvironments(projectId)
  } catch (e) {
    console.error('加载环境失败', e)
  }
}

async function loadPlan() {
  if (!planId) return
  try {
    const plan = await testPlansApi.get(projectId, planId)
    form.value = { ...plan }
    globalTimeout.value = plan.execution_config?.timeout || 0
    globalRetries.value = plan.execution_config?.max_retries || 0
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载计划失败')
  }
}

async function loadItems() {
  if (!planId) return
  try {
    selectedItems.value = await testPlanItemsApi.list(projectId, planId)
  } catch (e) {
    console.error('加载节点失败', e)
  }
}

async function loadAvailable() {
  try {
    const res = await testPlanItemsApi.available(projectId, planId || 0, {
      keyword: searchKeyword.value || undefined,
      item_type: filterType.value || undefined,
    })
    availableCases.value = res.cases
    availableScenarios.value = res.scenarios
  } catch (e) {
    console.error('加载可用节点失败', e)
  }
}

function addItem(type: string, item: AvailableItem) {
  const newItem: TestPlanItem & { tempId?: string } = {
    id: 0,
    plan_id: planId,
    item_type: type,
    ref_id: item.id,
    item_name: item.name,
    sort_order: selectedItems.value.length,
    enabled: true,
    fail_strategy: 'stop',
    timeout: globalTimeout.value,
    max_retries: globalRetries.value,
    config: {},
    tempId: `temp-${Date.now()}-${Math.random()}`,
    created_at: '',
    updated_at: '',
  }
  selectedItems.value.push(newItem)
  // 如果是编辑模式，立即保存到后端
  if (planId) {
    saveNewItem(newItem)
  }
  loadAvailable()
}

async function saveNewItem(item: any) {
  try {
    const saved = await testPlanItemsApi.add(projectId, planId, {
      item_type: item.item_type,
      ref_id: item.ref_id,
      item_name: item.item_name,
      sort_order: item.sort_order,
      enabled: item.enabled,
      fail_strategy: item.fail_strategy,
      timeout: item.timeout,
      max_retries: item.max_retries,
      config: item.config,
    })
    item.id = saved.id
    item.tempId = undefined
  } catch (e: any) {
    message.error(e.response?.data?.detail || '添加节点失败')
  }
}

async function updateItem(item: TestPlanItem) {
  if (!planId || !item.id) return
  try {
    await testPlanItemsApi.update(projectId, planId, item.id, {
      enabled: item.enabled,
      fail_strategy: item.fail_strategy,
      timeout: item.timeout,
      max_retries: item.max_retries,
    })
  } catch (e) {
    console.error('更新节点失败', e)
  }
}

async function removeItem(index: number) {
  const item = selectedItems.value[index]
  if (planId && item.id) {
    try {
      await testPlanItemsApi.delete(projectId, planId, item.id)
    } catch (e) {
      console.error('删除节点失败', e)
    }
  }
  selectedItems.value.splice(index, 1)
  // 重新排序
  selectedItems.value.forEach((it, idx) => { it.sort_order = idx })
  if (planId) {
    const ids = selectedItems.value.filter(i => i.id).map(i => i.id)
    testPlanItemsApi.reorder(projectId, planId, ids)
  }
  loadAvailable()
}

function moveUp(index: number) {
  if (index === 0) return
  const items = selectedItems.value
  ;[items[index - 1], items[index]] = [items[index], items[index - 1]]
  items.forEach((it, idx) => { it.sort_order = idx })
  if (planId) {
    const ids = items.filter(i => i.id).map(i => i.id)
    testPlanItemsApi.reorder(projectId, planId, ids)
  }
}

function moveDown(index: number) {
  if (index === selectedItems.value.length - 1) return
  const items = selectedItems.value
  ;[items[index + 1], items[index]] = [items[index], items[index + 1]]
  items.forEach((it, idx) => { it.sort_order = idx })
  if (planId) {
    const ids = items.filter(i => i.id).map(i => i.id)
    testPlanItemsApi.reorder(projectId, planId, ids)
  }
}

function clearAll() {
  selectedItems.value = []
  if (planId) {
    loadAvailable()
  }
}

async function handleSave() {
  if (!form.value.name) {
    message.warning('请输入计划名称')
    return
  }
  saving.value = true
  try {
    const data = {
      ...form.value,
      execution_config: {
        timeout: globalTimeout.value,
        max_retries: globalRetries.value,
      },
    }
    if (planId) {
      await testPlansApi.update(projectId, planId, data)
      message.success('保存成功')
    } else {
      const created = await testPlansApi.create(projectId, data)
      message.success('创建成功')
      router.replace(`/projects/${projectId}/test-plans/${created.id}/edit`)
      return
    }
  } catch (e: any) {
    message.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

function goBack() {
  router.push(`/projects/${projectId}/plans`)
}

onMounted(() => {
  loadEnvironments()
  loadPlan()
  loadItems()
  loadAvailable()
})
</script>

<style scoped>
.test-plan-edit {
  padding: 16px;
}
.node-library, .selected-nodes {
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  height: 600px;
  display: flex;
  flex-direction: column;
}
.library-header, .selected-header {
  padding: 12px;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.selected-header {
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
}
.library-list, .selected-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.library-group {
  margin-bottom: 16px;
}
.group-title {
  font-size: 12px;
  color: #999;
  margin-bottom: 8px;
  padding: 0 4px;
}
.library-item {
  padding: 10px 12px;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s;
}
.library-item:hover:not(.disabled) {
  border-color: #1890ff;
  background: #e6f7ff;
}
.library-item.disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background: #fafafa;
}
.item-name {
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.item-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}
.item-path {
  font-size: 11px;
  color: #999;
  font-family: monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.selected-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  margin-bottom: 8px;
  background: #fff;
}
.item-drag {
  cursor: move;
  color: #ccc;
}
.item-index {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #1890ff;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  flex-shrink: 0;
}
.item-content {
  flex: 1;
  min-width: 0;
}
.item-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.item-title .item-name {
  margin-bottom: 0;
}
.item-config {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.config-label {
  font-size: 11px;
  color: #999;
}
.item-actions {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.empty-tip {
  text-align: center;
  color: #999;
  padding: 60px 20px;
  font-size: 13px;
}
</style>
