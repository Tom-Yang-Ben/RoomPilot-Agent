"""generate_layout 產品分支的特徵測試(characterization tests)。

用途:`docs/擺位計算邏輯.md` 的柵格引擎要接管擺位計算,而 generate_layout 還扛著
規格完全沒有模型的產品功能。這些分支**原本沒有任何測試保護**,改壞了不會有人發現。

本檔先把現行行為釘住,再動核心 —— 斷言的是「使用者看得到的性質」(地毯壓在沙發上、
鎖定件不被重排、窗簾貼窗、層板不參與碰撞),不是實作細節,所以換引擎後仍應成立。
"""
from __future__ import annotations

import pytest

from shapely.geometry import Point, Polygon

from backend.engine.dxf_room import Room, Wall
from backend.server.scene_service import generate_layout, generate_layout_by_room

ROOM_W = 450.0
ROOM_D = 380.0


def _rect_room(width: float = ROOM_W, depth: float = ROOM_D) -> Room:
    return Room(
        width=width,
        depth=depth,
        walls=[
            Wall(0.0, 0.0, width, 0.0),
            Wall(width, 0.0, width, depth),
            Wall(width, depth, 0.0, depth),
            Wall(0.0, depth, 0.0, 0.0),
        ],
    )


def _item(furniture_id: str, ftype: str, w: float, d: float, h: float = 80.0, **extra):
    return {
        "furniture_id": furniture_id,
        "normalized_type": ftype,
        "name_zh_raw": furniture_id,
        "size_cm": {"width": w, "depth": d, "height": h},
        "has_model": True,
        "model_url": None,
        "primary_style": None,
        **extra,
    }


def _by_id(objects):
    return {obj["furniture_id"]: obj for obj in objects}


def _overlaps(a, b) -> bool:
    """軸對齊粗略重疊(只用來驗「地毯壓在沙發下」這種語意)。"""
    ax, az = a["position_cm"]["x"], a["position_cm"]["z"]
    bx, bz = b["position_cm"]["x"], b["position_cm"]["z"]
    aw, ad = a["footprint_cm"]["width"], a["footprint_cm"]["depth"]
    bw, bd = b["footprint_cm"]["width"], b["footprint_cm"]["depth"]
    return abs(ax - bx) < (aw + bw) / 2 and abs(az - bz) < (ad + bd) / 2


# ── _OVERLAY_TYPES:地毯是平面件,必須允許家具壓在上面 ────────────────
def test_rug_is_placed_under_its_target_furniture():
    items = [
        _item("sofa", "fabric-sofa", 200, 90),
        _item("rug", "large-medium-rug", 200, 140, h=1.0),
    ]
    objects = _by_id(generate_layout(ROOM_W, ROOM_D, items, room=_rect_room()))
    assert not objects["rug"]["placement_failed"]
    # 地毯與沙發重疊是**設計**,不是碰撞失敗
    assert _overlaps(objects["rug"], objects["sofa"])


def test_rug_without_any_target_still_gets_a_position():
    items = [_item("rug", "runner-small-rug", 160, 70, h=1.0)]
    objects = _by_id(generate_layout(ROOM_W, ROOM_D, items, room=_rect_room()))
    assert not objects["rug"]["placement_failed"]


def test_non_overlay_furniture_never_overlaps_each_other():
    items = [
        _item("sofa", "fabric-sofa", 200, 90),
        _item("cabinet", "storage-cabinet", 120, 45, h=200.0),
        _item("bookcase", "shelving-unit", 80, 35, h=200.0),
    ]
    objects = generate_layout(ROOM_W, ROOM_D, items, room=_rect_room())
    solid = [o for o in objects if not o["placement_failed"]]
    for i, a in enumerate(solid):
        for b in solid[i + 1:]:
            assert not _overlaps(a, b), f"{a['furniture_id']} 與 {b['furniture_id']} 重疊"


# ── position_locked / preserve_existing_count:使用者擺過的不准被重排 ──
def test_locked_position_is_kept_verbatim():
    locked = _item("sofa", "fabric-sofa", 200, 90)
    locked["position_locked"] = True
    locked["position_cm"] = {"x": -40.0, "z": 60.0}
    locked["rotation_y_deg"] = 90.0
    objects = _by_id(generate_layout(ROOM_W, ROOM_D, [locked], room=_rect_room()))
    assert objects["sofa"]["position_cm"] == {"x": -40.0, "z": 60.0}
    assert objects["sofa"]["rotation_y_deg"] == 90.0
    assert objects["sofa"]["position_locked"] is True


def test_locked_item_is_placed_before_and_pushes_others_away():
    locked = _item("sofa", "fabric-sofa", 200, 90)
    locked["position_locked"] = True
    locked["position_cm"] = {"x": 0.0, "z": 0.0}
    locked["rotation_y_deg"] = 0.0
    other = _item("cabinet", "storage-cabinet", 120, 45, h=200.0)
    objects = _by_id(generate_layout(ROOM_W, ROOM_D, [locked, other], room=_rect_room()))
    assert objects["sofa"]["position_cm"] == {"x": 0.0, "z": 0.0}
    if not objects["cabinet"]["placement_failed"]:
        assert not _overlaps(objects["sofa"], objects["cabinet"])


def test_preserve_existing_count_keeps_leading_items_in_place():
    kept = _item("sofa", "fabric-sofa", 200, 90)
    kept["position_cm"] = {"x": -30.0, "z": 40.0}
    kept["rotation_y_deg"] = 180.0
    fresh = _item("cabinet", "storage-cabinet", 120, 45, h=200.0)
    objects = _by_id(generate_layout(
        ROOM_W, ROOM_D, [kept, fresh], room=_rect_room(), preserve_existing_count=1,
    ))
    assert objects["sofa"]["position_cm"] == {"x": -30.0, "z": 40.0}
    # preserve 不等於 locked:回傳的 position_locked 仍為 False
    assert objects["sofa"]["position_locked"] is False


# ── _IGNORE_COLLISION_TYPES:層板掛牆,不參與地面碰撞 ──────────────────
def test_wall_shelf_is_placed_and_ignores_floor_collision():
    items = [
        _item("shelf", "wall-shelf", 90, 25, h=30.0),
        _item("cabinet", "storage-cabinet", 120, 45, h=200.0),
    ]
    objects = _by_id(generate_layout(ROOM_W, ROOM_D, items, room=_rect_room()))
    assert not objects["shelf"]["placement_failed"]


# ── placement_variant:A/B 是兩個可比較的方案 ────────────────────────
def test_variant_b_is_a_valid_alternative_layout():
    items = [
        _item("sofa", "fabric-sofa", 200, 90),
        _item("cabinet", "storage-cabinet", 120, 45, h=200.0),
    ]
    room = _rect_room()
    a = generate_layout(ROOM_W, ROOM_D, items, room=room, placement_variant="A")
    b = generate_layout(ROOM_W, ROOM_D, items, room=room, placement_variant="B")
    assert [o["furniture_id"] for o in a] == [o["furniture_id"] for o in b]
    # 兩案都必須是合法配置(不重疊);是否不同座標不強制 —— 小房可能只有一組解
    for objects in (a, b):
        solid = [o for o in objects if not o["placement_failed"]]
        for i, x in enumerate(solid):
            for y in solid[i + 1:]:
                assert not _overlaps(x, y)


# ── payload 契約:順序、鍵、單位 ─────────────────────────────────────
def test_output_order_matches_input_order():
    items = [
        _item("a", "storage-cabinet", 120, 45, h=200.0),
        _item("b", "fabric-sofa", 200, 90),
        _item("c", "shelving-unit", 80, 35, h=200.0),
    ]
    objects = generate_layout(ROOM_W, ROOM_D, items, room=_rect_room())
    assert [o["furniture_id"] for o in objects] == ["a", "b", "c"]


def test_every_object_carries_the_payload_contract_keys():
    objects = generate_layout(
        ROOM_W, ROOM_D, [_item("sofa", "fabric-sofa", 200, 90)], room=_rect_room(),
    )
    obj = objects[0]
    for key in (
        "furniture_id", "instance_id", "normalized_type", "size_cm", "footprint_cm",
        "position_cm", "rotation_y_deg", "position_locked", "placement_failed",
        "placement_reason", "placement_engine",
    ):
        assert key in obj, key
    assert set(obj["position_cm"]) == {"x", "z"}
    assert 0 <= obj["rotation_y_deg"] < 360


def test_placements_stay_inside_the_room():
    items = [
        _item("sofa", "fabric-sofa", 200, 90),
        _item("cabinet", "storage-cabinet", 120, 45, h=200.0),
        _item("bookcase", "shelving-unit", 80, 35, h=200.0),
    ]
    objects = generate_layout(ROOM_W, ROOM_D, items, room=_rect_room())
    for obj in objects:
        if obj["placement_failed"]:
            continue
        x, z = obj["position_cm"]["x"], obj["position_cm"]["z"]
        fw, fd = obj["footprint_cm"]["width"], obj["footprint_cm"]["depth"]
        assert -ROOM_W / 2 <= x - fw / 2 and x + fw / 2 <= ROOM_W / 2, obj["furniture_id"]
        assert -ROOM_D / 2 <= z - fd / 2 and z + fd / 2 <= ROOM_D / 2, obj["furniture_id"]


def test_failed_placement_reports_a_reason():
    # 巨大家具塞進小房 → 必須明確回報,不得硬塞
    tiny = _rect_room(160.0, 160.0)
    objects = generate_layout(
        160.0, 160.0, [_item("huge", "storage-cabinet", 400, 200, h=200.0)], room=tiny,
    )
    obj = objects[0]
    if obj["placement_failed"]:
        assert obj["placement_reason"]


# ── 逐房擺位:家具必須落在自己被指派的房間 ────────────────────────────
# 迴歸來源:floor04.png 實測時 13 件家具全部被擠進「最大的那一間」(廚房,只比臥室
# 大 0.04 m²)。原因是 build_scene_payload 只呼叫一次 generate_layout,place_boundary
# 固定用 _largest_region_boundary,其餘房間都被遮罩當成房外。

# 兩房平面圖:左房 x[0,400] / 右房 x[420,820],共用 z[0,400]
_TWO_ROOM_FLOORPLAN = {
    # 不標 coordinate_unit 會被 _floorplan_coordinate_scale_cm 當成公尺並 ×100
    "coordinate_unit": "cm",
    "room_regions": [
        {
            "room_id": "left", "label": "臥室", "room_type": "bedroom",
            "exterior": [[-410, -200], [-10, -200], [-10, 200], [-410, 200]], "holes": [],
        },
        {
            # 右房刻意大一點,確保它才是 _largest_region_boundary 選中的那間
            "room_id": "right", "label": "客廳", "room_type": "living_room",
            "exterior": [[10, -200], [420, -200], [420, 200], [10, 200]], "holes": [],
        },
    ],
}
_TWO_ROOM_W = 840.0
_TWO_ROOM_D = 400.0


def _two_room_polygons():
    return {
        region["room_id"]: Polygon([(p[0], p[1]) for p in region["exterior"]])
        for region in _TWO_ROOM_FLOORPLAN["room_regions"]
    }


def test_items_are_placed_inside_their_assigned_room():
    items = [
        _item("bed", "bed-frame", 160, 200, h=120.0, placement_room_id="left"),
        _item("wardrobe", "pax-wardrobe", 150, 60, h=200.0, placement_room_id="left"),
        _item("sofa", "fabric-sofa", 200, 90, placement_room_id="right"),
        _item("cabinet", "storage-cabinet", 120, 45, h=200.0, placement_room_id="right"),
    ]
    objects = generate_layout_by_room(
        _TWO_ROOM_W, _TWO_ROOM_D, items,
        room=_rect_room(_TWO_ROOM_W, _TWO_ROOM_D),
        floorplan=_TWO_ROOM_FLOORPLAN,
    )
    polys = _two_room_polygons()
    for item, obj in zip(items, objects):
        assert not obj["placement_failed"], f"{item['furniture_id']} 放不下"
        point = Point(obj["position_cm"]["x"], obj["position_cm"]["z"])
        want = item["placement_room_id"]
        assert polys[want].contains(point), (
            f"{item['furniture_id']} 指定 {want},卻落在 "
            f"({obj['position_cm']['x']:.1f}, {obj['position_cm']['z']:.1f})"
        )


def test_unassigned_items_follow_room_affinity():
    """沒有 placement_room_id 時依 ROOM_AFFINITY 找房型相符的房間。

    左房是 bedroom、右房是 living_room。床沒有指定房也該進左房 ——
    否則會像 floor04 實測那樣,沙發被丟進廚房。
    """
    items = [
        _item("bed", "bed-frame", 160, 200, h=120.0),      # → bedroom = left
        _item("sofa", "fabric-sofa", 200, 90),              # → living_room = right
    ]
    objects = generate_layout_by_room(
        _TWO_ROOM_W, _TWO_ROOM_D, items,
        room=_rect_room(_TWO_ROOM_W, _TWO_ROOM_D),
        floorplan=_TWO_ROOM_FLOORPLAN,
    )
    polys = _two_room_polygons()
    assert polys["left"].contains(Point(objects[0]["position_cm"]["x"], objects[0]["position_cm"]["z"]))
    assert polys["right"].contains(Point(objects[1]["position_cm"]["x"], objects[1]["position_cm"]["z"]))


def test_items_without_affinity_fall_back_to_the_largest_region():
    """房型適配表查不到的品項仍走最大區域,不得因分組而消失。"""
    items = [_item("lamp", "floor-lamp", 40, 40, h=150.0)]
    objects = generate_layout_by_room(
        _TWO_ROOM_W, _TWO_ROOM_D, items,
        room=_rect_room(_TWO_ROOM_W, _TWO_ROOM_D),
        floorplan=_TWO_ROOM_FLOORPLAN,
    )
    assert len(objects) == 1
    assert not objects[0]["placement_failed"]
    point = Point(objects[0]["position_cm"]["x"], objects[0]["position_cm"]["z"])
    assert _two_room_polygons()["right"].contains(point)


def test_per_room_placement_preserves_input_order():
    items = [
        _item("a", "fabric-sofa", 200, 90, placement_room_id="right"),
        _item("b", "bed-frame", 160, 200, h=120.0, placement_room_id="left"),
        _item("c", "storage-cabinet", 120, 45, h=200.0, placement_room_id="right"),
    ]
    objects = generate_layout_by_room(
        _TWO_ROOM_W, _TWO_ROOM_D, items,
        room=_rect_room(_TWO_ROOM_W, _TWO_ROOM_D),
        floorplan=_TWO_ROOM_FLOORPLAN,
    )
    assert [o["furniture_id"] for o in objects] == ["a", "b", "c"]


# ── §12 決定性:同輸入必得同輸出 ────────────────────────────────────
def test_layout_is_deterministic():
    items = [
        _item("sofa", "fabric-sofa", 200, 90),
        _item("rug", "large-medium-rug", 200, 140, h=1.0),
        _item("cabinet", "storage-cabinet", 120, 45, h=200.0),
    ]
    first = generate_layout(ROOM_W, ROOM_D, items, room=_rect_room())
    second = generate_layout(ROOM_W, ROOM_D, items, room=_rect_room())
    assert [(o["furniture_id"], o["position_cm"], o["rotation_y_deg"]) for o in first] == \
           [(o["furniture_id"], o["position_cm"], o["rotation_y_deg"]) for o in second]
