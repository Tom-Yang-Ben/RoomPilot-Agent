"""擺放策略層測試：貼牆錨定、正面朝內、選牆、貼床頭端、擺放順序。

座標約定同 `backend/engine/models.py`：原點在房間左下角，x 向右、y 向上，
單位公分；rotation 為逆時針角度，0 度時家具正面朝 +Y。
"""
import pytest

from backend.engine.clearance_defaults import catalog_with_default_clearance
from backend.engine.layout_strategy import (
    WALL_SIDES,
    free_spans,
    openings_on_wall,
    place_against_wall,
    place_beside,
    place_room,
    rank_wall_candidates,
    wall_rotation,
)
from backend.engine.models import FurnitureCatalogItem, Opening, PlacedFurniture, Room


# --- 測試用房間與家具 -------------------------------------------------------


def bare_room(width=400.0, depth=300.0, openings=None) -> Room:
    return Room(width=width, depth=depth, openings=list(openings or []))


def window(x1, y1, x2, y2, window_type="standard") -> Opening:
    return Opening(kind="window", x1=x1, y1=y1, x2=x2, y2=y2, window_type=window_type)


def door(x1, y1, x2, y2, swing=None) -> Opening:
    swing_x, swing_y = swing or (None, None)
    return Opening(kind="door", x1=x1, y1=y1, x2=x2, y2=y2, swing_x=swing_x, swing_y=swing_y)


def item(type_, name, width, depth, height=80.0) -> FurnitureCatalogItem:
    return catalog_with_default_clearance(
        FurnitureCatalogItem(type=type_, name=name, width=width, depth=depth, height=height)
    )


def footprint(placed: PlacedFurniture) -> tuple[float, float]:
    if placed.rotation in (90, 270):
        return placed.catalog.depth, placed.catalog.width
    return placed.catalog.width, placed.catalog.depth


def bounds(placed: PlacedFurniture) -> tuple[float, float, float, float]:
    fw, fd = footprint(placed)
    return (
        placed.pos_x - fw / 2,
        placed.pos_y - fd / 2,
        placed.pos_x + fw / 2,
        placed.pos_y + fd / 2,
    )


def touches_wall(placed: PlacedFurniture, room: Room, tolerance: float = 1.0) -> bool:
    left, bottom, right, top = bounds(placed)
    return (
        left <= tolerance
        or bottom <= tolerance
        or right >= room.width - tolerance
        or top >= room.depth - tolerance
    )


# --- Opening 基本語意 -------------------------------------------------------


def test_standard_window_defaults_to_90cm_sill():
    assert window(0, 0, 100, 0).sill_cm == 90.0


def test_floor_to_ceiling_window_has_zero_sill():
    assert window(0, 0, 100, 0, window_type="floor_to_ceiling").sill_cm == 0.0


def test_door_always_has_zero_sill_regardless_of_window_type():
    assert door(0, 0, 90, 0).sill_cm == 0.0


def test_window_without_explicit_type_is_treated_as_standard():
    opening = Opening(kind="window", x1=0, y1=0, x2=100, y2=0)
    assert opening.window_type == "standard"


def test_room_without_openings_keeps_previous_behaviour():
    room = Room(width=400, depth=300)
    assert room.openings == []
    assert room.doors() == []
    assert room.windows() == []


# --- 認得開口在哪面牆 -------------------------------------------------------


def test_opening_is_assigned_to_the_wall_it_sits_on():
    room = bare_room(openings=[window(100, 0, 200, 0)])
    assert openings_on_wall(room, "south") == room.openings
    for side in ("north", "west", "east"):
        assert openings_on_wall(room, side) == []


def test_vertical_window_belongs_to_the_west_wall():
    room = bare_room(openings=[window(0, 80, 0, 180)])
    assert openings_on_wall(room, "west") == room.openings
    assert openings_on_wall(room, "south") == []


# --- 牆面可用區段 -----------------------------------------------------------


def test_free_spans_on_a_clean_wall_is_the_whole_wall():
    room = bare_room()
    assert free_spans(room, "south") == [(0.0, 400.0)]


def test_window_splits_the_wall_into_two_spans():
    room = bare_room(openings=[window(150, 0, 250, 0)])
    assert free_spans(room, "south") == [(0.0, 150.0), (250.0, 400.0)]


def test_opening_at_the_wall_end_leaves_a_single_span():
    room = bare_room(openings=[window(300, 0, 400, 0)])
    assert free_spans(room, "south") == [(0.0, 300.0)]


def test_door_swing_widens_the_blocked_span_beyond_the_door_leaf():
    """門扇掃過的範圍也不可佔用，所以擋住的區段比門本身寬。"""
    plain = bare_room(openings=[door(100, 0, 190, 0)])
    swinging = bare_room(openings=[door(100, 0, 190, 0, swing=(100, 90))])
    plain_free = free_spans(plain, "south")
    swing_free = free_spans(swinging, "south")
    assert plain_free == [(0.0, 100.0), (190.0, 400.0)]
    # 門往房內開時，牆面上的可用區段不會比沒有門扇時更寬。
    assert swing_free[0][1] <= plain_free[0][1]
    assert swing_free[-1][0] >= plain_free[-1][0]


# --- 選牆排序 ---------------------------------------------------------------


def test_clean_wall_outranks_a_wall_with_a_window():
    room = bare_room(width=400, depth=400, openings=[window(0, 100, 0, 200)])
    ranked = rank_wall_candidates(room, needed_cm=150)
    assert ranked[0].side != "west"
    assert all(candidate.length >= 150 for candidate in ranked)


def test_longer_wall_wins_when_both_are_clean():
    room = bare_room(width=500, depth=300)
    ranked = rank_wall_candidates(room, needed_cm=100)
    assert ranked[0].side in ("south", "north")
    assert ranked[0].length == pytest.approx(500)


def test_wall_shorter_than_the_item_is_not_a_candidate():
    room = bare_room(width=400, depth=120)
    ranked = rank_wall_candidates(room, needed_cm=200)
    assert {candidate.side for candidate in ranked} == {"south", "north"}


def test_wall_with_a_door_ranks_below_a_wall_with_only_a_window():
    room = bare_room(
        width=400,
        depth=400,
        openings=[door(150, 0, 240, 0), window(0, 150, 0, 240)],
    )
    ranked = rank_wall_candidates(room, needed_cm=100)
    order = [candidate.side for candidate in ranked]
    assert order.index("west") < order.index("south")


# --- 貼牆與正面朝向 ---------------------------------------------------------


@pytest.mark.parametrize(
    "side,expected_rotation",
    [("south", 0), ("north", 180), ("west", 270), ("east", 90)],
)
def test_wall_rotation_makes_the_front_face_into_the_room(side, expected_rotation):
    assert wall_rotation(side) == expected_rotation


def test_placed_against_wall_actually_touches_that_wall():
    room = bare_room()
    wardrobe = item("wardrobe", "衣櫃", 100, 60, height=200)
    result = place_against_wall(room, wardrobe, "wardrobe_1", [], sides=["south"])
    assert result["success"]
    left, bottom, right, top = bounds(result["placed"])
    assert bottom == pytest.approx(0.0, abs=1.0)
    assert result["placed"].rotation == 0


def test_placed_against_side_wall_swaps_the_footprint():
    room = bare_room()
    bookcase = item("bookcase", "書櫃", 80, 30, height=205)
    result = place_against_wall(room, bookcase, "bookcase_1", [], sides=["west"])
    assert result["success"]
    placed = result["placed"]
    assert placed.rotation == 270
    fw, fd = footprint(placed)
    assert (fw, fd) == (30, 80)
    left, _, _, _ = bounds(placed)
    assert left == pytest.approx(0.0, abs=1.0)


def test_wall_anchored_item_never_lands_in_the_middle_of_the_room():
    room = bare_room()
    wardrobe = item("wardrobe", "衣櫃", 100, 60, height=200)
    result = place_against_wall(room, wardrobe, "wardrobe_1", [])
    assert result["success"]
    assert touches_wall(result["placed"], room)


def test_tall_item_avoids_a_wall_whose_window_it_would_block():
    """一般窗窗台 90：衣櫃 200 高會擋住，所以不選那面牆。"""
    room = bare_room(width=400, depth=400, openings=[window(0, 0, 0, 400)])
    wardrobe = item("wardrobe", "衣櫃", 100, 60, height=200)
    result = place_against_wall(room, wardrobe, "wardrobe_1", [])
    assert result["success"]
    left, _, _, _ = bounds(result["placed"])
    assert left > 1.0


def test_low_item_may_sit_under_a_standard_window():
    """床頭櫃 55 高低於窗台 90，可以擺在窗下。"""
    room = bare_room(width=200, depth=200, openings=[window(0, 0, 0, 200)])
    table = item("bedside-table", "床頭櫃", 40, 40, height=55)
    result = place_against_wall(room, table, "bedside-table_1", [], sides=["west"])
    assert result["success"]


def test_nothing_may_sit_under_a_floor_to_ceiling_window():
    room = bare_room(
        width=200, depth=200, openings=[window(0, 0, 0, 200, window_type="floor_to_ceiling")]
    )
    table = item("bedside-table", "床頭櫃", 40, 40, height=55)
    result = place_against_wall(room, table, "bedside-table_1", [], sides=["west"])
    assert not result["success"]


# --- 貼床頭端 ---------------------------------------------------------------


def bed_against_north_wall(room: Room) -> PlacedFurniture:
    """床頭貼北牆（y=depth），床尾朝房間內。"""
    bed = item("bed", "雙人床", 150, 200, height=45)
    return PlacedFurniture(
        id="bed_1",
        catalog=bed,
        pos_x=room.width / 2,
        pos_y=room.depth - 100,
        rotation=180,
    )


def test_bedside_table_lands_at_the_head_not_the_foot():
    room = bare_room(width=400, depth=400)
    bed = bed_against_north_wall(room)
    table = item("bedside-table", "床頭櫃", 40, 40, height=55)
    result = place_beside(room, table, "bedside-table_1", bed, [], end="head")
    assert result["success"]
    _, bottom, _, top = bounds(result["placed"])
    # 床佔 y[200,400]，床頭在 y=400 那端；床頭櫃必須落在床的上半段。
    assert top == pytest.approx(400, abs=2.0)
    assert bottom > 300


def test_bedside_table_sits_next_to_the_bed_not_overlapping_it():
    room = bare_room(width=400, depth=400)
    bed = bed_against_north_wall(room)
    table = item("bedside-table", "床頭櫃", 40, 40, height=55)
    result = place_beside(room, table, "bedside-table_1", bed, [], end="head", gap=5.0)
    assert result["success"]
    left, _, right, _ = bounds(result["placed"])
    bed_left, _, bed_right, _ = bounds(bed)
    assert right <= bed_left or left >= bed_right


def test_two_bedside_tables_land_on_opposite_sides_of_the_bed():
    room = bare_room(width=400, depth=400)
    bed = bed_against_north_wall(room)
    table = item("bedside-table", "床頭櫃", 40, 40, height=55)
    first = place_beside(room, table, "bedside-table_1", bed, [bed], end="head")
    assert first["success"]
    second = place_beside(
        room, table, "bedside-table_2", bed, [bed, first["placed"]], end="head"
    )
    assert second["success"]
    bed_center = bed.pos_x
    assert (first["placed"].pos_x - bed_center) * (second["placed"].pos_x - bed_center) < 0


# --- 整間房：擺放順序與「不浮在中央」 ---------------------------------------


def test_bedroom_puts_the_bed_head_on_a_wall_without_door_or_window():
    """對應 floor04 主臥：下牆有門、左牆有窗，只有上牆與右牆乾淨。"""
    room = bare_room(
        width=338,
        depth=310,
        openings=[door(255, 0, 337, 0, swing=(255, 91)), window(0, 103, 0, 207)],
    )
    result = place_room(
        room,
        "bedroom",
        [
            (item("bed", "雙人床", 150, 200, height=45), "bed_1"),
            (item("wardrobe", "衣櫃", 100, 60, height=200), "wardrobe_1"),
            (item("bedside-table", "床頭櫃", 40, 40, height=55), "bedside-table_1"),
            (item("bedside-table", "床頭櫃", 40, 40, height=55), "bedside-table_2"),
        ],
    )
    placed_by_id = {placed.id: placed for placed in result["placed"]}
    assert "bed_1" in placed_by_id, result["failed"]
    _, _, _, bed_top = bounds(placed_by_id["bed_1"])
    assert bed_top == pytest.approx(310, abs=2.0)


def test_no_anchor_furniture_floats_in_the_middle_of_the_room():
    room = bare_room(width=338, depth=310)
    result = place_room(
        room,
        "bedroom",
        [
            (item("bed", "雙人床", 150, 200, height=45), "bed_1"),
            (item("wardrobe", "衣櫃", 100, 60, height=200), "wardrobe_1"),
        ],
    )
    for placed in result["placed"]:
        assert touches_wall(placed, room), f"{placed.id} 浮在房間中央"


def test_living_room_sofa_and_tv_bench_face_each_other():
    room = bare_room(width=338, depth=298)
    result = place_room(
        room,
        "living_room",
        [
            (item("sofa", "沙發", 220, 90, height=85), "sofa_1"),
            (item("tv-bench", "電視櫃", 180, 40, height=50), "tv-bench_1"),
        ],
    )
    placed_by_id = {placed.id: placed for placed in result["placed"]}
    assert {"sofa_1", "tv-bench_1"} <= set(placed_by_id), result["failed"]
    sofa = placed_by_id["sofa_1"]
    tv = placed_by_id["tv-bench_1"]
    assert abs(sofa.rotation - tv.rotation) == 180


def test_storage_shelves_all_hug_a_wall():
    room = bare_room(width=338, depth=298)
    result = place_room(
        room,
        "storage",
        [
            (item("shelving-unit", "層架A", 80, 30, height=180), "shelving-unit_1"),
            (item("shelving-unit", "層架B", 80, 30, height=180), "shelving-unit_2"),
            (item("cabinet-cupboard", "收納櫃", 100, 50, height=200), "cabinet-cupboard_1"),
        ],
    )
    assert len(result["placed"]) == 3, result["failed"]
    for placed in result["placed"]:
        assert touches_wall(placed, room), f"{placed.id} 沒有貼牆"


def test_place_room_reports_structured_failure_when_nothing_fits():
    room = bare_room(width=100, depth=100)
    result = place_room(
        room,
        "bedroom",
        [(item("bed", "雙人床", 150, 200, height=45), "bed_1")],
    )
    assert result["placed"] == []
    assert result["failed"]
    assert result["failed"][0]["id"] == "bed_1"
    assert result["failed"][0]["reason"]


def test_place_room_is_deterministic():
    def run():
        room = bare_room(width=338, depth=310, openings=[window(0, 103, 0, 207)])
        return place_room(
            room,
            "bedroom",
            [
                (item("bed", "雙人床", 150, 200, height=45), "bed_1"),
                (item("wardrobe", "衣櫃", 100, 60, height=200), "wardrobe_1"),
            ],
        )

    first = [(p.id, p.pos_x, p.pos_y, p.rotation) for p in run()["placed"]]
    second = [(p.id, p.pos_x, p.pos_y, p.rotation) for p in run()["placed"]]
    assert first == second


def test_all_wall_sides_are_covered():
    assert set(WALL_SIDES) == {"south", "north", "west", "east"}


# --- 茶几：刻意不貼牆 -------------------------------------------------------


def test_coffee_table_sits_in_front_of_the_sofa_not_against_a_wall():
    # TV-first（08-02）後，298 深的小房塞不下「電視＋觀影距離＋沙發＋茶几帶」，
    # 引擎誠實失敗、砍茶几歸 Agent（v1：茶几可選）。本測試改用放得下的房深。
    room = bare_room(width=338, depth=500)
    result = place_room(
        room,
        "living_room",
        [
            (item("sofa", "沙發", 220, 90, height=85), "sofa_1"),
            (item("tv-bench", "電視櫃", 180, 40, height=50), "tv-bench_1"),
            (item("coffee-table", "茶几", 110, 60, height=42), "coffee-table_1"),
        ],
    )
    placed_by_id = {placed.id: placed for placed in result["placed"]}
    assert "coffee-table_1" in placed_by_id, result["failed"]
    table = placed_by_id["coffee-table_1"]
    sofa = placed_by_id["sofa_1"]
    assert not touches_wall(table, room), "茶几不應該貼牆"
    # 茶几與沙發共用中線，且落在沙發正面那一側（方向由沙發貼哪面牆決定）。
    front = {0: (0, 1), 90: (-1, 0), 180: (0, -1), 270: (1, 0)}[int(sofa.rotation) % 360]
    offset = (table.pos_x - sofa.pos_x, table.pos_y - sofa.pos_y)
    assert offset[0] * front[0] + offset[1] * front[1] > 0, "茶几不在沙發正面那一側"
    # 垂直於正面的方向上要對齊中線。
    assert abs(offset[0] * front[1] - offset[1] * front[0]) == pytest.approx(0, abs=1.0)


def test_coffee_table_without_a_sofa_reports_a_structured_failure():
    room = bare_room(width=338, depth=298)
    result = place_room(
        room,
        "living_room",
        [(item("coffee-table", "茶几", 110, 60, height=42), "coffee-table_1")],
    )
    assert result["placed"] == []
    assert result["failed"][0]["id"] == "coffee-table_1"


# --- 小房間：置中不行就貼齊牆角，不要留死縫 -------------------------------


def test_small_room_bed_hugs_the_corner_instead_of_leaving_a_dead_gap():
    """260×240 小房：置中會讓兩側淨空都不足，退讓時應貼齊牆角。

    早期版本會停在「離牆 10 公分」的中間位置——合法，但那 10 公分既走不了
    人也放不了東西，是純粹的死空間。
    """
    room = bare_room(
        width=260,
        depth=240,
        openings=[door(170, 0, 255, 0, swing=(170, 85))],
    )
    result = place_room(
        room,
        "bedroom",
        [
            (item("bed", "雙人床", 150, 200, height=45), "bed_1"),
            (item("bedside-table", "床頭櫃", 40, 40, height=55), "bedside-table_1"),
        ],
    )
    placed_by_id = {placed.id: placed for placed in result["placed"]}
    assert "bed_1" in placed_by_id, result["failed"]
    left, _, right, _ = bounds(placed_by_id["bed_1"])
    gap = min(left, room.width - right)
    assert gap <= 1.0, f"床離牆 {gap:.0f} 公分，應該貼齊"


def test_centered_placement_still_wins_when_it_is_legal():
    """大房間不受影響：置中合法時仍然置中，不會被貼齊搶走。"""
    room = bare_room(width=338, depth=310)
    result = place_room(
        room,
        "bedroom",
        [(item("bed", "雙人床", 150, 200, height=45), "bed_1")],
    )
    bed = result["placed"][0]
    assert bed.pos_x == pytest.approx(room.width / 2, abs=1.0)


# --- 整合：scene_service 的逐件迴圈必須尊重錨點順序 -------------------------


def test_generate_layout_places_anchors_first_regardless_of_item_order():
    """衣櫃排在清單第一位時，床仍須先搶到最好的牆（床頭貼無門無窗的北牆）。

    引擎的 place_room() 自己會排序，但第 6 步走的是 scene_service 的逐件
    迴圈——實測 Agent 補件把衣櫃插到清單最前時，衣櫃先佔走北牆，床被擠去
    貼窗牆。本測試鎖住「處理順序依房型規則的錨點優先，與清單順序無關」。
    """
    from backend.server.scene_service import generate_layout, room_from_payload

    width, depth = 338.0, 310.0

    def centered(x, y):
        return {"x": x - width / 2, "z": y - depth / 2}

    floorplan = {
        "width_cm": width,
        "depth_cm": depth,
        "coordinate_unit": "cm",
        "wall_segments": [],
        "door_segments": [
            {"start": centered(255, 0), "end": centered(337, 0), "swing_end": centered(255, 91)}
        ],
        "window_segments": [{"start": centered(0, 103), "end": centered(0, 207)}],
    }
    engine_room = room_from_payload(floorplan)

    def payload_item(fid, type_, w, d, h):
        return {
            "furniture_id": fid,
            "normalized_type": type_,
            "name_zh_raw": fid,
            "has_model": True,
            "model_url": "https://example.test/x.glb",
            "size_cm": {"width": w, "depth": d, "height": h},
        }

    # 衣櫃刻意排第一——Agent 補件（無模型假件換真品時前插）就是這個順序。
    objects = generate_layout(
        width,
        depth,
        [
            payload_item("wardrobe-1", "wardrobe", 100, 60, 210),
            payload_item("bed-1", "bed", 152, 200, 55),
            payload_item("table-1", "bedside-table", 45, 40, 55),
        ],
        room=engine_room,
        floorplan=floorplan,
        room_type="bedroom",
    )
    by_type = {obj["normalized_type"]: obj for obj in objects}
    bed = by_type["bed"]
    assert not bed.get("placement_failed"), bed.get("placement_reason")
    bed_top = bed["position_cm"]["z"] + depth / 2 + bed["footprint_cm"]["depth"] / 2
    assert bed_top >= depth - 10, f"床頭應貼北牆，實際上緣在 {bed_top:.0f}"


# --- 餐廳：置中錨點＋環繞入座 -----------------------------------------------


def test_dining_table_sits_at_room_center_not_against_a_wall():
    room = bare_room(width=340, depth=300)
    result = place_room(
        room,
        "dining_room",
        [(item("dining-table", "餐桌", 140, 80, height=75), "dining-table_1")],
    )
    table = result["placed"][0]
    assert not touches_wall(table, room), "餐桌是唯一刻意置中的錨點"
    assert table.pos_x == pytest.approx(170, abs=35)
    assert table.pos_y == pytest.approx(150, abs=35)


def test_four_dining_chairs_surround_the_table_facing_it():
    room = bare_room(width=380, depth=340)
    items = [(item("dining-table", "餐桌", 140, 80, height=75), "dining-table_1")]
    for i in range(4):
        items.append((item("dining-chair", "餐椅", 48, 52, height=82), f"dining-chair_{i+1}"))
    result = place_room(room, "dining_room", items)
    assert not result["failed"], result["failed"]
    table = next(p for p in result["placed"] if p.catalog.type == "dining-table")
    chairs = [p for p in result["placed"] if p.catalog.type == "dining-chair"]
    assert len(chairs) == 4
    for chair in chairs:
        # 正面向量必須指向桌心（內積為正）
        front = {0: (0, 1), 90: (-1, 0), 180: (0, -1), 270: (1, 0)}[int(chair.rotation) % 360]
        to_table = (table.pos_x - chair.pos_x, table.pos_y - chair.pos_y)
        assert front[0] * to_table[0] + front[1] * to_table[1] > 0, "餐椅沒有朝向桌心"
    # 140 桌的現實配置是長邊 2+2 對坐；至少要出現兩個相對的方位。
    sides = set()
    for chair in chairs:
        dx = chair.pos_x - table.pos_x
        dy = chair.pos_y - table.pos_y
        sides.add("x" + ("+" if dx > 0 else "-") if abs(dx) > abs(dy) else "y" + ("+" if dy > 0 else "-"))
    assert {"y+", "y-"} <= sides or {"x+", "x-"} <= sides


def test_six_chairs_fit_around_a_long_table():
    room = bare_room(width=460, depth=380)
    items = [(item("dining-table", "餐桌", 180, 90, height=75), "dining-table_1")]
    for i in range(6):
        items.append((item("dining-chair", "餐椅", 48, 52, height=82), f"dining-chair_{i+1}"))
    result = place_room(room, "dining_room", items)
    chairs = [p for p in result["placed"] if p.catalog.type == "dining-chair"]
    assert len(chairs) == 6, result["failed"]


# --- 書房：桌貼牆、椅面桌 ---------------------------------------------------


def test_office_chair_faces_the_desk():
    room = bare_room(width=300, depth=260)
    result = place_room(
        room,
        "workspace",
        [
            (item("desk", "書桌", 120, 60, height=75), "desk_1"),
            (item("office-chair", "辦公椅", 60, 60, height=90), "office-chair_1"),
        ],
    )
    assert not result["failed"], result["failed"]
    desk = next(p for p in result["placed"] if p.catalog.type == "desk")
    chair = next(p for p in result["placed"] if p.catalog.type == "office-chair")
    assert touches_wall(desk, room)
    # 椅子的正面向量指向書桌
    front = {0: (0, 1), 90: (-1, 0), 180: (0, -1), 270: (1, 0)}[int(chair.rotation) % 360]
    to_desk = (desk.pos_x - chair.pos_x, desk.pos_y - chair.pos_y)
    assert front[0] * to_desk[0] + front[1] * to_desk[1] > 0, "辦公椅沒有面向書桌"


# --- 玄關 --------------------------------------------------------------------


def test_entry_shoe_cabinet_hugs_a_wall():
    room = bare_room(width=200, depth=180)
    result = place_room(
        room,
        "entry",
        [(item("shoe-cabinet", "鞋櫃", 80, 35, height=120), "shoe-cabinet_1")],
    )
    assert not result["failed"], result["failed"]
    assert touches_wall(result["placed"][0], room)
