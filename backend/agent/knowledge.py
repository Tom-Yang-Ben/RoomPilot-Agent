"""家具擺放潛規則 —— agent 的領域知識單一事實源(自 room_pilot2 移植)。

擺放邏輯的完整敘事(選件 → 擺位 → 修復,三個消費端同一份資料):

1. 房型基礎家具(ROOM_ESSENTIALS):臥室=床、客廳=沙發、餐廚=餐桌。
   選件缺了就自動補(select._ensure_room_essentials、前端 2D 規格保底)、
   擺位最優先卡位(ESSENTIAL_FAMILIES)、修復迴圈絕不靜默移除
   (place.resolve_placements 只升級回報)。
2. 成組副件(COMPANION_OF):床頭櫃貼床、茶几/電視櫃對沙發、餐椅繞桌、
   辦公椅貼書桌。只准貼主件的成組候選;主件不在或貼不上就退場,
   寧缺勿亂。餐桌成套餐椅數由 dining_chair_target() 決定,有桌必有椅。
3. 自由座椅(FREE_SEATING_FAMILIES):最後撿剩餘空間;沙發已就位的房間
   只准沙發左前/右前(對談位),不得卡進沙發-電視的視聽走廊。
4. 房型適配(ROOM_AFFINITY):決定家具能進哪些房型;未列 = 泛用件。
   戶外家具(is_outdoor_item)靠名稱記號辨識,室內房型一律排除。

擺放優先序(place.placement_hints):基礎家具(面積大→小)→ 泛用件 →
副件 → 自由座椅。語彙與引擎一致:型錄 normalized_type 先經 family_of()
摺疊成擺位「族系」。本模組只放宣告式知識,不放幾何 —— 座標一律由
backend.engine 計算。
"""
from __future__ import annotations

# ── 族系摺疊 ───────────────────────────────────────────────────────────
# 型錄具體類型 → 擺位族系(缺項 = 類型即族系)。涵蓋 scene_service._TYPE_FAMILY
# 與 layout_service 候選群組會出現的所有別名;agent 端自持一份,不 import server。
FAMILY_OF: dict[str, str] = {
    "fabric-sofa": "sofa",
    "leather-sofa": "sofa",
    "modular-sofa": "sofa",
    "sofa-bed": "sofa",
    "bed-frame": "bed",
    "pax-wardrobe": "wardrobe",
    "cabinets-cupboard": "wardrobe",
    "storage-solution-system": "wardrobe",
    "chests-of-drawer": "sideboard",
    "tv-media-furniture": "tv-bench",
    "table": "dining-table",
    "shelving-unit": "bookcase",
    # 電競椅摺進辦公椅族系:沿用 office-chair 的房型適配(臥室/儲藏)與成組(貼書桌)。
    "gaming-chair": "office-chair",
}


def family_of(normalized_type: str | None) -> str:
    """normalized_type → 擺位族系;未知類型原樣返回(泛用件)。"""
    key = str(normalized_type or "")
    return FAMILY_OF.get(key, key)


# ── 房型基礎家具 ───────────────────────────────────────────────────────
# 每個房型「應該具備」的基礎家具族系。三層保證:
# 1. 選件保底:已回答的房缺基礎家具 → 從候選自動補(select、前端 2D 規格)。
# 2. 擺位優先:基礎家具最先卡位,其他物件依它們的位置配置。
# 3. 修復護欄:連最小款都放不下也只升級回報,絕不靜默移除。
ROOM_ESSENTIALS: dict[str, tuple[str, ...]] = {
    "living_room": ("sofa",),
    "bedroom": ("bed",),
    "kitchen": ("dining-table",),
}

# 基礎家具「必備」的升級訊息(修復迴圈回報給使用者)。
ESSENTIAL_REQUIRED_ZH: dict[str, str] = {
    "bed": "臥室必須有床",
    "sofa": "客廳必須有沙發",
    "dining-table": "餐廚必須有餐桌",
}

# 擺位主件(成組的錨):最先卡好牆位,泛用件次之,副件(COMPANION_OF)最後
# 擺 —— 引擎的成組候選要有「已就位的主件」才貼得上去。
ANCHOR_FAMILIES: tuple[str, ...] = ("bed", "sofa", "dining-table", "desk")

# 擺位優先族系 = 成組主件 + 大型量體(衣櫃):hints 的第 0 順位,
# 「先放基礎家具,其他物件再依基礎家具擺位」的實作點。
ESSENTIAL_FAMILIES: tuple[str, ...] = (*ANCHOR_FAMILIES, "wardrobe")

# ── 成組副件 ───────────────────────────────────────────────────────────
# 副件 → 可接受主件(族系)。副件只能相對主件擺放:選件時該房沒選主件就
# 不選副件;擺位時主件不在或放不下,副件跟著退場,絕不獨立靠牆。
# 鍵值對齊引擎的成組候選(office-chair→desk、bedside-table→bed、
# coffee-table→sofa、tv-bench→sofa 對牆、dining-chair→繞桌)。
COMPANION_OF: dict[str, tuple[str, ...]] = {
    "bedside-table": ("bed",),
    "coffee-table": ("sofa",),
    "tv-bench": ("sofa",),
    "dining-chair": ("dining-table",),
    "office-chair": ("desk",),
}

# 餐桌成套餐椅:有桌必有椅,絕不會只有一張。桌寬達四人桌就配 4 張。
DINING_CHAIRS_MIN = 2
DINING_CHAIRS_STANDARD = 4
DINING_TABLE_FOUR_SEAT_WIDTH_CM = 140.0


def dining_chair_target(table_width_cm: float | None) -> int:
    """依餐桌寬度決定成套餐椅數:≥140cm 四人桌配 4 張,其餘至少 2 張。"""
    try:
        width = float(table_width_cm or 0)
    except (TypeError, ValueError):
        width = 0.0
    return (
        DINING_CHAIRS_STANDARD
        if width >= DINING_TABLE_FOUR_SEAT_WIDTH_CM
        else DINING_CHAIRS_MIN
    )


# ── 自由座椅 ───────────────────────────────────────────────────────────
# 自由座椅:不靠牆、不成組,擺在「副件之後」撿剩餘空間。它們的泛用候選
# 是房間中央 —— 若照泛用件順位先擺,會搶走沙發正前方的成組位
# (茶几/電視櫃還沒擺就被躺椅卡住,feedback.png 的躺椅擋在沙發前)。
# 不列入 COMPANION_OF:書房閱讀椅可獨立存在,主件缺席不應被移除;
# 但沙發已就位的房間只准沙發左前/右前(引擎層強制)。
FREE_SEATING_FAMILIES: tuple[str, ...] = ("armchair", "lounge-chair")

# ── 房型適配 ───────────────────────────────────────────────────────────
# 族系 → 適用房型;缺項 = 不限(書櫃/邊櫃/衣櫃等泛用件各房皆宜)。
# 房型鍵一律用 canonical taxonomy(見 scene.html 的 <option>,由
# test_space_editor_exposes_only_the_canonical_room_taxonomy 強制):沒有
# dining_room / study,餐廚歸 kitchen、辦公家具歸 bedroom 或 storage
# (與 scene_service.SPACE_DEFAULTS 同步)。desk/office-chair/gaming-chair
# 兩房皆許,平面圖多半有臥室、少有儲藏室,才不會 fallback 回最大區域(客廳)。
# wardrobe 族系刻意不限:cabinets-cupboard / storage-solution-system 也歸
# 此族,廚房、儲藏室、家事間的候選群組都用得到,限臥室會誤殺。
ROOM_AFFINITY: dict[str, tuple[str, ...]] = {
    "bed": ("bedroom",),
    "bedside-table": ("bedroom",),
    "sofa": ("living_room",),
    "tv-bench": ("living_room",),
    "coffee-table": ("living_room",),
    "dining-table": ("kitchen",),
    "dining-chair": ("kitchen",),
    "desk": ("bedroom", "storage"),
    "office-chair": ("bedroom", "storage"),
    # 休閒座椅只進客廳與書房(儲藏);臥室、廚衛、玄關都不選不擺
    # (feedback:扶手椅先被選進廚房、後被放進臥室,都不對)。
    "armchair": ("living_room", "storage"),
    "lounge-chair": ("living_room", "storage"),
}


# 房型「禁用」族系(黑名單)。ROOM_AFFINITY 是白名單、缺項=不限,對刻意不限的
# 族系使不上力:wardrobe 族系(含 cabinets-cupboard、storage-solution-system)為了
# 廚房/儲藏室/家事間的候選而不設限,結果陽台也照收,第 6 步就把收納櫃擺上陽台。
# 把 wardrobe 改成白名單會誤殺那些房型(見上方註記),所以只對特定房型設黑名單。
# 這裡擋的是自動選件與路由;使用者精選(protected_ids)在 select 端已先短路,
# 不受影響 —— 產品承諾不受潛規則否決。
ROOM_FAMILY_DENYLIST: dict[str, tuple[str, ...]] = {
    # 陽台是半戶外空間:收納櫃、衣櫃不自動進來(植栽、休憩椅仍可)。
    "balcony": ("wardrobe", "storage-cabinet"),
}


def affinity_permits(normalized_type: str | None, room_type: str | None) -> bool:
    """該家具是否適合放進此房型(§潛規則房型適配)。

    先看 ``ROOM_FAMILY_DENYLIST``(房型明確禁用),再看 ``ROOM_AFFINITY``;後者
    未列的族系不限房型(泛用件)一律允許 —— 與 select._apply_conventions 同一判準,
    單房選件與多房路由共用。
    """
    family = family_of(normalized_type)
    if family in ROOM_FAMILY_DENYLIST.get(str(room_type or ""), ()):
        return False
    allowed = ROOM_AFFINITY.get(family)
    return not (allowed and room_type and room_type not in allowed)


# ── 戶外家具 ───────────────────────────────────────────────────────────
# 戶外家具記號:Kai 型錄把庭院躺椅/露臺沙發/戶外餐椅歸在 sofa、armchair、
# dining-chair 等室內類型,room_types 也誤標 living_room —— 唯一可靠的訊號是
# 名稱/分類字串。自動選件與換小替補一律排除戶外品;使用者在 /library 明確
# 挑選的不在此限(尊重使用者)。
OUTDOOR_TOKENS: tuple[str, ...] = (
    "戶外", "露臺", "露台", "庭院", "泳池", "outdoor", "patio", "all-weather",
)

# 允許戶外家具的房型(問卷 taxonomy 沒有 outdoor,保留給未來資料)。
OUTDOOR_ROOM_TYPES: tuple[str, ...] = ("balcony", "outdoor")


def is_outdoor_item(item: dict) -> bool:
    """名稱/分類字串含戶外記號即視為戶外家具(型錄類型與 room_types 不可信)。"""
    text = " ".join(
        str(item.get(key) or "")
        for key in (
            "name_en", "name_zh", "name_zh_raw",
            "category_label", "normalized_type", "object_type_zh",
        )
    ).casefold()
    return any(token in text for token in OUTDOOR_TOKENS)


# ── 成組標籤與繁中名 ───────────────────────────────────────────────────
# 族系 → 成組標籤(進 hints 的 group 欄;語意說明用,引擎不據此算座標)。
GROUP_OF: dict[str, str] = {
    "bed": "sleeping",
    "bedside-table": "sleeping",
    "sofa": "seating",
    "coffee-table": "seating",
    "tv-bench": "seating",
    "armchair": "seating",
    "dining-table": "dining",
    "dining-chair": "dining",
    "desk": "work",
    "office-chair": "work",
}

FAMILY_ZH: dict[str, str] = {
    "bed": "床",
    "bedside-table": "床頭櫃",
    "wardrobe": "衣櫃",
    "sofa": "沙發",
    "tv-bench": "電視櫃",
    "coffee-table": "茶几",
    "dining-table": "餐桌",
    "dining-chair": "餐椅",
    "desk": "書桌",
    "office-chair": "辦公椅",
    "bookcase": "書櫃",
    "sideboard": "邊櫃",
    "armchair": "單人椅",
    "wall-shelf": "壁架",
}

ROOM_TYPE_ZH: dict[str, str] = {
    "living_room": "客廳",
    "bedroom": "臥室",
    "dining_room": "餐廳",
    "study": "書房",
    "workspace": "工作區",
    "kitchen": "廚房",
    "entry": "玄關",
    "balcony": "陽台",
    "storage": "儲藏室",
    "laundry": "家事間",
}


def _zh(family: str) -> str:
    return FAMILY_ZH.get(family, family)


def prompt_rules() -> str:
    """由知識庫資料生成選件 prompt 的潛規則條文(資料改、條文跟著改)。"""
    lines = ["擺放潛規則(選件時必須遵守的搭配常識):"]
    essentials = "、".join(
        f"{ROOM_TYPE_ZH.get(room, room)}要有{'與'.join(_zh(f) for f in families)}"
        for room, families in ROOM_ESSENTIALS.items()
    )
    lines.append(f"- 房型基礎家具:{essentials};漏選時系統會自動補上。")
    for family, anchors in COMPANION_OF.items():
        who = "或".join(_zh(anchor) for anchor in anchors)
        lines.append(
            f"- {_zh(family)}必須與{who}成組相鄰擺放;該空間未選{who}就不要選{_zh(family)}。"
        )
    by_rooms: dict[tuple[str, ...], list[str]] = {}
    for family, rooms in ROOM_AFFINITY.items():
        by_rooms.setdefault(rooms, []).append(_zh(family))
    for rooms, families_zh in by_rooms.items():
        rooms_zh = "、".join(ROOM_TYPE_ZH.get(room, room) for room in rooms)
        lines.append(f"- {'、'.join(families_zh)}只適合{rooms_zh},其他空間不要選。")
    lines.append("- 床頭櫃慣例成對(count=2);餐椅依餐桌人數(count=4,小餐廳 count=2),有餐桌就一定要有餐椅。")
    lines.append("- 空間放不下時擺位引擎會自動換小或減量,不需為此少選主件。")
    return "\n".join(lines)
