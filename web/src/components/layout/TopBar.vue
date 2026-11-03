<script setup lang="ts">
/**
 * TopBar —— 顶部栏（方案 1 · 刊头 Masthead）
 *
 * 阅读动线：品牌 › 竖线 › 当前会话，形成一条自然的左向起点；
 * 右侧集中承载「产品事实」（知识库切片数 / 文档数 / 用户数）与连接状态。
 *
 * 数据来自后端真实接口（/api/knowledge/stats、/api/meta），不是写死的装饰。
 */
import StatusPill from '../ui/StatusPill.vue'
import BrandMark from '../ui/BrandMark.vue'

export interface TopBarStats {
  chunks: number
  docs: number
  users: number
}

withDefaults(
  defineProps<{
    sessionTitle?: string
    statusLabel?: string
    statusTone?: 'ok' | 'warn' | 'danger'
    stats?: TopBarStats | null
  }>(),
  {
    sessionTitle: '新对话',
    statusLabel: 'RAG 已连接',
    statusTone: 'ok',
    stats: null,
  },
)

defineEmits<{ toggleInspector: []; openKnowledge: [] }>()
</script>

<template>
  <header class="topbar">
    <!-- 品牌 -->
    <div class="brand">
      <BrandMark :size="30" />
      <div class="btxt">
        <span class="bn">智扫通</span>
        <span class="bs">ZhiSaoTong</span>
      </div>
    </div>

    <span class="vr" aria-hidden="true" />

    <!-- 当前会话 -->
    <div class="sess">
      <span class="lbl">当前会话</span>
      <span class="val" :title="sessionTitle">{{ sessionTitle }}</span>
    </div>

    <div class="spacer" />

    <!-- 产品事实（真实数据） -->
    <div v-if="stats" class="facts" aria-label="知识库概况">
      <span class="fact"><b class="mono">{{ stats.chunks }}</b> 切片</span>
      <span class="fact"><b class="mono">{{ stats.docs }}</b> 文档</span>
      <span class="fact"><b class="mono">{{ stats.users }}</b> 用户</span>
    </div>

    <StatusPill :label="statusLabel" :tone="statusTone" />

    <div class="r">
      <button
        class="icon-btn"
        type="button"
        title="知识库"
        aria-label="打开知识库"
        @click="$emit('openKnowledge')"
      >
        <span class="i-lucide-library" />
      </button>
      <button
        class="icon-btn"
        type="button"
        title="切换检查器"
        aria-label="切换检查器"
        @click="$emit('toggleInspector')"
      >
        <span class="i-lucide-panel-right" />
      </button>
    </div>
  </header>
</template>

<style scoped>
.topbar {
  height: 64px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 22px;
  border-bottom: 1px solid var(--line-hairline);
  /* 顶栏下方是粒子层：半透明纸色 + 模糊 = 真正的毛玻璃 */
  background: rgba(253, 251, 247, 0.88);
  backdrop-filter: blur(14px) saturate(130%);
  position: relative;
  z-index: 30;
}

/* ---------- 品牌 ---------- */
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.btxt {
  display: flex;
  flex-direction: column;
  line-height: 1.12;
}

.bn {
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--text-primary);
}

.bs {
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--text-faint);
  margin-top: 2px;
}

/* ---------- 分隔竖线 ---------- */
.vr {
  width: 1px;
  height: 26px;
  background: var(--line-hairline);
  flex-shrink: 0;
}

/* ---------- 当前会话 ---------- */
.sess {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex-shrink: 1;
}

.sess .lbl {
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-faint);
}

.sess .val {
  font-size: 13.5px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 360px;
}

.spacer {
  flex: 1;
  min-width: 12px;
}

/* ---------- 产品事实 ---------- */
.facts {
  display: flex;
  align-items: center;
  gap: 0;
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.fact {
  padding: 3px 12px;
  border-right: 1px solid var(--line-hairline);
  white-space: nowrap;
}

.fact:last-child {
  border-right: none;
}

.fact b {
  color: var(--accent-core);
  font-weight: 500;
}

.r {
  display: flex;
  align-items: center;
  gap: 9px;
  flex-shrink: 0;
}

.icon-btn {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  background: var(--surface-1);
  border: 1px solid var(--line-hairline);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 15px;
  transition: all 0.2s var(--ease-standard);
}

.icon-btn:hover {
  color: var(--accent-core);
  border-color: var(--a-35);
  background: var(--a-08);
}

/* ---------- 窄屏降级 ---------- */
@media (max-width: 1180px) {
  .facts {
    display: none;
  }
}

@media (max-width: 900px) {
  .sess,
  .vr {
    display: none;
  }
  .topbar {
    gap: 12px;
    padding: 0 14px;
  }
}
</style>
