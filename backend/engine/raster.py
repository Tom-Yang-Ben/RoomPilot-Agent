"""佔用網格(柵格化)—— 全案唯一的碰撞事實源。

依 `docs/擺位計算邏輯.md` §3 實作,單位全部改寫成**公分**(規格原文為 mm,
本 repo 的不變量是「引擎與 Python 業務層一律公分」,故常數整除 10)。

擺位不做解析幾何:牆板環用掃描線填充、牆/門/窗線段用歐氏距離描粗,
之後所有碰撞判定都在布林網格上做(見 `obb.py`)。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np

# ── §11 常數總表(公分版)──────────────────────────────────────────────
DEFAULT_CELL_CM = 5.0        # 網格格徑 = 碰撞解析度(規格 50mm)
MAX_CELLS_PER_AXIS = 1200    # 單軸格數上限,超過則放大格徑
WALL_THICKNESS_CM = 12.0     # 線段描粗厚度,對齊前端 3D 牆厚(規格 120mm)
_MARGIN_CELLS = 2            # bbox 外圍留白格數,保證外部連通

Point = tuple[float, float]
Segment = tuple[float, float, float, float]


@dataclass
class Grid:
    """佔用網格。``occ[iy, ix]`` 為列優先(y 在前),True = 結構占據。"""

    origin_x: float
    origin_y: float
    cell: float
    nx: int
    ny: int
    occ: np.ndarray

    def world(self, ix: float, iy: float) -> Point:
        """格索引 → 格心世界座標(§3.1)。"""
        return (
            self.origin_x + (ix + 0.5) * self.cell,
            self.origin_y + (iy + 0.5) * self.cell,
        )

    def blank(self) -> np.ndarray:
        """同尺寸的空白布林畫布(房間遮罩、暫存烙印用,不動 occ)。"""
        return np.zeros((self.ny, self.nx), dtype=bool)

    def cell_centers(self) -> tuple[np.ndarray, np.ndarray]:
        """回傳 (xs, ys) 一維格心座標軸,供向量化運算。"""
        xs = self.origin_x + (np.arange(self.nx) + 0.5) * self.cell
        ys = self.origin_y + (np.arange(self.ny) + 0.5) * self.cell
        return xs, ys


def make_grid(bbox: Sequence[float]) -> Grid:
    """依 §3.1 由 ``bbox = [min_x, min_y, max_x, max_y]`` 建立空網格。"""
    min_x, min_y, max_x, max_y = (float(v) for v in bbox)
    bbox_w = max_x - min_x
    bbox_h = max_y - min_y
    span = max(bbox_w, bbox_h, 1.0)
    cell = max(DEFAULT_CELL_CM, span / MAX_CELLS_PER_AXIS)
    origin_x = min_x - _MARGIN_CELLS * cell
    origin_y = min_y - _MARGIN_CELLS * cell
    nx = math.ceil(bbox_w / cell) + 2 * _MARGIN_CELLS + 1
    ny = math.ceil(bbox_h / cell) + 2 * _MARGIN_CELLS + 1
    return Grid(origin_x, origin_y, cell, nx, ny, np.zeros((ny, nx), dtype=bool))


def _fill_ring(grid: Grid, mask: np.ndarray, ring: Sequence[Point]) -> None:
    """掃描線填充一個封閉環(§3.2)。

    半開區間規則 ``(y1 <= y_c < y2) or (y2 <= y_c < y1)`` 保證每列與每條
    跨越邊恰交一次;交點排序後成對填充,填的是**格心落在 [xa, xb] 內**的格。
    """
    pts = [(float(p[0]), float(p[1])) for p in ring]
    if len(pts) < 3:
        return
    if pts[0] != pts[-1]:
        pts.append(pts[0])

    for iy in range(grid.ny):
        y_c = grid.origin_y + (iy + 0.5) * grid.cell
        xs: list[float] = []
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if (y1 <= y_c < y2) or (y2 <= y_c < y1):
                # y1 == y2 已被半開區間排除,不會除以零
                xs.append(x1 + (y_c - y1) * (x2 - x1) / (y2 - y1))
        if not xs:
            continue
        xs.sort()
        for xa, xb in zip(xs[0::2], xs[1::2]):
            ix0 = math.ceil((xa - grid.origin_x) / grid.cell - 0.5)
            ix1 = math.floor((xb - grid.origin_x) / grid.cell - 0.5)
            if ix1 < 0 or ix0 >= grid.nx:
                continue
            mask[iy, max(0, ix0):min(grid.nx, ix1 + 1)] = True


def _stroke_segment(grid: Grid, mask: np.ndarray, seg: Segment, radius: float) -> None:
    """線段描粗(§3.2):格心到線段的歐氏距離 ≤ radius 即占據。"""
    ax, ay, bx, by = (float(v) for v in seg)
    dx, dy = bx - ax, by - ay
    len_sq = dx * dx + dy * dy

    lo_x = min(ax, bx) - radius
    hi_x = max(ax, bx) + radius
    lo_y = min(ay, by) - radius
    hi_y = max(ay, by) + radius
    ix0 = max(0, int((lo_x - grid.origin_x) / grid.cell) - 1)
    ix1 = min(grid.nx, int((hi_x - grid.origin_x) / grid.cell) + 2)
    iy0 = max(0, int((lo_y - grid.origin_y) / grid.cell) - 1)
    iy1 = min(grid.ny, int((hi_y - grid.origin_y) / grid.cell) + 2)
    if ix0 >= ix1 or iy0 >= iy1:
        return

    xs = grid.origin_x + (np.arange(ix0, ix1) + 0.5) * grid.cell
    ys = grid.origin_y + (np.arange(iy0, iy1) + 0.5) * grid.cell
    px = xs[None, :] - ax
    py = ys[:, None] - ay
    if len_sq == 0.0:
        t = np.zeros((iy1 - iy0, ix1 - ix0))       # 退化成點時取 t = 0
    else:
        t = np.clip((px * dx + py * dy) / len_sq, 0.0, 1.0)
    ex = px - t * dx
    ey = py - t * dy
    mask[iy0:iy1, ix0:ix1] |= (ex * ex + ey * ey) <= radius * radius


def stroke_segments(
    grid: Grid,
    mask: np.ndarray,
    segments: Iterable[Segment],
    radius: float,
) -> None:
    """對一批線段描粗(對外便利函式,淨空帶用)。"""
    for seg in segments:
        _stroke_segment(grid, mask, seg, radius)


def build_occupancy(plan: dict) -> Grid:
    """依 §3 把平面圖柵格化成佔用網格。

    ``plan`` 需要 ``bbox``;``walls`` / ``wall_polygons`` / ``doors`` / ``windows``
    皆選填。**門窗都要封** —— 門洞不封則相鄰房間互通、窗洞不封則室內漏到室外,
    flood-fill 會把房間誤判成外部。
    """
    grid = make_grid(plan["bbox"])
    stroke_r = max(WALL_THICKNESS_CM / 2, 0.51 * grid.cell)
    edge_r = 0.51 * grid.cell

    for ring in plan.get("wall_polygons") or []:
        _fill_ring(grid, grid.occ, ring)
        pts = list(ring)
        if len(pts) >= 2:
            if pts[0] != pts[-1]:
                pts.append(pts[0])
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                _stroke_segment(grid, grid.occ, (x1, y1, x2, y2), edge_r)

    for key in ("walls", "doors", "windows"):
        for seg in plan.get(key) or []:
            _stroke_segment(grid, grid.occ, seg, stroke_r)

    return grid


def room_mask(grid: Grid, polygon: Sequence[Point], holes: Sequence[Sequence[Point]] = ()) -> np.ndarray:
    """房間 polygon 用同一套掃描線填充畫在**獨立畫布**上(§4),不動 ``grid.occ``。"""
    mask = grid.blank()
    _fill_ring(grid, mask, polygon)
    for hole in holes or ():
        carved = grid.blank()
        _fill_ring(grid, carved, hole)
        mask &= ~carved
    return mask
