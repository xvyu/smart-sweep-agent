/**
 * useChat —— 对话状态机
 *
 * 职责：
 *   1. 把 SSE 事件流聚合成「可渲染的消息结构」
 *   2. 把完整的消息持久化到后端（会话可回看、刷新不丢）
 *
 * 聚合规则（本项目的核心逻辑）：
 *   - thinking 事件是**逐字**到达的，不能每个字建一个步骤 →
 *     同一 step 的文本累积到同一个 ThinkingStep 上
 *   - tool 事件先 running 后 success/error，用 id 合并到同一个 ToolCall
 *   - delta 事件逐字拼接到当前助手的 answer 上
 *   - done / error 结束本轮，解除 streaming 状态
 *
 * 持久化策略：
 *   - 用户消息：发送时立即落库（即使生成失败也保留提问）
 *   - 助手消息：`done`/`error`/中断后整条落库（不逐 token 写库）
 *   - 落库失败不阻塞 UI，只在控制台告警（离线也能继续对话）
 *
 * 为什么思考要合并：
 *   后端 stream_mode="messages" 是 token 级流，一次回答会产生 150+ 个
 *   thinking 事件。若逐条渲染会有 150 行，完全不可读。按 step 合并后
 *   通常只有 1-3 段，正好对应 ReAct 的 1-3 轮思考。
 */

import { reactive, ref } from 'vue'
import { api, streamChat } from '../api/client'
import type {
  DoneEvent,
  ErrorEvent,
  StoredMessage,
  ThinkingStep,
  ToolCall,
  ToolEvent,
} from '../api/types'

export type Role = 'user' | 'assistant'

export interface ChatMessage {
  id: string
  role: Role
  /** 用户消息原文 / 助手最终答案（Markdown） */
  content: string
  /** 助手的思考步骤（仅 assistant） */
  thinking: ThinkingStep[]
  /** 助手的工具调用（仅 assistant） */
  tools: ToolCall[]
  /** 是否正在流式输出 */
  streaming: boolean
  /** 是否出错 */
  error?: string
  /** 本轮统计 */
  stats?: DoneEvent
  /** 时间戳（毫秒） */
  at: number
}

let seq = 0
const nextId = (prefix: string) => `${prefix}-${Date.now()}-${seq++}`

export function useChat() {
  const messages = reactive<ChatMessage[]>([])
  const streaming = ref(false)
  const currentQuery = ref('')
  /** 当前会话 ID（null 表示尚未创建，首次发送时自动创建） */
  const sessionId = ref<string | null>(null)

  let controller: AbortController | null = null
  /** 当前正在生成的助手消息（引用） */
  let active: ChatMessage | null = null

  /* --------------------------------------------------------------------- */
  /* 消息构造与聚合                                                         */
  /* --------------------------------------------------------------------- */

  function ensureAssistant(): ChatMessage {
    if (active) return active
    const msg: ChatMessage = {
      id: nextId('a'),
      role: 'assistant',
      content: '',
      thinking: [],
      tools: [],
      streaming: true,
      at: Date.now(),
    }
    messages.push(msg)
    active = msg
    return msg
  }

  /** 把逐字到达的 thinking 文本合并到对应 step */
  function appendThinking(text: string, step: number) {
    const msg = ensureAssistant()
    const last = msg.thinking[msg.thinking.length - 1]
    if (last && last.step === step) {
      last.text += text
      last.at = Date.now()
    } else {
      msg.thinking.push({ text, step, at: Date.now() })
    }
  }

  /** 合并工具调用状态（先 running，后 success/error） */
  function upsertTool(ev: ToolEvent) {
    const msg = ensureAssistant()
    const existing = msg.tools.find((t) => t.id === ev.id)
    if (existing) {
      existing.status = ev.status
      if (ev.args && Object.keys(ev.args).length) existing.args = ev.args
      if (ev.durationMs != null) existing.durationMs = ev.durationMs
      if (ev.result != null) existing.result = ev.result
      // 工具名可能是首包才带，后续补全
      if (ev.name && ev.name !== 'unknown') existing.name = ev.name
    } else {
      msg.tools.push({
        id: ev.id,
        name: ev.name,
        args: ev.args ?? {},
        status: ev.status,
        durationMs: ev.durationMs,
        result: ev.result,
        startedAt: Date.now(),
      })
    }
  }

  /* --------------------------------------------------------------------- */
  /* 持久化                                                                 */
  /* --------------------------------------------------------------------- */

  /** 确保会话已创建，返回会话 ID */
  async function ensureSession(_firstMessage: string): Promise<string | null> {
    if (sessionId.value) return sessionId.value
    try {
      // 标题统一交给后端处理：后端会在首条用户消息写入时自动命名。
      // 前端若也用提问命名，会与后端逻辑重复且顺序不确定。
      const { session } = await api.createSession('新对话')
      sessionId.value = session.id
      return session.id
    } catch (err) {
      console.warn('[useChat] 创建会话失败（离线模式继续）：', err)
      return null
    }
  }

  /** 落库单条消息，失败不抛出 */
  async function persistMessage(msg: ChatMessage, sid: string | null) {
    if (!sid) return
    try {
      await api.addMessage(sid, {
        role: msg.role,
        content: msg.content,
        thinking: msg.role === 'assistant' ? msg.thinking : undefined,
        tools: msg.role === 'assistant' ? msg.tools : undefined,
        stats: msg.stats,
        error: msg.error ?? null,
      })
    } catch (err) {
      console.warn('[useChat] 消息落库失败：', err)
    }
  }

  /* --------------------------------------------------------------------- */
  /* 发送                                                                   */
  /* --------------------------------------------------------------------- */

  async function send(text: string, opts: { report?: boolean } = {}) {
    const query = text.trim()
    if (!query || streaming.value) return

    currentQuery.value = query
    streaming.value = true
    active = null

    // 用户消息（先入 UI）
    const userMsg: ChatMessage = {
      id: nextId('u'),
      role: 'user',
      content: query,
      thinking: [],
      tools: [],
      streaming: false,
      at: Date.now(),
    }
    messages.push(userMsg)

    // 先建会话再落库用户消息
    const sid = await ensureSession(query)
    void persistMessage(userMsg, sid)

    controller = new AbortController()

    try {
      await streamChat(query, opts.report ?? false, {
        signal: controller.signal,
        onEvent(name, data) {
          switch (name) {
            case 'thinking': {
              const d = data as { text: string; step: number }
              appendThinking(d.text, d.step)
              break
            }
            case 'tool':
              upsertTool(data as ToolEvent)
              break
            case 'delta': {
              const d = data as { text: string }
              ensureAssistant().content += d.text
              break
            }
            case 'done': {
              const d = data as DoneEvent
              const msg = ensureAssistant()
              msg.stats = d
              msg.streaming = false
              break
            }
            case 'error': {
              const d = data as ErrorEvent
              const msg = ensureAssistant()
              msg.error = d.message
              msg.streaming = false
              if (d.detail) console.error('[zsapi]', d.detail)
              break
            }
            default:
              break
          }
        },
      })
    } catch (err) {
      const msg = ensureAssistant()
      if ((err as Error).name === 'AbortError') {
        msg.error = undefined
        msg.content = msg.content || '（已停止生成）'
      } else {
        msg.error = `请求失败：${(err as Error).message}`
      }
      msg.streaming = false
    } finally {
      const finished = active
      if (finished) {
        ;(finished as ChatMessage).streaming = false
        // 助手消息整条落库
        void persistMessage(finished as ChatMessage, sid)
      }
      active = null
      streaming.value = false
      controller = null
    }
  }

  function stop() {
    controller?.abort()
  }

  /** 清空当前会话（不删除后端记录） */
  function reset() {
    controller?.abort()
    messages.splice(0, messages.length)
    active = null
    streaming.value = false
    currentQuery.value = ''
    sessionId.value = null
  }

  /* --------------------------------------------------------------------- */
  /* 历史会话                                                               */
  /* --------------------------------------------------------------------- */

  /** 载入某个历史会话的消息 */
  async function loadSession(id: string): Promise<boolean> {
    try {
      const { messages: stored } = await api.getSession(id)
      controller?.abort()
      messages.splice(0, messages.length)
      active = null
      streaming.value = false
      sessionId.value = id

      for (const m of stored) {
        messages.push(fromStored(m))
      }
      return true
    } catch (err) {
      console.warn('[useChat] 载入会话失败：', err)
      return false
    }
  }

  function fromStored(m: StoredMessage): ChatMessage {
    return {
      id: m.id,
      role: m.role,
      content: m.content,
      thinking: (m.thinking ?? []) as ThinkingStep[],
      tools: (m.tools ?? []) as ToolCall[],
      streaming: false,
      error: m.error ?? undefined,
      stats: m.stats ?? undefined,
      at: m.createdAt * 1000,
    }
  }

  /** 新建会话：清空 UI 并重置会话 ID（真正的会话记录在首次发送时创建） */
  function newSession() {
    reset()
  }

  return {
    messages,
    streaming,
    currentQuery,
    sessionId,
    send,
    stop,
    reset,
    newSession,
    loadSession,
  }
}
