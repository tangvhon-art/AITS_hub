<template>
  <div class="dashboard-container">
    <!-- 顶部栏 -->
    <div class="dashboard-header">
      <div class="header-left">
        <h2 class="page-title">智能助手</h2>
        <span class="header-subtitle">AI 驱动的测试管理助手</span>
      </div>
      <div class="header-right">
        <a-select
          v-model:value="selectedProjectId"
          placeholder="选择项目"
          style="width: 200px"
          allow-clear
          @change="handleProjectChange"
        >
          <a-select-option v-for="p in projects" :key="p.id" :value="p.id">
            {{ p.name }}
          </a-select-option>
        </a-select>
        <a-select
          v-model:value="selectedLlmConfigId"
          placeholder="选择模型"
          style="width: 180px; margin-left: 12px"
          allow-clear
        >
          <a-select-option v-for="c in llmConfigs" :key="c.id" :value="c.id">
            {{ c.name }} ({{ c.provider }})
          </a-select-option>
        </a-select>
        <a-switch
          v-model:checked="useKnowledge"
          checked-children="知识库"
          un-checked-children="关闭"
          style="margin-left: 12px"
        />
      </div>
    </div>

    <div class="dashboard-body">
      <!-- 左侧快捷入口 -->
      <div class="sidebar">
        <div class="sidebar-section">
          <h4>快捷功能</h4>
          <div class="quick-cards">
            <div class="quick-card" @click="goTo('cases')">
              <div class="card-icon">📋</div>
              <div class="card-text">用例管理</div>
            </div>
            <div class="quick-card" @click="goTo('defects')">
              <div class="card-icon">🐛</div>
              <div class="card-text">缺陷管理</div>
            </div>
            <div class="quick-card" @click="goTo('reports')">
              <div class="card-icon">📊</div>
              <div class="card-text">测试报告</div>
            </div>
            <div class="quick-card" @click="goTo('knowledge')">
              <div class="card-icon">📚</div>
              <div class="card-text">知识库</div>
            </div>
            <div class="quick-card" @click="goTo('suites')">
              <div class="card-icon">⚡</div>
              <div class="card-text">自动化编排</div>
            </div>
            <div class="quick-card" @click="goTo('scripts')">
              <div class="card-icon">📝</div>
              <div class="card-text">脚本库</div>
            </div>
          </div>
        </div>

        <div class="sidebar-section">
          <h4>常用提问</h4>
          <div class="suggestion-list">
            <a-tag
              v-for="s in suggestions"
              :key="s"
              class="suggestion-tag"
              @click="sendSuggestion(s)"
            >
              {{ s }}
            </a-tag>
          </div>
        </div>
      </div>

      <!-- 右侧 Chat 区 -->
      <div class="chat-panel">
        <div class="chat-messages" ref="messagesContainer">
          <div v-if="messages.length === 0" class="empty-chat">
            <div class="empty-icon">
              <svg viewBox="0 0 120 120" width="100" height="100">
                <!-- 机器人天线 -->
                <line x1="60" y1="15" x2="60" y2="28" stroke="#52c41a" stroke-width="3" stroke-linecap="round"/>
                <circle cx="60" cy="12" r="5" fill="#ff7a45"/>
                <!-- 机器人头部 -->
                <rect x="25" y="28" width="70" height="55" rx="12" fill="#f0f5ff" stroke="#52c41a" stroke-width="3"/>
                <!-- 眼睛 -->
                <circle cx="45" cy="52" r="10" fill="#fff" stroke="#52c41a" stroke-width="2"/>
                <circle cx="45" cy="52" r="5" fill="#52c41a"/>
                <circle cx="75" cy="52" r="10" fill="#fff" stroke="#52c41a" stroke-width="2"/>
                <circle cx="75" cy="52" r="5" fill="#52c41a"/>
                <!-- 嘴巴 -->
                <rect x="42" y="68" width="36" height="8" rx="4" fill="#52c41a"/>
                <!-- 耳朵 -->
                <rect x="18" y="42" width="10" height="20" rx="4" fill="#52c41a"/>
                <rect x="92" y="42" width="10" height="20" rx="4" fill="#52c41a"/>
                <!-- 身体 -->
                <rect x="35" y="85" width="50" height="25" rx="8" fill="#f0f5ff" stroke="#52c41a" stroke-width="3"/>
                <circle cx="50" cy="97" r="4" fill="#ff7a45"/>
                <circle cx="60" cy="97" r="4" fill="#1890ff"/>
                <circle cx="70" cy="97" r="4" fill="#52c41a"/>
              </svg>
            </div>
            <div class="empty-title">你好，我是 AITS 智能助手</div>
            <div class="empty-desc">
              我可以帮你解答测试问题、分析缺陷、生成用例思路，<br />
              选择项目后还能基于知识库回答项目相关问题。
            </div>
          </div>

          <div
            v-for="(msg, index) in messages"
            :key="index"
            class="message-item"
            :class="msg.role"
          >
            <div class="message-avatar" :class="{ 'avatar-ai': msg.role === 'assistant' }">
              <template v-if="msg.role === 'assistant'">
                <svg viewBox="0 0 40 40" width="24" height="24">
                  <circle cx="20" cy="6" r="3" fill="#ff7a45"/>
                  <line x1="20" y1="9" x2="20" y2="14" stroke="#fff" stroke-width="2"/>
                  <rect x="8" y="14" width="24" height="18" rx="5" fill="#fff"/>
                  <circle cx="15" cy="22" r="3" fill="#52c41a"/>
                  <circle cx="25" cy="22" r="3" fill="#52c41a"/>
                  <rect x="14" y="27" width="12" height="3" rx="1.5" fill="#52c41a"/>
                </svg>
              </template>
              <template v-else>我</template>
            </div>
            <div class="message-bubble">
              <div v-if="msg.role === 'assistant' && !msg.content && isLoading && (!msg.tool_calls || msg.tool_calls.length === 0)" class="typing-indicator">
                <span></span><span></span><span></span>
              </div>
              <div v-else-if="msg.content" class="message-content" v-html="formatContent(msg.content)"></div>

              <!-- 工具调用展示 -->
              <div v-if="msg.tool_calls && msg.tool_calls.length > 0" class="tool-calls">
                <div
                  v-for="(tc, ti) in msg.tool_calls"
                  :key="ti"
                  class="tool-call-item"
                  :class="tc.status"
                >
                  <div class="tool-call-header">
                    <span class="tool-icon">
                      <a-spin v-if="tc.status === 'running'" size="small" />
                      <span v-else-if="tc.status === 'success'" class="tool-success">✓</span>
                      <span v-else class="tool-failed">✗</span>
                    </span>
                    <span class="tool-name">{{ getToolDisplayName(tc.name) }}</span>
                  </div>
                  <div v-if="tc.result && tc.status === 'success'" class="tool-result">
                    {{ typeof tc.result === 'string' ? tc.result : JSON.stringify(tc.result) }}
                  </div>
                </div>
              </div>

              <div v-if="msg.knowledge_results && msg.knowledge_results.length" class="message-refs">
                <div class="refs-title">参考资料：</div>
                <div
                  v-for="(ref, ri) in msg.knowledge_results"
                  :key="ri"
                  class="ref-item"
                >
                  {{ ref.title }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="chat-input-area">
          <div class="input-row">
            <a-textarea
              v-model:value="inputMessage"
              placeholder="输入你的问题，按 Enter 发送，Shift+Enter 换行"
              :rows="2"
              :disabled="isLoading"
              @keydown="handleKeydown"
              class="chat-textarea"
            />
            <div class="input-buttons">
              <a-button
                v-if="isLoading"
                danger
                @click="stopGeneration"
                class="stop-btn"
              >
                停止
              </a-button>
              <a-button
                v-else
                type="primary"
                @click="sendMessage"
                :disabled="!inputMessage.trim()"
                class="send-btn"
              >
                发送
              </a-button>
            </div>
          </div>
          <div class="input-hint-row">
            <span class="input-hint">
              {{ selectedProjectId ? '已关联项目，支持知识库问答和工具调用' : '未选择项目（仅通用问答）' }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { chatStream, type ChatMessage, type KnowledgeResult, type ToolCall } from '@/api/chat'
import { getProjects, type Project } from '@/api/projects'
import { getLLMConfigs, type LLMConfig } from '@/api/llm'

const router = useRouter()

interface DisplayMessage extends ChatMessage {
  knowledge_results?: KnowledgeResult[]
  tool_calls?: ToolCall[]
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

const suggestions = [
  '什么是边界值分析法？',
  '帮我生成登录功能的测试用例',
  '分析一下当前项目的缺陷情况',
  '生成一份测试报告',
  '查询项目的用例统计',
]

// 工具名称映射
const toolNameMap: Record<string, string> = {
  generate_test_cases: '生成测试用例',
  analyze_defects: '缺陷分析',
  generate_report: '生成测试报告',
  query_project_stats: '查询项目统计',
  search_knowledge: '知识库检索',
  list_cases: '查询用例列表',
  list_defects: '查询缺陷列表',
  create_defect: '创建缺陷',
}

onMounted(async () => {
  await loadProjects()
  await loadLLMConfigs()
})

async function loadProjects() {
  try {
    projects.value = await getProjects()
    if (projects.value.length > 0) {
      selectedProjectId.value = projects.value[0].id
    }
  } catch (e) {
    console.error('加载项目失败', e)
  }
}

async function loadLLMConfigs() {
  try {
    const configs = await getLLMConfigs()
    llmConfigs.value = configs
    const defaultConfig = configs.find((c: any) => c.is_default)
    if (defaultConfig) {
      selectedLlmConfigId.value = defaultConfig.id
    }
  } catch (e) {
    console.error('加载模型配置失败', e)
  }
}

function handleProjectChange() {
  // 切换项目时清空对话
  // messages.value = []
}

function goTo(type: string) {
  if (!selectedProjectId.value) {
    message.warning('请先选择项目')
    return
  }
  const routes: Record<string, string> = {
    cases: `/projects/${selectedProjectId.value}/cases`,
    defects: `/projects/${selectedProjectId.value}/defects`,
    reports: `/projects/${selectedProjectId.value}/reports`,
    knowledge: `/projects/${selectedProjectId.value}/knowledge`,
    suites: `/projects/${selectedProjectId.value}/suites`,
    scripts: `/projects/${selectedProjectId.value}/scripts`,
  }
  if (routes[type]) {
    router.push(routes[type])
  }
}

function sendSuggestion(text: string) {
  inputMessage.value = text
  sendMessage()
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

function formatContent(content: string): string {
  let html = content
    .replace(/\n/g, '<br/>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  return html
}

function getToolDisplayName(name: string): string {
  return toolNameMap[name] || name
}

async function scrollToBottom() {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

function stopGeneration() {
  if (abortController.value) {
    abortController.value.abort()
    abortController.value = null
  }
  isLoading.value = false
}

async function sendMessage() {
  const text = inputMessage.value.trim()
  if (!text || isLoading.value) return

  // 立即清理输入框
  inputMessage.value = ''
  await nextTick()

  // 设置加载状态（禁用输入框）
  isLoading.value = true

  // 添加用户消息
  messages.value.push({ role: 'user', content: text })
  await scrollToBottom()

  // 添加 AI 消息占位
  const aiMessage: DisplayMessage = { role: 'assistant', content: '', tool_calls: [] }
  messages.value.push(aiMessage)
  const aiIndex = messages.value.length - 1

  // 构建历史（排除最后一条空的 AI 消息）
  const history = messages.value.slice(0, -1).map((m) => ({
    role: m.role,
    content: m.content,
  }))

  // 创建 AbortController
  abortController.value = new AbortController()

  await chatStream(
    {
      message: text,
      project_id: selectedProjectId.value,
      llm_config_id: selectedLlmConfigId.value,
      history,
      use_knowledge: useKnowledge.value,
      stream: true,
    },
    {
      onContent: (chunk) => {
        messages.value[aiIndex].content += chunk
        scrollToBottom()
      },
      onDone: () => {
        isLoading.value = false
        abortController.value = null
        scrollToBottom()
      },
      onError: (error) => {
        messages.value[aiIndex].content += `\n\n[错误] ${error}`
        isLoading.value = false
        abortController.value = null
        message.error(error)
      },
      onMetadata: (metadata) => {
        console.log('Chat metadata:', metadata)
      },
      onToolCall: (toolCall) => {
        if (!messages.value[aiIndex].tool_calls) {
          messages.value[aiIndex].tool_calls = []
        }
        messages.value[aiIndex].tool_calls!.push({
          ...toolCall,
          status: 'running',
        })
        scrollToBottom()
      },
      onToolResult: (toolCall) => {
        const calls = messages.value[aiIndex].tool_calls
        if (calls && calls.length > 0) {
          const lastCall = calls[calls.length - 1]
          if (lastCall.name === toolCall.name) {
            lastCall.status = toolCall.status || 'success'
            lastCall.result = toolCall.result
          }
        }
        scrollToBottom()
      },
      onKnowledge: (results) => {
        if (results.length > 0) {
          messages.value[aiIndex].knowledge_results = results
          scrollToBottom()
        }
      },
    },
    abortController.value.signal,
  )
}
</script>

<style scoped>
.dashboard-container {
  height: calc(100vh - 64px);
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: #fff;
  border-bottom: 1px solid #f0f0f0;
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #1f1f1f;
}

.header-subtitle {
  font-size: 13px;
  color: #8c8c8c;
}

.header-right {
  display: flex;
  align-items: center;
}

.dashboard-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.sidebar {
  width: 260px;
  background: #fff;
  border-right: 1px solid #f0f0f0;
  padding: 16px;
  overflow-y: auto;
}

.sidebar-section {
  margin-bottom: 24px;
}

.sidebar-section h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
  color: #1f1f1f;
}

.quick-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.quick-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 8px;
  background: #fafafa;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.quick-card:hover {
  background: #e6f4ff;
  border-color: #91caff;
}

.card-icon {
  font-size: 24px;
  margin-bottom: 4px;
}

.card-text {
  font-size: 12px;
  color: #595959;
}

.suggestion-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.suggestion-tag {
  cursor: pointer;
  text-align: left;
  padding: 6px 10px;
  font-size: 12px;
  white-space: normal;
  line-height: 1.5;
}

.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fff;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.empty-chat {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
}

.empty-icon {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-title {
  font-size: 20px;
  font-weight: 600;
  color: #1f1f1f;
  margin-bottom: 8px;
}

.empty-desc {
  font-size: 14px;
  color: #8c8c8c;
  line-height: 1.8;
}

.message-item {
  display: flex;
  margin-bottom: 20px;
  gap: 12px;
}

.message-item.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}

.message-item.user .message-avatar {
  background: #1677ff;
  color: #fff;
}

.message-item.assistant .message-avatar {
  background: #f6ffed;
  border: 2px solid #52c41a;
}

.message-avatar.avatar-ai {
  padding: 0;
}

.message-bubble {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.7;
  word-break: break-word;
}

.message-item.user .message-bubble {
  background: #1677ff;
  color: #fff;
  border-top-right-radius: 4px;
}

.message-item.assistant .message-bubble {
  background: #f5f5f5;
  color: #1f1f1f;
  border-top-left-radius: 4px;
}

.message-content :deep(code) {
  background: rgba(0, 0, 0, 0.06);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
}

.message-item.user .message-content :deep(code) {
  background: rgba(255, 255, 255, 0.2);
}

.tool-calls {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tool-call-item {
  padding: 8px 12px;
  background: #fafafa;
  border-radius: 8px;
  border-left: 3px solid #d9d9d9;
}

.tool-call-item.running {
  border-left-color: #1677ff;
}

.tool-call-item.success {
  border-left-color: #52c41a;
}

.tool-call-item.failed {
  border-left-color: #ff4d4f;
}

.tool-call-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
  color: #595959;
}

.tool-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
}

.tool-success {
  color: #52c41a;
  font-weight: bold;
}

.tool-failed {
  color: #ff4d4f;
  font-weight: bold;
}

.tool-result {
  margin-top: 6px;
  font-size: 12px;
  color: #8c8c8c;
  line-height: 1.6;
  max-height: 120px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.message-refs {
  margin-top: 12px;
  padding-top: 8px;
  border-top: 1px solid #e8e8e8;
}

.refs-title {
  font-size: 12px;
  color: #8c8c8c;
  margin-bottom: 4px;
}

.ref-item {
  font-size: 12px;
  color: #1677ff;
  padding: 2px 0;
}

.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #bfbfbf;
  animation: typing 1.4s infinite;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%, 60%, 100% {
    opacity: 0.3;
    transform: translateY(0);
  }
  30% {
    opacity: 1;
    transform: translateY(-4px);
  }
}

.chat-input-area {
  padding: 16px 24px;
  border-top: 1px solid #f0f0f0;
  background: #fff;
}

.input-row {
  display: flex;
  align-items: flex-end;
  gap: 12px;
}

.chat-textarea {
  flex: 1;
}

.input-buttons {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.send-btn,
.stop-btn {
  height: 66px;
  min-width: 72px;
  font-size: 15px;
  font-weight: 500;
}

.input-hint-row {
  margin-top: 8px;
}

.input-hint {
  font-size: 12px;
  color: #8c8c8c;
}
</style>
