"""垂直佔用帶:平面可以重疊,只要垂直不重疊。

取代「這個型別要不要算碰撞」的二元開關——開關講不出「壁架跟矮櫃可以、
跟高衣櫃不行」,一個離地高度就講得出來。
"""
import pytest

from backend.catalog.style_db import (
    MOUNT_HEIGHT_BY_TYPE,
    OVERLAP_ALLOWED_BY_TYPE,
    catalog_item_from_scene_object,
)
from backend.engine.clearance import check_placement_with_clearance
from backend.engine.geometry import (
    check_placement,
    hits_furniture,
    may_share_floor_space,
    vertical_overlap,
)
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


# 高度表的型別不一定「整個型別都是壁掛」——cabinet-cupboard 等型別只有
# 名稱命中壁掛判準的子集吃得到高度，所以用壁掛名稱建構才進得了 WALL 分支。
@pytest.mark.parametrize("item_type,mount", sorted(MOUNT_HEIGHT_BY_TYPE.items()))
def test_mount_height_table_reaches_the_engine(item_type: str, mount: float) -> None:
    catalog = _catalog(item_type, f"壁掛{item_type}", 60, 20, 40)
    assert catalog.mount_height_cm == mount
    assert catalog.vertical_span() == (mount, mount + 40)


# ── 2026-08-03 高度表擴充（Ben 拍板全套）────────────────────────────────

def test_wall_hung_besta_cabinet_floats_above_a_sofa() -> None:
    """180cm 寬的上牆式收納櫃不該再擋掉一整面牆的地板。"""
    cabinet = _catalog("cabinet-cupboard", "BESTÅ - 上牆式收納櫃組合, 白色", 180, 42, 64)
    sofa = _catalog("sofa", "三人座沙發", 200, 90, 80)
    assert cabinet.vertical_span() == (130.0, 194.0)
    assert cabinet.is_wall_mounted() is True
    # 帶 [130,194] 對沙發 [0,80]：垂直不重疊，平面可以共存。
    assert vertical_overlap(_placed("cabinet", cabinet), _placed("sofa", sofa)) is False


def test_plain_floor_cabinet_keeps_floor_span() -> None:
    """同型別、沒有壁掛名稱的一般櫃子不受高度表影響。"""
    cabinet = _catalog("cabinet-cupboard", "BESTÅ 收納櫃組合, 白色", 120, 40, 74)
    assert cabinet.vertical_span() == (0.0, 74.0)
    assert cabinet.is_wall_mounted() is False


def test_wall_hung_bedside_table_aligns_with_mattress_top() -> None:
    table = _catalog("bedside-table", "STOMSÖ 壁掛床邊桌", 36, 29, 20)
    assert table.vertical_span() == (45.0, 65.0)
    floor_table = _catalog("bedside-table", "HEMNES 床邊桌", 46, 35, 70)
    assert floor_table.vertical_span() == (0.0, 70.0)


def test_wall_hint_never_lifts_desks_off_the_floor() -> None:
    """壁掛折疊桌的桌下要容椅子與腿，維持落地佔用才符合實際使用。"""
    desk = _catalog("desk", "floating wall-mounted desk", 74, 60, 74)
    assert desk.vertical_span() == (0.0, 74.0)
    assert desk.is_wall_mounted() is False
    folding = _catalog("bar-table", "NORBERG 壁掛折疊桌，白色", 74, 60, 74)
    assert folding.vertical_span() == (0.0, 74.0)


def test_feature_marker_keeps_ambiguous_wall_cabinet_on_the_floor() -> None:
    """「附」配備標記的已知保守誤判：EKET 附2抽屜壁櫃其實是壁櫃。

    「附」在型錄裡幾乎都描述配備（附層板電競桌），拿掉標記會誤傷更多真
    落地家具；這一筆接受多擋不漏擋。
    """
    eket = _catalog("bedside-table", "EKET 附2抽屜壁櫃，胡桃木紋", 35, 35, 35)
    assert eket.vertical_span() == (0.0, 35.0)


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


# ── 成對例外(Phase 3) ────────────────────────────────────────────────

def test_pair_table_is_symmetric() -> None:
    """單向寫表會造成 A 查得到 B、B 查不到 A。"""
    for item_type, partners in OVERLAP_ALLOWED_BY_TYPE.items():
        for partner in partners:
            assert item_type in OVERLAP_ALLOWED_BY_TYPE[partner]


def test_dining_chair_tucks_under_the_table() -> None:
    table = _placed("tbl_1", _catalog("dining-table", "餐桌", 160, 90, 75))
    chair = _placed("chr_1", _catalog("dining-chair", "餐椅", 45, 50, 90))

    assert vertical_overlap(chair, table) is True, "兩者垂直帶確實重疊,靠例外放行"
    assert may_share_floor_space(chair, table) is True
    assert hits_furniture(chair, [table]) is None
    assert hits_furniture(table, [chair]) is None


def test_office_chair_tucks_under_the_desk_including_its_clearance() -> None:
    """書桌的前方淨空本來就是給辦公椅用的,不該判成擋住開合空間。"""
    room = _room()
    desk = _placed("desk_1", _catalog("desk", "書桌", 140, 70, 75))
    chair = _placed("chr_1", _catalog("office-chair", "辦公椅", 60, 60, 95), y=190.0)

    assert desk.catalog.clearance is not None, "書桌本來就有前方淨空"
    assert check_placement_with_clearance(chair, room, [desk]) is None
    assert check_placement_with_clearance(desk, room, [chair]) is None


def test_grouped_but_not_overlappable_pairs_still_collide() -> None:
    """成組不等於可重疊:床頭櫃配床、茶几配沙發該並排,不該疊在一起。"""
    bed = _placed("bed_1", _catalog("bed", "雙人床", 160, 200, 50))
    bedside = _placed("bs_1", _catalog("bedside-table", "床頭櫃", 45, 40, 55))
    assert hits_furniture(bedside, [bed]) is bed

    sofa = _placed("sofa_1", _catalog("sofa", "沙發", 200, 90, 80))
    coffee = _placed("cof_1", _catalog("coffee-table", "茶几", 100, 55, 40))
    assert hits_furniture(coffee, [sofa]) is sofa


def test_chair_still_collides_with_furniture_outside_the_pair() -> None:
    chair = _placed("chr_1", _catalog("dining-chair", "餐椅", 45, 50, 90))
    wardrobe = _placed("wr_1", _catalog("wardrobe", "衣櫃", 120, 60, 200))

    assert may_share_floor_space(chair, wardrobe) is False
    assert hits_furniture(chair, [wardrobe]) is wardrobe


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
