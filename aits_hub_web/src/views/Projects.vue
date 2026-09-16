<template>
  <div class="page-container">
    <PageHeader title="项目管理">
      <template #extra>
        <a-button type="primary" @click="openCreate()">
          <template #icon>
            <PlusOutlined />
          </template>
          新建项目
        </a-button>
      </template>
    </PageHeader>

    <a-card>
      <SearchBar @search="handleSearch" @reset="handleReset">
      <a-form-item label="关键词">
        <a-input v-model:value="searchKeyword" placeholder="搜索项目名称/描述" allow-clear style="width: 220px" />
      </a-form-item>
    </SearchBar>

    <a-spin :spinning="loading">
      <a-row :gutter="[24, 24]">
        <a-col :xs="24" :sm="12" :lg="8" :xl="6" v-for="project in pagedProjects" :key="project.id">
          <a-card class="project-card" hoverable>
            <div class="project-icon" @click="enterProject(project)">
              <FolderOutlined :style="{ fontSize: '32px', color: '#1677ff' }" />
            </div>
            <h3 @click="enterProject(project)">{{ project.name }}</h3>
            <p class="project-desc">{{ project.description || '暂无描述' }}</p>
            <div class="project-meta">
              <CalendarOutlined />
              <span>创建于 {{ formatDate(project.created_at) }}</span>
            </div>
            <div class="project-quick-actions">
              <a-button size="small" type="link" @click="goToPage(project, 'requirements')">
                <template #icon><FileTextOutlined /></template>
                需求
              </a-button>
              <a-button size="small" type="link" @click="goToPage(project, 'cases')">
                <template #icon><UnorderedListOutlined /></template>
                用例
              </a-button>
              <a-button size="small" type="link" @click="goToPage(project, 'execution')">
                <template #icon><PlayCircleOutlined /></template>
                执行
              </a-button>
            </div>
            <div class="project-actions">
              <a-button size="small" @click.stop="openEdit(project.id, project)">编辑</a-button>
              <a-button size="small" danger @click.stop="handleDelete(project.id, project.name, project)">删除</a-button>
            </div>
          </a-card>
        </a-col>

        <a-col :span="24" v-if="list.length === 0 && !loading">
          <a-empty description="暂无项目，点击右上角创建" />
        </a-col>
      </a-row>

      <div class="pagination-wrapper" v-if="list.length > 0">
        <a-pagination
          v-model:current="currentPage"
          v-model:pageSize="pageSize"
          :total="list.length"
          :page-size-options="['12', '24', '48']"
          show-size-changer
          show-quick-jumper
          :show-total="(total: number) => `共 ${total} 个项目`"
        />
      </div>
    </a-spin>
    </a-card>

    <!-- 创建/编辑项目对话框 -->
    <FormModal
      v-model:visible="modalVisible"
      :title="editingId ? '编辑项目' : '新建项目'"
      :loading="modalLoading"
      @ok="submit"
    >
      <a-form-item label="项目名称" required>
        <a-input v-model:value="formData.name" placeholder="请输入项目名称" />
      </a-form-item>
      <a-form-item label="项目描述">
        <a-textarea
          v-model:value="formData.description"
          :rows="3"
          placeholder="请输入项目描述"
        />
      </a-form-item>
    </FormModal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined, FolderOutlined, CalendarOutlined, FileTextOutlined, UnorderedListOutlined, PlayCircleOutlined } from '@ant-design/icons-vue'
import { getProjects, createProject, updateProject, deleteProject, Project } from '@/api/projects'
import { formatDate } from '@/utils/date'
import PageHeader from '@/components/PageHeader.vue'
import SearchBar from '@/components/SearchBar.vue'
import FormModal from '@/components/FormModal.vue'
import { useList } from '@/composables/useList'
import { useCRUD } from '@/composables/useCRUD'

const router = useRouter()
const searchKeyword = ref('')
const currentPage = ref(1)
const pageSize = ref(12)

// ── 列表（项目为全量接口，包装为 useList 统一形态）──
const { loading, list, loadData } = useList<Project>(
  async (params) => {
    const data = await getProjects()
    localStorage.setItem('projects', JSON.stringify(data))
    return { items: data, total: data.length, page: params.page, page_size: params.page_size }
  },
)

// 搜索条件变化时重置到第一页
watch(searchKeyword, () => {
  currentPage.value = 1
})

const filteredProjects = computed(() => {
  if (!searchKeyword.value) return list.value
  const kw = searchKeyword.value.toLowerCase()
  return list.value.filter(p =>
    p.name?.toLowerCase().includes(kw) ||
    p.description?.toLowerCase().includes(kw)
  )
})

const pagedProjects = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredProjects.value.slice(start, start + pageSize.value)
})

function handleSearch() {}

function handleReset() {
  searchKeyword.value = ''
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
} = useCRUD<Project>({
  api: {
    create: (data) => createProject({ name: data.name, description: data.description }),
    update: (id, data) => updateProject(id, { name: data.name, description: data.description }),
    remove: (id) => deleteProject(id),
  },
  resourceName: '项目',
  onSuccess: loadData,
  beforeSubmit: () => {
    if (!formData.name?.trim()) {
      message.warning('请输入项目名称')
      return false
    }
    return true
  },
})

function enterProject(project: Project) {
  router.push(`/projects/${project.id}/cases`)
}

function goToPage(project: Project, page: string) {
  router.push(`/projects/${project.id}/${page}`)
}
</script>

<style scoped>
.project-card {
  cursor: pointer;
  transition: all 0.2s;
}

.project-card :deep(.ant-card-body) {
  padding: 24px;
}

.project-icon {
  margin-bottom: 16px;
}

.project-card h3 {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.88);
}

.project-desc {
  color: rgba(0, 0, 0, 0.45);
  font-size: 14px;
  min-height: 42px;
  margin-bottom: 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.project-meta {
  color: rgba(0, 0, 0, 0.25);
  font-size: 12px;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.project-quick-actions {
  display: flex;
  gap: 4px;
  margin-bottom: 12px;
  padding: 8px 0;
  border-top: 1px solid #f0f0f0;
  border-bottom: 1px solid #f0f0f0;
}

.project-quick-actions .ant-btn {
  flex: 1;
  padding: 0 4px;
  font-size: 12px;
}

.project-actions {
  display: flex;
  gap: 8px;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 24px;
}
</style>
