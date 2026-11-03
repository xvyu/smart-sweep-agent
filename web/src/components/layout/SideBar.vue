<script setup lang="ts">
/**
 * SideBar —— 左侧栏
 *
 * 会话列表来自后端持久化（刷新不丢），支持：
 *   - 点击切换（真实载入历史消息）
 *   - 悬停显示删除 / 重命名
 *   - 能力入口（知识库 / 数据看板 / 环境适配）
 *   - 右边界拖拽调宽（见文件末尾的把手实现）
 */
import { computed, onBeforeUnmount, ref } from 'vue'

export interface SessionItem {
  id: string
  title: string
  at: string
  active: boolean
}

const props = withDefaults(
  defineProps<{
    sessions?: SessionItem[]
    userLabel?: string
    userMeta?: string
    loading?: boolean
    /** 当前宽度（受控，由父组件持久化） */
    width?: number
    /** 是否可拖拽调整；窄屏由 CSS 断点自行降级 */
    resizable?: boolean
  }>(),
  {
    sessions: () => [],
    userLabel: '访客',
    userMeta: '未绑定设备',
    loading: false,
    width: 260,
    resizable: false,
  },
)

const emit = defineEmits<{
  newChat: []
  pick: [id: string]
  remove: [id: string]
  rename: [payload: { id: string; title: string }]
  capability: [name: string]
  /** 拖拽中：传出期望宽度（像素） */
  resize: [width: number]
  /** 双击把手：请求复位 */
  resizeReset: []
}>()

/* ---------------- 拖拽调整宽度 ---------------- */
/** 把手嵌在侧栏右边界，绝对定位，不额外占宽度 */
const dragging = ref(false)
const startX = ref(0)
const startWidth = ref(0)

const isRail = computed(() => props.width <= 72)

function onPointerDown(e: PointerEvent) {
  if (!props.resizable) return
  dragging.value = true
  startX.value = e.clientX
  startWidth.value = props.width
  // 捕获指针：即使光标移出把手也能继续收到 move/up
  ;(e.target as HTMLElement).setPointerCapture?.(e.pointerId)
  // 拖拽期间禁止选中文本、统一光标，避免 iframe/文字吞事件
  document.body.style.userSelect = 'none'
  document.body.style.cursor = 'col-resize'
  e.preventDefault()
}

function onPointerMove(e: PointerEvent) {
  if (!dragging.value) return
  emit('resize', startWidth.value + (e.clientX - startX.value))
}

function endDrag(e: PointerEvent) {
  if (!dragging.value) return
  dragging.value = false
  ;(e.target as HTMLElement).releasePointerCapture?.(e.pointerId)
  document.body.style.userSelect = ''
  document.body.style.cursor = ''
}

function onKeydown(e: KeyboardEvent) {
  if (!props.resizable) return
  const step = e.shiftKey ? 32 : 8
  if (e.key === 'ArrowLeft') emit('resize', props.width - step)
  else if (e.key === 'ArrowRight') emit('resize', props.width + step)
  else if (e.key === 'Home') emit('resizeReset')
  else if (e.key === 'End') emit('resize', 420)
  else return
  e.preventDefault()
}

onBeforeUnmount(() => {
  document.body.style.userSelect = ''
  document.body.style.cursor = ''
})

/* ---------------- 重命名 ---------------- */
const editingId = ref<string | null>(null)
const editingTitle = ref('')
const inputRef = ref<HTMLInputElement | null>(null)

function startRename(s: SessionItem) {
  editingId.value = s.id
  editingTitle.value = s.title
  requestAnimationFrame(() => {
    inputRef.value?.focus()
    inputRef.value?.select()
  })
}

function commitRename() {
  if (!editingId.value) return
  const title = editingTitle.value.trim()
  if (title) emit('rename', { id: editingId.value, title })
  editingId.value = null
}

function cancelRename() {
  editingId.value = null
}

/* ---------------- 删除 ---------------- */
const confirmingId = ref<string | null>(null)

function askDelete(id: string) {
  confirmingId.value = id
}

function confirmDelete() {
  if (confirmingId.value) emit('remove', confirmingId.value)
  confirmingId.value = null
}

function cancelDelete() {
  confirmingId.value = null
}
</script>

<template>
  <aside
    class="sidebar"
    :class="{ rail: isRail }"
    :style="{ '--sb-w': width + 'px' }"
  >
    <button class="new-chat" type="button" @click="emit('newChat')">
      <span class="i-lucide-plus" />
      <span>新建对话</span>
    </button>

    <div class="group sessions-group">
      <p class="group-title">最近会话</p>

      <p v-if="loading" class="hint-line">正在载入…</p>

      <p v-else-if="!sessions.length" class="empty">还没有对话——问一句试试</p>

      <!-- 只有这个列表内部滚动，默认恰好显示 5 条 -->
      <div v-else class="sessions" tabindex="0" role="list" aria-label="最近会话">
        <div
          v-for="s in sessions"
          :key="s.id"
          class="nav-item"
          :class="{ active: s.active, editing: editingId === s.id }"
          role="listitem"
        >
        <!-- 重命名输入 -->
        <template v-if="editingId === s.id">
          <input
            ref="inputRef"
            v-model="editingTitle"
            class="rename-input"
            maxlength="80"
            @keydown.enter.prevent="commitRename"
            @keydown.esc.prevent="cancelRename"
            @blur="commitRename"
          />
        </template>

        <!-- 正常显示 -->
        <template v-else>
          <button class="nav-main" type="button" @click="emit('pick', s.id)">
            <span class="i-lucide-message-circle nav-ic" />
            <span class="nav-meta">
              <span class="nav-title">{{ s.title }}</span>
              <span class="nav-time">{{ s.at }}</span>
            </span>
          </button>

          <span class="nav-actions">
            <button
              class="mini"
              type="button"
              title="重命名"
              aria-label="重命名"
              @click.stop="startRename(s)"
            >
              <span class="i-lucide-pencil" />
            </button>
            <button
              class="mini danger"
              type="button"
              title="删除"
              aria-label="删除"
              @click.stop="askDelete(s.id)"
            >
              <span class="i-lucide-trash-2" />
            </button>
          </span>
        </template>
        </div>
      </div>
    </div>

    <div class="group">
      <p class="group-title">能力</p>
      <button class="nav-item nav-main" type="button" @click="emit('capability', 'knowledge')">
        <span class="i-lucide-library nav-ic" />
        <span class="nav-meta"><span class="nav-title">知识库检索</span></span>
      </button>
      <button class="nav-item nav-main" type="button" @click="emit('capability', 'analytics')">
        <span class="i-lucide-file-bar-chart nav-ic" />
        <span class="nav-meta"><span class="nav-title">数据看板</span></span>
      </button>
      <button class="nav-item nav-main" type="button" @click="emit('capability', 'env')">
        <span class="i-lucide-cloud-sun nav-ic" />
        <span class="nav-meta"><span class="nav-title">环境适配</span></span>
      </button>
    </div>

    <div class="footer">
      <div class="avatar">{{ userLabel.slice(0, 1).toUpperCase() }}</div>
      <div class="who">
        <span class="n">{{ userLabel }}</span>
        <span class="r">{{ userMeta }}</span>
      </div>
    </div>

    <!-- 拖拽把手：嵌在右边界内，默认只有 1px 分隔线（侧栏自带 border-right） -->
    <div
      v-if="resizable"
      class="resizer"
      :class="{ on: dragging }"
      role="separator"
      aria-orientation="vertical"
      tabindex="0"
      aria-label="拖动调整侧栏宽度，方向键可微调"
      :aria-valuenow="width"
      aria-valuemin="72"
      aria-valuemax="420"
      title="拖动调整宽度 · 双击复位"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="endDrag"
      @pointercancel="endDrag"
      @dblclick="emit('resizeReset')"
      @keydown="onKeydown"
    >
      <span class="grip" />
      <span class="tip mono">{{ width }}px</span>
    </div>

    <!-- 删除确认 -->
    <div v-if="confirmingId" class="confirm-mask" @click.self="cancelDelete">
      <div class="confirm-box">
        <p class="confirm-title">删除这个会话？</p>
        <p class="confirm-desc">对话记录将一并删除，且无法恢复。</p>
        <div class="confirm-actions">
          <button class="cbtn" type="button" @click="cancelDelete">取消</button>
          <button class="cbtn danger" type="button" @click="confirmDelete">删除</button>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  /* 会话行高（固定值，便于精确算出「恰好 5 条」） */
  --session-row: 52px;
  --session-gap: 2px;

  position: relative; /* 容纳绝对定位的拖拽把手 */
  /* 宽度由父组件通过 --sb-w 传入；窄屏媒体查询可覆盖它 */
  width: var(--sb-w, 260px);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 16px 0;
  border-right: 1px solid var(--line-hairline);
  min-height: 0;
  /* 侧栏自身不滚动：新建对话 / 能力 / 用户区始终固定可见，
     只有「最近会话」列表内部滚动（见 .sessions） */
  overflow: hidden;
}

.new-chat {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 11px;
  border-radius: var(--r-md);
  cursor: pointer;
  /* 暖色主题：主行动按钮为实心陶土橘（深色主题下是低透明发光，不适用） */
  background: var(--brand-gradient);
  border: none;
  color: var(--text-inverse);
  box-shadow: var(--shadow-accent);
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  transition: all 0.2s var(--ease-standard);
}

.new-chat:hover {
  transform: translateY(-1px);
  box-shadow: 0 5px 16px var(--a-35);
}

.group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

/* ---------- 最近会话：侧栏里唯一的滚动区域 ---------- */
.sessions-group {
  min-height: 0;
}

.sessions {
  display: flex;
  flex-direction: column;
  gap: var(--session-gap);
  /* 默认恰好露出 5 条；空间不足时可收缩到 2 条 */
  max-height: calc(var(--session-row) * 5 + var(--session-gap) * 4);
  min-height: calc(var(--session-row) * 2 + var(--session-gap));
  flex: 0 1 auto;
  overflow-y: auto;
  /* 滚到列表末尾时不把滚动传给父级，避免整栏跟着动 */
  overscroll-behavior: contain;
  scrollbar-width: thin;
  scrollbar-color: var(--line-strong) transparent;
  /* 左侧留 2px 给选中态的竖条，右侧留滚动条位 */
  padding-right: 4px;
}

.sessions::-webkit-scrollbar {
  width: 5px;
}
.sessions::-webkit-scrollbar-track {
  background: transparent;
}
.sessions::-webkit-scrollbar-thumb {
  background: var(--line-strong);
  border-radius: 9999px;
  border: none;
  background-clip: border-box;
}
.sessions::-webkit-scrollbar-thumb:hover {
  background: var(--accent-line);
}

/* 键盘可达：聚焦时给出可见环 */
.sessions:focus-visible {
  outline: 2px solid var(--line-glow);
  outline-offset: 2px;
  border-radius: 10px;
}

/* 固定行高，保证「5 条」的高度算术成立 */
.sessions .nav-item {
  flex-shrink: 0;
  height: var(--session-row);
}

.sessions .nav-main {
  height: 100%;
  padding: 0 10px;
}

.sessions .nav-meta {
  gap: 0;
}

.sessions .nav-title {
  line-height: 1.5;
}

.sessions .nav-time {
  line-height: 1.35;
}

.sessions .nav-item.editing {
  padding: 0 6px;
}

.group-title {
  margin: 0 0 6px;
  padding: 0 10px;
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-faint);
  font-weight: 500;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  border-radius: 10px;
  border-left: 2px solid transparent;
  transition: all 0.18s;
  width: 100%;
  position: relative;
}

.nav-item:hover {
  background: var(--surface-2);
}

.nav-item.active {
  background: var(--a-08);
  border-left-color: var(--accent-core);
}

.nav-item.editing {
  background: var(--a-06);
  padding: 4px 6px;
}

.nav-main {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  background: transparent;
  border: none;
  cursor: pointer;
  text-align: left;
  width: 100%;
  font-family: inherit;
  min-width: 0;
}

.nav-ic {
  font-size: 15px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.nav-item.active .nav-ic {
  color: var(--accent-core);
}

.nav-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 2px;
  flex: 1;
}

.nav-title {
  font-size: 12.5px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nav-time {
  font-size: 10px;
  color: var(--text-faint);
}

/* ---------- 悬停操作 ---------- */
.nav-actions {
  display: flex;
  gap: 2px;
  padding-right: 6px;
  opacity: 0;
  transition: opacity 0.15s;
  flex-shrink: 0;
}

.nav-item:hover .nav-actions {
  opacity: 1;
}

.mini {
  width: 22px;
  height: 22px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  display: grid;
  place-items: center;
  font-size: 12px;
  transition: all 0.15s;
}

.mini:hover {
  background: var(--line-hairline);
  color: var(--accent-core);
}

.mini.danger:hover {
  color: var(--danger);
  background: var(--d-12);
}

/* ---------- 重命名输入 ---------- */
.rename-input {
  width: 100%;
  padding: 6px 8px;
  border-radius: 6px;
  background: var(--surface-3);
  border: 1px solid var(--a-45);
  color: var(--text-primary);
  font-size: 12.5px;
  font-family: inherit;
  outline: none;
}

.hint-line,
.empty {
  margin: 4px 10px;
  font-size: 12px;
  color: var(--text-faint);
  line-height: 1.6;
}

.footer {
  margin-top: auto;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 10px 0;
  border-top: 1px solid var(--line-hairline);
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: var(--r-full);
  display: grid;
  place-items: center;
  background: var(--a-15);
  border: 1px solid var(--a-30);
  color: var(--accent-core);
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.who {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.n {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
}

.r {
  font-size: 10px;
  color: var(--text-faint);
}

/* ---------- 删除确认 ---------- */
.confirm-mask {
  position: fixed;
  inset: 0;
  z-index: 90;
  background: var(--scrim-70);
  backdrop-filter: blur(4px);
  display: grid;
  place-items: center;
}

.confirm-box {
  width: 320px;
  padding: 20px;
  border-radius: var(--r-lg);
  background: var(--bg-elevated);
  border: 1px solid var(--line-strong);
  box-shadow: var(--shadow-float);
}

.confirm-title {
  margin: 0 0 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.confirm-desc {
  margin: 0 0 18px;
  font-size: 12.5px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.confirm-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.cbtn {
  padding: 7px 14px;
  border-radius: var(--r-sm);
  border: 1px solid var(--line-hairline);
  background: var(--surface-1);
  color: var(--text-secondary);
  font-size: 12.5px;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s;
}

.cbtn:hover {
  background: var(--surface-2);
}

.cbtn.danger {
  background: var(--d-15);
  border-color: var(--d-35);
  color: var(--danger);
}

.cbtn.danger:hover {
  background: var(--d-25);
}

/* ---------- 拖拽把手 ---------- */
.resizer {
  position: absolute;
  top: 0;
  right: -5px; /* 骑在 border-right 上，不额外占宽度 */
  width: 11px;
  height: 100%;
  cursor: col-resize;
  display: grid;
  place-items: center;
  background: transparent;
  z-index: 20;
  touch-action: none; /* 触屏拖拽时不被浏览器手势劫持 */
}

.resizer::before {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: 50%;
  width: 1px;
  transform: translateX(-50%);
  background: transparent;
  transition: background 0.16s, width 0.16s;
}

.resizer .grip {
  position: relative;
  z-index: 2;
  width: 4px;
  height: 34px;
  border-radius: 9999px;
  background: var(--line-strong);
  opacity: 0;
  transition: opacity 0.16s, height 0.16s, background 0.16s;
}

.resizer .tip {
  position: absolute;
  top: 50%;
  left: 14px;
  transform: translateY(-50%);
  z-index: 21;
  font-size: 10px;
  color: var(--text-inverse);
  background: var(--text-primary);
  padding: 3px 7px;
  border-radius: 5px;
  white-space: nowrap;
  opacity: 0;
  transition: opacity 0.14s;
  pointer-events: none;
}

.resizer:hover::before,
.resizer.on::before,
.resizer:focus-visible::before {
  background: var(--accent-core);
  width: 2px;
}

.resizer:hover .grip,
.resizer.on .grip,
.resizer:focus-visible .grip {
  opacity: 1;
  background: var(--accent-core);
  height: 52px;
}

.resizer.on .tip {
  opacity: 1;
}

.resizer:focus-visible {
  outline: none;
}

/* ---------- 图标栏态（拖到最窄） ---------- */
.sidebar.rail .new-chat span:last-child,
.sidebar.rail .group-title,
.sidebar.rail .nav-meta,
.sidebar.rail .who,
.sidebar.rail .nav-actions {
  display: none;
}

.sidebar.rail .nav-item,
.sidebar.rail .nav-main {
  justify-content: center;
  border-left: none;
}

.sidebar.rail .footer {
  justify-content: center;
}

@media (max-width: 1024px) {
  .sidebar {
    width: 72px;
  }
  .resizer {
    display: none; /* 窄屏不允许拖拽 */
  }
  .new-chat span:last-child,
  .group-title,
  .nav-meta,
  .who,
  .nav-actions {
    display: none;
  }
  .nav-item,
  .nav-main {
    justify-content: center;
    border-left: none;
  }
  .footer {
    justify-content: center;
  }
}

@media (max-width: 768px) {
  .sidebar {
    display: none;
  }
}
</style>
