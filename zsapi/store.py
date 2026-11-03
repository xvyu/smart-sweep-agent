"""
会话存储（SQLite 持久化）

为什么需要它：
    前端原有的「新建对话 / 历史会话」全部只存在内存里，刷新即丢，
    点击历史会话也只切换高亮、看不到内容——属于纯装饰的假功能。
    本模块提供真正的持久化，让会话可创建、可回看、可删除、可重命名。

设计要点：
  1. 单文件 SQLite，落在 `data/app.db`，无需额外服务；
  2. 只存「用户可见的对话内容」，不存 Agent 内部状态（无需 LangGraph checkpoint）；
  3. 线程安全：FastAPI 默认线程池执行同步接口，这里每次操作独立连接 + WAL；
  4. 与后端既有代码完全解耦——不 import 任何 Agent.* 模块。
"""
from __future__ import annotations

import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

# Agent/zsapi/store.py -> Agent/
AGENT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = AGENT_DIR / "data" / "app.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    message_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,          -- 'user' | 'assistant'
    content     TEXT NOT NULL DEFAULT '',
    thinking    TEXT NOT NULL DEFAULT '[]',   -- JSON 数组
    tools       TEXT NOT NULL DEFAULT '[]',   -- JSON 数组
    stats       TEXT,                          -- JSON 或 NULL
    error       TEXT,
    created_at  REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_session
    ON messages(session_id, created_at);

CREATE INDEX IF NOT EXISTS idx_sessions_updated
    ON sessions(updated_at DESC);
"""


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    """每次操作独立连接（避免跨线程复用），并启用 WAL 与外键。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """建表（幂等）。应用启动时调用一次。"""
    with _connect() as conn:
        conn.executescript(_SCHEMA)


# ---------------------------------------------------------------------------
# 会话
# ---------------------------------------------------------------------------


def create_session(title: str = "新对话") -> dict[str, Any]:
    now = time.time()
    sid = f"s-{uuid.uuid4().hex[:12]}"
    with _connect() as conn:
        conn.execute(
            "INSERT INTO sessions (id, title, created_at, updated_at, message_count)"
            " VALUES (?, ?, ?, ?, 0)",
            (sid, title.strip() or "新对话", now, now),
        )
    return {"id": sid, "title": title.strip() or "新对话", "createdAt": now, "updatedAt": now, "messageCount": 0}


def list_sessions(limit: int = 50) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, title, created_at, updated_at, message_count"
            " FROM sessions ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "title": r["title"],
            "createdAt": r["created_at"],
            "updatedAt": r["updated_at"],
            "messageCount": r["message_count"],
        }
        for r in rows
    ]


def get_session(session_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, title, created_at, updated_at, message_count"
            " FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "title": row["title"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "messageCount": row["message_count"],
    }


def rename_session(session_id: str, title: str) -> bool:
    clean = title.strip()
    if not clean:
        return False
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
            (clean[:80], time.time(), session_id),
        )
        return cur.rowcount > 0


def delete_session(session_id: str) -> bool:
    with _connect() as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        return cur.rowcount > 0


def touch_session(session_id: str, title_hint: str | None = None) -> None:
    """更新会话的 updated_at；若标题仍是默认值则用首条提问命名。"""
    now = time.time()
    with _connect() as conn:
        row = conn.execute("SELECT title FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            return
        title = row["title"]
        if title_hint and title in ("新对话", ""):
            hint = title_hint.strip()
            title = hint[:24] + ("…" if len(hint) > 24 else "")
        conn.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
            (title, now, session_id),
        )


# ---------------------------------------------------------------------------
# 消息
# ---------------------------------------------------------------------------


def add_message(
    session_id: str,
    role: str,
    content: str,
    *,
    thinking: list[dict[str, Any]] | None = None,
    tools: list[dict[str, Any]] | None = None,
    stats: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    import json

    now = time.time()
    mid = f"m-{uuid.uuid4().hex[:12]}"
    thinking_json = json.dumps(thinking or [], ensure_ascii=False)
    tools_json = json.dumps(tools or [], ensure_ascii=False)
    stats_json = json.dumps(stats, ensure_ascii=False) if stats else None

    with _connect() as conn:
        conn.execute(
            "INSERT INTO messages (id, session_id, role, content, thinking, tools, stats, error, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (mid, session_id, role, content, thinking_json, tools_json, stats_json, error, now),
        )
        conn.execute(
            "UPDATE sessions SET message_count = message_count + 1, updated_at = ? WHERE id = ?",
            (now, session_id),
        )

    return {
        "id": mid,
        "sessionId": session_id,
        "role": role,
        "content": content,
        "thinking": thinking or [],
        "tools": tools or [],
        "stats": stats,
        "error": error,
        "createdAt": now,
    }


def list_messages(session_id: str) -> list[dict[str, Any]]:
    import json

    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()

    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": r["id"],
                "sessionId": r["session_id"],
                "role": r["role"],
                "content": r["content"],
                "thinking": _safe_json(r["thinking"], []),
                "tools": _safe_json(r["tools"], []),
                "stats": _safe_json(r["stats"], None),
                "error": r["error"],
                "createdAt": r["created_at"],
            }
        )
    return out


def _safe_json(raw: str | None, fallback: Any) -> Any:
    import json

    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return fallback
