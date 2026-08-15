<template>
  <div class="page-container">
    <div class="page-header">
      <h2>项目管理</h2>
      <a-button type="primary" @click="showCreateModal = true">
        <template #icon>
          <PlusOutlined />
        </template>
        新建项目
      </a-button>
    </div>

    <a-spin :spinning="loading">
      <a-row :gutter="[24, 24]">
        <a-col :xs="24" :sm="12" :lg="8" :xl="6" v-for="project in projects" :key="project.id">
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
              <a-button size="small" @click.stop="editProject(project)">编辑</a-button>
              <a-button size="small" danger @click.stop="deleteProject(project)">删除</a-button>
            </div>
          </a-card>
        </a-col>

        <a-col :span="24" v-if="projects.length === 0 && !loading">
          <a-empty description="暂无项目，点击右上角创建" />
        </a-col>
      </a-row>
    </a-spin>

    <!-- 创建/编辑项目对话框 -->
    <a-modal
      v-model:open="showCreateModal"
      :title="editingProject ? '编辑项目' : '新建项目'"
      @ok="saveProject"
      :confirm-loading="saving"
    >
      <a-form layout="vertical">
        <a-form-item label="项目名称" required>
          <a-input v-model:value="projectForm.name" placeholder="请输入项目名称" />
        </a-form-item>
        <a-form-item label="项目描述">
          <a-textarea
            v-model:value="projectForm.description"
            :rows="3"
            placeholder="请输入项目描述"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { PlusOutlined, FolderOutlined, CalendarOutlined, FileTextOutlined, UnorderedListOutlined, PlayCircleOutlined } from '@ant-design/icons-vue'
import { getProjects, createProject, updateProject, deleteProject as deleteProjectApi, Project } from '@/api/projects'
import { formatDate } from '@/utils/date'

const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const projects = ref<Project[]>([])
const showCreateModal = ref(false)
const editingProject = ref<Project | null>(null)

const projectForm = reactive({
  name: '',
  description: ''
})

async function fetchProjects() {
  loading.value = true
  try {
    const data = await getProjects()
    projects.value = data
    localStorage.setItem('projects', JSON.stringify(data))
  } finally {
    loading.value = false
  }
}

function enterProject(project: Project) {
  router.push(`/projects/${project.id}/cases`)
}

function goToPage(project: Project, page: string) {
  router.push(`/projects/${project.id}/${page}`)
}

function editProject(project: Project) {
  editingProject.value = project
  projectForm.name = project.name
  projectForm.description = project.description
  showCreateModal.value = true
}

async function saveProject() {
  if (!projectForm.name.trim()) {
    message.warning('请输入项目名称')
    return
  }
  saving.value = true
  try {
    if (editingProject.value) {
      await updateProject(editingProject.value.id, projectForm)
      message.success('更新成功')
    } else {
      await createProject(projectForm)
      message.success('创建成功')
    }
    showCreateModal.value = false
    editingProject.value = null
    projectForm.name = ''
    projectForm.description = ''
    fetchProjects()
  } finally {
    saving.value = false
  }
}

function deleteProject(project: Project) {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除项目「${project.name}」吗？`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      await deleteProjectApi(project.id)
      message.success('删除成功')
      fetchProjects()
    }
  })
}

onMounted(fetchProjects)
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
</style>
