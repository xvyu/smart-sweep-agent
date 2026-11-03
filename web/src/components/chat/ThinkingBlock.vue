<script setup lang="ts">
/**
 * ThinkingBlock —— ReAct 思考过程折叠块
 *
 * 这是本产品的视觉主角：让 AI 的推理过程成为可观看的对象。
 * - 竖向时间轴 + 渐变竖线，节点在最后一颗时脉冲（表示"正在想"）
 * - 进行中时整块有扫描线扫过（动效即状态）
 */
import { computed, ref } from 'vue'
import type { ThinkingStep } from '../../api/types'

const props = withDefaults(
  defineProps<{
    steps: ThinkingStep[]
    running?: boolean
    durationMs?: number
  }>(),
  { running: false },
)

const open = ref(true)

const stepCount = computed(() => props.steps.length)
const joined = computed(() => props.steps.map((s) => s.text).join(''))
const durationText = computed(() =>
  props.durationMs != null ? `${(props.durationMs / 1000).toFixed(1)}s` : null,
)
</script>

<template>
  <div class="think" :class="{ running }">
    <button class="head" type="button" @click="open = !open">
      <span class="glyph">◇</span>
      <span class="title">思考过程</span>
      <span class="count mono">{{ stepCount }} 步</span>
      <span v-if="durationText" class="dur mono">{{ durationText }}</span>
      <span v-else-if="running" class="dur mono thinking-live">思考中</span>
      <span class="i-lucide-chevron-down chev" :class="{ rot: open }" />
    </button>

    <div v-if="open && steps.length" class="timeline">
      <div v-for="(s, i) in steps" :key="`${s.step}-${i}`" class="step">
        <span class="node" :class="{ last: i === steps.length - 1 && running }" />
        <p class="txt">{{ s.text }}</p>
      </div>
    </div>

    <div v-else-if="open && !steps.length" class="timeline">
      <div class="step">
        <span class="node last" />
        <p class="txt dim">正在理解你的问题…</p>
      </div>
    </div>

    <!-- 折叠时给一行摘要，避免信息完全丢失 -->
    <p v-if="!open && joined" class="summary">{{ joined.slice(0, 120) }}{{ joined.length > 120 ? '…' : '' }}</p>
  </div>
</template>

<style scoped>
.think {
  position: relative;
  border-radius: var(--r-lg);
  overflow: hidden;
  background: var(--surface-1);
  border: 1px solid var(--line-hairline);
  margin-bottom: 12px;
}

/* 进行中：扫描线扫过 */
.think.running::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(
    100deg,
    transparent 30%,
    var(--a-12) 50%,
    transparent 70%
  );
  background-size: 200% 100%;
  animation: scan 2.4s linear infinite;
}

@keyframes scan {
  from {
    background-position: 200% 0;
  }
  to {
    background-position: -100% 0;
  }
}

.head {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: transparent;
  border: none;
  cursor: pointer;
  font-family: inherit;
  position: relative;
  z-index: 1;
}

.glyph {
  color: var(--accent-core);
  font-size: 13px;
}

.title {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.count,
.dur {
  font-size: 11px;
  color: var(--text-tertiary);
}

.dur {
  margin-left: auto;
}

.thinking-live {
  color: var(--accent-core);
  animation: fade 1.4s ease-in-out infinite;
}

@keyframes fade {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}

.chev {
  font-size: 14px;
  color: var(--text-tertiary);
  transition: transform 0.2s var(--ease-standard);
}

.rot {
  transform: rotate(180deg);
}

.timeline {
  padding: 4px 16px 16px;
  position: relative;
  z-index: 1;
}

.step {
  position: relative;
  padding-left: 22px;
  padding-bottom: 14px;
}

.step::before {
  content: '';
  position: absolute;
  left: 4px;
  top: 12px;
  bottom: 0;
  width: 1px;
  background: linear-gradient(180deg, var(--a-50), var(--a-08));
}

.step:last-child {
  padding-bottom: 0;
}

.step:last-child::before {
  display: none;
}

.node {
  position: absolute;
  left: 0;
  top: 5px;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--bg-elevated);
  border: 1.5px solid var(--a-60);
}

.node.last {
  background: var(--accent-core);
  box-shadow: 0 0 10px var(--accent-core);
  animation: pulse 1.4s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.35;
  }
}

.txt {
  margin: 0;
  font-size: 13px;
  line-height: 1.75;
  color: var(--text-secondary);
  white-space: pre-wrap;
}

.txt.dim {
  color: var(--text-tertiary);
}

.summary {
  margin: 0;
  padding: 0 16px 14px 40px;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
