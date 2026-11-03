<script setup lang="ts">
/**
 * MessageBubble —— 消息气泡
 *
 * 用户侧：右对齐、墨色底、不对称圆角（20/20/5/20）
 * 助手侧：左对齐、白卡 + 暖细线、Zodiak 衬线正文、流式光标
 *
 * showAvatar：ChatView 会在助手回合外层自带一个品牌标识头像，
 * 那种场景下要关掉这里的内层头像，否则同一回合出现两个标识。
 */
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import BrandMark from '../ui/BrandMark.vue'

const props = withDefaults(
  defineProps<{
    role: 'user' | 'assistant'
    content: string
    streaming?: boolean
    error?: string
    showAvatar?: boolean
  }>(),
  { streaming: false, showAvatar: true },
)

const md = new MarkdownIt({
  html: false, // 安全：禁止原始 HTML
  linkify: true,
  breaks: true,
})

/**
 * 预处理模型输出的 Markdown。
 *
 * 实测问题：模型常写出 `**"控水、勤晾、防霉"**` 这种「加粗紧贴中文引号」的形式，
 * CommonMark 的 `**` 定界符规则要求右侧不能紧跟标点，导致 markdown-it 判定为
 * 不闭合而原样输出星号。
 *
 * 处理方式（保守，不改变语义）：
 *   1. `**"..."**` / `**“...”**` → 把引号移到加粗外面，保持加粗生效
 *   2. `***文字***` → 统一降级为 `**文字**`（本项目不使用粗斜体）
 */
function normalizeMarkdown(src: string): string {
  let out = src

  // ***xxx*** → **xxx**（避免被解析成 emphasis+strong 的混合失败）
  out = out.replace(/\*\*\*([^*\n]+?)\*\*\*/g, '**$1**')

  // **"xxx"** → "**xxx**"（直引号）
  out = out.replace(/\*\*(["'“”‘’])([^*\n]+?)\1\*\*/g, '$1**$2**$1')

  // **“xxx”** 这类全角引号配对（左右不同字符）
  out = out.replace(/\*\*“([^*\n]+?)”\*\*/g, '“**$1**”')
  out = out.replace(/\*\*‘([^*\n]+?)’\*\*/g, '‘**$1**’')

  return out
}

// 让外链在新窗口打开
const defaultLinkOpen =
  md.renderer.rules.link_open ??
  ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options))

md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  tokens[idx].attrSet('target', '_blank')
  tokens[idx].attrSet('rel', 'noopener noreferrer')
  return defaultLinkOpen(tokens, idx, options, env, self)
}

const html = computed(() => md.render(normalizeMarkdown(props.content || '')))
</script>

<template>
  <div class="row" :class="role">
    <div v-if="role === 'assistant' && showAvatar" class="avatar">
      <BrandMark :size="17" />
    </div>

    <div class="stack">
      <div class="bubble" :class="{ err: !!error }">
        <div v-if="role === 'user'" class="plain">{{ content }}</div>

        <template v-else>
          <div v-if="content" class="prose" v-html="html" />
          <p v-if="streaming" class="streaming-hint">
            <span class="caret">▍</span>
          </p>
          <p v-if="error" class="error">
            <span class="i-lucide-circle-alert" />
            {{ error }}
          </p>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.row {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  animation: fadeUp 0.45s var(--ease-entrance) both;
}

.row.user {
  flex-direction: row-reverse;
}

@keyframes fadeUp {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

.avatar {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  /* 纸色底：品牌标识自带橘色，容器再上橘会撞色 */
  background: var(--bg-void);
  border: 1px solid var(--line-hairline);
}

.stack {
  max-width: min(82%, 760px);
  display: flex;
  flex-direction: column;
}

.row.user .stack {
  align-items: flex-end;
}

.bubble {
  padding: 14px 18px;
  border-radius: 20px 20px 20px 6px;
}

.row.assistant .bubble {
  background: var(--surface-1);
  border: 1px solid var(--line-hairline);
  box-shadow: var(--shadow-panel);
}

.bubble.err {
  border-color: var(--d-35);
}

.row.user .bubble {
  /* 暖色杂志：用户消息是墨色气泡（对齐已确认的预览 B） */
  background: var(--text-primary);
  border: none;
  border-radius: 20px 20px 5px 20px;
  color: var(--text-inverse);
  box-shadow: var(--shadow-sm);
}

.plain {
  font-size: 14.5px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}

/* ---------- Markdown 排版 ---------- */
.prose {
  /* 杂志感：答案正文用衬线，行高更宽 */
  font-family: var(--font-serif);
  font-size: 16px;
  line-height: 1.8;
  color: var(--text-primary);
  word-break: break-word;
}

.prose :deep(h1),
.prose :deep(h2),
.prose :deep(h3),
.prose :deep(h4) {
  font-family: var(--font-display);
  color: var(--text-primary);
  font-weight: 600;
  letter-spacing: -0.01em;
  margin: 20px 0 9px;
  line-height: 1.3;
}

.prose :deep(h1) {
  font-size: 20px;
}
.prose :deep(h2) {
  font-size: 17px;
}
.prose :deep(h3) {
  font-size: 15px;
}

.prose :deep(p) {
  margin: 0 0 12px;
}

.prose :deep(ul),
.prose :deep(ol) {
  margin: 0 0 12px;
  padding-left: 20px;
}

.prose :deep(li) {
  margin: 5px 0;
}

.prose :deep(strong) {
  color: var(--accent-core);
  font-weight: 700;
}

.prose :deep(em) {
  color: var(--text-secondary);
}

.prose :deep(code) {
  padding: 2px 6px;
  border-radius: 6px;
  font-family: var(--font-mono);
  font-size: 12.5px;
  background: var(--surface-code);
  color: var(--accent-core);
  border: 1px solid var(--line-hairline);
}

.prose :deep(pre) {
  padding: 14px;
  border-radius: 12px;
  overflow-x: auto;
  background: var(--surface-code);
  border: 1px solid var(--line-hairline);
  margin: 12px 0;
}

.prose :deep(pre code) {
  background: none;
  border: none;
  padding: 0;
  color: var(--text-secondary);
}

.prose :deep(a) {
  color: var(--accent-blue);
  text-decoration: none;
  border-bottom: 1px solid var(--a-30);
}

.prose :deep(blockquote) {
  margin: 12px 0;
  padding: 8px 14px;
  border-left: 2px solid var(--a-50);
  color: var(--text-secondary);
  background: var(--a-05);
  border-radius: 0 8px 8px 0;
}

.prose :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: 13px;
}

.prose :deep(th),
.prose :deep(td) {
  padding: 8px 12px;
  border: 1px solid var(--line-hairline);
  text-align: left;
}

.prose :deep(th) {
  background: var(--surface-2);
  color: var(--text-secondary);
  font-weight: 600;
}

.prose :deep(hr) {
  border: none;
  border-top: 1px solid var(--line-hairline);
  margin: 16px 0;
}

/* ---------- 流式 / 错误 ---------- */
.streaming-hint {
  margin: 0;
  line-height: 1;
}

.caret {
  display: inline-block;
  color: var(--accent-core);
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
}

.error {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 10px 0 0;
  font-size: 13px;
  color: var(--danger);
}
</style>
