"""靠牆錨定掃描與房型規則 —— 依 `docs/擺位計算邏輯.md` §6、§7(公分版)。

本層**不認得開合淨空** —— 淨空是 agent 層的知識(`backend/agent/clearance.py`),
依賴方向上不能反向 import,因此由 agent 層收尾覆核(§9.4 `_resolve_clearance`)。
"""
from __future__ import annotations

import math
from typing import Callable, Sequence

from .layout_model import Edge, Placement, RoomContext, Template
from .obb import Obb, facing_deg, front_vector

# ── §11 常數(公分版)────────────────────────────────────────────────
WALL_GAP_CM = 5.0            # 家具背面與牆間距(規格 50mm)
TABLE_GAP_CM = 45.0          # 沙發前緣到茶几走距(規格 450mm)
RUG_TUCK_CM = 40.0           # 地毯內收進沙發下深度(規格 400mm)
CHAIR_GAP_CM = 3.0           # 椅與桌緣間距,副件相對位同用(規格 30mm)
SIDE_GAP_CM = 5.0            # 床頭櫃與床側向間距(規格 50mm)
_NS_FWD_TRIES = (0.0, 15.0, 30.0)   # 床頭櫃滑位序列(規格 0/150/300mm)
ANCHOR_EDGE_TRIES = 10       # 每件嘗試的最長邊數
ANCHOR_STEP_CM = 15.0        # 沿邊步進補掃間距(規格 150mm)
_EDGE_TS = (0.5, 0.35, 0.65, 0.2, 0.8)   # 沿邊五定點(歷史相容前綴)
TV_PARALLEL_DEG = 30.0       # 電視櫃「對面平行牆」夾角容許

Point = tuple[float, float]
FreeFn = Callable[[Template, Obb], bool]


def anchor_ts(length: float, width: float) -> tuple[float, ...]:
    """沿邊錨點參數序列(§6.1)。

    五定點是**歷史前綴**:先試它們,既有擺位的選點不變。定點全被踩掉才進
    步進補掃,**由中心向外**。五定點即使落在可行域外也照試,遮罩會否決。
    """
    if length <= 0:
        return _EDGE_TS
    lo = (width / 2 + WALL_GAP_CM) / length
    hi = 1.0 - lo
    if lo >= hi:                       # 邊短於件 → 只回五定點,交由遮罩否決
        return _EDGE_TS
    n = max(1, round((hi - lo) * length / ANCHOR_STEP_CM))
    fill = [lo + (hi - lo) * k / n for k in range(n + 1)]
    fill.sort(key=lambda t: abs(t - 0.5))   # 穩定排序:同值取較小 t(fill 本為升冪)
    extra = [t for t in fill if all(abs(t - fixed) > 1e-9 for fixed in _EDGE_TS)]
    return _EDGE_TS + tuple(extra)


def candidate_edges(edges: Sequence[Edge], width: float) -> list[Edge]:
    """可容納該件的候選邊:長邊優先,完整 tie-break 保證決定性(§6)。"""
    usable = [e for e in edges if e.length >= width]
    usable.sort(key=lambda e: (-e.length, e.mid[1], e.mid[0]))
    return usable[:ANCHOR_EDGE_TRIES]


def try_against_wall(
    ctx: RoomContext,
    tpl: Template,
    *,
    edges: Sequence[Edge] | None = None,
    free: FreeFn | None = None,
) -> tuple[Point, Point, float] | None:
    """靠牆錨定掃描(§6),回 ``(錨點, inward, rotation_deg)``;放不下回 None。

    貪婪不回溯:第一個過關者即用。放不下不是錯誤,略過該件即可。
    """
    is_free = free or ctx.free
    for edge in candidate_edges(edges if edges is not None else ctx.edges, tpl.w):
        normal = edge.inward()
        rotation = facing_deg(normal)
        off = tpl.d / 2 + WALL_GAP_CM
        for t in anchor_ts(edge.length, tpl.w):
            px, py = edge.point_at(t)
            point = (px + normal[0] * off, py + normal[1] * off)
            obb = Obb.from_deg(point[0], point[1], tpl.w, tpl.d, rotation)
            if is_free(tpl, obb):
                return point, normal, rotation
    return None


def _place_at(ctx: RoomContext, tpl: Template, point: Point, rotation: float, index: int = 0) -> Placement:
    return Placement(
        id=f"{ctx.room_id}-{tpl.kind}-{index}",
        kind=tpl.kind,
        cx=point[0],
        cy=point[1],
        w=tpl.w,
        d=tpl.d,
        rotation_deg=rotation,
        height=tpl.height,
        name=tpl.name,
    )


# ── §7.1 living ─────────────────────────────────────────────────────
def place_living(
    ctx: RoomContext,
    by_kind: dict[str, Template],
    free: FreeFn | None = None,
) -> tuple[str, ...]:
    """沙發靠牆 → 地毯內收 → 茶几走距 → 電視櫃對面平行牆。

    回傳本規則已消化的 kind;主件放不下 → 回空 tuple,剩件仍走 §8 分流。
    """
    is_free = free or ctx.free
    sofa_tpl = by_kind.get("sofa")
    if sofa_tpl is None:
        return ()
    anchored = try_against_wall(ctx, sofa_tpl, free=is_free)
    if anchored is None:
        return ()
    point, normal, rotation = anchored
    ctx.commit(_place_at(ctx, sofa_tpl, point, rotation))
    consumed = ["sofa"]

    def ahead(dist: float) -> Point:
        return (point[0] + normal[0] * dist, point[1] + normal[1] * dist)

    rug_tpl = by_kind.get("rug")
    if rug_tpl is not None:
        centre = ahead(sofa_tpl.d / 2 + rug_tpl.d / 2 - RUG_TUCK_CM)
        obb = Obb.from_deg(centre[0], centre[1], rug_tpl.w, rug_tpl.d, rotation)
        # 地毯只驗遮罩,不驗已放家具(壓沙發是設計);登記但不烙印
        from .obb import obb_blocked
        if not obb_blocked(ctx.blocked_for(rug_tpl.height), ctx.grid, obb):
            ctx.commit(_place_at(ctx, rug_tpl, centre, rotation), stamp=False)
        consumed.append("rug")

    table_tpl = by_kind.get("coffee_table")
    if table_tpl is not None:
        centre = ahead(sofa_tpl.d / 2 + TABLE_GAP_CM + table_tpl.d / 2)
        obb = Obb.from_deg(centre[0], centre[1], table_tpl.w, table_tpl.d, rotation)
        if is_free(table_tpl, obb):
            ctx.commit(_place_at(ctx, table_tpl, centre, rotation))
        consumed.append("coffee_table")

    tv_tpl = by_kind.get("tv")
    if tv_tpl is not None:
        if _place_tv(ctx, tv_tpl, point, normal, rotation, is_free):
            pass
        consumed.append("tv")
    return tuple(consumed)


def _edge_angle(edge: Edge) -> float:
    return math.atan2(edge.by - edge.ay, edge.bx - edge.ax)


def _place_tv(
    ctx: RoomContext,
    tpl: Template,
    sofa_point: Point,
    sofa_normal: Point,
    sofa_rotation: float,
    is_free: FreeFn,
) -> bool:
    """電視櫃:沙發正前方**最遠的平行牆**(§7.1)。

    ``mod π`` 可直接比:θ = facing_deg(n) = φ + π,兩邊都差同一個 π,mod π 抵銷。
    """
    r_sofa = math.radians(sofa_rotation)
    tol = math.radians(TV_PARALLEL_DEG)
    scored: list[tuple[float, Edge]] = []
    for edge in ctx.edges:
        if edge.length < tpl.w:
            continue
        diff = (_edge_angle(edge) - r_sofa) % math.pi
        if min(diff, math.pi - diff) > tol:
            continue
        mid = edge.mid
        proj = (mid[0] - sofa_point[0]) * sofa_normal[0] + (mid[1] - sofa_point[1]) * sofa_normal[1]
        if proj <= 0:
            continue
        scored.append((proj, edge))
    scored.sort(key=lambda item: (-item[0], item[1].mid[1], item[1].mid[0]))

    for _, edge in scored:
        found = try_against_wall(ctx, tpl, edges=[edge], free=is_free)
        if found is not None:
            point, _, rotation = found
            ctx.commit(_place_at(ctx, tpl, point, rotation))
            return True
    return False


# ── §7.2 bedroom ────────────────────────────────────────────────────
def place_bedroom(
    ctx: RoomContext,
    by_kind: dict[str, Template],
    free: FreeFn | None = None,
) -> tuple[str, ...]:
    """床靠牆 → 床頭櫃貼床頭板兩側 → 衣櫃另跑一次獨立靠牆錨定。"""
    is_free = free or ctx.free
    bed_tpl = by_kind.get("bed")
    if bed_tpl is None:
        return ()
    anchored = try_against_wall(ctx, bed_tpl, free=is_free)
    if anchored is None:
        return ()
    point, normal, rotation = anchored
    ctx.commit(_place_at(ctx, bed_tpl, point, rotation))
    consumed = ["bed"]

    ns_tpl = by_kind.get("nightstand")
    if ns_tpl is not None:
        _place_nightstands(ctx, ns_tpl, bed_tpl, point, normal, rotation, is_free)
        consumed.append("nightstand")

    wardrobe_tpl = by_kind.get("wardrobe")
    if wardrobe_tpl is not None:
        found = try_against_wall(ctx, wardrobe_tpl, free=is_free)
        if found is not None:
            w_point, _, w_rotation = found
            ctx.commit(_place_at(ctx, wardrobe_tpl, w_point, w_rotation))
        consumed.append("wardrobe")
    return tuple(consumed)


def _place_nightstands(
    ctx: RoomContext,
    tpl: Template,
    bed: Template,
    bed_point: Point,
    normal: Point,
    rotation: float,
    is_free: FreeFn,
) -> None:
    """至多 ``min(2, count)`` 件,床的兩側各一;床頭角被占則沿床側向床尾滑位。"""
    ns_max = min(2, max(1, tpl.count))
    u = (normal[1], -normal[0])                 # 沿牆方向(inward 順轉 90°)
    back = bed.d / 2 - tpl.d / 2                # 背線與床頭板齊
    side = bed.w / 2 + tpl.w / 2 + SIDE_GAP_CM
    cap = bed.d - tpl.d                         # 滑到底仍不越床尾
    placed = 0
    for sign in (1.0, -1.0):
        for fwd in _NS_FWD_TRIES:
            if fwd > cap:
                break
            cx = bed_point[0] - normal[0] * (back - fwd) + u[0] * side * sign
            cy = bed_point[1] - normal[1] * (back - fwd) + u[1] * side * sign
            obb = Obb.from_deg(cx, cy, tpl.w, tpl.d, rotation)
            if is_free(tpl, obb):
                ctx.commit(_place_at(ctx, tpl, (cx, cy), rotation, index=placed))
                placed += 1
                break                            # 該側成功就換下一側
        if placed >= ns_max:
            break


# ── §7.3 dining ─────────────────────────────────────────────────────
def place_dining(
    ctx: RoomContext,
    by_kind: dict[str, Template],
    free: FreeFn | None = None,
) -> tuple[str, ...]:
    """餐桌置房間質心、對齊最長牆走向;餐椅兩長邊各 2 張,面向餐桌。"""
    is_free = free or ctx.free
    table_tpl = by_kind.get("dining_table")
    if table_tpl is None:
        return ()
    if not ctx.edges:
        return ()
    longest = max(ctx.edges, key=lambda e: (e.length, -e.mid[1], -e.mid[0]))
    base_deg = facing_deg(longest.inward())
    centre = ctx.centroid

    chosen: float | None = None
    for rotation in (base_deg, base_deg + 90.0):
        obb = Obb.from_deg(centre[0], centre[1], table_tpl.w, table_tpl.d, rotation)
        if is_free(table_tpl, obb):
            chosen = rotation
            break
    if chosen is None:
        return ()
    ctx.commit(_place_at(ctx, table_tpl, centre, chosen))
    consumed = ["dining_table"]

    chair_tpl = by_kind.get("dining_chair")
    if chair_tpl is not None:
        _place_dining_chairs(ctx, chair_tpl, table_tpl, centre, chosen, is_free)
        consumed.append("dining_chair")
    return tuple(consumed)


def _place_dining_chairs(
    ctx: RoomContext,
    tpl: Template,
    table: Template,
    table_centre: Point,
    table_rotation: float,
    is_free: FreeFn,
) -> None:
    r = math.radians(table_rotation)
    w_dir = (math.cos(r), math.sin(r))
    d_dir = (-math.sin(r), math.cos(r))
    depth_off = table.d / 2 + tpl.d / 2 + CHAIR_GAP_CM
    index = 0
    for side in (1.0, -1.0):
        face = (-d_dir[0] * side, -d_dir[1] * side)   # 椅子面向餐桌
        rotation = facing_deg(face)
        for along in (-table.w / 4, table.w / 4):
            cx = table_centre[0] + d_dir[0] * depth_off * side + w_dir[0] * along
            cy = table_centre[1] + d_dir[1] * depth_off * side + w_dir[1] * along
            obb = Obb.from_deg(cx, cy, tpl.w, tpl.d, rotation)
            if is_free(tpl, obb):
                ctx.commit(_place_at(ctx, tpl, (cx, cy), rotation, index=index))
                index += 1


RULES: dict[str, Callable[..., tuple[str, ...]]] = {
    "living": place_living,
    "bedroom": place_bedroom,
    "dining": place_dining,
}

# 各房型規則會嘗試處理的 kind —— §8.1 第 2 項用它判斷「規則已試過就別重試」
RULE_KINDS_BY_LABEL: dict[str, frozenset[str]] = {
    "living": frozenset({"sofa", "rug", "coffee_table", "tv"}),
    "bedroom": frozenset({"bed", "nightstand", "wardrobe"}),
    "dining": frozenset({"dining_table", "dining_chair"}),
}
