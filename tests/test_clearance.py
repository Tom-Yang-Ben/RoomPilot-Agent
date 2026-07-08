"""
clearance.py 淨空運算測試

涵蓋:無淨空家具、淨空撞牆、淨空撞家具本體、
淨空互撞、反向檢查(本體壓到別人的淨空)、旋轉後淨空方向正確

單位:一律公分(cm),與引擎契約一致(2026-07-08 公分化)。
"""
import pytest

from roompilot.engine.models import Room, Wall, FurnitureCatalogItem, PlacedFurniture, ClearanceZone
from roompilot.engine.clearance import clearance_polygon, clearance_conflict, check_placement_with_clearance


@pytest.fixture
def room() -> Room:
    return Room(
        width=500, depth=400,
        walls=[
            Wall(0, 0, 500, 0),
            Wall(500, 0, 500, 400),
            Wall(500, 400, 0, 400),
            Wall(0, 400, 0, 0),
        ],
    )


def make_wardrobe(pos_x=250, pos_y=50, rotation=0) -> PlacedFurniture:
    """衣櫃:150cm 寬、60cm 深,front 需要 60cm 開門淨空"""
    return PlacedFurniture(
        id="wardrobe_1",
        catalog=FurnitureCatalogItem(
            type="wardrobe", name="衣櫃", width=150, depth=60,
            clearance=ClearanceZone(side="front", depth=60),
        ),
        pos_x=pos_x, pos_y=pos_y, rotation=rotation,
    )


def make_sofa(pos_x=250, pos_y=200) -> PlacedFurniture:
    """沙發:無淨空需求"""
    return PlacedFurniture(
        id="sofa_1",
        catalog=FurnitureCatalogItem(type="sofa", name="沙發", width=200, depth=90),
        pos_x=pos_x, pos_y=pos_y,
    )


# ---------- clearance_polygon 基本行為 ----------

def test_no_clearance_returns_none():
    """無淨空需求的家具,clearance_polygon 應回傳 None"""
    sofa = make_sofa()
    assert clearance_polygon(sofa) is None


def test_clearance_polygon_extends_front():
    """front 淨空應該往 +y 方向延伸,不含本體"""
    wardrobe = make_wardrobe(pos_x=250, pos_y=50)
    zone = clearance_polygon(wardrobe)
    assert zone is not None
    minx, miny, maxx, maxy = zone.bounds
    # 本體 front 邊在 y = 50 + 30 = 80,淨空應該從 80 延伸到 140
    assert miny == pytest.approx(80)
    assert maxy == pytest.approx(140)
    # 淨空區寬度跟家具同寬
    assert minx == pytest.approx(250 - 75)
    assert maxx == pytest.approx(250 + 75)


def test_clearance_rotates_with_furniture():
    """家具轉 180 度後,front 淨空應該改朝 -y 方向"""
    wardrobe = make_wardrobe(pos_x=250, pos_y=200, rotation=180)
    zone = clearance_polygon(wardrobe)
    minx, miny, maxx, maxy = zone.bounds
    # 旋轉 180 後,淨空應該在本體下方:從 y=170 往下延伸到 y=110
    assert maxy == pytest.approx(170)
    assert miny == pytest.approx(110)


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
    wardrobe = make_wardrobe(pos_x=250, pos_y=50)
    sofa = make_sofa(pos_x=250, pos_y=130)  # 沙發後緣 y=85,壓進淨空區(80~140)
    reason = clearance_conflict(wardrobe, room, [sofa])
    assert reason == "「衣櫃」的開合空間與「沙發」衝突"


def test_two_clearances_conflict(room):
    """兩個衣櫃面對面、淨空區重疊 → 淨空互撞"""
    w1 = make_wardrobe(pos_x=250, pos_y=50, rotation=0)      # 淨空 80~140
    w2 = make_wardrobe(pos_x=250, pos_y=200, rotation=180)    # 淨空 110~170,與 w1 重疊
    w2.id = "wardrobe_2"
    reason = clearance_conflict(w1, room, [w2])
    assert reason == "「衣櫃」與「衣櫃」的開合空間互相衝突"


# ---------- check_placement_with_clearance(總入口)----------

def test_body_check_runs_first(room):
    """本體出界時,應優先回報出界,而不是淨空問題"""
    wardrobe = make_wardrobe(pos_x=1000, pos_y=1000)
    reason = check_placement_with_clearance(wardrobe, room, [])
    assert reason == "物件超出空間範圍"


def test_reverse_check_body_blocks_others_clearance(room):
    """新家具本體壓到已放置家具的淨空 → 反向檢查應擋下"""
    wardrobe = make_wardrobe(pos_x=250, pos_y=50)
    bed = PlacedFurniture(
        id="bed_1",
        catalog=FurnitureCatalogItem(type="bed", name="雙人床", width=180, depth=200),
        pos_x=250, pos_y=210,  # 床前緣 y=110,壓進衣櫃淨空(80~140)
    )
    reason = check_placement_with_clearance(bed, room, [wardrobe])
    assert reason == "擋住了「衣櫃」的開合空間"


def test_valid_layout_passes_all_checks(room):
    """衣櫃靠牆門朝內 + 床離淨空夠遠 → 全部檢查通過"""
    wardrobe = make_wardrobe(pos_x=250, pos_y=50)
    bed = PlacedFurniture(
        id="bed_1",
        catalog=FurnitureCatalogItem(type="bed", name="雙人床", width=180, depth=200),
        pos_x=250, pos_y=260,  # 床前緣 y=160,離淨空上緣 140 還有距離
    )
    reason = check_placement_with_clearance(bed, room, [wardrobe])
    assert reason is None
