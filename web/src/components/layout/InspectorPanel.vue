<script setup lang="ts">
/**
 * InspectorPanel —— 右侧检查器
 *
 * 三个 Tab：
 *   思考轨迹：本次推理的分步耗时 + 步骤摘要
 *   工具调用：所有工具卡片的紧凑列表
 *   知识命中：工具返回的检索片段（从 rag_summarize 结果里提取）
 *
 * 这里是「可观测性」的第二落点：对话流里看过程，检查器里看细节。
 */
import { computed, onBeforeUnmount, ref } from 'vue'
import type { ThinkingStep, ToolCall, ToolMeta } from '../../api/types'

const props = withDefaults(
  defineProps<{
    thinking?: ThinkingStep[]
    tools?: ToolCall[]
    toolCatalog?: ToolMeta[]
    durationMs?: number
    streaming?: boolean
    /** 当前宽度（受控，由父组件持久化） */
    width?: number
    /** 是否可拖拽调整；窄屏抽屉态由 CSS 自行禁用 */
    resizable?: boolean
  }>(),
  {
    thinking: () => [],
    tools: () => [],
    toolCatalog: () => [],
    streaming: false,
    width: 380,
    resizable: false,
  },
)

const emit = defineEmits<{
  close: []
  /** 拖拽中：传出期望宽度（像素） */
  resize: [width: number]
  /** 双击把手：请求复位 */
  resizeReset: []
}>()

/* ---------------- 拖拽调整宽度（与左侧栏镜像） ---------------- */
/** 把手嵌在检查器左边界，绝对定位，不额外占宽度 */
const dragging = ref(false)
const startX = ref(0)
const startWidth = ref(0)

function onPointerDown(e: PointerEvent) {
  if (!props.resizable) return
  dragging.value = true
  startX.value = e.clientX
  startWidth.value = props.width
  // 捕获指针：即使光标移出把手也能继续收到 move/up
  ;(e.target as HTMLElement).setPointerCapture?.(e.pointerId)
  document.body.style.userSelect = 'none'
  document.body.style.cursor = 'col-resize'
  e.preventDefault()
}

function onPointerMove(e: PointerEvent) {
  if (!dragging.value) return
  // 镜像：检查器停靠右侧，向左拖（delta 为负）才是变宽
  emit('resize', startWidth.value - (e.clientX - startX.value))
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
  // 方向与视觉一致：← 让面板向左扩张（变宽），→ 收窄
  if (e.key === 'ArrowLeft') emit('resize', props.width + step)
  else if (e.key === 'ArrowRight') emit('resize', props.width - step)
  else if (e.key === 'Home') emit('resizeReset')
  else if (e.key === 'End') emit('resize', 620)
  else return
  e.preventDefault()
}

onBeforeUnmount(() => {
  document.body.style.userSelect = ''
  document.body.style.cursor = ''
})

type Tab = 'thinking' | 'tools' | 'knowledge'
const tab = ref<Tab>('thinking')

const tabs: { key: Tab; label: string }[] = [
  { key: 'thinking', label: '思考轨迹' },
  { key: 'tools', label: '工具调用' },
  { key: 'knowledge', label: '知识命中' },
]

/** 思考步骤摘要（每步取前 60 字） */
const stepSummaries = computed(() =>
  props.thinking.map((s, i) => ({
    index: i + 1,
    label: i === 0 ? '意图判断' : i === props.thinking.length - 1 ? '生成回答' : `第 ${i + 1} 轮思考`,
    preview: s.text.slice(0, 60) + (s.text.length > 60 ? '…' : ''),
  })),
)

/** 工具调用的耗时（没有单独计时就按整轮均分展示） */
const toolRows = computed(() =>
  props.tools.map((t) => {
    const meta = props.toolCatalog.find((m) => m.name === t.name)
    return {
      ...t,
      label: meta?.label ?? t.name,
      icon: meta?.icon ?? 'wrench',
      durationText: t.durationMs != null ? `${t.durationMs}ms` : '—',
    }
  }),
)

/** 知识命中：从 rag_summarize 的结果里提取片段 */
const knowledge = computed(() => {
  const rag = props.tools.filter((t) => t.name === 'rag_summarize' && t.result)
  return rag.map((t, i) => ({
    id: t.id,
    index: i + 1,
    query: String(t.args?.query ?? '—'),
    snippet: t.result!.slice(0, 220) + (t.result!.length > 220 ? '…' : ''),
    chars: t.result!.length,
  }))
})

const totalMs = computed(() => props.durationMs ?? 0)
const hasData = computed(
  () => props.thinking.length > 0 || props.tools.length > 0 || props.streaming,
)
</script>

<template>
  <aside class="inspector" :style="{ '--ins-w': width + 'px' }">
    <!-- 拖拽把手：骑在左边界上，默认只露检查器自身的 1px 分隔线 -->
    <div
      v-if="resizable"
      class="resizer"
      :class="{ on: dragging }"
      role="separator"
      aria-orientation="vertical"
      tabindex="0"
      aria-label="拖动调整检查器宽度，方向键可微调"
      :aria-valuenow="width"
      aria-valuemin="280"
      aria-valuemax="620"
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

    <div class="tabs" role="tablist">
      <button
        v-for="t in tabs"
        :key="t.key"
        class="tab"
        :class="{ active: tab === t.key }"
        type="button"
        role="tab"
        :aria-selected="tab === t.key"
        @click="tab = t.key"
      >
        {{ t.label }}
      </button>
      <button class="tab-close" type="button" title="关闭检查器" aria-label="关闭检查器" @click="emit('close')">
        <span class="i-lucide-x" />
      </button>
    </div>

    <div class="scroll">
      <!-- 空状态 -->
      <div v-if="!hasData" class="empty">
        <span class="i-lucide-brain empty-icon" />
        <p class="empty-title">等待第一次提问</p>
        <p class="empty-desc">提问后，这里会实时显示 AI 的推理步骤、工具调用与知识命中。</p>
      </div>

      <!-- 思考轨迹 -->
      <template v-else-if="tab === 'thinking'">
        <div class="section">
          <p class="section-title">本次推理</p>
          <div class="stepper">
            <div v-for="s in stepSummaries" :key="s.index" class="stepper-row">
              <span class="stepper-dot" />
              <div class="stepper-body">
                <span class="stepper-label">{{ s.label }}</span>
                <span class="stepper-preview">{{ s.preview }}</span>
              </div>
            </div>
            <div v-if="!stepSummaries.length" class="stepper-row">
              <span class="stepper-dot pulsing" />
              <div class="stepper-body">
                <span class="stepper-label">正在理解…</span>
              </div>
            </div>
          </div>
        </div>

        <div class="section">
          <p class="section-title">本次指标</p>
          <div class="metric">
            <div class="metric-top">
              <span class="metric-label">思考步骤</span>
              <span class="metric-val">
                {{ thinking.length }}<span class="metric-unit">步</span>
              </span>
            </div>
            <div class="track">
              <div class="fill" :style="{ width: Math.min(thinking.length * 33, 100) + '%' }" />
            </div>
          </div>
          <div class="metric">
            <div class="metric-top">
              <span class="metric-label">工具调用</span>
              <span class="metric-val">
                {{ tools.length }}<span class="metric-unit">次</span>
              </span>
            </div>
            <div class="track">
              <div class="fill" :style="{ width: Math.min(tools.length * 25, 100) + '%' }" />
            </div>
          </div>
          <div class="metric">
            <div class="metric-top">
              <span class="metric-label">总耗时</span>
              <span class="metric-val">
                {{ totalMs ? (totalMs / 1000).toFixed(1) : '—'
                }}<span class="metric-unit">s</span>
              </span>
            </div>
            <div class="track">
              <div class="fill" :style="{ width: Math.min(totalMs / 150, 100) + '%' }" />
            </div>
          </div>
        </div>
      </template>

      <!-- 工具调用 -->
      <template v-else-if="tab === 'tools'">
        <div class="section">
          <p class="section-title">工具调用（{{ toolRows.length }}）</p>
          <div v-if="!toolRows.length" class="mini-empty">本轮未调用工具</div>
          <div v-for="t in toolRows" :key="t.id" class="tool-row" :class="t.status">
            <div class="tool-bar" />
            <div class="tool-row-head">
              <span class="tool-row-name">{{ t.name }}</span>
              <span class="tool-row-dur mono">{{ t.durationText }}</span>
            </div>
            <div class="tool-row-label">{{ t.label }}</div>
          </div>
        </div>
      </template>

      <!-- 知识命中 -->
      <template v-else>
        <div class="section">
          <p class="section-title">检索片段（{{ knowledge.length }}）</p>
          <div v-if="!knowledge.length" class="mini-empty">本轮没有知识库检索</div>
          <div v-for="k in knowledge" :key="k.id" class="kb-card">
            <div class="kb-head">
              <span class="i-lucide-file-text kb-ic" />
              <span class="kb-query">{{ k.query }}</span>
            </div>
            <p class="kb-snippet">{{ k.snippet }}</p>
            <span class="kb-chars mono">{{ k.chars }} 字</span>
          </div>
        </div>
      </template>
    </div>
  </aside>
</template>

<style scoped>
.inspector {
  position: relative; /* 容纳绝对定位的拖拽把手 */
  /* 宽度由父组件通过 --ins-w 传入；窄屏媒体查询可覆盖它 */
  width: var(--ins-w, 380px);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--line-hairline);
  padding: 16px 0;
  min-height: 0;
}

.tabs {
  display: flex;
  gap: 4px;
  padding: 0 12px 12px;
  border-bottom: 1px solid var(--line-hairline);
}

.tab {
  flex: 1;
  padding: 8px 10px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  background: transparent;
  color: var(--text-tertiary);
  font-size: 11.5px;
  font-weight: 500;
  letter-spacing: 0.03em;
  transition: all 0.18s;
  font-family: inherit;
}

.tab:hover {
  color: var(--text-secondary);
  background: var(--surface-1);
}

.tab.active {
  color: var(--accent-core);
  background: var(--a-10);
}

.tab-close {
  flex: 0 0 30px;
  width: 30px;
  padding: 0;
  border-radius: 8px;
  border: 1px solid var(--line-hairline);
  background: var(--surface-1);
  color: var(--text-tertiary);
  cursor: pointer;
  font-size: 14px;
  display: grid;
  place-items: center;
  transition: all 0.18s;
}

.tab-close:hover {
  color: var(--danger);
  border-color: var(--d-35);
}

/* 宽屏时不需要关闭按钮（检查器是常驻栏） */
@media (min-width: 1281px) {
  .tab-close {
    display: none;
  }
}

.scroll {
  flex: 1;
  overflow-y: auto;
  padding: 16px 12px;
}

/* ---------- 空状态 ---------- */
.empty {
  padding: 48px 16px;
  text-align: center;
}

.empty-icon {
  font-size: 28px;
  color: var(--text-faint);
  margin-bottom: 12px;
}

.empty-title {
  margin: 0 0 6px;
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 500;
}

.empty-desc {
  margin: 0;
  font-size: 12px;
  color: var(--text-faint);
  line-height: 1.65;
}

.mini-empty {
  padding: 16px 0;
  font-size: 12px;
  color: var(--text-faint);
}

/* ---------- 分区 ---------- */
.section {
  margin-bottom: 22px;
}

.section-title {
  margin: 0 0 10px;
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-faint);
  font-weight: 500;
}

/* ---------- 步骤 ---------- */
.stepper {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.stepper-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.stepper-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent-core);
  box-shadow: 0 0 8px var(--accent-core);
  flex-shrink: 0;
  margin-top: 7px;
}

.stepper-dot.pulsing {
  animation: pulse 1.4s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.3;
  }
}

.stepper-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.stepper-label {
  font-size: 12.5px;
  color: var(--text-secondary);
}

.stepper-preview {
  font-size: 11px;
  color: var(--text-faint);
  line-height: 1.55;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
}

/* ---------- 指标 ---------- */
.metric {
  margin-bottom: 16px;
}

.metric:last-child {
  margin-bottom: 0;
}

.metric-top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 8px;
}

.metric-label {
  font-size: 11px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text-tertiary);
  font-weight: 500;
}

.metric-val {
  font-family: var(--font-mono);
  font-size: 26px;
  font-weight: 600;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.metric-unit {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-left: 2px;
  font-weight: 400;
}

.track {
  height: 4px;
  border-radius: var(--r-full);
  background: var(--line-hairline);
  overflow: hidden;
}

.fill {
  height: 100%;
  border-radius: var(--r-full);
  background: linear-gradient(90deg, var(--accent-core), var(--accent-bright));
  transition: width 1.2s var(--ease-entrance);
}

/* ---------- 工具行 ---------- */
.tool-row {
  position: relative;
  padding: 10px 12px 10px 16px;
  border-radius: 10px;
  background: var(--surface-1);
  border: 1px solid var(--line-hairline);
  margin-bottom: 8px;
  overflow: hidden;
}

.tool-bar {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--accent-blue);
}

.tool-row.success .tool-bar {
  background: var(--ok);
}

.tool-row.error .tool-bar {
  background: var(--danger);
}

.tool-row-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.tool-row-name {
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--text-primary);
}

.tool-row-dur {
  font-size: 10.5px;
  color: var(--text-tertiary);
}

.tool-row-label {
  margin-top: 2px;
  font-size: 10.5px;
  color: var(--text-faint);
}

/* ---------- 知识卡片 ---------- */
.kb-card {
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--surface-1);
  border: 1px solid var(--line-hairline);
  margin-bottom: 8px;
}

.kb-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.kb-ic {
  font-size: 12px;
  color: var(--accent-core);
  flex-shrink: 0;
}

.kb-query {
  font-size: 11.5px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-snippet {
  margin: 0 0 6px;
  font-size: 11.5px;
  line-height: 1.6;
  color: var(--text-tertiary);
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  line-clamp: 4;
  -webkit-box-orient: vertical;
}

.kb-chars {
  font-size: 10px;
  color: var(--text-faint);
}

/* ---------- 拖拽把手（与左侧栏镜像：骑在左边界上） ---------- */
.resizer {
  position: absolute;
  top: 0;
  left: -5px; /* 骑在 border-left 上，不额外占宽度 */
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
  transition:
    background 0.16s,
    width 0.16s;
}

.resizer .grip {
  position: relative;
  z-index: 2;
  width: 4px;
  height: 34px;
  border-radius: 9999px;
  background: var(--line-strong);
  opacity: 0;
  transition:
    opacity 0.16s,
    height 0.16s,
    background 0.16s;
}

/* 读数浮在把手左侧（主内容区），与侧栏把手对称 */
.resizer .tip {
  position: absolute;
  top: 50%;
  right: 14px;
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

@media (max-width: 1280px) {
  .inspector {
    position: fixed;
    right: 0;
    top: 64px;
    bottom: 0;
    /* 抽屉态：忽略用户拖拽宽度，固定 380（连 --ins-w 一起重置，避免变量残留生效） */
    --ins-w: 380px;
    width: 380px;
    max-width: 92vw;
    z-index: 40;
    background: var(--bg-base);
    box-shadow: var(--shadow-float);
    animation: slideIn 0.28s var(--ease-entrance) both;
  }
  /* 抽屉态不允许拖拽 */
  .resizer {
    display: none;
  }
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateX(24px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

@media (max-width: 768px) {
  .inspector {
    display: none;
  }
}
</style>
