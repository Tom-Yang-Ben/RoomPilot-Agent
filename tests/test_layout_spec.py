"""柵格擺位引擎規格測試 —— 對照 `docs/擺位計算邏輯.md`(公分版)。

§13 的手算驗證範例是第一組驗收數字:規格原文以 mm 寫,本 repo 統一公分,
常數整除 10,故座標亦整除 10(床心 (2000,1050)mm → (200,105)cm)。
"""
from __future__ import annotations

import math

import pytest

from backend.agent.adjust import move_placement, rotate_placement
from backend.agent.clearance import CLEARANCE_OF, clearance_conflict, zone_obb
from backend.agent.furnish import furnish_room
from backend.engine.constraints import BlockedMasks, blocked_masks
from backend.engine.layout_model import (
    Edge,
    Placement,
    RoomContext,
    Template,
    polygon_centroid,
    room_edges,
)
from backend.engine.obb import Obb, facing_deg, front_vector, obb_blocked, side_vector, stamp_obb
from backend.engine.raster import build_occupancy, make_grid, room_mask
from backend.engine.rules import anchor_ts, candidate_edges, try_against_wall

# §13 輸入:矩形房 (0,0)-(400,300) CCW,室內在左
ROOM = [(0.0, 0.0), (400.0, 0.0), (400.0, 300.0), (0.0, 300.0)]
PLAN = {"bbox": [0.0, 0.0, 400.0, 300.0], "walls": [], "wall_polygons": [], "doors": [], "windows": []}


def _ctx(label: str = "bedroom", polygon=None) -> RoomContext:
    polygon = polygon or ROOM
    grid = build_occupancy({**PLAN, "bbox": [
        min(p[0] for p in polygon), min(p[1] for p in polygon),
        max(p[0] for p in polygon), max(p[1] for p in polygon),
    ]})
    masks = blocked_masks(grid, polygon)
    return RoomContext(
        grid=grid,
        masks=masks,
        edges=room_edges(polygon),
        centroid=polygon_centroid(polygon),
        room_id="r1",
        label=label,
    )


# ── §2.1 三個互為逆運算的向量 ───────────────────────────────────────
@pytest.mark.parametrize("n", [(0.0, 1.0), (1.0, 0.0), (0.0, -1.0), (-1.0, 0.0)])
def test_facing_deg_and_front_vector_are_inverse(n):
    got = front_vector(facing_deg(n))
    assert got[0] == pytest.approx(n[0], abs=1e-9)
    assert got[1] == pytest.approx(n[1], abs=1e-9)


def test_side_vector_is_front_rotated():
    for deg in (0.0, 37.0, 90.0, 180.0, 271.5):
        f = front_vector(deg)
        s = side_vector(deg)
        assert s[0] == pytest.approx(-f[1], abs=1e-9)
        assert s[1] == pytest.approx(f[0], abs=1e-9)


# ── §13 ① 邊排序 ───────────────────────────────────────────────────
def test_edge_sort_matches_worked_example():
    edges = room_edges(ROOM)
    ordered = candidate_edges(edges, width=150.0)
    keys = [(round(-e.length), e.mid[1], e.mid[0]) for e in ordered]
    assert keys == [
        (-400, 0.0, 200.0),        # e0 (0,0)→(400,0)
        (-400, 300.0, 200.0),      # e2 (400,300)→(0,300)
        (-300, 150.0, 0.0),        # e3 (0,300)→(0,0)
        (-300, 150.0, 400.0),      # e1 (400,0)→(400,300)
    ]


# ── §13 ② e0 的室內法線與朝向 ──────────────────────────────────────
def test_e0_inward_normal_and_rotation():
    e0 = room_edges(ROOM)[0]
    inward = e0.inward()
    assert inward == pytest.approx((0.0, 1.0), abs=1e-12)
    assert facing_deg(inward) == pytest.approx(180.0)
    assert front_vector(180.0) == pytest.approx((0.0, 1.0), abs=1e-12)


# ── §13 ③ 錨點序列 ─────────────────────────────────────────────────
def test_anchor_ts_matches_worked_example():
    ts = anchor_ts(length=400.0, width=150.0)
    assert ts[:5] == (0.5, 0.35, 0.65, 0.2, 0.8)
    # lo=0.2 hi=0.8 n=16 → 步距 0.0375;去掉與五定點重合者後由中心向外
    assert ts[5] == pytest.approx(0.4625)
    assert ts[6] == pytest.approx(0.5375)
    assert ts[7] == pytest.approx(0.425)
    assert ts[8] == pytest.approx(0.575)
    assert len(ts) == 5 + 12


def test_anchor_ts_falls_back_to_five_fixed_points_when_edge_too_short():
    assert anchor_ts(length=100.0, width=150.0) == (0.5, 0.35, 0.65, 0.2, 0.8)


# ── §13 ④ 床的落點 ─────────────────────────────────────────────────
def test_bed_anchor_matches_worked_example():
    ctx = _ctx("bedroom")
    bed = Template(kind="bed", w=150.0, d=200.0, height=120.0)
    found = try_against_wall(ctx, bed)
    assert found is not None
    point, normal, rotation = found
    assert point == pytest.approx((200.0, 105.0))
    assert normal == pytest.approx((0.0, 1.0), abs=1e-12)
    assert rotation == pytest.approx(180.0)
    # 背面 y = 105 − 100 = 5 → 離牆 5cm(規格 WALL_GAP)
    assert point[1] - bed.d / 2 == pytest.approx(5.0)


# ── §13 ⑤ 床頭櫃 ───────────────────────────────────────────────────
def test_nightstand_pair_matches_worked_example():
    ctx = _ctx("bedroom")
    furnish_room(ctx, [
        Template(kind="bed", w=150.0, d=200.0, height=120.0),
        Template(kind="nightstand", w=45.0, d=40.0, height=50.0, count=2),
    ])
    stands = sorted((p for p in ctx.placements if p.kind == "nightstand"), key=lambda p: p.cx)
    assert len(stands) == 2
    assert (stands[1].cx, stands[1].cy) == pytest.approx((302.5, 25.0))
    assert (stands[0].cx, stands[0].cy) == pytest.approx((97.5, 25.0))
    # 背線與床背齊:25 − 20 = 5
    assert stands[0].cy - stands[0].d / 2 == pytest.approx(5.0)
    # 側向間隙 = 302.5 − 22.5 − (200 + 75) = 5
    assert stands[1].cx - stands[1].w / 2 - (200.0 + 150.0 / 2) == pytest.approx(5.0)


# ── §13 ⑥ 床頭櫃的淨空區 ───────────────────────────────────────────
def test_nightstand_clearance_zone_matches_worked_example():
    ns = Placement(id="r1-nightstand-0", kind="nightstand", cx=302.5, cy=25.0,
                   w=45.0, d=40.0, rotation_deg=180.0, height=50.0)
    side, depth = CLEARANCE_OF["nightstand"]
    zone = zone_obb(ns, side, depth)
    assert (zone.cx, zone.cy) == pytest.approx((302.5, 62.5))
    assert (zone.w, zone.d) == pytest.approx((45.0, 35.0))
    assert zone.rad == pytest.approx(math.pi)


# ── §3 柵格化 ──────────────────────────────────────────────────────
def test_grid_dimensions_follow_spec():
    grid = make_grid([0.0, 0.0, 400.0, 300.0])
    assert grid.cell == 5.0                       # DEFAULT_CELL_CM
    assert (grid.origin_x, grid.origin_y) == (-10.0, -10.0)   # −2·cell
    assert grid.nx == math.ceil(400 / 5) + 5
    assert grid.ny == math.ceil(300 / 5) + 5


def test_cell_grows_when_axis_would_exceed_cap():
    grid = make_grid([0.0, 0.0, 12000.0, 100.0])
    assert grid.cell == pytest.approx(12000 / 1200)


def test_segment_stroke_marks_cells_within_radius():
    grid = make_grid([0.0, 0.0, 100.0, 100.0])
    plan = {"bbox": [0.0, 0.0, 100.0, 100.0], "walls": [(0.0, 50.0, 100.0, 50.0)]}
    occ = build_occupancy(plan).occ
    assert occ.any()
    # 牆厚 12cm → 半徑 6cm,y=50 附近整列被畫上
    marked_rows = {int(iy) for iy in occ.nonzero()[0]}
    assert len(marked_rows) >= 2


def test_room_mask_is_drawn_on_a_separate_canvas():
    grid = build_occupancy(PLAN)
    before = grid.occ.copy()
    room_mask(grid, ROOM)
    assert (grid.occ == before).all()             # 不得動到 grid.occ


# ── §5 OBB 與碰撞 ──────────────────────────────────────────────────
def test_obb_blocked_returns_true_when_out_of_grid():
    grid = make_grid([0.0, 0.0, 100.0, 100.0])
    outside = Obb(cx=9999.0, cy=9999.0, w=10.0, d=10.0)
    assert obb_blocked(grid.blank(), grid, outside) is True


def test_obb_blocked_detects_stamped_body():
    grid = make_grid([0.0, 0.0, 400.0, 300.0])
    canvas = grid.blank()
    stamp_obb(canvas, grid, Obb(cx=200.0, cy=150.0, w=100.0, d=50.0))
    assert obb_blocked(canvas, grid, Obb(cx=200.0, cy=150.0, w=20.0, d=20.0)) is True
    assert obb_blocked(canvas, grid, Obb(cx=50.0, cy=50.0, w=20.0, d=20.0)) is False


# ── §4 禁放遮罩 ────────────────────────────────────────────────────
def test_blocked_band_adds_window_strip_only_for_tall_items():
    grid = build_occupancy(PLAN)
    masks = blocked_masks(grid, ROOM, windows=[(0.0, 0.0, 400.0, 0.0)])
    assert masks.band.sum() > masks.low.sum()
    assert masks.for_height(50.0) is masks.low       # 矮件貼窗合法
    assert masks.for_height(90.0) is masks.band      # ≥ WINDOW_SILL_CM 受窗前帶約束
    assert masks.for_height(200.0) is masks.band


def test_outside_room_is_always_blocked():
    grid = build_occupancy(PLAN)
    masks = blocked_masks(grid, ROOM)
    # 房外一點:¬room_mask 讓它必然禁放 —— 家具不會被移出自己房間的根本原因
    assert obb_blocked(masks.low, grid, Obb(cx=-5.0, cy=150.0, w=10.0, d=10.0)) is True


# ── §7.1 living ────────────────────────────────────────────────────
def test_living_rule_places_sofa_rug_table_and_tv():
    ctx = _ctx("living")
    furnish_room(ctx, [
        Template(kind="sofa", w=200.0, d=90.0, height=80.0),
        Template(kind="rug", w=200.0, d=140.0, height=1.0),
        Template(kind="coffee_table", w=100.0, d=50.0, height=40.0),
        Template(kind="tv", w=140.0, d=40.0, height=50.0),
    ])
    kinds = {p.kind for p in ctx.placements}
    assert "sofa" in kinds
    sofa = ctx.find("sofa")
    table = ctx.find("coffee_table")
    assert table is not None
    # 茶几在沙發正前方 TABLE_GAP_CM 走距處
    f = front_vector(sofa.rotation_deg)
    gap = ((table.cx - sofa.cx) * f[0] + (table.cy - sofa.cy) * f[1]) - sofa.d / 2 - table.d / 2
    assert gap == pytest.approx(45.0)


def test_rug_is_registered_but_not_stamped():
    ctx = _ctx("living")
    furnish_room(ctx, [
        Template(kind="sofa", w=200.0, d=90.0, height=80.0),
        Template(kind="rug", w=200.0, d=140.0, height=1.0),
    ])
    rug = ctx.find("rug")
    assert rug is not None
    # 地毯不烙印 → 其位置在 ctx.placed 上必須是空的(允許家具壓上去)
    assert obb_blocked(ctx.placed, ctx.grid, Obb(rug.cx, rug.cy, 10.0, 10.0)) is False


# ── §7.3 dining ────────────────────────────────────────────────────
def test_dining_table_sits_at_centroid_with_chairs_facing_it():
    ctx = _ctx("dining")
    furnish_room(ctx, [
        Template(kind="dining_table", w=140.0, d=80.0, height=75.0),
        Template(kind="dining_chair", w=45.0, d=45.0, height=90.0, count=4),
    ])
    table = ctx.find("dining_table")
    assert table is not None
    assert (table.cx, table.cy) == pytest.approx(ctx.centroid)
    chairs = [p for p in ctx.placements if p.kind == "dining_chair"]
    assert len(chairs) == 4
    # 椅子沿桌邊有 ±w/4 偏移,正面不指向桌心而是垂直桌緣;驗的是「面向那一側」:
    # 正面在桌心方向的投影 = 桌深/2 + 椅深/2 + CHAIR_GAP。
    for chair in chairs:
        f = front_vector(chair.rotation_deg)
        to_table = (table.cx - chair.cx, table.cy - chair.cy)
        assert f[0] * to_table[0] + f[1] * to_table[1] == pytest.approx(
            table.d / 2 + chair.d / 2 + 3.0
        )


# ── §8.1 副件寧缺勿亂 ──────────────────────────────────────────────
def test_companion_is_skipped_when_anchor_missing():
    ctx = _ctx("default")
    furnish_room(ctx, [Template(kind="office_chair", w=50.0, d=50.0, height=90.0)])
    assert ctx.placements == []                # 絕不退回泛用靠牆
    assert any("沒有可依附的主件" in note for note in ctx.notes)


def test_companion_lands_in_front_of_its_anchor():
    ctx = _ctx("default")
    furnish_room(ctx, [
        Template(kind="desk", w=120.0, d=60.0, height=75.0),
        Template(kind="office_chair", w=50.0, d=50.0, height=90.0),
    ])
    desk = ctx.find("desk")
    chair = ctx.find("office_chair")
    assert desk is not None and chair is not None
    f = front_vector(desk.rotation_deg)
    gap = ((chair.cx - desk.cx) * f[0] + (chair.cy - desk.cy) * f[1]) - desk.d / 2 - chair.d / 2
    assert gap == pytest.approx(3.0)           # CHAIR_GAP_CM
    # 椅子回頭面向書桌:兩者正面反平行(比向量而非角度值,避免 359.999… 的環繞噪音)
    cf = front_vector(chair.rotation_deg)
    assert (cf[0], cf[1]) == pytest.approx((-f[0], -f[1]), abs=1e-9)


def test_companion_count_is_never_expanded():
    ctx = _ctx("default")
    furnish_room(ctx, [
        Template(kind="desk", w=120.0, d=60.0, height=75.0),
        Template(kind="office_chair", w=50.0, d=50.0, height=90.0, count=3),
    ])
    assert len([p for p in ctx.placements if p.kind == "office_chair"]) == 1


# ── §8.2 泛用件 ────────────────────────────────────────────────────
def test_generic_items_are_placed_count_times_and_stop_on_failure():
    ctx = _ctx("default")
    furnish_room(ctx, [Template(kind="bookcase", w=80.0, d=35.0, height=200.0, count=3)])
    assert len(ctx.placements) == 3
    for placement in ctx.placements:
        assert not obb_blocked(ctx.masks.for_height(200.0), ctx.grid, placement.obb())


# ── §9 開合淨空 ────────────────────────────────────────────────────
def test_clearance_zone_sides_follow_spec_geometry():
    p = Placement(id="x", kind="wardrobe", cx=100.0, cy=100.0, w=120.0, d=60.0, rotation_deg=0.0)
    front = zone_obb(p, "front", 60.0)
    back = zone_obb(p, "back", 60.0)
    right = zone_obb(p, "right", 60.0)
    left = zone_obb(p, "left", 60.0)
    # rotation 0 → f = (0, −1)
    assert (front.cx, front.cy) == pytest.approx((100.0, 100.0 - 60.0))
    assert (back.cx, back.cy) == pytest.approx((100.0, 100.0 + 60.0))
    assert (front.w, front.d) == pytest.approx((120.0, 60.0))   # front/back 與家具同寬
    assert (right.w, right.d) == pytest.approx((60.0, 60.0))    # left/right 與家具同深
    assert (right.cx, right.cy) == pytest.approx((190.0, 100.0))
    assert (left.cx, left.cy) == pytest.approx((10.0, 100.0))


def test_items_without_clearance_requirement_always_pass():
    ctx = _ctx("living")
    sofa = Placement(id="s", kind="sofa", cx=200.0, cy=150.0, w=200.0, d=90.0)
    assert clearance_conflict(ctx.grid, ctx.masks.low, sofa, []) is None


def test_clearance_conflict_messages_are_traditional_chinese():
    ctx = _ctx("bedroom")
    # 衣櫃背對牆但正面淨空頂到對牆:房深 300,衣櫃放中央、淨空 60
    wardrobe = Placement(id="w", kind="wardrobe", cx=200.0, cy=32.5, w=120.0, d=55.0,
                         rotation_deg=180.0, height=200.0, name="衣櫃")
    blocker = Placement(id="b", kind="cabinet", cx=200.0, cy=110.0, w=120.0, d=40.0,
                        rotation_deg=180.0, height=90.0, name="矮櫃")
    message = clearance_conflict(ctx.grid, ctx.masks.low, wardrobe, [blocker])
    assert message == "「衣櫃」的開合空間與「矮櫃」衝突"


# ── §10 微調 ───────────────────────────────────────────────────────
def _adjust_fixture():
    ctx = _ctx("bedroom")
    bed = Placement(id="r1-bed-0", kind="bed", cx=200.0, cy=105.0, w=150.0, d=200.0,
                    rotation_deg=180.0, height=120.0, name="床")
    return ctx, [bed]


def test_move_with_zero_delta_is_success_not_failure():
    ctx, placements = _adjust_fixture()
    result = move_placement(ctx.grid, ctx.masks, placements, "r1-bed-0", 0, 0)
    assert result.ok is True
    assert result.placements[0].cx == 200.0


def test_move_is_axis_separated_and_partial_success_counts():
    ctx, placements = _adjust_fixture()
    # X 可走、Y 往牆裡走不了 → 仍算成功,只有 X 生效
    result = move_placement(ctx.grid, ctx.masks, placements, "r1-bed-0", 20, -500)
    assert result.ok is True
    assert result.placements[0].cx == pytest.approx(220.0)
    assert result.placements[0].cy == pytest.approx(105.0)


def test_move_fails_when_both_axes_blocked():
    ctx, placements = _adjust_fixture()
    result = move_placement(ctx.grid, ctx.masks, placements, "r1-bed-0", -5000, -5000)
    assert result.ok is False
    assert result.reason
    assert result.placements[0].cx == 200.0        # 原清單未變動


def test_rotate_normalises_and_keeps_original_on_failure():
    ctx, placements = _adjust_fixture()
    ok = rotate_placement(ctx.grid, ctx.masks, placements, "r1-bed-0", 360 + 180)
    assert ok.ok is True
    assert ok.placements[0].rotation_deg == pytest.approx(180.0)

    blocked = rotate_placement(ctx.grid, ctx.masks, placements, "r1-bed-0", 90)
    if not blocked.ok:
        assert blocked.placements[0].rotation_deg == pytest.approx(180.0)


def test_adjust_never_mutates_in_place():
    ctx, placements = _adjust_fixture()
    original = placements[0]
    move_placement(ctx.grid, ctx.masks, placements, "r1-bed-0", 20, 0)
    assert original.cx == 200.0                    # dataclasses.replace,不就地改


# ── §12 決定性 ─────────────────────────────────────────────────────
def test_same_input_gives_same_output():
    templates = [
        Template(kind="bed", w=150.0, d=200.0, height=120.0),
        Template(kind="nightstand", w=45.0, d=40.0, height=50.0, count=2),
        Template(kind="wardrobe", w=120.0, d=60.0, height=200.0),
    ]
    first = furnish_room(_ctx("bedroom"), templates).placements
    second = furnish_room(_ctx("bedroom"), templates).placements
    assert [(p.kind, p.cx, p.cy, p.rotation_deg) for p in first] == \
           [(p.kind, p.cx, p.cy, p.rotation_deg) for p in second]
