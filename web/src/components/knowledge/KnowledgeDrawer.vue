<script setup lang="ts">
/**
 * KnowledgeDrawer —— 知识库抽屉
 *
 * 顶栏「知识库」按钮与侧栏「知识库检索」入口都指向这里。
 * 直接调用后端 `/api/knowledge/search` 做向量检索，
 * 把「到底命中了哪些片段、来自哪个文件第几页、相关度多少」摊开展示，
 * 而不是让用户只看一段被模型总结过的文字。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../../api/client'
import type { KnowledgeItem, KnowledgeSearchResult, KnowledgeStats } from '../../api/types'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()

const query = ref('')
const k = ref(5)
const loading = ref(false)
const result = ref<KnowledgeSearchResult | null>(null)
const stats = ref<KnowledgeStats | null>(null)
const error = ref('')

const presetQueries = [
  '滤网清洗周期',
  '滚刷缠毛处理',
  '小户型选购',
  '回南天防潮',
  '电池保养',
]

const hasResult = computed(() => (result.value?.items.length ?? 0) > 0)

async function loadStats() {
  try {
    stats.value = await api.knowledgeStats()
  } catch {
    stats.value = null
  }
}

async function search(q?: string) {
  const text = (q ?? query.value).trim()
  if (!text || loading.value) return
  query.value = text
  loading.value = true
  error.value = ''
  try {
    result.value = await api.knowledgeSearch(text, k.value)
  } catch (err) {
    error.value = (err as Error).message
    result.value = null
  } finally {
    loading.value = false
  }
}

function relevancePercent(item: KnowledgeItem): number {
  return Math.round(item.relevance * 100)
}

function toneOf(item: KnowledgeItem): 'accent' | 'warn' {
  return item.relevance >= 0.5 ? 'accent' : 'warn'
}

/** 高亮查询词（简单包含匹配，够用且无依赖） */
function highlight(text: string): string {
  const q = query.value.trim()
  const safe = text.replace(/[<>&]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' })[c] ?? c)
  if (!q) return safe
  const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return safe.replace(new RegExp(escaped, 'gi'), (m) => `<mark>${m}</mark>`)
}

onMounted(loadStats)

// 每次打开时刷新统计（知识库可能刚更新）
watch(
  () => props.open,
  (v) => {
    if (v) {
      loadStats()
      if (!result.value) search(presetQueries[0])
    }
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
            <span class="i-lucide-library head-ic" />
            <div>
              <h2 class="title">知识库</h2>
              <p class="sub">
                向量检索 · 共
                <span class="mono">{{ stats?.totalChunks ?? '—' }}</span>
                个切片
              </p>
            </div>
          </div>
          <button class="close" type="button" aria-label="关闭" @click="emit('close')">
            <span class="i-lucide-x" />
          </button>
        </header>

        <!-- 检索栏 -->
        <div class="searchbar">
          <span class="i-lucide-search sb-ic" />
          <input
            v-model="query"
            class="sb-input"
            placeholder="检索知识库，例如：滤网多久清洗一次"
            @keydown.enter="search()"
          />
          <select v-model.number="k" class="sb-k" title="返回条数">
            <option :value="3">3 条</option>
            <option :value="5">5 条</option>
            <option :value="10">10 条</option>
          </select>
          <button class="sb-btn" type="button" :disabled="loading || !query.trim()" @click="search()">
            {{ loading ? '检索中' : '检索' }}
          </button>
        </div>

        <div class="presets">
          <button
            v-for="p in presetQueries"
            :key="p"
            class="preset"
            type="button"
            @click="search(p)"
          >
            {{ p }}
          </button>
        </div>

        <!-- 来源分布 -->
        <section v-if="stats?.sources?.length" class="sources">
          <p class="section-title">知识来源</p>
          <div class="source-list">
            <div v-for="s in stats.sources" :key="s.name" class="source-row">
              <span class="i-lucide-file-text src-ic" />
              <span class="src-name">{{ s.name }}</span>
              <span class="src-count mono">{{ s.chunks }}</span>
            </div>
          </div>
        </section>

        <!-- 结果 -->
        <section class="results">
          <p class="section-title">
            检索结果
            <span v-if="result" class="mono dim">
              「{{ result.query }}」命中 {{ result.count }} 条
            </span>
          </p>

          <p v-if="error" class="error-line">
            <span class="i-lucide-circle-alert" /> {{ error }}
          </p>

          <div v-if="loading" class="loading">
            <span class="spinner" /> 正在检索向量库…
          </div>

          <div v-else-if="!hasResult && result" class="empty">
            没有命中片段，换个说法试试
          </div>

          <article v-for="(item, i) in result?.items ?? []" :key="i" class="card">
            <header class="card-head">
              <span class="rank mono">{{ String(i + 1).padStart(2, '0') }}</span>
              <span class="src">
                {{ item.sourceName }}
                <span v-if="item.pageLabel || item.page != null" class="page">
                  · p{{ item.pageLabel ?? (item.page ?? 0) + 1 }}
                </span>
              </span>
              <span class="rel mono" :class="toneOf(item)">{{ relevancePercent(item) }}%</span>
            </header>

            <div class="rel-track">
              <div
                class="rel-fill"
                :class="toneOf(item)"
                :style="{ width: relevancePercent(item) + '%' }"
              />
            </div>

            <p class="content" v-html="highlight(item.content)" />

            <footer class="card-foot mono">
              {{ item.length }} 字 · 距离 {{ item.score }}
            </footer>
          </article>
        </section>
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
  width: min(640px, 94vw);
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-base);
  border-left: 1px solid var(--line-strong);
  box-shadow: var(--shadow-float);
  overflow: hidden;
}

/* 入场动画 */
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

/* ---------- 检索栏 ---------- */
.searchbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 16px 20px 10px;
  padding: 8px 8px 8px 14px;
  background: var(--surface-2);
  border: 1px solid var(--line-hairline);
  border-radius: var(--r-md);
  flex-shrink: 0;
  transition: border-color 0.2s;
}

.searchbar:focus-within {
  border-color: var(--a-45);
  box-shadow: 0 0 0 3px var(--a-08);
}

.sb-ic {
  font-size: 14px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.sb-input {
  flex: 1;
  min-width: 0;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-size: 13.5px;
  font-family: inherit;
}

.sb-input::placeholder {
  color: var(--text-faint);
}

.sb-k {
  background: var(--surface-1);
  border: 1px solid var(--line-hairline);
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 11.5px;
  padding: 4px 6px;
  font-family: inherit;
  cursor: pointer;
}

.sb-btn {
  padding: 7px 14px;
  border-radius: var(--r-sm);
  border: none;
  background: linear-gradient(135deg, var(--accent-core), var(--accent-bright));
  color: var(--text-inverse);
  font-size: 12.5px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  flex-shrink: 0;
}

.sb-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.presets {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  padding: 0 20px 14px;
  flex-shrink: 0;
}

.preset {
  padding: 5px 10px;
  font-size: 11.5px;
  color: var(--text-tertiary);
  background: var(--surface-1);
  border: 1px solid var(--line-hairline);
  border-radius: var(--r-full);
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
}

.preset:hover {
  color: var(--accent-core);
  border-color: var(--a-35);
}

/* ---------- 来源 ---------- */
.sources {
  padding: 0 20px 14px;
  border-bottom: 1px solid var(--line-hairline);
  flex-shrink: 0;
}

.section-title {
  margin: 0 0 8px;
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-faint);
  font-weight: 500;
}

.dim {
  color: var(--text-faint);
  text-transform: none;
  letter-spacing: 0;
  font-size: 10.5px;
  margin-left: 6px;
}

.source-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.source-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 9px;
  border-radius: var(--r-full);
  background: var(--surface-1);
  border: 1px solid var(--line-hairline);
}

.src-ic {
  font-size: 11px;
  color: var(--text-tertiary);
}

.src-name {
  font-size: 11px;
  color: var(--text-secondary);
}

.src-count {
  font-size: 10px;
  color: var(--accent-core);
}

/* ---------- 结果 ---------- */
.results {
  flex: 1;
  overflow-y: auto;
  padding: 14px 20px 24px;
  min-height: 0;
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

.error-line {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  color: var(--danger);
}

.empty {
  padding: 24px 0;
  font-size: 12.5px;
  color: var(--text-faint);
  text-align: center;
}

.card {
  padding: 12px 14px;
  margin-bottom: 10px;
  border-radius: var(--r-md);
  background: var(--surface-1);
  border: 1px solid var(--line-hairline);
  transition: border-color 0.18s;
}

.card:hover {
  border-color: var(--a-28);
}

.card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.rank {
  font-size: 10.5px;
  color: var(--accent-core);
  letter-spacing: 0.05em;
}

.src {
  font-size: 11.5px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.page {
  color: var(--text-faint);
}

.rel {
  margin-left: auto;
  font-size: 11px;
  flex-shrink: 0;
}

.rel.accent {
  color: var(--ok);
}

.rel.warn {
  color: var(--warn);
}

.rel-track {
  height: 3px;
  border-radius: var(--r-full);
  background: var(--line-hairline);
  overflow: hidden;
  margin-bottom: 10px;
}

.rel-fill {
  height: 100%;
  border-radius: var(--r-full);
  transition: width 0.6s var(--ease-entrance);
}

.rel-fill.accent {
  background: linear-gradient(90deg, var(--accent-core), var(--accent-bright));
}

.rel-fill.warn {
  background: linear-gradient(90deg, var(--warn), var(--accent-bright));
}

.content {
  margin: 0 0 8px;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 180px;
  overflow-y: auto;
}

.content :deep(mark) {
  background: var(--a-25);
  color: var(--accent-core);
  border-radius: 3px;
  padding: 0 2px;
}

.card-foot {
  font-size: 10px;
  color: var(--text-faint);
}

@media (max-width: 768px) {
  .drawer {
    width: 100vw;
  }
}
</style>
