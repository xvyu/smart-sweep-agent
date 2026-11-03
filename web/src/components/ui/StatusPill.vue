<script setup lang="ts">
/**
 * StatusPill —— 呼吸点状态胶囊
 * 用于顶栏展示 RAG 连接状态。
 */
withDefaults(
  defineProps<{
    label: string
    tone?: 'ok' | 'warn' | 'danger'
    dot?: boolean
  }>(),
  { tone: 'ok', dot: true },
)
</script>

<template>
  <div class="pill" :class="`tone-${tone}`">
    <span v-if="dot" class="dot" />
    <span class="txt">{{ label }}</span>
  </div>
</template>

<style scoped>
.pill {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 12px;
  border-radius: var(--r-full);
  white-space: nowrap;
}

.tone-ok {
  background: var(--g-08);
  border: 1px solid var(--g-25);
}
.tone-ok .dot {
  background: var(--ok);
  box-shadow: 0 0 8px var(--ok);
}
.tone-ok .txt {
  color: var(--ok);
}

.tone-warn {
  background: var(--w-08);
  border: 1px solid var(--w-25);
}
.tone-warn .dot {
  background: var(--warn);
  box-shadow: 0 0 8px var(--warn);
}
.tone-warn .txt {
  color: var(--warn);
}

.tone-danger {
  background: var(--d-08);
  border: 1px solid var(--d-25);
}
.tone-danger .dot {
  background: var(--danger);
  box-shadow: 0 0 8px var(--danger);
}
.tone-danger .txt {
  color: var(--danger);
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  animation: breathe 2s ease-in-out infinite;
}

@keyframes breathe {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}

.txt {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.03em;
}
</style>
