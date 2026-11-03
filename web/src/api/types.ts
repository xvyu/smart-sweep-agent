/**
 * 后端类型定义 —— 与 zsapi/app.py 的响应结构一一对应。
 */

export interface ToolMeta {
  name: string
  label: string
  desc: string
  icon: string
  kind: string
}

export interface UserMonths {
  userId: string
  months: string[]
}

export interface MetaResponse {
  tools: ToolMeta[]
  users: UserMonths[]
}

export interface HealthResponse {
  ok: boolean
  service: string
  version: string
  time: string
  bootstrap: {
    agent_dir: string
    project_dir: string
    cwd: string
    sys_path_ok: boolean
    env_filled: string[]
    deepseek_key_present: boolean
  }
  agent: { ok: boolean; build_ms?: number; warmup_ms?: number; error?: string }
  ollama: { ok: boolean; models?: string[]; has_embedding_model?: boolean; latencyMs?: number; error?: string }
  chroma: { ok: boolean; path?: string; collection?: string; sizeMb?: number; error?: string }
}

/* ------------------------------------------------------------------------- */
/* SSE 事件                                                                   */
/* ------------------------------------------------------------------------- */

export type StreamEventName = 'status' | 'thinking' | 'tool' | 'delta' | 'done' | 'error'

export interface StatusEvent {
  phase: string
  query: string
  report: boolean
}

export interface ThinkingEvent {
  text: string
  step: number
  stepId: string
}

export type ToolStatus = 'running' | 'success' | 'error'

export interface ToolEvent {
  id: string
  name: string
  args: Record<string, unknown>
  status: ToolStatus
  durationMs?: number
  result?: string
}

export interface DeltaEvent {
  text: string
}

export interface DoneEvent {
  durationMs: number
  steps: number
  toolCount: number
  thinkingChars: number
  answerChars: number
}

export interface ErrorEvent {
  message: string
  detail?: string
}

/* ------------------------------------------------------------------------- */
/* 前端内部模型                                                               */
/* ------------------------------------------------------------------------- */

/** 思考步骤（前端聚合后的形态，非后端原样） */
export interface ThinkingStep {
  text: string
  step: number
  at: number
}

/** 工具调用卡片 */
export interface ToolCall {
  id: string
  name: string
  args: Record<string, unknown>
  status: ToolStatus
  durationMs?: number
  result?: string
  startedAt: number
}

export interface UsageRecord {
  userId: string
  feature: string
  efficiency: string
  consumables: string
  comparison: string
  month: string
}

/* ------------------------------------------------------------------------- */
/* 会话持久化                                                                 */
/* ------------------------------------------------------------------------- */

export interface SessionMeta {
  id: string
  title: string
  createdAt: number
  updatedAt: number
  messageCount: number
}

/** 后端存下来的消息（结构对齐前端 ChatMessage） */
export interface StoredMessage {
  id: string
  sessionId: string
  role: 'user' | 'assistant'
  content: string
  thinking: ThinkingStep[]
  tools: ToolCall[]
  stats: DoneEvent | null
  error: string | null
  createdAt: number
}

/* ------------------------------------------------------------------------- */
/* 知识库                                                                     */
/* ------------------------------------------------------------------------- */

export interface KnowledgeItem {
  content: string
  source: string
  sourceName: string
  page: number | null
  pageLabel: string | null
  score: number
  relevance: number
  length: number
}

export interface KnowledgeSearchResult {
  query: string
  k: number
  collection: string
  totalChunks: number
  count: number
  items: KnowledgeItem[]
}

export interface KnowledgeStats {
  ok: boolean
  collection?: string
  totalChunks?: number
  sources?: { name: string; chunks: number }[]
  error?: string
}

/* ------------------------------------------------------------------------- */
/* 数据看板                                                                   */
/* ------------------------------------------------------------------------- */

export interface AnalyticsOverview {
  ok: boolean
  userCount: number
  monthCount: number
  recordCount: number
  months: string[]
  users: string[]
  metrics: {
    avgCoverage: number | null
    avgFilterPercent: number | null
    avgBatteryDecay: number | null
    avgBrushDays: number | null
    sampleCoverage: number
  }
}

export interface UserSummary {
  userId: string
  feature: string
  latestMonth: string
  monthCount: number
  coverage: number | null
  filterPercent: number | null
  batteryDecay: number | null
  comparison: string
}

export interface TrendPoint {
  month: string
  coverage: number | null
  dailyArea: number | null
  brushDays: number | null
  filterPercent: number | null
  batteryDecay: number | null
}

export interface UserDetail {
  ok: boolean
  userId: string
  feature: string
  comparison: string
  latestMonth: string
  trend: TrendPoint[]
  latest: { efficiency: string; consumables: string }
}
