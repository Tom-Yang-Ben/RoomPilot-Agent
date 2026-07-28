"""把 v3 的六風格判定與 embedded_text 併回官方家具目錄，產出交付給 SQL 端的主表。

依 i_need_rag.md 的來源限制：向量檔的 `embedded_text` / `text_hash` 必須與官方家具
JSON **完全一致**。因此兩邊的文字必須同源——本腳本直接把 v3 已經算好、且已據以
產生向量的 `embedded_text` 原樣搬進官方目錄，**不重新組合**，確保 hash 對得上、
現有 9,349 個向量不必重算。

同時帶入六風格改版的欄位（style_primary 從舊 12 風格改為 6 風格 + 色卡），
否則 SQL 端的風格欄位會與向量所依據的文字不一致。

輸出：rag_export/furniture_official_catagory.json（9,349 筆，正式家具）

用法：
    python3 json_adjustment/build_official_catalog.py
    python3 json_adjustment/build_official_catalog.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
OFFICIAL = PROJ / "json_adjustment" / "furniture_official_catagory.json"
V3 = PROJ / "rag_dataset" / "furniture_enriched_v3.json"
DST = PROJ / "rag_export" / "furniture_official_catagory.json"
TZ8 = timezone(timedelta(hours=8))

# 從 v3 帶進官方目錄的欄位。chroma_metadata / rag_indexable 是檢索端專用，不帶。
CARRY_OVER = [
    # 向量交付的必要條件（i_need_rag.md 要求兩邊完全一致）
    "embedded_text",
    "text_hash",
    "text_format_version",
    # 六風格改版
    "style_primary",
    "style_secondary",
    "style_card",
    "style_card_id",
    "style_palette_hex",
    "style_confidence",
    "style_source",
    "style_primary_v1",
    "style_secondary_v1",
    # 分類修正
    "category_final",
    "category_conflict",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    official = json.loads(OFFICIAL.read_text(encoding="utf-8"))
    v3 = json.loads(V3.read_text(encoding="utf-8"))
    v3_by_id = {i["id"]: i for i in v3["items"]}

    out_items = []
    dropped = []
    for item in official["items"]:
        src = v3_by_id.get(item["id"])
        if not src:
            # v3 已排除的非正式家具（目前 1 筆：被誤分類成扶手椅的保溫瓶）
            dropped.append({"id": item["id"], "name_zh": item.get("name_zh")})
            continue
        new = dict(item)
        for key in CARRY_OVER:
            if key in src:
                new[key] = src[key]
        out_items.append(new)

    now = datetime.now(TZ8).isoformat(timespec="seconds")
    out = dict(official)
    out.update({
        "schema_version": "2.1+six_style+embedded_text",
        "supersedes": official.get("schema_version"),
        "count": len(out_items),
        "taxonomy_version": "v2-six-style",
        "embedding_target": {
            "embedding_model": "BAAI/bge-m3",
            "embedding_dimension": 1024,
            "distance_metric": "cosine",
            "normalized": True,
        },
        "text_format_version": v3.get("text_format_version"),
        "text_fields": v3.get("text_fields"),
        "excluded_items": dropped,
        "generated_at": now,
        "notes": [
            "embedded_text / text_hash 直接取自 furniture_enriched_v3.json，未重新組合，"
            "與 rag_export/furniture_embeddings_bge_m3.jsonl 為同一批文字。",
            "style_primary / style_secondary 已改為六風格（taxonomy_v2），"
            "舊的 12 風格值保留在 style_primary_v1 / style_secondary_v1。",
            "excluded_items 為非正式家具，已排除於 9,349 筆之外。",
        ],
        "items": out_items,
    })

    # 一致性檢查：交付的向量檔必須與本檔逐筆 hash 相同
    emb_path = PROJ / "rag_export" / "furniture_embeddings_bge_m3.jsonl"
    legacy = PROJ / "rag_export" / "furniture_embeddings.jsonl"
    check = emb_path if emb_path.exists() else legacy
    mismatch = missing = 0
    if check.exists():
        by_id = {i["id"]: i["text_hash"] for i in out_items}
        seen = set()
        with check.open(encoding="utf-8") as fh:
            for line in fh:
                row = json.loads(line)
                fid = row.get("item_id") or row.get("furniture_id")
                seen.add(fid)
                if fid not in by_id:
                    missing += 1
                elif by_id[fid] != row["text_hash"]:
                    mismatch += 1
        not_embedded = len(by_id) - len(seen & set(by_id))
        print(f"對照 {check.name}：hash 不符 {mismatch}／向量檔多出 {missing}／缺向量 {not_embedded}")
    else:
        print("尚未產出向量檔，略過一致性檢查")

    print(f"正式家具 {len(out_items)} 筆　排除 {len(dropped)} 筆")
    for d in dropped:
        print(f"  ✂ {d['id'][:52]}  {d['name_zh']}")
    have_text = sum(1 for i in out_items if i.get("embedded_text"))
    print(f"帶有 embedded_text：{have_text} 筆　帶有 text_hash：{sum(1 for i in out_items if i.get('text_hash'))} 筆")

    if args.dry_run:
        print("\n--- 範例（第一筆的新增欄位）---")
        s = out_items[0]
        print(json.dumps({k: s.get(k) for k in CARRY_OVER}, ensure_ascii=False, indent=2)[:900])
        return 0

    DST.parent.mkdir(exist_ok=True)
    DST.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已寫出 {DST.relative_to(PROJ)}  ({DST.stat().st_size / 1024 / 1024:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
