<template>
  <div class="skills-page">
    <div class="page-header">
      <h2>Skill 管理</h2>
      <div class="header-actions">
        <a-button @click="openImport">导入 Skill 包</a-button>
        <a-button type="primary" @click="openCreate">新建 Skill</a-button>
      </div>
    </div>

    <div class="filter-bar">
      <a-input
        v-model:value="searchKeyword"
        placeholder="搜索名称/标识/描述"
        allow-clear
        style="width: 220px"
        @keyup.enter="handleSearch"
      >
        <template #prefix><SearchOutlined /></template>
      </a-input>
      <a-select v-model:value="filterSource" placeholder="来源" style="width: 120px" allow-clear @change="handleSearch">
        <a-select-option value="builtin">内置</a-select-option>
        <a-select-option value="manual">手动</a-select-option>
        <a-select-option value="imported">已导入</a-select-option>
      </a-select>
      <a-select v-model:value="filterCategory" placeholder="分类" style="width: 120px" allow-clear @change="handleSearch">
        <a-select-option value="testing">测试</a-select-option>
        <a-select-option value="analysis">分析</a-select-option>
        <a-select-option value="automation">自动化</a-select-option>
        <a-select-option value="other">其他</a-select-option>
      </a-select>
      <a-button type="primary" @click="handleSearch">查询</a-button>
      <a-button @click="handleReset">重置</a-button>
    </div>

    <a-table :columns="columns" :data-source="filteredList" :pagination="pagination" :loading="loading" row-key="id">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'source'">
          <a-tag :color="sourceColor(record.source)">{{ sourceLabel(record.source) }}</a-tag>
        </template>
        <template v-else-if="column.key === 'trigger'">
          <span>{{ (record.trigger_config || {}).type || '-' }}</span>
        </template>
        <template v-else-if="column.key === 'is_active'">
          <a-switch :checked="record.is_active" :disabled="record.is_builtin" @change="toggleSkill(record)" />
        </template>
        <template v-else-if="column.key === 'action'">
          <a-button type="link" size="small" @click="openEdit(record)">编辑</a-button>
          <a-button type="link" size="small" @click="handleExport(record)">导出</a-button>
          <a-button type="link" size="small" @click="openFileViewer(record)" :disabled="!record.files || Object.keys(record.files).length === 0">文件</a-button>
          <a-popconfirm v-if="!record.is_builtin" title="确认删除？" @confirm="handleDelete(record)">
            <a-button type="link" size="small" danger>删除</a-button>
          </a-popconfirm>
        </template>
      </template>
    </a-table>

    <!-- 新建/编辑弹窗 -->
    <a-modal v-model:open="modalVisible" :title="editingId ? '编辑 Skill' : '新建 Skill'" :width="720" @ok="handleSave" :confirm-loading="saving">
      <a-form :model="form" layout="vertical">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="标识名" required>
              <a-input v-model:value="form.name" placeholder="英文标识，唯一" :disabled="!!editingId" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="显示名称" required>
              <a-input v-model:value="form.title" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="2" />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="分类">
              <a-select v-model:value="form.category">
                <a-select-option value="testing">测试</a-select-option>
                <a-select-option value="analysis">分析</a-select-option>
                <a-select-option value="automation">自动化</a-select-option>
                <a-select-option value="other">其他</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="版本">
              <a-input v-model:value="form.version" placeholder="1.0.0" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="最大工具调用轮次">
              <a-input-number v-model:value="maxRounds" :min="1" :max="50" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="触发方式">
          <a-select v-model:value="triggerType" @change="onTriggerTypeChange">
            <a-select-option value="keyword">关键词</a-select-option>
            <a-select-option value="regex">正则表达式</a-select-option>
            <a-select-option value="intent">意图</a-select-option>
            <a-select-option value="keyword_or_intent">关键词或意图</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item v-if="triggerType === 'keyword' || triggerType === 'keyword_or_intent'" label="关键词（逗号分隔）">
          <a-input v-model:value="keywordsStr" placeholder="自动测试, 生成计划" />
        </a-form-item>
        <a-form-item v-if="triggerType === 'regex' || triggerType === 'keyword_or_intent'" label="正则表达式">
          <a-input v-model:value="regexPattern" placeholder="^跑.*测试$" />
        </a-form-item>
        <a-form-item label="System Prompt">
          <a-textarea v-model:value="systemPrompt" :rows="4" placeholder="定义 Skill 的角色和行为..." />
        </a-form-item>
        <a-form-item label="允许的工具（多选）">
          <a-select v-model:value="allowedTools" mode="multiple" placeholder="选择工具" :options="toolOptions" style="width: 100%" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 导入弹窗 -->
    <a-modal v-model:open="importVisible" title="导入 Skill" @ok="handleImport" :confirm-loading="importing" width="640px" :ok-button-props="{ disabled: importMode === 'zip' && !importFile }">
      <a-tabs v-model:activeKey="importMode">
        <a-tab-pane key="zip" tab="上传 zip 包">
          <!-- 未选择文件：上传区域 -->
          <a-upload-dragger v-if="!importFile"
            :file-list="[]"
            :before-upload="beforeUpload"
            accept=".zip"
            :max-count="1"
          >
            <p class="ant-upload-drag-icon"><InboxOutlined /></p>
            <p class="ant-upload-text">点击或拖拽 zip 包到此处</p>
            <p class="ant-upload-hint">支持 .zip 格式，最大 2MB，需包含 skill.md</p>
          </a-upload-dragger>

          <!-- 已选择文件：预览区域 -->
          <div v-else class="file-preview">
            <div class="preview-header">
              <div class="file-info">
                <FileZipOutlined class="file-icon" />
                <div>
                  <div class="file-name">{{ importFile.name }}</div>
                  <div class="file-size">{{ formatFileSize(importFile.size) }}</div>
                </div>
              </div>
              <a-button type="link" size="small" @click="clearImportFile">重新选择</a-button>
            </div>

            <div v-if="previewLoading" class="preview-loading">
              <LoadingOutlined class="spin" /> 正在解析包内容...
            </div>

            <div v-else-if="previewError" class="preview-error">
              <CloseCircleOutlined /> {{ previewError }}
            </div>

            <div v-else class="preview-content">
              <div class="preview-section">
                <div class="preview-label">skill.md 内容预览</div>
                <div class="preview-meta">
                  <span v-if="previewMeta.name"><b>名称：</b>{{ previewMeta.name }}</span>
                  <span v-if="previewMeta.title"><b>标题：</b>{{ previewMeta.title }}</span>
                  <span v-if="previewMeta.version"><b>版本：</b>{{ previewMeta.version }}</span>
                  <span v-if="previewMeta.category"><b>分类：</b>{{ previewMeta.category }}</span>
                </div>
                <div class="preview-body" v-if="previewBody">{{ previewBody }}</div>
                <div class="preview-files" v-if="previewFiles.length">
                  <b>包内文件：</b>
                  <a-tag v-for="f in previewFiles" :key="f" color="blue">{{ f }}</a-tag>
                </div>
              </div>
            </div>
          </div>
        </a-tab-pane>
        <a-tab-pane key="text" tab="粘贴 skill.md 内容">
          <a-textarea
            v-model:value="importText"
            :rows="12"
            placeholder="粘贴 skill.md 内容，格式：&#10;---&#10;name: my-skill&#10;title: 我的技能&#10;version: 1.0.0&#10;category: testing&#10;trigger:&#10;  type: keyword&#10;  keywords: [测试]&#10;config:&#10;  allowed_tools: [list_cases]&#10;---&#10;&#10;# 技能指令&#10;你是一名测试助手..."
            class="import-textarea"
          />
        </a-tab-pane>
      </a-tabs>
      <div v-if="importResult" class="import-result" :class="{ success: importResult.success, error: !importResult.success }">
        {{ importResult.message }}
        <div v-if="importResult.warnings && importResult.warnings.length">
          <div v-for="(w, i) in importResult.warnings" :key="i" class="warning-item">⚠ {{ w }}</div>
        </div>
      </div>
    </a-modal>

    <!-- 文件查看器弹窗 -->
    <a-modal v-model:open="fileViewerVisible" :title="`文件浏览 - ${fileViewerSkill?.title || ''}`" width="800px" :footer="null">
      <div class="file-viewer">
        <div class="file-tree-panel">
          <div class="file-tree-header">文件列表 ({{ fileCount }} 个文件)</div>
          <div class="file-tree">
            <template v-for="item in visibleTreeItems" :key="item.key">
              <div
                class="file-tree-item"
                :class="{ active: selectedFile === item.path, folder: item.type === 'folder' }"
                :style="{ paddingLeft: (item.depth * 16 + 14) + 'px' }"
                @click="onTreeItemClick(item)"
              >
                <span class="tree-expand">
                  <CaretRightOutlined v-if="item.type === 'folder' && !item.expanded" />
                  <CaretDownOutlined v-else-if="item.type === 'folder' && item.expanded" />
                  <span v-else style="display:inline-block;width:10px"></span>
                </span>
                <span class="file-icon" :class="item.type === 'folder' ? 'icon-folder' : getFileIconClass(item.path)">
                  <FolderOutlined v-if="item.type === 'folder'" />
                  <FileTextOutlined v-else-if="item.path.endsWith('.md')" />
                  <CodeOutlined v-else-if="item.path.endsWith('.py') || item.path.endsWith('.js') || item.path.endsWith('.ts') || item.path.endsWith('.json') || item.path.endsWith('.yaml') || item.path.endsWith('.yml')" />
                  <FileOutlined v-else />
                </span>
                <span class="file-name">{{ item.name }}</span>
              </div>
            </template>
          </div>
        </div>
        <div class="file-content-panel">
          <div class="file-content-header">
            <span>{{ selectedFile || '选择文件查看内容' }}</span>
          </div>
          <div class="file-content-body" v-if="selectedFile">
            <pre class="file-content-text">{{ fileViewerSkill?.files?.[selectedFile] || '(空文件)' }}</pre>
          </div>
          <div class="file-content-empty" v-else>
            <FileTextOutlined style="font-size: 48px; color: #d9d9d9" />
            <p>点击左侧文件查看内容</p>
          </div>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { message } from 'ant-design-vue'
import { InboxOutlined, SearchOutlined, FileZipOutlined, LoadingOutlined, FolderOutlined, FileTextOutlined, CodeOutlined, FileOutlined, CaretRightOutlined, CaretDownOutlined } from '@ant-design/icons-vue'
import JSZip from 'jszip'
import { skillsApi, type Skill } from '@/api/skills'
import { mcpApi } from '@/api/mcp'

const loading = ref(false)
const saving = ref(false)
const importing = ref(false)
const fileViewerVisible = ref(false)
const fileViewerSkill = ref<Skill | null>(null)
const selectedFile = ref('')
const expandedFolders = ref<Set<string>>(new Set())

interface TreeNode {
  key: string
  name: string
  type: 'folder' | 'file'
  path: string
  depth: number
  expanded: boolean
}

const fileCount = computed(() => Object.keys(fileViewerSkill.value?.files || {}).length)

// 构建树结构（文件夹 + 文件，按层级排序）
const visibleTreeItems = computed<TreeNode[]>(() => {
  const files = fileViewerSkill.value?.files || {}
  const paths = Object.keys(files).sort()
  const items: TreeNode[] = []
  const folderSet = new Set<string>()

  for (const path of paths) {
    const parts = path.split('/')
    // 为每一级文件夹创建节点
    for (let i = 1; i < parts.length; i++) {
      const folderPath = parts.slice(0, i).join('/')
      if (!folderSet.has(folderPath)) {
        folderSet.add(folderPath)
        items.push({
          key: 'folder:' + folderPath,
          name: parts[i - 1],
          type: 'folder',
          path: folderPath,
          depth: i - 1,
          expanded: expandedFolders.value.has(folderPath),
        })
      }
    }
    // 文件节点
    items.push({
      key: 'file:' + path,
      name: parts[parts.length - 1],
      type: 'file',
      path,
      depth: parts.length - 1,
      expanded: false,
    })
  }

  // 过滤收起的文件夹内容
  const result: TreeNode[] = []
  for (const item of items) {
    if (item.type === 'file') {
      // 检查文件的所有父文件夹是否都展开
      const parts = item.path.split('/')
      let hidden = false
      for (let i = 1; i < parts.length; i++) {
        const parentPath = parts.slice(0, i).join('/')
        if (!expandedFolders.value.has(parentPath)) {
          hidden = true
          break
        }
      }
      if (!hidden) result.push(item)
    } else {
      // 文件夹：检查父文件夹是否展开
      const parts = item.path.split('/')
      let hidden = false
      for (let i = 1; i < parts.length; i++) {
        const parentPath = parts.slice(0, i).join('/')
        if (!expandedFolders.value.has(parentPath)) {
          hidden = true
          break
        }
      }
      if (!hidden) result.push(item)
    }
  }
  return result
})

function onTreeItemClick(item: TreeNode) {
  if (item.type === 'folder') {
    if (expandedFolders.value.has(item.path)) {
      expandedFolders.value.delete(item.path)
    } else {
      expandedFolders.value.add(item.path)
    }
  } else {
    selectedFile.value = item.path
  }
}

function getFileIconClass(path: string): string {
  const ext = path.split('.').pop()?.toLowerCase() || ''
  if (['md', 'markdown'].includes(ext)) return 'icon-md'
  if (['py'].includes(ext)) return 'icon-py'
  if (['js', 'jsx', 'ts', 'tsx'].includes(ext)) return 'icon-js'
  if (['json'].includes(ext)) return 'icon-json'
  if (['yaml', 'yml'].includes(ext)) return 'icon-yaml'
  if (['txt'].includes(ext)) return 'icon-txt'
  return 'icon-other'
}
const list = ref<Skill[]>([])
const pagination = ref({ current: 1, pageSize: 20, total: 0, showSizeChanger: true })
const filterSource = ref<string>()
const filterCategory = ref<string>()
const searchKeyword = ref('')
const modalVisible = ref(false)
const importVisible = ref(false)
const editingId = ref<number | null>(null)
const importFile = ref<File | null>(null)
const importResult = ref<any>(null)
const importMode = ref<'zip' | 'text'>('zip')
const importText = ref('')
const previewLoading = ref(false)
const previewError = ref('')
const previewMeta = ref<Record<string, any>>({})
const previewBody = ref('')
const previewFiles = ref<string[]>([])
const allTools = ref<any[]>([])

const filteredList = computed(() => {
  let result = list.value
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase()
    result = result.filter(s =>
      s.title.toLowerCase().includes(kw) ||
      s.name.toLowerCase().includes(kw) ||
      (s.description || '').toLowerCase().includes(kw)
    )
  }
  if (filterSource.value) result = result.filter(s => s.source === filterSource.value)
  if (filterCategory.value) result = result.filter(s => s.category === filterCategory.value)
  return result
})

const form = ref<any>({ name: '', title: '', description: '', category: 'other', version: '1.0.0' })
const triggerType = ref('keyword')
const keywordsStr = ref('')
const regexPattern = ref('')
const systemPrompt = ref('')
const allowedTools = ref<string[]>([])
const maxRounds = ref(10)

const toolOptions = computed(() => allTools.value.map(t => ({ label: `${t.name} - ${t.description.slice(0, 30)}`, value: t.name })))

const columns = [
  { title: '名称', dataIndex: 'title', key: 'title' },
  { title: '标识', dataIndex: 'name', key: 'name', width: 140 },
  { title: '来源', key: 'source', width: 100 },
  { title: '触发', key: 'trigger', width: 100 },
  { title: '版本', dataIndex: 'version', key: 'version', width: 80 },
  { title: '启用', key: 'is_active', width: 80 },
  { title: '操作', key: 'action', width: 260 },
]

function sourceColor(s: string) { return { builtin: 'blue', manual: 'green', imported: 'orange' }[s] || 'default' }
function sourceLabel(s: string) { return { builtin: '内置', manual: '手动', imported: '已导入' }[s] || s }

async function loadData() {
  loading.value = true
  try {
    const res = await skillsApi.list({ page: 1, page_size: 100 })
    list.value = res.items
    pagination.value.total = res.total
  } finally { loading.value = false }
}

function handleSearch() {
  pagination.value.current = 1
}

function handleReset() {
  searchKeyword.value = ''
  filterSource.value = undefined
  filterCategory.value = undefined
  pagination.value.current = 1
}

async function loadTools() {
  try { const res = await mcpApi.listAllTools(); allTools.value = res.tools } catch {}
}

function openCreate() {
  editingId.value = null
  form.value = { name: '', title: '', description: '', category: 'other', version: '1.0.0' }
  triggerType.value = 'keyword'; keywordsStr.value = ''; regexPattern.value = ''; systemPrompt.value = ''; allowedTools.value = []; maxRounds.value = 10
  modalVisible.value = true
}

function openEdit(record: Skill) {
  editingId.value = record.id
  form.value = { ...record }
  const tc = record.trigger_config || {}
  triggerType.value = tc.type || 'keyword'
  keywordsStr.value = (tc.keywords || []).join(', ')
  regexPattern.value = tc.pattern || ''
  const sc = record.skill_config || {}
  systemPrompt.value = sc.system_prompt || ''
  allowedTools.value = sc.allowed_tools || []
  maxRounds.value = sc.max_tool_calls || 10
  modalVisible.value = true
}

function onTriggerTypeChange() {}

async function handleSave() {
  if (!form.value.name || !form.value.title) { message.warning('请填写标识名和显示名称'); return }
  saving.value = true
  try {
    const trigger_config: any = { type: triggerType.value }
    if (keywordsStr.value) trigger_config.keywords = keywordsStr.value.split(',').map(s => s.trim()).filter(Boolean)
    if (regexPattern.value) trigger_config.pattern = regexPattern.value
    const skill_config = { system_prompt: systemPrompt.value, allowed_tools: allowedTools.value, max_tool_calls: maxRounds.value }
    const data = { ...form.value, trigger_config, skill_config }
    if (editingId.value) await skillsApi.update(editingId.value, data)
    else await skillsApi.create(data)
    message.success('保存成功')
    modalVisible.value = false
    loadData()
  } finally { saving.value = false }
}

async function toggleSkill(record: Skill) {
  await skillsApi.toggle(record.id)
  loadData()
}

async function handleDelete(record: Skill) {
  await skillsApi.remove(record.id)
  message.success('删除成功')
  loadData()
}

async function handleExport(record: Skill) {
  try {
    await skillsApi.exportSkill(record.id)
    message.success('导出成功')
  } catch (e: any) {
    message.error(e.message || '导出失败')
  }
}

function openFileViewer(record: Skill) {
  fileViewerSkill.value = record
  selectedFile.value = ''
  expandedFolders.value = new Set()
  // 默认展开第一级文件夹
  const files = record.files || {}
  const topFolders = new Set<string>()
  for (const path of Object.keys(files)) {
    const parts = path.split('/')
    if (parts.length > 1) topFolders.add(parts[0])
  }
  topFolders.forEach(f => expandedFolders.value.add(f))
  fileViewerVisible.value = true
}

function openImport() {
  importFile.value = null
  importResult.value = null
  importText.value = ''
  importMode.value = 'zip'
  previewLoading.value = false
  previewError.value = ''
  previewMeta.value = {}
  previewBody.value = ''
  previewFiles.value = []
  importVisible.value = true
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(2) + ' MB'
}

function clearImportFile() {
  importFile.value = null
  previewError.value = ''
  previewMeta.value = {}
  previewBody.value = ''
  previewFiles.value = []
}

async function parseZipPreview(file: File) {
  previewLoading.value = true
  previewError.value = ''
  previewMeta.value = {}
  previewBody.value = ''
  previewFiles.value = []
  try {
    const zip = await JSZip.loadAsync(file)
    const files = Object.keys(zip.files).filter(n => !zip.files[n].dir && !n.startsWith('__MACOSX'))
    previewFiles.value = files
    // 查找 skill.md：支持根目录或子文件夹（第一层为 skill 名称文件夹）
    const mdFile = files.find(n => n.toLowerCase().endsWith('skill.md'))
    if (!mdFile) {
      previewError.value = '包内未找到 skill.md 文件（支持根目录或子文件夹）'
      return
    }
    const baseDir = mdFile.includes('/') ? mdFile.split('/').slice(0, -1).join('/') + '/' : ''
    const content = await zip.files[mdFile].async('string')
    // 解析 frontmatter
    if (content.startsWith('---')) {
      const endIdx = content.indexOf('\n---', 3)
      if (endIdx !== -1) {
        const fmText = content.slice(3, endIdx).trim()
        previewBody.value = content.slice(endIdx + 4).trim().slice(0, 500)
        // 简单解析 frontmatter 关键字段
        const lines = fmText.split('\n')
        for (const line of lines) {
          const m = line.match(/^(\w+):\s*(.+)$/)
          if (m) {
            const key = m[1].trim()
            const val = m[2].trim().replace(/^['"]|['"]$/g, '')
            if (['name', 'title', 'version', 'category', 'author', 'description'].includes(key)) {
              previewMeta.value[key] = val
            }
          }
        }
      } else {
        previewBody.value = content.slice(0, 500)
      }
    } else {
      previewBody.value = content.slice(0, 500)
    }
  } catch (e: any) {
    previewError.value = `解析失败: ${e.message}`
  } finally {
    previewLoading.value = false
  }
}

function beforeUpload(file: File) {
  if (file.size > 2 * 1024 * 1024) { message.error('文件超过 2MB'); return false }
  importFile.value = file
  parseZipPreview(file)
  return false
}

async function handleImport() {
  importing.value = true
  try {
    if (importMode.value === 'text') {
      if (!importText.value.trim()) { message.warning('请输入 skill.md 内容'); return }
      importResult.value = await skillsApi.importText(importText.value)
    } else {
      if (!importFile.value) { message.warning('请选择文件'); return }
      importResult.value = await skillsApi.importSkill(importFile.value)
    }
    if (importResult.value.success) {
      message.success('导入成功')
      loadData()
      importVisible.value = false
    }
  } finally { importing.value = false }
}

onMounted(() => { loadData(); loadTools() })
</script>

<style scoped>
.skills-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 18px; }
.header-actions { display: flex; gap: 8px; }
.filter-bar { display: flex; gap: 12px; margin-bottom: 16px; }
.import-result { margin-top: 12px; padding: 10px; border-radius: 6px; font-size: 13px; }
.import-result.success { background: #f6ffed; color: #52c41a; }
.import-result.error { background: #fff2f0; color: #ff4d4f; }
.warning-item { color: #faad14; font-size: 12px; margin-top: 4px; }
.import-textarea { font-family: monospace; font-size: 12px; margin-top: 8px; }
.file-preview { border: 1px solid #e8e8e8; border-radius: 8px; padding: 16px; }
.preview-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.file-info { display: flex; align-items: center; gap: 12px; }
.file-icon { font-size: 32px; color: #1677ff; }
.file-name { font-size: 14px; font-weight: 600; color: #1f2329; }
.file-size { font-size: 12px; color: #86909c; margin-top: 2px; }
.preview-loading { text-align: center; padding: 24px; color: #1677ff; font-size: 13px; }
.preview-error { text-align: center; padding: 24px; color: #ff4d4f; font-size: 13px; }
.spin { animation: spin 1s linear infinite; margin-right: 6px; }
@keyframes spin { from { transform: rotate(0); } to { transform: rotate(360deg); } }
.preview-section { background: #fafbfc; border-radius: 6px; padding: 12px; }
.preview-label { font-size: 12px; font-weight: 600; color: #86909c; margin-bottom: 8px; }
.preview-meta { display: flex; flex-wrap: wrap; gap: 12px; font-size: 12px; color: #4e5969; margin-bottom: 8px; }
.preview-body { font-size: 12px; color: #4e5969; background: #fff; padding: 8px; border-radius: 4px; max-height: 120px; overflow-y: auto; white-space: pre-wrap; font-family: monospace; margin-bottom: 8px; }
.preview-files { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; font-size: 12px; color: #86909c; }
.file-viewer { display: flex; height: 500px; border: 1px solid #e8e8e8; border-radius: 8px; overflow: hidden; }
.file-tree-panel { width: 240px; border-right: 1px solid #e8e8e8; display: flex; flex-direction: column; background: #fafafa; }
.file-tree-header { padding: 10px 14px; font-size: 13px; font-weight: 600; color: #1f2329; border-bottom: 1px solid #e8e8e8; background: #fff; }
.file-tree { flex: 1; overflow-y: auto; padding: 6px 0; }
.file-tree-item { display: flex; align-items: center; gap: 5px; padding: 5px 12px; cursor: pointer; font-size: 12px; color: #4e5969; transition: background 0.15s; border-radius: 4px; margin: 1px 4px; }
.file-tree-item:hover { background: #f0f7ff; }
.file-tree-item.active { background: #e8f3ff; color: #1677ff; font-weight: 500; }
.file-tree-item.folder { font-weight: 500; color: #1f2329; }
.tree-expand { width: 10px; display: flex; justify-content: center; font-size: 9px; color: #a9aeb8; flex-shrink: 0; }
.file-tree-item .file-icon { width: 14px; height: 14px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: 13px; }
.file-tree-item .file-icon.icon-folder { color: #faad14; }
.file-tree-item .file-icon.icon-md { color: #519aba; }
.file-tree-item .file-icon.icon-py { color: #3572A5; }
.file-tree-item .file-icon.icon-js { color: #f0a020; }
.file-tree-item .file-icon.icon-json { color: #cbcb41; }
.file-tree-item .file-icon.icon-yaml { color: #cb171e; }
.file-tree-item .file-icon.icon-txt { color: #86909c; }
.file-tree-item .file-icon.icon-other { color: #a9aeb8; }
.file-tree-item .file-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-content-panel { flex: 1; display: flex; flex-direction: column; background: #fff; }
.file-content-header { padding: 10px 16px; font-size: 13px; font-weight: 500; color: #1f2329; border-bottom: 1px solid #e8e8e8; background: #fafafa; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-content-body { flex: 1; overflow: auto; padding: 0; }
.file-content-text { margin: 0; padding: 16px; font-size: 12px; line-height: 1.6; color: #1f2329; font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace; white-space: pre-wrap; word-break: break-all; }
.file-content-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; color: #86909c; font-size: 14px; }
</style>
