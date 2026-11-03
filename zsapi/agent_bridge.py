"""
Agent 桥接层：把 LangChain ReAct Agent 的执行过程翻译成结构化事件。

## 为什么不能直接用 ReactAgent.execute_stream()

后端 `agent/react_agent.py` 的 `execute_stream()` 是给命令行看的：

    for chunk in self.agent.stream(input_dict, stream_mode="values", context={"report": False}):
        latest_message = chunk["messages"][-1]
        if latest_message.content:
            yield latest_message.content.strip() + '\\n'

问题有三：
  1. `stream_mode="values"` 只给「最新一条消息的全文」，没有 token 级增量 →
     前端只能整段整段地跳，做不到打字机效果。
  2. 只取 `content`，**工具名、参数、耗时、结果全部被丢弃** →
     而"思考过程可见"正是本产品的核心卖点。
  3. 每轮把完整快照重复 yield 一遍，内容会重复叠加。

因此这里改为直接用 `agent.stream(stream_mode="messages")` 拿到
`(message_chunk, metadata)` 二元组，从中重建思考 / 工具 / 答案。

本模块**不修改后端任何文件**，仅消费其公开对象（ReactAgent）。

## 三个必须处理的真实坑（实测发现）

### 坑 1：工具调用的流式增量只有首包带 id

    {'name':'rag_summarize','args':'','id':'call_00_xxx','index':0}   ← 首包
    {'name':None,        'args':'{','id':None,        'index':0}     ← 后续
    {'name':None,        'args':'"',  'id':None,      'index':0}

若用 `id` 做键，后续每个增量都会被当成新工具，前端会看到一堆 `unknown` 卡片。
**对策**：以 `(langgraph_step, index)` 作为稳定键，首包记录真实 id 用于和
`ToolMessage.tool_call_id` 对账。

### 坑 2：后端 `rag_server.get_prompt()` 里有 print()

`rag/rag_server.py` 的 `get_prompt()` 会把整段 RAG 提示词 print 到 stdout。
它不会进入 SSE 事件流（我们只 yield 结构化事件），但会污染服务日志。
**对策**：在服务入口把 stdout 重定向到日志文件（见 app.py），事件流不受影响。

### 坑 3：思考与答案的区分

流式无法预知"本轮之后还会不会调工具"。可靠信号是**工具是否已全部结束**：
工具调用全部 finished 之后，模型输出的文本才是最终答案；此前都是思考。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Iterator

from langchain_core.messages import AIMessageChunk, ToolMessage

# 必须在导入 Agent.* 之前完成自举（sys.path / cwd / 环境变量）
from . import bootstrap  # noqa: F401  (import 副作用即自举)


# ---------------------------------------------------------------------------
# 事件模型
# ---------------------------------------------------------------------------


@dataclass
class StreamEvent:
    """一条 SSE 事件。`event` 是前端 EventSource 监听的事件名。"""

    event: str
    data: dict[str, Any]

    def to_sse(self) -> str:
        payload = json.dumps(self.data, ensure_ascii=False)
        return f"event: {self.event}\ndata: {payload}\n\n"


@dataclass
class _ToolState:
    """一次工具调用的生命周期状态。"""

    key: str
    call_id: str
    name: str
    args_text: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    started_at: float = field(default_factory=time.perf_counter)
    finished_at: float | None = None
    result: str = ""
    status: str = "running"  # running | success | error

    @property
    def duration_ms(self) -> int:
        end = self.finished_at or time.perf_counter()
        return int((end - self.started_at) * 1000)


# ---------------------------------------------------------------------------
# 工具元信息（用于前端展示中文标签与图标）
# ---------------------------------------------------------------------------

TOOL_CATALOG: dict[str, dict[str, str]] = {
    "rag_summarize": {
        "label": "知识库检索",
        "desc": "从向量库检索扫地/扫拖机器人的专业资料",
        "icon": "library",
        "kind": "rag",
    },
    "get_weather": {
        "label": "天气查询",
        "desc": "获取指定城市的天气、湿度、降雨概率",
        "icon": "cloud-sun",
        "kind": "env",
    },
    "get_user_location": {
        "label": "定位城市",
        "desc": "获取当前用户所在城市",
        "icon": "map-pin",
        "kind": "env",
    },
    "get_user_id": {
        "label": "读取用户 ID",
        "desc": "获取当前用户唯一标识",
        "icon": "user-round",
        "kind": "profile",
    },
    "get_current_month": {
        "label": "读取月份",
        "desc": "获取系统当前月份（YYYY-MM）",
        "icon": "calendar",
        "kind": "profile",
    },
    "fetch_external_data": {
        "label": "读取使用记录",
        "desc": "拉取指定用户指定月份的使用数据",
        "icon": "database",
        "kind": "data",
    },
    "fill_context_for_report": {
        "label": "切换报告模式",
        "desc": "注入上下文，切换为报告生成提示词",
        "icon": "file-bar-chart",
        "kind": "report",
    },
}


# ---------------------------------------------------------------------------
# Agent 桥接
# ---------------------------------------------------------------------------


class AgentBridge:
    """封装 ReAct Agent 的构建与流式执行（懒加载 + 单例复用）。"""

    def __init__(self) -> None:
        self._agent = None
        self._build_error: str | None = None
        self._build_ms: int | None = None

    # -- 构建 ---------------------------------------------------------------

    def _ensure_agent(self):
        if self._agent is not None:
            return self._agent
        if self._build_error is not None:
            raise RuntimeError(self._build_error)

        started = time.perf_counter()
        try:
            # 复用后端既有实现，零改动
            from Agent.agent.react_agent import ReactAgent

            self._agent = ReactAgent().agent
            self._build_ms = int((time.perf_counter() - started) * 1000)
        except Exception as exc:  # pragma: no cover - 依赖外部环境
            self._build_error = f"{type(exc).__name__}: {exc}"
            raise
        return self._agent

    def warmup(self) -> dict[str, Any]:
        """预热并返回诊断信息。失败不抛异常，交由 /health 汇报。"""
        started = time.perf_counter()
        try:
            self._ensure_agent()
            return {
                "ok": True,
                "build_ms": self._build_ms,
                "warmup_ms": int((time.perf_counter() - started) * 1000),
            }
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    # -- 流式执行 -----------------------------------------------------------

    def stream(
        self,
        query: str,
        *,
        report: bool = False,
    ) -> Iterator[StreamEvent]:
        """执行一次问答，逐条产出 SSE 事件。

        事件序列（正常路径）：
            status(started) → thinking* → tool(running) → tool(done)* →
            delta* → done
        """
        started_at = time.perf_counter()

        try:
            agent = self._ensure_agent()
        except Exception as exc:
            yield StreamEvent(
                "error",
                {
                    "message": "智能体初始化失败，请检查 DEEPSEEK_API_KEY 与模型服务是否可用。",
                    "detail": f"{type(exc).__name__}: {exc}",
                },
            )
            return

        yield StreamEvent(
            "status",
            {"phase": "started", "query": query, "report": report},
        )

        messages = [{"role": "user", "content": query}]
        context = {"report": report}

        # 稳定键 (step, index) -> _ToolState；并维护 tool_call_id -> 稳定键 的对账表
        tools: dict[str, _ToolState] = {}
        by_call_id: dict[str, str] = {}
        thinking_chars = 0
        answer_chars = 0
        step_count = 0
        last_step: str | None = None

        try:
            for chunk, meta in agent.stream(
                {"messages": messages},
                stream_mode="messages",
                context=context,
            ):
                step = str(meta.get("langgraph_step", "")) if isinstance(meta, dict) else ""

                # ---------------- 工具执行结果 ----------------
                if isinstance(chunk, ToolMessage):
                    key = by_call_id.get(chunk.tool_call_id or "")
                    state = tools.get(key) if key else None
                    if state is None:
                        # 兜底：找不到对应发起记录时补一条完整卡片
                        state = _ToolState(
                            key=chunk.tool_call_id or "tool",
                            call_id=chunk.tool_call_id or "tool",
                            name=getattr(chunk, "name", None) or "unknown",
                        )
                        tools[state.key] = state
                    state.finished_at = time.perf_counter()
                    state.result = _stringify(chunk.content)
                    state.status = (
                        "error" if getattr(chunk, "status", "") == "error" else "success"
                    )
                    yield StreamEvent(
                        "tool",
                        {
                            "id": state.call_id,
                            "name": state.name,
                            "args": state.args,
                            "status": state.status,
                            "durationMs": state.duration_ms,
                            "result": _truncate(state.result, 2000),
                        },
                    )
                    continue

                if not isinstance(chunk, AIMessageChunk):
                    continue

                # ---------------- 工具调用发起（流式增量） ----------------
                if chunk.tool_call_chunks:
                    for tc in chunk.tool_call_chunks:
                        if not isinstance(tc, dict):
                            continue
                        idx = tc.get("index", 0)
                        call_id = tc.get("id")
                        name = tc.get("name")
                        args_frag = tc.get("args")

                        # 关键：用 (step, index) 做稳定键，而不是可能为 None 的 id
                        key = f"{step}:{idx}"
                        state = tools.get(key)

                        if state is None:
                            state = _ToolState(
                                key=key,
                                call_id=call_id or key,
                                name=name or "unknown",
                            )
                            tools[key] = state
                            if call_id:
                                by_call_id[call_id] = key
                            yield StreamEvent(
                                "tool",
                                {
                                    "id": state.call_id,
                                    "name": state.name,
                                    "args": {},
                                    "status": "running",
                                },
                            )
                        else:
                            if call_id and call_id not in by_call_id:
                                state.call_id = call_id
                                by_call_id[call_id] = key
                            if name:
                                state.name = name

                        if args_frag:
                            state.args_text += args_frag
                            state.args = _safe_json(state.args_text)
                    continue

                # ---------------- 文本增量 ----------------
                text = _content_to_text(chunk.content)
                if not text:
                    continue

                if step != last_step:
                    last_step = step
                    step_count += 1

                # 工具全部结束后，模型文本才是「答案」
                tools_done = bool(tools) and all(t.status != "running" for t in tools.values())

                if tools_done:
                    answer_chars += len(text)
                    yield StreamEvent("delta", {"text": text})
                else:
                    thinking_chars += len(text)
                    yield StreamEvent(
                        "thinking",
                        {"text": text, "step": step_count, "stepId": step},
                    )

        except Exception as exc:
            yield StreamEvent(
                "error",
                {
                    "message": "生成过程中断，请重试。",
                    "detail": f"{type(exc).__name__}: {exc}",
                },
            )
            return

        yield StreamEvent(
            "done",
            {
                "durationMs": int((time.perf_counter() - started_at) * 1000),
                "steps": step_count,
                "toolCount": len(tools),
                "thinkingChars": thinking_chars,
                "answerChars": answer_chars,
            },
        )


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _content_to_text(content: Any) -> str:
    """把 LangChain 的 content（str 或 content-block 列表）压平成纯文本。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") in ("text", "text_delta") and isinstance(block.get("text"), str):
                    parts.append(block["text"])
        return "".join(parts)
    return ""


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


def _safe_json(raw: str) -> dict[str, Any]:
    """流式拼装的 JSON 参数可能不完整，解析失败就返回空字典。"""
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except json.JSONDecodeError:
        return {}


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + f"…（已截断，共 {len(text)} 字）"


# 全局单例
bridge = AgentBridge()
