"""OBB 幾何與網格碰撞判定；公開邊界見 `backend/engine/README.md`。

⚠ 角度約定(§2.2)最易錯:**正面 f 是 OBB 的本地 −y**。
本模組一律以 ``f = (sin r, -cos r)`` 為正面基準,不沿用「本地 +y 是正面」的說法。
本體 OBB 對 ±d 對稱,故此差異不影響碰撞,只在淨空區往哪一側外推時有意義。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .raster import Grid

Point = tuple[float, float]


# ── §2.1 三個互為逆運算的向量 ───────────────────────────────────────
def facing_deg(n: Point) -> float:
    """「要正面朝向單位向量 n」所需的 rotation_deg。

    ``+ 0.0`` 是把 IEEE754 的負零吃掉:法線常算出 ``-0.0``,而
    ``atan2(-0.0, -1)`` 會回 −π,使軸對齊牆得到 −180° 而非規格 §13 的 180°。
    兩者數學等價,但角度值會外流到 payload 與測試,故在此正規化。
    """
    return math.degrees(math.atan2(n[0] + 0.0, -n[1] + 0.0))


def front_vector(rotation_deg: float) -> Point:
    """該角度下家具正面的世界方向 f = (sin r, −cos r)。

    與 :func:`facing_deg` 嚴格互逆:``front_vector(facing_deg(n)) == n``。
    """
    r = math.radians(rotation_deg)
    return (math.sin(r), -math.cos(r))


def side_vector(rotation_deg: float) -> Point:
    """家具本地 +w(右)方向 s = (−f_y, f_x) = (cos r, sin r)。"""
    r = math.radians(rotation_deg)
    return (math.cos(r), math.sin(r))


@dataclass(frozen=True)
class Obb:
    """有向包圍盒。``w`` 沿牆方向的寬、``d`` 離牆的進深、``rad`` 為弧度。"""

    cx: float
    cy: float
    w: float
    d: float
    rad: float = 0.0

    @classmethod
    def from_deg(cls, cx: float, cy: float, w: float, d: float, rotation_deg: float) -> "Obb":
        return cls(cx, cy, w, d, math.radians(rotation_deg))


def obb_corners(obb: Obb) -> list[Point]:
    """四角世界座標(§5.1)。"""
    cos_r, sin_r = math.cos(obb.rad), math.sin(obb.rad)
    hw, hd = obb.w / 2, obb.d / 2
    return [
        (obb.cx + x_l * cos_r - y_l * sin_r, obb.cy + x_l * sin_r + y_l * cos_r)
        for x_l, y_l in ((-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd))
    ]


def _window(grid: Grid, obb: Obb) -> tuple[int, int, int, int] | None:
    """OBB 四角的 AABB → 格索引視窗;越界回 None(§5.2 第 2 步)。"""
    corners = obb_corners(obb)
    min_x = min(c[0] for c in corners)
    max_x = max(c[0] for c in corners)
    min_y = min(c[1] for c in corners)
    max_y = max(c[1] for c in corners)
    ix0 = int((min_x - grid.origin_x) / grid.cell)
    ix1 = int((max_x - grid.origin_x) / grid.cell) + 1
    iy0 = int((min_y - grid.origin_y) / grid.cell)
    iy1 = int((max_y - grid.origin_y) / grid.cell) + 1
    if ix0 < 0 or iy0 < 0 or ix1 >= grid.nx or iy1 >= grid.ny:
        return None
    return ix0, ix1, iy0, iy1


def _inside(grid: Grid, obb: Obb, win: tuple[int, int, int, int]) -> np.ndarray:
    """視窗內每個格心反旋轉進 OBB 本地座標,回布林遮罩(§5.2 第 3 步)。"""
    ix0, ix1, iy0, iy1 = win
    xs = grid.origin_x + (np.arange(ix0, ix1 + 1) + 0.5) * grid.cell
    ys = grid.origin_y + (np.arange(iy0, iy1 + 1) + 0.5) * grid.cell
    dx = xs[None, :] - obb.cx
    dy = ys[:, None] - obb.cy
    cos_r, sin_r = math.cos(-obb.rad), math.sin(-obb.rad)
    lx = dx * cos_r - dy * sin_r
    ly = dx * sin_r + dy * cos_r
    return (np.abs(lx) <= obb.w / 2) & (np.abs(ly) <= obb.d / 2)


def obb_blocked(mask: np.ndarray, grid: Grid, obb: Obb) -> bool:
    """唯一的碰撞函式(§5.2)。越界 = 房間外 = 必然禁放 → True。"""
    win = _window(grid, obb)
    if win is None:
        return True
    ix0, ix1, iy0, iy1 = win
    inside = _inside(grid, obb, win)
    return bool((inside & mask[iy0:iy1 + 1, ix0:ix1 + 1]).any())


def stamp_obb(mask: np.ndarray, grid: Grid, obb: Obb) -> None:
    """把 OBB 烙印進遮罩(§5.2)。越界部分忽略,不報錯。"""
    corners = obb_corners(obb)
    min_x = min(c[0] for c in corners)
    max_x = max(c[0] for c in corners)
    min_y = min(c[1] for c in corners)
    max_y = max(c[1] for c in corners)
    ix0 = max(0, int((min_x - grid.origin_x) / grid.cell))
    ix1 = min(grid.nx - 1, int((max_x - grid.origin_x) / grid.cell) + 1)
    iy0 = max(0, int((min_y - grid.origin_y) / grid.cell))
    iy1 = min(grid.ny - 1, int((max_y - grid.origin_y) / grid.cell) + 1)
    if ix0 > ix1 or iy0 > iy1:
        return
    inside = _inside(grid, obb, (ix0, ix1, iy0, iy1))
    mask[iy0:iy1 + 1, ix0:ix1 + 1] |= inside


def obb_overlaps(grid: Grid, probe: Obb, target: Obb) -> bool:
    """兩件家具是否重疊(§5.2):把 target 烙進暫存畫布,再拿 probe 測碰撞。

    ⚠ 重疊判定的解析度 = 格徑(預設 5cm),不是解析幾何。呼叫端必須先確認
    probe 在網格內,否則出界的 True 會被誤讀成重疊。
    """
    canvas = grid.blank()
    stamp_obb(canvas, grid, target)
    return obb_blocked(canvas, grid, probe)
