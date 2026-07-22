"""家具選件與配置的宣告式領域知識。"""

from __future__ import annotations


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
    """把型錄類型摺疊成引擎擺位族系。"""
    key = str(normalized_type or "")
    return FAMILY_OF.get(key, key)


COMPANION_OF: dict[str, tuple[str, ...]] = {
    "bedside-table": ("bed",),
    "coffee-table": ("sofa",),
    "tv-bench": ("sofa",),
    "dining-chair": ("dining-table",),
    "office-chair": ("desk",),
}

ROOM_AFFINITY: dict[str, tuple[str, ...]] = {
    "bed": ("bedroom",),
    "bedside-table": ("bedroom",),
    "sofa": ("living_room",),
    "tv-bench": ("living_room",),
    "coffee-table": ("living_room",),
    "dining-table": ("dining_room",),
    "dining-chair": ("dining_room",),
}

ANCHOR_FAMILIES: tuple[str, ...] = ("bed", "sofa", "dining-table", "desk")

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
