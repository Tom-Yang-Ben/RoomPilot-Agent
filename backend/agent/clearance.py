"""開合淨空（門扇／抽屜操作空間）；幾何邊界見 `backend/engine/README.md`。

淨空需求是**宣告式資料**(`CLEARANCE_OF`),缺項 = 無需求。沙發、茶几、床、
開放式書櫃…完全跳過淨空檢查。

放在 agent 層而非引擎層:淨空是「哪種家具會開門抽拉」的領域知識,
引擎層(`backend/engine/`)在依賴方向上不能 import 它。
"""
from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np

from ..engine.layout_model import Placement
from ..engine.obb import Obb, front_vector, obb_blocked, side_vector
from ..engine.raster import Grid

# ── §9.1 需求表(kind → (面, 進深 cm));規格原為 mm,整除 10 ──────────
CLEARANCE_OF: dict[str, tuple[str, float]] = {
    "wardrobe": ("front", 60.0),         # 對開門扇全開(規格 600mm)
    "cabinet_low": ("front", 45.0),      # 抽屜拉出(規格 450mm)
    "dressing_table": ("front", 45.0),   # 抽屜拉出 + 坐入(規格 450mm)
    "nightstand": ("front", 35.0),       # 小抽屜拉出(規格 350mm)
}


def zone_obb(placement: Placement, side: str, depth: float) -> Obb:
    """淨空區幾何(§9.2):指定面外緣往外延伸 ``depth`` 的 OBB,與家具同角度。

    front／back 的淨空**與家具同寬**;left／right **與家具同深**。
    """
    f = front_vector(placement.rotation_deg)
    s = side_vector(placement.rotation_deg)
    rad = placement.obb().rad
    if side == "front":
        off = placement.d / 2 + depth / 2
        return Obb(placement.cx + f[0] * off, placement.cy + f[1] * off, placement.w, depth, rad)
    if side == "back":
        off = placement.d / 2 + depth / 2
        return Obb(placement.cx - f[0] * off, placement.cy - f[1] * off, placement.w, depth, rad)
    if side == "right":
        off = placement.w / 2 + depth / 2
        return Obb(placement.cx + s[0] * off, placement.cy + s[1] * off, depth, placement.d, rad)
    if side == "left":
        off = placement.w / 2 + depth / 2
        return Obb(placement.cx - s[0] * off, placement.cy - s[1] * off, depth, placement.d, rad)
    raise ValueError(f"未知的淨空面:{side}")


def clearance_zone(placement: Placement) -> Obb | None:
    """該家具的淨空區;無開合需求回 None。"""
    spec = CLEARANCE_OF.get(placement.kind)
    if spec is None:
        return None
    side, depth = spec
    return zone_obb(placement, side, depth)


def clearance_conflict(
    grid: Grid,
    blocked_low: np.ndarray,
    candidate: Placement,
    others: Sequence[Placement],
    *,
    reverse: bool = True,
) -> str | None:
    """§9.3 衝突判定,回 None 表示過關。訊息是繁中原句,可直接轉述給使用者。

    第 1 項驗的是 ``low`` 而非 ``band`` —— 淨空是「人站立操作」的空間,
    落在窗前合法。``reverse=False`` 供「逐件覆核既有配置」使用:第 4 項會在
    對方那一輪以第 2 項的身分被抓到,兩邊都報只是重複噪音。
    """
    zone = clearance_zone(candidate)
    if zone is not None:
        # 1. 自己的淨空撞牆體或動線
        if obb_blocked(blocked_low, grid, zone):
            return f"「{candidate.label}」的開合空間被牆體或動線阻擋"
        canvas = grid.blank()
        for other in others:
            if other.id == candidate.id:
                continue
            # 2. 自己的淨空撞他件本體
            canvas[:] = False
            from ..engine.obb import stamp_obb
            stamp_obb(canvas, grid, other.obb())
            if obb_blocked(canvas, grid, zone):
                return f"「{candidate.label}」的開合空間與「{other.label}」衝突"
            # 3. 自己的淨空撞他件淨空
            other_zone = clearance_zone(other)
            if other_zone is not None:
                canvas[:] = False
                stamp_obb(canvas, grid, other_zone)
                if obb_blocked(canvas, grid, zone):
                    return f"「{candidate.label}」與「{other.label}」的開合空間互相衝突"

    if reverse:
        # 4. 自己本體壓到他件淨空
        body = candidate.obb()
        canvas = grid.blank()
        from ..engine.obb import stamp_obb
        for other in others:
            if other.id == candidate.id:
                continue
            other_zone = clearance_zone(other)
            if other_zone is None:
                continue
            canvas[:] = False
            stamp_obb(canvas, grid, other_zone)
            if obb_blocked(canvas, grid, body):
                return f"擋住了「{other.label}」的開合空間"
    return None


def clearance_free(
    grid: Grid,
    blocked_low: np.ndarray,
    candidate: Placement,
    others: Iterable[Placement],
    *,
    reverse: bool = True,
) -> bool:
    """布林版,擺位掃描逐點快篩用(§9.3)。"""
    return clearance_conflict(grid, blocked_low, candidate, list(others), reverse=reverse) is None
