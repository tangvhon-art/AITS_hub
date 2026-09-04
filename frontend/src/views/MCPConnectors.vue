<template>
  <div class="mcp-page">
    <PageHeader title="MCP 连接器管理">
      <template #extra>
        <a-button @click="jsonImportVisible = true">从 JSON 导入</a-button>
        <a-button type="primary" @click="openCreate()">新建连接器</a-button>
      </template>
    </PageHeader>

    <a-card>
      <SearchBar @search="handleSearch" @reset="handleReset">
      <a-form layout="inline">
        <a-form-item label="关键词">
          <a-input
            v-model:value="searchKeyword"
            placeholder="搜索名称/描述"
            allow-clear
            style="width: 220px"
          >
            <template #prefix><SearchOutlined /></template>
          </a-input>
        </a-form-item>
        <a-form-item label="状态">
          <a-select v-model:value="filterStatus" placeholder="全部状态" allow-clear style="width: 130px">
            <a-select-option value="connected">已连接</a-select-option>
            <a-select-option value="disconnected">未连接</a-select-option>
            <a-select-option value="error">错误</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="传输方式">
          <a-select v-model:value="filterTransport" placeholder="全部传输方式" allow-clear style="width: 130px">
            <a-select-option value="sse">SSE</a-select-option>
            <a-select-option value="stdio">stdio</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </SearchBar>

    <DataTable
      :columns="columns"
      :data-source="list"
      :loading="loading"
      row-key="id"
      @change="handleTableChange"
    >
        :page="pagination.current"
        :page-size="pagination.pageSize"
        :total="pagination.total"
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
          <a-button type="link" size="small" @click="openEditWithFields(record.id, record)">编辑</a-button>
          <a-button type="link" size="small" danger @click="handleDelete(record.id, record.name, record)">删除</a-button>
        </template>
      </template>
    </DataTable>
    </a-card>

    <!-- 新建/编辑弹窗 -->
    <FormModal
      v-model:visible="modalVisible"
      :title="editingId ? '编辑连接器' : '新建连接器'"
      :loading="modalLoading"
      @ok="submit"
    >
      <a-form-item label="名称" required>
        <a-input v-model:value="formData.name" placeholder="连接器名称" />
      </a-form-item>
      <a-form-item label="描述">
        <a-textarea v-model:value="formData.description" :rows="2" />
      </a-form-item>
      <a-form-item label="传输方式" required>
        <a-select v-model:value="formData.transport">
          <a-select-option value="sse">SSE（HTTP）</a-select-option>
          <a-select-option value="stdio">stdio（本地命令）</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item v-if="formData.transport === 'sse'" label="服务地址" required>
        <a-input v-model:value="formData.url" placeholder="https://example.com/mcp" />
      </a-form-item>
      <a-form-item v-if="formData.transport === 'stdio'" label="启动命令" required>
        <a-input v-model:value="formData.command" placeholder="npx -y @modelcontextprotocol/server-filesystem" />
      </a-form-item>
      <a-form-item v-if="formData.transport === 'stdio'" label="命令参数">
        <a-input v-model:value="formData.argsStr" placeholder="参数，空格分隔" />
      </a-form-item>
      <a-form-item label="环境变量（JSON）">
        <a-textarea v-model:value="formData.envStr" :rows="3" placeholder='{"KEY": "value"}' />
      </a-form-item>
    </FormModal>

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
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { SearchOutlined } from '@ant-design/icons-vue'
import { mcpApi, type MCPConnector } from '@/api/mcp'
import PageHeader from '@/components/PageHeader.vue'
import SearchBar from '@/components/SearchBar.vue'
import DataTable from '@/components/DataTable.vue'
import FormModal from '@/components/FormModal.vue'
import { useList } from '@/composables/useList'
import { useCRUD } from '@/composables/useCRUD'

const searchKeyword = ref('')
const filterStatus = ref<string>()
const filterTransport = ref<string>()
const jsonImportVisible = ref(false)
const jsonImporting = ref(false)
const jsonConfig = ref('')
const jsonParseResult = ref<{ success: boolean; message: string } | null>(null)

// ── 服务端分页列表（useList + DataTable）──
const {
  loading,
  list,
  total,
  pagination,
  loadData,
  handleTableChange,
} = useList<MCPConnector>(
  (params) =>
    mcpApi.list({
      page: params.page,
      page_size: params.page_size,
      status: filterStatus.value,
      keyword: searchKeyword.value || undefined,
    }),
)

/** 搜索：回到第一页再加载 */
function handleSearch() {
  pagination.current = 1
  loadData()
}

/** 重置筛选并回到第一页 */
function handleReset() {
  searchKeyword.value = ''
  filterStatus.value = undefined
  filterTransport.value = undefined
  pagination.current = 1
  loadData()
}

// ── 新增/编辑/删除（useCRUD + FormModal）──
const {
  modalVisible,
  modalLoading,
  editingId,
  formData,
  openCreate,
  openEdit,
  submit,
  handleDelete,
} = useCRUD<MCPConnector>({
  api: {
    create: (data) => mcpApi.create(data),
    update: (id, data) => mcpApi.update(id, data),
    remove: (id) => mcpApi.remove(id),
  },
  resourceName: '连接器',
  onSuccess: loadData,
  beforeSubmit: () => {
    if (!formData.name?.trim()) {
      message.warning('请输入名称')
      return false
    }
    if (!formData.transport) {
      message.warning('请选择传输方式')
      return false
    }
    if (formData.transport === 'sse' && !formData.url?.trim()) {
      message.warning('请输入服务地址')
      return false
    }
    if (formData.transport === 'stdio' && !formData.command?.trim()) {
      message.warning('请输入启动命令')
      return false
    }
    return true
  },
})

/** 编辑：展开数组/对象字段为可编辑字符串 */
function openEditWithFields(id: number, record: MCPConnector) {
  openEdit(id, {
    ...record,
    argsStr: (record.args || []).join(' '),
    envStr: JSON.stringify(record.env_vars || {}, null, 2),
  })
}

const columns = [
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '传输', dataIndex: 'transport', key: 'transport', width: 100 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 120 },
  { title: '工具数', dataIndex: 'tools_count', key: 'tools_count', width: 80 },
  { title: '最后连接', dataIndex: 'last_connected_at', key: 'last_connected_at', width: 180 },
  { title: '操作', key: 'action', width: 260 },
]

function statusColor(s: string) {
  return { connected: 'green', disconnected: 'default', error: 'red' }[s] || 'default'
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
      // 识别传输方式：显式 type=stdio，或有 command 字段则为 stdio
      const transport = (cfg.type === 'stdio' || cfg.command) ? 'stdio' : 'sse'
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
</script>

<style scoped>
.mcp-page { padding: 20px; }
.json-import-hint { font-size: 12px; color: #86909c; margin-bottom: 8px; }
.json-textarea { font-family: monospace; font-size: 12px; }
.json-parse-result { margin-top: 8px; padding: 8px 12px; border-radius: 4px; font-size: 13px; }
.json-parse-result.success { background: #f6ffed; color: #52c41a; border: 1px solid #b7eb8f; }
.json-parse-result.error { background: #fff2f0; color: #ff4d4f; border: 1px solid #ffccc7; }
</style>
