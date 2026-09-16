<template>
  <!--
    ═══════════════════════════════════════════════════════════════════════
    标准管理页模板（五件套 + useList/useCRUD + 服务端分页）

    用途：新建"列表 + 新增/编辑弹窗 + 删除"类管理页面时，复制本文件到
          src/views/ 下改名使用，按下方 TODO 标记替换即可。

    组成：
      PageHeader    → 页面标题 + 操作区
      SearchBar     → 搜索筛选栏（默认槽放筛选控件，extra 槽放额外按钮）
      DataTable     → 服务端分页表格（emit change(page, pageSize)）
      FormModal     → 新增/编辑弹窗（v-model:visible + @ok）
      useList       → 分页/加载/筛选逻辑
      useCRUD       → 弹窗状态/提交/统一删除确认（Modal.confirm）

    后端配套：
      - 资源 API 用 BaseAPI 实例化（项目级/全局）
      - 后端标准路由用 core/base_router.ResourceRouter 组装（统一响应 + 分页 + 审计）
      - 列表接口返回 { items, total, page, page_size }（分页模式）
    ═══════════════════════════════════════════════════════════════════════
  -->
  <div class="manage-page">
    <!-- ① 页面头部 -->
    <PageHeader title="资源管理">
      <template #extra>
        <!-- TODO: 页面级操作按钮，如"批量导入""初始化" -->
        <a-button @click="handleCustomAction">辅助操作</a-button>
        <a-button type="primary" @click="openCreate(defaultForm)">
          <template #icon><PlusOutlined /></template>
          新建资源
        </a-button>
      </template>
    </PageHeader>

    <!-- ② 搜索筛选栏 -->
    <SearchBar @search="handleSearch" @reset="handleReset">
      <!-- 筛选控件直接绑定 useList 的 filters（类型 unknown，需 as 转换或改用本地 ref） -->
      <a-form layout="inline">
        <a-form-item label="关键词">
          <a-input v-model:value="filterKeyword" placeholder="搜索名称" allow-clear style="width: 200px" @keyup.enter="handleSearch" />
        </a-form-item>
        <a-form-item label="状态">
          <a-select v-model:value="filterStatus" allow-clear placeholder="全部状态" style="width: 150px">
            <a-select-option value="active">启用</a-select-option>
            <a-select-option value="disabled">停用</a-select-option>
          </a-select>
        </a-form-item>
        <!-- 可选：SearchBar extra 槽放快捷按钮 -->
      </a-form>
    </SearchBar>

    <!-- ③ 服务端分页表格 -->
    <DataTable
      :columns="columns"
      :data-source="list"
      :loading="loading"
      :page="pagination.current"
      :page-size="pagination.pageSize"
      :total="total"
      @change="onTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <!-- 枚举 → 中文标签（可升级为 StatusTag 组件） -->
          <a-tag :color="record.status === 'active' ? 'green' : 'default'">
            {{ record.status === 'active' ? '启用' : '停用' }}
          </a-tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-button type="link" size="small" @click="openEdit(record.id, record)">编辑</a-button>
          <a-button type="link" size="small" danger @click="handleDelete(record.id, record.name)">删除</a-button>
        </template>
      </template>
    </DataTable>

    <!-- ④ 新增/编辑弹窗 -->
    <FormModal
      v-model:visible="modalVisible"
      :title="editingId ? '编辑资源' : '新建资源'"
      :loading="modalLoading"
      :model="formData"
      width="600px"
      ok-text="确定"
      cancel-text="取消"
      @ok="submit"
    >
      <!-- TODO: 表单字段，直接绑定 formData.xxx -->
      <a-form-item label="名称" required>
        <a-input v-model:value="formData.name" placeholder="请输入名称" />
      </a-form-item>
      <a-form-item label="状态">
        <a-switch v-model:checked="formData.status" checked-value="active" un-checked-value="disabled" />
      </a-form-item>
    </FormModal>
  </div>
</template>

<script setup lang="ts">
/**
 * 标准管理页脚本骨架
 *
 * 使用步骤（替换 TODO）：
 * 1. 改资源类型与 API：import { xxxApi, type Xxx, type XxxCreate } from '@/api/xxx'
 * 2. 列表 fetch 函数返回 { items, total }（分页模式）
 * 3. useCRUD api 对象提供 create/update/remove 三个方法（签名已统一）
 * 4. columns 按资源字段定义，bodyCell 插槽渲染自定义列
 */
import { ref } from 'vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import SearchBar from '@/components/SearchBar.vue'
import DataTable from '@/components/DataTable.vue'
import FormModal from '@/components/FormModal.vue'
import { useList } from '@/composables/useList'
import { useCRUD } from '@/composables/useCRUD'
// TODO: 替换为真实资源 API
// import { versionApi } from '@/api/projectVersions'
// import type { ProjectVersion } from '@/api/projectVersions'

// ── 筛选条件（本地 ref，类型安全；useList 的 filters 为 Record<string, unknown>）──
const filterKeyword = ref('')
const filterStatus = ref<string>()

// ── 服务端分页列表 ──
// TODO: 替换 fetchFn：xxxApi.list(projectId, { ... }) 或 xxxApi.listGlobal({ ... })
const {
  loading,
  list,
  total,
  pagination,
  loadData,
} = useList<any>(
  (params) =>
    // 示例：项目级资源
    // versionApi.list(projectId, {
    //   keyword: filterKeyword.value,
    //   status: filterStatus.value,
    //   page: params.page,
    //   page_size: params.page_size,
    // })
    Promise.resolve({ items: [], total: 0 }),
)

/** 搜索：回到第一页再加载 */
function handleSearch() {
  pagination.current = 1
  loadData()
}

/** 重置筛选并回到第一页 */
function handleReset() {
  filterKeyword.value = ''
  filterStatus.value = undefined
  pagination.current = 1
  loadData()
}

/** DataTable change 适配（emit page, pageSize 两个数字参数） */
function onTableChange(page: number, pageSize: number) {
  pagination.current = page
  pagination.pageSize = pageSize
  loadData()
}

// ── 新增/编辑/删除 ──
// TODO: 默认表单值
const defaultForm: Record<string, any> = {
  name: '',
  status: 'active',
}

const {
  modalVisible,
  modalLoading,
  editingId,
  formData,
  openCreate,
  openEdit,
  submit,
  handleDelete,
} = useCRUD<any>({
  api: {
    // TODO: 替换为真实 API（项目级：xxxApi.create(projectId, data)；全局：createGlobal）
    create: () => Promise.resolve(),
    update: () => Promise.resolve(),
    remove: () => Promise.resolve(),
  },
  resourceName: '资源',
  onSuccess: loadData,
  beforeSubmit: () => {
    // TODO: 表单校验，返回 false 阻止提交
    if (!formData.name?.trim()) {
      // message.warning('请输入名称')
      return false
    }
    return true
  },
})

// TODO: 表格列定义
const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '状态', key: 'status', width: 100 },
  { title: '操作', key: 'action', width: 140 },
]

/** 页面级辅助操作 */
function handleCustomAction() {
  // TODO: 辅助操作逻辑
}
</script>

<style scoped>
.manage-page {
  padding: 0;
}
</style>
