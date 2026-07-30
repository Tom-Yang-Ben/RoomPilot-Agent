"""taiwan_style_cards.json + taxonomy_v1.json → taxonomy_v2.json（六風格版）。

風格從 12 個收斂成色卡定義的 6 個，並把每個風格的 3 張色卡與 palette 帶進 taxonomy，
讓 VLM 標註與需求解析都能引用色票判斷。其餘詞表（圖樣 / 氛圍 / 房型 / 類別對照）沿用 v1。

用法：
    python3 json_adjustment/build_taxonomy_v2.py
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
CARDS = PROJ / "taiwan_style_cards.json"
V1 = PROJ / "vlm_annotation" / "taxonomy_v1.json"
DST = PROJ / "vlm_annotation" / "taxonomy_v2.json"
TZ8 = timezone(timedelta(hours=8))

# 色卡只提供卡名與色票，判定用的定義文字在此撰寫（VLM 與需求解析都會讀這段）
DEFINITIONS = {
    "scandinavian": (
        "淺色原木與白色基調，搭配燕麥、米白與柔和灰綠，線條簡潔圓潤，"
        "布藝、羊毛與淺色木材為主，重視自然採光、留白與溫暖質感，氛圍明亮放鬆。"
    ),
    "japanese": (
        "日式侘寂與禪意，原木、藤編、亞麻與和紙等自然材質，米灰與麻褐等低彩度大地色，"
        "家具低矮貼地，線條乾淨，強調留白、收納整齊與寧靜秩序感。"
    ),
    "modern_minimal": (
        "俐落直線與幾何形體，黑白灰與暖灰為主色，玻璃、金屬與烤漆面材，"
        "平整無把手面板，裝飾極少，強調機能與比例，整體乾淨明快、都會感強。"
    ),
    "cream": (
        "以奶油白、奶茶與淺駝為主調，柔霧質感與圓潤曲線，大量布藝軟裝、絨布與淺色木質，"
        "邊角圓弧、視覺柔和，氛圍溫柔療癒並帶法式優雅。"
    ),
    "industrial": (
        "裸露質感為特色，黑鐵件、深色木材、皮革與水泥灰，粗獷金屬結構外露，色調深沉，"
        "常見鉚釘、管線與復古工坊元素，氛圍粗獷率性。"
    ),
    "american": (
        "厚實木作與線板細節，米白、駝色搭配胡桃木或櫻桃木等深色木質，皮革與格紋布藝，"
        "從鄉村溫馨到現代輕奢皆有，色調沉穩大器，強調舒適包覆感與家庭氛圍。"
    ),
}

# 6×6 相容度矩陣（對稱）。檢索時做風格加權：使用者要 A，B 的分數 = compat[A][B]
COMPAT = {
    "scandinavian":   {"scandinavian": 1.0, "japanese": 0.9, "modern_minimal": 0.8, "cream": 0.7, "american": 0.4, "industrial": 0.3},
    "japanese":       {"japanese": 1.0, "scandinavian": 0.9, "modern_minimal": 0.8, "cream": 0.5, "industrial": 0.4, "american": 0.2},
    "modern_minimal": {"modern_minimal": 1.0, "scandinavian": 0.8, "japanese": 0.8, "industrial": 0.7, "cream": 0.5, "american": 0.4},
    "cream":          {"cream": 1.0, "scandinavian": 0.7, "american": 0.7, "modern_minimal": 0.5, "japanese": 0.5, "industrial": 0.2},
    "industrial":     {"industrial": 1.0, "modern_minimal": 0.7, "american": 0.5, "japanese": 0.4, "scandinavian": 0.3, "cream": 0.2},
    "american":       {"american": 1.0, "cream": 0.7, "industrial": 0.5, "modern_minimal": 0.4, "scandinavian": 0.4, "japanese": 0.2},
}

# 舊 12 風格 → 新 6 風格的參考對映。只用於保留欄位的可讀性與抽驗比對，
# 實際風格值一律由 reclassify_styles.py 重新判定（映射不乾淨的佔 33.6%）
LEGACY_HINT = {
    "nordic": "scandinavian",
    "japandi": "japanese",
    "minimalist": "modern_minimal",
    "modern": "modern_minimal",
    "contemporary": "modern_minimal",
    "industrial": "industrial",
    "american_classic": "american",
    "mid_century": None,
    "scandi_luxe": None,
    "french_country": None,
    "rustic": None,
    "boho": None,
}


def main() -> int:
    cards = json.loads(CARDS.read_text(encoding="utf-8"))
    v1 = json.loads(V1.read_text(encoding="utf-8"))

    styles = {}
    for entry in cards["styles"]:
        sid = entry["style_id"]
        if sid not in DEFINITIONS:
            raise SystemExit(f"色卡出現未定義的風格 {sid}，請先在 DEFINITIONS 補上判定描述")
        styles[sid] = {
            "zh": entry["style_name_zh"],
            "definition": DEFINITIONS[sid],
            "cards": [
                {
                    "card_id": c["card_id"],
                    "name_zh": c["name_zh"],
                    "palette_hex": c["palette_hex"],
                    "image_file": c.get("image_file"),
                }
                for c in entry["cards"]
            ],
        }

    missing = set(styles) ^ set(COMPAT)
    if missing:
        raise SystemExit(f"style_compat 與色卡風格不一致：{missing}")

    out = {
        "taxonomy_version": "v2-six-style",
        "source_cards": "taiwan_style_cards.json",
        "source_cards_version": cards.get("schema_version"),
        "supersedes": v1.get("taxonomy_version"),
        "generated_at": datetime.now(TZ8).isoformat(timespec="seconds"),
        "styles": styles,
        "style_compat": COMPAT,
        "legacy_style_hint": LEGACY_HINT,
        # 以下沿用 v1，未隨風格改版
        "pattern_enum": v1["pattern_enum"],
        "visual_weight_enum": v1["visual_weight_enum"],
        "height_zone_enum": v1["height_zone_enum"],
        "role_enum": v1["role_enum"],
        "room_enum": v1["room_enum"],
        "mood_vocab": v1["mood_vocab"],
        "category_map": v1["category_map"],
    }

    DST.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已寫出 {DST.relative_to(PROJ)}")
    print(f"風格 {len(styles)} 個：" + "、".join(f"{k}({v['zh']}, {len(v['cards'])}卡)" for k, v in styles.items()))
    print(f"氛圍詞 {len(out['mood_vocab'])}／圖樣 {len(out['pattern_enum'])}／類別對照 {len(out['category_map'])}（沿用 v1）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
