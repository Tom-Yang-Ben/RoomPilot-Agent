"""知識庫(潛規則單一事實源)referential integrity —— 自 room_pilot2 測試移植。

知識庫是宣告式資料,測試守的是「資料自洽」:副件的主件必須是已知主件
族系、族系語彙對得上引擎、prompt 條文由資料生成(資料改條文跟著改)。
"""
from backend.agent.knowledge import (
    ANCHOR_FAMILIES,
    COMPANION_OF,
    FAMILY_ZH,
    GROUP_OF,
    ROOM_AFFINITY,
    ROOM_TYPE_ZH,
    affinity_permits,
    family_of,
    prompt_rules,
)

# layout_service.DEFAULT_TYPE_GROUPS 的房型鍵 + scene_service SPACE_DEFAULTS 的
# workspace —— 知識庫的房型語彙必須落在這個集合內
_KNOWN_ROOM_TYPES = {
    "living_room", "bedroom", "dining_room", "study", "workspace",
    "kitchen", "entry", "balcony", "storage", "laundry",
}


def test_companion_anchors_are_known_anchor_families():
    for companion, anchors in COMPANION_OF.items():
        assert anchors, f"{companion} 缺主件"
        assert companion not in anchors, f"{companion} 不可自為主件"
        for anchor in anchors:
            assert anchor in ANCHOR_FAMILIES, f"{companion} 的主件 {anchor} 不在 ANCHOR_FAMILIES"
        assert companion not in ANCHOR_FAMILIES, f"副件 {companion} 不可同時是主件"


def test_room_affinity_room_types_are_known():
    for family, rooms in ROOM_AFFINITY.items():
        assert rooms, f"{family} 空房型清單"
        for room_type in rooms:
            assert room_type in _KNOWN_ROOM_TYPES, f"{family} 的房型 {room_type} 未知"


def test_gaming_chair_folds_into_office_chair_family():
    """電競椅循 office-chair 族系:繼承房型適配(臥室/儲藏)與成組(貼書桌),
    不再是無族系的野放件被丟進客廳。"""
    assert family_of("gaming-chair") == "office-chair"


def test_affinity_permits_enforces_canonical_room_rules():
    # 限定房型的家具:房型不符 → 不允許
    assert not affinity_permits("bed", "living_room")
    assert affinity_permits("bed", "bedroom")
    # 辦公家具兩房皆許(臥室 or 儲藏),客廳不許;電競椅循族系同規則
    assert affinity_permits("office-chair", "bedroom")
    assert affinity_permits("office-chair", "storage")
    assert not affinity_permits("office-chair", "living_room")
    assert not affinity_permits("gaming-chair", "living_room")
    assert affinity_permits("gaming-chair", "bedroom")
    # 餐廚歸 kitchen(canonical 無 dining_room)
    assert affinity_permits("dining-table", "kitchen")
    assert not affinity_permits("dining-table", "living_room")
    # 休閒座椅屬起居空間;廚房不選不擺(feedback:扶手椅被選進廚房)
    assert affinity_permits("armchair", "living_room")
    assert affinity_permits("armchair", "bedroom")
    assert not affinity_permits("armchair", "kitchen")
    assert not affinity_permits("lounge-chair", "kitchen")
    # 泛用件(未列 affinity)與空房型一律允許
    assert affinity_permits("bookcase", "living_room")
    assert affinity_permits("bed", "")


def test_family_of_folds_catalog_specific_types():
    assert family_of("fabric-sofa") == "sofa"
    assert family_of("leather-sofa") == "sofa"
    assert family_of("bed-frame") == "bed"
    assert family_of("tv-media-furniture") == "tv-bench"
    assert family_of("shelving-unit") == "bookcase"
    # 未知類型原樣返回(泛用件),None 安全
    assert family_of("bookcase") == "bookcase"
    assert family_of(None) == ""


def test_companion_and_anchor_families_have_zh_names():
    """報錯訊息與 prompt 條文都要有繁中名,缺名會露出英文 id 給使用者。"""
    for family in (*COMPANION_OF, *(a for anchors in COMPANION_OF.values() for a in anchors)):
        assert family in FAMILY_ZH, f"{family} 缺繁中名"
    for room_type_tuple in ROOM_AFFINITY.values():
        for room_type in room_type_tuple:
            assert room_type in ROOM_TYPE_ZH, f"{room_type} 缺繁中名"


def test_group_labels_cover_companion_pairs():
    """副件與其主件必須同組,hints 的 group 語意才成立。"""
    for companion, anchors in COMPANION_OF.items():
        assert companion in GROUP_OF
        assert any(GROUP_OF.get(anchor) == GROUP_OF[companion] for anchor in anchors)


def test_prompt_rules_generated_from_knowledge():
    rules = prompt_rules()
    # 成組條文(逐條由 COMPANION_OF 生成)
    assert "床頭櫃" in rules and "茶几" in rules and "餐椅" in rules
    # 房型適配條文(由 ROOM_AFFINITY 生成)
    assert "臥室" in rules and "客廳" in rules and "餐廳" in rules
    # 慣例條文
    assert "count=2" in rules
