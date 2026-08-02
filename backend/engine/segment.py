"""通行段(牆縫式開口)—— 依 `docs/擺位計算邏輯.md` §4.2(公分版)。

沒有 door 實體、只靠牆縫連通的開口也要留通行淨空。做法是用形態學閉運算把
≤ 2k 格的縫封起來,「被閉運算補上的格」就是被封的門洞裸縫。

只用 numpy(不引入 scipy):8-鄰域 dilate/erode 與 4-連通標記都自行實作。
"""
from __future__ import annotations

import numpy as np

from .raster import Grid

DOOR_GAP_CM = 100.0    # 閉運算可封的最大縫寬(規格 DOOR_GAP_MM = 1000)

Segment = tuple[float, float, float, float]


def _dilate8(mask: np.ndarray) -> np.ndarray:
    """8-鄰域膨脹一次。"""
    out = mask.copy()
    out[1:, :] |= mask[:-1, :]
    out[:-1, :] |= mask[1:, :]
    out[:, 1:] |= mask[:, :-1]
    out[:, :-1] |= mask[:, 1:]
    out[1:, 1:] |= mask[:-1, :-1]
    out[1:, :-1] |= mask[:-1, 1:]
    out[:-1, 1:] |= mask[1:, :-1]
    out[:-1, :-1] |= mask[1:, 1:]
    return out


def _erode8(mask: np.ndarray) -> np.ndarray:
    """8-鄰域侵蝕一次(邊界外視為 False,與 dilate 對稱)。"""
    return ~_dilate8(~mask)


def _close(mask: np.ndarray, k: int) -> np.ndarray:
    """形態學閉運算:dilate k 次 → erode k 次。"""
    out = mask
    for _ in range(k):
        out = _dilate8(out)
    for _ in range(k):
        out = _erode8(out)
    return out


def label_regions(mask: np.ndarray) -> np.ndarray:
    """4-連通元件標記,回傳與 mask 同形的 int 陣列(0 = 背景,1.. = 元件)。"""
    labels = np.zeros(mask.shape, dtype=np.int32)
    ny, nx = mask.shape
    current = 0
    for sy in range(ny):
        for sx in range(nx):
            if not mask[sy, sx] or labels[sy, sx]:
                continue
            current += 1
            stack = [(sy, sx)]
            labels[sy, sx] = current
            while stack:
                y, x = stack.pop()
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny_, nx_ = y + dy, x + dx
                    if 0 <= ny_ < ny and 0 <= nx_ < nx and mask[ny_, nx_] and not labels[ny_, nx_]:
                        labels[ny_, nx_] = current
                        stack.append((ny_, nx_))
    return labels


def passage_segments(grid: Grid, margin_cells: int = 2) -> list[Segment]:
    """回傳牆縫式開口的中線段(§4.2)。

    寬開口(閉運算封不住)不產格 → 不吐假段。與門帶重疊時冗餘但無害
    (同進深、同語意)。
    """
    occ = grid.occ
    k = int(np.ceil(DOOR_GAP_CM / 2 / grid.cell))
    if k <= 0:
        return []

    closed = _close(occ, k)
    # 還原 margin:膨脹灌滿的外環不算縫
    m = margin_cells
    if m > 0:
        closed[:m, :] = occ[:m, :]
        closed[-m:, :] = occ[-m:, :]
        closed[:, :m] = occ[:, :m]
        closed[:, -m:] = occ[:, -m:]

    gap = closed & ~occ
    if not gap.any():
        return []

    # 只留貼室內的塊(外角雜格不貼室內)
    interior = label_regions(closed) > 0
    gap &= interior

    segments: list[Segment] = []
    labels = label_regions(gap)
    for label in range(1, int(labels.max()) + 1):
        ys, xs = np.nonzero(labels == label)
        if ys.size == 0:
            continue
        x0, _ = grid.world(float(xs.min()), 0.0)
        x1, _ = grid.world(float(xs.max()), 0.0)
        _, y0 = grid.world(0.0, float(ys.min()))
        _, y1 = grid.world(0.0, float(ys.max()))
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        half_x, half_y = (x1 - x0) / 2, (y1 - y0) / 2
        # 沿較短半邊方向過塊心吐一條中線段(穿過縫口)
        if half_x <= half_y:
            segments.append((cx - half_x, cy, cx + half_x, cy))
        else:
            segments.append((cx, cy - half_y, cx, cy + half_y))
    return segments
