"""第 6 步的擺放行為必須讀型錄層的 placement_surface,不能自己再維護一份型別名單。

以前 scene_service 硬編碼 2 種地毯與 1 種壁掛,型錄實際宣告 7 種與 4 種——
其餘 8 種被當成落地家具去算碰撞與淨空,放不下就卡進第 6 步待處理清單。
"""
import inspect

import pytest

from backend.catalog.placement_surface import _FLOOR_COVERING_TYPES, _WALL_TYPES
from backend.server import scene_service
from backend.server.scene_service import (
    _is_collision_exempt_item,
    _is_overlay_item,
    validate_single_placement,
)


def _floorplan():
    return {
        "coordinate_unit": "cm",
        "width_cm": 600,
        "depth_cm": 500,
        "room_height_cm": 270,
    }


def _item(normalized_type: str, **extra):
    payload = {
        "furniture_id": f"{normalized_type}-1",
        "normalized_type": normalized_type,
        "size_cm": {"width": 160, "depth": 120, "height": 2},
        "position_cm": {"x": 0, "z": 0},
        "rotation_y_deg": 0,
    }
    payload.update(extra)
    return payload


@pytest.mark.parametrize("item_type", sorted(_FLOOR_COVERING_TYPES))
def test_every_catalog_floor_covering_is_treated_as_an_overlay(item_type: str) -> None:
    assert _is_overlay_item(item_type) is True
    assert _is_collision_exempt_item(item_type) is False


@pytest.mark.parametrize("item_type", sorted(_WALL_TYPES))
def test_every_catalog_wall_item_is_collision_exempt(item_type: str) -> None:
    assert _is_collision_exempt_item(item_type) is True
    assert _is_overlay_item(item_type) is False


def test_ordinary_floor_furniture_stays_on_the_engine_path() -> None:
    for item_type in ("sofa", "bed", "wardrobe", "dining-table"):
        assert _is_overlay_item(item_type) is False, item_type
        assert _is_collision_exempt_item(item_type) is False, item_type


def test_rug_types_beyond_the_old_hardcoded_pair_overlap_furniture() -> None:
    """round-rug 以前不在名單裡,會和沙發判定重疊而放不下。"""
    floorplan = _floorplan()
    sofa = _item(
        "sofa",
        furniture_id="sofa-1",
        size_cm={"width": 200, "depth": 90, "height": 80},
        position_cm={"x": 0, "z": 0},
    )
    rug = _item("round-rug", position_cm={"x": 0, "z": 0})

    result = validate_single_placement(floorplan, rug, [sofa])

    assert result["ok"] is True, result["reason"]


def test_mirror_beyond_the_old_hardcoded_type_ignores_floor_collision() -> None:
    """large-mirror 掛在牆上,不該和落地家具算碰撞。"""
    floorplan = _floorplan()
    wardrobe = _item(
        "wardrobe",
        furniture_id="wardrobe-1",
        size_cm={"width": 120, "depth": 60, "height": 200},
        position_cm={"x": 0, "z": 0},
    )
    mirror = _item(
        "large-mirror",
        size_cm={"width": 60, "depth": 5, "height": 160},
        position_cm={"x": 0, "z": 0},
    )

    result = validate_single_placement(floorplan, mirror, [wardrobe])

    assert result["ok"] is True, result["reason"]


def test_name_hints_downgrade_mistyped_accessories() -> None:
    """型錄把滑鼠墊記成 stool-bench;品名判準要能把它降級,不再帶 footprint。"""
    assert _is_overlay_item("stool-bench", "電競滑鼠墊") is False
    assert _is_collision_exempt_item("shelving-unit", "壁掛層板") is True
    # 「附層板」是配備描述,主體仍是桌子。
    assert _is_collision_exempt_item("desk", "電競桌，附層板") is False


def test_scene_service_no_longer_keeps_a_second_type_vocabulary() -> None:
    source = inspect.getsource(scene_service)
    assert "_OVERLAY_TYPES" not in source
    assert "_IGNORE_COLLISION_TYPES" not in source
    assert "placement_surface_for" in source
