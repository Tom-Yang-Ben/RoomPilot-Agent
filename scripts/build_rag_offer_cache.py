#!/usr/bin/env python
"""離線產生「RAG 選件快取」：每個（家具族系 × 風格）先算好 top-N 推薦。

為什麼離線：2026-08-01 實測，線上 RAG 單次查詢 CPU 約 40 秒、RTX 2060 6GB
開 CUDA 反而 73~106 秒（VRAM 塞爆）。而資料庫已定版不再增加，「族系 × 風格」
的組合有限且固定，先算好存檔，線上查表毫秒級——同時也繞過線上 LLM parse
的 5~7 秒與 role 猜測不穩定的問題（本腳本不用 LLM、不用 role 過濾）。

作法：BAAI/bge-m3 把「{風格}風格的{家具}」嵌入成查詢向量，直接對 PostgreSQL
的 pgvector 家具向量做餘弦排序（只讀，不改任何 Django／Kai 的表），每組取
top-N 個 item_id 寫進 `.runtime/rag_offer_cache.json`。

用法（需 PostgreSQL 在跑、bge-m3 已快取）：

    .venv/bin/python scripts/build_rag_offer_cache.py
    .venv/bin/python scripts/build_rag_offer_cache.py --top 12 --out 自訂路徑.json

之後由 `/api/agent/furniture/select` 讀取（見 main.py `_rag_cache_offers`）。
資料換版時重跑本腳本即可。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.agent.knowledge import FAMILY_ZH, family_of  # noqa: E402

# 風格中文對照：只拿來組查詢句，讓向量吃得到語意；缺的風格用代碼原文。
STYLE_ZH = {
    "scandinavian": "北歐",
    "japanese": "日式無印",
    "modern_minimal": "現代簡約",
    "cream": "奶油",
    "industrial": "工業",
    "american": "美式",
}

EMBEDDING_MODEL = "BAAI/bge-m3"


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=12)
    parser.add_argument("--out", default=str(REPO_ROOT / ".runtime" / "rag_offer_cache.json"))
    args = parser.parse_args()

    env = load_env(REPO_ROOT / ".env")
    import psycopg2  # noqa: PLC0415 — 沿用專案既有驅動

    conn = psycopg2.connect(
        host=env.get("DB_HOST", "localhost"),
        port=int(env.get("DB_PORT", "5432")),
        dbname=env.get("DB_NAME", "roompilot_db"),
        user=env.get("DB_USER", "postgres"),
        password=env.get("DB_PASSWORD", ""),
    )
    cur = conn.cursor()

    # 族系 → 該族系底下所有 catalog 分類碼（例如 sofa → sofa/fabric-sofa/…）。
    cur.execute(
        "SELECT DISTINCT category_code FROM roompilot.furniture_catalog_current "
        "WHERE kind='furniture' AND category_code IS NOT NULL"
    )
    families: dict[str, list[str]] = {}
    for (code,) in cur.fetchall():
        families.setdefault(family_of(code), []).append(code)

    styles = list(STYLE_ZH.keys())
    print(f"族系 {len(families)} 個 × 風格 {len(styles)}+1 組，top {args.top}")

    print("載入 embedding 模型（CPU）...", flush=True)
    from sentence_transformers import SentenceTransformer  # noqa: PLC0415

    started = time.time()
    model = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
    print(f"模型就緒 {time.time() - started:.1f}s", flush=True)

    # 一次算完全部查詢向量：族系 ×（各風格＋不指定風格 "*"）。
    keys: list[tuple[str, str]] = []
    texts: list[str] = []
    for family in sorted(families):
        zh = FAMILY_ZH.get(family, family)
        for style in styles:
            keys.append((family, style))
            texts.append(f"{STYLE_ZH[style]}風格的{zh}，適合台灣住宅")
        keys.append((family, "*"))
        texts.append(f"適合台灣住宅的{zh}")
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)

    sql = (
        "SELECT c.item_id "
        "FROM roompilot.furniture_catalog_current c "
        "JOIN roompilot.furniture_embedding_source_current s ON s.item_id = c.item_id "
        "JOIN roompilot.furniture_embeddings e "
        "  ON e.item_id = s.item_id AND e.text_hash = s.text_hash "
        " AND e.embedding_model = %s "
        "WHERE c.kind = 'furniture' AND c.category_code = ANY(%s) "
        "  AND c.glb_url IS NOT NULL AND c.glb_url <> '' "
        "  AND COALESCE(c.width_cm, 0) >= 20 AND COALESCE(c.depth_cm, 0) >= 20 "
        "ORDER BY e.embedding <=> %s::vector "
        "LIMIT %s"
    )

    entries: dict[str, list[str]] = {}
    started = time.time()
    for (family, style), vector in zip(keys, vectors):
        literal = "[" + ",".join(f"{v:.6f}" for v in vector.tolist()) + "]"
        cur.execute(sql, (EMBEDDING_MODEL, families[family], literal, args.top))
        ids = [row[0] for row in cur.fetchall()]
        if ids:
            entries[f"{family}|{style}"] = ids
    print(f"檢索完成 {time.time() - started:.1f}s，{len(entries)} 組有結果")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "schema_version": "roompilot.rag_offer_cache.v1",
                "embedding_model": EMBEDDING_MODEL,
                "top": args.top,
                "entries": entries,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"已寫入 {out_path}（{out_path.stat().st_size / 1024:.0f} KB）")

    for probe in ("bed|scandinavian", "tv-bench|modern_minimal", "sofa|*"):
        print(f"  {probe}: {entries.get(probe, [])[:3]}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
