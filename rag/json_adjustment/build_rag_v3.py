"""furniture_enriched_v2.json → v3（RAG-ready，供 bge-m3 向量化與 SQL 交付）。

依 json_adjustment/RAGSQL.md 的交付規格加工。原則同本專案既有慣例：**只增不覆寫**，
v2 既有欄位一律保留原值，v3 只新增衍生欄位。

新增內容：
  1. embedded_text / text_hash / text_format_version  ── 送進 embedding model 的正規文本與指紋
  2. chroma_metadata                                  ── 攤平成純量的過濾用 metadata（Chroma where 只吃 scalar）
  3. category_final / category_conflict               ── 解 865 筆 name_category_conflict
  4. rag_indexable                                    ── 是否納入向量索引（排除 is_active=False）
  5. rag_text 補漏（僅 150 筆原本為空者填入 fallback，並記 rag_text_source）

用法：
    python3 json_adjustment/build_rag_v3.py
    python3 json_adjustment/build_rag_v3.py --dry-run     # 只印統計不寫檔
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
SRC = PROJ / "rag_dataset" / "furniture_enriched_v2.json"
DST = PROJ / "rag_dataset" / "furniture_enriched_v3.json"
TAXONOMY = PROJ / "vlm_annotation" / "taxonomy_v2.json"          # 六風格色卡版
STYLE_V2 = PROJ / "vlm_annotation" / "style_v2_annotations.jsonl"  # reclassify_styles.py 產出

TEXT_FORMAT_VERSION = "v1"
EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_DIMENSION = 1024
TZ8 = timezone(timedelta(hours=8))

# embedded_text 實際使用的欄位與順序（會寫進 v3 header 的 text_fields，SQL 端據此驗證）
TEXT_FIELDS = [
    "name_zh",
    "category_final",
    "object_type_zh",
    "colors",
    "materials",
    "room_types",
    "style_primary",
    "style_secondary",
    "style_card",       # 六風格色卡版新增：色卡名（如「侘寂自然」）本身就是好的檢索訊號
    "mood_tags",
    "pattern",
    "shape_tags",
    "description",
    "features",
    "search_keywords",
]

ROOM_ZH = {
    "living_room": "客廳",
    "bedroom": "臥室",
    "dining_room": "餐廳",
    "study": "書房",
    "entryway": "玄關",
    "kids_room": "兒童房",
    "outdoor": "戶外",
    "bathroom": "浴室",
    "kitchen": "廚房",
}

# VLM 偶有英文或複合值，正規化回 taxonomy 的 4 個受控圖樣
PATTERN_NORM = {
    "solid": "素色",
    "geometric": "幾何",
    "wood_grain": "木紋",
    "素色/木紋": "木紋",
    "紋理": "素色",
    "漸變": "素色",
    "漸層": "素色",
    "大理石紋": "花紋",
    "動物圖案": "花紋",
    "文字圖案": "花紋",
}


def load_taxonomy() -> dict:
    return json.loads(TAXONOMY.read_text(encoding="utf-8"))


def load_style_v2() -> dict:
    """reclassify_styles.py 的判定結果：id → {style_primary, style_secondary, card_id…}。"""
    if not STYLE_V2.exists():
        return {}
    rows = {}
    with STYLE_V2.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except Exception:
                continue
            rows[row["id"]] = row  # 同一 id 重複時以最後一次為準
    return rows


def build_majority_map(style_v2: dict, items: list) -> dict:
    """從已判定的資料統計「舊 12 風格 → 新 6 風格」的多數決映射。

    用於尚未判定的品項（例如 API 額度中斷）。比手寫映射可靠，因為它反映的是
    模型在同一批資料上的實際判準；這些品項會標記 style_source=legacy_majority_map，
    日後補跑 reclassify_styles.py 就會被真正的判定取代。
    """
    by_old = {}
    old_of = {i["id"]: i.get("style_primary") for i in items}
    for fid, ann in style_v2.items():
        old = old_of.get(fid)
        if old:
            by_old.setdefault(old, Counter())[ann["style_primary"]] += 1
    return {old: counter.most_common(1)[0][0] for old, counter in by_old.items()}


def apply_style_v2(item: dict, ann: dict | None, cards: dict, fallback: dict | None = None) -> dict:
    """把六風格判定寫進 item，舊的 12 風格值搬到 *_v1 保留。

    沒有新判定時，用多數決映射補上——否則舊的 12 風格 key 留在 style_primary，
    檢索時 style_compat 查不到會拿 0 分，那批物件會被系統性壓到最後。
    """
    item["style_primary_v1"] = item.get("style_primary")
    item["style_secondary_v1"] = item.get("style_secondary")

    if not ann:
        mapped = (fallback or {}).get(item.get("style_primary"))
        if mapped:
            item["style_primary"] = mapped
            item["style_secondary"] = (fallback or {}).get(item.get("style_secondary"), mapped)
            item["style_source"] = "legacy_majority_map"
        else:
            item["style_source"] = "legacy_v1_unmapped"
        return item

    card = cards.get(ann["card_id"], {})
    item["style_primary"] = ann["style_primary"]
    item["style_secondary"] = ann["style_secondary"]
    item["style_card_id"] = ann["card_id"]
    item["style_card"] = card.get("name_zh", "")
    item["style_palette_hex"] = card.get("palette_hex", [])
    item["style_confidence"] = ann.get("confidence")
    item["style_reason"] = ann.get("reason")
    item["style_source"] = "text_reclassify_v2"
    return item


def as_list(value) -> list:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()]


def join_zh(values, limit=None) -> str:
    items = as_list(values)
    if limit:
        items = items[:limit]
    return "、".join(items)


def resolve_category(item: dict) -> tuple:
    """name_category_conflict 的 865 筆改用 suggested_category 作為檢索類別。"""
    conflict = item.get("consistency_flag") == "name_category_conflict"
    suggested = (item.get("suggested_category") or "").strip()
    if conflict and suggested:
        return suggested, True
    return item.get("canonical_category_zh") or "", conflict


def fill_rag_text(item: dict) -> tuple:
    """rag_text 為空時（150 筆）以既有欄位組回三段式，其餘原封不動。"""
    existing = as_list(item.get("rag_text"))
    if existing:
        return existing, "original"

    segments = []
    head = " ".join(
        x for x in [item.get("object_type_zh") or "", join_zh(item.get("shape_tags"), 2), join_zh(item.get("colors"), 3)] if x
    ).strip()
    if head:
        segments.append(head)
    feats = join_zh(item.get("features"))
    if feats:
        segments.append(feats)
    kws = as_list(item.get("search_keywords"))
    if kws:
        segments.append("；".join(kws))
    if not segments:
        desc = (item.get("description") or "").strip()
        if desc:
            segments.append(desc)
        name = (item.get("name_zh") or "").strip()
        if name and not segments:
            segments.append(name)
    return segments, ("fallback_derived" if segments else "empty")


def build_embedded_text(item: dict, category_final: str, style_zh: dict) -> str:
    """text_format_version v1：固定欄位順序的中文句式，欄位缺值則整段略過。"""
    parts = []

    def add(label, value):
        value = (value or "").strip().rstrip("。")  # 描述句尾自帶句號，避免組出「。。」
        if value:
            parts.append(f"{label}：{value}")

    add("名稱", (item.get("name_zh") or item.get("name_en") or "").strip())
    add("類別", category_final)
    add("物件類型", (item.get("object_type_zh") or "").strip())
    add("顏色", join_zh(item.get("colors")))
    add("材質", join_zh(item.get("materials")))
    add("適用空間", "、".join(ROOM_ZH.get(r, r) for r in as_list(item.get("room_types"))))

    styles = []
    for key in ("style_primary", "style_secondary"):
        raw = (item.get(key) or "").split("(")[0].strip()
        if raw and raw not in styles:
            styles.append(raw)
    add("風格", "、".join(f"{style_zh.get(s, s)}({s})" for s in styles))
    add("色卡", (item.get("style_card") or "").strip())

    add("氛圍", join_zh(item.get("mood_tags")))
    pattern = (item.get("pattern") or "").strip()
    add("表面圖樣", PATTERN_NORM.get(pattern, pattern))
    add("造型", join_zh(item.get("shape_tags")))
    add("描述", (item.get("description") or "").strip())
    add("特徵", join_zh(item.get("features")))
    add("關鍵字", "；".join(as_list(item.get("search_keywords"))))

    return "。".join(parts) + "。" if parts else ""


def build_chroma_metadata(item: dict, category_final: str, category_conflict: bool) -> dict:
    """Chroma metadata 只接受 str/int/float/bool，故 list 欄位一律攤平。"""
    rooms = as_list(item.get("room_types"))
    colors = as_list(item.get("colors"))
    materials = as_list(item.get("materials"))
    moods = as_list(item.get("mood_tags"))
    pattern = (item.get("pattern") or "").strip()

    w = item.get("width_cm") or 0.0
    d = item.get("depth_cm") or 0.0
    h = item.get("height_cm") or 0.0

    meta = {
        "furniture_id": item["id"],
        "name_zh": item.get("name_zh") or "",
        "category": category_final,
        "category_original": item.get("canonical_category_zh") or "",
        "category_conflict": bool(category_conflict),
        "style_primary": (item.get("style_primary") or "").split("(")[0].strip(),
        "style_secondary": (item.get("style_secondary") or "").split("(")[0].strip(),
        "style_card_id": item.get("style_card_id") or "",
        "style_card": item.get("style_card") or "",
        "style_primary_v1": item.get("style_primary_v1") or "",   # 舊 12 風格，供回溯比對
        "style_confidence": float(item.get("style_confidence") or 0.0),
        "pattern": PATTERN_NORM.get(pattern, pattern),
        "role": item.get("role") or "",
        "size_class": item.get("size_class") or "",
        "visual_weight": item.get("visual_weight") or "",
        "height_zone": item.get("height_zone") or "",
        "price_twd": int(item.get("price_twd") or 0),
        "price_is_estimated": bool(item.get("price_is_estimated")),
        "width_cm": float(w),
        "depth_cm": float(d),
        "height_cm": float(h),
        "max_dim_cm": float(max(w, d, h)),
        "footprint_m2": round(float(w) * float(d) / 10000.0, 4),
        "color_main": colors[0] if colors else "",
        "material_main": materials[0] if materials else "",
        # 多值欄位：兩用途 —— 前綴分隔字串供顯示與後過濾，布林旗標供 Chroma where 硬過濾
        "colors_flat": "|".join(colors),
        "materials_flat": "|".join(materials),
        "moods_flat": "|".join(moods),
        "rooms_flat": "|".join(rooms),
        "has_glb": bool(item.get("glb_url")),
        "duplicate_group": item.get("duplicate_group") or "",
        "confidence": float(item.get("confidence") or 0.0),
    }
    # 房型是硬過濾條件，攤成布林欄位讓 Chroma where 直接吃；
    # 氛圍走語意比對，不另開 24 個布林欄位，需要時以 moods_flat 後過濾
    for key in ROOM_ZH:
        meta[f"room_{key}"] = key in rooms
    return meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只印統計不寫檔")
    args = ap.parse_args()

    src = json.loads(SRC.read_text(encoding="utf-8"))
    items = src["items"]
    tax = load_taxonomy()
    style_zh = {k: v["zh"] for k, v in tax["styles"].items()}
    cards = {c["card_id"]: c for s in tax["styles"].values() for c in s["cards"]}
    style_v2 = load_style_v2()
    fallback = build_majority_map(style_v2, items)
    print(f"六風格判定結果：{len(style_v2)} 筆（taxonomy {tax['taxonomy_version']}）")
    if len(style_v2) < len(items):
        print(f"  未判定 {len(items) - len(style_v2)} 筆將套用多數決映射："
              + "、".join(f'{o}→{n}' for o, n in sorted(fallback.items())))

    stats = Counter()
    excluded: list = []
    text_lengths = []
    hashes = Counter()
    out_items = []

    for item in items:
        new = dict(item)  # 只增不覆寫：原欄位整份保留
        # 風格改用六風格色卡版；舊 12 風格搬到 *_v1。之後所有加工都要吃 new，不是 item
        new = apply_style_v2(new, style_v2.get(item["id"]), cards, fallback)
        stats[new["style_source"]] += 1
        category_final, category_conflict = resolve_category(item)

        rag_text, rag_source = fill_rag_text(item)
        if rag_source != "original":
            stats[f"rag_text_{rag_source}"] += 1
        new["rag_text"] = rag_text
        new["rag_text_source"] = rag_source

        new["category_final"] = category_final
        new["category_conflict"] = bool(category_conflict)
        if category_conflict:
            stats["category_conflict"] += 1

        embedded_text = build_embedded_text(new, category_final, style_zh)
        text_hash = hashlib.sha256(embedded_text.encode("utf-8")).hexdigest()
        new["embedded_text"] = embedded_text
        new["text_hash"] = text_hash
        new["text_format_version"] = TEXT_FORMAT_VERSION
        text_lengths.append(len(embedded_text))
        hashes[text_hash] += 1

        indexable = item.get("is_active") is not False and bool(embedded_text)
        new["rag_indexable"] = indexable
        stats["indexable" if indexable else "not_indexable"] += 1

        # 不可索引者直接排除在 v3 之外（例如 is_active=False 的錯誤分類品：
        # UNDERLÄTTA 保溫瓶被歸到「扶手椅」）。留在 v3 只會造成 9,350 vs 9,349
        # 的筆數落差，且它本來就進不了索引。v1/v2 仍保留該筆供回溯。
        if not indexable:
            excluded.append({
                "id": item["id"],
                "name_zh": item.get("name_zh"),
                "category": category_final,
                "reason": "is_active=False" if item.get("is_active") is False else "embedded_text 為空",
            })
            continue

        new["chroma_metadata"] = build_chroma_metadata(new, category_final, category_conflict)
        out_items.append(new)

    dup_hash = sum(c - 1 for c in hashes.values() if c > 1)
    now = datetime.now(TZ8).isoformat(timespec="seconds")

    out = {
        "schema": src.get("schema", "roompilot"),
        "schema_version": "3.0+rag_ready",
        "source_schema_version": src.get("schema_version"),
        "source_file": "rag_dataset/furniture_enriched_v2.json",
        "source_catalog": src.get("source_catalog"),
        "dataset_name": src.get("dataset_name"),
        "count": len(out_items),
        "source_item_count": len(items),
        "indexable_count": stats["indexable"],
        "excluded_items": excluded,
        "taxonomy_version": src.get("taxonomy_version"),
        "text_format_version": TEXT_FORMAT_VERSION,
        "text_fields": TEXT_FIELDS,
        "embedding_target": {
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dimension": EMBEDDING_DIMENSION,
            "distance_metric": "cosine",
            "normalized": True,
        },
        "id_key": "id",
        "generated_at": now,
        "notes": [
            "v3 只新增衍生欄位，v2 既有欄位原封不動保留。",
            "embedded_text 為 embedding 的唯一輸入來源；text_hash = sha256(embedded_text)。",
            "chroma_metadata 已攤平為純量，可直接餵 Chroma collection.add(metadatas=...)。",
            "category_final 對 865 筆 name_category_conflict 改用 suggested_category。",
            "rag_indexable=False 者已從 v3 排除（明細見 excluded_items），v1/v2 仍保留供回溯。",
        ],
        "items": out_items,
    }

    print(f"items            : {len(out_items)}")
    print(f"indexable        : {stats['indexable']}  (排除 {len(excluded)} 筆不可索引)")
    for e in excluded:
        print(f"  ✂ 已排除 {e['id'][:52]}  {e['name_zh']}（{e['reason']}）")
    print(f"category_conflict: {stats['category_conflict']} 筆改用 suggested_category")
    print(f"rag_text fallback: {stats['rag_text_fallback_derived']} 筆補齊, 仍為空 {stats['rag_text_empty']} 筆")
    print(f"embedded_text 長度: min {min(text_lengths)} / 中位 {sorted(text_lengths)[len(text_lengths)//2]} / max {max(text_lengths)}")
    print(f"text_hash 重複    : {dup_hash} 筆（文字完全相同的家具）")

    if args.dry_run:
        print("\n--- 範例 embedded_text ---")
        print(out_items[0]["embedded_text"])
        print("\n--- 範例 chroma_metadata ---")
        print(json.dumps(out_items[0]["chroma_metadata"], ensure_ascii=False, indent=2))
        return 0

    DST.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已寫出 {DST.relative_to(PROJ)}  ({DST.stat().st_size / 1024 / 1024:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
