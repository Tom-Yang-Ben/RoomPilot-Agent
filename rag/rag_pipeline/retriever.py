"""兩階段檢索：Chroma where 硬過濾 → bge-m3 向量 → bge-reranker-v2-m3 → 風格加權 → 去重。

排序公式（權重可調）：
    final = 0.60 × rerank(sigmoid 正規化)
          + 0.20 × style_compat[主導風格][物件 style_primary]
          + 0.10 × mood 命中率
          + 0.10 × item.confidence

風格走加權而非硬過濾：單一風格硬過濾後，疊上房型與類別可能只剩個位數；
用 taxonomy_v2 的 6×6 style_compat 矩陣加權（japanese↔scandinavian 0.9、
cream↔american 0.7），相容風格也撈得進來，但最搭的仍排最前。

用法：
    .venv-rag/bin/python rag_pipeline/retriever.py "日式侘寂感、預算兩萬內的客廳沙發"
"""

from __future__ import annotations

import json
import math
import os
import statistics
import sys
from functools import lru_cache
from pathlib import Path

# 模型已在本機快取；不設離線的話 sentence_transformers 每次載入都會連 HF Hub
# 檢查更新，未登入被限流時會乾等數分鐘。首次在新機器跑需 HF_HUB_OFFLINE=0 先下載。
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

PROJ = Path(__file__).resolve().parent.parent
V3 = PROJ / "rag_dataset" / "furniture_enriched_v3.json"
GROUPS = PROJ / "rag_pipeline" / "category_groups.json"
TAXONOMY = PROJ / "vlm_annotation" / "taxonomy_v2.json"
CHROMA_DIR = PROJ / "chroma_db"
COLLECTION = "furniture_v3"

EMBED_MODEL = "BAAI/bge-m3"
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"

VEC_TOP_K = 50          # 向量召回
RERANK_TOP_K = 20       # 送進 reranker 的候選數（cross-encoder 每 50 筆約 10 秒，是延遲主因）
RERANK_TOP_K_LIGHT = 12 # 配件品項（is_inferred / accent）再降額；仍 > FINAL_TOP_K，去重後夠取
FINAL_TOP_K = 8         # 最終回傳
BUDGET_SLACK = 1.3      # 預算分配的檢索寬容係數
W_RERANK, W_STYLE, W_MOOD, W_CONF = 0.60, 0.20, 0.10, 0.10


# ── 資源載入（單例，Gradio 重複查詢不重載） ──────────────────────────

@lru_cache(maxsize=1)
def load_data() -> dict:
    v3 = json.loads(V3.read_text(encoding="utf-8"))
    groups = json.loads(GROUPS.read_text(encoding="utf-8"))
    tax = json.loads(TAXONOMY.read_text(encoding="utf-8"))

    items = {i["id"]: i for i in v3["items"]}
    prices = {}
    for key, spec in groups["groups"].items():
        cats = set(spec["categories"])
        vals = sorted(i["price_twd"] for i in v3["items"] if i["category_final"] in cats)
        if vals:
            prices[key] = {
                "median": statistics.median(vals),
                "p33": vals[len(vals) // 3],
                "p67": vals[len(vals) * 2 // 3],
            }
    return {
        "items": items,
        "groups": groups["groups"],
        "room_sets": groups["room_default_sets"],
        "style_compat": tax["style_compat"],
        "styles_zh": {k: v["zh"] for k, v in tax["styles"].items()},
        "prices": prices,
    }


@lru_cache(maxsize=1)
def load_models() -> tuple:
    import torch
    from sentence_transformers import CrossEncoder, SentenceTransformer

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    try:
        embedder = SentenceTransformer(EMBED_MODEL, device=device)
        reranker = CrossEncoder(RERANK_MODEL, device=device, max_length=512)
    except Exception:  # MPS 偶有算子不支援，退回 CPU 仍可跑
        embedder = SentenceTransformer(EMBED_MODEL, device="cpu")
        reranker = CrossEncoder(RERANK_MODEL, device="cpu", max_length=512)
    embedder.max_seq_length = 512
    return embedder, reranker


@lru_cache(maxsize=1)
def load_collection():
    import chromadb

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_collection(COLLECTION)


def query_collection(**kwargs):
    """查詢 Chroma，索引在背後被重建時自動重連。

    embed_v3.py 重建索引的方式是 delete_collection + create_collection，
    新 collection 會拿到新的 UUID。長時間執行的 UI 因為 lru_cache 抓著舊 handle，
    重建後第一次查詢會噴 NotFoundError（Collection [uuid] does not exist）。
    這裡攔下來清快取重取一次——使用者只會感覺那一次查詢慢了一點。
    """
    from chromadb.errors import NotFoundError

    try:
        return load_collection().query(**kwargs)
    except NotFoundError:
        load_collection.cache_clear()
        load_data.cache_clear()  # 索引重建通常伴隨 v3 更新，價格分位數等一併重讀
        print("[retriever] 索引已被重建，重新連線後重試", flush=True)
        return load_collection().query(**kwargs)


# ── 條件推導 ─────────────────────────────────────────────────────

def allocate_budget(items: list, budget_total: int | None, data: dict) -> dict:
    """總預算依各類別群組的實際中位價按比例分配。

    平均分配會讓沙發（中位價 18,000）在 6 萬 / 5 件的情境下一件都撈不到，
    所以用中位價當權重；檢索階段再乘 BUDGET_SLACK 放寬，總價約束留到組合階段。
    """
    if not budget_total:
        return {}
    weights = {}
    for item in items:
        med = data["prices"].get(item.get("category_group") or "", {}).get("median", 5000)
        weights[item["item_id"]] = med * max(1, item.get("quantity") or 1)
    total = sum(weights.values()) or 1
    return {
        k: int(budget_total * w / total * BUDGET_SLACK)
        for k, w in weights.items()
    }


def resolve_price_bounds(item: dict, parsed: dict, allocated: dict, data: dict) -> tuple:
    """回傳 (price_min, price_max)。相對詞（便宜/高級）換算成該類別群組的分位數。"""
    if item.get("price_max"):
        return None, int(item["price_max"])
    if item["item_id"] in allocated:
        return None, allocated[item["item_id"]]

    level = parsed.get("price_level")
    stats = data["prices"].get(item.get("category_group") or "")
    if level and stats:
        if level == "budget":
            return None, int(stats["p33"])
        if level == "premium":
            return int(stats["p67"]), None
        return int(stats["p33"]), int(stats["p67"])
    if parsed.get("budget_total"):
        return None, int(parsed["budget_total"] * BUDGET_SLACK)
    return None, None


def build_where(item: dict, parsed: dict, allocated: dict, data: dict) -> dict | None:
    """Chroma metadata 硬過濾。風格與氛圍不進來 —— 它們只影響排序。

    注意：不要過濾 rag_indexable —— 它是 v3 的頂層欄位、不在 chroma_metadata 裡，
    寫進 where 會命中 0 筆；且 collection 本來就只收可索引的 9,349 筆。
    """
    clauses: list = []

    room = parsed.get("room_type")
    if room:
        clauses.append({f"room_{room}": {"$eq": True}})

    group = item.get("category_group")
    if group and group in data["groups"]:
        clauses.append({"category": {"$in": data["groups"][group]["categories"]}})

    lo, hi = resolve_price_bounds(item, parsed, allocated, data)
    if lo:
        clauses.append({"price_twd": {"$gte": lo}})
    if hi:
        clauses.append({"price_twd": {"$lte": hi}})

    if item.get("max_width_cm"):
        clauses.append({"width_cm": {"$lte": float(item["max_width_cm"])}})
    if item.get("max_height_cm"):
        clauses.append({"height_cm": {"$lte": float(item["max_height_cm"])}})
    if item.get("role"):
        clauses.append({"role": {"$eq": item["role"]}})
    if item.get("size_hint"):
        clauses.append({"size_class": {"$eq": item["size_hint"]}})

    if not clauses:
        return None  # 完全沒有硬條件（只給風格）→ 全庫語意檢索
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


# ── 排序 ────────────────────────────────────────────────────────

def style_score(meta: dict, styles: list, compat: dict) -> float:
    """使用者風格 vs 物件風格的相容度（取主/次風格的較佳者）。"""
    if not styles:
        return 0.5
    best = 0.0
    for want in styles:
        row = compat.get(want, {})
        for key, weight in (("style_primary", 1.0), ("style_secondary", 0.6)):
            got = meta.get(key)
            if got:
                best = max(best, row.get(got, 0.0) * weight)
    return best


def mood_score(meta: dict, moods: list) -> float:
    if not moods:
        return 0.5
    got = set((meta.get("moods_flat") or "").split("|")) - {""}
    return len(got & set(moods)) / len(moods)


def search_item(item: dict, parsed: dict, allocated: dict, data: dict,
                dominant_style: str | None, top_k: int = FINAL_TOP_K) -> dict:
    embedder, reranker = load_models()

    query = item["semantic_query"]
    where = build_where(item, parsed, allocated, data)
    qvec = embedder.encode([query], normalize_embeddings=True)[0].tolist()

    hits = query_collection(
        query_embeddings=[qvec],
        n_results=VEC_TOP_K,
        where=where,
        include=["metadatas", "documents", "distances"],
    )
    ids = hits["ids"][0]
    if not ids:
        return {"item": item, "where": where, "results": [], "relaxed": False}

    # 向量召回 50 筆當硬過濾緩衝，但只把前段送進 cross-encoder：
    # rerank 是延遲主因（每 50 筆約 10 秒），正解幾乎都落在向量 top 20 內；
    # 推論出的配件品項再降額，把算力留給使用者明講的主件
    n_rerank = (
        RERANK_TOP_K_LIGHT
        if (item.get("is_inferred") or item.get("role") == "accent")
        else RERANK_TOP_K
    )
    ids = ids[:n_rerank]
    metas, docs = hits["metadatas"][0][:n_rerank], hits["documents"][0][:n_rerank]
    scores = reranker.predict([(query, d) for d in docs])

    styles = item.get("styles") or ([dominant_style] if dominant_style else parsed.get("styles") or [])
    moods = parsed.get("moods") or []

    ranked = []
    for fid, meta, doc, raw in zip(ids, metas, docs, scores):
        # bge-reranker-v2-m3 經 CrossEncoder 已內建 sigmoid，輸出就是 0-1；
        # 只有當模型換成輸出 logit 的版本時才補一次 sigmoid，否則會壓平判別力
        raw = float(raw)
        rerank_norm = raw if 0.0 <= raw <= 1.0 else 1 / (1 + math.exp(-raw))
        s_style = style_score(meta, styles, data["style_compat"])
        s_mood = mood_score(meta, moods)
        final = (
            W_RERANK * rerank_norm
            + W_STYLE * s_style
            + W_MOOD * s_mood
            + W_CONF * float(meta.get("confidence") or 0)
        )
        ranked.append({
            "id": fid, "meta": meta, "document": doc,
            "score_final": round(final, 4),
            "score_rerank": round(rerank_norm, 4),
            "score_style": round(s_style, 3),
            "score_mood": round(s_mood, 3),
        })

    ranked.sort(key=lambda r: r["score_final"], reverse=True)
    return {"item": item, "where": where, "results": ranked[: top_k * 3], "relaxed": False}


def retrieve(parsed: dict, top_k: int = FINAL_TOP_K) -> dict:
    """多品項檢索 + set 層收斂（主導風格、跨品項去重）。"""
    data = load_data()
    items = parsed.get("items") or []
    allocated = allocate_budget(items, parsed.get("budget_total"), data)

    # anchor 先跑，用它的 top-1 決定主導風格（使用者已指定風格時直接沿用）
    order = sorted(items, key=lambda i: 0 if i.get("role") == "anchor" else 1)
    if not order:
        return {"dominant_style": None, "style_zh": "", "budget_total": None,
                "estimated_total": 0, "blocks": []}

    dominant = (parsed.get("styles") or [None])[0]
    first = search_item(order[0], parsed, allocated, data, dominant)
    per_item = {order[0]["item_id"]: first}

    if not dominant and first["results"]:
        # 主導風格是事後才定的 → 第一個品項要用它重排一次，否則整組風格會不一致
        dominant = first["results"][0]["meta"].get("style_primary")
        per_item[order[0]["item_id"]] = search_item(order[0], parsed, allocated, data, dominant)

    for item in order[1:]:
        per_item[item["item_id"]] = search_item(item, parsed, allocated, data, dominant)

    # 跨品項去重：同一 id 或同一 duplicate_group 不重複出現
    seen_ids, seen_groups = set(), set()
    output = []
    for item in order:
        res = per_item[item["item_id"]]
        picked = []
        for row in res["results"]:
            dup = row["meta"].get("duplicate_group") or ""
            if row["id"] in seen_ids or (dup and dup in seen_groups):
                continue
            seen_ids.add(row["id"])
            if dup:
                seen_groups.add(dup)
            picked.append(row)
            if len(picked) >= top_k:
                break
        output.append({
            "item_id": item["item_id"],
            "label_zh": item["label_zh"],
            "category_group": item.get("category_group"),
            "quantity": item.get("quantity") or 1,
            "is_inferred": item.get("is_inferred", False),
            "price_cap": allocated.get(item["item_id"]),
            "where": res["where"],
            "hits": picked,
        })

    est_total = sum(
        (b["hits"][0]["meta"]["price_twd"] * b["quantity"]) for b in output if b["hits"]
    )
    return {
        "dominant_style": dominant,
        "style_zh": data["styles_zh"].get(dominant or "", ""),
        "budget_total": parsed.get("budget_total"),
        "estimated_total": est_total,
        "blocks": output,
    }


def main() -> int:
    from query_parser import parse_query

    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    parsed = parse_query(" ".join(sys.argv[1:]))
    result = retrieve(parsed)

    print(f"主導風格：{result['dominant_style']}（{result['style_zh']}）")
    if result["budget_total"]:
        print(f"預算：{result['budget_total']:,} / 目前組合首選總價：{result['estimated_total']:,}")
    for block in result["blocks"]:
        tag = "（建議加入）" if block["is_inferred"] else ""
        cap = f"，分配預算 {block['price_cap']:,}" if block["price_cap"] else ""
        print(f"\n■ {block['label_zh']} ×{block['quantity']}{tag}{cap} — {len(block['hits'])} 筆")
        for row in block["hits"]:
            m = row["meta"]
            print(f"   {row['score_final']:.3f} | {m['name_zh'][:34]:36s} "
                  f"{m['category']:8s} {m['style_primary']:16s} {m['price_twd']:>6,} "
                  f"(rr {row['score_rerank']:.2f} st {row['score_style']:.2f} md {row['score_mood']:.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
