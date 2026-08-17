<template>
  <div class="notification-channels-page">
    <a-card :bordered="false" class="page-card">
      <div class="page-header">
        <div class="header-left">
          <h2 class="page-title">通知渠道</h2>
          <span class="page-desc">配置飞书机器人等通知渠道，全局共享</span>
        </div>
        <div class="header-right">
          <a-input-search
            v-model:value="searchKeyword"
            placeholder="搜索渠道名称"
            style="width: 220px; margin-right: 12px"
            allow-clear
            @search="loadChannels"
          />
          <a-button type="primary" style="margin-right: 8px" @click="loadChannels">查询</a-button>
          <a-button style="margin-right: 8px" @click="handleReset">重置</a-button>
          <a-button type="primary" @click="openCreateModal">
            <template #icon><plus-outlined /></template>
            新建渠道
          </a-button>
        </div>
      </div>

      <a-table
        :columns="columns"
        :data-source="channels"
        :loading="loading"
        :pagination="false"
        row-key="id"
        size="middle"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <span class="channel-name">{{ record.name }}</span>
            <div v-if="record.description" class="channel-desc">{{ record.description }}</div>
          </template>
          <template v-else-if="column.key === 'channel_type'">
            <a-tag color="blue">{{ typeLabel(record.channel_type) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'webhook_url'">
            <span class="webhook-url" :title="record.webhook_url">{{ record.webhook_url }}</span>
          </template>
          <template v-else-if="column.key === 'sign_enabled'">
            <a-tag :color="record.sign_enabled ? 'green' : 'default'">
              {{ record.sign_enabled ? '已启用' : '未启用' }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'enabled'">
            <a-switch
              :checked="record.enabled"
              size="small"
              @change="(val: boolean) => handleToggleEnabled(record, val)"
            />
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space>
              <a-button type="link" size="small" @click="handleTest(record)">
                <loading-outlined v-if="testingId === record.id" />
                测试发送
              </a-button>
              <a-button type="link" size="small" @click="openEditModal(record)">编辑</a-button>
              <a-popconfirm
                title="确定删除该渠道吗？"
                ok-text="确定"
                cancel-text="取消"
                @confirm="handleDelete(record)"
              >
                <a-button type="link" size="small" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 新建/编辑弹窗 -->
    <a-modal
      v-model:open="modalVisible"
      :title="isEdit ? '编辑渠道' : '新建渠道'"
      width="560px"
      :confirm-loading="saving"
      ok-text="保存"
      cancel-text="取消"
      @ok="handleSave"
    >
      <a-form :model="formData" layout="vertical">
        <a-form-item label="渠道名称" required>
          <a-input v-model:value="formData.name" placeholder="请输入渠道名称，如：测试团队飞书群" />
        </a-form-item>
        <a-form-item label="渠道类型" required>
          <a-select v-model:value="formData.channel_type" placeholder="请选择渠道类型">
            <a-select-option value="feishu">飞书机器人</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="Webhook 地址" required>
          <a-input
            v-model:value="formData.webhook_url"
            placeholder="请输入飞书机器人 Webhook 地址"
          />
        </a-form-item>
        <a-form-item label="启用签名校验">
          <a-switch v-model:checked="formData.sign_enabled" />
          <span class="form-hint">开启后需要填写签名密钥</span>
        </a-form-item>
        <a-form-item v-if="formData.sign_enabled" label="签名密钥" required>
          <a-input-password
            v-model:value="formData.secret"
            :placeholder="isEdit && formData.has_secret ? '留空则不修改原密钥' : '请输入签名密钥'"
          />
        </a-form-item>
        <a-form-item label="备注">
          <a-textarea
            v-model:value="formData.description"
            placeholder="请输入备注说明（可选）"
            :rows="2"
          />
        </a-form-item>
        <a-form-item label="启用渠道">
          <a-switch v-model:checked="formData.enabled" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined, LoadingOutlined } from '@ant-design/icons-vue'
import { notificationApi, type NotificationChannel } from '@/api/notifications'
import { useUrlSearch } from '@/composables/useUrlSearch'

const { loadFromUrl, syncToUrl } = useUrlSearch()

const loading = ref(false)
const saving = ref(false)
const channels = ref<NotificationChannel[]>([])
const searchKeyword = ref('')
const testingId = ref<number | null>(null)

const modalVisible = ref(false)
const isEdit = ref(false)
const editingId = ref<number | null>(null)

const formData = reactive({
  name: '',
  channel_type: 'feishu',
  webhook_url: '',
  sign_enabled: false,
  secret: '',
  enabled: true,
  description: '',
  has_secret: false,
})

const columns = [
  { title: '渠道名称', key: 'name', dataIndex: 'name', width: 200 },
  { title: '类型', key: 'channel_type', dataIndex: 'channel_type', width: 120 },
  { title: 'Webhook 地址', key: 'webhook_url', dataIndex: 'webhook_url', ellipsis: true },
  { title: '验签', key: 'sign_enabled', dataIndex: 'sign_enabled', width: 90 },
  { title: '启用', key: 'enabled', dataIndex: 'enabled', width: 80 },
  { title: '操作', key: 'action', width: 220 },
]

function typeLabel(type: string): string {
  const map: Record<string, string> = { feishu: '飞书机器人', dingtalk: '钉钉', wecom: '企业微信', webhook: 'Webhook' }
  return map[type] || type
}

async function loadChannels() {
  syncToUrl({ keyword: searchKeyword.value })
  loading.value = true
  try {
    const params: any = {}
    if (searchKeyword.value) params.keyword = searchKeyword.value
    channels.value = await notificationApi.getChannels(params)
  } catch (e) {
    // 错误已由拦截器处理
  } finally {
    loading.value = false
  }
}

function resetForm() {
  formData.name = ''
  formData.channel_type = 'feishu'
  formData.webhook_url = ''
  formData.sign_enabled = false
  formData.secret = ''
  formData.enabled = true
  formData.description = ''
  formData.has_secret = false
  editingId.value = null
}

function openCreateModal() {
  resetForm()
  isEdit.value = false
  modalVisible.value = true
}

function openEditModal(record: NotificationChannel) {
  resetForm()
  isEdit.value = true
  editingId.value = record.id
  formData.name = record.name
  formData.channel_type = record.channel_type
  formData.webhook_url = record.webhook_url
  formData.sign_enabled = record.sign_enabled
  formData.enabled = record.enabled
  formData.description = record.description || ''
  formData.has_secret = record.has_secret
  modalVisible.value = true
}

async function handleSave() {
  if (!formData.name.trim()) {
    message.warning('请输入渠道名称')
    return
  }
  if (!formData.webhook_url.trim()) {
    message.warning('请输入 Webhook 地址')
    return
  }
  if (formData.sign_enabled && !formData.secret && !(isEdit.value && formData.has_secret)) {
    message.warning('启用签名校验时必须填写签名密钥')
    return
  }

  saving.value = true
  try {
    const payload: any = {
      name: formData.name,
      channel_type: formData.channel_type,
      webhook_url: formData.webhook_url,
      sign_enabled: formData.sign_enabled,
      enabled: formData.enabled,
      description: formData.description,
    }
    if (formData.secret) payload.secret = formData.secret
    if (isEdit.value && editingId.value) {
      await notificationApi.updateChannel(editingId.value, payload)
      message.success('渠道更新成功')
    } else {
      await notificationApi.createChannel(payload)
      message.success('渠道创建成功')
    }
    modalVisible.value = false
    loadChannels()
  } catch (e) {
    // 错误已由拦截器处理
  } finally {
    saving.value = false
  }
}

async function handleToggleEnabled(record: NotificationChannel, val: boolean) {
  try {
    await notificationApi.updateChannel(record.id, { enabled: val })
    record.enabled = val
    message.success(val ? '渠道已启用' : '渠道已禁用')
  } catch (e) {
    // 错误已由拦截器处理
  }
}

async function handleTest(record: NotificationChannel) {
  testingId.value = record.id
  try {
    const result = await notificationApi.testChannel(record.id)
    if (result.success) {
      message.success('测试消息发送成功，请查看飞书群')
    } else {
      message.error(`发送失败：${result.message}`)
    }
  } catch (e) {
    // 错误已由拦截器处理
  } finally {
    testingId.value = null
  }
}

async function handleDelete(record: NotificationChannel) {
  try {
    await notificationApi.deleteChannel(record.id)
    message.success('渠道已删除')
    loadChannels()
  } catch (e) {
    // 错误已由拦截器处理
  }
}

function handleReset() {
  searchKeyword.value = ''
  loadChannels()
}

onMounted(() => {
  const params = loadFromUrl({ keyword: '' })
  searchKeyword.value = params.keyword
  loadChannels()
})
</script>

<style scoped>
.notification-channels-page {
  padding: 0;
}
.page-card {
  min-height: calc(100vh - 120px);
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}
.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #1f1f1f;
}
.page-desc {
  font-size: 13px;
  color: #8c8c8c;
  margin-left: 12px;
}
.header-left {
  display: flex;
  align-items: baseline;
}
.channel-name {
  font-weight: 500;
  color: #1f1f1f;
}
.channel-desc {
  font-size: 12px;
  color: #8c8c8c;
  margin-top: 2px;
}
.webhook-url {
  font-family: monospace;
  font-size: 12px;
  color: #595959;
}
.form-hint {
  margin-left: 8px;
  font-size: 12px;
  color: #8c8c8c;
}
</style>
