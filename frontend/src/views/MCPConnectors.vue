<template>
  <div class="mcp-page">
    <div class="page-header">
      <h2>MCP 连接器管理</h2>
      <div class="header-actions">
        <a-button @click="jsonImportVisible = true">从 JSON 导入</a-button>
        <a-button type="primary" @click="openCreate">新建连接器</a-button>
      </div>
    </div>

    <div class="filter-bar">
      <a-input
        v-model:value="searchKeyword"
        placeholder="搜索名称/描述"
        allow-clear
        style="width: 220px"
        @keyup.enter="handleSearch"
      >
        <template #prefix><SearchOutlined /></template>
      </a-input>
      <a-select v-model:value="filterStatus" placeholder="全部状态" allow-clear style="width: 130px" @change="handleSearch">
        <a-select-option value="connected">已连接</a-select-option>
        <a-select-option value="disconnected">未连接</a-select-option>
        <a-select-option value="error">错误</a-select-option>
      </a-select>
      <a-select v-model:value="filterTransport" placeholder="全部传输方式" allow-clear style="width: 130px" @change="handleSearch">
        <a-select-option value="sse">SSE</a-select-option>
        <a-select-option value="stdio">stdio</a-select-option>
      </a-select>
      <a-button type="primary" @click="handleSearch">查询</a-button>
      <a-button @click="handleReset">重置</a-button>
    </div>

    <a-table :columns="columns" :data-source="filteredList" :pagination="pagination" :loading="loading" row-key="id">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="statusColor(record.status)">{{ record.status }}</a-tag>
        </template>
        <template v-else-if="column.key === 'transport'">
          <a-tag>{{ record.transport }}</a-tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-button type="link" size="small" @click="handleConnect(record)" :disabled="record.status === 'connected'">连接</a-button>
          <a-button type="link" size="small" @click="handleDisconnect(record)" :disabled="record.status !== 'connected'">断开</a-button>
          <a-button type="link" size="small" @click="openEdit(record)">编辑</a-button>
          <a-popconfirm title="确认删除？" @confirm="handleDelete(record)">
            <a-button type="link" size="small" danger>删除</a-button>
          </a-popconfirm>
        </template>
      </template>
    </a-table>

    <!-- 新建/编辑弹窗 -->
    <a-modal v-model:open="modalVisible" :title="editingId ? '编辑连接器' : '新建连接器'" @ok="handleSave" :confirm-loading="saving">
      <a-form :model="form" layout="vertical">
        <a-form-item label="名称" required>
          <a-input v-model:value="form.name" placeholder="连接器名称" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="2" />
        </a-form-item>
        <a-form-item label="传输方式" required>
          <a-select v-model:value="form.transport">
            <a-select-option value="sse">SSE（HTTP）</a-select-option>
            <a-select-option value="stdio">stdio（本地命令）</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item v-if="form.transport === 'sse'" label="服务地址" required>
          <a-input v-model:value="form.url" placeholder="https://example.com/mcp" />
        </a-form-item>
        <a-form-item v-if="form.transport === 'stdio'" label="启动命令" required>
          <a-input v-model:value="form.command" placeholder="npx -y @modelcontextprotocol/server-filesystem" />
        </a-form-item>
        <a-form-item v-if="form.transport === 'stdio'" label="命令参数">
          <a-input v-model:value="form.argsStr" placeholder="参数，空格分隔" />
        </a-form-item>
        <a-form-item label="环境变量（JSON）">
          <a-textarea v-model:value="form.envStr" :rows="3" placeholder='{"KEY": "value"}' />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- JSON 批量导入弹窗 -->
    <a-modal v-model:open="jsonImportVisible" title="从 JSON 配置导入连接器" @ok="handleJsonImport" :confirm-loading="jsonImporting" width="600px">
      <div class="json-import-hint">
        支持标准 MCP 配置格式（如 Claude Desktop 的 mcpServers 配置），可一次导入多个连接器：
      </div>
      <a-textarea
        v-model:value="jsonConfig"
        :rows="10"
        placeholder='{&#10;  "mcpServers": {&#10;    "fetch": {&#10;      "type": "sse",&#10;      "url": "https://example.com/mcp/sse"&#10;    },&#10;    "filesystem": {&#10;      "type": "stdio",&#10;      "command": "npx",&#10;      "args": ["-y", "@modelcontextprotocol/server-filesystem"]&#10;    }&#10;  }&#10;}'
        class="json-textarea"
      />
      <div v-if="jsonParseResult" class="json-parse-result" :class="{ success: jsonParseResult.success, error: !jsonParseResult.success }">
        {{ jsonParseResult.message }}
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { SearchOutlined } from '@ant-design/icons-vue'
import { mcpApi, type MCPConnector } from '@/api/mcp'

const loading = ref(false)
const saving = ref(false)
const list = ref<MCPConnector[]>([])
const pagination = ref({ current: 1, pageSize: 20, total: 0, showSizeChanger: true })
const modalVisible = ref(false)
const editingId = ref<number | null>(null)
const form = ref<any>({ name: '', description: '', transport: 'sse', url: '', command: '', argsStr: '', envStr: '' })
const searchKeyword = ref('')
const filterStatus = ref<string>()
const filterTransport = ref<string>()
const jsonImportVisible = ref(false)
const jsonImporting = ref(false)
const jsonConfig = ref('')
const jsonParseResult = ref<{ success: boolean; message: string } | null>(null)

const filteredList = computed(() => {
  let result = list.value
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase()
    result = result.filter(c => c.name.toLowerCase().includes(kw) || (c.description || '').toLowerCase().includes(kw))
  }
  if (filterStatus.value) result = result.filter(c => c.status === filterStatus.value)
  if (filterTransport.value) result = result.filter(c => c.transport === filterTransport.value)
  return result
})

const columns = [
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '传输', dataIndex: 'transport', key: 'transport', width: 100 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 120 },
  { title: '工具数', dataIndex: 'tools_count', key: 'tools_count', width: 80 },
  { title: '最后连接', dataIndex: 'last_connected_at', key: 'last_connected_at', width: 180 },
  { title: '操作', key: 'action', width: 240 },
]

function statusColor(s: string) {
  return { connected: 'green', disconnected: 'default', error: 'red' }[s] || 'default'
}

async function loadData() {
  loading.value = true
  try {
    const res = await mcpApi.list({ page: pagination.value.current, page_size: pagination.value.pageSize })
    list.value = res.items
    pagination.value.total = res.total
  } finally { loading.value = false }
}

function handleSearch() {
  pagination.value.current = 1
}

function handleReset() {
  searchKeyword.value = ''
  filterStatus.value = undefined
  filterTransport.value = undefined
  pagination.value.current = 1
}

async function handleJsonImport() {
  jsonParseResult.value = null
  if (!jsonConfig.value.trim()) {
    jsonParseResult.value = { success: false, message: '请输入 JSON 配置' }
    return
  }
  try {
    const config = JSON.parse(jsonConfig.value)
    const servers = config.mcpServers || config.servers || config
    if (typeof servers !== 'object' || !servers) {
      jsonParseResult.value = { success: false, message: '未找到 mcpServers 配置' }
      return
    }
    jsonImporting.value = true
    let created = 0
    let skipped = 0
    for (const [name, cfg] of Object.entries(servers) as [string, any]) {
      const transport = cfg.type === 'stdio' ? 'stdio' : 'sse'
      const payload: any = {
        name,
        description: cfg.description || `从 JSON 导入的 ${name} 连接器`,
        transport,
        url: cfg.url || '',
        command: cfg.command || '',
        args: cfg.args || [],
        env_vars: cfg.env || cfg.env_vars || {},
      }
      try {
        await mcpApi.create(payload)
        created++
      } catch {
        skipped++
      }
    }
    jsonParseResult.value = {
      success: skipped === 0,
      message: `导入完成：成功 ${created} 个${skipped > 0 ? `，跳过 ${skipped} 个（可能已存在）` : ''}`,
    }
    await loadData()
    if (skipped === 0) {
      jsonImportVisible.value = false
      jsonConfig.value = ''
      jsonParseResult.value = null
    }
  } catch (e: any) {
    jsonParseResult.value = { success: false, message: `JSON 解析失败: ${e.message}` }
  } finally {
    jsonImporting.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.value = { name: '', description: '', transport: 'sse', url: '', command: '', argsStr: '', envStr: '' }
  modalVisible.value = true
}

function openEdit(record: MCPConnector) {
  editingId.value = record.id
  form.value = { ...record, argsStr: (record.args || []).join(' '), envStr: JSON.stringify(record.env_vars || {}, null, 2) }
  modalVisible.value = true
}

async function handleSave() {
  if (!form.value.name) { message.warning('请输入名称'); return }
  saving.value = true
  try {
    const data: any = { ...form.value }
    if (form.value.argsStr) data.args = form.value.argsStr.split(' ').filter(Boolean)
    if (form.value.envStr) { try { data.env_vars = JSON.parse(form.value.envStr) } catch {} }
    if (editingId.value) await mcpApi.update(editingId.value, data)
    else await mcpApi.create(data)
    message.success('保存成功')
    modalVisible.value = false
    loadData()
  } finally { saving.value = false }
}

async function handleConnect(record: MCPConnector) {
  const res = await mcpApi.connect(record.id)
  if (res.success) message.success(`连接成功，获取 ${res.tools_count} 个工具`)
  else message.error(res.message)
  loadData()
}

async function handleDisconnect(record: MCPConnector) {
  await mcpApi.disconnect(record.id)
  message.success('已断开')
  loadData()
}

async function handleDelete(record: MCPConnector) {
  await mcpApi.remove(record.id)
  message.success('删除成功')
  loadData()
}

onMounted(loadData)
</script>

<style scoped>
.mcp-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 18px; }
.header-actions { display: flex; gap: 8px; }
.filter-bar { display: flex; gap: 12px; margin-bottom: 16px; }
.json-import-hint { font-size: 12px; color: #86909c; margin-bottom: 8px; }
.json-textarea { font-family: monospace; font-size: 12px; }
.json-parse-result { margin-top: 8px; padding: 8px 12px; border-radius: 4px; font-size: 13px; }
.json-parse-result.success { background: #f6ffed; color: #52c41a; border: 1px solid #b7eb8f; }
.json-parse-result.error { background: #fff2f0; color: #ff4d4f; border: 1px solid #ffccc7; }
</style>
