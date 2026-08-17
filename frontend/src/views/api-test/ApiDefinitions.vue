<template>
  <div class="api-definitions">
    <!-- 左侧分组树 -->
    <div class="module-sidebar">
      <div class="sidebar-header">
        <span class="sidebar-title">接口分组</span>
        <a-button type="text" size="small" @click="handleAddRootGroup">
          <template #icon><PlusOutlined /></template>
        </a-button>
      </div>
      <div class="module-tree-wrap">
        <div
          class="tree-node-item"
          :class="{ active: selectedModuleId === undefined }"
          @click="selectModule(undefined)"
        >
          <span class="expand-icon placeholder"></span>
          <FolderOutlined style="color: #faad14; margin-right: 6px" />
          <span class="node-name">全部接口</span>
          <span class="node-count">{{ pagination.total }}</span>
        </div>
        <template v-for="node in moduleTree" :key="node.id">
          <ModuleTreeNode
            :node="node"
            :selected-id="selectedModuleId"
            @select="selectModule"
            @add-child="handleAddChildGroup"
            @rename="handleRenameGroup"
            @delete-group="handleDeleteGroup"
          />
        </template>
        <div v-if="moduleTree.length === 0" class="empty-tip">暂无分组，点击上方 + 创建</div>
      </div>
    </div>

    <!-- 右侧接口列表 -->
    <div class="api-list-area">
      <div class="list-header">
        <div class="list-title">
          <span>{{ currentModuleName }}</span>
        </div>
        <div class="header-actions">
          <a-button @click="showImportModal = true">
            <template #icon><ImportOutlined /></template>
            导入接口
          </a-button>
          <a-button type="primary" @click="handleCreate">
            <template #icon><PlusOutlined /></template>
            新建接口
          </a-button>
        </div>
      </div>

      <div class="filter-bar">
        <a-input-search
          v-model:value="keyword"
          placeholder="搜索接口名称或路径"
          style="width: 280px"
          @search="loadData"
        />
        <a-select v-model:value="methodFilter" placeholder="请求方法" style="width: 120px" allow-clear>
          <a-select-option value="GET">GET</a-select-option>
          <a-select-option value="POST">POST</a-select-option>
          <a-select-option value="PUT">PUT</a-select-option>
          <a-select-option value="DELETE">DELETE</a-select-option>
        </a-select>
        <a-space>
          <a-button type="primary" @click="loadData">查询</a-button>
          <a-button @click="handleReset">重置</a-button>
        </a-space>
      </div>

      <a-table
        :columns="columns"
        :data-source="dataSource"
        :loading="loading"
        :pagination="pagination"
        @change="handleTableChange"
        row-key="id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'method'">
            <a-tag :color="getMethodColor(record.method)">{{ record.method }}</a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space>
              <a-button type="link" size="small" @click="handleDebug(record)">调试</a-button>
              <a-button type="link" size="small" @click="handleEdit(record)">编辑</a-button>
              <a-popconfirm title="确定删除该接口？" @confirm="handleDelete(record)">
                <a-button type="link" size="small" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </div>

    <!-- 分组弹窗（新建/重命名） -->
    <a-modal v-model:open="showGroupModal" :title="groupModalTitle" @ok="saveGroup" :confirm-loading="groupSaving">
      <a-form layout="vertical">
        <a-form-item label="分组名称" required>
          <a-input v-model:value="groupForm.name" placeholder="输入分组名称" @pressEnter="saveGroup" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 导入弹窗 -->
    <a-modal v-model:open="showImportModal" title="导入接口" width="600px">
      <a-form layout="vertical">
        <a-form-item label="导入格式">
          <a-select v-model:value="importType" style="width: 100%" placeholder="选择导入格式">
            <a-select-option value="swagger">Swagger / OpenAPI</a-select-option>
            <a-select-option value="postman">Postman Collection</a-select-option>
            <a-select-option value="jmeter">JMeter</a-select-option>
            <a-select-option value="har">HAR 文件</a-select-option>
            <a-select-option value="apifox">Apifox</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="选择文件">
          <a-upload :before-upload="handleBeforeUpload" :show-upload-list="false" accept=".json,.yaml,.yml,.jmx,.har">
            <a-button>
              <template #icon><UploadOutlined /></template>
              点击选择文件
            </a-button>
            <span v-if="importFileName" style="margin-left: 8px">{{ importFileName }}</span>
          </a-upload>
        </a-form-item>
      </a-form>
      <template #footer>
        <a-button @click="showImportModal = false">取消</a-button>
        <a-button type="primary" :loading="importing" @click="handleImport">开始导入</a-button>
      </template>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, defineComponent, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import {
  PlusOutlined, ImportOutlined, UploadOutlined,
  FolderOutlined,
  EditOutlined, DeleteOutlined, MoreOutlined,
} from '@ant-design/icons-vue'
import { apiDefinitionsApi, apiModulesApi, apiImportApi, type ApiDefinition, type ApiModule } from '@/api/apiTest'
import { useUrlSearch } from '@/composables/useUrlSearch'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)
const { loadFromUrl, syncToUrl } = useUrlSearch()

// ====== 接口列表 ======
const loading = ref(false)
const keyword = ref('')
const methodFilter = ref('')
const dataSource = ref<ApiDefinition[]>([])
const pagination = ref({ current: 1, pageSize: 20, total: 0 })

const showImportModal = ref(false)
const importType = ref('swagger')
const importFile = ref<File | null>(null)
const importFileName = ref('')
const importing = ref(false)

// ====== 分组树 ======
const moduleTree = ref<ApiModule[]>([])
const selectedModuleId = ref<number | undefined>(undefined)

// ====== 分组弹窗 ======
const showGroupModal = ref(false)
const groupSaving = ref(false)
const groupForm = ref({ name: '' })
const groupMode = ref<'add-root' | 'add-child' | 'rename'>('add-root')
const groupTargetId = ref<number | null>(null)

const groupModalTitle = computed(() => {
  if (groupMode.value === 'rename') return '重命名分组'
  return '新建分组'
})

const currentModuleName = computed(() => {
  if (selectedModuleId.value === undefined) return '全部接口'
  const find = (nodes: ApiModule[]): string => {
    for (const n of nodes) {
      if (n.id === selectedModuleId.value) return n.name
      if (n.children) {
        const found = find(n.children)
        if (found) return found
      }
    }
    return ''
  }
  return find(moduleTree.value) || '全部接口'
})

const columns = [
  { title: '方法', key: 'method', width: 80 },
  { title: '接口名称', dataIndex: 'name', key: 'name' },
  { title: '路径', dataIndex: 'path', key: 'path' },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '状态', dataIndex: 'status', key: 'status', width: 80 },
  { title: '操作', key: 'action', width: 180 },
]

const getMethodColor = (method: string) => {
  const colors: Record<string, string> = {
    GET: 'green', POST: 'blue', PUT: 'orange', DELETE: 'red', PATCH: 'purple'
  }
  return colors[method] || 'default'
}

// ====== 数据加载 ======
const loadData = async () => {
  syncToUrl({ keyword: keyword.value, method: methodFilter.value })
  loading.value = true
  try {
    const res = await apiDefinitionsApi.list(projectId, {
      page: pagination.value.current,
      page_size: pagination.value.pageSize,
      keyword: keyword.value,
      method: methodFilter.value,
      module_id: selectedModuleId.value,
    })
    dataSource.value = res.items
    pagination.value.total = res.total
  } finally {
    loading.value = false
  }
}

const loadModules = async () => {
  try {
    moduleTree.value = await apiModulesApi.getTree(projectId)
  } catch {
    moduleTree.value = []
  }
}

const handleTableChange = (pag: any) => {
  pagination.value.current = pag.current
  pagination.value.pageSize = pag.pageSize
  loadData()
}

function handleReset() {
  keyword.value = ''
  methodFilter.value = ''
  pagination.value.current = 1
  loadData()
}

// ====== 分组操作 ======
function selectModule(moduleId: number | undefined) {
  selectedModuleId.value = moduleId
  pagination.value.current = 1
  loadData()
}

function handleAddRootGroup() {
  groupMode.value = 'add-root'
  groupTargetId.value = null
  groupForm.value = { name: '' }
  showGroupModal.value = true
}

function handleAddChildGroup(parentId: number) {
  groupMode.value = 'add-child'
  groupTargetId.value = parentId
  groupForm.value = { name: '' }
  showGroupModal.value = true
}

function handleRenameGroup(id: number, currentName: string) {
  groupMode.value = 'rename'
  groupTargetId.value = id
  groupForm.value = { name: currentName }
  showGroupModal.value = true
}

async function saveGroup() {
  if (!groupForm.value.name) {
    message.warning('请输入分组名称')
    return
  }
  groupSaving.value = true
  try {
    if (groupMode.value === 'rename' && groupTargetId.value) {
      await apiModulesApi.update(projectId, groupTargetId.value, { name: groupForm.value.name })
      message.success('重命名成功')
    } else {
      await apiModulesApi.create(projectId, {
        name: groupForm.value.name,
        parent_id: groupMode.value === 'add-child' ? groupTargetId.value : null,
        sort_order: 0,
      })
      message.success('分组创建成功')
    }
    showGroupModal.value = false
    await loadModules()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '操作失败')
  } finally {
    groupSaving.value = false
  }
}

async function handleDeleteGroup(id: number) {
  // 检查分组下是否有接口
  try {
    const res = await apiDefinitionsApi.list(projectId, { module_id: id, page_size: 1 })
    if (res.total > 0) {
      message.warning(`该分组下有 ${res.total} 个接口，请先移除或移动接口后再删除`)
      return
    }
  } catch {
    // 检查失败时仍然阻止删除
    message.warning('无法检查分组内容，请刷新后重试')
    return
  }

  // 二次确认
  Modal.confirm({
    title: '确认删除分组',
    content: '确定要删除该分组吗？此操作不可撤销。',
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    async onOk() {
      try {
        await apiModulesApi.delete(projectId, id)
        message.success('分组已删除')
        if (selectedModuleId.value === id) {
          selectedModuleId.value = undefined
        }
        await loadModules()
        await loadData()
      } catch (e: any) {
        message.error(e.response?.data?.detail || '删除失败')
      }
    },
  })
}

// ====== 接口操作 ======
const handleCreate = () => {
  const query: Record<string, any> = {}
  if (selectedModuleId.value) query.module_id = selectedModuleId.value
  router.push({ path: `/projects/${projectId}/api-test/definitions/new`, query })
}

const handleEdit = (record: ApiDefinition) => {
  router.push(`/projects/${projectId}/api-test/definitions/${record.id}`)
}

const handleDebug = (record: ApiDefinition) => {
  router.push({
    path: `/projects/${projectId}/api-test/debug`,
    query: { api_id: record.id }
  })
}

const handleDelete = async (record: ApiDefinition) => {
  await apiDefinitionsApi.delete(projectId, record.id)
  message.success('删除成功')
  loadData()
}

// ====== 导入 ======
const handleBeforeUpload = (file: File) => {
  importFile.value = file
  importFileName.value = file.name
  return false
}

const handleImport = async () => {
  if (!importFile.value) {
    message.warning('请选择文件')
    return
  }
  importing.value = true
  try {
    const formData = new FormData()
    formData.append('file', importFile.value)
    formData.append('import_type', importType.value)
    await apiImportApi.import(projectId, formData)
    message.success('导入成功')
    showImportModal.value = false
    loadData()
  } finally {
    importing.value = false
  }
}

// ====== 树节点组件 ======
const ModuleTreeNode = defineComponent({
  name: 'ModuleTreeNode',
  props: {
    node: { type: Object, required: true },
    selectedId: { type: Number, default: null },
    depth: { type: Number, default: 0 },
  },
  emits: ['select', 'add-child', 'rename', 'delete-group'],
  setup(props, { emit }) {
    const showActions = ref(false)
    const expanded = ref(true)

    return () => {
      const node = props.node as any
      const isActive = props.selectedId === node.id
      const children = node.children || []

      return h('div', { class: 'module-node-group' }, [
        h('div', {
          class: ['tree-node-item', { active: isActive }],
          style: { paddingLeft: `${12 + props.depth * 16}px` },
          onClick: () => emit('select', node.id),
          onMouseenter: () => { showActions.value = true },
          onMouseleave: () => { showActions.value = false },
        }, [
          children.length > 0
            ? h('span', {
                class: 'expand-icon',
                onClick: (e: Event) => { e.stopPropagation(); expanded.value = !expanded.value },
              }, expanded.value ? '▾' : '▸')
            : h('span', { class: 'expand-icon placeholder' }),
          h(FolderOutlined, { style: { color: '#faad14', marginRight: '6px' } }),
          h('span', { class: 'node-name' }, node.name),
          showActions.value
            ? h('span', { class: ['node-actions', { 'actions-active': isActive }] }, [
                h('span', {
                  class: 'action-btn',
                  title: '新建子分组',
                  onClick: (e: Event) => { e.stopPropagation(); emit('add-child', node.id) },
                }, [h(PlusOutlined)]),
                h('span', {
                  class: 'action-btn',
                  title: '重命名',
                  onClick: (e: Event) => { e.stopPropagation(); emit('rename', node.id, node.name) },
                }, [h(EditOutlined)]),
                h('span', {
                  class: 'action-btn danger',
                  title: '删除分组',
                  onClick: (e: Event) => { e.stopPropagation(); emit('delete-group', node.id) },
                }, [h(DeleteOutlined)]),
              ])
            : null,
        ]),
        expanded.value && children.length > 0
          ? children.map((child: any) =>
              h(ModuleTreeNode, {
                key: child.id,
                node: child,
                selectedId: props.selectedId,
                depth: props.depth + 1,
                onSelect: (id: number) => emit('select', id),
                onAddChild: (id: number) => emit('add-child', id),
                onRename: (id: number, name: string) => emit('rename', id, name),
                onDeleteGroup: (id: number) => emit('delete-group', id),
              })
            )
          : null,
      ])
    }
  },
})

onMounted(() => {
  const params = loadFromUrl({ keyword: '', method: '' })
  keyword.value = params.keyword
  methodFilter.value = params.method
  loadModules()
  loadData()
})
</script>

<style scoped>
.api-definitions {
  display: flex;
  height: 100%;
  gap: 0;
  background: #fff;
}

/* 左侧分组树 */
.module-sidebar {
  width: 240px;
  min-width: 240px;
  border-right: 1px solid #f0f0f0;
  display: flex;
  flex-direction: column;
  background: #fafafa;
}
.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
}
.sidebar-title {
  font-size: 14px;
  font-weight: 600;
  color: #262626;
}
.module-tree-wrap {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}
.empty-tip {
  padding: 24px 16px;
  color: #bfbfbf;
  font-size: 12px;
  text-align: center;
}

/* 树节点 */
.tree-node-item {
  display: flex;
  align-items: center;
  padding: 6px 12px 6px 0;
  cursor: pointer;
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
  transition: all 0.15s;
  position: relative;
  user-select: none;
  border-radius: 4px;
  margin: 1px 4px;
}
.tree-node-item:hover {
  background: #f0f5ff;
}
.tree-node-item.active {
  background: #e6f4ff;
  color: #1677ff;
  font-weight: 500;
}
.module-node-group {
  position: relative;
}
.module-node-group::before {
  content: '';
  position: absolute;
  left: 20px;
  top: 0;
  bottom: 0;
  width: 1px;
  background: #e8e8e8;
}
.module-node-group > .tree-node-item::before {
  content: '';
  position: absolute;
  left: 20px;
  top: 50%;
  width: 8px;
  height: 1px;
  background: #e8e8e8;
}
.expand-icon {
  width: 18px;
  height: 18px;
  font-size: 10px;
  color: #8c8c8c;
  cursor: pointer;
  text-align: center;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 2px;
  transition: all 0.15s;
  z-index: 1;
  background: #fafafa;
}
.expand-icon:hover {
  background: #e6f4ff;
  color: #1677ff;
}
.expand-icon.placeholder {
  width: 18px;
  background: transparent;
}
.node-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-left: 4px;
}
.node-count {
  font-size: 11px;
  color: #bfbfbf;
  margin-left: auto;
  flex-shrink: 0;
  background: #f0f0f0;
  padding: 0 6px;
  border-radius: 8px;
  min-width: 18px;
  text-align: center;
}
.node-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-left: auto;
  flex-shrink: 0;
  padding-left: 8px;
  opacity: 0;
  transition: opacity 0.15s;
}
.tree-node-item:hover .node-actions {
  opacity: 1;
}
.node-actions.actions-active {
  opacity: 1;
}
.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 4px;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
  cursor: pointer;
  transition: all 0.15s;
}
.action-btn:hover {
  background: #fff;
  color: #1677ff;
  box-shadow: 0 1px 2px rgba(0,0,0,0.1);
}
.action-btn.danger:hover {
  background: #fff1f0;
  color: #ff4d4f;
}

/* 右侧接口列表 */
.api-list-area {
  flex: 1;
  padding: 20px 24px;
  overflow-y: auto;
  min-width: 0;
}
.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.list-title {
  font-size: 18px;
  font-weight: 600;
  color: #262626;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
</style>
