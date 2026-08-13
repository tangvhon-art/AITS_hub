<template>
  <div class="knowledge-page">
    <div class="page-header">
      <h2>知识库管理</h2>
      <a-space>
        <a-button @click="showCreateModal">
          <template #icon><FileAddOutlined /></template>
          新建文档
        </a-button>
        <a-upload :show-upload-list="false" :before-upload="handleUpload">
          <a-button type="primary">
            <template #icon><UploadOutlined /></template>
            上传文件
          </a-button>
        </a-upload>
      </a-space>
    </div>

    <!-- 统计卡片 -->
    <a-row :gutter="16" class="stats-row">
      <a-col :span="8">
        <a-card>
          <a-statistic title="文档总数" :value="stats.total_docs" />
        </a-card>
      </a-col>
      <a-col :span="8">
        <a-card>
          <a-statistic title="向量块数" :value="stats.total_chunks" />
        </a-card>
      </a-col>
      <a-col :span="8">
        <a-card>
          <a-input-search v-model:value="searchQuery" placeholder="检索知识库..." @search="handleSearch" enter-button />
        </a-card>
      </a-col>
    </a-row>

    <!-- 检索结果 -->
    <a-card v-if="searchResults.length > 0" title="检索结果" class="search-results-card">
      <a-list :data-source="searchResults" item-layout="vertical">
        <template #renderItem="{ item }">
          <a-list-item>
            <a-list-item-meta :title="item.title" :description="`相似度: ${(item.similarity * 100).toFixed(1)}%`" />
            <p>{{ item.content }}</p>
          </a-list-item>
        </template>
      </a-list>
    </a-card>

    <!-- 文档列表 -->
    <a-card title="文档列表">
      <a-table
        :columns="columns"
        :data-source="docs"
        :loading="loading"
        :pagination="pagination"
        @change="handleTableChange"
        row-key="id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">{{ statusText(record.status) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'file_type'">
            <a-tag>{{ record.file_type }}</a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space>
              <a-button type="link" size="small" @click="viewDoc(record)">查看</a-button>
              <a-popconfirm title="确定删除此文档？" @confirm="deleteDoc(record.id)">
                <a-button type="link" size="small" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 新建文档弹窗 -->
    <a-modal v-model:open="createVisible" title="新建知识库文档" @ok="handleCreate" :confirm-loading="creating">
      <a-form layout="vertical">
        <a-form-item label="文档标题" required>
          <a-input v-model:value="createForm.title" placeholder="请输入文档标题" />
        </a-form-item>
        <a-form-item label="文档内容" required>
          <a-textarea v-model:value="createForm.content" :rows="8" placeholder="请输入文档内容" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 文档详情弹窗 -->
    <a-modal v-model:open="detailVisible" title="文档详情" :footer="null" width="700px">
      <div v-if="currentDoc" class="doc-detail">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="标题" :span="2">{{ currentDoc.title }}</a-descriptions-item>
          <a-descriptions-item label="类型">{{ currentDoc.file_type }}</a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-tag :color="statusColor(currentDoc.status)">{{ statusText(currentDoc.status) }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="向量块数">{{ currentDoc.chunk_count }}</a-descriptions-item>
          <a-descriptions-item label="创建时间">{{ currentDoc.created_at }}</a-descriptions-item>
        </a-descriptions>
        <div class="doc-content">{{ currentDoc.content }}</div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { FileAddOutlined, UploadOutlined } from '@ant-design/icons-vue'
import {
  getKnowledgeDocs, createKnowledgeDoc, uploadKnowledgeDoc, deleteKnowledgeDoc as deleteDocApi,
  searchKnowledge, getKnowledgeStats, type KnowledgeDoc, type KnowledgeSearchResult,
} from '@/api/knowledge'

const route = useRoute()
const projectId = Number(route.params.id)

const loading = ref(false)
const creating = ref(false)
const docs = ref<KnowledgeDoc[]>([])
const stats = ref({ total_docs: 0, total_chunks: 0 })
const pagination = ref({ current: 1, pageSize: 20, total: 0 })

const searchQuery = ref('')
const searchResults = ref<KnowledgeSearchResult['results']>([])

const createVisible = ref(false)
const detailVisible = ref(false)
const currentDoc = ref<KnowledgeDoc | null>(null)
const createForm = ref({ title: '', content: '' })

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '标题', dataIndex: 'title', key: 'title', ellipsis: true },
  { title: '类型', dataIndex: 'file_type', key: 'file_type', width: 100 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '向量块数', dataIndex: 'chunk_count', key: 'chunk_count', width: 100 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170 },
  { title: '操作', key: 'action', width: 140, fixed: 'right' as const },
]

async function loadDocs() {
  loading.value = true
  if (!projectId) {
    loading.value = false
    message.error('缺少项目 ID，无法加载知识库')
    return
  }
  try {
    const [docsRes, statsRes] = await Promise.all([
      getKnowledgeDocs(projectId, { page: pagination.value.current, page_size: pagination.value.pageSize }),
      getKnowledgeStats(projectId),
    ])
    docs.value = docsRes.items
    pagination.value.total = docsRes.total
    stats.value = statsRes
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

function handleTableChange(pag: any) {
  pagination.value.current = pag.current
  pagination.value.pageSize = pag.pageSize
  loadDocs()
}

function showCreateModal() {
  createForm.value = { title: '', content: '' }
  createVisible.value = true
}

async function handleCreate() {
  if (!createForm.value.title || !createForm.value.content) {
    message.warning('请填写标题和内容')
    return
  }
  creating.value = true
  try {
    await createKnowledgeDoc(projectId, createForm.value)
    message.success('创建成功')
    createVisible.value = false
    loadDocs()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

async function handleUpload(file: File) {
  try {
    await uploadKnowledgeDoc(projectId, file)
    message.success('上传成功')
    loadDocs()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '上传失败')
  }
  return false
}

async function handleSearch() {
  if (!searchQuery.value.trim()) {
    searchResults.value = []
    return
  }
  try {
    const res = await searchKnowledge(projectId, searchQuery.value, 5)
    searchResults.value = res.results
  } catch (e: any) {
    message.error(e.response?.data?.detail || '检索失败')
  }
}

function viewDoc(record: KnowledgeDoc) {
  currentDoc.value = record
  detailVisible.value = true
}

async function deleteDoc(id: number) {
  try {
    await deleteDocApi(projectId, id)
    message.success('删除成功')
    loadDocs()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '删除失败')
  }
}

function statusColor(s?: string) {
  const map: Record<string, string> = { pending: 'default', processing: 'orange', ready: 'green', failed: 'red' }
  return map[s || ''] || 'default'
}
function statusText(s?: string) {
  const map: Record<string, string> = { pending: '待处理', processing: '处理中', ready: '就绪', failed: '失败' }
  return map[s || ''] || s
}

onMounted(() => {
  if (projectId) loadDocs()
})

</script>

<style scoped>
.knowledge-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 20px; font-weight: 600; }
.stats-row { margin-bottom: 16px; }
.search-results-card { margin-bottom: 16px; }
.doc-detail { max-height: 500px; overflow-y: auto; }
.doc-content { margin-top: 16px; white-space: pre-wrap; line-height: 1.8; background: #fafafa; padding: 12px; border-radius: 4px; }
</style>
