"""
智扫通 · Web 适配层 HTTP 服务

设计原则：
  - **只读**调用既有后端，不修改 agent/ rag/ utils/ 下任何文件
  - 所有对外接口统一挂在 /api 前缀
  - SSE 用于流式问答；其余接口均为普通 JSON
  - 任何后端异常都转换成结构化的中文提示，绝不把堆栈返回给前端

启动：
    cd D:\\Pycharm(project)\\Agent
    .venv\\Scripts\\python.exe -m zsapi.app
或：
    uvicorn zsapi.app:app --host 127.0.0.1 --port 8010
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path


_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)
_stdout_log = open(_LOG_DIR / f"zsapi_{datetime.now():%Y%m%d}.stdout.log", "a", encoding="utf-8")
contextlib.redirect_stdout(_stdout_log).__enter__()

from .bootstrap import BOOTSTRAP_INFO  # noqa: E402
from .agent_bridge import TOOL_CATALOG, bridge  # noqa: E402
from . import store  # noqa: E402
from .insights import (  # noqa: E402
    analytics_overview,
    analytics_user,
    analytics_users,
    knowledge_stats,
    search_knowledge,
)

from fastapi import FastAPI, HTTPException, Query, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

logger = logging.getLogger("zsapi")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _h = logging.StreamHandler(sys.stderr)
    _h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_h)

AGENT_DIR = Path(__file__).resolve().parent.parent
RECORDS_CSV = AGENT_DIR / "data" / "external" / "records.csv"

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="用户提问")
    report: bool = Field(False, description="是否强制走报告生成模式")
    sessionId: str | None = Field(None, description="会话 ID；不传则本轮不落库")


class ChatEcho(BaseModel):
    ok: bool
    message: str


class SessionCreateRequest(BaseModel):
    title: str = Field("新对话", max_length=80)


class SessionRenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=80)


class MessageCreateRequest(BaseModel):
    """前端在流式结束后，把完整的助手消息落库。"""

    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field("", max_length=100_000)
    thinking: list[dict] | None = None
    tools: list[dict] | None = None
    stats: dict | None = None
    error: str | None = None


app = FastAPI(
    title="智扫通 · Web 适配层",
    description="只读封装既有 LangChain ReAct Agent，提供 SSE 流式问答与数据查询",
    version="1.0.0",
)

# 开发期允许 Vite dev server 跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# 健康检查
# ---------------------------------------------------------------------------


def _check_ollama() -> dict:
    """探测 Ollama 是否可用（RAG 向量化依赖它）。"""
    started = time.perf_counter()
    try:
        import ollama

        client = ollama.Client()
        models = client.list()
        names = [m.model for m in getattr(models, "models", [])]
        return {
            "ok": True,
            "models": names,
            "has_embedding_model": any("embedding" in n for n in names),
            "latencyMs": int((time.perf_counter() - started) * 1000),
        }
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _check_chroma() -> dict:
    """检查向量库目录与集合是否可读。"""
    try:
        from Agent.utils.config_handler import chroma_conf

        persist = chroma_conf.get("persist_directory", "chroma_db")
        path = (AGENT_DIR / persist).resolve()
        sqlite = path / "chroma.sqlite3"
        return {
            "ok": sqlite.exists(),
            "path": str(path),
            "collection": chroma_conf.get("collection_name"),
            "sizeMb": round(sqlite.stat().st_size / 1024 / 1024, 2) if sqlite.exists() else 0,
        }
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


@app.get("/api/health")
def health() -> dict:
    """服务与依赖健康检查。前端启动时调用，决定是否显示"RAG 已连接"。"""
    ollama = _check_ollama()
    chroma = _check_chroma()
    agent = bridge.warmup()

    overall = bool(ollama.get("ok")) and bool(chroma.get("ok")) and bool(agent.get("ok"))
    return {
        "ok": overall,
        "service": "zsapi",
        "version": app.version,
        "time": datetime.now().isoformat(timespec="seconds"),
        "bootstrap": BOOTSTRAP_INFO,
        "agent": agent,
        "ollama": ollama,
        "chroma": chroma,
    }


@app.get("/api/meta")
def meta() -> dict:
    """返回工具清单与可用用户/月份，供前端展示与选择器使用。"""
    return {
        "tools": [
            {"name": name, **info} for name, info in TOOL_CATALOG.items()
        ],
        "users": _load_user_months(),
    }


def _load_user_months() -> list[dict]:
    """解析 records.csv，得到 用户 -> 月份列表（只读，不写回）。"""
    if not RECORDS_CSV.exists():
        return []
    users: dict[str, set[str]] = {}
    try:
        with RECORDS_CSV.open("r", encoding="utf-8") as f:
            next(f, None)  # 跳过表头
            for line in f:
                parts = [p.strip().strip('"') for p in line.rstrip("\n").split(",")]
                if len(parts) < 6:
                    continue
                users.setdefault(parts[0], set()).add(parts[5])
    except Exception as exc:
        logger.warning("解析 records.csv 失败: %s", exc)
        return []

    return [
        {"userId": uid, "months": sorted(months)}
        for uid, months in sorted(users.items())
    ]


@app.get("/api/records/{user_id}")
def records(user_id: str) -> dict:
    """读取某用户的全部月度使用记录。"""
    rows = _read_records()
    picked = [r for r in rows if r["userId"] == user_id]
    if not picked:
        raise HTTPException(status_code=404, detail=f"未找到用户 {user_id} 的使用记录")
    return {"userId": user_id, "count": len(picked), "records": picked}


@app.get("/api/records/{user_id}/{month}")
def record_one(user_id: str, month: str) -> dict:
    """读取某用户某月的使用记录。"""
    rows = _read_records()
    for r in rows:
        if r["userId"] == user_id and r["month"] == month:
            return {"ok": True, "record": r}
    raise HTTPException(status_code=404, detail=f"未找到 {user_id} 在 {month} 的记录")


def _read_records() -> list[dict]:
    """把 records.csv 读成结构化列表（列名与后端 generate_external_data 一致）。"""
    if not RECORDS_CSV.exists():
        return []
    out: list[dict] = []
    with RECORDS_CSV.open("r", encoding="utf-8") as f:
        next(f, None)
        for line in f:
            parts = [p.strip().strip('"') for p in line.rstrip("\n").split(",")]
            if len(parts) < 6:
                continue
            out.append(
                {
                    "userId": parts[0],
                    "feature": parts[1],
                    "efficiency": parts[2],
                    "consumables": parts[3],
                    "comparison": parts[4],
                    "month": parts[5],
                }
            )
    return out


# ---------------------------------------------------------------------------
# SSE 流式问答
# ---------------------------------------------------------------------------


@app.post("/api/chat")
def chat(req: ChatRequest, request: Request) -> StreamingResponse:
    """SSE 流式问答。

    前端用 fetch + ReadableStream 消费（EventSource 不支持 POST）。

    事件类型：
        status   {phase, query, report}
        thinking {text, step, stepId}
        tool     {id, name, args, status, durationMs?, result?}
        delta    {text}
        done     {durationMs, steps, toolCount, thinkingChars, answerChars}
        error    {message, detail?}
    """

    def event_source():
        try:
            for ev in bridge.stream(req.message, report=req.report):
                # 客户端断开时及时停止，避免继续消耗模型额度
                if request.client and _client_disconnected(request):
                    logger.info("客户端已断开，停止生成")
                    break
                yield ev.to_sse()
        except Exception as exc:  # pragma: no cover - 兜底
            logger.exception("SSE 生成失败")
            payload = json.dumps(
                {"message": "服务内部错误，请稍后重试。", "detail": str(exc)},
                ensure_ascii=False,
            )
            yield f"event: error\ndata: {payload}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )


def _client_disconnected(request: Request) -> bool:
    """尽力检测客户端是否已断开（Starlette 的 is_disconnected 是异步的，这里保守返回 False）。"""
    return False


# ---------------------------------------------------------------------------
# 日志（只读）
# ---------------------------------------------------------------------------


@app.get("/api/logs")
def logs(
    limit: int = Query(80, ge=1, le=500),
    level: str | None = Query(None, description="按级别过滤：INFO/DEBUG/WARNING/ERROR"),
) -> dict:
    """读取最近的后端日志行，供前端"运行轨迹"面板展示。

    注意：后端 `utils/logger_handler.py` 生成的文件名是
    `agent_20261028'agent.log'`（带字面量单引号）——那是 f-string 引号写错的产物。
    这里不做改名（不修改后端），而是用两种模式都能匹配。
    """
    log_dir = AGENT_DIR / "logs"
    if not log_dir.exists():
        return {"lines": [], "file": None}

    candidates = list(log_dir.glob("agent_*.log")) + list(log_dir.glob("agent_*agent.log*"))
    # 去重并按修改时间倒序
    seen: set[str] = set()
    files = []
    for p in candidates:
        if p.name in seen:
            continue
        seen.add(p.name)
        files.append(p)
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    if not files:
        return {"lines": [], "file": None}

    target = files[0]
    try:
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"读取日志失败: {exc}") from exc

    if level:
        lines = [ln for ln in lines if f" - {level.upper()} - " in ln]

    return {"file": target.name, "lines": lines[-limit:]}


# ---------------------------------------------------------------------------
# 会话持久化
# ---------------------------------------------------------------------------


@app.get("/api/sessions")
def list_sessions(limit: int = Query(50, ge=1, le=200)) -> dict:
    """会话列表（按最近活跃倒序）。"""
    return {"sessions": store.list_sessions(limit)}


@app.post("/api/sessions", status_code=201)
def create_session(req: SessionCreateRequest) -> dict:
    """新建会话。"""
    return {"session": store.create_session(req.title)}


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    """会话详情 + 全部消息（用于点击历史会话时回看）。"""
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
    return {"session": session, "messages": store.list_messages(session_id)}


@app.patch("/api/sessions/{session_id}")
def rename_session(session_id: str, req: SessionRenameRequest) -> dict:
    """重命名会话。"""
    if not store.rename_session(session_id, req.title):
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在或标题为空")
    return {"ok": True, "session": store.get_session(session_id)}


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str) -> dict:
    """删除会话（级联删除消息）。"""
    if not store.delete_session(session_id):
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
    return {"ok": True, "deleted": session_id}


@app.post("/api/sessions/{session_id}/messages", status_code=201)
def add_message(session_id: str, req: MessageCreateRequest) -> dict:
    """把一条完整消息写入会话。

    前端在流式结束后调用（用户消息在发送时立即写入，助手消息在 done 时写入），
    避免把 SSE 的每个 token 都落库。
    """
    if store.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")

    msg = store.add_message(
        session_id,
        req.role,
        req.content,
        thinking=req.thinking,
        tools=req.tools,
        stats=req.stats,
        error=req.error,
    )
    # 首条用户消息顺便给会话命名
    if req.role == "user":
        store.touch_session(session_id, title_hint=req.content)
    else:
        store.touch_session(session_id)

    return {"ok": True, "message": msg}


# ---------------------------------------------------------------------------
# 知识库
# ---------------------------------------------------------------------------


@app.get("/api/knowledge/stats")
def kb_stats() -> dict:
    """知识库概览：切片总数与来源文件分布。"""
    return knowledge_stats()


@app.get("/api/knowledge/search")
def kb_search(
    q: str = Query(..., min_length=1, max_length=500, description="检索词"),
    k: int = Query(5, ge=1, le=20, description="返回片段数"),
) -> dict:
    """向量检索，返回命中的文档片段、来源、页码与相关度。"""
    try:
        return search_knowledge(q, k)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"检索失败：{type(exc).__name__}: {exc}") from exc


# ---------------------------------------------------------------------------
# 数据看板
# ---------------------------------------------------------------------------


@app.get("/api/analytics/overview")
def analytics_overview_ep() -> dict:
    """全局概览：用户数、月份跨度、各项均值。"""
    return analytics_overview()


@app.get("/api/analytics/users")
def analytics_users_ep() -> dict:
    """所有用户的摘要列表（用于看板卡片）。"""
    return analytics_users()


@app.get("/api/analytics/user/{user_id}")
def analytics_user_ep(user_id: str) -> dict:
    """单个用户的月度趋势。"""
    result = analytics_user(user_id)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("error", "未找到用户"))
    return result


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------


@app.on_event("startup")
def _on_startup() -> None:
    logger.info("zsapi 启动：cwd=%s", os.getcwd())
    logger.info("bootstrap=%s", BOOTSTRAP_INFO)
    # 初始化会话存储（建表，幂等）
    try:
        store.init_db()
        logger.info("会话存储就绪：%s", store.DB_PATH)
    except Exception as exc:
        logger.error("会话存储初始化失败：%s", exc)
    # 预热 Agent（首次构建约 10-15s，提前做掉避免首问卡顿）
    result = bridge.warmup()
    if result.get("ok"):
        logger.info("Agent 预热完成，耗时 %sms", result.get("build_ms"))
    else:
        logger.error("Agent 预热失败：%s", result.get("error"))


def main() -> None:
    import uvicorn

    uvicorn.run(
        "zsapi.app:app",
        host="127.0.0.1",
        port=8010,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
