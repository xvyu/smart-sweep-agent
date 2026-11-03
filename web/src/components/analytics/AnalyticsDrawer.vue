<script setup lang="ts">
/**
 * AnalyticsDrawer —— 使用数据看板
 *
 * 侧栏「数据看板」入口指向这里。
 * 数据来自后端 `/api/analytics/*`，由 records.csv 解析而来：
 *   - 概览：10 个用户 × 12 个月，覆盖率/滤网/电池 均值
 *   - 用户列表：每人的户型特征与最新指标
 *   - 用户详情：12 个月趋势折线（用 SVG 手绘，不引图表库）
 */
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../../api/client'
import type { AnalyticsOverview, TrendPoint, UserDetail, UserSummary } from '../../api/types'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()

const overview = ref<AnalyticsOverview | null>(null)
const users = ref<UserSummary[]>([])
const detail = ref<UserDetail | null>(null)
const selectedUser = ref<string | null>(null)
const loading = ref(true)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [ov, us] = await Promise.all([api.analyticsOverview(), api.analyticsUsers()])
    overview.value = ov
    users.value = us.users ?? []
    if (!selectedUser.value && users.value.length) {
      selectUser(users.value[0].userId)
    }
  } catch (err) {
    error.value = (err as Error).message
  } finally {
    loading.value = false
  }
}

async function selectUser(userId: string) {
  selectedUser.value = userId
  try {
    detail.value = await api.analyticsUser(userId)
  } catch {
    detail.value = null
  }
}

/* ------------------------- 折线图（手绘 SVG） ------------------------- */

const CHART_W = 520
const CHART_H = 140
const PAD = 8

const coveragePoints = computed(() => {
  const trend = detail.value?.trend ?? []
  const values = trend.map((t) => t.coverage)
  const nums = values.filter((v): v is number => v != null)
  if (nums.length < 2) return { line: '', area: '', dots: [] as { x: number; y: number; v: number }[] }

  const min = Math.min(...nums) - 2
  const max = Math.max(...nums) + 2
  const span = Math.max(max - min, 1)

  const dots = trend
    .map((t, i) => {
      if (t.coverage == null) return null
      const x = PAD + (i / Math.max(trend.length - 1, 1)) * (CHART_W - PAD * 2)
      const y = PAD + (1 - (t.coverage - min) / span) * (CHART_H - PAD * 2)
      return { x, y, v: t.coverage }
    })
    .filter((d): d is { x: number; y: number; v: number } => d !== null)

  const line = dots.map((d, i) => `${i === 0 ? 'M' : 'L'}${d.x.toFixed(1)},${d.y.toFixed(1)}`).join(' ')
  const area = `${line} L${dots[dots.length - 1].x.toFixed(1)},${CHART_H - PAD} L${dots[0].x.toFixed(1)},${CHART_H - PAD} Z`
  return { line, area, dots }
})

const trendMonths = computed(() => detail.value?.trend.map((t: TrendPoint) => t.month.slice(5)) ?? [])

/* ------------------------- 指标卡 ------------------------- */

const metricCards = computed(() => {
  const m = overview.value?.metrics
  if (!m) return []
  return [
    { label: '平均覆盖率', value: m.avgCoverage, unit: '%', tone: 'accent' },
    { label: '平均滤网余量', value: m.avgFilterPercent, unit: '%', tone: m.avgFilterPercent != null && m.avgFilterPercent < 30 ? 'warn' : 'accent' },
    { label: '平均电池衰减', value: m.avgBatteryDecay, unit: '%', tone: 'warn' },
    { label: '平均主刷余量', value: m.avgBrushDays, unit: '天', tone: 'accent' },
  ]
})

function barWidth(v: number | null, max = 100): string {
  if (v == null) return '0%'
  return `${Math.min(100, Math.max(0, (v / max) * 100))}%`
}

onMounted(load)

watch(
  () => props.open,
  (v) => {
    if (v && !overview.value) load()
  },
  { immediate: true },
)
</script>

<template>
  <Transition name="slide">
    <div v-if="open" class="mask" @click.self="emit('close')">
      <aside class="drawer">
        <header class="head">
          <div class="head-left">
            <span class="i-lucide-file-bar-chart head-ic" />
            <div>
              <h2 class="title">使用数据看板</h2>
              <p class="sub">
                <template v-if="overview">
                  <span class="mono">{{ overview.userCount }}</span> 位用户 ·
                  <span class="mono">{{ overview.monthCount }}</span> 个月 ·
                  <span class="mono">{{ overview.recordCount }}</span> 条记录
                </template>
                <template v-else>正在载入…</template>
              </p>
            </div>
          </div>
          <button class="close" type="button" aria-label="关闭" @click="emit('close')">
            <span class="i-lucide-x" />
          </button>
        </header>

        <div class="scroll">
          <p v-if="error" class="error-line">
            <span class="i-lucide-circle-alert" /> {{ error }}
          </p>

          <!-- 概览指标 -->
          <section class="metrics">
            <div v-for="m in metricCards" :key="m.label" class="metric-card">
              <p class="metric-label">{{ m.label }}</p>
              <p class="metric-value">
                {{ m.value ?? '—' }}<span class="metric-unit">{{ m.unit }}</span>
              </p>
              <div class="track">
                <div
                  class="fill"
                  :class="m.tone"
                  :style="{ width: barWidth(m.value, m.unit === '天' ? 120 : 100) }"
                />
              </div>
            </div>
          </section>

          <!-- 用户列表 -->
          <section>
            <p class="section-title">用户概览（点击查看趋势）</p>
            <div class="user-grid">
              <button
                v-for="u in users"
                :key="u.userId"
                class="user-card"
                :class="{ active: selectedUser === u.userId }"
                type="button"
                @click="selectUser(u.userId)"
              >
                <div class="uc-head">
                  <span class="uc-id mono">{{ u.userId }}</span>
                  <span class="uc-month mono">{{ u.latestMonth }}</span>
                </div>
                <p class="uc-feature">{{ u.feature }}</p>
                <div class="uc-metrics">
                  <span class="uc-m">
                    覆盖率
                    <b class="mono">{{ u.coverage ?? '—' }}%</b>
                  </span>
                  <span class="uc-m">
                    滤网
                    <b class="mono" :class="{ warn: u.filterPercent != null && u.filterPercent < 30 }">
                      {{ u.filterPercent ?? '—' }}%
                    </b>
                  </span>
                </div>
              </button>
            </div>
          </section>

          <!-- 趋势 -->
          <section v-if="detail">
            <p class="section-title">
              覆盖率趋势 · 用户 {{ detail.userId }}
              <span class="dim">{{ detail.feature }}</span>
            </p>

            <div class="chart-wrap">
              <svg :viewBox="`0 0 ${CHART_W} ${CHART_H}`" class="chart" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="covGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="var(--a-35)" />
                    <stop offset="100%" stop-color="var(--a-00)" />
                  </linearGradient>
                </defs>
                <path :d="coveragePoints.area" fill="url(#covGrad)" />
                <path
                  :d="coveragePoints.line"
                  fill="none"
                  stroke="var(--accent-core)"
                  stroke-width="2"
                  stroke-linejoin="round"
                  stroke-linecap="round"
                />
                <circle
                  v-for="(d, i) in coveragePoints.dots"
                  :key="i"
                  :cx="d.x"
                  :cy="d.y"
                  r="3"
                  fill="var(--bg-elevated)"
                  stroke="var(--accent-core)"
                  stroke-width="1.6"
                />
              </svg>
              <div class="chart-x">
                <span v-for="(m, i) in trendMonths" :key="i" class="mono">{{ m }}</span>
              </div>
            </div>

            <div class="detail-grid">
              <div class="detail-block">
                <p class="section-title">最新效率</p>
                <pre class="detail-text">{{ detail.latest.efficiency }}</pre>
              </div>
              <div class="detail-block">
                <p class="section-title">耗材状态</p>
                <pre class="detail-text">{{ detail.latest.consumables }}</pre>
              </div>
            </div>

            <p class="comparison">
              <span class="i-lucide-trending-up" />
              {{ detail.comparison }}
            </p>
          </section>

          <div v-if="loading" class="loading">
            <span class="spinner" /> 正在载入数据…
          </div>
        </div>
      </aside>
    </div>
  </Transition>
</template>

<style scoped>
.mask {
  position: fixed;
  inset: 0;
  z-index: 80;
  background: var(--scrim-60);
  backdrop-filter: blur(3px);
  display: flex;
  justify-content: flex-end;
}

.drawer {
  width: min(680px, 94vw);
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-base);
  border-left: 1px solid var(--line-strong);
  box-shadow: var(--shadow-float);
}

.slide-enter-active,
.slide-leave-active {
  transition: opacity 0.22s var(--ease-standard);
}
.slide-enter-active .drawer,
.slide-leave-active .drawer {
  transition: transform 0.28s var(--ease-entrance);
}
.slide-enter-from,
.slide-leave-to {
  opacity: 0;
}
.slide-enter-from .drawer,
.slide-leave-to .drawer {
  transform: translateX(40px);
}

.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px;
  border-bottom: 1px solid var(--line-hairline);
  flex-shrink: 0;
}

.head-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.head-ic {
  font-size: 20px;
  color: var(--accent-core);
}

.title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.sub {
  margin: 2px 0 0;
  font-size: 11.5px;
  color: var(--text-tertiary);
}

.close {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  border: 1px solid var(--line-hairline);
  background: var(--surface-1);
  color: var(--text-tertiary);
  cursor: pointer;
  display: grid;
  place-items: center;
  font-size: 15px;
  transition: all 0.15s;
}

.close:hover {
  color: var(--danger);
  border-color: var(--d-35);
}

.scroll {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px 28px;
  min-height: 0;
}

.error-line {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  color: var(--danger);
}

.section-title {
  margin: 0 0 10px;
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-faint);
  font-weight: 500;
}

.dim {
  text-transform: none;
  letter-spacing: 0;
  font-size: 10.5px;
  color: var(--text-faint);
  margin-left: 6px;
}

/* ---------- 指标卡 ---------- */
.metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 22px;
}

.metric-card {
  padding: 12px 14px;
  border-radius: var(--r-md);
  background: var(--surface-1);
  border: 1px solid var(--line-hairline);
}

.metric-label {
  margin: 0 0 6px;
  font-size: 10.5px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-tertiary);
}

.metric-value {
  margin: 0 0 8px;
  font-family: var(--font-mono);
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.metric-unit {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-left: 2px;
  font-weight: 400;
}

.track {
  height: 3px;
  border-radius: var(--r-full);
  background: var(--line-hairline);
  overflow: hidden;
}

.fill {
  height: 100%;
  border-radius: var(--r-full);
  transition: width 0.8s var(--ease-entrance);
}

.fill.accent {
  background: linear-gradient(90deg, var(--accent-core), var(--accent-bright));
}

.fill.warn {
  background: linear-gradient(90deg, var(--warn), var(--accent-bright));
}

/* ---------- 用户卡片 ---------- */
.user-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 22px;
}

.user-card {
  padding: 10px 12px;
  border-radius: var(--r-md);
  background: var(--surface-1);
  border: 1px solid var(--line-hairline);
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  transition: all 0.16s;
}

.user-card:hover {
  border-color: var(--a-28);
}

.user-card.active {
  border-color: var(--a-55);
  background: var(--a-07);
}

.uc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.uc-id {
  font-size: 11px;
  color: var(--accent-core);
}

.uc-month {
  font-size: 9.5px;
  color: var(--text-faint);
}

.uc-feature {
  margin: 0 0 6px;
  font-size: 11.5px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.uc-metrics {
  display: flex;
  gap: 12px;
}

.uc-m {
  font-size: 10px;
  color: var(--text-faint);
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.uc-m b {
  font-size: 11.5px;
  color: var(--text-secondary);
  font-weight: 600;
}

.uc-m b.warn {
  color: var(--warn);
}

/* ---------- 折线图 ---------- */
.chart-wrap {
  padding: 10px 12px 6px;
  border-radius: var(--r-md);
  background: var(--surface-1);
  border: 1px solid var(--line-hairline);
  margin-bottom: 16px;
}

.chart {
  width: 100%;
  height: 140px;
  display: block;
}

.chart-x {
  display: flex;
  justify-content: space-between;
  padding: 4px 2px 0;
}

.chart-x span {
  font-size: 9px;
  color: var(--text-faint);
}

/* ---------- 详情 ---------- */
.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.detail-text {
  margin: 0;
  padding: 10px 12px;
  border-radius: var(--r-sm);
  background: var(--surface-code);
  border: 1px solid var(--line-hairline);
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.7;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
}

.comparison {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  padding: 10px 12px;
  border-radius: var(--r-sm);
  background: var(--a-06);
  border-left: 2px solid var(--a-50);
  font-size: 12px;
  color: var(--text-secondary);
}

.loading {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 20px 0;
  font-size: 12.5px;
  color: var(--text-tertiary);
}

.spinner {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid var(--line-strong);
  border-top-color: var(--accent-core);
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 768px) {
  .drawer {
    width: 100vw;
  }
  .metrics,
  .user-grid,
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
