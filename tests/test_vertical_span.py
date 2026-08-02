"""垂直佔用帶:平面可以重疊,只要垂直不重疊。

取代「這個型別要不要算碰撞」的二元開關——開關講不出「壁架跟矮櫃可以、
跟高衣櫃不行」,一個離地高度就講得出來。
"""
import pytest

from backend.catalog.style_db import MOUNT_HEIGHT_BY_TYPE, catalog_item_from_scene_object
from backend.engine.geometry import check_placement, hits_furniture, vertical_overlap
from backend.engine.models import FurnitureCatalogItem, PlacedFurniture, Room, Wall


def _room(width=600.0, depth=500.0) -> Room:
    return Room(
        width=width,
        depth=depth,
        walls=[
            Wall(0, 0, width, 0),
            Wall(width, 0, width, depth),
            Wall(width, depth, 0, depth),
            Wall(0, depth, 0, 0),
        ],
    )


def _placed(item_id: str, catalog: FurnitureCatalogItem, x=300.0, y=250.0) -> PlacedFurniture:
    return PlacedFurniture(id=item_id, catalog=catalog, pos_x=x, pos_y=y)


def _catalog(item_type: str, name: str, w: float, d: float, h: float) -> FurnitureCatalogItem:
    return catalog_item_from_scene_object(item_type, name, w, d, h)


# ── 資料結構 ──────────────────────────────────────────────────────────

def test_floor_furniture_spans_from_the_ground_by_default() -> None:
    sofa = FurnitureCatalogItem(type="sofa", name="沙發", width=200, depth=90, height=80)
    assert sofa.vertical_span() == (0.0, 80.0)
    assert sofa.is_wall_mounted() is False


def test_non_occupying_items_have_no_span() -> None:
    rug = _catalog("large-medium-rug", "地毯", 200, 150, 2)
    assert rug.vertical_span() is None
    assert rug.is_wall_mounted() is False


def test_wall_mounted_items_start_above_the_floor() -> None:
    shelf = _catalog("wall-shelf", "層架", 80, 25, 30)
    assert shelf.vertical_span() == (120.0, 150.0)
    assert shelf.is_wall_mounted() is True


@pytest.mark.parametrize("item_type,mount", sorted(MOUNT_HEIGHT_BY_TYPE.items()))
def test_mount_height_table_reaches_the_engine(item_type: str, mount: float) -> None:
    catalog = _catalog(item_type, item_type, 60, 20, 40)
    assert catalog.mount_height_cm == mount
    assert catalog.vertical_span() == (mount, mount + 40)


# ── 重疊判定 ──────────────────────────────────────────────────────────

def test_shelf_above_a_low_cabinet_does_not_overlap() -> None:
    shelf = _placed("shelf_1", _catalog("wall-shelf", "層架", 80, 25, 30))
    cabinet = _placed("cab_1", _catalog("sideboard", "矮櫃", 120, 40, 80))

    assert vertical_overlap(shelf, cabinet) is False
    assert hits_furniture(shelf, [cabinet]) is None


def test_shelf_against_a_tall_wardrobe_overlaps() -> None:
    """今天的漏洞:壁架設成「完全不算碰撞」,掛在 200 公分衣櫃前也合法。"""
    shelf = _placed("shelf_1", _catalog("wall-shelf", "層架", 80, 25, 30))
    wardrobe = _placed("wr_1", _catalog("wardrobe", "衣櫃", 120, 60, 200))

    assert vertical_overlap(shelf, wardrobe) is True
    assert hits_furniture(shelf, [wardrobe]) is wardrobe


def test_sofa_may_stand_on_a_rug() -> None:
    rug = _placed("rug_1", _catalog("large-medium-rug", "地毯", 240, 180, 2))
    sofa = _placed("sofa_1", _catalog("sofa", "沙發", 200, 90, 80))

    assert vertical_overlap(sofa, rug) is False
    assert hits_furniture(sofa, [rug]) is None
    assert hits_furniture(rug, [sofa]) is None


def test_two_floor_items_still_collide() -> None:
    sofa = _placed("sofa_1", _catalog("sofa", "沙發", 200, 90, 80))
    table = _placed("tbl_1", _catalog("dining-table", "餐桌", 160, 90, 75))

    assert vertical_overlap(sofa, table) is True
    assert hits_furniture(sofa, [table]) is table


# ── 牆與邊界 ──────────────────────────────────────────────────────────

def test_wall_mounted_items_are_not_judged_by_wall_penetration() -> None:
    """層架掛在牆面上,穿牆是它的正常狀態。"""
    room = _room()
    shelf = _placed("shelf_1", _catalog("wall-shelf", "層架", 80, 25, 30), x=300.0, y=2.0)

    assert check_placement(shelf, room, []) is None


def test_floor_furniture_still_fails_on_wall_penetration() -> None:
    # 牆厚 10 公分 → 牆體佔 y 的 -5~5。深 40 置於 y=22 只穿牆、不出界,
    # 避免同時命中前一項檢查(順序上「出界」會先回報)。
    room = _room()
    cabinet = _placed("cab_1", _catalog("sideboard", "矮櫃", 120, 40, 80), x=300.0, y=22.0)

    assert check_placement(cabinet, room, []) == "與牆體穿透"


def test_rug_still_has_to_stay_inside_the_room() -> None:
    """地毯不佔垂直空間,但仍然不能鋪穿牆或鋪到房間外。"""
    room = _room()
    rug = _placed("rug_1", _catalog("large-medium-rug", "地毯", 240, 180, 2), x=300.0, y=91.0)
    assert check_placement(rug, room, []) == "與牆體穿透"

    outside = _placed("rug_2", _catalog("large-medium-rug", "地毯", 240, 180, 2), x=300.0, y=-50.0)
    assert check_placement(outside, room, []) == "物件超出空間範圍"
