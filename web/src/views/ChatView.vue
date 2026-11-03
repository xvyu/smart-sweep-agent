<script setup lang="ts">
/**
 * ChatView —— 智能问答主视图
 *
 * 组装：对话流（消息 + 思考块 + 工具卡片）+ 输入区。
 * 空状态给引导，有对话时自动滚动到底部。
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import ChatComposer from '../components/chat/ChatComposer.vue'
import MessageBubble from '../components/chat/MessageBubble.vue'
import ThinkingBlock from '../components/chat/ThinkingBlock.vue'
import ToolCallCard from '../components/chat/ToolCallCard.vue'
import BrandMark from '../components/ui/BrandMark.vue'
import type { ChatMessage } from '../composables/useChat'
import type { TopBarStats } from '../components/layout/TopBar.vue'

const props = withDefaults(
  defineProps<{
    messages: ChatMessage[]
    streaming?: boolean
    suggestions?: string[]
    /** 知识库真实统计，用于空状态的数据条 */
    stats?: TopBarStats | null
  }>(),
  { streaming: false, suggestions: () => [], stats: null },
)

const emit = defineEmits<{
  send: [text: string]
  stop: []
}>()

const scrollRef = ref<HTMLElement | null>(null)
const atBottom = ref(true)

/** 用户主动上翻时置为 true，暂停自动跟随；滚回底部附近后恢复 */
let userScrolledUp = false

function onScroll() {
  const el = scrollRef.value
  if (!el) return
  const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80
  atBottom.value = nearBottom
  // 只要用户滚回底部，就恢复跟随
  if (nearBottom) userScrolledUp = false
}

/** 用户用滚轮/触摸主动上翻 → 暂停跟随 */
function onUserIntent(e: Event) {
  const el = scrollRef.value
  if (!el) return
  if (e.type === 'wheel') {
    if ((e as WheelEvent).deltaY < 0) userScrolledUp = true
    return
  }
  // touchmove：交由 scroll 判断
  const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80
  if (!nearBottom) userScrolledUp = true
}

/**
 * 滚到底部。
 *
 * 不能用 `el.scrollTop = el.scrollHeight`：容器上设了 scroll-behavior: smooth，
 * 在流式高频更新时会产生互相打断的平滑动画，表现为"完全不滚动"。
 * 这里改用 scrollTo({ behavior: 'auto' }) 强制瞬时定位，保证跟手。
 */
function scrollToBottom(force = false) {
  const el = scrollRef.value
  if (!el) return
  if (!force && (userScrolledUp || !atBottom.value)) return
  el.scrollTo({ top: el.scrollHeight, behavior: 'auto' })
}

// 消息数量变化 → 强制滚到底（新一轮提问）
watch(
  () => props.messages.length,
  () => nextTick(() => scrollToBottom(true)),
)

/**
 * 内容增长 → 跟随滚动。
 *
 * 这里用 MutationObserver 而不是 watch：
 * 消息对象在父组件里是 reactive 数组的元素，通过 props 传入后，
 * 深层字段（content / thinking[].text）的变更在 watch getter 里不一定被追踪到，
 * 实测表现为"完全不跟随"。直接观察 DOM 变化最可靠，也能覆盖
 * 思考块逐字增长、工具卡片状态翻转、Markdown 渲染等所有情况。
 */
let observer: MutationObserver | null = null

onMounted(() => {
  const el = scrollRef.value
  if (!el) return
  observer = new MutationObserver(() => {
    // 内容变化时，若用户仍在底部附近就继续跟随
    scrollToBottom()
  })
  observer.observe(el, { childList: true, subtree: true, characterData: true })
  el.addEventListener('wheel', onUserIntent, { passive: true })
  el.addEventListener('touchmove', onUserIntent, { passive: true })
})

onBeforeUnmount(() => {
  observer?.disconnect()
  observer = null
  const el = scrollRef.value
  el?.removeEventListener('wheel', onUserIntent)
  el?.removeEventListener('touchmove', onUserIntent)
})

const isEmpty = computed(() => props.messages.length === 0)

/** 空状态的问题索引：编号 + 真实问题，点击即发送 */
const starters = [
  '小户型适合哪些扫地机器人？',
  '滚刷缠毛严重，怎么处理？',
  '滤网多久清洗一次？',
  '生成我 2025-10 的使用报告',
]
</script>

<template>
  <div class="chat-view">
    <div ref="scrollRef" class="scroll" @scroll="onScroll">
      <!-- 空状态：刊头 + 问题索引 -->
      <div v-if="isEmpty" class="hero">
        <!-- 内层容器统一负责「限宽 + 水平居中」。
             不能写在 .hero > * 上：子元素各自的 margin 简写
             （如 .eyebrow{margin:0 0 14px}）会覆盖掉 auto，
             导致只有未声明 margin 的 .index 被居中，
             检查器收起后 main 变宽，错位被放大成数百像素。 -->
        <div class="hero-inner">
          <p class="eyebrow">智扫通 · 扫地机器人 / 扫拖一体机</p>

          <h1 class="hero-title"><span class="rule" aria-hidden="true" />每个回答，<br />都带着<em>出处</em></h1>

          <p class="hero-sub">
            基于RAG向量库进行查询回答，优化回答质量。
          </p>

          <div v-if="stats" class="metastrip">
            <span class="mi first">知识库 <b class="mono">{{ stats.chunks }}</b> 条切片</span>
            <span class="mi"><b class="mono">{{ stats.docs }}</b> 份文档</span>
            <span class="mi last">覆盖 选购 · 保养 · 故障 · 维修</span>
          </div>

          <div class="index">
            <button
              v-for="(q, i) in starters"
              :key="q"
              class="idx-row"
              type="button"
              @click="emit('send', q)"
            >
              <span class="idx-num mono">{{ String(i + 1).padStart(2, '0') }}</span>
              <span class="idx-q">{{ q }}</span>
              <span class="idx-arrow i-lucide-arrow-right" />
            </button>
          </div>
        </div>
      </div>

      <!-- 消息流 -->
      <template v-else>
        <template v-for="m in messages" :key="m.id">
          <!-- 助手：先思考块、再工具卡片、最后答案 -->
          <template v-if="m.role === 'assistant'">
            <div class="assistant-wrap">
              <div class="avatar">
                <BrandMark :size="17" />
              </div>

              <div class="assistant-body">
                <ThinkingBlock
                  v-if="m.thinking.length || (m.streaming && !m.content)"
                  :steps="m.thinking"
                  :running="m.streaming && !m.content"
                />

                <ToolCallCard v-for="t in m.tools" :key="t.id" :call="t" />

                <MessageBubble
                  v-if="m.content || m.error || (m.streaming && m.thinking.length)"
                  role="assistant"
                  :content="m.content"
                  :streaming="m.streaming"
                  :error="m.error"
                  :show-avatar="false"
                />

                <p v-if="m.stats" class="stats mono">
                  {{ (m.stats.durationMs / 1000).toFixed(1) }}s ·
                  {{ m.stats.toolCount }} 次工具调用 ·
                  {{ m.stats.steps }} 轮推理
                </p>
              </div>
            </div>
          </template>

          <!-- 用户 -->
          <MessageBubble v-else role="user" :content="m.content" />
        </template>
      </template>
    </div>

    <ChatComposer
      :streaming="streaming"
      :suggestions="suggestions"
      @send="emit('send', $event)"
      @stop="emit('stop')"
    />
  </div>
</template>

<style scoped>
.chat-view {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.scroll {
  flex: 1;
  overflow-y: auto;
  padding: 20px 4px 8px;
  min-height: 0;
  /* 不用 smooth：流式高频滚动时会与动画互相打断，见 scrollToBottom 注释 */
  overscroll-behavior: contain;
}

/* ---------- 空状态：刊头 + 问题索引 ---------- */
.hero {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 40px 24px 48px;
  animation: fadeUp 0.6s var(--ease-entrance) both;
}

@keyframes fadeUp {
  from {
    opacity: 0;
    transform: translateY(16px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

/* 内部限宽并居中，文字本身左对齐（杂志排版）。
   用独立容器而不是 .hero > *：后者会被子元素各自的 margin 简写覆盖，
   导致部分元素居中、部分左对齐（检查器收起、main 变宽时错位尤其明显）。 */
.hero-inner {
  width: 100%;
  max-width: 680px;
  margin: 0 auto;
}

.eyebrow {
  margin: 0 0 14px;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--text-faint);
}

.hero-title {
  margin: 0 0 16px;
  font-family: var(--font-display);
  font-size: clamp(30px, 3.8vw, 40px);
  font-weight: 600;
  letter-spacing: -0.025em;
  line-height: 1.16;
  color: var(--text-primary);
}

/* 标题前的陶土橘短横：杂志栏目标记 */
.hero-title .rule {
  display: inline-block;
  width: 44px;
  height: 3px;
  background: var(--accent-core);
  border-radius: 2px;
  vertical-align: 12px;
  margin-right: 14px;
}

.hero-title em {
  font-style: normal;
  color: var(--accent-core);
}

.hero-sub {
  margin: 0 0 22px;
  font-family: var(--font-serif);
  font-size: 15.5px;
  line-height: 1.8;
  color: var(--text-secondary);
  max-width: 600px;
}

/* ---------- 数据条（真实统计） ---------- */
.metastrip {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  border-top: 1px solid var(--line-hairline);
  border-bottom: 1px solid var(--line-hairline);
  padding: 9px 0;
  margin: 0 0 26px;
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--text-tertiary);
}

.mi {
  padding: 0 14px;
  border-right: 1px solid var(--line-hairline);
  white-space: nowrap;
}

.mi.first {
  padding-left: 0;
}

.mi.last {
  border-right: none;
}

.mi b {
  color: var(--accent-core);
  font-weight: 500;
}

/* ---------- 问题索引 ---------- */
.index {
  border-top: 1px solid var(--line-hairline);
}

.idx-row {
  display: grid;
  grid-template-columns: 34px 1fr auto;
  gap: 14px;
  align-items: center;
  width: 100%;
  padding: 13px 2px;
  border: none;
  border-bottom: 1px solid var(--line-hairline);
  background: transparent;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  transition:
    background 0.16s var(--ease-standard),
    padding 0.16s var(--ease-standard);
}

.idx-row:hover {
  background: var(--accent-soft);
  padding-left: 10px;
}

.idx-row:focus-visible {
  outline: 2px solid var(--line-glow);
  outline-offset: -2px;
  border-radius: 6px;
}

.idx-num {
  font-size: 10.5px;
  color: var(--text-faint);
  letter-spacing: 0.04em;
}

.idx-row:hover .idx-num {
  color: var(--accent-core);
}

.idx-q {
  font-family: var(--font-serif);
  font-size: 15px;
  color: var(--text-primary);
}

.idx-arrow {
  font-size: 13px;
  color: var(--text-faint);
  transition: transform 0.16s var(--ease-standard);
}

.idx-row:hover .idx-arrow {
  color: var(--accent-core);
  transform: translateX(3px);
}

/* ---------- 助手消息块 ---------- */
.assistant-wrap {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  animation: fadeUp 0.45s var(--ease-entrance) both;
}

.avatar {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  /* 纸色底：标识自带橘色，容器再上橘会撞色 */
  background: var(--bg-void);
  border: 1px solid var(--line-hairline);
  font-size: 15px;
}

.assistant-body {
  flex: 1;
  min-width: 0;
  max-width: min(82%, 760px);
}

.stats {
  margin: -8px 0 0;
  font-size: 10.5px;
  color: var(--text-faint);
  letter-spacing: 0.02em;
}

@media (max-width: 768px) {
  .hero {
    padding: 28px 16px 36px;
  }
  .idx-q {
    font-size: 14px;
  }
  .assistant-body {
    max-width: 100%;
  }
}
</style>
