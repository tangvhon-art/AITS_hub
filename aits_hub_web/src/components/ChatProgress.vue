<template>
  <div class="chat-progress" v-if="nodes.length > 0">
    <div class="progress-header" @click="collapsed = !collapsed">
      <span class="progress-title">
        <LoadingOutlined v-if="isRunning" class="spin-icon" />
        <CheckCircleOutlined v-else class="done-icon" />
        处理进度
      </span>
      <span class="progress-summary" v-if="!isRunning && !collapsed">
        调用 {{ toolCount }} 个工具，耗时 {{ totalDuration }}
      </span>
      <span class="collapse-icon">{{ collapsed ? '展开' : '收起' }}</span>
    </div>
    <div class="progress-body" v-show="!collapsed">
      <div
        v-for="(node, idx) in nodes"
        :key="idx"
        class="progress-node"
        :class="node.status"
      >
        <div class="node-icon">
          <CheckCircleOutlined v-if="node.status === 'done'" class="icon-done" />
          <LoadingOutlined v-else-if="node.status === 'running'" class="icon-running spin" />
          <CloseCircleOutlined v-else-if="node.status === 'error'" class="icon-error" />
          <ClockCircleOutlined v-else class="icon-pending" />
        </div>
        <div class="node-content">
          <span class="node-label">{{ node.label }}</span>
          <span class="node-detail" v-if="node.detail">{{ node.detail }}</span>
        </div>
        <span class="node-duration" v-if="node.status === 'done' && node.duration">{{ node.duration }}</span>
      </div>
    </div>
    <div class="progress-body-collapsed" v-show="collapsed && !isRunning">
      <span class="summary-text">✓ 已完成（调用 {{ toolCount }} 个工具，耗时 {{ totalDuration }}）</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined } from '@ant-design/icons-vue'

export interface ProgressNode {
  node: string
  label: string
  status: 'running' | 'done' | 'error' | 'pending'
  detail?: string
  duration?: string
}

const props = defineProps<{
  nodes: ProgressNode[]
}>()

const collapsed = ref(false)

const isRunning = computed(() => props.nodes.some(n => n.status === 'running'))

// 进度全部完成后自动收起
watch(isRunning, (running) => {
  if (!running && props.nodes.length > 0) {
    setTimeout(() => { collapsed.value = true }, 800)
  }
})

const toolCount = computed(() => props.nodes.filter(n => n.node && n.node.startsWith('tool_')).length)
const totalDuration = computed(() => {
  const done = props.nodes.filter(n => n.status === 'done' && n.duration)
  if (done.length === 0) return '0s'
  return done[done.length - 1].duration || '0s'
})
</script>

<style scoped>
.chat-progress {
  background: #fafbfc;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  margin-bottom: 12px;
  overflow: hidden;
}
.progress-header {
  display: flex;
  align-items: center;
  padding: 10px 14px;
  cursor: pointer;
  background: #fff;
  border-bottom: 1px solid #f0f0f0;
  font-size: 13px;
}
.progress-title {
  font-weight: 600;
  color: #1f2329;
  display: flex;
  align-items: center;
  gap: 6px;
}
.spin-icon { color: #1677ff; }
.done-icon { color: #52c41a; }
.progress-summary {
  margin-left: auto;
  color: #86909c;
  font-size: 12px;
}
.collapse-icon {
  margin-left: 12px;
  color: #1677ff;
  font-size: 12px;
}
.progress-body {
  padding: 8px 14px;
}
.progress-node {
  display: flex;
  align-items: center;
  padding: 6px 0;
  gap: 10px;
  font-size: 13px;
}
.node-icon { width: 16px; display: flex; justify-content: center; }
.icon-done { color: #52c41a; }
.icon-running { color: #1677ff; }
.icon-error { color: #ff4d4f; }
.icon-pending { color: #c9cdd4; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0); } to { transform: rotate(360deg); } }
.node-content { flex: 1; display: flex; align-items: center; gap: 8px; }
.node-label { color: #1f2329; }
.node-detail { color: #86909c; font-size: 12px; }
.node-duration { color: #86909c; font-size: 12px; }
.progress-node.pending .node-label { color: #c9cdd4; }
.progress-body-collapsed {
  padding: 8px 14px;
  font-size: 12px;
  color: #52c41a;
}
</style>
