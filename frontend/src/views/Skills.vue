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
          <a-button type="link" size="small" @click="testMatch(record)">匹配测试</a-button>
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

    <!-- 匹配测试弹窗 -->
    <a-modal v-model:open="matchVisible" title="Skill 匹配测试" @ok="handleMatchTest" :confirm-loading="matchLoading" width="520px" okText="测试匹配" cancelText="关闭">
      <div class="match-test-form">
        <div class="match-test-label">测试消息</div>
        <a-textarea
          v-model:value="matchMessage"
          placeholder="输入用户消息，测试是否能匹配到此 Skill..."
          :rows="3"
          :disabled="matchLoading"
        />
        <div v-if="matchResult" class="match-test-result" :class="matchResult.matched ? 'success' : 'fail'">
          <div class="result-title">
            <CheckCircleOutlined v-if="matchResult.matched" class="result-icon success" />
            <CloseCircleOutlined v-else class="result-icon fail" />
            <span>{{ matchResult.matched ? '匹配成功' : '未匹配' }}</span>
          </div>
          <div v-if="matchResult.matched && matchResult.skill" class="result-detail">
            <div><span class="label">匹配 Skill：</span>{{ matchResult.skill.title }}</div>
            <div v-if="matchResult.reason"><span class="label">匹配原因：</span>{{ matchResult.reason }}</div>
          </div>
          <div v-else class="result-detail">
            <div><span class="label">原因：</span>{{ matchResult.reason || '当前消息未匹配到任何 Skill' }}</div>
          </div>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { message } from 'ant-design-vue'
import { InboxOutlined, SearchOutlined, FileZipOutlined, LoadingOutlined, CloseCircleOutlined, CheckCircleOutlined } from '@ant-design/icons-vue'
import JSZip from 'jszip'
import { skillsApi, type Skill } from '@/api/skills'
import { mcpApi } from '@/api/mcp'

const loading = ref(false)
const saving = ref(false)
const importing = ref(false)
const matchVisible = ref(false)
const matchLoading = ref(false)
const matchMessage = ref('')
const matchResult = ref<any>(null)
const matchRecord = ref<Skill | null>(null)
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

function handleExport(record: Skill) {
  window.open(skillsApi.exportUrl(record.id), '_blank')
}

function testMatch(record: Skill) {
  matchRecord.value = record
  matchMessage.value = ''
  matchResult.value = null
  matchVisible.value = true
}

async function handleMatchTest() {
  if (!matchMessage.value.trim()) {
    message.warning('请输入测试消息')
    return
  }
  matchLoading.value = true
  matchResult.value = null
  try {
    const res = await skillsApi.match(matchMessage.value)
    const isCurrentSkill = res.matched && res.skill?.id === matchRecord.value?.id
    matchResult.value = {
      matched: isCurrentSkill,
      skill: res.skill,
      reason: isCurrentSkill ? '成功匹配到当前 Skill' : (res.reason || '未匹配到此 Skill'),
    }
  } catch (e: any) {
    matchResult.value = { matched: false, reason: `测试失败: ${e.message}` }
  } finally {
    matchLoading.value = false
  }
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
.match-test-form { display: flex; flex-direction: column; gap: 16px; }
.match-test-label { font-size: 14px; font-weight: 500; color: #1f2329; margin-bottom: 4px; }
.match-test-result { padding: 12px 16px; border-radius: 8px; background: #f7f8fa; }
.match-test-result.success { background: #e8ffea; border: 1px solid #b7eb8f; }
.match-test-result.fail { background: #fff2f0; border: 1px solid #ffccc7; }
.result-title { display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 600; margin-bottom: 8px; }
.result-title.success { color: #389e0d; }
.result-title.fail { color: #cf1322; }
.result-icon { font-size: 16px; }
.result-detail { font-size: 13px; color: #4e5969; line-height: 1.8; }
.result-detail .label { color: #86909c; }
</style>
