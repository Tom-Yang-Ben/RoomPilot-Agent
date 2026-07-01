"""
furniture_engine 核心邏輯測試

涵蓋:
- place_furniture:合法放置 / 重疊偵測 / 出界偵測 / 穿牆偵測
- adjust_furniture:移動(軸分離)/ 旋轉
"""
import pytest

from furniture_engine.models import Room, Wall, FurnitureCatalogItem, PlacedFurniture
from furniture_engine.geometry import check_placement
from furniture_engine.placement import place_furniture, place_furniture_batch
from furniture_engine.adjustment import adjust_furniture


# ---------- 共用測資 ----------

@pytest.fixture
def room() -> Room:
    """5m x 4m 的矩形房間,四面都有牆"""
    return Room(
        width=5, depth=4,
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


# ---------- check_placement 基本案例 ----------

def test_center_placement_is_valid(room, sofa_catalog):
    """家具放在房間正中央,應該合法"""
    item = PlacedFurniture(id="sofa_1", catalog=sofa_catalog, pos_x=2.5, pos_y=2)
    assert check_placement(item, room, []) is None


def test_out_of_bounds_detected(room, sofa_catalog):
    """家具中心點超出房間邊界,應該偵測到出界"""
    item = PlacedFurniture(id="sofa_1", catalog=sofa_catalog, pos_x=10, pos_y=10)
    reason = check_placement(item, room, [])
    assert reason == "物件超出空間範圍"


def test_wall_collision_detected(room, sofa_catalog):
    """家具貼在牆的正上方(中心點在牆邊界),應該偵測到穿牆"""
    item = PlacedFurniture(id="sofa_1", catalog=sofa_catalog, pos_x=2.5, pos_y=0.47)
    reason = check_placement(item, room, [])
    assert reason == "與牆體穿透"


def test_furniture_overlap_detected(room, sofa_catalog, table_catalog):
    """兩件家具位置重疊,應該偵測到重疊並回報名稱"""
    sofa = PlacedFurniture(id="sofa_1", catalog=sofa_catalog, pos_x=2.5, pos_y=2)
    table = PlacedFurniture(id="table_1", catalog=table_catalog, pos_x=2.5, pos_y=2)
    reason = check_placement(table, room, [sofa])
    assert reason == "與「沙發」重疊"


def test_furniture_no_false_positive_when_apart(room, sofa_catalog, table_catalog):
    """兩件家具位置離得夠遠,不該誤判重疊"""
    sofa = PlacedFurniture(id="sofa_1", catalog=sofa_catalog, pos_x=2.5, pos_y=2)
    table = PlacedFurniture(id="table_1", catalog=table_catalog, pos_x=2.5, pos_y=3.5)
    reason = check_placement(table, room, [sofa])
    assert reason is None


# ---------- place_furniture / place_furniture_batch ----------

def test_place_furniture_finds_valid_position(room, sofa_catalog):
    result = place_furniture(room, sofa_catalog, "sofa_1", [])
    assert result["success"] is True
    assert result["placed"] is not None
    # 確認回傳的座標本身真的合法
    assert check_placement(result["placed"], room, []) is None


def test_place_furniture_batch_avoids_overlap(room, sofa_catalog, table_catalog):
    """批次放置時,後放的家具不該跟先放好的重疊"""
    items = [(sofa_catalog, "sofa_1"), (table_catalog, "table_1")]
    result = place_furniture_batch(room, items)
    assert len(result["placed"]) == 2
    assert result["failed"] == []

    sofa, table = result["placed"]
    assert check_placement(table, room, [sofa]) is None


def test_place_furniture_fails_when_room_too_small(sofa_catalog):
    """房間太小塞不下家具時,應該回報失敗,而不是硬塞一個不合法的位置"""
    tiny_room = Room(width=1, depth=1, walls=[])
    result = place_furniture(tiny_room, sofa_catalog, "sofa_1", [])
    assert result["success"] is False
    assert result["reason"] == "找不到合法擺放位置"


# ---------- adjust_furniture：移動 ----------

def test_move_valid_direction_succeeds(room, sofa_catalog):
    sofa = PlacedFurniture(id="sofa_1", catalog=sofa_catalog, pos_x=2.5, pos_y=2)
    result = adjust_furniture(room, sofa, [], {"action": "move", "dx": 0.3, "dy": 0})
    assert result["success"] is True
    assert sofa.pos_x == pytest.approx(2.8)
    assert sofa.pos_y == pytest.approx(2)


def test_move_axis_separation_blocks_only_bad_axis(room, sofa_catalog):
    """
    軸分離特性:X 方向移動會撞牆(該方向被擋、還原),
    Y 方向移動 0 距離必定合法,所以整體回報 success=True,
    但 X 座標不應該真的改變。
    """
    sofa = PlacedFurniture(id="sofa_1", catalog=sofa_catalog, pos_x=2.5, pos_y=2)
    result = adjust_furniture(room, sofa, [], {"action": "move", "dx": 10, "dy": 0})
    assert result["success"] is True          # Y 軸(移動0)必定成功
    assert sofa.pos_x == pytest.approx(2.5)    # X 軸被擋下,座標不變
    assert sofa.pos_y == pytest.approx(2)


def test_move_both_axes_blocked_reports_failure(room, sofa_catalog):
    """兩個軸同時都會撞到才會回報真正的 success=False"""
    sofa = PlacedFurniture(id="sofa_1", catalog=sofa_catalog, pos_x=2.5, pos_y=2)
    result = adjust_furniture(room, sofa, [], {"action": "move", "dx": 10, "dy": 10})
    assert result["success"] is False
    assert result["reason"] is not None
    # 位置應該完全沒變
    assert sofa.pos_x == pytest.approx(2.5)
    assert sofa.pos_y == pytest.approx(2)


def test_move_blocked_by_other_furniture(room, sofa_catalog, table_catalog):
    """移動目標會撞到別件家具,應該被擋下"""
    sofa = PlacedFurniture(id="sofa_1", catalog=sofa_catalog, pos_x=2.5, pos_y=1.5)
    table = PlacedFurniture(id="table_1", catalog=table_catalog, pos_x=2.5, pos_y=3)
    result = adjust_furniture(room, sofa, [table], {"action": "move", "dx": 0, "dy": 1.5})
    assert sofa.pos_y == pytest.approx(1.5)  # 應該被擋下,沒有移動到跟 table 重疊


# ---------- adjust_furniture：旋轉 ----------

def test_rotate_valid_angle_succeeds(room, sofa_catalog):
    sofa = PlacedFurniture(id="sofa_1", catalog=sofa_catalog, pos_x=2.5, pos_y=2)
    result = adjust_furniture(room, sofa, [], {"action": "rotate", "rotation": 90})
    assert result["success"] is True
    assert sofa.rotation == 90


def test_rotate_into_wall_reverts(room, sofa_catalog):
    """靠近牆邊的家具,旋轉後若會穿牆,應該還原成原本角度"""
    # 沙發寬 2m、深 0.9m,放在很靠近側牆的位置,旋轉 90 度後長邊會朝向牆
    sofa = PlacedFurniture(id="sofa_1", catalog=sofa_catalog, pos_x=0.5, pos_y=2, rotation=0)
    result = adjust_furniture(room, sofa, [], {"action": "rotate", "rotation": 90})
    assert result["success"] is False
    assert sofa.rotation == 0  # 還原


def test_unknown_action_returns_failure(room, sofa_catalog):
    sofa = PlacedFurniture(id="sofa_1", catalog=sofa_catalog, pos_x=2.5, pos_y=2)
    result = adjust_furniture(room, sofa, [], {"action": "teleport"})
    assert result["success"] is False
    assert "未知的動作" in result["reason"]