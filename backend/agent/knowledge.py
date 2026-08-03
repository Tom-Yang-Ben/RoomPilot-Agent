"""家具擺放潛規則 —— agent 的領域知識單一事實源(自 room_pilot2 移植)。

兩個消費端,同一份資料:
- select.py 以 prompt_rules() 把潛規則注入選件 prompt,並在 parse_selections
  於系統邊界強制執行(房型適配 → 成組依賴)。
- place.py 依 COMPANION_OF 排出「主件先、泛用次、副件最後」的擺放優先序,
  並在引擎回報放不下時執行寧缺勿亂:副件絕不脫離主件獨活,這正是
  「床頭櫃不在床旁邊」的根治點。

語彙與現行引擎一致:型錄 normalized_type 先經 family_of() 摺疊成擺位
「族系」(同 scene_service._placement_candidates 的成組語意)。本模組只放
宣告式知識,不放幾何 —— 座標一律由 backend.engine 計算。
"""
from __future__ import annotations

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


# 副件 → 可接受主件(族系)。副件只能相對主件擺放:選件時該房沒選主件就
# 不選副件;擺位時主件不在或放不下,副件跟著退場,絕不獨立靠牆。
# 鍵值對齊引擎的成組候選(office-chair→desk、bedside-table→bed、
# coffee-table→sofa、tv-bench→sofa 對牆)。
COMPANION_OF: dict[str, tuple[str, ...]] = {
    "bedside-table": ("bed",),
    "coffee-table": ("sofa",),
    "tv-bench": ("sofa",),
    "dining-chair": ("dining-table",),
    "office-chair": ("desk",),
}

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
}


def affinity_permits(normalized_type: str | None, room_type: str | None) -> bool:
    """該家具是否適合放進此房型(§潛規則房型適配)。

    ``ROOM_AFFINITY`` 未列的族系不限房型(泛用件)一律允許 —— 與
    select._apply_conventions 的 short-circuit 同一判準,單房選件與多房路由共用。
    """
    allowed = ROOM_AFFINITY.get(family_of(normalized_type))
    return not (allowed and room_type and room_type not in allowed)

# 擺位主件(成組的錨):最先卡好牆位,泛用件次之,副件(COMPANION_OF)最後
# 擺 —— 引擎的成組候選要有「已就位的主件」才貼得上去。
ANCHOR_FAMILIES: tuple[str, ...] = ("bed", "sofa", "dining-table", "desk")

# 自由座椅:不靠牆、不成組,擺在「副件之後」撿剩餘空間。它們的泛用候選
# 是房間中央 —— 若照泛用件順位先擺,會搶走沙發正前方的成組位
# (茶几/電視櫃還沒擺就被躺椅卡住,feedback.png 的躺椅擋在沙發前)。
# 不列入 COMPANION_OF:躺椅可獨立存在(臥室閱讀椅),主件缺席不應被移除。
FREE_SEATING_FAMILIES: tuple[str, ...] = ("armchair", "lounge-chair")

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
    lines.append("- 床頭櫃慣例成對(count=2);餐椅依餐桌人數(count=4,小餐廳 count=2)。")
    lines.append("- 空間放不下時擺位引擎會自動換小或減量,不需為此少選主件。")
    return "\n".join(lines)
