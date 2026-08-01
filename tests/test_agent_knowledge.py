"""Agent 家具知識的公開契約測試。"""

from backend.agent.knowledge import (
    ANCHOR_FAMILIES,
    COMPANION_OF,
    FAMILY_ZH,
    GROUP_OF,
    ROOM_AFFINITY,
    ROOM_TYPE_ZH,
    family_of,
    prompt_rules,
)


KNOWN_ROOM_TYPES = {
    "living_room",
    "bedroom",
    "dining_room",
    "study",
    "workspace",
    "kitchen",
    "entry",
    "balcony",
    "storage",
    "laundry",
    "multifunction",  # v1 十二房型之一（2026-07-31 定版）
}


def test_catalog_types_fold_to_placement_families() -> None:
    assert family_of("fabric-sofa") == "sofa"
    assert family_of("leather-sofa") == "sofa"
    assert family_of("bed-frame") == "bed"
    assert family_of("tv-media-furniture") == "tv-bench"
    # 2026-07 拍板：層架自成族系（儲藏室最少件），不再併入書櫃——
    # 併了會讓儲藏／書房選件被臥室親和性誤丟。收納系統與泛用收納摺進層架。
    assert family_of("shelving-unit") == "shelving-unit"
    assert family_of("storage-solution-system") == "shelving-unit"
    assert family_of("storage-furniture") == "shelving-unit"
    assert family_of("bookcase") == "bookcase"
    assert family_of(None) == ""


def test_companion_rules_reference_known_anchors_and_groups() -> None:
    for companion, anchors in COMPANION_OF.items():
        assert anchors
        assert companion not in anchors
        assert companion not in ANCHOR_FAMILIES
        assert companion in GROUP_OF
        for anchor in anchors:
            assert anchor in ANCHOR_FAMILIES
            assert anchor in FAMILY_ZH
        assert any(GROUP_OF.get(anchor) == GROUP_OF[companion] for anchor in anchors)


def test_room_affinity_uses_known_localized_room_types() -> None:
    for rooms in ROOM_AFFINITY.values():
        assert rooms
        for room_type in rooms:
            assert room_type in KNOWN_ROOM_TYPES
            assert room_type in ROOM_TYPE_ZH


def test_prompt_rules_are_generated_in_traditional_chinese() -> None:
    rules = prompt_rules()
    assert "床頭櫃" in rules
    assert "茶几" in rules
    assert "餐椅" in rules
    assert "臥室" in rules
    assert "客廳" in rules
    assert "餐廳" in rules
    assert "count=2" in rules


def test_outdoor_alias_maps_catalog_rooms_to_balcony() -> None:
    """catalog 房間碼是 outdoor（236 件）；缺此別名陽台永遠零候選（v1 第 1 項）。"""
    from backend.agent.knowledge import normalize_room_type

    assert normalize_room_type("outdoor") == "balcony"
