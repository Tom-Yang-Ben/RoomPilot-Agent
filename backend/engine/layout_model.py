"""擺位管線的資料模型 —— 依 `docs/擺位計算邏輯.md` §1、§5.3(公分版)。

與舊 Shapely 引擎的 ``models.py`` 並存:那組型別是型錄/payload 契約,
本模組是新柵格引擎的內部工作型別。
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Sequence

import numpy as np

from .constraints import BlockedMasks
from .obb import Obb, obb_blocked, stamp_obb
from .raster import Grid

Point = tuple[float, float]


@dataclass(frozen=True)
class Template:
    """一件待擺家具的規格。``w`` = 沿牆方向的寬、``d`` = 離牆的進深(§2)。"""

    kind: str
    w: float
    d: float
    height: float = 0.0
    count: int = 1
    name: str = ""

    @property
    def label(self) -> str:
        return self.name or self.kind


@dataclass(frozen=True)
class Placement:
    """擺位結果。座標為世界公分,``rotation_deg`` 為 three.js Y 旋轉角。"""

    id: str
    kind: str
    cx: float
    cy: float
    w: float
    d: float
    rotation_deg: float = 0.0
    height: float = 0.0
    name: str = ""

    @property
    def label(self) -> str:
        return self.name or self.kind

    def obb(self) -> Obb:
        return Obb.from_deg(self.cx, self.cy, self.w, self.d, self.rotation_deg)

    def moved(self, cx: float, cy: float) -> "Placement":
        """§10.4 不可變:一律產新物件,絕不就地改。"""
        return replace(self, cx=cx, cy=cy)

    def rotated(self, rotation_deg: float) -> "Placement":
        return replace(self, rotation_deg=rotation_deg % 360)


@dataclass
class Edge:
    """房間輪廓邊。室內恆在邊的左側(§2.3)。"""

    ax: float
    ay: float
    bx: float
    by: float

    @property
    def length(self) -> float:
        return float(np.hypot(self.bx - self.ax, self.by - self.ay))

    @property
    def mid(self) -> Point:
        return ((self.ax + self.bx) / 2, (self.ay + self.by) / 2)

    def inward(self) -> Point:
        """左法線(§2.3)—— 不需質心可見性判斷,L 形房、凹房都正確。

        ``+ 0.0`` 消去負零:軸對齊邊會產生 ``-0.0``,經 ``facing_deg`` 會變成 −180°。
        """
        length = self.length or 1.0
        return (-(self.by - self.ay) / length + 0.0, (self.bx - self.ax) / length + 0.0)

    def point_at(self, t: float) -> Point:
        return (self.ax + (self.bx - self.ax) * t, self.ay + (self.by - self.ay) * t)


@dataclass
class RoomContext:
    """一間房的擺位工作狀態。"""

    grid: Grid
    masks: BlockedMasks
    edges: list[Edge]
    centroid: Point
    room_id: str = "room"
    label: str = "default"
    placements: list[Placement] = field(default_factory=list)
    placed: np.ndarray = None  # type: ignore[assignment]
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.placed is None:
            self.placed = self.grid.blank()

    def blocked_for(self, height_cm: float) -> np.ndarray:
        return self.masks.for_height(height_cm)

    def free(self, tpl: Template, obb: Obb) -> bool:
        """§5.3 合法性三層:遮罩 + 本房已放家具的累計烙印。"""
        if obb_blocked(self.blocked_for(tpl.height), self.grid, obb):
            return False
        return not obb_blocked(self.placed, self.grid, obb)

    def commit(self, placement: Placement, *, stamp: bool = True) -> None:
        """登記一件家具。``rug`` 是平面件:登記但不烙印(允許家具壓在上面)。"""
        self.placements.append(placement)
        if stamp and placement.kind != "rug":
            stamp_obb(self.placed, self.grid, placement.obb())

    def restamp(self) -> None:
        """清空重畫全清單(§5.3):移除或改位家具後必須呼叫。"""
        self.placed = self.grid.blank()
        for placement in self.placements:
            if placement.kind != "rug":
                stamp_obb(self.placed, self.grid, placement.obb())

    def remove(self, placement_id: str) -> None:
        self.placements = [p for p in self.placements if p.id != placement_id]
        self.restamp()

    def find(self, kind: str) -> Placement | None:
        for placement in self.placements:
            if placement.kind == kind:
                return placement
        return None


def room_edges(polygon: Sequence[Point]) -> list[Edge]:
    """由 polygon 依序取邊(首尾相接,零長邊剔除)(§5.1)。"""
    pts = [(float(p[0]), float(p[1])) for p in polygon]
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    edges: list[Edge] = []
    for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
        if ax == bx and ay == by:
            continue
        edges.append(Edge(ax, ay, bx, by))
    return edges


def polygon_centroid(polygon: Sequence[Point]) -> Point:
    """多邊形質心(退化時退回頂點平均)。"""
    pts = [(float(p[0]), float(p[1])) for p in polygon]
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if not pts:
        return (0.0, 0.0)
    area2 = 0.0
    cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        cross = x0 * y1 - x1 * y0
        area2 += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if abs(area2) < 1e-9:
        return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
    return (cx / (3 * area2), cy / (3 * area2))
