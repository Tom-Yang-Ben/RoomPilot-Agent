"""
clearance.py 淨空運算測試

涵蓋:無淨空家具、淨空撞牆、淨空撞家具本體、
淨空互撞、反向檢查(本體壓到別人的淨空)、旋轉後淨空方向正確

單位:一律公分(cm),與引擎契約一致。
"""
import pytest

from backend.engine.models import (
    ClearanceSpec,
    ClearanceZone,
    FurnitureCatalogItem,
    PlacedFurniture,
    Room,
    Wall,
)
from backend.engine.clearance_defaults import (
    catalog_with_default_clearance,
    default_clearance_for_type,
)
from backend.engine.clearance import (
    clearance_conflict,
    clearance_polygon,
    check_placement_with_clearance,
    validate_placement_with_clearance,
)


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
    w1 = make_wardrobe(pos_x=250, pos_y=50, rotation=0)       # 淨空 80~140
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


# ---------- v1.2 雙層淨空、結構化結果與配套家具 ----------

def test_clearance_zone_keeps_legacy_depth_and_supports_ideal_floor() -> None:
    legacy = ClearanceZone(side="front", depth=60)
    assert legacy.kind == "operation"
    assert legacy.floor_cm == pytest.approx(60)
    assert legacy.ideal_cm == pytest.approx(60)
    assert legacy.depth == pytest.approx(60)

    dual = ClearanceZone(
        side="front",
        kind="operation",
        ideal_cm=90,
        floor_cm=50,
        reason="門扇開啟",
    )
    assert dual.depth == pytest.approx(50)
    assert dual.floor_cm == pytest.approx(50)
    assert dual.ideal_cm == pytest.approx(90)


def test_ideal_clearance_conflict_is_a_structured_compression_warning(room) -> None:
    wardrobe = PlacedFurniture(
        id="wardrobe_1",
        catalog=FurnitureCatalogItem(
            type="wardrobe",
            name="衣櫃",
            width=150,
            depth=60,
            clearance=ClearanceZone(
                side="front",
                kind="operation",
                ideal_cm=90,
                floor_cm=50,
                reason="門扇開啟",
            ),
        ),
        pos_x=250,
        pos_y=50,
    )
    blocker = PlacedFurniture(
        id="stool_1",
        catalog=FurnitureCatalogItem(type="stool", name="矮凳", width=50, depth=20),
        pos_x=250,
        pos_y=155,
    )

    result = validate_placement_with_clearance(wardrobe, room, [blocker])

    assert result.legal is True
    assert result.errors == []
    assert result.warnings[0].code == "clearance_compressed"
    assert result.warnings[0].item_id == "wardrobe_1"
    assert result.warnings[0].related_item_id == "stool_1"
    assert result.warnings[0].required_cm == pytest.approx(90)
    assert result.warnings[0].available_cm == pytest.approx(65, abs=0.2)
    assert result.warnings[0].shortfall_cm == pytest.approx(25, abs=0.2)


def test_floor_clearance_conflict_returns_structured_error(room) -> None:
    wardrobe = PlacedFurniture(
        id="wardrobe_1",
        catalog=FurnitureCatalogItem(
            type="wardrobe",
            name="衣櫃",
            width=150,
            depth=60,
            clearance=ClearanceZone(
                side="front", kind="operation", ideal_cm=90, floor_cm=50
            ),
        ),
        pos_x=250,
        pos_y=50,
    )
    blocker = PlacedFurniture(
        id="stool_1",
        catalog=FurnitureCatalogItem(type="stool", name="矮凳", width=50, depth=20),
        pos_x=250,
        pos_y=120,
    )

    result = validate_placement_with_clearance(wardrobe, room, [blocker])

    assert result.legal is False
    issue = result.errors[0]
    assert issue.code == "clearance_body_conflict"
    assert issue.item_id == "wardrobe_1"
    assert issue.related_item_id == "stool_1"
    assert issue.required_cm == pytest.approx(50)
    assert issue.available_cm == pytest.approx(30, abs=0.2)
    assert issue.shortfall_cm == pytest.approx(20, abs=0.2)
    assert check_placement_with_clearance(wardrobe, room, [blocker]) == issue.message_zh


def test_access_zone_warns_but_companion_pair_is_exempt(room) -> None:
    desk = PlacedFurniture(
        id="desk_1",
        catalog=FurnitureCatalogItem(
            type="desk",
            name="書桌",
            width=120,
            depth=60,
            clearance=ClearanceZone(
                side="front", kind="access", ideal_cm=105, floor_cm=75, reason="拉椅入座"
            ),
        ),
        pos_x=250,
        pos_y=100,
    )
    chair = PlacedFurniture(
        id="chair_1",
        catalog=FurnitureCatalogItem(type="office-chair", name="辦公椅", width=50, depth=50),
        pos_x=250,
        pos_y=165,
    )

    without_relation = validate_placement_with_clearance(desk, room, [chair])
    with_relation = validate_placement_with_clearance(
        desk,
        room,
        [chair],
        companion_pairs={frozenset(("desk_1", "chair_1"))},
    )

    assert without_relation.legal is True
    assert [issue.code for issue in without_relation.warnings] == ["access_body_conflict"]
    assert with_relation.legal is True
    assert with_relation.warnings == []


def test_companion_pair_never_bypasses_operation_clearance(room) -> None:
    wardrobe = make_wardrobe(pos_x=250, pos_y=50)
    chair = PlacedFurniture(
        id="chair_1",
        catalog=FurnitureCatalogItem(type="office-chair", name="辦公椅", width=50, depth=50),
        pos_x=250,
        pos_y=110,
    )

    result = validate_placement_with_clearance(
        wardrobe,
        room,
        [chair],
        companion_pairs={frozenset(("wardrobe_1", "chair_1"))},
    )

    assert result.legal is False
    assert result.errors[0].code == "clearance_body_conflict"


def test_side_by_side_clearance_zones_that_only_touch_do_not_conflict(room) -> None:
    left = PlacedFurniture(
        id="wardrobe_left",
        catalog=FurnitureCatalogItem(
            type="wardrobe", name="左衣櫃", width=100, depth=60,
            clearance=ClearanceZone(side="front", depth=50),
        ),
        pos_x=100,
        pos_y=50,
    )
    right = PlacedFurniture(
        id="wardrobe_right",
        catalog=FurnitureCatalogItem(
            type="wardrobe", name="右衣櫃", width=100, depth=60,
            clearance=ClearanceZone(side="front", depth=50),
        ),
        pos_x=200,
        pos_y=50,
    )

    assert clearance_conflict(left, room, [right]) is None


def test_front_clearance_rotates_ninety_degrees_toward_local_front() -> None:
    wardrobe = make_wardrobe(pos_x=250, pos_y=200, rotation=90)

    zone = clearance_polygon(wardrobe)

    assert zone is not None
    min_x, min_y, max_x, max_y = zone.bounds
    assert min_x == pytest.approx(160)
    assert max_x == pytest.approx(220)
    assert min_y == pytest.approx(125)
    assert max_y == pytest.approx(275)


def test_original_furniture_type_gets_its_own_default_clearance() -> None:
    drawer = default_clearance_for_type("chests-of-drawer")
    sideboard = default_clearance_for_type("sideboard")
    sofa_bed = default_clearance_for_type("sofa-bed")

    assert drawer is not None and drawer.floor_cm == pytest.approx(60)
    assert sideboard is not None and sideboard.floor_cm == pytest.approx(60)
    assert sofa_bed is None


def test_explicit_rag_clearance_wins_over_type_default() -> None:
    explicit = ClearanceZone(
        side="front", kind="operation", ideal_cm=30, floor_cm=25, reason="推拉門"
    )
    catalog = FurnitureCatalogItem(
        type="wardrobe", name="推拉門衣櫃", width=120, depth=60, clearance=explicit
    )

    resolved = catalog_with_default_clearance(catalog)

    assert resolved is catalog
    assert resolved.clearance is explicit


def test_type_default_is_opt_in_and_does_not_mutate_catalog() -> None:
    catalog = FurnitureCatalogItem(
        type="mirror-cabinet", name="鏡櫃", width=60, depth=15
    )

    resolved = catalog_with_default_clearance(catalog)

    assert catalog.clearance is None
    assert resolved is not catalog
    assert resolved.clearance is not None
    assert resolved.clearance.floor_cm == pytest.approx(45)


# ---------- v1.3 床至少一側、餐桌有椅才留面 ----------

def _bed_item(pos_x=200, pos_y=150, rotation=0) -> PlacedFurniture:
    return PlacedFurniture(
        id="bed_1",
        catalog=FurnitureCatalogItem(
            type="bed",
            name="雙人床",
            width=150,
            depth=200,
            clearance_spec=ClearanceSpec(
                mode="any",
                enforce_floor=True,
                zones=[
                    ClearanceZone(side="left", kind="access", ideal_cm=75, floor_cm=60, reason="上下床"),
                    ClearanceZone(side="right", kind="access", ideal_cm=75, floor_cm=60, reason="上下床"),
                ],
            ),
        ),
        pos_x=pos_x,
        pos_y=pos_y,
        rotation=rotation,
    )


def test_bed_passes_when_only_one_long_side_keeps_floor_clearance(room) -> None:
    """床可靠牆：左右只要一側達最低 60cm 即可。"""
    bed = _bed_item(pos_x=85, pos_y=150)  # 左側貼近邊界，右側應仍可留空
    result = validate_placement_with_clearance(bed, room, [])
    assert result.legal is True


def test_bed_fails_when_both_long_sides_are_blocked(room) -> None:
    bed = _bed_item(pos_x=250, pos_y=200)
    left_blocker = PlacedFurniture(
        id="box_left",
        catalog=FurnitureCatalogItem(type="storage-boxes-basket", name="左箱", width=40, depth=180),
        pos_x=115,
        pos_y=200,
    )
    right_blocker = PlacedFurniture(
        id="box_right",
        catalog=FurnitureCatalogItem(type="storage-boxes-basket", name="右箱", width=40, depth=180),
        pos_x=385,
        pos_y=200,
    )
    result = validate_placement_with_clearance(bed, room, [left_blocker, right_blocker])
    assert result.legal is False
    assert result.errors[0].code == "access_any_side_unmet"
    assert result.errors[0].required_cm == pytest.approx(60)


def test_bed_foot_block_does_not_count_as_side_clearance_failure(room) -> None:
    """床尾被擋不算『左右至少一側』失敗。"""
    bed = _bed_item(pos_x=250, pos_y=150)
    foot_blocker = PlacedFurniture(
        id="bench_1",
        catalog=FurnitureCatalogItem(type="stool-bench", name="床尾凳", width=100, depth=40),
        pos_x=250,
        pos_y=280,
    )
    result = validate_placement_with_clearance(bed, room, [foot_blocker])
    assert result.legal is True


def test_bed_warns_when_best_side_only_meets_floor_not_ideal(room) -> None:
    bed = _bed_item(pos_x=250, pos_y=200)
    # 左側完全堵住；右側只留約 65cm：達最低 60、未達理想 75。
    left_blocker = PlacedFurniture(
        id="cabinet_left",
        catalog=FurnitureCatalogItem(type="sideboard", name="左櫃", width=40, depth=180),
        pos_x=145,
        pos_y=200,
    )
    right_wall_proxy = PlacedFurniture(
        id="cabinet_right",
        catalog=FurnitureCatalogItem(type="sideboard", name="右櫃", width=40, depth=180),
        pos_x=410,
        pos_y=200,
    )
    result = validate_placement_with_clearance(bed, room, [left_blocker, right_wall_proxy])
    assert result.legal is True
    assert any(issue.code == "clearance_compressed" for issue in result.warnings)


def test_sofa_bed_default_has_no_bed_side_rule() -> None:
    assert default_clearance_for_type("sofa-bed") is None
    catalog = catalog_with_default_clearance(
        FurnitureCatalogItem(type="sofa-bed", name="沙發床", width=180, depth=90)
    )
    assert catalog.clearance is None
    assert catalog.clearance_spec is None


def test_dining_table_requires_declared_chair_sides_only(room) -> None:
    table = PlacedFurniture(
        id="table_1",
        catalog=FurnitureCatalogItem(
            type="dining-table",
            name="餐桌",
            width=140,
            depth=80,
            clearance_spec=ClearanceSpec(
                mode="all",
                enforce_floor=True,
                zones=[
                    ClearanceZone(side="front", kind="access", ideal_cm=75, floor_cm=60, reason="拉椅入座"),
                    ClearanceZone(side="back", kind="access", ideal_cm=75, floor_cm=60, reason="拉椅入座"),
                ],
            ),
        ),
        pos_x=250,
        pos_y=200,
    )
    # 左右貼牆代理物：因為沒宣告 left/right，不應因此失敗
    left = PlacedFurniture(
        id="wall_proxy_l",
        catalog=FurnitureCatalogItem(type="sideboard", name="左牆櫃", width=20, depth=70),
        pos_x=160,
        pos_y=200,
    )
    right = PlacedFurniture(
        id="wall_proxy_r",
        catalog=FurnitureCatalogItem(type="sideboard", name="右牆櫃", width=20, depth=70),
        pos_x=340,
        pos_y=200,
    )
    result = validate_placement_with_clearance(table, room, [left, right])
    assert result.legal is True


def test_dining_chair_companion_may_occupy_table_access_zone(room) -> None:
    table = PlacedFurniture(
        id="table_1",
        catalog=FurnitureCatalogItem(
            type="dining-table",
            name="餐桌",
            width=140,
            depth=80,
            clearance_spec=ClearanceSpec(
                mode="all",
                enforce_floor=True,
                zones=[
                    ClearanceZone(side="front", kind="access", ideal_cm=75, floor_cm=60, reason="拉椅入座"),
                ],
            ),
        ),
        pos_x=250,
        pos_y=200,
    )
    chair = PlacedFurniture(
        id="chair_1",
        catalog=FurnitureCatalogItem(type="dining-chair", name="餐椅", width=45, depth=50),
        pos_x=250,
        pos_y=200 + 40 + 30,
    )
    blocked = validate_placement_with_clearance(table, room, [chair])
    allowed = validate_placement_with_clearance(
        table,
        room,
        [chair],
        companion_pairs={frozenset(("table_1", "chair_1"))},
    )
    assert blocked.legal is False
    assert allowed.legal is True


def test_bed_and_dining_defaults_use_clearance_spec() -> None:
    bed = catalog_with_default_clearance(
        FurnitureCatalogItem(type="bed", name="床", width=150, depth=200)
    )
    dining = catalog_with_default_clearance(
        FurnitureCatalogItem(type="dining-table", name="餐桌", width=140, depth=80)
    )
    assert bed.clearance_spec is not None
    assert bed.clearance_spec.mode == "any"
    assert {zone.side for zone in bed.clearance_spec.zones} == {"left", "right"}
    assert dining.clearance_spec is not None
    assert dining.clearance_spec.mode == "all"
    assert {zone.side for zone in dining.clearance_spec.zones} == {"front", "back", "left", "right"}
