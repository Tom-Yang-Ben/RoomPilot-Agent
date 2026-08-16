"""柵格擺位引擎規格測試；公開邊界見 `backend/engine/README.md`。

§13 的手算驗證範例是第一組驗收數字:規格原文以 mm 寫,本 repo 統一公分,
常數整除 10,故座標亦整除 10(床心 (2000,1050)mm → (200,105)cm)。
"""
from __future__ import annotations

import math

import pytest

from backend.engine.constraints import blocked_masks
from backend.engine.layout_model import (
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

\n