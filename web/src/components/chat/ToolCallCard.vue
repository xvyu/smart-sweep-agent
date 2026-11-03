<script setup lang="ts">
/**
 * ToolCallCard —— 工具调用卡片
 *
 * 展示一次工具调用的完整生命周期：名称 → 参数 → 结果 → 耗时 → 成败。
 * 左侧 3px 竖条的颜色即状态：蓝=进行中，绿=成功，红=失败。
 */
import { computed, ref } from 'vue'
import type { ToolCall } from '../../api/types'

const props = defineProps<{ call: ToolCall }>()

const open = ref(false)

const tone = computed(
  () =>
    ({
      running: 'var(--accent-blue)',
      success: 'var(--ok)',
      error: 'var(--danger)',
    })[props.call.status],
)

const hasArgs = computed(() => Object.keys(props.call.args ?? {}).length > 0)

const argsText = computed(() => {
  const a = props.call.args
  if (!a || !Object.keys(a).length) return '{}'
  return JSON.stringify(a, null, 2)
})

const statusLabel = computed(
  () =>
    ({
      running: '执行中',
      success: '成功',
      error: '失败',
    })[props.call.status],
)
</script>

<template>
  <div class="tool" :style="{ '--tone': tone }">
    <div class="bar" />

    <button class="head" type="button" @click="open = !open">
      <span class="dot" />
      <span class="name">{{ call.name }}</span>
      <span class="status-txt">{{ statusLabel }}</span>

      <span class="meta">
        <span v-if="call.durationMs != null" class="ms mono">{{ call.durationMs }}ms</span>
        <span v-if="call.status === 'success'" class="i-lucide-check icon" />
        <span v-else-if="call.status === 'error'" class="i-lucide-x icon" />
        <span v-else class="spinner" />
        <span class="i-lucide-chevron-down chev" :class="{ rot: open }" />
      </span>
    </button>

    <div v-if="open" class="body">
      <template v-if="hasArgs">
        <p class="label">参数</p>
        <pre class="code">{{ argsText }}</pre>
      </template>

      <template v-if="call.result">
        <p class="label">结果</p>
        <pre class="code res">{{ call.result }}</pre>
      </template>

      <p v-if="!hasArgs && !call.result" class="empty">
        {{ call.status === 'running' ? '正在等待返回…' : '该工具无参数与返回值' }}
      </p>
    </div>
  </div>
</template>

<style scoped>
.tool {
  position: relative;
  border-radius: 14px;
  overflow: hidden;
  background: var(--surface-1);
  border: 1px solid var(--line-hairline);
  margin-bottom: 12px;
}

.bar {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--tone);
  box-shadow: 0 0 12px var(--tone);
  transition: background 0.3s;
}

.head {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 14px 11px 18px;
  background: transparent;
  border: none;
  cursor: pointer;
  font-family: inherit;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--tone);
  box-shadow: 0 0 8px var(--tone);
  flex-shrink: 0;
}

.name {
  font-family: var(--font-mono);
  font-size: 12.5px;
  color: var(--text-primary);
  font-weight: 500;
}

.status-txt {
  font-size: 10.5px;
  color: var(--tone);
  letter-spacing: 0.04em;
  opacity: 0.9;
}

.meta {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-tertiary);
  font-size: 11px;
}

.ms {
  font-size: 11px;
}

.icon {
  font-size: 13px;
  color: var(--tone);
}

.chev {
  font-size: 14px;
  transition: transform 0.2s var(--ease-standard);
}

.rot {
  transform: rotate(180deg);
}

.spinner {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 1.5px solid var(--line-strong);
  border-top-color: var(--tone);
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.body {
  padding: 0 14px 14px 18px;
  border-top: 1px solid var(--line-hairline);
}

.label {
  margin: 12px 0 6px;
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text-tertiary);
  font-weight: 500;
}

.code {
  margin: 0;
  padding: 10px 12px;
  border-radius: 10px;
  overflow-x: auto;
  max-height: 260px;
  overflow-y: auto;
  background: var(--surface-code);
  border: 1px solid var(--line-hairline);
  font-family: var(--font-mono);
  font-size: 11.5px;
  line-height: 1.65;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
}

.res {
  color: var(--text-secondary);
}

.empty {
  margin: 12px 0 0;
  font-size: 12px;
  color: var(--text-tertiary);
}
</style>
