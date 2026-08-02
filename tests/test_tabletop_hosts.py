"""檯面小物的宿主相容表與平面包含判定（2026-08-03 Ben 拍板方案 B）。

花瓶、抱枕等 TABLETOP 品項不佔垂直空間、不算碰撞，但要「站在哪件家具
檯面上」才有意義：相容表回答能不能站上去，引擎回答腳印有沒有落在宿主
範圍內。3D 呈現高度是前端的事，這裡不管。
"""
from __future__ import annotations

from backend.catalog.placement_surface import _TABLETOP_TYPES
from backend.catalog.style_db import (
    TABLETOP_HOST_TYPES,
    allowed_host_types,
    catalog_item_from_scene_object,
)
from backend.engine.geometry import rests_within_host
from backend.engine.models import FurnitureCatalogItem, PlacedFurniture


def _placed(item_id: str, item_type: str, name: str, w: float, d: float, h: float,
            x: float = 0.0, y: float = 0.0, rotation: float = 0.0) -> PlacedFurniture:
    return PlacedFurniture(
        id=item_id,
        catalog=catalog_item_from_scene_object(item_type, name, w, d, h),
        pos_x=x,
        pos_y=y,
        rotation=rotation,
    )


# ── 相容表 ────────────────────────────────────────────────────────────

def test_every_tabletop_type_has_a_host_entry() -> None:
    """placement_surface 的 TABLETOP 型別與宿主表必須同步，新增型別漏配就紅。"""
    missing = set(_TABLETOP_TYPES) - set(TABLETOP_HOST_TYPES)
    assert not missing, f"TABLETOP 型別缺宿主表：{sorted(missing)}"


def test_vase_stands_on_tables_not_on_sofas() -> None:
    assert "dining-table" in allowed_host_types("vase")
    assert "coffee-table" in allowed_host_types("vase")
    assert "sofa" not in allowed_host_types("vase")


def test_pillow_rests_on_seating_not_on_tables() -> None:
    assert "sofa" in allowed_host_types("pillow-cushion")
    assert "bed" in allowed_host_types("pillow-cushion")
    assert "dining-table" not in allowed_host_types("pillow-cushion")


def test_unknown_type_gets_no_hosts() -> None:
    """未知型別保守不吸附，而不是到處都能站。"""
    assert allowed_host_types("sofa") == frozenset()
    assert allowed_host_types(None) == frozenset()


# ── 平面包含判定 ──────────────────────────────────────────────────────

def test_vase_centered_on_table_rests_within_host() -> None:
    table = _placed("table-1", "dining-table", "餐桌", 160, 90, 74, x=300, y=250)
    vase = _placed("vase-1", "vase", "花瓶", 18, 18, 30, x=300, y=250)
    assert rests_within_host(vase, table) is True


def test_vase_off_the_table_edge_is_rejected() -> None:
    table = _placed("table-1", "dining-table", "餐桌", 160, 90, 74, x=300, y=250)
    vase = _placed("vase-1", "vase", "花瓶", 18, 18, 30, x=300 + 90, y=250)
    assert rests_within_host(vase, table) is False


def test_edge_tolerance_allows_a_vase_flush_with_the_rim() -> None:
    """貼著桌緣是正常擺法：中心離緣半個瓶身，容差 2cm 內要放行。"""
    table = _placed("table-1", "dining-table", "餐桌", 160, 90, 74, x=300, y=250)
    flush = _placed("vase-1", "vase", "花瓶", 18, 18, 30, x=300 + 80 - 9 + 1, y=250)
    assert rests_within_host(flush, table) is True


def test_rotated_host_containment_follows_the_rotation() -> None:
    table = _placed("table-1", "dining-table", "餐桌", 160, 90, 74, x=300, y=250, rotation=90)
    # 旋轉 90 度後長邊沿 y 軸：沿 y 偏 70 仍在桌面上，沿 x 偏 70 已出界。
    on_long_axis = _placed("vase-1", "vase", "花瓶", 18, 18, 30, x=300, y=250 + 70)
    off_short_axis = _placed("vase-2", "vase", "花瓶", 18, 18, 30, x=300 + 70, y=250)
    assert rests_within_host(on_long_axis, table) is True
    assert rests_within_host(off_short_axis, table) is False


def test_zero_sized_host_never_carries_anything() -> None:
    ghost = PlacedFurniture(
        id="ghost",
        catalog=FurnitureCatalogItem(type="coffee-table", name="壞資料", width=0, depth=0, height=40),
        pos_x=300,
        pos_y=250,
    )
    vase = _placed("vase-1", "vase", "花瓶", 18, 18, 30, x=300, y=250)
    assert rests_within_host(vase, ghost) is False
