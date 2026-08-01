"""家具擺放規則：Agent 選件與擺位紀律共用的單一事實來源。

兩個消費端共用同一份資料：
- ``select.py`` 透過 ``prompt_rules()`` 將規則加入選件提示，並在解析
  結果時強制執行房型適配與成組依賴。
- ``place.py`` 透過 ``COMPANION_OF`` 安排主件、泛用件、副件的順序，
  並在引擎回報放不下時避免副件脫離主件單獨存在。

房型最少預設與砍件策略的人讀規格見：
``backend/engine/room_strategy/README.md``。本模組是 Agent 執行用的
機器可讀對照；兩者衝突時以 room_strategy 拍板為準並回修此檔。

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
    # 櫃體／收納系統不併入衣櫃族，避免廚房／儲藏選件被臥室親和性誤丟。
    # 抽屜櫃必須自立，不可併成餐邊櫃。
    "storage-solution-system": "shelving-unit",
    "chest-of-drawers": "chests-of-drawer",
    "tv-media-furniture": "tv-bench",
    "table": "dining-table",
    "bar-table": "dining-table",
    "shelving-unit": "shelving-unit",
    # 儲藏室最少件：層架或收納家具擇一即可滿足。
    "storage-furniture": "shelving-unit",
}


def family_of(normalized_type: str | None) -> str:
    """把型錄類型摺疊成擺位族系；未知類型原樣返回。"""
    key = str(normalized_type or "")
    return FAMILY_OF.get(key, key)


# 第 4 步細分房型 → 策略／規則用的正規房型。
ROOM_TYPE_ALIASES: dict[str, str] = {
    "primary_bedroom": "bedroom",
    "secondary_bedroom": "bedroom",
    "entryway": "entry",
    "study": "workspace",
    "circulation": "hallway",
    "flex": "multifunction",
    "foyer": "entry",
    # catalog 的房間碼用 outdoor（236 件），策略房型叫 balcony；缺這條別名
    # 陽台永遠撈到零候選（room_strategy v1「v0→v1 差異」第 1 項）。
    "outdoor": "balcony",
}


def normalize_room_type(room_type: str | None) -> str:
    """把 UI／問卷房型摺成策略規則使用的正規鍵。"""
    key = str(room_type or "").strip()
    return ROOM_TYPE_ALIASES.get(key, key)


# 副件 → 可接受主件。選件時若房內沒有主件就不選副件；擺位時主件
# 不存在或放不下，Agent 自選的副件也必須退場，避免床頭櫃等物件獨活。
COMPANION_OF: dict[str, tuple[str, ...]] = {
    "bedside-table": ("bed",),
    "coffee-table": ("sofa",),
    "tv-bench": ("sofa",),
    "dining-chair": ("dining-table",),
    "office-chair": ("desk",),
}

# 族系 → 適用房型。未列出的視為泛用（仍受成組規則約束）。
ROOM_AFFINITY: dict[str, tuple[str, ...]] = {
    "bed": ("bedroom",),
    "bedside-table": ("bedroom",),
    "wardrobe": ("bedroom",),
    "chests-of-drawer": ("bedroom",),
    "sofa": ("living_room", "multifunction"),
    "tv-bench": ("living_room",),
    "coffee-table": ("living_room",),
    "armchair": ("living_room",),
    "dining-table": ("dining_room",),
    "dining-chair": ("dining_room",),
    "sideboard": ("dining_room",),
    "desk": ("workspace", "bedroom", "multifunction"),
    "office-chair": ("workspace", "bedroom", "multifunction"),
    "shoe-cabinet": ("entry",),
    "shelving-unit": ("storage", "workspace", "balcony"),
}

# 各房「最少自動配置」族系。空 tuple = 該房預設不自動塞家具
# （廚房／浴室／陽台／走道：家電與動線優先，見 room_strategy）。
ROOM_MINIMUM_FAMILIES: dict[str, tuple[str, ...]] = {
    "bedroom": ("bed", "wardrobe", "bedside-table"),
    "living_room": ("sofa", "tv-bench"),
    "dining_room": ("dining-table", "dining-chair"),
    "workspace": ("desk", "office-chair"),
    "entry": ("shoe-cabinet",),
    "storage": ("shelving-unit",),
    "kitchen": (),
    "bathroom": (),
    "balcony": (),
    "hallway": (),
    "multifunction": (),
}


def required_families_for_room(room_type: str | None) -> tuple[str, ...]:
    """回傳該房選件必須齊的族系；未知房型不強制。"""
    return ROOM_MINIMUM_FAMILIES.get(normalize_room_type(room_type), ())


# 成組擺放的主件優先取得牆位，泛用件其次，COMPANION_OF 副件最後。
ANCHOR_FAMILIES: tuple[str, ...] = ("bed", "sofa", "dining-table", "desk", "wardrobe")

# 族系 → 成組語意標籤。此資料只進入提示，不參與座標計算。
GROUP_OF: dict[str, str] = {
    "bed": "sleeping",
    "bedside-table": "sleeping",
    "wardrobe": "sleeping",
    "chests-of-drawer": "sleeping",
    "sofa": "seating",
    "coffee-table": "seating",
    "tv-bench": "seating",
    "armchair": "seating",
    "dining-table": "dining",
    "dining-chair": "dining",
    "sideboard": "dining",
    "desk": "work",
    "office-chair": "work",
    "shoe-cabinet": "entry",
    "shelving-unit": "storage",
}

FAMILY_ZH: dict[str, str] = {
    "bed": "床",
    "bedside-table": "床頭櫃",
    "wardrobe": "衣櫃",
    "chests-of-drawer": "抽屜櫃",
    "sofa": "沙發",
    "tv-bench": "電視櫃",
    "coffee-table": "茶几",
    "dining-table": "餐桌",
    "dining-chair": "餐椅",
    "desk": "書桌",
    "office-chair": "辦公椅",
    "bookcase": "書櫃",
    "sideboard": "餐邊櫃",
    "armchair": "單人椅",
    "wall-shelf": "壁架",
    "shoe-cabinet": "鞋櫃",
    "shelving-unit": "層架／收納",
}

ROOM_TYPE_ZH: dict[str, str] = {
    "living_room": "客廳",
    "bedroom": "臥室",
    "primary_bedroom": "主臥",
    "secondary_bedroom": "次臥",
    "dining_room": "餐廳",
    "study": "書房",
    "workspace": "書房／工作區",
    "kitchen": "廚房",
    "bathroom": "浴室",
    "entry": "玄關",
    "entryway": "玄關",
    "balcony": "陽台",
    "storage": "儲藏室",
    "hallway": "走道／動線",
    "circulation": "走道／動線",
    "multifunction": "多功能室",
    "flex": "多功能室",
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

    lines.append(
        "- 臥室最少：床、衣櫃、床頭櫃。主臥床頭櫃建議成對，同一款以 count=2 表達；"
        "次臥 1 件即可（空間不足時先減到 1）。"
    )
    lines.append("- 客廳最少：沙發、電視櫃；茶几／單椅／書櫃為可選。無獨立電視機。")
    lines.append("- 餐廳最少：餐桌＋餐椅；餐椅人數跟問卷（常見 2／4／6，上限 6）。")
    lines.append("- 書房／工作區最少：書桌＋辦公椅。")
    lines.append("- 玄關最少：鞋櫃。儲藏室最少：層架或收納家具。")
    lines.append("- 廚房、浴室、陽台、走道：不要為了自動配置硬塞家具；家電只留問卷／生圖。")
    lines.append("- 地毯、燈、抱枕等軟裝不要當自動配置必備。")
    lines.append("- 空間放不下時由擺位引擎換小或減量，不由 LLM 硬塞座標。")
    return "\n".join(lines)
