<template>
  <div class="suite-mind-page">
    <!-- 顶部工具栏 -->
    <div class="mind-toolbar">
      <a-space :size="4" wrap>
        <a-button size="small" @click="goBack"><template #icon><ArrowLeftOutlined /></template>返回</a-button>
        <a-button size="small" @click="refresh">刷新</a-button>
        <a-button size="small" @click="exportXmind">导出 XMind</a-button>
        <a-divider type="vertical" />
        <a-button size="small" @click="toCenter">居中</a-button>
        <a-button size="small" @click="expandAll">展开全部</a-button>
        <a-button size="small" @click="collapseAll">收起全部</a-button>
      </a-space>
    </div>

    <!-- 信息栏 -->
    <div v-if="suiteName" class="mind-info">
      <span class="suite-name">{{ suiteName }}</span>
      <a-tag>共 {{ totalCases }} 条用例</a-tag>
      <a-tag>覆盖 {{ moduleCount }} 个模块</a-tag>
      <span class="tip-text">滚轮/双指缩放 · 拖拽平移 · 悬停节点点击 +/- 收起</span>
    </div>

    <!-- 脑图容器（mind-elixir 挂载点） -->
    <div ref="mapEl" class="mind-map"></div>

    <!-- 用例详情抽屉 -->
    <a-drawer
      v-model:open="detailVisible"
      :title="detailCase?.title || '用例详情'"
      width="480"
    >
      <template v-if="detailCase">
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="优先级">
            <a-tag :color="priorityColor(detailCase.priority)">{{ detailCase.priority }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="模块">{{ detailCase.module || '-' }}</a-descriptions-item>
          <a-descriptions-item label="前置条件">{{ detailCase.preconditions || '无' }}</a-descriptions-item>
          <a-descriptions-item label="步骤">
            <ol v-if="detailCase.stepsList?.length" style="margin: 0; padding-left: 18px;">
              <li v-for="(s, i) in detailCase.stepsList" :key="i">{{ s }}</li>
            </ol>
            <span v-else>无步骤</span>
          </a-descriptions-item>
          <a-descriptions-item label="预期结果">{{ detailCase.expected_result || '无' }}</a-descriptions-item>
          <a-descriptions-item label="所属需求">
            <span>{{ detailCase.req_id ? `需求 #${detailCase.req_id}` : '-' }}</span>
          </a-descriptions-item>
        </a-descriptions>
        <div style="margin-top: 16px; text-align: right;">
          <a-button type="primary" size="small" @click="goEditCase">在用例管理编辑</a-button>
        </div>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { ArrowLeftOutlined } from '@ant-design/icons-vue'
import MindElixir from 'mind-elixir'
import 'mind-elixir/style'
import { getSuiteMind, exportSuiteXmind } from '@/api/caseSuites'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)
const suiteId = Number(route.params.suiteId)

const mapEl = ref<HTMLElement>()
let mind: MindElixir | null = null

const suiteName = ref('')
const totalCases = ref(0)
const moduleCount = ref(0)
const detailVisible = ref(false)
const detailCase = ref<any>(null)

const CASE_DETAIL = new Map<number, any>()

function priorityColor(p: string) {
  return { P0: 'red', P1: 'orange', P2: 'blue', P3: 'default' }[p] || 'default'
}

function escapeHtml(s: string) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' } as any)[c])
}

/** 优先级着色 class */
function prioClass(p: string) {
  return { P0: 'me-p0', P1: 'me-p1', P2: 'me-p2', P3: 'me-p3' }[p] || 'me-p3'
}

/** 用例标题：优先级【Px】/ [Px] 着色，其余转义（不重复加前缀） */
function buildTitleHtml(title: string) {
  const parts = String(title || '').split(/([【\[]P\d[】\]])/g)
  return parts.map((part) => {
    const m = /^[【\[]?(P\d)[】\]]?$/.exec(part)
    if (m && /^[【\[]P\d[】\]]$/.test(part)) return `<span class="me-prio ${prioClass(m[1])}">${part}</span>`
    return escapeHtml(part)
  }).join('')
}

/** 字段节点 HTML（字段名小字 + 内容，对齐 XMind 链式导出：前置条件/测试步骤/预期结果） */
function fieldNodeHtml(name: string, body: string, plain = false) {
  const bodyHtml = plain ? body : escapeHtml(body).replace(/[；;]\s*/g, '<br>')
  return `<div class="me-fldnode"><div class="me-fld-name">${name}</div><div class="me-fld-body">${bodyHtml}</div></div>`
}

/** 用例标题节点 HTML（优先级 [Px] 着色） */
function caseTitleHtml(c: any) {
  return `<div class="me-fldnode"><div class="me-fld-name">用例标题</div><div class="me-fld-body">${buildTitleHtml(c.title)}</div></div>`
}

/**
 * 构建 mind-elixir 数据：链式结构（与 XMind 导出格式一致）
 * 根=用例集名 → 模块 → 用例标题 → 前置条件 → 测试步骤 → 预期结果
 * 每条用例一条链到底（字段链默认折叠，点击用例标题节点展开）
 */
function buildMindData(data: any) {
  CASE_DETAIL.clear()
  // MindElixir.new 返回 { nodeData } 包裹结构，init 也接收该结构
  const md = MindElixir.new(data.root.title)
  const root = md.nodeData
  root.metadata = { kind: 'root' }
  root.expanded = true
  root.children = data.root.children.map((mod: any) => {
    const modNode: any = {
      topic: mod.module,
      id: 'mod-' + Math.random().toString(36).slice(2, 10),
      expanded: true,
      branchColor: '#3370ff',
      metadata: { kind: 'module', module: mod.module },
      children: mod.cases.map((c: any) => {
        CASE_DETAIL.set(c.id, {
          id: c.id,
          title: c.title,
          priority: c.priority,
          module: mod.module,
          preconditions: c.preconditions,
          expected_result: c.expected_result,
          stepsList: c.steps ? c.steps.split(/[；;]\s*/).filter(Boolean) : [],
          req_id: (c as any).req_id,
        })
        return {
          topic: '',
          id: 'case-' + c.id,
          expanded: false,
          metadata: { kind: 'case', caseId: c.id },
          dangerouslySetInnerHTML: caseTitleHtml(c),
          children: [{
            topic: '',
            id: 'pre-' + c.id,
            expanded: false,
            metadata: { kind: 'field', field: 'preconditions', caseId: c.id },
            dangerouslySetInnerHTML: fieldNodeHtml('前置条件', c.preconditions || '无'),
            children: [{
              topic: '',
              id: 'step-' + c.id,
              expanded: false,
              metadata: { kind: 'field', field: 'steps', caseId: c.id },
              dangerouslySetInnerHTML: fieldNodeHtml('测试步骤', c.steps || '无步骤'),
              children: [{
                topic: '',
                id: 'exp-' + c.id,
                expanded: false,
                metadata: { kind: 'field', field: 'expected_result', caseId: c.id },
                dangerouslySetInnerHTML: fieldNodeHtml('预期结果', c.expected_result || '无'),
              }],
            }],
          }],
        }
      }),
    }
    return modNode
  })
  return md
}

/** 飞书式浅色主题 */
const FEISHU_THEME = {
  name: 'feishu',
  type: 'light' as const,
  palette: ['#3370ff'],
  cssVar: {
    '--main-color': '#3370ff',
    '--main-bgcolor': '#ffffff',
    '--main-bgcolor-transparent': 'rgba(255,255,255,0.9)',
    '--color': '#333333',
    '--bgcolor': '#ffffff',
    '--selected': '#4f90f2',
    '--accent-color': '#3370ff',
    '--root-color': '#1f1f1f',
    '--root-bgcolor': 'transparent',
    '--root-border-color': 'transparent',
    '--root-radius': '6px',
    '--main-radius': '4px',
    '--topic-padding': '2px 4px',
    '--node-gap-x': '26px',
    '--node-gap-y': '12px',
    '--main-gap-x': '46px',
    '--main-gap-y': '12px',
    '--map-padding': '30px',
    '--panel-color': '#333',
    '--panel-bgcolor': '#fff',
    '--panel-border-color': '#e5e5e5',
  },
}

/** 飞书式浅灰贝塞尔分支线 */
function branchPath(p: any, sub: boolean) {
  const x1 = p.pL + p.pW
  const y1 = p.pT + p.pH / 2
  const x2 = p.cL
  const y2 = p.cT + p.cH / 2
  const mx = x1 + (x2 - x1) * 0.45
  return `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`
}

function initMind(data: any) {
  if (!mapEl.value) return
  if (mind) {
    mind.destroy()
    mind = null
  }
  mind = new MindElixir({
    el: mapEl.value,
    direction: MindElixir.RIGHT,
    editable: false,
    contextMenu: false,
    toolBar: false,
    keypress: false,
    allowUndo: false,
    scaleMin: 0.2,
    scaleMax: 3,
    alignment: 'root',
    theme: FEISHU_THEME,
    generateMainBranch: (p: any) => branchPath(p, false),
    generateSubBranch: (p: any) => branchPath(p, true),
    handleWheel: (e: WheelEvent) => {
      e.preventDefault()
      e.stopPropagation()
      if (!mind) return
      // 触控板捏合（ctrl/meta）与鼠标滚轮 → 以鼠标为锚点缩放
      if (e.ctrlKey || e.metaKey || Math.abs(e.deltaY) >= 60 || Math.abs(e.deltaX) >= 60) {
        const factor = Math.exp(-(e.deltaY || e.deltaX) * 0.0018)
        const next = Math.min(3, Math.max(0.2, mind.scaleVal * factor))
        if (Math.abs(next - mind.scaleVal) > 1e-4) {
          mind.scale(next, { x: e.clientX, y: e.clientY })
        }
        return
      }
      // 触控板双指滚动 → 平移画布
      mind.move(-e.deltaX, -e.deltaY)
    },
  })
  // editable:false 时 mind-elixir 不会 fire selectNewNode，用容器 click 委托打开用例详情
  // （记录 pointerdown 位置，拖动平移后不触发，避免误开抽屉）
  let downPos: { x: number; y: number } | null = null
  const onDown = (ev: PointerEvent) => { downPos = { x: ev.clientX, y: ev.clientY } }
  const onClick = (ev: MouseEvent) => {
    const dist = downPos ? Math.hypot(ev.clientX - downPos.x, ev.clientY - downPos.y) : 0
    downPos = null
    if (dist > 5) return
    const tpc = (ev.target as HTMLElement).closest('.me-tpc')
    const nodeObj = (tpc as any)?.nodeObj
    const caseId = nodeObj?.metadata?.caseId
    if (caseId && CASE_DETAIL.has(caseId)) {
      detailCase.value = CASE_DETAIL.get(caseId)
      detailVisible.value = true
    }
  }
  mind.container.addEventListener('pointerdown', onDown)
  mind.container.addEventListener('click', onClick)
  mind.bus.addListener('expandNode', () => {
    // 折叠状态变化后不需要额外处理（mind-elixir 自行重排）
  })
  // data 已是 buildMindData 产物（{ nodeData }）
  mind.init(data).then(() => {
    nextTick(() => {
      if (!mind) return
      const c = mind.container
      const cr = c.getBoundingClientRect()
      // 链式结构：初始按树宽自适应缩放（默认字段链折叠，宽度约 根+模块+用例标题）
      // 让整条链横向可见；随后 toCenter 使根节点（用例集名）居中显示
      const nodesW = mind.nodes?.getBoundingClientRect().width || 0
      const s = Math.min(0.9, Math.max(0.3, (cr.width - 24) / nodesW))
      mind.scale(s, { x: cr.left + cr.width / 2, y: cr.top + cr.height / 2 })
      mind.toCenter()
    })
  })
}

function expandAll() {
  if (!mind) return
  walkExpand(mind.nodeData, true)
  mind.refresh()
  nextTick(() => mind?.toCenter())
}

function collapseAll() {
  if (!mind) return
  walkExpand(mind.nodeData, false)
  mind.refresh()
  nextTick(() => mind?.toCenter())
}

function walkExpand(node: any, expanded: boolean) {
  node.expanded = expanded
  node.children?.forEach((ch: any) => walkExpand(ch, expanded))
}

function toCenter() {
  mind?.toCenter()
}

async function renderMind() {
  try {
    const data = await getSuiteMind(projectId, suiteId)
    suiteName.value = data.root.title
    totalCases.value = data.stat.total_cases
    moduleCount.value = data.stat.modules
    await nextTick()
    initMind(buildMindData(data))
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '加载脑图失败')
  }
}

function refresh() { renderMind() }

async function exportXmind() {
  try {
    const blob: any = await exportSuiteXmind(projectId, suiteId)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${suiteName.value || '用例集'}.xmind`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '导出失败')
  }
}

function goBack() {
  router.push(`/projects/${projectId}/case-suites`)
}
function goEditCase() {
  if (!detailCase.value) return
  router.push(`/projects/${projectId}/cases?highlight=${detailCase.value.id}`)
}

onMounted(() => {
  renderMind()
})

onBeforeUnmount(() => {
  mind?.destroy()
  mind = null
})
</script>

<style scoped>
.suite-mind-page {
  height: calc(100vh - 48px);
  display: flex;
  flex-direction: column;
  background: #fafbfc;
  overflow: hidden;
}
.mind-toolbar {
  padding: 8px 16px;
  background: #fff;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}
.tip-text {
  color: #8c8c8c;
  font-size: 12px;
  margin-left: auto;
}
.mind-info {
  padding: 8px 16px;
  background: #fff;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.suite-name {
  font-weight: 600;
  font-size: 15px;
  margin-right: 8px;
}
.mind-map {
  flex: 1;
  min-height: 320px;
  overflow: hidden;
}
</style>

<!-- mind-elixir 动态 DOM 样式（非 scoped，覆盖默认样式为飞书观感） -->
<style>
/* 分支线：浅灰贝塞尔 */
.map-container .lines path,
.map-container .subLines path {
  stroke: #c9c9c9 !important;
  stroke-width: 1.6 !important;
  fill: none !important;
}

/* 根节点：用例集名（纯文本，窄化） */
.map-container .me-root > .me-parent > .me-tpc {
  font-size: 14px;
  font-weight: 600;
  color: #1f1f1f;
  background: transparent;
  border: none;
  padding: 4px 10px;
  white-space: nowrap;
}

/* 模块节点：纯文本 */
.map-container .me-parent .me-tpc {
  font-size: 13.5px;
  font-weight: 600;
  color: #333;
  background: transparent;
  border: none;
  border-radius: 4px;
  padding: 3px 6px;
}

/* 折叠按钮：悬停出现，蓝色加减圆钮 */
.map-container .me-epd {
  width: 18px !important;
  height: 18px !important;
  border-radius: 50%;
  background-color: #eef3ff;
  background-size: 12px !important;
  opacity: 0 !important;
  transition: opacity 0.2s;
}
.map-container .me-parent:hover > .me-epd,
.map-container .me-root:hover > .me-parent > .me-epd {
  opacity: 1 !important;
}
.map-container .me-parent .me-epd.minus,
.map-container .me-root .me-epd.minus {
  opacity: 0 !important;
}
.map-container .me-parent:hover > .me-epd.minus,
.map-container .me-root:hover > .me-epd.minus {
  opacity: 1 !important;
}

/* 选中态 */
.map-container .selected {
  outline: 2px solid #4f90f2;
  outline-offset: 2px;
  border-radius: 4px;
}

/* 链式字段节点：字段名小字 + 内容（与 XMind 导出链一致：用例标题/前置条件/测试步骤/预期结果） */
.map-container .me-fldnode {
  font-size: 12px;
  line-height: 19px;
  max-width: 220px;
}
.map-container .me-fldnode .me-fld-name {
  font-size: 10.5px;
  color: #9aa1ab;
  margin-bottom: 1px;
}
.map-container .me-fldnode .me-fld-body {
  color: #333;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: normal;
}
/* 模块节点：限宽换行，避免长模块名把链拉宽 */
.map-container .me-main .me-tpc {
  max-width: 190px;
  white-space: normal;
  overflow-wrap: anywhere;
  line-height: 1.45;
}
/* 根节点（用例集名）：蓝色方块包裹 + 稍大字号、限宽换行 */
.map-container .me-root .me-tpc {
  font-size: 15px;
  max-width: 240px;
  white-space: normal;
  overflow-wrap: anywhere;
  line-height: 1.45;
  background: #3370ff;
  color: #ffffff;
  border-radius: 8px;
  padding: 7px 14px;
  box-shadow: 0 2px 6px rgba(51, 112, 255, 0.25);
}
.map-container .me-prio {
  font-weight: 600;
  margin-right: 2px;
}
.map-container .me-p0 { color: #f5222d; }
.map-container .me-p1 { color: #fa8c16; }
.map-container .me-p2 { color: #1677ff; }
.map-container .me-p3 { color: #8c8c8c; }
</style>
