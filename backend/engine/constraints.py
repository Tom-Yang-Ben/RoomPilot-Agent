"""禁放遮罩（True = 禁放）；公開邊界見 `backend/engine/README.md`。

兩層遮罩:

    blocked_low  = occ | ¬room_mask | stroke(doors, 75) | stroke(passages, 75)
    blocked_band = blocked_low | stroke(windows, 40)

選用規則:家具 ``height_cm >= WINDOW_SILL_CM`` → 用 band(會擋光,必須讓開窗前);
否則用 low(矮件貼窗合法)。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .raster import Grid, Segment, room_mask, stroke_segments

# ── §11 常數(公分版)────────────────────────────────────────────────
DOOR_CLEARANCE_CM = 75.0     # 門前通行淨空,含開門迴轉;通行縫同值(規格 750mm)
WINDOW_CLEARANCE_CM = 40.0   # 窗前採光帶進深(規格 400mm)
WINDOW_SILL_CM = 90.0        # 窗台高:家具高於此才受窗前帶約束(規格 900mm)

Point = tuple[float, float]


@dataclass
class BlockedMasks:
    """一間房的兩層禁放遮罩。"""

    low: np.ndarray
    band: np.ndarray

    def for_height(self, height_cm: float) -> np.ndarray:
        """依家具高度選遮罩(§4)。"""
        return self.band if float(height_cm or 0.0) >= WINDOW_SILL_CM else self.low


def clearance_mask(
    grid: Grid,
    segments: Sequence[Segment],
    depth_cm: float,
) -> np.ndarray:
    """淨空帶:對線段**雙側描粗**,不判法線方向(§4)。

    門/窗的另一側必在房間外,已被 ``¬room_mask`` 蓋掉,因此結構上不可能畫錯側。
    """
    mask = grid.blank()
    stroke_segments(grid, mask, segments, depth_cm)
    return mask


def blocked_masks(
    grid: Grid,
    polygon: Sequence[Point],
    doors: Sequence[Segment] = (),
    windows: Sequence[Segment] = (),
    passages: Sequence[Segment] = (),
    holes: Sequence[Sequence[Point]] = (),
) -> BlockedMasks:
    """逐房計算兩層禁放遮罩(§4)。

    ``¬room_mask`` 讓「房間外」一律禁放 —— 這是家具不會被移出自己房間的根本原因。
    門窗不過濾是否鄰接本房:非鄰接段與本房交集為空,多畫無害。
    """
    inside = room_mask(grid, polygon, holes)
    low = grid.occ | ~inside
    low |= clearance_mask(grid, list(doors), DOOR_CLEARANCE_CM)
    low |= clearance_mask(grid, list(passages), DOOR_CLEARANCE_CM)
    band = low | clearance_mask(grid, list(windows), WINDOW_CLEARANCE_CM)
    return BlockedMasks(low=low, band=band)
