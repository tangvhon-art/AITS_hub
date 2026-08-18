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
      <a-col :span="6">
        <a-card>
          <a-statistic title="文档总数" :value="stats.total_docs" />
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card>
          <a-statistic title="向量块数" :value="stats.total_chunks" />
        </a-card>
      </a-col>
      <a-col :span="12">
        <a-card>
          <a-input-search v-model:value="searchQuery" placeholder="语义检索知识库（向量搜索）..." @search="handleSearch" enter-button="检索" />
          <div style="margin-top: 8px; display: flex; justify-content: space-between; align-items: center">
            <span style="color: rgba(0,0,0,0.45); font-size: 12px">输入问题，AI 将从知识库中检索最相关的内容</span>
            <a-button v-if="searchResults.length > 0" size="small" @click="handleReset">清除检索结果</a-button>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 语义检索结果 -->
    <a-card v-if="searchResults.length > 0" title="语义检索结果" class="search-results-card">
      <a-list :data-source="searchResults" item-layout="vertical">
        <template #renderItem="{ item }">
          <a-list-item>
            <a-list-item-meta>
              <template #title>
                <span>{{ item.title }}</span>
                <a-tag color="blue" style="margin-left: 8px">相似度 {{ (item.similarity * 100).toFixed(1) }}%</a-tag>
              </template>
            </a-list-item-meta>
            <div class="search-result-content">{{ item.content }}</div>
          </a-list-item>
        </template>
      </a-list>
    </a-card>

    <!-- Tab 切换 -->
    <a-card>
      <a-tabs v-model:activeKey="activeTab">
        <!-- 文档管理 -->
        <a-tab-pane key="docs" tab="文档管理">
          <div class="tab-toolbar">
            <a-input
              v-model:value="docKeyword"
              placeholder="搜索文档标题/内容"
              allow-clear
              style="width: 250px"
              @keyup.enter="loadDocs"
              @change="onDocKeywordChange"
            />
            <a-select v-model:value="docSourceType" placeholder="来源类型" allow-clear style="width: 140px" @change="loadDocs">
              <a-select-option value="manual">手动创建</a-select-option>
              <a-select-option value="upload">文件上传</a-select-option>
              <a-select-option value="requirement">需求同步</a-select-option>
            </a-select>
            <a-button type="primary" @click="loadDocs">查询</a-button>
          </div>
          <a-table
            :columns="docColumns"
            :data-source="docs"
            :loading="loading"
            :pagination="docPagination"
            @change="handleDocTableChange"
            row-key="id"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'title'">
                <a-tooltip placement="topLeft" :overlay-style="{ maxWidth: '500px' }">
                  <template #title>
                    <div style="white-space: pre-wrap">{{ record.title }}</div>
                  </template>
                  <span class="cell-ellipsis-text">{{ record.title }}</span>
                </a-tooltip>
              </template>
              <template v-else-if="column.key === 'status'">
                <a-tag :color="statusColor(record.status)">{{ statusText(record.status) }}</a-tag>
              </template>
              <template v-else-if="column.key === 'file_type'">
                <a-tag>{{ fileTypeText(record.file_type) }}</a-tag>
              </template>
              <template v-else-if="column.key === 'source_type'">
                <a-tag :color="sourceTypeColor(record.source_type)">{{ sourceTypeText(record.source_type) }}</a-tag>
              </template>
              <template v-else-if="column.key === 'action'">
                <a-space>
                  <a-button
                    type="link"
                    size="small"
                    :loading="record.status === 'processing'"
                    :disabled="record.status === 'processing'"
                    @click="handleGenerateChunks(record)"
                  >生成切片</a-button>
                  <a-button type="link" size="small" @click="viewDoc(record)">查看</a-button>
                  <a-popconfirm title="确定删除此文档？" @confirm="deleteDoc(record.id)">
                    <a-button type="link" size="small" danger>删除</a-button>
                  </a-popconfirm>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-tab-pane>

        <!-- 知识内容（切片列表） -->
        <a-tab-pane key="chunks" tab="知识内容">
          <div class="tab-toolbar">
            <a-input
              v-model:value="chunkKeyword"
              placeholder="搜索切片内容"
              allow-clear
              style="width: 250px"
              @keyup.enter="loadChunks"
            />
            <a-select
              v-model:value="chunkDocId"
              placeholder="筛选文档"
              allow-clear
              style="width: 250px"
              :options="docFilterOptions"
              @change="loadChunks"
            />
            <a-button type="primary" @click="loadChunks">查询</a-button>
            <a-button @click="resetChunkFilter">重置</a-button>
          </div>
          <a-table
            :columns="chunkColumns"
            :data-source="chunks"
            :loading="chunksLoading"
            :pagination="chunkPagination"
            @change="handleChunkTableChange"
            row-key="id"
            size="middle"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'doc_title'">
                <a-tooltip placement="topLeft" :overlay-style="{ maxWidth: '400px' }">
                  <template #title>
                    <div style="white-space: pre-wrap">{{ record.doc_title }}</div>
                  </template>
                  <span class="cell-ellipsis-text">{{ record.doc_title }}</span>
                </a-tooltip>
              </template>
              <template v-else-if="column.key === 'content'">
                <a-tooltip placement="topLeft" :overlay-style="{ maxWidth: '600px' }">
                  <template #title>
                    <div style="white-space: pre-wrap; max-height: 400px; overflow-y: auto">{{ record.content }}</div>
                  </template>
                  <span class="cell-ellipsis-text chunk-preview">{{ record.content }}</span>
                </a-tooltip>
              </template>
              <template v-else-if="column.key === 'action'">
                <a-button type="link" size="small" @click="viewChunk(record)">查看全文</a-button>
              </template>
            </template>
          </a-table>
        </a-tab-pane>
      </a-tabs>
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
          <a-descriptions-item label="类型">{{ fileTypeText(currentDoc.file_type) }}</a-descriptions-item>
          <a-descriptions-item label="来源">{{ sourceTypeText(currentDoc.source_type) }}</a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-tag :color="statusColor(currentDoc.status)">{{ statusText(currentDoc.status) }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="向量块数">{{ currentDoc.chunk_count }}</a-descriptions-item>
          <a-descriptions-item label="创建时间" :span="2">{{ $formatDateTime(currentDoc.created_at) }}</a-descriptions-item>
        </a-descriptions>
        <div class="doc-content">{{ currentDoc.content }}</div>
      </div>
    </a-modal>

    <!-- 切片全文弹窗 -->
    <a-modal v-model:open="chunkDetailVisible" title="知识内容详情" :footer="null" width="700px">
      <div v-if="currentChunk" class="chunk-detail">
        <a-descriptions :column="2" bordered size="small" style="margin-bottom: 16px">
          <a-descriptions-item label="所属文档" :span="2">{{ currentChunk.doc_title }}</a-descriptions-item>
          <a-descriptions-item label="切片序号">#{{ currentChunk.chunk_index + 1 }}</a-descriptions-item>
          <a-descriptions-item label="字符数">{{ currentChunk.token_count }}</a-descriptions-item>
        </a-descriptions>
        <div class="chunk-content-full">{{ currentChunk.content }}</div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { formatDateTime } from '@/utils/date'
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useUrlSearch } from '@/composables/useUrlSearch'
import { message } from 'ant-design-vue'
import { FileAddOutlined, UploadOutlined } from '@ant-design/icons-vue'
import {
  getKnowledgeDocs, getKnowledgeChunks, createKnowledgeDoc, uploadKnowledgeDoc,
  deleteKnowledgeDoc as deleteDocApi, generateChunks, searchKnowledge, getKnowledgeStats,
  type KnowledgeDoc, type KnowledgeChunk, type KnowledgeSearchResult,
} from '@/api/knowledge'

const route = useRoute()
const { loadFromUrl, syncToUrl } = useUrlSearch()
const projectId = Number(route.params.id)

const activeTab = ref('docs')

// === 文档管理 ===
const loading = ref(false)
const creating = ref(false)
const docs = ref<KnowledgeDoc[]>([])
const stats = ref({ total_docs: 0, total_chunks: 0 })
const docKeyword = ref('')
const docSourceType = ref<string | undefined>(undefined)
const docPagination = reactive({ current: 1, pageSize: 10, total: 0, showSizeChanger: true, showTotal: (t: number) => `共 ${t} 条` })

const searchQuery = ref('')
const searchResults = ref<KnowledgeSearchResult['results']>([])

const createVisible = ref(false)
const detailVisible = ref(false)
const currentDoc = ref<KnowledgeDoc | null>(null)
const createForm = ref({ title: '', content: '' })

const docColumns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '标题', dataIndex: 'title', key: 'title', ellipsis: true },
  { title: '类型', dataIndex: 'file_type', key: 'file_type', width: 100 },
  { title: '来源', dataIndex: 'source_type', key: 'source_type', width: 100 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90 },
  { title: '向量块数', dataIndex: 'chunk_count', key: 'chunk_count', width: 90 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170, customRender: ({ text }: { text: string }) => formatDateTime(text) },
  { title: '操作', key: 'action', width: 200, fixed: 'right' as const },
]

// === 知识内容（切片） ===
const chunksLoading = ref(false)
const chunks = ref<KnowledgeChunk[]>([])
const chunkKeyword = ref('')
const chunkDocId = ref<number | undefined>(undefined)
const chunkPagination = reactive({ current: 1, pageSize: 10, total: 0, showSizeChanger: true, showTotal: (t: number) => `共 ${t} 条` })
const chunkDetailVisible = ref(false)
const currentChunk = ref<KnowledgeChunk | null>(null)

const chunkColumns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
  { title: '所属文档', dataIndex: 'doc_title', key: 'doc_title', width: 200, ellipsis: true },
  { title: '序号', dataIndex: 'chunk_index', key: 'chunk_index', width: 70, customRender: ({ text }: { text: number }) => `#${text + 1}` },
  { title: '内容', dataIndex: 'content', key: 'content', ellipsis: true },
  { title: '字符数', dataIndex: 'token_count', key: 'token_count', width: 90 },
  { title: '操作', key: 'action', width: 100 },
]

const docFilterOptions = computed(() =>
  docs.value.map(d => ({ label: d.title, value: d.id }))
)

// === 文档加载 ===
async function loadDocs() {
  loading.value = true
  if (!projectId) {
    loading.value = false
    message.error('缺少项目 ID，无法加载知识库')
    return
  }
  try {
    const [docsRes, statsRes] = await Promise.all([
      getKnowledgeDocs(projectId, {
        page: docPagination.current,
        page_size: docPagination.pageSize,
        keyword: docKeyword.value || undefined,
        source_type: docSourceType.value || undefined,
      }),
      getKnowledgeStats(projectId),
    ])
    docs.value = docsRes.items
    docPagination.total = docsRes.total
    stats.value = statsRes
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

function handleDocTableChange(pag: any) {
  docPagination.current = pag.current
  docPagination.pageSize = pag.pageSize
  loadDocs()
}

function onDocKeywordChange() {
  if (!docKeyword.value) {
    docPagination.current = 1
    loadDocs()
  }
}

// === 切片加载 ===
async function loadChunks() {
  chunksLoading.value = true
  try {
    const res = await getKnowledgeChunks(projectId, {
      page: chunkPagination.current,
      page_size: chunkPagination.pageSize,
      keyword: chunkKeyword.value || undefined,
      doc_id: chunkDocId.value || undefined,
    })
    chunks.value = res.items
    chunkPagination.total = res.total
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载知识内容失败')
  } finally {
    chunksLoading.value = false
  }
}

function handleChunkTableChange(pag: any) {
  chunkPagination.current = pag.current
  chunkPagination.pageSize = pag.pageSize
  loadChunks()
}

function resetChunkFilter() {
  chunkKeyword.value = ''
  chunkDocId.value = undefined
  chunkPagination.current = 1
  loadChunks()
}

function viewChunk(record: KnowledgeChunk) {
  currentChunk.value = record
  chunkDetailVisible.value = true
}

// === 语义检索 ===
async function handleSearch() {
  syncToUrl({ q: searchQuery.value })
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

function handleReset() {
  searchQuery.value = ''
  searchResults.value = []
  syncToUrl({ q: searchQuery.value })
}

// === 文档 CRUD ===
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

let pollTimer: ReturnType<typeof setInterval> | null = null

function startPolling() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    const hasProcessing = docs.value.some(d => d.status === 'processing')
    if (hasProcessing) {
      await loadDocs()
    } else {
      stopPolling()
    }
  }, 3000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function handleGenerateChunks(record: KnowledgeDoc) {
  if (!record.id) return
  try {
    await generateChunks(projectId, record.id)
    message.success('切片任务已提交')
    record.status = 'processing'
    startPolling()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '提交切片任务失败')
  }
}

// === 工具函数 ===
function statusColor(s?: string) {
  const map: Record<string, string> = { pending: 'default', processing: 'orange', ready: 'green', failed: 'red' }
  return map[s || ''] || 'default'
}
function statusText(s?: string) {
  const map: Record<string, string> = { pending: '待处理', processing: '处理中', ready: '就绪', failed: '失败' }
  return map[s || ''] || s
}
function fileTypeText(t?: string) {
  const map: Record<string, string> = { text: '文本', markdown: 'Markdown', docx: 'Word', pdf: 'PDF' }
  return map[t || ''] || t || '-'
}
function sourceTypeText(t?: string) {
  const map: Record<string, string> = { manual: '手动创建', upload: '文件上传', requirement: '需求同步' }
  return map[t || ''] || t || '-'
}
function sourceTypeColor(t?: string) {
  const map: Record<string, string> = { manual: 'blue', upload: 'cyan', requirement: 'purple' }
  return map[t || ''] || 'default'
}

onMounted(async () => {
  const params = loadFromUrl({ q: '' })
  searchQuery.value = params.q
  if (projectId) {
    await loadDocs()
    if (docs.value.some(d => d.status === 'processing')) {
      startPolling()
    }
    if (searchQuery.value) handleSearch()
  }
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.knowledge-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 20px; font-weight: 600; }
.stats-row { margin-bottom: 16px; }
.search-results-card { margin-bottom: 16px; }
.search-result-content { white-space: pre-wrap; line-height: 1.8; color: rgba(0,0,0,0.75); }
.tab-toolbar { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.doc-detail { max-height: 500px; overflow-y: auto; }
.doc-content { margin-top: 16px; white-space: pre-wrap; line-height: 1.8; background: #fafafa; padding: 12px; border-radius: 4px; }
.chunk-detail { max-height: 600px; overflow-y: auto; }
.chunk-content-full { white-space: pre-wrap; line-height: 1.8; background: #fafafa; padding: 16px; border-radius: 4px; }
.cell-ellipsis-text {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: bottom;
}
.chunk-preview {
  color: rgba(0, 0, 0, 0.7);
}
</style>
