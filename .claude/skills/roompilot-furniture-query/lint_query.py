#!/usr/bin/env python3
"""RoomPilot 檢索句校驗器。

把要送進 POST /api/rag/search 的 query 字串拿來比對真實受控詞表，
在送出前抓出「看起來會動、實際撈錯東西」的寫法。

詞表讀 backend/spatial_data/rag/data/*.json（vocab.py 的同一份來源），
不讀 references/vocabulary.md——那份是給人看的副本，詞表改版時本腳本會先抓到。

用法：
    python3 lint_query.py "客廳，japanese 日式、侘寂自然色卡，寧靜／自然；要一張沙發；…"
    python3 lint_query.py --file query.txt --sized-by-client
    cat query.txt | python3 lint_query.py - --json

退出碼：0 = 無 FAIL；1 = 有 FAIL（--strict 時 WARN 也算）；2 = 用法或環境錯誤。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

QUERY_MAX_CHARS = 1000  # backend/spatial_data/rag/models.py:83
MAX_STYLES = 2  # models.py:58
MAX_MOODS = 3  # models.py:59

# 六風格的口語別名。舊 12 風格中有對應者也列在這裡（鄉村／中古世紀 → american）。
STYLE_ALIASES: dict[str, tuple[str, ...]] = {
    "scandinavian": ("scandinavian", "北歐風", "北歐", "nordic", "scandi"),
    "japanese": ("japanese", "日式", "和風", "無印風", "無印", "侘寂", "japandi"),
    "modern_minimal": (
        "modern_minimal", "現代簡約", "極簡", "簡約", "性冷淡", "minimalist",
    ),
    "cream": ("cream", "奶油風", "奶油", "奶茶色", "奶茶"),
    "industrial": ("industrial", "工業風", "工業", "loft", "LOFT"),
    "american": ("american", "美式", "中古世紀", "mid-century", "輕奢", "鄉村"),
}

# 現行六風格沒有對應的舊詞／外來詞。必須換掉，換完要告訴使用者。
UNSUPPORTED_STYLES: dict[str, str] = {
    "波希米亞": "scandinavian（天然纖維與編織質感最接近）",
    "boho": "scandinavian（天然纖維與編織質感最接近）",
    "法式鄉村": "cream（法式柔霧色卡）",
    "french_country": "cream（法式柔霧色卡）",
    "法式": "cream（法式柔霧色卡）",
    "mid_century": "american",
    "contemporary": "modern_minimal",
    "當代風": "modern_minimal",
    "scandi_luxe": "american（現代輕奢）或 cream",
    "rustic": "american（鄉村溫馨色卡）",
    "地中海": "cream 或 scandinavian",
    "新古典": "american（經典優雅色卡）",
    "巴洛克": "american（經典優雅色卡）",
    "摩洛哥": "無對應，建議改用色卡與材質描述",
}

# 常被寫錯的氛圍詞 → 詞表裡真正存在的詞。mood_score 是逐字集合交集，寫錯 = 0 分。
MOOD_CONFUSABLES: dict[str, tuple[str, ...]] = {
    "溫暖": ("溫馨", "溫潤"),
    "有溫度": ("溫馨", "溫潤"),
    "安靜": ("寧靜", "靜謐"),
    "平靜": ("寧靜", "靜謐"),
    "清爽": ("俐落", "純粹"),
    "簡潔": ("俐落", "純粹"),
    "乾淨": ("俐落", "純粹"),
    "舒適": ("放鬆",),
    "舒服": ("放鬆",),
    "大氣": ("大器",),
    "氣派": ("大器",),
    "典雅": ("優雅", "精緻"),
    "有質感": ("精緻", "優雅"),
    "樸素": ("質樸",),
    "素樸": ("質樸",),
    "奢華": ("高級",),
    "高檔": ("高級",),
    "隨性": ("率性",),
    "童趣": ("活潑",),
    "可愛": ("活潑",),
    "冷靜": ("沉穩",),
    "穩重": ("沉穩",),
    "內斂": ("沉穩",),
    "都市感": ("都會",),
    "城市感": ("都會",),
    "年代感": ("復古", "懷舊"),
    "未來感": (),  # 詞表沒有落點，寧可不寫氛圍
    "有個性": (),
}

ROOM_ALIASES: dict[str, tuple[str, ...]] = {
    "living_room": ("客廳", "起居室", "living_room"),
    "bedroom": ("主臥", "次臥", "臥室", "寢室", "bedroom"),
    "dining_room": ("餐廳", "飯廳", "用餐區", "dining_room"),
    "kitchen": ("廚房", "中島區", "kitchen"),
    "bathroom": ("浴室", "衛浴", "廁所", "bathroom"),
    "study": ("書房", "工作室", "辦公區", "study"),
    "kids_room": ("兒童房", "小孩房", "嬰兒房", "kids_room"),
    "entryway": ("玄關", "鞋櫃區", "entryway"),
    "outdoor": ("陽台", "露台", "庭院", "戶外", "outdoor"),
}

# 不在家具型錄的品項。家電留在問卷與 scene_json.render_context 供第 8 步生圖。
NON_CATALOG_ITEMS: dict[str, str] = {
    "冰箱": "家電",
    "洗衣機": "家電",
    "烘乾機": "家電",
    "冷氣": "家電",
    "空調": "家電",
    "微波爐": "家電",
    "烤箱": "家電",
    "洗碗機": "家電",
    "除濕機": "家電",
    "電視機": "家電",
    "抽油煙機": "家電",
    "窗簾": "非型錄品項",
    "馬桶": "衛浴設備",
    "浴缸": "衛浴設備",
    "洗手台": "衛浴設備",
    "流理台": "廚具",
}

# 數字 + 長度單位。「米」要排除米白／米色等顏色詞。
DIMENSION_PATTERNS = (
    re.compile(r"\d+(?:\.\d+)?\s*(?:公分|公尺|cm|CM|吋|inch)", re.IGNORECASE),
    re.compile(r"\d+(?:\.\d+)?\s*米(?![白色灰黃棕])"),
    re.compile(r"[一二兩三四五六七八九十百]+\s*(?:公分|公尺|米(?![白色灰黃棕]))"),
)

PRICE_ABSOLUTE_PATTERNS = (
    re.compile(r"\d[\d,]*\s*(?:元|塊|萬|k|K)"),
    re.compile(r"[一二兩三四五六七八九十]+\s*萬"),
)

# 「高級」是 24 個氛圍詞之一，故不列為相對價位詞，避免誤判。
PRICE_RELATIVE_WORDS = (
    "便宜", "平價", "省錢", "划算", "不要太貴",
    "中等價位", "中價位", "高檔", "高階", "貴一點", "好一點的",
)

SET_WORDS = ("一整組", "整組", "一套", "全室", "配一組", "整間")


class Finding:
    __slots__ = ("level", "code", "message", "hint")

    def __init__(self, level: str, code: str, message: str, hint: str = "") -> None:
        self.level = level
        self.code = code
        self.message = message
        self.hint = hint

    def as_dict(self) -> dict[str, str]:
        return {
            "level": self.level,
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
        }


def find_repo_root(start: Path) -> Path | None:
    marker = Path("backend/spatial_data/rag/data/taxonomy.json")
    for candidate in [start, *start.parents]:
        if (candidate / marker).is_file():
            return candidate
    return None


def load_vocab(repo_root: Path) -> dict[str, Any]:
    data_dir = repo_root / "backend" / "spatial_data" / "rag" / "data"
    taxonomy = json.loads((data_dir / "taxonomy.json").read_text(encoding="utf-8"))
    groups = json.loads((data_dir / "category_groups.json").read_text(encoding="utf-8"))
    cards: dict[str, str] = {}
    full_taxonomy = repo_root / "rag" / "vlm_annotation" / "taxonomy_v2.json"
    if full_taxonomy.is_file():
        full = json.loads(full_taxonomy.read_text(encoding="utf-8"))
        for style_id, style in full.get("styles", {}).items():
            for card in style.get("cards", []):
                name = card.get("name_zh")
                if name:
                    cards[name] = style_id
    return {
        "styles": taxonomy["styles"],
        "moods": list(taxonomy["moods"]),
        "patterns": list(taxonomy["patterns"]),
        "groups": groups["groups"],
        "room_default_sets": groups["room_default_sets"],
        "cards": cards,
    }


def consume_matches(text: str, terms: dict[str, str]) -> tuple[dict[str, list[str]], str]:
    """長詞優先比對並吃掉命中片段，避免「床」誤中「床邊桌」。"""
    hits: dict[str, list[str]] = {}
    remaining = text
    for term in sorted(terms, key=len, reverse=True):
        if term and term in remaining:
            hits.setdefault(terms[term], []).append(term)
            remaining = remaining.replace(term, "\x00" * len(term))
    return hits, remaining


def check(query: str, vocab: dict[str, Any], sized_by_client: bool) -> tuple[list[Finding], dict[str, Any]]:
    findings: list[Finding] = []
    detected: dict[str, Any] = {}
    text = query.strip()

    # --- 結構性硬限制 ---
    if not text:
        return [Finding("FAIL", "empty_query", "檢索句為空。")], detected
    if len(text) > QUERY_MAX_CHARS:
        findings.append(Finding(
            "FAIL", "query_too_long",
            f"檢索句 {len(text)} 字，超過 API 上限 {QUERY_MAX_CHARS} 字。",
            "刪掉重複的形容詞，語意描述維持 30–120 字即可。",
        ))

    # --- 尺寸：硬過濾，猜錯就砍光正確結果 ---
    dimensions = [m.group(0) for pattern in DIMENSION_PATTERNS for m in pattern.finditer(text)]
    if dimensions:
        detected["dimensions"] = dimensions
        if not sized_by_client:
            findings.append(Finding(
                "FAIL", "unconfirmed_dimension",
                f"出現尺寸 {'、'.join(dimensions)}，而尺寸是硬過濾條件。",
                "屋主親口給的數字才可以寫，確認後加 --sized-by-client；"
                "若只是「不要太大」這類感受，改寫進語意描述，不要換算成公分。",
            ))

    # --- 色卡（先吃掉，避免「自然木質」被當成氛圍詞「自然」、「法式柔霧」被當成舊詞「法式」）---
    card_hits, text_after_cards = consume_matches(text, dict(vocab["cards"]))
    card_names = [name for names in card_hits.values() for name in names]
    detected["cards"] = card_names

    # --- 舊詞（再吃掉，避免「法式鄉村」的「鄉村」被當成 american）---
    legacy_hits, text_rest = consume_matches(
        text_after_cards, {term: term for term in UNSUPPORTED_STYLES}
    )

    # --- 風格 ---
    style_terms = {alias: sid for sid, aliases in STYLE_ALIASES.items() for alias in aliases}
    style_hits, _ = consume_matches(text_rest, style_terms)
    styles = sorted(style_hits)
    for card_name in card_names:
        card_style = vocab["cards"][card_name]
        if card_style not in styles:
            styles.append(card_style)
            findings.append(Finding(
                "WARN", "card_style_mismatch",
                f"色卡「{card_name}」屬於 {card_style}，但檢索句沒寫這個風格。",
                f"補上「{card_style} {vocab['styles'][card_style]['zh']}」，或換一張所寫風格的色卡。",
            ))
    detected["styles"] = styles

    if not styles:
        findings.append(Finding(
            "WARN", "no_style",
            "沒有偵測到六風格中的任何一個，風格加權會落在中性 0.5。",
            "屋主真的沒有調性偏好才這樣送；有偏好就補風格 id + 中文名。",
        ))
    elif len(styles) > MAX_STYLES:
        findings.append(Finding(
            "WARN", "too_many_styles",
            f"偵測到 {len(styles)} 個風格（{'、'.join(styles)}），上限 {MAX_STYLES} 個。",
            "多的會被截掉；相斥風格還會互相稀釋（cream↔industrial 相容度 0.2）。",
        ))

    for legacy in sorted(legacy_hits):
        findings.append(Finding(
            "WARN", "unsupported_style",
            f"「{legacy}」不在現行六風格內。",
            f"建議改用 {UNSUPPORTED_STYLES[legacy]}，並主動告訴使用者你換了詞。",
        ))

    # --- 氛圍：逐字集合交集，寫錯就是 0 分 ---
    mood_terms = {mood: mood for mood in vocab["moods"]}
    mood_hits, _ = consume_matches(text_rest, mood_terms)
    moods = sorted(mood_hits)
    detected["moods"] = moods

    # 三個名額已滿時不再挑近義詞——多出來的字是語意描述的一部分（「線條乾淨」），
    # 本來就不會、也不需要進 moods。
    for wrong, suggestions in ([] if len(moods) >= MAX_MOODS else MOOD_CONFUSABLES.items()):
        if wrong in text_rest and not any(s in moods for s in suggestions):
            hint = (
                f"詞表裡對應的是「{'」或「'.join(suggestions)}」。"
                if suggestions
                else "詞表沒有對應的詞，寧可不寫氛圍（回中性 0.5），把感覺寫進語意描述。"
            )
            findings.append(Finding(
                "WARN", "mood_not_in_vocab",
                f"「{wrong}」不在 24 個氛圍詞內，mood_score 會算 0 分。", hint,
            ))

    if len(moods) > MAX_MOODS:
        findings.append(Finding(
            "WARN", "too_many_moods",
            f"偵測到 {len(moods)} 個氛圍詞（{'、'.join(moods)}），上限 {MAX_MOODS} 個。",
            "挑最關鍵的三個，其餘寫進語意描述。",
        ))

    # --- 家具群組 ---
    # 群組刻意重疊（category_groups.json 的 note：「Groups intentionally overlap」），
    # 例如「電視櫃」同屬 storage 與 media、「兒童桌」同屬 desk 與 kids。
    # consume_matches 一個詞只歸一組，所以命中後要把該詞的所有歸屬群組都補回來，
    # 否則摘要會漏報使用者實際可能觸發的硬過濾。
    term_owners: dict[str, list[str]] = {}
    for group_id, spec in vocab["groups"].items():
        for label in str(spec.get("label_zh", "")).split("／"):
            if label:
                term_owners.setdefault(label, []).append(group_id)
        for category in spec.get("categories", []):
            term_owners.setdefault(category, []).append(group_id)
    group_terms = {term: owners[0] for term, owners in term_owners.items()}
    group_hits, _ = consume_matches(text, group_terms)

    matched_terms = sorted({term for terms in group_hits.values() for term in terms})
    hits_by_group: dict[str, list[str]] = {}
    for term in matched_terms:
        for group_id in term_owners[term]:
            hits_by_group.setdefault(group_id, []).append(term)
    groups = sorted(hits_by_group)
    detected["groups"] = groups
    detected["group_terms"] = hits_by_group

    if not groups:
        findings.append(Finding(
            "WARN", "no_category",
            "沒有偵測到 19 個家具群組中的任何一個，會走跨類別檢索。",
            "屋主只給風格沒給品項時這是正確做法（別硬猜類別），"
            "但記得追問想先看哪一件。",
        ))

    for item, kind in NON_CATALOG_ITEMS.items():
        if item in text:
            findings.append(Finding(
                "WARN", "non_catalog_item",
                f"「{item}」屬於{kind}，不在家具型錄裡。",
                "家電需求留在問卷與 scene_json.render_context 供第 8 步生圖，不進 2D/3D 擺設。",
            ))

    # --- 房型：硬過濾，只能一個 ---
    room_terms = {alias: rid for rid, aliases in ROOM_ALIASES.items() for alias in aliases}
    room_hits, _ = consume_matches(text, room_terms)
    rooms = sorted(room_hits)
    detected["rooms"] = rooms

    if not rooms:
        findings.append(Finding(
            "WARN", "no_room_type",
            "沒有偵測到房型，不會做房型硬過濾。",
            "結果可能混入其他空間的物件；屋主講了空間就補上。",
        ))
    elif len(rooms) > 1:
        findings.append(Finding(
            "WARN", "multiple_room_types",
            f"偵測到多個房型（{'、'.join(rooms)}），房型硬過濾只能一個。",
            "拆成多次檢索，一個空間一句。",
        ))

    # --- 價格：具體金額與相對詞互斥 ---
    absolute = [m.group(0) for pattern in PRICE_ABSOLUTE_PATTERNS for m in pattern.finditer(text)]
    relative = [word for word in PRICE_RELATIVE_WORDS if word in text]
    detected["price_absolute"] = absolute
    detected["price_relative"] = relative
    if absolute and relative:
        findings.append(Finding(
            "WARN", "price_conflict",
            f"同時出現具體金額（{'、'.join(absolute)}）與相對價位詞（{'、'.join(relative)}）。",
            "兩者互斥，解析器會二選一。留具體金額就好。",
        ))

    is_set = any(word in text for word in SET_WORDS)
    detected["is_set"] = is_set
    if is_set and not absolute:
        findings.append(Finding(
            "WARN", "set_without_budget",
            "要求成套配置但沒給總預算。",
            "有總預算才能依各群組中位價比例分配（×1.3 寬容係數）；"
            "沒有的話各品項不設價格上限。",
        ))
    if is_set and len(rooms) == 1 and rooms[0] not in vocab["room_default_sets"]:
        findings.append(Finding(
            "WARN", "no_default_set",
            f"房型 {rooms[0]} 沒有預設組合，系統不會替你推論品項。",
            "回頭問屋主要哪些品項，不要自行補。",
        ))

    return findings, detected


def format_report(findings: list[Finding], detected: dict[str, Any], query: str) -> str:
    lines: list[str] = []
    fails = [f for f in findings if f.level == "FAIL"]
    warns = [f for f in findings if f.level == "WARN"]

    for finding in fails + warns:
        lines.append(f"[{finding.level}] {finding.code}: {finding.message}")
        if finding.hint:
            lines.append(f"        → {finding.hint}")
    if not findings:
        lines.append("[PASS] 檢索句通過所有檢查。")

    def show(label: str, value: Any) -> str:
        if not value:
            return f"  {label}：（無）"
        if isinstance(value, list):
            return f"  {label}：{'、'.join(str(v) for v in value)}"
        return f"  {label}：{value}"

    lines.append("")
    lines.append(f"偵測摘要（{len(query.strip())} 字 / 上限 {QUERY_MAX_CHARS}）")
    lines.append(show("房型（硬過濾）", detected.get("rooms")))
    lines.append(show("家具群組（硬過濾）", detected.get("groups")))
    lines.append(show("尺寸（硬過濾）", detected.get("dimensions")))
    lines.append(show("價格", (detected.get("price_absolute") or []) + (detected.get("price_relative") or [])))
    lines.append(show("風格（軟加權）", detected.get("styles")))
    lines.append(show("色卡（軟加權）", detected.get("cards")))
    lines.append(show("氛圍（軟加權）", detected.get("moods")))
    lines.append(show("成套配置", "是" if detected.get("is_set") else ""))
    lines.append("")
    lines.append(f"FAIL {len(fails)} 項、WARN {len(warns)} 項。")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="校驗要送進 POST /api/rag/search 的 query 字串。",
    )
    parser.add_argument("query", nargs="?", help="檢索句；用 - 表示從 stdin 讀取")
    parser.add_argument("--file", type=Path, help="從檔案讀取檢索句")
    parser.add_argument(
        "--sized-by-client", action="store_true",
        help="檢索句裡的尺寸確實是屋主親口給的，放行尺寸檢查",
    )
    parser.add_argument("--strict", action="store_true", help="WARN 也視為失敗")
    parser.add_argument("--json", action="store_true", help="輸出 JSON")
    args = parser.parse_args(argv)

    if args.file:
        if not args.file.is_file():
            print(f"找不到檔案：{args.file}", file=sys.stderr)
            return 2
        query = args.file.read_text(encoding="utf-8")
    elif args.query == "-" or (args.query is None and not sys.stdin.isatty()):
        query = sys.stdin.read()
    elif args.query is not None:  # 明確傳空字串要走 empty_query 檢查，不是用法錯誤
        query = args.query
    else:
        parser.print_usage(sys.stderr)
        return 2

    repo_root = find_repo_root(Path(__file__).resolve().parent)
    if repo_root is None:
        print(
            "找不到 backend/spatial_data/rag/data/taxonomy.json；"
            "請在 RoomPilot-Agent repo 內執行。",
            file=sys.stderr,
        )
        return 2

    try:
        vocab = load_vocab(repo_root)
    except (OSError, ValueError, KeyError) as exc:
        print(f"讀取詞表失敗：{exc}", file=sys.stderr)
        return 2

    findings, detected = check(query, vocab, args.sized_by_client)
    has_fail = any(f.level == "FAIL" for f in findings)
    has_warn = any(f.level == "WARN" for f in findings)

    if args.json:
        print(json.dumps(
            {
                "query": query.strip(),
                "length": len(query.strip()),
                "findings": [f.as_dict() for f in findings],
                "detected": {k: v for k, v in detected.items() if k != "group_terms"},
            },
            ensure_ascii=False,
            indent=2,
        ))
    else:
        print(format_report(findings, detected, query))

    return 1 if has_fail or (args.strict and has_warn) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
