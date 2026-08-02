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


def test_wall_mirror_clears_low_furniture_but_not_a_tall_wardrobe() -> None:
    """壁掛的合法性靠垂直佔用帶,不是「壁掛一律不算碰撞」的開關。

    large-mirror 掛在 90 公分、自身高 160 → 佔 90–250。
    矮櫃 0–80 不重疊,可以掛在它上方;衣櫃 0–200 重疊,會撞在一起。
    """
    floorplan = _floorplan()
    mirror = _item(
        "large-mirror",
        size_cm={"width": 60, "depth": 5, "height": 160},
        position_cm={"x": 0, "z": 0},
    )
    low_cabinet = _item(
        "sideboard",
        furniture_id="sideboard-1",
        size_cm={"width": 120, "depth": 40, "height": 80},
        position_cm={"x": 0, "z": 0},
    )
    tall_wardrobe = _item(
        "wardrobe",
        furniture_id="wardrobe-1",
        size_cm={"width": 120, "depth": 60, "height": 200},
        position_cm={"x": 0, "z": 0},
    )

    over_low = validate_single_placement(floorplan, mirror, [low_cabinet])
    assert over_low["ok"] is True, over_low["reason"]

    over_tall = validate_single_placement(floorplan, mirror, [tall_wardrobe])
    assert over_tall["ok"] is False
    assert "重疊" in over_tall["reason"]


def test_name_hints_downgrade_mistyped_accessories() -> None:
    """型錄把滑鼠墊記成 stool-bench;品名判準要能把它降級,不再帶 footprint。"""
    assert _is_overlay_item("stool-bench", "電競滑鼠墊") is False
    assert _is_collision_exempt_item("shelving-unit", "壁掛層板") is True
    # 「附層板」是配備描述,主體仍是桌子。
    assert _is_collision_exempt_item("desk", "電競桌，附層板") is False


def test_auto_decor_rugs_cover_the_indoor_catalog_types() -> None:
    """自動軟裝原本只認 2 種地毯,型錄有 7 種——另外 3 種室內地毯一直選不到。"""
    from backend.server.main import _AUTO_DECOR_TYPES

    rug_types = set(_AUTO_DECOR_TYPES["rug"])

    assert rug_types <= _FLOOR_COVERING_TYPES, "自動軟裝不能挑型錄沒宣告成地面覆蓋物的型別"
    assert {"rug", "handmade-rug", "round-rug"} <= rug_types
    # 戶外地毯與門口踏墊不是室內軟裝,放進臥室比少放一張地毯糟糕。
    assert rug_types.isdisjoint({"outdoor-rug", "door-mat"})


def test_scene_service_no_longer_keeps_a_second_type_vocabulary() -> None:
    source = inspect.getsource(scene_service)
    assert "_OVERLAY_TYPES" not in source
    assert "_IGNORE_COLLISION_TYPES" not in source
    assert "placement_surface_for" in source
