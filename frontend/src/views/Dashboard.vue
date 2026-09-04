<template>
  <div class="dashboard-immersive">
    <!-- 顶部控制栏 -->
    <div class="top-bar">
      <div class="top-bar-left">
        <a-select
          v-model:value="selectedProjectId"
          class="control-select"
          placeholder="选择项目（可选，不选则通用问答）"
          allow-clear
          @change="handleProjectChange"
        >
          <a-select-option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</a-select-option>
        </a-select>
        <a-select
          v-model:value="selectedLlmConfigId"
          class="control-select"
          placeholder="选择模型"
          @change="handleModelChange"
        >
          <a-select-option v-for="c in llmConfigs" :key="c.id" :value="c.id">{{ c.name }}</a-select-option>
        </a-select>
        <a-button type="text" size="small" :loading="probingCaps" @click="reprobeCapabilities" title="重新检测模型能力">
          <ReloadOutlined />
        </a-button>
        <a-button type="text" size="small" :loading="reloadingSkills" @click="handleReloadSkills" title="刷新 Skill 列表">
          <ThunderboltOutlined />
        </a-button>
        <a-checkbox v-model:checked="useKnowledge" class="knowledge-checkbox" :disabled="!selectedProjectId">知识库</a-checkbox>
      </div>
      <div class="top-bar-right">
        <span class="app-title">AITS 助手</span>
        <button class="icon-btn" @click="newChat" title="新对话">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <line x1="12" y1="5" x2="12" y2="19"/>
            <line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
        </button>
        <button class="icon-btn" @click="openHistoryDrawer" title="历史对话">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 12a9 9 0 1 0 3-6.7L3 8"/>
            <path d="M3 3v5h5"/>
            <path d="M12 7v5l3 2"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- 历史对话抽屉 -->
    <a-drawer
      v-model:open="historyDrawerVisible"
      title="历史对话"
      placement="right"
      :width="320"
    >
      <div class="drawer-search">
        <a-input v-model:value="sessionSearch" placeholder="搜索对话" allow-clear>
          <template #prefix><SearchOutlined /></template>
        </a-input>
      </div>
      <div class="drawer-session-list">
        <!-- 骨架屏加载 -->
        <div v-if="loadingSessions" class="session-skeleton-list">
          <div v-for="i in 6" :key="i" class="session-skeleton-item">
            <div class="skeleton-line skeleton-title"></div>
            <div class="skeleton-line skeleton-meta"></div>
          </div>
        </div>
        <div v-else-if="filteredSessions.length === 0" class="session-empty">暂无对话</div>
        <div
          v-for="s in filteredSessions"
          :key="s.id"
          class="session-item"
          :class="{ active: currentSessionId === s.id }"
          @click="loadSession(s.id)"
        >
          <div class="session-item-title">{{ s.title }}</div>
          <div class="session-item-meta">
            <span>{{ s.message_count }} 条</span>
            <span>{{ formatTime(s.last_message_at) }}</span>
          </div>
          <div class="session-item-actions" @click.stop>
            <a-button type="text" size="small" @click="renameSession(s)" title="重命名">
              <EditOutlined />
            </a-button>
            <a-button type="text" size="small" danger @click="deleteSession(s.id)" title="删除">
              <DeleteOutlined />
            </a-button>
          </div>
        </div>
      </div>
    </a-drawer>

    <!-- 模型降级提示 -->
    <div v-if="degradeWarning" class="degrade-banner">
      <WarningOutlined class="warn-icon" />
      <span>{{ degradeWarning }}，如需调用工具请切换其他模型</span>
      <span class="banner-close" @click="degradeWarning = ''">×</span>
    </div>

    <!-- 聊天区域 -->
    <div class="chat-container" ref="messagesContainer">
      <!-- 空状态 -->
      <div v-if="messages.length === 0 && !loadingMessages" class="empty-state">
        <div class="empty-logo">
          <svg viewBox="0 0 40 40" width="48" height="48">
            <circle cx="20" cy="6" r="3" fill="#1677ff"/>
            <line x1="20" y1="9" x2="20" y2="14" stroke="#1677ff" stroke-width="2"/>
            <rect x="8" y="14" width="24" height="18" rx="5" fill="#e6f4ff" stroke="#1677ff" stroke-width="1"/>
            <circle cx="15" cy="22" r="2.5" fill="#1677ff"/>
            <circle cx="25" cy="22" r="2.5" fill="#1677ff"/>
            <rect x="14" y="27" width="12" height="2.5" rx="1.25" fill="#1677ff"/>
          </svg>
        </div>
        <div class="empty-title">有什么可以帮你的？</div>
        <div class="empty-desc">选择模型即可开始问答，选择项目可启用工具调用和知识库</div>
      </div>

      <!-- 消息加载骨架屏 -->
      <div v-if="loadingMessages" class="messages-loading">
        <div v-for="i in 3" :key="i" class="msg-skeleton" :class="i % 2 === 0 ? 'right' : 'left'">
          <div class="msg-skeleton-bubble"></div>
        </div>
      </div>

      <!-- 消息列表 -->
      <div v-for="(msg, index) in messages" :key="index" class="message-item" :class="msg.role">
        <template v-if="msg.role === 'user'">
          <div class="user-bubble">{{ msg.content }}</div>
        </template>
        <template v-else>
          <div class="ai-message">
            <!-- 进度时间线 -->
            <ChatProgress v-if="msg.progressNodes && msg.progressNodes.length > 0" :nodes="msg.progressNodes" />
            <!-- 工具调用 -->
            <div v-if="msg.tool_calls && msg.tool_calls.length > 0" class="tool-calls-section">
              <div v-for="(tc, ti) in msg.tool_calls" :key="ti" class="tool-call-card" :class="tc.status">
                <div class="tool-call-header">
                  <LoadingOutlined v-if="tc.status === 'running'" class="spin" />
                  <CheckCircleOutlined v-else-if="tc.status === 'success'" class="success" />
                  <CloseCircleOutlined v-else class="error" />
                  <span class="tool-name">{{ getToolDisplayName(tc.name) }}</span>
                  <span v-if="tc.duration" class="tool-duration">{{ tc.duration }}s</span>
                </div>
                <div v-if="tc.result && tc.status === 'success'" class="tool-result-preview">
                  {{ typeof tc.result === 'string' ? tc.result.slice(0, 200) : JSON.stringify(tc.result).slice(0, 200) }}
                </div>
              </div>
            </div>
            <!-- 打字指示器 -->
            <div v-if="!msg.content && isLoading && (!msg.tool_calls || msg.tool_calls.length === 0) && (!msg.progressNodes || !msg.progressNodes.some(n => n.status === 'running'))" class="typing-indicator">
              <span></span><span></span><span></span>
            </div>
            <!-- 回答内容 -->
            <MdView v-if="msg.content" class="message-content" :content="msg.content" />
            <!-- 知识库引用 -->
            <div v-if="msg.knowledge_results && msg.knowledge_results.length" class="knowledge-refs">
              <div class="refs-header" @click="msg._refsCollapsed = !msg._refsCollapsed">
                <span class="refs-title">参考资料 ({{ msg.knowledge_results.length }})</span>
                <span class="refs-toggle">{{ msg._refsCollapsed ? '展开' : '收起' }}</span>
              </div>
              <div v-show="!msg._refsCollapsed" class="refs-list">
                <div v-for="(ref, ri) in msg.knowledge_results" :key="ri" class="ref-item">
                  <span class="ref-index">{{ ri + 1 }}.</span>
                  <span class="ref-title">{{ ref.title }}</span>
                  <span v-if="ref.score" class="ref-score">{{ (ref.score * 100).toFixed(0) }}%</span>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- 底部输入区 -->
    <div class="input-area">
      <div class="input-wrapper">
        <a-textarea
          v-model:value="inputMessage"
          placeholder="输入你的问题，按 Enter 发送，Shift+Enter 换行"
          :rows="2"
          :disabled="isLoading"
          @keydown="handleKeydown"
          class="chat-textarea"
        />
        <div class="input-actions">
          <button v-if="isLoading" class="btn stop-btn" @click="stopGeneration">
            <StopOutlined /> 停止
          </button>
          <button v-else class="btn send-btn" :disabled="!inputMessage.trim()" @click="sendMessage">
            发送 <SendOutlined />
          </button>
        </div>
      </div>
      <div class="input-footer">
        <span>{{ selectedProjectId ? '已关联项目 · 支持工具调用和知识库' : '未选择项目（仅通用问答）' }}</span>
      </div>
    </div>
</div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { SendOutlined, StopOutlined, WarningOutlined, LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined, ReloadOutlined, SearchOutlined, EditOutlined, DeleteOutlined, ThunderboltOutlined } from '@ant-design/icons-vue'
import { chatStream, listChatSessions, getChatSession, deleteChatSession, renameChatSession, reloadSkills, type ChatMessage, type KnowledgeResult, type ToolCall, type ChatSession as ChatSessionType } from '@/api/chat'
import { getProjects, type Project } from '@/api/projects'
import { getLLMConfigs, type LLMConfig } from '@/api/llm'
import { llmCapabilitiesApi, type ModelCapabilities } from '@/api/llmCapabilities'
import ChatProgress, { type ProgressNode } from '@/components/ChatProgress.vue'
import MdView from '@/components/MdView.vue'

interface DisplayMessage extends ChatMessage {
  knowledge_results?: KnowledgeResult[]
  tool_calls?: ToolCall[]
  progressNodes?: ProgressNode[]
  _refsCollapsed?: boolean
}

const projects = ref<Project[]>([])
const llmConfigs = ref<LLMConfig[]>([])
const selectedProjectId = ref<number | undefined>()
const selectedLlmConfigId = ref<number | undefined>()
const useKnowledge = ref(true)
const inputMessage = ref('')
const messages = ref<DisplayMessage[]>([])
const isLoading = ref(false)
const messagesContainer = ref<HTMLElement>()
const abortController = ref<AbortController | null>(null)
const degradeWarning = ref('')
const probingCaps = ref(false)
const showModelSelector = ref(false)

// 历史记录相关
const sessions = ref<ChatSessionType[]>([])
const currentSessionId = ref<number | null>(null)
const historyDrawerVisible = ref(false)
const sessionSearch = ref('')
const loadingSessions = ref(false)
const loadingMessages = ref(false)
const reloadingSkills = ref(false)

const filteredSessions = computed(() => {
  if (!sessionSearch.value) return sessions.value
  const kw = sessionSearch.value.toLowerCase()
  return sessions.value.filter(s => s.title.toLowerCase().includes(kw))
})

const toolNameMap: Record<string, string> = {
  query_project_stats: '项目统计', list_cases: '查询用例', list_defects: '查询缺陷',
  analyze_defects: '缺陷分析', search_knowledge: '知识库检索', create_defect: '创建缺陷',
  list_api_cases: '查询接口用例', list_test_plans: '查询测试计划', list_scripts: '查询脚本',
  list_versions: '查询版本', list_requirements: '查询需求', list_reports: '查询报告',
  list_api_definitions: '查询接口定义', list_api_scenarios: '查询接口场景',
  list_api_executions: '查询执行记录', query_quality_metrics: '质量指标',
}

onMounted(async () => {
  await loadProjects()
  await loadLLMConfigs()
  await loadSessions()
})

async function loadProjects() {
  try {
    projects.value = await getProjects()
    // 不自动选中项目，用户可选择项目或保持通用问答模式
  } catch (e) { console.error('加载项目失败', e) }
}

async function loadLLMConfigs() {
  try {
    const configs = await getLLMConfigs()
    llmConfigs.value = configs
    const defaultConfig = configs.find((c: any) => c.is_default)
    if (defaultConfig) {
      selectedLlmConfigId.value = defaultConfig.id
      checkModelCapabilities(defaultConfig.id)
    }
  } catch (e) { console.error('加载模型失败', e) }
}

async function checkModelCapabilities(configId: number, force = false) {
  try {
    const caps: ModelCapabilities = await llmCapabilitiesApi.get(configId, force)
    const warnings: string[] = []
    if (!caps.function_calling) warnings.push('Function Calling')
    if (!caps.skill_supported) warnings.push('Skill')
    if (!caps.mcp_supported) warnings.push('MCP 工具')
    if (warnings.length > 0) {
      degradeWarning.value = `当前模型不支持 ${warnings.join('、')}，已降级为普通问答`
    } else {
      degradeWarning.value = ''
    }
  } catch (e) {
    console.error('模型能力检测失败', e)
  }
}

async function reprobeCapabilities() {
  if (!selectedLlmConfigId.value) return
  probingCaps.value = true
  try {
    await checkModelCapabilities(selectedLlmConfigId.value, true)
    message.success('模型能力重新检测完成')
  } finally {
    probingCaps.value = false
  }
}

function handleProjectChange() {
  if (!selectedProjectId.value) {
    useKnowledge.value = false
  }
}

async function handleModelChange() {
  if (selectedLlmConfigId.value) {
    await checkModelCapabilities(selectedLlmConfigId.value)
  }
}

function newChat() {
  messages.value = []
  inputMessage.value = ''
  currentSessionId.value = null
}

function openHistoryDrawer() {
  historyDrawerVisible.value = true
  // 打开时立即加载，避免等动画结束后才加载导致抖动
  loadSessions()
}

async function loadSessions() {
  loadingSessions.value = true
  try {
    const res = await listChatSessions(undefined, 1, 100)
    sessions.value = res.items || []
  } catch (e) {
    console.error('加载会话列表失败', e)
  } finally {
    loadingSessions.value = false
  }
}

/**
 * 规范化历史进度节点：按 node 去重保留最终状态，已完成消息的 running 节点强制标记为 done
 */
function normalizeHistoryProgress(progress: any[], hasContent: boolean): ProgressNode[] {
  if (!progress || progress.length === 0) return []
  const map = new Map<string, ProgressNode>()
  for (const p of progress) {
    const node = p.node || p.label || 'unknown'
    map.set(node, {
      node: p.node || node,
      label: p.label || node,
      status: p.status || 'done',
      detail: p.detail,
      duration: p.duration,
    })
  }
  const nodes = Array.from(map.values())
  // 历史消息均已完成，若存在 running 节点则强制标记为 done（异常中断场景兜底）
  if (hasContent) {
    for (const n of nodes) {
      if (n.status === 'running') n.status = 'done'
    }
  }
  return nodes
}

async function loadSession(sessionId: number) {
  if (isLoading.value) {
    message.warning('请等待当前回答完成')
    return
  }
  loadingMessages.value = true
  try {
    const res = await getChatSession(sessionId)
    currentSessionId.value = sessionId
    const loaded = (res.messages || []).map((m: any) => ({
      role: m.role,
      content: m.content || '',
      knowledge_results: m.knowledge_results,
      tool_calls: m.tool_calls,
      progressNodes: normalizeHistoryProgress(m.progress, !!(m.content)),
      _refsCollapsed: true,
    }))
    if (res.session) {
      selectedProjectId.value = res.session.project_id || undefined
      selectedLlmConfigId.value = res.session.llm_config_id || undefined
      useKnowledge.value = res.session.use_knowledge
    }
    historyDrawerVisible.value = false
    await nextTick()
    messages.value = loaded
    loadingMessages.value = false
    await nextTick()
    await scrollToBottom()
  } catch (e) {
    loadingMessages.value = false
    console.error('加载会话失败', e)
    message.error('加载会话失败')
  }
}

async function deleteSession(sessionId: number) {
  Modal.confirm({
    title: '确认删除',
    content: '确定要删除这个对话吗？',
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      try {
        await deleteChatSession(sessionId)
        if (currentSessionId.value === sessionId) {
          newChat()
        }
        await loadSessions()
        message.success('已删除')
      } catch (e) {
        message.error('删除失败')
      }
    },
  })
}

function renameSession(session: ChatSessionType) {
  const newTitle = window.prompt('请输入新的对话名称', session.title)
  if (newTitle && newTitle.trim() && newTitle.trim() !== session.title) {
    renameChatSession(session.id, newTitle.trim()).then(() => {
      loadSessions()
      message.success('已重命名')
    }).catch(() => message.error('重命名失败'))
  }
}

async function handleReloadSkills() {
  reloadingSkills.value = true
  try {
    const res = await reloadSkills()
    message.success(res.message || `已刷新 ${res.count} 个 Skill`)
  } catch (e) {
    message.error('刷新 Skill 失败')
  } finally {
    reloadingSkills.value = false
  }
}

function formatTime(dt?: string): string {
  if (!dt) return ''
  const d = new Date(dt)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  if (diff < 604800000) return `${Math.floor(diff / 86400000)}天前`
  return `${d.getMonth() + 1}/${d.getDate()}`
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
}

function getToolDisplayName(name: string): string {
  if (name.includes('__')) {
    const [conn, tool] = name.split('__')
    return `[${conn}] ${toolNameMap[tool] || tool}`
  }
  return toolNameMap[name] || name
}

async function scrollToBottom() {
  await nextTick()
  if (messagesContainer.value) messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
}

function stopGeneration() {
  if (abortController.value) { abortController.value.abort(); abortController.value = null }
  isLoading.value = false
}

async function sendMessage() {
  const text = inputMessage.value.trim()
  if (!text || isLoading.value) return
  inputMessage.value = ''
  await nextTick()
  isLoading.value = true
  messages.value.push({ role: 'user', content: text })
  await scrollToBottom()
  const aiMessage: DisplayMessage = { role: 'assistant', content: '', tool_calls: [], progressNodes: [] }
  messages.value.push(aiMessage)
  const aiIndex = messages.value.length - 1
  const history = messages.value.slice(0, -1).map((m) => ({ role: m.role, content: m.content }))
  abortController.value = new AbortController()

  await chatStream(
    { message: text, project_id: selectedProjectId.value, llm_config_id: selectedLlmConfigId.value, history, use_knowledge: useKnowledge.value, stream: true, session_id: currentSessionId.value || undefined },
    {
      onSession: (sid: number) => {
        currentSessionId.value = sid
        loadSessions()
      },
      onContent: (chunk) => { messages.value[aiIndex].content += chunk; scrollToBottom() },
      onDone: () => { isLoading.value = false; abortController.value = null; scrollToBottom() },
      onError: (error) => { messages.value[aiIndex].content += `\n\n[错误] ${error}`; isLoading.value = false; abortController.value = null; message.error(error) },
      onToolCall: (toolCall) => {
        if (!messages.value[aiIndex].tool_calls) messages.value[aiIndex].tool_calls = []
        messages.value[aiIndex].tool_calls!.push({ ...toolCall, status: 'running' })
        scrollToBottom()
      },
      onToolResult: (toolCall) => {
        const calls = messages.value[aiIndex].tool_calls
        if (calls && calls.length > 0) {
          const lastCall = calls[calls.length - 1]
          if (lastCall.name === toolCall.name) { lastCall.status = toolCall.status || 'success'; lastCall.result = toolCall.result; lastCall.duration = toolCall.duration }
        }
        scrollToBottom()
      },
      onKnowledge: (results) => { messages.value[aiIndex].knowledge_results = results; messages.value[aiIndex]._refsCollapsed = true; scrollToBottom() },
      onProgressPlan: (steps) => {
        messages.value[aiIndex].progressNodes = steps.map((s: any) => ({
          node: s.node, label: s.label, status: s.status, duration: s.duration,
        }))
        scrollToBottom()
      },
      onProgress: (p) => {
        if (!messages.value[aiIndex].progressNodes) messages.value[aiIndex].progressNodes = []
        const nodes = messages.value[aiIndex].progressNodes!
        // tool_done 事件：合并到对应的 tool_calling 节点，标记为完成
        if (p.node === 'tool_done') {
          const calling = nodes.find(n => n.node === 'tool_calling' && n.status === 'running')
          if (calling) {
            calling.status = 'done'
            calling.label = p.label
            calling.detail = p.detail
            calling.duration = p.detail
            scrollToBottom()
            return
          }
        }
        // 相同 node 的 running/done 合并
        const existing = nodes.find(n => n.node === p.node && n.status === 'running')
        if (existing && p.status === 'done') {
          existing.status = 'done'
          existing.label = p.label
          existing.detail = p.detail
        } else {
          nodes.push({ node: p.node, label: p.label, status: p.status as any, detail: p.detail })
        }
        scrollToBottom()
      },
    },
    abortController.value.signal,
  )
}
</script>

<style scoped>
.dashboard-immersive {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 64px);
  background: #fff;
  overflow: hidden;
}
.icon-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #4e5969;
  transition: all 0.15s;
}
.icon-btn:hover {
  background: #f2f3f5;
  color: #1677ff;
}
.drawer-search {
  margin-bottom: 12px;
}
.drawer-session-list {
  height: calc(100vh - 200px);
  overflow-y: auto;
}
.session-skeleton-list {
  padding: 4px 0;
}
.session-skeleton-item {
  padding: 12px;
  margin-bottom: 4px;
  border-radius: 8px;
}
.skeleton-line {
  height: 12px;
  border-radius: 4px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.5s infinite;
}
.skeleton-title { width: 70%; margin-bottom: 8px; }
.skeleton-meta { width: 40%; height: 10px; }
@keyframes skeleton-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
.session-loading, .session-empty {
  text-align: center;
  padding: 32px 0;
  color: #999;
  font-size: 13px;
}
.session-item {
  position: relative;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  transition: background 0.15s;
  border: 1px solid transparent;
}
.session-item:hover {
  background: #f7f8fa;
  border-color: #e5e6eb;
}
.session-item.active {
  background: #e8f3ff;
  border-color: #c6e2ff;
}
.session-item-title {
  font-size: 13px;
  color: #1f2329;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 48px;
  font-weight: 500;
}
.session-item-meta {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #86909c;
  margin-top: 6px;
}
.session-item-actions {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  display: none;
  gap: 2px;
}
.session-item:hover .session-item-actions {
  display: flex;
}
.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  height: 48px;
  border-bottom: 1px solid #f0f0f0;
  background: #fff;
  flex-shrink: 0;
}
.top-bar-left { display: flex; align-items: center; gap: 12px; }
.control-select { min-width: 140px; }
.knowledge-checkbox { font-size: 13px; }
.top-bar-right { display: flex; align-items: center; gap: 12px; }
.app-title { font-size: 14px; font-weight: 600; color: #1f2329; }
.degrade-banner {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 20px; background: #fffbe6; border-bottom: 1px solid #ffe58f;
  font-size: 13px; color: #d48806;
  flex-shrink: 0;
}
.warn-icon { color: #faad14; }
.banner-close { margin-left: auto; cursor: pointer; font-size: 18px; color: #d48806; }
.chat-container {
  flex: 1; overflow-y: auto; padding: 24px 0;
  max-width: 860px; width: 100%; margin: 0 auto;
  min-height: 0;
}
.empty-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 100%; gap: 16px;
}
.empty-logo { opacity: 0.8; }
.empty-title { font-size: 22px; font-weight: 600; color: #1f2329; }
.empty-desc { font-size: 14px; color: #86909c; }
.messages-loading { padding: 0 20px; }
.msg-skeleton { display: flex; margin-bottom: 20px; }
.msg-skeleton.left { justify-content: flex-start; }
.msg-skeleton.right { justify-content: flex-end; }
.msg-skeleton-bubble {
  width: 60%; height: 40px; border-radius: 12px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.5s infinite;
}
.message-item { display: flex; margin-bottom: 20px; padding: 0 20px; }
.message-item.user { justify-content: flex-end; }
.user-bubble {
  background: #e6f4ff; color: #1f2329; padding: 10px 16px;
  border-radius: 12px; max-width: 70%; font-size: 14px; line-height: 1.6;
}
.ai-message { max-width: 85%; }
.tool-calls-section { margin-bottom: 12px; }
.tool-call-card {
  background: #fafbfc; border: 1px solid #e8e8e8; border-radius: 8px;
  padding: 8px 12px; margin-bottom: 6px; font-size: 13px;
}
.tool-call-header { display: flex; align-items: center; gap: 8px; }
.tool-name { font-weight: 500; color: #1f2329; }
.tool-duration { color: #86909c; font-size: 12px; margin-left: auto; }
.tool-result-preview { color: #86909c; font-size: 12px; margin-top: 4px; overflow: hidden; text-overflow: ellipsis; }
.spin { animation: spin 1s linear infinite; color: #1677ff; }
@keyframes spin { from { transform: rotate(0); } to { transform: rotate(360deg); } }
.success { color: #52c41a; }
.error { color: #ff4d4f; }
.typing-indicator { display: flex; gap: 4px; padding: 8px 0; }
.typing-indicator span {
  width: 8px; height: 8px; border-radius: 50%; background: #c9cdd4;
  animation: bounce 1.4s infinite ease-in-out both;
}
.typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
.typing-indicator span:nth-child(2) { animation-delay: -0.16s; }
@keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }
.message-content { font-size: 14px; line-height: 1.7; color: #1f2329; word-break: break-word; }
.message-content :deep(h1) { font-size: 20px; margin: 16px 0 8px; font-weight: 600; border-bottom: 1px solid #e8e8e8; padding-bottom: 6px; }
.message-content :deep(h2) { font-size: 17px; margin: 14px 0 8px; font-weight: 600; color: #1677ff; border-left: 3px solid #1677ff; padding-left: 8px; }
.message-content :deep(h3) { font-size: 15px; margin: 12px 0 6px; font-weight: 600; }
.message-content :deep(h4), .message-content :deep(h5), .message-content :deep(h6) { font-size: 14px; margin: 10px 0 4px; font-weight: 600; }
.message-content :deep(p) { margin: 8px 0; }
.message-content :deep(ul), .message-content :deep(ol) { margin: 8px 0; padding-left: 24px; }
.message-content :deep(li) { margin: 4px 0; }
.message-content :deep(strong) { font-weight: 600; }
.message-content :deep(em) { font-style: italic; }
.message-content :deep(blockquote) { margin: 8px 0; padding: 8px 12px; border-left: 4px solid #d9d9d9; background: #fafafa; color: #666; border-radius: 0 4px 4px 0; }
.message-content :deep(code) { background: #f5f5f5; padding: 2px 6px; border-radius: 4px; font-size: 13px; font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace; }
.message-content :deep(pre) { background: #1e1e1e; color: #d4d4d4; padding: 12px 16px; border-radius: 8px; overflow-x: auto; margin: 10px 0; font-size: 13px; line-height: 1.5; }
.message-content :deep(pre code) { background: none; padding: 0; color: inherit; font-size: 13px; }
.message-content :deep(table) { border-collapse: collapse; margin: 10px 0; width: 100%; }
.message-content :deep(th), .message-content :deep(td) { border: 1px solid #e8e8e8; padding: 8px 12px; text-align: left; }
.message-content :deep(th) { background: #fafafa; font-weight: 600; }
.message-content :deep(a) { color: #1677ff; text-decoration: none; }
.message-content :deep(a:hover) { text-decoration: underline; }
.message-content :deep(hr) { border: none; border-top: 1px solid #e8e8e8; margin: 16px 0; }
.knowledge-refs { margin-top: 12px; background: #f6ffed; border-radius: 8px; border: 1px solid #b7eb8f; overflow: hidden; }
.refs-header { display: flex; align-items: center; justify-content: space-between; padding: 8px 14px; cursor: pointer; }
.refs-title { font-size: 12px; color: #52c41a; font-weight: 600; }
.refs-toggle { font-size: 12px; color: #52c41a; }
.refs-list { padding: 0 14px 10px; }
.ref-item { font-size: 12px; color: #389e0d; padding: 3px 0; display: flex; align-items: center; gap: 6px; }
.ref-index { color: #95de64; }
.ref-title { flex: 1; }
.ref-score { color: #95de64; font-size: 11px; }
.input-area { padding: 16px 20px 20px; border-top: 1px solid #f0f0f0; background: #fff; flex-shrink: 0; }
.input-wrapper {
  max-width: 860px; margin: 0 auto; position: relative;
  border: 1px solid #d9d9d9; border-radius: 12px; overflow: hidden;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.input-wrapper:focus-within { border-color: #1677ff; box-shadow: 0 0 0 2px rgba(22,119,255,0.1); }
.chat-textarea { border: none !important; box-shadow: none !important; resize: none; padding: 12px 16px !important; }
.input-actions { display: flex; justify-content: flex-end; padding: 0 12px 10px; }
.btn {
  display: flex; align-items: center; gap: 6px; padding: 6px 16px;
  border-radius: 8px; border: none; cursor: pointer; font-size: 13px; font-weight: 500;
  transition: all 0.2s;
}
.send-btn { background: linear-gradient(135deg, #1677ff, #4096ff); color: #fff; }
.send-btn:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(22,119,255,0.3); }
.send-btn:disabled { background: #c9cdd4; cursor: not-allowed; }
.stop-btn { background: #fff; color: #ff4d4f; border: 1px solid #ff4d4f; }
.stop-btn:hover { background: #fff1f0; }
.input-footer { max-width: 860px; margin: 8px auto 0; text-align: center; font-size: 12px; color: #86909c; }
</style>
