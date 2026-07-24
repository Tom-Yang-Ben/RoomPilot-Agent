"""家具擺放規則：Agent 選件與擺位紀律共用的單一事實來源。

兩個消費端共用同一份資料：
- ``select.py`` 透過 ``prompt_rules()`` 將規則加入選件提示，並在解析
  結果時強制執行房型適配與成組依賴。
- ``place.py`` 透過 ``COMPANION_OF`` 安排主件、泛用件、副件的順序，
  並在引擎回報放不下時避免副件脫離主件單獨存在。

型錄的 ``normalized_type`` 會先經 ``family_of()`` 摺疊成擺位族系。
本模組只放宣告式知識，不放幾何；座標一律由 :mod:`backend.engine` 計算。
"""

from __future__ import annotations


# 型錄具體類型 → 擺位族系。未列出的類型會直接以原類型作為族系，
# 讓 Agent 與 server 的候選型錄保持解耦。
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
}


def family_of(normalized_type: str | None) -> str:
    """把型錄類型摺疊成擺位族系；未知類型原樣返回。"""
    key = str(normalized_type or "")
    return FAMILY_OF.get(key, key)


# 副件 → 可接受主件。選件時若房內沒有主件就不選副件；擺位時主件
# 不存在或放不下，Agent 自選的副件也必須退場，避免床頭櫃等物件獨活。
COMPANION_OF: dict[str, tuple[str, ...]] = {
    "bedside-table": ("bed",),
    "coffee-table": ("sofa",),
    "tv-bench": ("sofa",),
    "dining-chair": ("dining-table",),
    "office-chair": ("desk",),
}

# 族系 → 適用房型。未列出的書櫃、邊櫃、書桌等視為泛用家具。
# wardrobe 刻意不限房型，因為收納系統也可能用在廚房、儲藏室或家事間。
ROOM_AFFINITY: dict[str, tuple[str, ...]] = {
    "bed": ("bedroom",),
    "bedside-table": ("bedroom",),
    "sofa": ("living_room",),
    "tv-bench": ("living_room",),
    "coffee-table": ("living_room",),
    "dining-table": ("dining_room",),
    "dining-chair": ("dining_room",),
}

# 成組擺放的主件優先取得牆位，泛用件其次，COMPANION_OF 副件最後。
ANCHOR_FAMILIES: tuple[str, ...] = ("bed", "sofa", "dining-table", "desk")

# 族系 → 成組語意標籤。此資料只進入提示，不參與座標計算。
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
    "coffee-table": "茶幾",
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
    """從知識表生成 LLM 選件必須遵守的繁中條文。"""
    lines = ["擺放潛規則（選件時必須遵守的搭配常識）："]
    for family, anchors in COMPANION_OF.items():
        anchor_text = "或".join(_zh(anchor) for anchor in anchors)
        lines.append(
            f"- {_zh(family)}必須與{anchor_text}成組相鄰擺放；"
            f"該空間未選{anchor_text}就不要選{_zh(family)}。"
        )
    grouped: dict[tuple[str, ...], list[str]] = {}
    for family, rooms in ROOM_AFFINITY.items():
        grouped.setdefault(rooms, []).append(_zh(family))
    for rooms, families in grouped.items():
        room_text = "、".join(ROOM_TYPE_ZH.get(room, room) for room in rooms)
        lines.append(f"- {'、'.join(families)}只適合{room_text}，其他空間不要選。")
    lines.append("- 床頭櫃慣例成對（count=2）；餐椅依餐桌人數（count=4，小餐廳 count=2）。")
    lines.append("- 空間放不下時由擺位引擎換小或減量，不由 LLM 硬塞座標。")
    return "\n".join(lines)
