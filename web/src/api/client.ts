/**
 * API 客户端
 *
 * 关键点：EventSource 只支持 GET，无法发送 POST body，
 * 所以流式问答必须用 fetch + ReadableStream 手动解析 SSE。
 * 这里实现了完整的 SSE 帧解析（兼容 \r\n 与 \n、多行 data）。
 */

import type {
  AnalyticsOverview,
  HealthResponse,
  KnowledgeSearchResult,
  KnowledgeStats,
  MetaResponse,
  SessionMeta,
  StoredMessage,
  StreamEventName,
  UsageRecord,
  UserDetail,
  UserSummary,
} from './types'

/** 开发期走 Vite 代理；生产期同源部署时也是相对路径 */
const BASE = '/api'

/* ------------------------------------------------------------------------- */
/* 普通 JSON 请求                                                             */
/* ------------------------------------------------------------------------- */

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      detail = body.detail ?? body.message ?? detail
    } catch {
      /* 忽略解析失败 */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<HealthResponse>('/health'),

  meta: () => request<MetaResponse>('/meta'),

  records: (userId: string) =>
    request<{ userId: string; count: number; records: UsageRecord[] }>(`/records/${userId}`),

  record: (userId: string, month: string) =>
    request<{ ok: boolean; record: UsageRecord }>(`/records/${userId}/${month}`),

  logs: (limit = 80, level?: string) => {
    const qs = new URLSearchParams({ limit: String(limit) })
    if (level) qs.set('level', level)
    return request<{ file: string | null; lines: string[] }>(`/logs?${qs}`)
  },

  /* ---------------------- 会话持久化 ---------------------- */

  sessions: () => request<{ sessions: SessionMeta[] }>('/sessions'),

  createSession: (title = '新对话') =>
    request<{ session: SessionMeta }>('/sessions', {
      method: 'POST',
      body: JSON.stringify({ title }),
    }),

  getSession: (id: string) =>
    request<{ session: SessionMeta; messages: StoredMessage[] }>(`/sessions/${id}`),

  renameSession: (id: string, title: string) =>
    request<{ ok: boolean; session: SessionMeta }>(`/sessions/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    }),

  deleteSession: (id: string) =>
    request<{ ok: boolean; deleted: string }>(`/sessions/${id}`, { method: 'DELETE' }),

  addMessage: (
    sessionId: string,
    payload: {
      role: 'user' | 'assistant'
      content: string
      thinking?: unknown[]
      tools?: unknown[]
      stats?: unknown
      error?: string | null
    },
  ) =>
    request<{ ok: boolean }>(`/sessions/${sessionId}/messages`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /* ---------------------- 知识库 ---------------------- */

  knowledgeStats: () => request<KnowledgeStats>('/knowledge/stats'),

  knowledgeSearch: (q: string, k = 5) => {
    const qs = new URLSearchParams({ q, k: String(k) })
    return request<KnowledgeSearchResult>(`/knowledge/search?${qs}`)
  },

  /* ---------------------- 数据看板 ---------------------- */

  analyticsOverview: () => request<AnalyticsOverview>('/analytics/overview'),

  analyticsUsers: () => request<{ ok: boolean; users: UserSummary[] }>('/analytics/users'),

  analyticsUser: (userId: string) => request<UserDetail>(`/analytics/user/${userId}`),
}

/* ------------------------------------------------------------------------- */
/* SSE 流式问答                                                               */
/* ------------------------------------------------------------------------- */

export interface StreamHandlers {
  onEvent: (name: StreamEventName, data: unknown) => void
  signal?: AbortSignal
}

/**
 * 发起流式问答并逐帧回调。
 *
 * 为什么手写解析而不用 EventSource：
 *   1. EventSource 不支持 POST
 *   2. EventSource 会自动重连，但问答场景不需要重连（会重复生成）
 */
export async function streamChat(
  message: string,
  report: boolean,
  handlers: StreamHandlers,
): Promise<void> {
  const res = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify({ message, report }),
    signal: handlers.signal,
  })

  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      detail = body.detail ?? body.message ?? detail
    } catch {
      /* 忽略 */
    }
    throw new Error(detail)
  }

  if (!res.body) {
    throw new Error('当前浏览器不支持流式响应（ReadableStream）')
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // SSE 以空行分隔事件；同时兼容 \r\n
      let boundary = buffer.search(/\r?\n\r?\n/)
      while (boundary !== -1) {
        const rawFrame = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + (buffer[boundary] === '\r' ? 4 : 2))

        const parsed = parseFrame(rawFrame)
        if (parsed) {
          handlers.onEvent(parsed.name, parsed.data)
        }
        boundary = buffer.search(/\r?\n\r?\n/)
      }
    }

    // 处理可能残留的最后一帧（服务端未以空行结尾的极端情况）
    const tail = parseFrame(buffer)
    if (tail) handlers.onEvent(tail.name, tail.data)
  } finally {
    reader.releaseLock()
  }
}

/** 解析单个 SSE 帧：`event: xxx\ndata: {...}` */
function parseFrame(frame: string): { name: StreamEventName; data: unknown } | null {
  const text = frame.trim()
  if (!text) return null

  let name: string | null = null
  const dataLines: string[] = []

  for (const line of text.split(/\r?\n/)) {
    if (line.startsWith('event:')) {
      name = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart())
    }
  }

  if (!name) return null

  const raw = dataLines.join('\n')
  let data: unknown = null
  try {
    data = raw ? JSON.parse(raw) : null
  } catch {
    data = { text: raw }
  }

  return { name: name as StreamEventName, data }
}
