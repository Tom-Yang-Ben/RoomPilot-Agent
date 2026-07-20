# -*- coding: utf-8 -*-
"""DXF 平面圖尺寸辨識。

「屏蔽」在 CAD 路徑等於圖層過濾：僅讀取牆／門／窗圖層，家具與標註圖層不進入量測。
單位以 $INSUNITS 換算為 mm；缺漏時假設 mm 並提出警告。
"""
from __future__ import annotations

import math
import os
import tempfile

import ezdxf
from ezdxf import bbox

# $INSUNITS → 每單位對應 mm
_UNIT_TO_MM = {0: 1.0, 1: 25.4, 2: 304.8, 4: 1.0, 5: 10.0, 6: 1000.0}
_UNIT_NAME = {0: "未指定（假設 mm）", 1: "inch", 2: "ft", 4: "mm", 5: "cm", 6: "m"}

_WALL_KEYS = ("WALL", "牆")
_DOOR_KEYS = ("DOOR", "門")
_WINDOW_KEYS = ("WINDOW", "WIN", "窗")
_SKIP_KEYS = ("FURN", "FUR", "家具", "FIX", "DIM", "標註", "TEXT", "ANNO", "HATCH")


def _layer_kind(name: str) -> str:
    upper = (name or "").upper()
    if any(k in upper for k in _WALL_KEYS):
        return "wall"
    if any(k in upper for k in _WINDOW_KEYS):
        return "window"
    if any(k in upper for k in _DOOR_KEYS):
        return "door"
    if any(k in upper for k in _SKIP_KEYS):
        return "skip"
    return "other"


def _polyline_segments(entity) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    pts = [(p[0], p[1]) for p in entity.get_points("xy")]
    segs = list(zip(pts, pts[1:]))
    if entity.closed and len(pts) > 2:
        segs.append((pts[-1], pts[0]))
    return segs


def analyze_dxf(file_bytes: bytes) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
        tmp.write(file_bytes)
        path = tmp.name
    try:
        doc = ezdxf.readfile(path)
    finally:
        os.unlink(path)

    insunits = int(doc.header.get("$INSUNITS", 0) or 0)
    factor = _UNIT_TO_MM.get(insunits)
    warnings: list[str] = []
    if factor is None:
        factor = 1.0
        warnings.append(f"未支援的 $INSUNITS={insunits}，假設圖面單位為 mm。")
    if insunits == 0:
        warnings.append("DXF 未宣告單位（$INSUNITS=0），假設為 mm，請確認。")

    msp = doc.modelspace()
    elements: list[dict] = []
    skipped_layers: set[str] = set()

    def _collect_lines(kind_filter: str) -> None:
        for e in msp:
            dxftype = e.dxftype()
            layer_kind = _layer_kind(getattr(e.dxf, "layer", ""))
            if layer_kind == "skip":
                skipped_layers.add(e.dxf.layer)
                continue
            if layer_kind != kind_filter:
                continue
            segs: list[tuple[tuple[float, float], tuple[float, float]]] = []
            if dxftype == "LINE":
                s, t = e.dxf.start, e.dxf.end
                segs = [((s.x, s.y), (t.x, t.y))]
            elif dxftype == "LWPOLYLINE":
                segs = _polyline_segments(e)
            for p1, p2 in segs:
                length = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
                if length * factor < 50:  # 忽略 5cm 以下碎線
                    continue
                elements.append({"kind": "wall", "p1": list(p1), "p2": list(p2),
                                 "px_length": round(length, 2),
                                 "length_mm": round(length * factor, 1),
                                 "thickness_px": None})

    _collect_lines("wall")
    if not elements:
        warnings.append("未找到牆體圖層（名稱含 WALL／牆），改列出所有非家具、非標註圖層的線段。")
        for e in msp:
            layer_kind = _layer_kind(getattr(e.dxf, "layer", ""))
            if layer_kind in ("skip", "door", "window"):
                continue
            if e.dxftype() == "LINE":
                s, t = e.dxf.start, e.dxf.end
                length = math.hypot(t.x - s.x, t.y - s.y)
                if length * factor >= 50:
                    elements.append({"kind": "wall", "p1": [s.x, s.y], "p2": [t.x, t.y],
                                     "px_length": round(length, 2),
                                     "length_mm": round(length * factor, 1), "thickness_px": None})
            elif e.dxftype() == "LWPOLYLINE":
                for p1, p2 in _polyline_segments(e):
                    length = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
                    if length * factor >= 50:
                        elements.append({"kind": "wall", "p1": list(p1), "p2": list(p2),
                                         "px_length": round(length, 2),
                                         "length_mm": round(length * factor, 1), "thickness_px": None})

    # 門／窗：INSERT 圖塊以邊界框主軸長度作為寬度
    for e in msp.query("INSERT"):
        layer_kind = _layer_kind(getattr(e.dxf, "layer", ""))
        block_kind = _layer_kind(getattr(e.dxf, "name", ""))
        # 門不辨識（使用者規格）：DXF 門圖塊略過，只量測窗寬
        kind = "window" if "window" in (layer_kind, block_kind) else None
        if kind is None:
            continue
        box = bbox.extents([e], fast=True)
        if not box.has_data:
            continue
        size = box.size
        width = max(size.x, size.y)
        if size.x >= size.y:
            p1 = [box.extmin.x, (box.extmin.y + box.extmax.y) / 2]
            p2 = [box.extmax.x, (box.extmin.y + box.extmax.y) / 2]
        else:
            p1 = [(box.extmin.x + box.extmax.x) / 2, box.extmin.y]
            p2 = [(box.extmin.x + box.extmax.x) / 2, box.extmax.y]
        elements.append({"kind": kind, "p1": p1, "p2": p2,
                         "px_length": round(width, 2),
                         "length_mm": round(width * factor, 1), "thickness_px": None})

    if skipped_layers:
        warnings.append("已屏蔽圖層（家具／標註）：" + "、".join(sorted(skipped_layers)))
    warnings.append("雙線牆的內外緣會分別列為兩條牆段，屬本版已知行為。")

    for i, e in enumerate(elements, 1):
        e["id"] = f"{'W' if e['kind'] == 'wall' else 'O'}{i}"

    return {
        "source": "dxf",
        "unit": _UNIT_NAME.get(insunits, str(insunits)),
        "calibration": {"method": "dxf", "mm_per_px": None, "samples": len(elements), "spread": None},
        "elements": elements,
        "warnings": warnings,
    }
