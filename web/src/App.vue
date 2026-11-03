<script setup lang="ts">
/**
 * App —— 应用外壳
 *
 * 组装三栏：TopBar / SideBar / ChatView / InspectorPanel，
 * 并负责：
 *   - 健康检查（决定顶栏状态胶囊）
 *   - 会话持久化（新建 / 切换 / 删除 / 重命名，刷新不丢）
 *   - 知识库抽屉与数据看板抽屉
 *   - 把「当前活跃助手消息」的思考/工具/统计喂给检查器
 */
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from './api/client'
import type { HealthResponse, SessionMeta, ToolMeta } from './api/types'
import AnalyticsDrawer from './components/analytics/AnalyticsDrawer.vue'
import KnowledgeDrawer from './components/knowledge/KnowledgeDrawer.vue'
import InspectorPanel from './components/layout/InspectorPanel.vue'
import SideBar, { type SessionItem } from './components/layout/SideBar.vue'
import TopBar, { type TopBarStats } from './components/layout/TopBar.vue'
import { useChat } from './composables/useChat'
import ChatView from './views/ChatView.vue'

/**
 * 粒子背景是纯装饰，且依赖 three.js（~600KB）。
 * 异步加载 + 延迟到首屏绘制后，保证 it 完全不阻塞对话界面的可用性。
 */
const ParticleField = defineAsyncComponent(() => import('./components/background/ParticleField.vue'))

/* ------------------------------ 对话 ------------------------------ */
const { messages, streaming, sessionId, send, stop, newSession, loadSession } = useChat()

/* ---------------------------- 健康检查 ---------------------------- */
const health = ref<HealthResponse | null>(null)
const healthLoading = ref(true)

const statusLabel = computed(() => {
  if (healthLoading.value) return '正在连接…'
  if (!health.value) return '服务未连接'
  if (health.value.ok) return 'RAG 已连接'
  if (!health.value.agent?.ok) return '模型未就绪'
  if (!health.value.ollama?.ok) return '向量服务离线'
  if (!health.value.chroma?.ok) return '知识库未加载'
  return '服务降级'
})

const statusTone = computed<'ok' | 'warn' | 'danger'>(() => {
  if (healthLoading.value) return 'warn'
  if (!health.value) return 'danger'
  return health.value.ok ? 'ok' : 'warn'
})

async function checkHealth() {
  healthLoading.value = true
  try {
    health.value = await api.health()
  } catch {
    health.value = null
  } finally {
    healthLoading.value = false
  }
}

/* ---------------------------- 工具目录 ---------------------------- */
const toolCatalog = ref<ToolMeta[]>([])

async function loadMeta() {
  try {
    const meta = await api.meta()
    toolCatalog.value = meta.tools
    userCount.value = meta.users?.length ?? 0
  } catch {
    toolCatalog.value = []
  }
}

/* ------------------------ 知识库统计（顶栏数据条） ------------------------ */
const chunkCount = ref(0)
const docCount = ref(0)
const userCount = ref(0)

async function loadKnowledgeStats() {
  try {
    const s = await api.knowledgeStats()
    chunkCount.value = s.totalChunks ?? 0
    docCount.value = s.sources?.length ?? 0
  } catch {
    chunkCount.value = 0
    docCount.value = 0
  }
}

/** 顶栏与空状态共用的真实统计 */
const topStats = computed<TopBarStats | null>(() => {
  if (!chunkCount.value && !docCount.value) return null
  return { chunks: chunkCount.value, docs: docCount.value, users: userCount.value }
})

/* ---------------------------- 会话历史 ---------------------------- */
const sessions = ref<SessionMeta[]>([])
const sessionsLoading = ref(true)

function formatRelative(ts: number): string {
  // 后端返回秒，统一转毫秒
  const ms = ts < 1e12 ? ts * 1000 : ts
  const diff = Date.now() - ms
  if (diff < 60_000) return '刚刚'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`
  return `${Math.floor(diff / 86_400_000)} 天前`
}

const sessionItems = computed<SessionItem[]>(() =>
  sessions.value.map((s) => ({
    id: s.id,
    title: s.title,
    at: formatRelative(s.updatedAt),
    active: s.id === sessionId.value,
  })),
)

const currentTitle = computed(() => {
  if (!sessionId.value) return '新对话'
  return sessions.value.find((s) => s.id === sessionId.value)?.title ?? '新对话'
})

async function refreshSessions() {
  sessionsLoading.value = true
  try {
    const res = await api.sessions()
    sessions.value = res.sessions
  } catch {
    sessions.value = []
  } finally {
    sessionsLoading.value = false
  }
}

/* ---------------------------- 交互 ---------------------------- */
async function handleSend(text: string) {
  await send(text)
  // 生成结束后刷新会话列表（标题/时间会变化）
  refreshSessions()
}

function handleNewChat() {
  newSession()
  refreshSessions()
}

async function handlePick(id: string) {
  if (id === sessionId.value) return
  await loadSession(id)
}

async function handleRemove(id: string) {
  try {
    await api.deleteSession(id)
    // 删的是当前会话 → 清空界面
    if (id === sessionId.value) newSession()
    await refreshSessions()
  } catch (err) {
    console.warn('[App] 删除会话失败：', err)
  }
}

async function handleRename(payload: { id: string; title: string }) {
  try {
    await api.renameSession(payload.id, payload.title)
    await refreshSessions()
  } catch (err) {
    console.warn('[App] 重命名失败：', err)
  }
}

/* ---------------------------- 抽屉 ---------------------------- */
const knowledgeOpen = ref(false)
const analyticsOpen = ref(false)

function handleCapability(name: string) {
  if (name === 'knowledge') {
    knowledgeOpen.value = true
    return
  }
  if (name === 'analytics' || name === 'report') {
    analyticsOpen.value = true
    return
  }
  if (name === 'env') {
    handleSend('我在深圳，最近天气潮湿，扫地机器人该怎么保养？')
  }
}

/* --------------------------- 检查器数据 --------------------------- */
const activeAssistant = computed(() => {
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === 'assistant') return messages[i]
  }
  return null
})

/**
 * 检查器默认开合：
 * 宽屏（>1280px）三栏并排，默认展开；
 * 窄屏下它是覆盖式抽屉，默认收起，避免一进页面就挡住对话。
 */
const inspectorOpen = ref(
  typeof window === 'undefined' ? true : window.innerWidth > 1280,
)

function syncInspectorToViewport() {
  inspectorOpen.value = window.innerWidth > 1280
}

const suggestions = ['小户型适合哪款', '滚刷缠毛怎么办', '生成我的使用报告']

/* ------------------------ 侧栏宽度（可拖拽） ------------------------ */
const SB_MIN = 200
const SB_MAX = 420
const SB_DEFAULT = 260
const SB_RAIL = 72
/** 低于此值吸附到图标栏 */
const SB_SNAP = 160
const SB_STORE_KEY = 'zs.sidebar.width'

function clampSidebar(w: number): number {
  if (w < SB_SNAP) return SB_RAIL
  return Math.max(SB_MIN, Math.min(SB_MAX, Math.round(w)))
}

function readStoredSidebar(): number {
  if (typeof window === 'undefined') return SB_DEFAULT
  const raw = window.localStorage.getItem(SB_STORE_KEY)
  const n = raw ? Number.parseInt(raw, 10) : NaN
  return Number.isFinite(n) ? clampSidebar(n) : SB_DEFAULT
}

const sidebarWidth = ref(readStoredSidebar())

function setSidebarWidth(w: number, persist = true) {
  sidebarWidth.value = clampSidebar(w)
  if (persist && typeof window !== 'undefined') {
    window.localStorage.setItem(SB_STORE_KEY, String(sidebarWidth.value))
  }
}

/** SideBar 已按自身宽度算好增量，这里只做钳制与持久化 */
function onSidebarResize(width: number) {
  setSidebarWidth(width)
}

/* --------------------- 检查器宽度（可拖拽） --------------------- */
const IN_MIN = 280
const IN_MAX = 620
const IN_DEFAULT = 380
const IN_STORE_KEY = 'zs.inspector.width'

function clampInspector(w: number): number {
  return Math.max(IN_MIN, Math.min(IN_MAX, Math.round(w)))
}

function readStoredInspector(): number {
  if (typeof window === 'undefined') return IN_DEFAULT
  const raw = window.localStorage.getItem(IN_STORE_KEY)
  const n = raw ? Number.parseInt(raw, 10) : NaN
  return Number.isFinite(n) ? clampInspector(n) : IN_DEFAULT
}

const inspectorWidth = ref(readStoredInspector())

function setInspectorWidth(w: number, persist = true) {
  inspectorWidth.value = clampInspector(w)
  if (persist && typeof window !== 'undefined') {
    window.localStorage.setItem(IN_STORE_KEY, String(inspectorWidth.value))
  }
}

/** InspectorPanel 已按镜像方向算好宽度，这里只做钳制与持久化 */
function onInspectorResize(width: number) {
  setInspectorWidth(width)
}

onMounted(() => {
  checkHealth()
  loadMeta()
  loadKnowledgeStats()
  refreshSessions()
  // 健康检查失败后每 30s 重试一次
  setInterval(() => {
    if (!health.value?.ok) checkHealth()
  }, 30_000)
  window.addEventListener('resize', syncInspectorToViewport)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', syncInspectorToViewport)
})
</script>

<template>
  <div class="shell">
    <!-- 背景层 -->
    <div class="aurora" />
    <div class="grid-overlay" />
    <ParticleField />

    <TopBar
      :session-title="currentTitle"
      :status-label="statusLabel"
      :status-tone="statusTone"
      :stats="topStats"
      @toggle-inspector="inspectorOpen = !inspectorOpen"
      @open-knowledge="knowledgeOpen = true"
    />

    <div class="body-row">
      <SideBar
        :sessions="sessionItems"
        :loading="sessionsLoading"
        :user-label="'访客'"
        :user-meta="health?.chroma?.ok ? '知识库已就绪' : '知识库未就绪'"
        :width="sidebarWidth"
        :resizable="true"
        @new-chat="handleNewChat"
        @pick="handlePick"
        @remove="handleRemove"
        @rename="handleRename"
        @capability="handleCapability"
        @resize="onSidebarResize"
        @resize-reset="setSidebarWidth(SB_DEFAULT)"
      />

      <main class="main">
        <ChatView
          :messages="messages"
          :streaming="streaming"
          :suggestions="suggestions"
          :stats="topStats"
          @send="handleSend"
          @stop="stop"
        />
      </main>

      <InspectorPanel
        v-if="inspectorOpen"
        :thinking="activeAssistant?.thinking ?? []"
        :tools="activeAssistant?.tools ?? []"
        :tool-catalog="toolCatalog"
        :duration-ms="activeAssistant?.stats?.durationMs"
        :streaming="streaming"
        :width="inspectorWidth"
        :resizable="true"
        @close="inspectorOpen = false"
        @resize="onInspectorResize"
        @resize-reset="setInspectorWidth(IN_DEFAULT)"
      />
    </div>

    <!-- 抽屉 -->
    <KnowledgeDrawer :open="knowledgeOpen" @close="knowledgeOpen = false" />
    <AnalyticsDrawer :open="analyticsOpen" @close="analyticsOpen = false" />
  </div>
</template>

<style scoped>
.shell {
  position: relative;
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--bg-void);
}

.aurora {
  position: fixed;
  top: -32%;
  left: 50%;
  transform: translateX(-50%);
  width: 1100px;
  height: 700px;
  pointer-events: none;
  z-index: 0;
  /* 暖色主题：顶部一层极淡的陶土橘暖光，像纸面受光 */
  background: radial-gradient(ellipse at center, var(--a-08), transparent 62%);
  filter: blur(70px);
}

.grid-overlay {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  /* 纸面颗粒：用暖线色画点阵（原深色主题用白色，在奶油底上不可见） */
  background-image: radial-gradient(var(--line-hairline) 1px, transparent 1px);
  background-size: 32px 32px;
  opacity: 0.55;
  -webkit-mask-image: radial-gradient(ellipse 80% 60% at 50% 0%, #000 40%, transparent 100%);
  mask-image: radial-gradient(ellipse 80% 60% at 50% 0%, #000 40%, transparent 100%);
}

.body-row {
  position: relative;
  z-index: 10;
  flex: 1;
  display: flex;
  gap: 20px;
  padding: 0 24px 20px;
  max-width: 1680px;
  width: 100%;
  margin: 0 auto;
  min-height: 0;
}

.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

@media (max-width: 768px) {
  .body-row {
    padding: 0 12px 12px;
  }
}
</style>
