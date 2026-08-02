"""隨機配套池（2026-08-02 Ancai 拍板）：預設最少＋隨機配套、達到設計效果。

規格：每房 5 槽——必備族系各佔一槽（床頭櫃×2 屬同一族系槽）、配套「單元」
佔一槽（桌椅組＝1 槽 2 件）；AI 配置在必備外隨機抽單元補滿，同一單元可跨
房型（電競桌椅：臥室與客廳都合理）；型錄無貨的單元不得進抽。
"""

import random

import pytest

from backend.agent.knowledge import (
    ADDON_UNITS,
    ROOM_ADDON_POOLS,
    ROOM_SLOT_LIMIT,
    addon_units_for_room,
    family_of,
    required_families_for_room,
)
from backend.server.main import _addon_offers, _addon_seed_item

FAKE_CATALOG = [
    {"furniture_id": "d-gaming", "normalized_type": "desk", "name_en": "AmazonBasics Gaming Desk", "model_url": "u"},
    {"furniture_id": "d-plain", "normalized_type": "desk", "name_en": "Plain Writing Desk", "model_url": "u"},
    {"furniture_id": "c-gaming", "normalized_type": "office-chair", "name_zh": "電競椅 Movian", "model_url": "u"},
    {"furniture_id": "c-plain", "normalized_type": "office-chair", "name_en": "Task Chair", "model_url": "u"},
    {"furniture_id": "bk-1", "normalized_type": "bookcase", "name_en": "Billy", "model_url": "u"},
    {"furniture_id": "ch-1", "normalized_type": "chests-of-drawer", "name_en": "Malm", "model_url": "u"},
    {"furniture_id": "ar-1", "normalized_type": "armchair", "name_en": "Rocksjon", "model_url": "u"},
    {"furniture_id": "dp-1", "normalized_type": "display-cabinet", "name_en": "Detolf", "model_url": "u"},
    {"furniture_id": "sh-1", "normalized_type": "shelving-unit", "name_en": "PS2026", "model_url": "u"},
]

KNOWN_CATALOG_EMPTY = {"appliance-cabinet", "storage-cabinet", "bathroom-vanity", "cabinets-cupboard"}


def test_addon_pool_is_wellformed_and_free_of_dead_keys():
    for key, unit in ADDON_UNITS.items():
        assert unit["families"], key
        for fam in unit["families"]:
            assert family_of(fam) == fam, f"{key}: {fam} 不是正規族系鍵"
            assert fam not in KNOWN_CATALOG_EMPTY, f"{key}: {fam} 是型錄 0 件死鍵"
    for room_type, keys in ROOM_ADDON_POOLS.items():
        for key in keys:
            assert key in ADDON_UNITS, f"{room_type} 池引用未定義單元 {key}"
        # 池單元不得與該房必備重複（必備已固定佔槽）
        required = set(required_families_for_room(room_type))
        for key in keys:
            assert not (set(ADDON_UNITS[key]["families"]) & required), (room_type, key)


def test_addon_pool_families_are_affine_to_their_rooms():
    """池說可進、ROOM_AFFINITY 說不行＝抽中也會被選件驗證踢掉（白佔槽）。
    兩張表必須一致——實測第一版客廳抽中層架／桌椅組全被親和表擋下。"""
    from backend.agent.knowledge import ROOM_AFFINITY

    for room_type, keys in ROOM_ADDON_POOLS.items():
        for key in keys:
            for fam in ADDON_UNITS[key]["families"]:
                allowed = ROOM_AFFINITY.get(fam)
                assert allowed is None or room_type in allowed, (
                    f"{room_type} 池單元 {key} 的 {fam} 被 ROOM_AFFINITY 擋在門外"
                )


def test_desk_set_is_shared_by_bedroom_and_living_room():
    # Ancai 拍板原文：電競桌椅可以出現在房間（臥室），也可以出現在客廳。
    assert "desk-set" in ROOM_ADDON_POOLS["bedroom"]
    assert "desk-set" in ROOM_ADDON_POOLS["living_room"]
    assert "gaming" in (ADDON_UNITS["desk-set"].get("flavors") or ())


def test_addon_offers_fills_up_to_slot_limit_without_touching_required():
    rooms = [{"room_id": "r1", "room_type": "bedroom"}]
    offers, picks = _addon_offers(rooms, {}, rng=random.Random(42), catalog=FAKE_CATALOG)
    required = set(required_families_for_room("bedroom"))
    free = ROOM_SLOT_LIMIT - len(required)  # bedroom 必備 3 槽 → 配套至多 2 單元
    my_picks = [p for p in picks if p["room_id"] == "r1"]
    assert 1 <= len(my_picks) <= free
    seeded_families = {family_of(o["normalized_type"]) for o in offers.get("r1", [])}
    assert not (seeded_families & required)
    pool_families = {f for u in addon_units_for_room("bedroom") for f in u["families"]}
    assert seeded_families <= pool_families


def test_addon_offers_respects_existing_offer_slots():
    rooms = [{"room_id": "r1", "room_type": "bedroom"}]
    # 既有 offers 已佔掉兩個非必備族系槽（必備 3＋2＝5，滿）→ 不再抽。
    pre = {"r1": [
        {"furniture_id": "bk-1", "normalized_type": "bookcase", "variant_id": "standard"},
        {"furniture_id": "ar-1", "normalized_type": "armchair", "variant_id": "standard"},
    ]}
    offers, picks = _addon_offers(rooms, pre, rng=random.Random(1), catalog=FAKE_CATALOG)
    assert [p for p in picks if p["room_id"] == "r1"] == []
    assert len(offers["r1"]) == 2


def test_addon_sampling_varies_with_rng():
    rooms = [{"room_id": "r1", "room_type": "living_room"}]
    outcomes = set()
    for seed in range(12):
        _, picks = _addon_offers(rooms, {}, rng=random.Random(seed), catalog=FAKE_CATALOG)
        outcomes.add(tuple(sorted(p["unit"] for p in picks)))
    assert len(outcomes) >= 2, "隨機抽樣應該產生不同組合（設計變化）"


def test_gaming_flavor_prefers_gaming_items():
    pool = [i for i in FAKE_CATALOG if i["normalized_type"] == "desk"]
    for _ in range(8):
        item = _addon_seed_item(pool, "gaming", random.Random(7))
        assert item["furniture_id"] == "d-gaming"
    chairs = [i for i in FAKE_CATALOG if i["normalized_type"] == "office-chair"]
    assert _addon_seed_item(chairs, "gaming", random.Random(7))["furniture_id"] == "c-gaming"
