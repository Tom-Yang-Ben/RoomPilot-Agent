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


def test_validate_only_keeps_positions_and_never_collapses():
    """最終確認(進入即時寫實):validate_only 一律照舊座標、絕不重排。合法件回報
    合法;越界件回報失敗但位置**仍照舊,不塌成 (0,0)**(原本重排把合法配置塌到
    原點疊一起、又卡住進不了下一步,正是此測要守的回歸)。"""
    legal = _item("sofa", "fabric-sofa", 200, 90)
    legal["position_cm"] = {"x": 0.0, "z": 0.0}
    legal["rotation_y_deg"] = 0.0
    outside = _item("desk", "desk", 120, 60)
    outside["position_cm"] = {"x": 9000.0, "z": 9000.0}
    outside["rotation_y_deg"] = 0.0
    objects = _by_id(generate_layout(
        ROOM_W, ROOM_D, [legal, outside], room=_rect_room(), validate_only=True,
    ))
    assert objects["sofa"]["position_cm"] == {"x": 0.0, "z": 0.0}
    assert objects["sofa"]["placement_failed"] is False
    assert objects["desk"]["placement_failed"] is True
    assert objects["desk"]["position_cm"] == {"x": 9000.0, "z": 9000.0}


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


# ── 靠牆錨定掃描:門前動線壓掉類型錨點時,靠牆家具仍須貼牆 ────────────
# 迴歸來源:floor04.png 客廳,門前 75cm 動線帶恰好蓋住沙發/電視櫃在該面牆的
# 2-3 個固定錨點,家具全數落到 3×3 網格散點(房間中央)。

_DOOR_BLOCK_FLOORPLAN = {
    "coordinate_unit": "cm",
    "room_regions": [{
        "room_id": "living",
        "room_type": "living_room",
        "exterior": [[-225, -190], [225, -190], [225, 190], [-225, 190]],
        "holes": [],
    }],
    # 下牆中央的門:75cm 動線帶涵蓋沙發在下牆的兩個類型錨點
    "door_segments": [
        {"start": {"x": -60, "z": 190}, "end": {"x": 60, "z": 190}},
    ],
}


def _nearest_wall_gap(obj, exterior):
    xs = [p[0] for p in exterior]
    zs = [p[1] for p in exterior]
    x, z = obj["position_cm"]["x"], obj["position_cm"]["z"]
    fw, fd = obj["footprint_cm"]["width"], obj["footprint_cm"]["depth"]
    return min(
        (x - fw / 2) - min(xs),
        max(xs) - (x + fw / 2),
        (z - fd / 2) - min(zs),
        max(zs) - (z + fd / 2),
    )


def test_wall_anchored_furniture_scans_other_walls_when_door_band_blocks_anchors():
    items = [_item("sofa", "sofa", 200, 90, placement_room_id="living")]
    objects = generate_layout_by_room(
        450.0, 380.0, items,
        room=_rect_room(450.0, 380.0),
        floorplan=_DOOR_BLOCK_FLOORPLAN,
    )
    obj = objects[0]
    assert not obj["placement_failed"]
    # 貼牆:最近一面牆的縫 ≤ 15cm(邊界內縮 8cm + 柵格量化);
    # 若退化回網格散點,離最近牆至少 90cm,此斷言必炸
    gap = _nearest_wall_gap(obj, _DOOR_BLOCK_FLOORPLAN["room_regions"][0]["exterior"])
    assert gap <= 15, f"沙發離最近牆 {gap:.1f}cm,未貼牆"
    # 朝向:軸對齊且正面朝房內(rot=0 面向 +z)
    assert obj["rotation_y_deg"] in {0.0, 90.0, 180.0, 270.0}


def test_sofa_may_back_onto_the_window_wall():
    """沙發族系豁免窗前採光帶(feedback 9/10):沙發背窗是常見客廳格局,
    被帶擋出窗牆會讓電視櫃的成組候選落到陽台門那側。高背沙發(≥90cm)
    也要能貼窗牆;其他高家具仍受帶約束。"""
    window_floorplan = {
        "coordinate_unit": "cm",
        "room_regions": [{
            "room_id": "living",
            "room_type": "living_room",
            "exterior": [[-225, -190], [225, -190], [225, 190], [-225, 190]],
            "holes": [],
        }],
        # 下牆中央的窗:40cm 採光帶涵蓋沙發在下牆的類型錨點
        "window_segments": [
            {"start": {"x": -80, "z": 190}, "end": {"x": 80, "z": 190}},
        ],
    }
    # 2D 流程送通用型 "sofa"(scene_layout2d.toSceneFurniture);候選表以它為鍵
    items = [_item("sofa", "sofa", 200, 90, h=96.0, placement_room_id="living")]
    objects = generate_layout_by_room(
        450.0, 380.0, items,
        room=_rect_room(450.0, 380.0),
        floorplan=window_floorplan,
    )
    obj = objects[0]
    assert not obj["placement_failed"]
    # 貼下牆(窗牆):背面貼齊內縮邊界、面向房內
    assert obj["rotation_y_deg"] == 180
    assert obj["position_cm"]["z"] > 100, f"沙發未靠窗牆,z={obj['position_cm']['z']}"


_BALCONY_OPENING_FLOORPLAN = {
    "coordinate_unit": "cm",
    "width_cm": 450.0,
    "depth_cm": 380.0,
    "room_regions": [{
        "room_id": "living",
        "room_type": "living_room",
        "exterior": [[-225, -190], [225, -190], [225, 190], [-225, 190]],
        "holes": [],
    }],
    # 下牆偏左的落地窗 = 陽台出入口(75cm 通行縫,矮家具與沙發都不得擋)
    "window_segments": [
        {
            "start": {"x": -160, "z": 190},
            "end": {"x": -70, "z": 190},
            "window_type": "floor_to_ceiling",
        },
    ],
}


def test_sofa_slides_sideways_past_the_balcony_opening():
    """沙發壓到陽台落地窗時要「往旁邊移一點,盡量在正前方」:同一面牆
    由中心向外滑位讓開通行縫,而不是跳到別的牆或擋住出入口。"""
    items = [_item("sofa", "sofa", 200, 90, h=96.0, placement_room_id="living")]
    objects = generate_layout_by_room(
        450.0, 380.0, items,
        room=_rect_room(450.0, 380.0),
        floorplan=_BALCONY_OPENING_FLOORPLAN,
    )
    obj = objects[0]
    assert not obj["placement_failed"]
    assert obj["rotation_y_deg"] == 180          # 仍在下牆、面向房內
    assert obj["position_cm"]["z"] > 100
    # 讓開出入口:左緣須越過通行縫右界(開口右端 -70 + 75cm 縫 = 5)
    left_edge = obj["position_cm"]["x"] - obj["footprint_cm"]["width"] / 2
    assert left_edge >= 4, f"沙發左緣 {left_edge:.0f} 仍壓住陽台出入縫"


def test_low_furniture_cannot_block_the_balcony_opening_either():
    """電視櫃這類矮家具過去只受 40cm 採光帶(高度未達窗台就豁免);
    落地窗是動線,矮家具也不得擋(feedback:10 號電視櫃擋住陽台門)。"""
    opening = {
        "start": {"x": -60, "z": -190},
        "end": {"x": 60, "z": -190},
        "window_type": "floor_to_ceiling",
    }
    floorplan = {
        **_BALCONY_OPENING_FLOORPLAN,
        "window_segments": [opening],
    }
    items = [_item("tv", "tv-bench", 120, 40, h=45.0, placement_room_id="living")]
    objects = generate_layout_by_room(
        450.0, 380.0, items,
        room=_rect_room(450.0, 380.0),
        floorplan=floorplan,
    )
    obj = objects[0]
    assert not obj["placement_failed"]
    x, z = obj["position_cm"]["x"], obj["position_cm"]["z"]
    fw, fd = obj["footprint_cm"]["width"], obj["footprint_cm"]["depth"]
    in_front_of_opening = (
        z - fd / 2 <= -190 + 75 and x + fw / 2 > -60 - 75 and x - fw / 2 < 60 + 75
    )
    assert not in_front_of_opening, f"電視櫃 ({x:.0f},{z:.0f}) 擋住落地窗通行縫"


def test_whole_house_final_validation_passes_furniture_in_every_room():
    """最終確認(進即時寫實)是「無 placement_room_id 的整屋 validate_only」:
    柵格對格外一律視為阻擋,邊界必須用所有房的聯集 —— 否則最大房以外的
    家具全數被誤殺,畫面卡在原步驟且配置全亂(使用者實際回報的按鈕災情)。"""
    from backend.server.scene_service import (
        _region_boundary_by_id,
        _regions_boundary,
        generate_layout,
    )
    from backend.agent.place import placement_hints

    two_rooms = {
        "coordinate_unit": "cm",
        "width_cm": _TWO_ROOM_W,
        "depth_cm": _TWO_ROOM_D,
        **{k: v for k, v in _TWO_ROOM_FLOORPLAN.items() if k != "coordinate_unit"},
    }
    room = _rect_room(_TWO_ROOM_W, _TWO_ROOM_D)
    placed = []
    for room_id, items in (
        ("left", [_item("bed", "bed", 160, 200, h=120.0, placement_room_id="left")]),
        ("right", [
            _item("sofa", "sofa", 200, 90, h=96.0, placement_room_id="right"),
            _item("book", "bookcase", 80, 35, h=200.0, placement_room_id="right"),
        ]),
    ):
        boundary = _region_boundary_by_id(two_rooms, room, room_id)
        placed.extend(generate_layout(
            _TWO_ROOM_W, _TWO_ROOM_D, items, room=room,
            regions_boundary=_regions_boundary(two_rooms, room),
            place_boundary=boundary, floorplan=two_rooms,
            hints=placement_hints(items),
        ))
    assert all(not obj["placement_failed"] for obj in placed)

    locked = [{**obj, "position_locked": True} for obj in placed]
    validated = generate_layout(
        _TWO_ROOM_W, _TWO_ROOM_D, locked, room=room,
        regions_boundary=_regions_boundary(two_rooms, room),
        place_boundary=_regions_boundary(two_rooms, room),   # 整屋聯集(修正點)
        floorplan=two_rooms,
        hints=placement_hints(locked),
        validate_only=True,
    )
    for original, checked in zip(locked, validated):
        assert not checked["placement_failed"], (
            f"{checked['furniture_id']} 在整屋最終驗證被誤殺:{checked['placement_reason']}"
        )
        assert checked["position_cm"] == original["position_cm"]


def test_whole_house_final_validation_does_not_teleport_locked_tv_bench_into_balcony():
    """使用者回報:第 6→7 步電視櫃從客廳「跑到陽台」。根因=最終確認(confirmWhiteModel)
    的整屋 /api/scene/layout 少送 validate_only → 對「整屋聯集邊界」重排;靠陽台共享牆、
    在聯集柵格裡變不合法的鎖定電視櫃被沿「沙發對面牆」推到對面 —— 也就是陽台。
    validate_only 只驗不排:座標照舊,不合法者只標記,絕不搬進別的房間。
    此測試同時釘住(1)少 validate_only 會跑位(bug 登記處)與(2)validate_only 修好。"""
    from backend.server.scene_service import _regions_boundary, generate_layout
    from backend.agent.place import placement_hints

    w, d = 460.0, 420.0
    living = {
        "room_id": "living", "room_type": "living_room",
        "exterior": [[-220, -160], [220, -160], [220, 60], [-220, 60]], "holes": [],
    }
    balcony = {
        "room_id": "balcony", "room_type": "balcony",
        "exterior": [[-220, 60], [220, 60], [220, 200], [-220, 200]], "holes": [],
    }
    floorplan = {
        "coordinate_unit": "cm", "width_cm": w, "depth_cm": d,
        "room_regions": [living, balcony],
        # 整面共享牆的落地窗 = 陽台出入口(75cm 通行縫吃掉客廳側該面牆)
        "window_segments": [{
            "start": {"x": -220, "z": 60}, "end": {"x": 220, "z": 60},
            "window_type": "floor_to_ceiling",
        }],
    }
    balcony_poly = Polygon([(p[0], p[1]) for p in balcony["exterior"]]).buffer(2)

    sofa = _item("sofa", "sofa", 200, 90, h=96.0, placement_room_id="living")
    sofa["position_cm"] = {"x": 0.0, "z": -110.0}   # 背客廳外牆、面向共享牆(+z)
    sofa["rotation_y_deg"] = 0.0
    sofa["position_locked"] = True
    tv = _item("tv", "tv-bench", 160, 40, h=45.0, placement_room_id="living")
    tv["position_cm"] = {"x": 0.0, "z": 30.0}       # 鎖在客廳側、落在陽台門帶內
    tv["rotation_y_deg"] = 180.0
    tv["position_locked"] = True

    room = _rect_room(w, d)
    union = _regions_boundary(floorplan, room)       # confirmWhiteModel 觸發的整屋聯集
    hints = placement_hints([sofa, tv])

    def _tv_out(validate_only):
        out = generate_layout(
            w, d, [dict(sofa), dict(tv)], room=_rect_room(w, d),
            regions_boundary=union, place_boundary=union,
            floorplan=floorplan, hints=hints, validate_only=validate_only,
        )
        return next(o for o in out if o["furniture_id"] == "tv")

    # (前提)少送 validate_only(舊 confirmWhiteModel):電視櫃被重排進陽台。
    teleported = _tv_out(False)
    assert balcony_poly.contains(
        Point(teleported["position_cm"]["x"], teleported["position_cm"]["z"])
    ), "前提:少了 validate_only 時電視櫃應被重排進陽台(重現使用者災情)"

    # (修法)只驗不排:座標照舊、絕不進陽台;不合法只標記交回 2D。
    kept = _tv_out(True)
    assert kept["position_cm"] == {"x": 0.0, "z": 30.0}
    assert not balcony_poly.contains(
        Point(kept["position_cm"]["x"], kept["position_cm"]["z"])
    )


def test_curtain_may_hang_on_the_balcony_opening_but_sofa_may_not():
    """窗簾本來就掛在窗上:落地窗的 75cm 通行縫不適用於窗簾,
    但沙發等家具仍不得擋。"""
    from backend.agent.place import placement_hints
    from backend.server.scene_service import generate_layout_by_room as _by_room

    curtain = _item("curtain", "curtain", 140, 12, h=240.0, placement_room_id="living")
    curtain["position_cm"] = {"x": -115.0, "z": 178.0}   # 貼在下牆偏左開口上
    curtain["rotation_y_deg"] = 0.0
    curtain["position_locked"] = True
    sofa = _item("sofa", "sofa", 200, 90, h=96.0, placement_room_id="living")
    sofa["position_cm"] = {"x": -115.0, "z": 137.0}
    sofa["rotation_y_deg"] = 180.0
    sofa["position_locked"] = True
    objects = _by_room(
        450.0, 380.0, [curtain, sofa],
        room=_rect_room(450.0, 380.0),
        floorplan=_BALCONY_OPENING_FLOORPLAN,
    )
    by_id = {obj["furniture_id"]: obj for obj in objects}
    assert not by_id["curtain"]["placement_failed"]
    assert by_id["curtain"]["position_cm"] == {"x": -115.0, "z": 178.0}
    # 沙發壓開口:鎖定位置不合法 → 被重排離開(或標失敗),不得原地保留
    sofa_result = by_id["sofa"]
    assert sofa_result["placement_failed"] or sofa_result["position_cm"] != {"x": -115.0, "z": 137.0}


def test_seating_beside_a_plain_window_passes_final_validation():
    """座椅豁免窗前採光帶:餐椅椅背常 ≥90cm,會誤中「高家具擋光」判準,
    但椅子不是量體 —— 貼桌餐椅靠窗必須通過最終驗證;高量體(衣櫃)同位
    仍要擋。座椅擋落地窗出入口也照樣不行。"""
    window_floorplan = {
        "coordinate_unit": "cm",
        "width_cm": 450.0,
        "depth_cm": 380.0,
        "room_regions": [{
            "room_id": "kitchen",
            "room_type": "kitchen",
            "exterior": [[-225, -190], [225, -190], [225, 190], [-225, 190]],
            "holes": [],
        }],
        "window_segments": [
            {
                "start": {"x": -60, "z": 190},
                "end": {"x": 60, "z": 190},
                "window_type": "standard",
                "sill_height_cm": 90,
            },
        ],
    }

    from backend.server.scene_service import _regions_boundary

    room = _rect_room(450.0, 380.0)

    def _validated(ftype, w, d, h, floorplan):
        item = _item("probe", ftype, w, d, h=h, placement_room_id="kitchen")
        item["position_cm"] = {"x": 0.0, "z": 160.0}    # 貼窗牆、壓進 40cm 採光帶
        item["rotation_y_deg"] = 0.0
        item["position_locked"] = True
        boundary = _regions_boundary(floorplan, room)
        return generate_layout(
            450.0, 380.0, [item], room=room,
            regions_boundary=boundary, place_boundary=boundary,
            floorplan=floorplan, validate_only=True,
        )[0]

    chair = _validated("dining-chair", 45, 50, 95.0, window_floorplan)
    assert chair["placement_failed"] is False
    assert chair["position_cm"] == {"x": 0.0, "z": 160.0}
    wardrobe = _validated("wardrobe", 100, 60, 200.0, window_floorplan)
    assert wardrobe["placement_failed"] is True
    assert "窗前淨空" in wardrobe["placement_reason"] or "門前動線" in wardrobe["placement_reason"]

    access = {
        **window_floorplan,
        "window_segments": [{
            "start": {"x": -60, "z": 190},
            "end": {"x": 60, "z": 190},
            "window_type": "floor_to_ceiling",
        }],
    }
    blocked = _validated("dining-chair", 45, 50, 95.0, access)
    assert blocked["placement_failed"] is True   # 出入口誰都不能擋


def test_validate_rejects_sofa_on_balcony_opening_but_allows_plain_window():
    from backend.server.scene_service import validate_single_placement

    sofa = _item("sofa", "sofa", 200, 90, h=96.0)
    sofa["position_cm"] = {"x": -115.0, "z": 137.0}   # 壓在下牆偏左開口正前
    sofa["rotation_y_deg"] = 180.0
    blocked = validate_single_placement(_BALCONY_OPENING_FLOORPLAN, sofa, [])
    assert blocked["ok"] is False
    assert "陽台" in blocked["reason"]

    plain = {
        **_BALCONY_OPENING_FLOORPLAN,
        "window_segments": [{
            "start": {"x": -160, "z": 190},
            "end": {"x": -70, "z": 190},
            "window_type": "standard",
            "sill_height_cm": 90,
        }],
    }
    allowed = validate_single_placement(plain, sofa, [])
    assert allowed["ok"] is True                      # 一般窗:沙發可背窗


def test_bedside_table_candidate_faces_into_the_room():
    # 床頭櫃候選位於下牆(+z 側),正面必須朝 -z(房內)= 180;
    # 舊候選寫 0,櫃子臉貼牆、抽屜開不了
    objects = generate_layout(
        400.0, 400.0, [_item("ns", "bedside-table", 40, 40)], room=_rect_room(400.0, 400.0),
    )
    assert not objects[0]["placement_failed"]
    assert objects[0]["rotation_y_deg"] == 180


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
