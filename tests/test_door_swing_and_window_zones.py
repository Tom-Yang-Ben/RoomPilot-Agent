"""門弧淨空與窗種分流的擺放規則。

門扇掃過的扇形不能有任何家具;落地窗前 50 公分硬淨空;一般窗前只擋
高過窗台的家具——矮櫃與臥榻仍然合法。
"""
from backend.server.scene_service import (
    FLOOR_WINDOW_CLEARANCE_CM,
    door_swing_zones,
    placement_forbidden_zones,
    room_from_payload,
    validate_single_placement,
)


def _floorplan(**extra):
    base = {
        "coordinate_unit": "cm",
        "width_cm": 600,
        "depth_cm": 500,
        "room_height_cm": 270,
    }
    base.update(extra)
    return base


def _item(normalized_type: str, *, height: float, x: float, z: float, width=80.0, depth=80.0):
    return {
        "furniture_id": f"{normalized_type}-1",
        "normalized_type": normalized_type,
        "size_cm": {"width": width, "depth": depth, "height": height},
        "position_cm": {"x": x, "z": z},
        "rotation_y_deg": 0,
    }


# ── 門弧 ──────────────────────────────────────────────────────────────

# 鉸鏈在 (-200, -250),打開後的門片端點在 (-200, -170)(伸進房內),
# 關門後的門片端點在 (-120, -250)(貼回牆上)。扇形是這兩者之間的 90 度。
_DOOR = {
    "start": {"x": -200, "z": -250},
    "end": {"x": -200, "z": -170},
    "swing_end": {"x": -120, "z": -250},
}


def test_door_swing_zone_is_built_from_hinge_and_swing_end() -> None:
    floorplan = _floorplan(door_segments=[_DOOR])
    zones = door_swing_zones(floorplan, room_from_payload(floorplan))

    assert len(zones) == 1
    zone = zones[0]
    assert zone.kind == "door_swing"
    assert zone.max_height_cm is None, "門弧不分高度,任何家具都不能進"
    # 四分之一圓面積 = pi * r^2 / 4,r = 80。離散成 12 段會略小於理論值。
    assert 4700 < zone.polygon.area < 5100


def test_furniture_inside_door_swing_is_rejected() -> None:
    floorplan = _floorplan(door_segments=[_DOOR])
    result = validate_single_placement(
        floorplan, _item("sideboard", height=80, x=-170, z=-220, width=30, depth=30), []
    )

    assert result["ok"] is False
    assert "門" in result["reason"]


def test_low_rug_inside_door_swing_is_still_rejected() -> None:
    """使用者要的是「不能有任何的傢俱」——地毯與壁架也不例外。"""
    floorplan = _floorplan(door_segments=[_DOOR])
    for item_type in ("large-medium-rug", "wall-shelf"):
        result = validate_single_placement(
            floorplan, _item(item_type, height=2, x=-170, z=-220, width=30, depth=30), []
        )
        assert result["ok"] is False, item_type
        assert "門" in result["reason"], item_type


def test_furniture_clear_of_door_swing_is_allowed() -> None:
    floorplan = _floorplan(door_segments=[_DOOR])
    result = validate_single_placement(
        floorplan, _item("sideboard", height=80, x=40, z=0, width=40, depth=40), []
    )

    assert result["ok"] is True, result["reason"]


def test_door_without_swing_end_still_produces_a_zone() -> None:
    """DXF 匯入的門沒有 swing_end,退回和前端同一條垂直後備規則。"""
    floorplan = _floorplan(
        door_segments=[{"start": {"x": -200, "z": -250}, "end": {"x": -200, "z": -170}}]
    )
    zones = door_swing_zones(floorplan, room_from_payload(floorplan))

    assert len(zones) == 1
    assert zones[0].max_height_cm is None


# ── 窗種分流 ──────────────────────────────────────────────────────────

_FLOOR_WINDOW = {
    "start": {"x": -100, "z": -250},
    "end": {"x": 100, "z": -250},
    "window_type": "floor_to_ceiling",
    "sill_height_cm": 0,
}
_STANDARD_WINDOW = {
    "start": {"x": -100, "z": -250},
    "end": {"x": 100, "z": -250},
    "window_type": "standard",
    "sill_height_cm": 90,
}


def test_floor_window_keeps_a_hard_50cm_band() -> None:
    floorplan = _floorplan(window_segments=[_FLOOR_WINDOW])
    zones = placement_forbidden_zones(floorplan, room_from_payload(floorplan))

    assert len(zones) == 1
    assert zones[0].kind == "floor_window"
    assert zones[0].max_height_cm is None
    assert FLOOR_WINDOW_CLEARANCE_CM == 50.0


def test_short_bench_in_front_of_floor_window_is_rejected() -> None:
    """落地窗前是進出與採光,矮到 40 公分也不能擺。"""
    floorplan = _floorplan(window_segments=[_FLOOR_WINDOW])
    result = validate_single_placement(
        floorplan, _item("sideboard", height=40, x=0, z=-220, width=60, depth=40), []
    )

    assert result["ok"] is False
    assert "落地窗" in result["reason"]


def test_furniture_beyond_the_floor_window_band_is_allowed() -> None:
    floorplan = _floorplan(window_segments=[_FLOOR_WINDOW])
    result = validate_single_placement(
        floorplan, _item("sideboard", height=200, x=0, z=-170, width=60, depth=40), []
    )

    assert result["ok"] is True, result["reason"]


def test_low_cabinet_under_the_sill_is_allowed_at_a_standard_window() -> None:
    """一般窗:高度不超過窗台就沒問題,這是使用者要的規則。"""
    floorplan = _floorplan(window_segments=[_STANDARD_WINDOW])
    result = validate_single_placement(
        floorplan, _item("sideboard", height=85, x=0, z=-220, width=60, depth=40), []
    )

    assert result["ok"] is True, result["reason"]


def test_tall_wardrobe_above_the_sill_is_rejected_at_a_standard_window() -> None:
    floorplan = _floorplan(window_segments=[_STANDARD_WINDOW])
    result = validate_single_placement(
        floorplan, _item("wardrobe", height=200, x=0, z=-220, width=60, depth=40), []
    )

    assert result["ok"] is False
    assert "窗台" in result["reason"]


def test_curtain_is_exempt_from_window_zones_but_not_from_doors() -> None:
    window_plan = _floorplan(window_segments=[_FLOOR_WINDOW])
    allowed = validate_single_placement(
        window_plan, _item("curtain", height=240, x=0, z=-235, width=200, depth=10), []
    )
    assert allowed["ok"] is True, allowed["reason"]

    door_plan = _floorplan(door_segments=[_DOOR])
    blocked = validate_single_placement(
        door_plan, _item("curtain", height=240, x=-170, z=-220, width=30, depth=10), []
    )
    assert blocked["ok"] is False
    assert "門" in blocked["reason"]


def test_seat_storage_preference_only_relaxes_standard_windows() -> None:
    """問卷選窗邊臥榻只關掉一般窗的判斷帶,門弧與落地窗不受影響。"""
    preferences = {"window_zone": "seat_storage"}

    standard_plan = _floorplan(window_segments=[_STANDARD_WINDOW])
    relaxed = validate_single_placement(
        standard_plan,
        _item("wardrobe", height=200, x=0, z=-220, width=60, depth=40),
        [],
        preferences,
    )
    assert relaxed["ok"] is True, relaxed["reason"]

    floor_plan = _floorplan(window_segments=[_FLOOR_WINDOW])
    still_blocked = validate_single_placement(
        floor_plan,
        _item("sideboard", height=40, x=0, z=-220, width=60, depth=40),
        [],
        preferences,
    )
    assert still_blocked["ok"] is False
    assert "落地窗" in still_blocked["reason"]

    door_plan = _floorplan(door_segments=[_DOOR])
    door_blocked = validate_single_placement(
        door_plan,
        _item("sideboard", height=80, x=-170, z=-220, width=30, depth=30),
        [],
        preferences,
    )
    assert door_blocked["ok"] is False
    assert "門" in door_blocked["reason"]
