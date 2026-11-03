<script setup lang="ts">
/**
 * ChatComposer —— 底部输入区
 *
 * Enter 发送 / Shift+Enter 换行；中文输入法组合期间不触发发送（关键细节）。
 * 生成中时发送按钮变为「停止」。
 */
import { computed, nextTick, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    disabled?: boolean
    streaming?: boolean
    placeholder?: string
    suggestions?: string[]
  }>(),
  {
    disabled: false,
    streaming: false,
    placeholder: '问问智扫通…',
    suggestions: () => [],
  },
)

const emit = defineEmits<{
  send: [text: string]
  stop: []
}>()

const text = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null)

const canSend = computed(() => text.value.trim().length > 0 && !props.disabled && !props.streaming)

function autoGrow() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 160)}px`
}

function submit() {
  if (!canSend.value) return
  emit('send', text.value.trim())
  text.value = ''
  nextTick(autoGrow)
}

function onKeydown(e: KeyboardEvent) {
  // isComposing：中文输入法候选框未确认时不发送
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    submit()
  }
}

function pick(s: string) {
  text.value = s
  nextTick(() => {
    autoGrow()
    textareaRef.value?.focus()
  })
}
</script>

<template>
  <div class="composer-wrap">
    <div v-if="suggestions.length && !text && !streaming" class="chips">
      <button v-for="s in suggestions" :key="s" class="chip" type="button" @click="pick(s)">
        {{ s }}
      </button>
    </div>

    <div class="composer">
      <textarea
        ref="textareaRef"
        v-model="text"
        rows="1"
        class="ta"
        :placeholder="placeholder"
        :disabled="disabled"
        @input="autoGrow"
        @keydown="onKeydown"
      />

      <button
        v-if="streaming"
        class="btn stop"
        type="button"
        title="停止生成"
        aria-label="停止生成"
        @click="emit('stop')"
      >
        <span class="i-lucide-square" />
      </button>
      <button
        v-else
        class="btn send"
        type="button"
        :disabled="!canSend"
        title="发送"
        aria-label="发送"
        @click="submit"
      >
        <span class="i-lucide-arrow-up" />
      </button>
    </div>

    <p class="hint">Enter 发送 · Shift + Enter 换行 · 回答基于知识库检索，请以实际产品为准</p>
  </div>
</template>

<style scoped>
.composer-wrap {
  flex-shrink: 0;
  padding: 8px 4px 4px;
}

.chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.chip {
  padding: 6px 12px;
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--surface-1);
  border: 1px solid var(--line-hairline);
  border-radius: var(--r-full);
  cursor: pointer;
  transition: all 0.2s var(--ease-standard);
  font-family: inherit;
}

.chip:hover {
  color: var(--accent-core);
  border-color: var(--a-35);
  background: var(--a-08);
}

.composer {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  padding: 14px 14px 14px 18px;
  background: var(--surface-1);
  border: 1px solid var(--line-strong);
  border-radius: var(--r-xl);
  transition:
    border-color 0.2s var(--ease-standard),
    box-shadow 0.2s var(--ease-standard);
}

.composer:focus-within {
  border-color: var(--a-45);
  box-shadow:
    0 0 0 4px var(--a-08),
    0 0 40px var(--a-15);
}

.ta {
  flex: 1;
  resize: none;
  max-height: 160px;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: 15px;
  line-height: 1.7;
}

.ta::placeholder {
  color: var(--text-tertiary);
}

.btn {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: var(--r-md);
  border: none;
  cursor: pointer;
  display: grid;
  place-items: center;
  font-size: 16px;
  transition: all 0.2s var(--ease-standard);
}

.send {
  background: linear-gradient(135deg, var(--accent-core), var(--accent-bright));
  color: var(--text-inverse);
  box-shadow: 0 0 20px var(--a-30);
}

.send:disabled {
  opacity: 0.3;
  box-shadow: none;
  cursor: not-allowed;
}

.send:not(:disabled):hover {
  filter: brightness(1.1);
  transform: translateY(-1px);
}

.stop {
  background: var(--d-15);
  color: var(--danger);
  border: 1px solid var(--d-30);
}

.stop:hover {
  background: var(--d-25);
}

.hint {
  margin: 10px 0 0;
  font-size: 11px;
  color: var(--text-tertiary);
  text-align: center;
  letter-spacing: 0.02em;
}
</style>
