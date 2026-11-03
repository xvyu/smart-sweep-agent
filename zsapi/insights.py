"""
知识库与数据看板服务

## 为什么需要

前端顶栏的「知识库」按钮、侧栏的「知识库检索 / 使用报告 / 环境适配」入口
原本都是死链接——点了没有任何反应，或者只是拼一句 prompt 丢给模型。

这里提供两类**真实数据接口**，让这些入口真正有内容：

1. **知识库检索**（`/api/knowledge/search`）
   直接调用既有 `VectorStoreService.get_retriever()` 做向量检索，
   把「命中了哪些文档片段、相似度、来源文件、页码」结构化返回，
   让用户能看见 RAG 到底检索到了什么，而不是只看到一段被总结过的文字。

2. **数据看板**（`/api/analytics/*`）
   解析 `data/external/records.csv`，把 10 个用户 × 12 个月的
   覆盖率 / 耗材寿命 / 横向对比 做成可计算的指标，供前端可视化。

本模块**只读**：不写 CSV、不建向量、不调用模型（检索除外，检索只用到 embedding）。
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

AGENT_DIR = Path(__file__).resolve().parent.parent
RECORDS_CSV = AGENT_DIR / "data" / "external" / "records.csv"


# ---------------------------------------------------------------------------
# 知识库检索
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_vector_store():
    """惰性构建向量库服务（首次调用约 1-2s，之后复用）。"""
    from Agent.rag.vector_store import VectorStoreService

    return VectorStoreService()


def search_knowledge(query: str, k: int = 5) -> dict[str, Any]:
    """向量检索，返回结构化片段（含来源、页码、相似度）。"""
    from Agent.utils.config_handler import chroma_conf

    vs = _get_vector_store()
    collection = vs.vector_store._collection
    total = collection.count()

    docs_with_scores = vs.vector_store.similarity_search_with_score(query, k=k)

    items: list[dict[str, Any]] = []
    for doc, score in docs_with_scores:
        meta = doc.metadata or {}
        source = str(meta.get("source", "")).replace("\\", "/")
        items.append(
            {
                "content": doc.page_content,
                "source": source,
                "sourceName": Path(source).name if source else "未知来源",
                "page": meta.get("page"),
                "pageLabel": meta.get("page_label"),
                "score": round(float(score), 4),
                # Chroma 的默认距离是 L2，越小越相似；这里给前端一个 0-1 的相关度
                "relevance": _distance_to_relevance(float(score)),
                "length": len(doc.page_content),
            }
        )

    return {
        "query": query,
        "k": k,
        "collection": chroma_conf.get("collection_name"),
        "totalChunks": total,
        "count": len(items),
        "items": items,
    }


def _distance_to_relevance(distance: float) -> float:
    """把 L2 距离映射到 0-1 的相关度（经验公式，仅用于展示排序）。"""
    if distance <= 0:
        return 1.0
    return round(max(0.0, min(1.0, 1.0 / (1.0 + distance))), 4)


def knowledge_stats() -> dict[str, Any]:
    """知识库概览：切片总数、来源文件分布。"""
    try:
        from Agent.utils.config_handler import chroma_conf

        vs = _get_vector_store()
        collection = vs.vector_store._collection
        total = collection.count()

        # 取一批 metadata 统计来源分布（最多 500 条，避免大库卡顿）
        got = collection.get(limit=min(total, 500), include=["metadatas"])
        sources: dict[str, int] = {}
        for meta in got.get("metadatas") or []:
            if not meta:
                continue
            src = str(meta.get("source", "")).replace("\\", "/")
            name = Path(src).name if src else "未知"
            sources[name] = sources.get(name, 0) + 1

        return {
            "ok": True,
            "collection": chroma_conf.get("collection_name"),
            "totalChunks": total,
            "sources": [
                {"name": name, "chunks": cnt}
                for name, cnt in sorted(sources.items(), key=lambda x: -x[1])
            ],
        }
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


# ---------------------------------------------------------------------------
# 使用数据看板
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _load_records() -> tuple[dict[str, Any], ...]:
    """解析 records.csv（只读一次，缓存）。"""
    import csv

    if not RECORDS_CSV.exists():
        return ()

    rows: list[dict[str, Any]] = []
    with RECORDS_CSV.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            rows.append(
                {
                    "userId": (raw.get("用户ID") or "").strip(),
                    "feature": (raw.get("特征") or "").strip(),
                    "efficiency": (raw.get("清洁效率") or "").strip(),
                    "consumables": (raw.get("耗材") or "").strip(),
                    "comparison": (raw.get("对比") or "").strip(),
                    "month": (raw.get("时间") or "").strip(),
                }
            )
    return tuple(rows)


def _parse_metrics(efficiency: str, consumables: str) -> dict[str, Any]:
    """从自由文本里抽取可量化的指标。

    字段内容是自然语言（如 "覆盖率:85%\\n日均清扫:45㎡\\n漏扫区域:沙发底部"），
    这里用正则做尽力而为的抽取，抽不到的返回 None（前端做降级展示）。
    """
    out: dict[str, Any] = {
        "coverage": None,      # 覆盖率 %
        "dailyArea": None,     # 日均清扫 ㎡
        "brushDays": None,     # 主刷剩余天数
        "filterPercent": None, # 滤网剩余 %
        "batteryDecay": None,  # 电池衰减 %
    }

    m = re.search(r"覆盖率[:：]\s*(\d+(?:\.\d+)?)\s*%", efficiency)
    if m:
        out["coverage"] = float(m.group(1))

    m = re.search(r"日均清扫[:：]\s*(\d+(?:\.\d+)?)\s*(?:㎡|平米)", efficiency)
    if m:
        out["dailyArea"] = float(m.group(1))

    m = re.search(r"剩余[:：]?\s*(\d+)\s*天", consumables)
    if m:
        out["brushDays"] = int(m.group(1))

    m = re.search(r"滤网[:：][^%\d]*(\d+)\s*%", consumables)
    if m:
        out["filterPercent"] = int(m.group(1))

    m = re.search(r"电池衰减[:：]\s*(\d+(?:\.\d+)?)\s*%", consumables)
    if m:
        out["batteryDecay"] = float(m.group(1))

    return out


def analytics_overview() -> dict[str, Any]:
    """全局概览：用户数、月份跨度、各指标均值、覆盖率分布。"""
    rows = _load_records()
    if not rows:
        return {"ok": False, "error": "records.csv 不存在或为空"}

    users = sorted({r["userId"] for r in rows})
    months = sorted({r["month"] for r in rows})

    coverages: list[float] = []
    filter_pcts: list[float] = []
    battery: list[float] = []
    brush_days: list[float] = []

    for r in rows:
        m = _parse_metrics(r["efficiency"], r["consumables"])
        if m["coverage"] is not None:
            coverages.append(m["coverage"])
        if m["filterPercent"] is not None:
            filter_pcts.append(float(m["filterPercent"]))
        if m["batteryDecay"] is not None:
            battery.append(m["batteryDecay"])
        if m["brushDays"] is not None:
            brush_days.append(float(m["brushDays"]))

    def avg(xs: list[float]) -> float | None:
        return round(sum(xs) / len(xs), 1) if xs else None

    return {
        "ok": True,
        "userCount": len(users),
        "monthCount": len(months),
        "recordCount": len(rows),
        "months": months,
        "users": users,
        "metrics": {
            "avgCoverage": avg(coverages),
            "avgFilterPercent": avg(filter_pcts),
            "avgBatteryDecay": avg(battery),
            "avgBrushDays": avg(brush_days),
            "sampleCoverage": len(coverages),
        },
    }


def analytics_user(user_id: str) -> dict[str, Any]:
    """单个用户的月度趋势与耗材状态。"""
    rows = [r for r in _load_records() if r["userId"] == user_id]
    if not rows:
        return {"ok": False, "error": f"未找到用户 {user_id}"}

    rows.sort(key=lambda r: r["month"])
    trend = []
    for r in rows:
        m = _parse_metrics(r["efficiency"], r["consumables"])
        trend.append({"month": r["month"], **m})

    latest = rows[-1]
    return {
        "ok": True,
        "userId": user_id,
        "feature": latest["feature"],
        "comparison": latest["comparison"],
        "latestMonth": latest["month"],
        "trend": trend,
        "latest": {
            "efficiency": latest["efficiency"],
            "consumables": latest["consumables"],
        },
    }


def analytics_users() -> dict[str, Any]:
    """所有用户的摘要（用于看板列表）。"""
    rows = _load_records()
    if not rows:
        return {"ok": False, "error": "records.csv 不存在或为空", "users": []}

    by_user: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_user.setdefault(r["userId"], []).append(r)

    out = []
    for uid, items in sorted(by_user.items()):
        items.sort(key=lambda r: r["month"])
        latest = items[-1]
        m = _parse_metrics(latest["efficiency"], latest["consumables"])
        out.append(
            {
                "userId": uid,
                "feature": latest["feature"],
                "latestMonth": latest["month"],
                "monthCount": len(items),
                "coverage": m["coverage"],
                "filterPercent": m["filterPercent"],
                "batteryDecay": m["batteryDecay"],
                "comparison": latest["comparison"],
            }
        )

    return {"ok": True, "users": out}
