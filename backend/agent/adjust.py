"""擺位微調 —— 依 `docs/擺位計算邏輯.md` §10(公分版)。

只吃**拆解好的結構化指令**,自然語言理解不在此層:

    {"action": "move",   "target": "r1-bed-0", "dx": 50, "dy": 0}
    {"action": "rotate", "target": "r1-bed-0", "rotation": 90}

⚠ 微調**不使用** ``ctx.placed`` —— 那份累計遮罩含目標自己的烙印,拿來判重疊會
與自己相撞。他件碰撞改由 placements 清單逐件比對。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from ..engine.constraints import BlockedMasks
from ..engine.layout_model import Placement
from ..engine.obb import obb_blocked, obb_overlaps
from ..engine.raster import Grid
from .clearance import clearance_conflict


@dataclass
class AdjustResult:
    """微調結果。失敗時 ``placements`` 是**未變動的原清單**(呼叫端可直接沿用)。"""

    ok: bool
    placements: list[Placement]
    reason: str | None = None


def _conflict(
    grid: Grid,
    masks: BlockedMasks,
    candidate: Placement,
    others: Sequence[Placement],
) -> str | None:
    """候選姿態的合法性三層(§10.1),回 None 表示過關。"""
    body = candidate.obb()
    # 1. 遮罩:房外 / 牆體 / 門前動線
    if obb_blocked(masks.for_height(candidate.height), grid, body):
        return f"「{candidate.label}」超出可放範圍(房外、牆體或門前動線)"
    # 2. 與他件本體重疊
    for other in others:
        if other.id == candidate.id:
            continue
        if obb_overlaps(grid, body, other.obb()):
            return f"「{candidate.label}」與「{other.label}」重疊"
    # 3. §9.3 四項(reverse=True)
    return clearance_conflict(grid, masks.low, candidate, others, reverse=True)


def _replace(placements: Sequence[Placement], updated: Placement) -> list[Placement]:
    return [updated if p.id == updated.id else p for p in placements]


def _find(placements: Sequence[Placement], target_id: str) -> Placement | None:
    for placement in placements:
        if placement.id == target_id:
            return placement
    return None


def move_placement(
    grid: Grid,
    masks: BlockedMasks,
    placements: Sequence[Placement],
    target_id: str,
    dx: float,
    dy: float,
) -> AdjustResult:
    """§10.2 軸分離位移:**能走多少走多少**。

    單軸被擋仍算成功(該軸座標不變),雙軸都被擋才失敗。
    ``delta = 0`` 的軸不計入成功 —— 否則「只想往 Y 移但被擋死」會回報假成功。
    """
    current = _find(placements, target_id)
    if current is None:
        return AdjustResult(False, list(placements), f"找不到目標「{target_id}」")
    if dx == 0 and dy == 0:
        return AdjustResult(True, list(placements))       # 沒要求移動,不是失敗

    others = [p for p in placements if p.id != target_id]
    moved = False
    working = current

    if dx != 0:
        candidate = working.moved(working.cx + dx, working.cy)
        if _conflict(grid, masks, candidate, others) is None:
            working = candidate
            moved = True
    if dy != 0:
        candidate = working.moved(working.cx, working.cy + dy)   # 吃 X 軸的結果
        if _conflict(grid, masks, candidate, others) is None:
            working = candidate
            moved = True

    if not moved:
        # 失敗原因取「雙軸同時位移」的目標點 —— 最貼近使用者本意
        both = current.moved(current.cx + dx, current.cy + dy)
        return AdjustResult(False, list(placements), _conflict(grid, masks, both, others))
    return AdjustResult(True, _replace(placements, working))


def rotate_placement(
    grid: Grid,
    masks: BlockedMasks,
    placements: Sequence[Placement],
    target_id: str,
    rotation: float,
) -> AdjustResult:
    """§10.3 旋轉:角度正規化 ``rotation % 360``;不合法就**保持原角度**並回失敗原因。"""
    current = _find(placements, target_id)
    if current is None:
        return AdjustResult(False, list(placements), f"找不到目標「{target_id}」")
    others = [p for p in placements if p.id != target_id]
    candidate = current.rotated(rotation)
    reason = _conflict(grid, masks, candidate, others)
    if reason is not None:
        return AdjustResult(False, list(placements), reason)
    return AdjustResult(True, _replace(placements, candidate))


def apply_command(
    grid: Grid,
    masks: BlockedMasks,
    placements: Sequence[Placement],
    command: dict,
) -> AdjustResult:
    """結構化指令派發(§10)。``add`` / ``remove`` 與相對方位指令未實作。"""
    action = str(command.get("action") or "")
    target = str(command.get("target") or "")
    if action == "move":
        return move_placement(
            grid, masks, placements, target,
            float(command.get("dx") or 0.0), float(command.get("dy") or 0.0),
        )
    if action == "rotate":
        return rotate_placement(
            grid, masks, placements, target, float(command.get("rotation") or 0.0),
        )
    return AdjustResult(False, list(placements), f"不支援的指令「{action}」")
