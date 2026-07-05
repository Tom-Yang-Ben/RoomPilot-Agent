"""
clearance.py 淨空運算測試

涵蓋:無淨空家具、淨空撞牆、淨空撞家具本體、
淨空互撞、反向檢查(本體壓到別人的淨空)、旋轉後淨空方向正確
"""
import pytest

from roompilot.engine.models import Room, Wall, FurnitureCatalogItem, PlacedFurniture, ClearanceZone
from roompilot.engine.clearance import clearance_polygon, clearance_conflict, check_placement_with_clearance


@pytest.fixture
def room() -> Room:
    return Room(
        width=5, depth=4,
        walls=[
            Wall(0, 0, 5, 0),
            Wall(5, 0, 5, 4),
            Wall(5, 4, 0, 4),
            Wall(0, 4, 0, 0),
        ],
    )


def make_wardrobe(pos_x=2.5, pos_y=0.5, rotation=0) -> PlacedFurniture:
    """衣櫃:1.5m 寬、0.6m 深,front 需要 0.6m 開門淨空"""
    return PlacedFurniture(
        id="wardrobe_1",
        catalog=FurnitureCatalogItem(
            type="wardrobe", name="衣櫃", width=1.5, depth=0.6,
            clearance=ClearanceZone(side="front", depth=0.6),
        ),
        pos_x=pos_x, pos_y=pos_y, rotation=rotation,
    )


def make_sofa(pos_x=2.5, pos_y=2.0) -> PlacedFurniture:
    """沙發:無淨空需求"""
    return PlacedFurniture(
        id="sofa_1",
        catalog=FurnitureCatalogItem(type="sofa", name="沙發", width=2.0, depth=0.9),
        pos_x=pos_x, pos_y=pos_y,
    )


# ---------- clearance_polygon 基本行為 ----------

def test_no_clearance_returns_none():
    """無淨空需求的家具,clearance_polygon 應回傳 None"""
    sofa = make_sofa()
    assert clearance_polygon(sofa) is None


def test_clearance_polygon_extends_front():
    """front 淨空應該往 +y 方向延伸,不含本體"""
    wardrobe = make_wardrobe(pos_x=2.5, pos_y=0.5)
    zone = clearance_polygon(wardrobe)
    assert zone is not None
    minx, miny, maxx, maxy = zone.bounds
    # 本體 front 邊在 y = 0.5 + 0.3 = 0.8,淨空應該從 0.8 延伸到 1.4
    assert miny == pytest.approx(0.8)
    assert maxy == pytest.approx(1.4)
    # 淨空區寬度跟家具同寬
    assert minx == pytest.approx(2.5 - 0.75)
    assert maxx == pytest.approx(2.5 + 0.75)


def test_clearance_rotates_with_furniture():
    """家具轉 180 度後,front 淨空應該改朝 -y 方向"""
    wardrobe = make_wardrobe(pos_x=2.5, pos_y=2.0, rotation=180)
    zone = clearance_polygon(wardrobe)
    minx, miny, maxx, maxy = zone.bounds
    # 旋轉 180 後,淨空應該在本體下方:從 y=1.7 往下延伸到 y=1.1
    assert maxy == pytest.approx(1.7)
    assert miny == pytest.approx(1.1)


# ---------- clearance_conflict ----------

def test_clearance_clear_when_open_space(room):
    """門朝房間內、前方無阻礙 → 無衝突"""
    wardrobe = make_wardrobe()
    assert clearance_conflict(wardrobe, room, []) is None


def test_clearance_blocked_by_wall(room):
    """門朝牆(旋轉 180、背對房間)→ 淨空撞牆"""
    wardrobe = make_wardrobe(rotation=180)
    reason = clearance_conflict(wardrobe, room, [])
    assert reason == "「衣櫃」的開合空間被牆體阻擋"


def test_clearance_blocked_by_furniture_body(room):
    """沙發擋在衣櫃門前 → 淨空撞家具本體"""
    wardrobe = make_wardrobe(pos_x=2.5, pos_y=0.5)
    sofa = make_sofa(pos_x=2.5, pos_y=1.3)  # 沙發後緣 y=0.85,壓進淨空區(0.8~1.4)
    reason = clearance_conflict(wardrobe, room, [sofa])
    assert reason == "「衣櫃」的開合空間與「沙發」衝突"


def test_two_clearances_conflict(room):
    """兩個衣櫃面對面、淨空區重疊 → 淨空互撞"""
    w1 = make_wardrobe(pos_x=2.5, pos_y=0.5, rotation=0)      # 淨空 0.8~1.4
    w2 = make_wardrobe(pos_x=2.5, pos_y=2.0, rotation=180)     # 淨空 1.1~1.7,與 w1 重疊
    w2.id = "wardrobe_2"
    reason = clearance_conflict(w1, room, [w2])
    assert reason == "「衣櫃」與「衣櫃」的開合空間互相衝突"


# ---------- check_placement_with_clearance(總入口)----------

def test_body_check_runs_first(room):
    """本體出界時,應優先回報出界,而不是淨空問題"""
    wardrobe = make_wardrobe(pos_x=10, pos_y=10)
    reason = check_placement_with_clearance(wardrobe, room, [])
    assert reason == "物件超出空間範圍"


def test_reverse_check_body_blocks_others_clearance(room):
    """新家具本體壓到已放置家具的淨空 → 反向檢查應擋下"""
    wardrobe = make_wardrobe(pos_x=2.5, pos_y=0.5)
    bed = PlacedFurniture(
        id="bed_1",
        catalog=FurnitureCatalogItem(type="bed", name="雙人床", width=1.8, depth=2.0),
        pos_x=2.5, pos_y=2.1,  # 床前緣 y=1.1,壓進衣櫃淨空(0.8~1.4)
    )
    reason = check_placement_with_clearance(bed, room, [wardrobe])
    assert reason == "擋住了「衣櫃」的開合空間"


def test_valid_layout_passes_all_checks(room):
    """衣櫃靠牆門朝內 + 床離淨空夠遠 → 全部檢查通過"""
    wardrobe = make_wardrobe(pos_x=2.5, pos_y=0.5)
    bed = PlacedFurniture(
        id="bed_1",
        catalog=FurnitureCatalogItem(type="bed", name="雙人床", width=1.8, depth=2.0),
        pos_x=2.5, pos_y=2.6,  # 床前緣 y=1.6,離淨空上緣 1.4 還有距離
    )
    reason = check_placement_with_clearance(bed, room, [wardrobe])
    assert reason is None