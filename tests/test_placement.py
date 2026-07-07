"""
furniture_engine 核心邏輯測試
"""
import pytest

from furniture_engine.adjustment import adjust_furniture
from furniture_engine.geometry import check_placement
from furniture_engine.models import FurnitureCatalogItem, PlacedFurniture, Room, Wall
from furniture_engine.placement import place_furniture, place_furniture_batch


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


@pytest.fixture
def sofa_catalog() -> FurnitureCatalogItem:
    return FurnitureCatalogItem(type="sofa", name="沙發", width=2, depth=0.9)


@pytest.fixture
def table_catalog() -> FurnitureCatalogItem:
    return FurnitureCatalogItem(type="table", name="茶几", width=1, depth=0.6)


def test_center_placement_is_valid(room, sofa_catalog):
    item = PlacedFurniture(id="sofa_1", catalog=sofa_catalog, pos_x=2.5, pos_y=2)
    assert check_placement(item, room, []) is None


def test_out_of_bounds_detected(room, sofa_catalog):
    item = PlacedFurniture(id="sofa_1", catalog=sofa_catalog, pos_x=10, pos_y=10)
    reason = check_placement(item, room, [])
    assert reason == "物件超出空間範圍"


def test_wall_collision_detected(room, sofa_catalog):
    item = PlacedFurniture(id="sofa_1", catalog=sofa_catalog, pos_x=2.5, pos_y=0.47)
    reason = check_placement(item, room, [])
    assert reason == "與牆體穿透"


def test_furniture_overlap_detected(room, sofa_catalog, table_catalog):
    sofa = PlacedFurniture(id="sofa_1", catalog=sofa_catalog, pos_x=2.5, pos_y=2)
    table = PlacedFurniture(id="table_1", catalog=table_catalog, pos_x=2.5, pos_y=2)
    reason = check_placement(table, room, [sofa])
    assert reason == "與「沙發」重疊"


def test_furniture_no_false_positive_when_apart(room, sofa_catalog, table_catalog):
    sofa = PlacedFurniture(id="sofa_1", catalog=sofa_catalog, pos_x=2.5, pos_y=2)
    table = PlacedFurniture(id="table_1", catalog=table_catalog, pos_x=2.5, pos_y=3.5)
    reason = check_placement(table, room, [sofa])
    assert reason is None


def test_place_furniture_finds_valid_position(room, sofa_catalog):
    result = place_furniture(room, sofa_catalog, "sofa_1", [])
    assert result["success"] is True
    assert result["placed"] is not None
    assert check_placement(result["placed"], room, []) is None


def test_place_furniture_batch_avoids_overlap(room, sofa_catalog, table_catalog):
    items = [(sofa_catalog, "sofa_1"), (table_catalog, "table_1")]
    result = place_furniture_batch(room, items)
    assert len(result["placed"]) == 2
    assert result["failed"] == []

    sofa, table = result["placed"]
    assert check_placement(table, room, [sofa]) is None


def test_place_furniture_fails_when_room_too_small(sofa_catalog):
    tiny_room = Room(width=1, depth=1, walls=[])
    result = place_furniture(tiny_room, sofa_catalog, "sofa_1", [])
    assert result["success"] is False
    assert result["reason"] == "找不到合法擺放位置"


def test_move_valid_direction_succeeds(room, sofa_catalog):
    sofa = PlacedFurniture(id="sofa_1", catalog=sofa_catalog, pos_x=2.5, pos_y=2)
    result = adjust_furniture(room, sofa, [], {"action": "move", "dx": 0.3, "dy": 0})
    assert result["success"] is True
    assert sofa.pos_x == pytest.approx(2.8)
    assert sofa.pos_y == pytest.approx(2)


def test_move_axis_separation_blocks_only_bad_axis(room, sofa_catalog):
    sofa = PlacedFurniture(id="sofa_1", catalog=sofa_catalog, pos_x=2.5, pos_y=2)
    result = adjust_furniture(room, sofa, [], {"action": "move", "dx": 10, "dy": 0})
    assert result["success"] is True
    assert sofa.pos_x == pytest.approx(2.5)
    assert sofa.pos_y == pytest.approx(2)


def test_move_both_axes_blocked_reports_failure(room, sofa_catalog):
    sofa = PlacedFurniture(id="sofa_1", catalog=sofa_catalog, pos_x=2.5, pos_y=2)
    result = adjust_furniture(room, sofa, [], {"action": "move", "dx": 10, "dy": 10})
    assert result["success"] is False
    assert result["reason"] is not None
    assert sofa.pos_x == pytest.approx(2.5)
    assert sofa.pos_y == pytest.approx(2)


def test_move_blocked_by_other_furniture(room, sofa_catalog, table_catalog):
    sofa = PlacedFurniture(id="sofa_1", catalog=sofa_catalog, pos_x=2.5, pos_y=1.5)
    table = PlacedFurniture(id="table_1", catalog=table_catalog, pos_x=2.5, pos_y=3)
    adjust_furniture(room, sofa, [table], {"action": "move", "dx": 0, "dy": 1.5})
    assert sofa.pos_y == pytest.approx(1.5)


def test_rotate_valid_angle_succeeds(room, sofa_catalog):
    sofa = PlacedFurniture(id="sofa_1", catalog=sofa_catalog, pos_x=2.5, pos_y=2)
    result = adjust_furniture(room, sofa, [], {"action": "rotate", "rotation": 90})
    assert result["success"] is True
    assert sofa.rotation == 90


def test_rotate_into_wall_reverts(room, sofa_catalog):
    sofa = PlacedFurniture(id="sofa_1", catalog=sofa_catalog, pos_x=0.5, pos_y=2, rotation=0)
    result = adjust_furniture(room, sofa, [], {"action": "rotate", "rotation": 90})
    assert result["success"] is False
    assert sofa.rotation == 0


def test_unknown_action_returns_failure(room, sofa_catalog):
    sofa = PlacedFurniture(id="sofa_1", catalog=sofa_catalog, pos_x=2.5, pos_y=2)
    result = adjust_furniture(room, sofa, [], {"action": "teleport"})
    assert result["success"] is False
    assert "未知的動作" in result["reason"]

