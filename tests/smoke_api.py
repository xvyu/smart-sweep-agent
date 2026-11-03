#!/usr/bin/env python
"""
智扫通 · 端到端冒烟测试

验证目标：前端依赖的每一个后端能力是否真的实装并能工作。

测试项：
  1. /api/health      健康检查（Agent / Ollama / Chroma 三依赖）
  2. /api/meta        工具目录与用户月份
  3. /api/records     使用记录读取
  4. /api/logs        日志读取
  5. /api/chat        SSE 流式问答（核心）—— 校验事件序列、工具调用、答案非空
  6. 错误处理         空输入 / 超长输入应被拒绝

用法：
    cd D:\\Pycharm(project)\\Agent
    .venv\\Scripts\\python.exe tests\\smoke_api.py

退出码：0 = 全部通过，1 = 有失败项
"""
from __future__ import annotations

import json
import re
import sys
import time
from typing import Any

import httpx

BASE = "http://127.0.0.1:8010"
TIMEOUT = 180.0

passed: list[str] = []
failed: list[tuple[str, str]] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    if condition:
        passed.append(name)
        print(f"  [PASS] {name}")
        return True
    failed.append((name, detail))
    print(f"  [FAIL] {name}  {detail}")
    return False


def section(title: str) -> None:
    print(f"\n{'=' * 66}\n{title}\n{'=' * 66}")


# ---------------------------------------------------------------------------
# 1. 健康检查
# ---------------------------------------------------------------------------
def test_health(client: httpx.Client) -> dict[str, Any]:
    section("1. 健康检查 /api/health")
    t0 = time.perf_counter()
    r = client.get(f"{BASE}/api/health")
    elapsed = time.perf_counter() - t0

    check("HTTP 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code != 200:
        return {}

    h = r.json()
    check("整体状态 ok", h.get("ok") is True, f"ok={h.get('ok')}")
    check("Agent 就绪", h.get("agent", {}).get("ok") is True, str(h.get("agent")))
    check("Ollama 可用", h.get("ollama", {}).get("ok") is True, str(h.get("ollama")))
    check(
        "嵌入模型存在",
        h.get("ollama", {}).get("has_embedding_model") is True,
        f"models={h.get('ollama', {}).get('models')}",
    )
    check("Chroma 可读", h.get("chroma", {}).get("ok") is True, str(h.get("chroma")))
    check("DEEPSEEK_API_KEY 已注入", h.get("bootstrap", {}).get("deepseek_key_present") is True)

    print(f"  (耗时 {elapsed:.2f}s, Agent 构建 {h.get('agent', {}).get('build_ms')}ms)")
    return h


# ---------------------------------------------------------------------------
# 2. 元信息
# ---------------------------------------------------------------------------
def test_meta(client: httpx.Client) -> None:
    section("2. 元信息 /api/meta")
    r = client.get(f"{BASE}/api/meta")
    check("HTTP 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code != 200:
        return

    m = r.json()
    tools = m.get("tools", [])
    check("返回工具目录", len(tools) >= 7, f"got {len(tools)}")

    names = {t["name"] for t in tools}
    expected = {
        "rag_summarize",
        "get_weather",
        "get_user_location",
        "get_user_id",
        "get_current_month",
        "fetch_external_data",
        "fill_context_for_report",
    }
    missing = expected - names
    check("7 个工具齐全", not missing, f"missing={missing}")

    check("每个工具有中文标签", all(t.get("label") for t in tools))

    users = m.get("users", [])
    check("解析出用户列表", len(users) == 10, f"got {len(users)}")
    if users:
        check("每个用户 12 个月", all(len(u["months"]) == 12 for u in users))


# ---------------------------------------------------------------------------
# 3. 使用记录
# ---------------------------------------------------------------------------
def test_records(client: httpx.Client) -> None:
    section("3. 使用记录 /api/records")
    r = client.get(f"{BASE}/api/records/1001")
    check("HTTP 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        check("1001 有 12 条记录", d.get("count") == 12, f"got {d.get('count')}")
        rec = d.get("records", [{}])[0]
        for field in ("feature", "efficiency", "consumables", "comparison", "month"):
            check(f"记录含字段 {field}", bool(rec.get(field)), f"got {rec.get(field)!r}")

    r = client.get(f"{BASE}/api/records/1001/2025-06")
    check("单月查询 HTTP 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        check("单月记录月份正确", r.json()["record"]["month"] == "2025-06")

    r = client.get(f"{BASE}/api/records/9999")
    check("不存在的用户返回 404", r.status_code == 404, f"got {r.status_code}")


# ---------------------------------------------------------------------------
# 4. 日志
# ---------------------------------------------------------------------------
def test_logs(client: httpx.Client) -> None:
    section("4. 日志 /api/logs")
    r = client.get(f"{BASE}/api/logs?limit=20")
    check("HTTP 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        check("返回日志文件", bool(d.get("file")), f"file={d.get('file')}")
        check("返回日志行", len(d.get("lines", [])) > 0)


# ---------------------------------------------------------------------------
# 5. SSE 流式问答（核心）
# ---------------------------------------------------------------------------
def test_chat_sse(client: httpx.Client) -> None:
    section("5. SSE 流式问答 /api/chat  (核心)")

    t0 = time.perf_counter()
    events: list[tuple[str, dict]] = []

    with client.stream(
        "POST",
        f"{BASE}/api/chat",
        json={"message": "滤网多久清洗一次", "report": False},
        timeout=TIMEOUT,
    ) as resp:
        check("HTTP 200", resp.status_code == 200, f"got {resp.status_code}")
        check(
            "Content-Type 为 text/event-stream",
            "text/event-stream" in resp.headers.get("content-type", ""),
            resp.headers.get("content-type", ""),
        )
        if resp.status_code != 200:
            return

        buffer = ""
        for chunk in resp.iter_text():
            buffer += chunk
            while "\n\n" in buffer:
                frame, buffer = buffer.split("\n\n", 1)
                parsed = _parse_sse_frame(frame)
                if parsed:
                    events.append(parsed)

    elapsed = time.perf_counter() - t0

    names = [e for e, _ in events]
    counts = {n: names.count(n) for n in set(names)}
    print(f"  事件统计: {counts}  (总耗时 {elapsed:.1f}s)")

    check("收到 status 事件", counts.get("status", 0) == 1)
    check("收到 thinking 事件", counts.get("thinking", 0) > 0, f"got {counts.get('thinking')}")
    check("收到 tool 事件", counts.get("tool", 0) >= 2, f"got {counts.get('tool')}")
    check("收到 delta 事件", counts.get("delta", 0) > 0, f"got {counts.get('delta')}")
    check("收到 done 事件", counts.get("done", 0) == 1)
    check("没有 error 事件", counts.get("error", 0) == 0, str([d for e, d in events if e == "error"]))

    # --- 工具调用完整性 ---
    tool_events = [d for e, d in events if e == "tool"]
    if tool_events:
        names_seen = {d.get("name") for d in tool_events}
        check("工具名非 unknown", "unknown" not in names_seen, f"names={names_seen}")

        # 去重：同一 (step,index) 只应出现一次 running
        running = [d for d in tool_events if d.get("status") == "running"]
        success = [d for d in tool_events if d.get("status") == "success"]
        check("running 与 success 数量一致", len(running) == len(success),
              f"running={len(running)} success={len(success)}")
        check("工具调用成功", len(success) >= 1, f"got {len(success)}")
        check("工具返回耗时", all(d.get("durationMs") is not None for d in success))
        check("工具返回结果", all(d.get("result") for d in success))
        if success:
            check("工具参数已解析", bool(success[0].get("args")), str(success[0].get("args")))

    # --- 思考与答案分离 ---
    thinking_text = "".join(d.get("text", "") for e, d in events if e == "thinking")
    answer = "".join(d.get("text", "") for e, d in events if e == "delta")

    check("思考内容非空", len(thinking_text) > 20, f"len={len(thinking_text)}")
    check("答案内容非空", len(answer) > 50, f"len={len(answer)}")
    check("思考与答案不重复", answer not in thinking_text, "answer 出现在 thinking 中")

    # 答案应基于检索到的资料，包含专业关键词
    keywords = ["滤网", "清洗", "更换"]
    hit = [k for k in keywords if k in answer]
    check("答案包含专业关键词", len(hit) >= 2, f"hits={hit}")

    # 不应再出现"未提供有效信息"（知识库为空的症状）
    check("未出现知识库空转症状", "未提供" not in answer and "无法据此" not in answer,
          answer[:120])

    done = next((d for e, d in events if e == "done"), {})
    check("done 含统计信息", all(k in done for k in ("durationMs", "steps", "toolCount")))
    check("统计工具数一致", done.get("toolCount") == len([d for d in tool_events if d.get("status") == "running"]),
          f"done={done.get('toolCount')}")

    print(f"  答案预览: {answer[:100]}...")


def _parse_sse_frame(frame: str) -> tuple[str, dict] | None:
    name = None
    data_lines = []
    for line in frame.splitlines():
        if line.startswith("event:"):
            name = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].strip())
    if not name:
        return None
    raw = "\n".join(data_lines)
    try:
        return name, json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return name, {"_raw": raw}


# ---------------------------------------------------------------------------
# 6. 参数校验
# ---------------------------------------------------------------------------
def test_validation(client: httpx.Client) -> None:
    section("6. 参数校验")
    r = client.post(f"{BASE}/api/chat", json={"message": "", "report": False})
    check("空输入被拒绝 (422)", r.status_code == 422, f"got {r.status_code}")

    r = client.post(f"{BASE}/api/chat", json={"message": "x" * 3000, "report": False})
    check("超长输入被拒绝 (422)", r.status_code == 422, f"got {r.status_code}")

    r = client.post(f"{BASE}/api/chat", json={"report": False})
    check("缺少 message 被拒绝 (422)", r.status_code == 422, f"got {r.status_code}")


# ---------------------------------------------------------------------------
# 7. 会话持久化
# ---------------------------------------------------------------------------
def test_sessions(client: httpx.Client) -> None:
    section("7. 会话持久化 /api/sessions")

    # 创建
    r = client.post(f"{BASE}/api/sessions", json={"title": "冒烟测试会话"})
    check("创建会话 201", r.status_code == 201, f"got {r.status_code}")
    if r.status_code != 201:
        return
    sid = r.json()["session"]["id"]
    check("返回会话 ID", bool(sid))

    try:
        # 列表
        r = client.get(f"{BASE}/api/sessions")
        check("会话列表 200", r.status_code == 200, f"got {r.status_code}")
        listed = r.json().get("sessions", [])
        check("新建的会话出现在列表中", any(s["id"] == sid for s in listed))

        # 写入用户消息
        r = client.post(
            f"{BASE}/api/sessions/{sid}/messages",
            json={"role": "user", "content": "滤网多久清洗一次"},
        )
        check("写入用户消息 201", r.status_code == 201, f"got {r.status_code}")

        # 写入助手消息（含思考/工具/统计）
        r = client.post(
            f"{BASE}/api/sessions/{sid}/messages",
            json={
                "role": "assistant",
                "content": "建议每 1-2 周清洗一次",
                "thinking": [{"text": "需要检索", "step": 1}],
                "tools": [{"name": "rag_summarize", "status": "success", "durationMs": 1800}],
                "stats": {"durationMs": 6000, "steps": 2, "toolCount": 1},
            },
        )
        check("写入助手消息 201", r.status_code == 201, f"got {r.status_code}")

        # 读取详情
        r = client.get(f"{BASE}/api/sessions/{sid}")
        check("会话详情 200", r.status_code == 200, f"got {r.status_code}")
        detail = r.json()
        msgs = detail.get("messages", [])
        check("详情含 2 条消息", len(msgs) == 2, f"got {len(msgs)}")
        if msgs:
            check("用户消息内容正确", msgs[0]["content"] == "滤网多久清洗一次")
            check("助手消息思考已保存", len(msgs[1].get("thinking", [])) == 1)
            check("助手消息工具已保存", len(msgs[1].get("tools", [])) == 1)
            check("助手消息统计已保存", bool(msgs[1].get("stats")))
        check(
            "会话保留显式指定的标题",
            detail["session"]["title"] == "冒烟测试会话",
            detail["session"]["title"],
        )

        # 另一条路径：标题为默认「新对话」时，应自动用首条提问命名
        r = client.post(f"{BASE}/api/sessions", json={"title": "新对话"})
        sid2 = r.json()["session"]["id"]
        try:
            client.post(
                f"{BASE}/api/sessions/{sid2}/messages",
                json={"role": "user", "content": "滚刷缠毛怎么处理"},
            )
            d2 = client.get(f"{BASE}/api/sessions/{sid2}").json()
            check(
                "默认标题被首条提问替换",
                d2["session"]["title"] == "滚刷缠毛怎么处理",
                d2["session"]["title"],
            )
        finally:
            client.delete(f"{BASE}/api/sessions/{sid2}")

        # 重命名
        r = client.patch(f"{BASE}/api/sessions/{sid}", json={"title": "重命名测试"})
        check("重命名 200", r.status_code == 200, f"got {r.status_code}")
        if r.status_code == 200:
            check("标题已更新", r.json()["session"]["title"] == "重命名测试")

        # 空标题应被拒绝
        r = client.patch(f"{BASE}/api/sessions/{sid}", json={"title": ""})
        check("空标题被拒绝 422", r.status_code == 422, f"got {r.status_code}")
    finally:
        # 删除
        r = client.delete(f"{BASE}/api/sessions/{sid}")
        check("删除会话 200", r.status_code == 200, f"got {r.status_code}")

        r = client.get(f"{BASE}/api/sessions/{sid}")
        check("删除后查询 404", r.status_code == 404, f"got {r.status_code}")

    # 不存在会话的操作
    r = client.get(f"{BASE}/api/sessions/s-not-exist")
    check("不存在的会话 404", r.status_code == 404, f"got {r.status_code}")


# ---------------------------------------------------------------------------
# 8. 知识库
# ---------------------------------------------------------------------------
def test_knowledge(client: httpx.Client) -> None:
    section("8. 知识库 /api/knowledge")

    r = client.get(f"{BASE}/api/knowledge/stats")
    check("统计 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        check("知识库已加载", d.get("ok") is True, str(d.get("error")))
        check("切片数 > 0", (d.get("totalChunks") or 0) > 0, f"got {d.get('totalChunks')}")
        sources = d.get("sources", [])
        check("有来源文件", len(sources) > 0, f"got {len(sources)}")
        if sources:
            check("来源含切片计数", all("chunks" in s and s["chunks"] > 0 for s in sources))

    r = client.get(f"{BASE}/api/knowledge/search", params={"q": "滤网清洗", "k": 3})
    check("检索 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        items = d.get("items", [])
        check("返回检索结果", len(items) > 0, f"got {len(items)}")
        check("结果数不超过 k", len(items) <= 3, f"got {len(items)}")
        if items:
            it = items[0]
            check("片段含内容", bool(it.get("content")))
            check("片段含来源名", bool(it.get("sourceName")))
            check("片段含相关度", isinstance(it.get("relevance"), (int, float)))
            check("相关度在 0-1 之间", 0 <= it["relevance"] <= 1, f"got {it['relevance']}")

    # 空查询应被拒绝
    r = client.get(f"{BASE}/api/knowledge/search", params={"q": ""})
    check("空查询被拒绝 422", r.status_code == 422, f"got {r.status_code}")


# ---------------------------------------------------------------------------
# 9. 数据看板
# ---------------------------------------------------------------------------
def test_analytics(client: httpx.Client) -> None:
    section("9. 数据看板 /api/analytics")

    r = client.get(f"{BASE}/api/analytics/overview")
    check("概览 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        check("概览 ok", d.get("ok") is True)
        check("用户数 = 10", d.get("userCount") == 10, f"got {d.get('userCount')}")
        check("月份数 = 12", d.get("monthCount") == 12, f"got {d.get('monthCount')}")
        check("记录数 = 120", d.get("recordCount") == 120, f"got {d.get('recordCount')}")
        m = d.get("metrics", {})
        check("平均覆盖率已计算", m.get("avgCoverage") is not None, str(m))
        check("覆盖率在合理范围", 0 < (m.get("avgCoverage") or 0) <= 100, f"got {m.get('avgCoverage')}")

    r = client.get(f"{BASE}/api/analytics/users")
    check("用户列表 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        users = r.json().get("users", [])
        check("用户列表 10 人", len(users) == 10, f"got {len(users)}")
        if users:
            u = users[0]
            check("用户含户型特征", bool(u.get("feature")))
            check("用户含 12 个月", u.get("monthCount") == 12, f"got {u.get('monthCount')}")

    r = client.get(f"{BASE}/api/analytics/user/1001")
    check("用户详情 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        check("详情含 12 个月趋势", len(d.get("trend", [])) == 12, f"got {len(d.get('trend', []))}")
        check("详情含最新效率", bool(d.get("latest", {}).get("efficiency")))
        trend = d.get("trend", [])
        if trend:
            check("趋势含覆盖率", trend[0].get("coverage") is not None)

    r = client.get(f"{BASE}/api/analytics/user/9999")
    check("不存在的用户 404", r.status_code == 404, f"got {r.status_code}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> int:
    print("智扫通 · 端到端冒烟测试")
    print(f"目标: {BASE}")

    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            try:
                client.get(f"{BASE}/api/health", timeout=5)
            except httpx.ConnectError:
                print(f"\n[ERROR] 无法连接 {BASE}")
                print("请先启动后端：.venv\\Scripts\\python.exe -m uvicorn zsapi.app:app --port 8010")
                return 1

            test_health(client)
            test_meta(client)
            test_records(client)
            test_logs(client)
            test_chat_sse(client)
            test_validation(client)
            test_sessions(client)
            test_knowledge(client)
            test_analytics(client)
    except Exception as exc:  # noqa: BLE001
        print(f"\n[ERROR] 测试异常: {type(exc).__name__}: {exc}")
        import traceback

        traceback.print_exc()
        return 1

    section("测试结果")
    print(f"  通过: {len(passed)}")
    print(f"  失败: {len(failed)}")
    if failed:
        print("\n  失败项：")
        for name, detail in failed:
            print(f"    - {name}  {detail}")
        return 1

    print("\n  全部通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
