"""
clearance.py 淨空運算測試
"""
import pytest

from furniture_engine.clearance import (
    check_placement_with_clearance,
    clearance_conflict,
    clearance_polygon,
)
from furniture_engine.models import ClearanceZone, FurnitureCatalogItem, PlacedFurniture, Room, Wall


@pytest.fixture
def room() -> Room:
    return Room(
        width=5,
        depth=4,
        walls=[
            Wall(0, 0, 5, 0),
            Wall(5, 0, 5, 4),
            Wall(5, 4, 0, 4),
            Wall(0, 4, 0, 0),
        ],
    )


def make_wardrobe(pos_x=2.5, pos_y=0.5, rotation=0) -> PlacedFurniture:
    return PlacedFurniture(
        id="wardrobe_1",
        catalog=FurnitureCatalogItem(
            type="wardrobe",
            name="衣櫃",
            width=1.5,
            depth=0.6,
            clearance=ClearanceZone(side="front", depth=0.6),
        ),
        pos_x=pos_x,
        pos_y=pos_y,
        rotation=rotation,
    )


def make_sofa(pos_x=2.5, pos_y=2.0) -> PlacedFurniture:
    return PlacedFurniture(
        id="sofa_1",
        catalog=FurnitureCatalogItem(type="sofa", name="沙發", width=2.0, depth=0.9),
        pos_x=pos_x,
        pos_y=pos_y,
    )


def test_no_clearance_returns_none():
    sofa = make_sofa()
    assert clearance_polygon(sofa) is None


def test_clearance_polygon_extends_front():
    wardrobe = make_wardrobe(pos_x=2.5, pos_y=0.5)
    zone = clearance_polygon(wardrobe)
    assert zone is not None
    minx, miny, maxx, maxy = zone.bounds
    assert miny == pytest.approx(0.8)
    assert maxy == pytest.approx(1.4)
    assert minx == pytest.approx(2.5 - 0.75)
    assert maxx == pytest.approx(2.5 + 0.75)


def test_clearance_rotates_with_furniture():
    wardrobe = make_wardrobe(pos_x=2.5, pos_y=2.0, rotation=180)
    zone = clearance_polygon(wardrobe)
    minx, miny, maxx, maxy = zone.bounds
    assert maxy == pytest.approx(1.7)
    assert miny == pytest.approx(1.1)


def test_clearance_clear_when_open_space(room):
    wardrobe = make_wardrobe()
    assert clearance_conflict(wardrobe, room, []) is None


def test_clearance_blocked_by_wall(room):
    wardrobe = make_wardrobe(rotation=180)
    reason = clearance_conflict(wardrobe, room, [])
    assert reason == "「衣櫃」的開合空間被牆體阻擋"


def test_clearance_blocked_by_furniture_body(room):
    wardrobe = make_wardrobe(pos_x=2.5, pos_y=0.5)
    sofa = make_sofa(pos_x=2.5, pos_y=1.3)
    reason = clearance_conflict(wardrobe, room, [sofa])
    assert reason == "「衣櫃」的開合空間與「沙發」衝突"


def test_two_clearances_conflict(room):
    w1 = make_wardrobe(pos_x=2.5, pos_y=0.5, rotation=0)
    w2 = make_wardrobe(pos_x=2.5, pos_y=2.0, rotation=180)
    w2.id = "wardrobe_2"
    reason = clearance_conflict(w1, room, [w2])
    assert reason == "「衣櫃」與「衣櫃」的開合空間互相衝突"


def test_body_check_runs_first(room):
    wardrobe = make_wardrobe(pos_x=10, pos_y=10)
    reason = check_placement_with_clearance(wardrobe, room, [])
    assert reason == "物件超出空間範圍"


def test_reverse_check_body_blocks_others_clearance(room):
    wardrobe = make_wardrobe(pos_x=2.5, pos_y=0.5)
    bed = PlacedFurniture(
        id="bed_1",
        catalog=FurnitureCatalogItem(type="bed", name="雙人床", width=1.8, depth=2.0),
        pos_x=2.5,
        pos_y=2.1,
    )
    reason = check_placement_with_clearance(bed, room, [wardrobe])
    assert reason == "擋住了「衣櫃」的開合空間"


def test_valid_layout_passes_all_checks(room):
    wardrobe = make_wardrobe(pos_x=2.5, pos_y=0.5)
    bed = PlacedFurniture(
        id="bed_1",
        catalog=FurnitureCatalogItem(type="bed", name="雙人床", width=1.8, depth=2.0),
        pos_x=2.5,
        pos_y=2.6,
    )
    reason = check_placement_with_clearance(bed, room, [wardrobe])
    assert reason is None

