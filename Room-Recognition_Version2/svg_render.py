# -*- coding: utf-8 -*-
"""將辨識結果渲染為 SVG：格線底圖、元素長度標籤（公分）、邊全長加總與空間面積。

標籤防重疊：所有文字標籤經 _Placer 貪婪佈局——空間標籤先佔位（版面錨點），
其餘標籤若與既有標籤相撞，沿法線軸向兩側步進尋找空位，避免數據互相壓字。
"""
from __future__ import annotations

import math

_COLORS = {"wall": "#17313B", "door": "#1F7A8C", "window": "#4E8F5A", "opening": "#8A6D1D"}
_LABELS = {"wall": "牆", "door": "門", "window": "窗", "opening": "開口"}
_DIM_COLOR = "#C22F1D"      # 元素尺寸（紅）
_TOTAL_COLOR = "#1F7A8C"    # 邊全長加總（青）
_ROOM_COLOR = "#7A3E8F"     # 空間面積（紫）
_FURN_COLOR = "#B25B0E"     # 家具偵測框（橙）
_USER_COLOR = "#4E8F5A"     # 使用者定義的家具（綠）：標註／修正／框選的結果
_UNC_COLOR = "#8A8F93"      # 無法辨識物件（灰）
_GRID_MINOR = "#C9D8DD"
_GRID_MAJOR = "#9FB8C0"


def _fmt(e: dict) -> str:
    """長度標籤：已校準以公分（一位小數）呈現，未校準退回像素。"""
    if e.get("length_mm") is not None:
        return f"{e['length_mm'] / 10:.1f} cm"
    return f"{e['px_length']:.0f} px"


def _est_w(s: str, fs: float) -> float:
    """估算文字寬度：CJK 全形 ≈ 字級、半形 ≈ 0.62 字級（IBM Plex Mono）。"""
    return sum(fs * (1.0 if ord(ch) > 0x2E7F else 0.62) for ch in s) or fs


class _Placer:
    """標籤防重疊佈局器：優先原位，相撞時沿指定軸向兩側步進找空位。"""

    def __init__(self) -> None:
        self._boxes: list[tuple[float, float, float, float]] = []

    def reserve(self, box: tuple[float, float, float, float]) -> None:
        self._boxes.append(box)

    @staticmethod
    def _hit(a: tuple, b: tuple) -> bool:
        return (min(a[2], b[2]) - max(a[0], b[0]) > 0
                and min(a[3], b[3]) - max(a[1], b[1]) > 0)

    def place(self, cx: float, cy: float, w: float, h: float,
              axis: str = "y") -> tuple[float, float]:
        step = 1.1 * (h if axis == "y" else w)
        first = None
        for k in range(13):
            for sign in ((1,) if k == 0 else (1, -1)):
                d = sign * k * step
                nx, ny = (cx, cy + d) if axis == "y" else (cx + d, cy)
                box = (nx - w / 2, ny - h / 2, nx + w / 2, ny + h / 2)
                if first is None:
                    first = (nx, ny, box)
                if not any(self._hit(box, b) for b in self._boxes):
                    self.reserve(box)
                    return nx, ny
        self.reserve(first[2])  # 全滿：回到原位，至少不越擺越遠
        return first[0], first[1]


def _text(x: float, y: float, s: str, size: float, fill: str, weight: int = 700,
          rotate: bool = False, anchor: str = "middle", extra: str = "") -> str:
    """白色描邊的標籤文字，確保壓在圖上仍清晰可讀。extra 可掛自訂屬性。"""
    tr = f' transform="rotate(-90 {x:.1f} {y:.1f})"' if rotate else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}"{tr}{extra} font-size="{size:.1f}" '
        f'font-family="IBM Plex Mono, monospace" font-weight="{weight}" fill="{fill}" '
        f'text-anchor="{anchor}" paint-order="stroke" stroke="#FFFFFF" '
        f'stroke-width="{size * 0.32:.1f}" stroke-linejoin="round">{s}</text>'
    )


def _placed_text(placer: _Placer, x: float, y: float, s: str, size: float, fill: str,
                 weight: int = 700, rotate: bool = False, extra: str = "") -> str:
    """經防重疊佈局的標籤：直式沿 x 軸閃避，橫式沿 y 軸閃避。"""
    tw = _est_w(s, size)
    if rotate:
        nx, ny = placer.place(x, y, size * 1.2, tw, axis="x")
    else:
        nx, ny = placer.place(x, y - size * 0.3, tw, size * 1.15, axis="y")
        ny += size * 0.3
    return _text(nx, ny, s, size, fill, weight, rotate, extra=extra)


def _label_pos(e: dict, offset: float) -> tuple[float, float, bool]:
    """回傳 (x, y, 是否直立)。標籤沿元素法線方向偏移。"""
    x1, y1 = e["p1"]
    x2, y2 = e["p2"]
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length, dx / length  # 法線
    return mx + nx * offset, my + ny * offset, abs(dy) > abs(dx)


def _element_svg(e: dict, stroke_w: float, font_size: float, offset: float,
                 placer: _Placer) -> str:
    x1, y1 = e["p1"]
    x2, y2 = e["p2"]
    color = _COLORS.get(e["kind"], "#17313B")
    dash = "" if e["kind"] == "wall" else ' stroke-dasharray="6,5"'
    lx, ly, rot = _label_pos(e, offset)
    label = f"{_LABELS.get(e['kind'], e['kind'])} {_fmt(e)}" if e["kind"] != "wall" else _fmt(e)
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{color}" stroke-width="{stroke_w:.1f}" stroke-opacity="0.75"{dash} '
        f'stroke-linecap="butt"/>'
        + _placed_text(placer, lx, ly, label, font_size, _DIM_COLOR, 700, rot)
    )


def _plan_totals(edge_totals: list[dict], w: float, h: float) -> list[dict]:
    """把每筆全長分配到圖面外側的四邊，並排出互不重疊的尺寸線「車道」。

    水平牆 → 依位置擺上／下側；垂直牆 → 擺左／右側。同一側若跨距重疊，
    自動往外挪一道，因此多條全長不會疊在一起。
    """
    planned: list[dict] = []
    lanes: dict[str, list[list[tuple[float, float]]]] = {}
    order = sorted(edge_totals,
                   key=lambda e: -math.hypot(e["p2"][0] - e["p1"][0],
                                             e["p2"][1] - e["p1"][1]))
    for e in order:
        x1, y1 = e["p1"]
        x2, y2 = e["p2"]
        if abs(x2 - x1) >= abs(y2 - y1):
            side = "top" if (y1 + y2) / 2 < h / 2 else "bottom"
            lo, hi = sorted((x1, x2))
        else:
            side = "left" if (x1 + x2) / 2 < w / 2 else "right"
            lo, hi = sorted((y1, y2))
        side_lanes = lanes.setdefault(side, [])
        lane = None
        for i, spans in enumerate(side_lanes):
            if all(hi <= s_lo or lo >= s_hi for s_lo, s_hi in spans):
                spans.append((lo, hi))
                lane = i
                break
        if lane is None:
            side_lanes.append([(lo, hi)])
            lane = len(side_lanes) - 1
        planned.append({"e": e, "side": side, "lane": lane, "lo": lo, "hi": hi})
    return planned


def _total_outside_svg(p: dict, w: float, h: float, font: float,
                       base: float, step: float, placer: _Placer) -> str:
    """圖面外側的全長尺寸線：延伸線 + 尺寸線 + 端點刻度 + 標籤（不壓在圖上）。"""
    e, side, lane, lo, hi = p["e"], p["side"], p["lane"], p["lo"], p["hi"]
    off = base + lane * step
    tick = max(5.0, font * 0.35)
    label = f"全長 {_fmt(e)}"
    fs = font * 0.95
    vertical = side in ("left", "right")
    if side == "top":
        pos, wall = -off, min(e["p1"][1], e["p2"][1])
    elif side == "bottom":
        pos, wall = h + off, max(e["p1"][1], e["p2"][1])
    elif side == "left":
        pos, wall = -off, min(e["p1"][0], e["p2"][0])
    else:
        pos, wall = w + off, max(e["p1"][0], e["p2"][0])
    away = -1 if side in ("top", "left") else 1   # 遠離圖面的方向

    if vertical:
        a, b = (pos, lo), (pos, hi)
        ext = [((wall, lo), (pos, lo)), ((wall, hi), (pos, hi))]
        t1 = ((pos - tick, lo), (pos + tick, lo))
        t2 = ((pos - tick, hi), (pos + tick, hi))
        lx, ly = pos + away * fs * 0.75, (lo + hi) / 2
    else:
        a, b = (lo, pos), (hi, pos)
        ext = [((lo, wall), (lo, pos)), ((hi, wall), (hi, pos))]
        t1 = ((lo, pos - tick), (lo, pos + tick))
        t2 = ((hi, pos - tick), (hi, pos + tick))
        lx, ly = (lo + hi) / 2, pos + away * fs * 0.55

    def _ln(p1, p2, color, width, dash=""):
        return (f'<line x1="{p1[0]:.1f}" y1="{p1[1]:.1f}" x2="{p2[0]:.1f}" y2="{p2[1]:.1f}" '
                f'stroke="{color}" stroke-width="{width}"{dash}/>')

    tw = _est_w(label, fs)
    box = ((lx - fs * 0.6, ly - tw / 2, lx + fs * 0.6, ly + tw / 2) if vertical
           else (lx - tw / 2, ly - fs * 0.8, lx + tw / 2, ly + fs * 0.4))
    placer.reserve(box)   # 佔位，避免其他標籤飄進尺寸線區
    return "".join([
        _ln(*ext[0], _TOTAL_COLOR, 0.8, ' stroke-opacity="0.45"'),
        _ln(*ext[1], _TOTAL_COLOR, 0.8, ' stroke-opacity="0.45"'),
        _ln(a, b, _TOTAL_COLOR, 1.6),
        _ln(*t1, _TOTAL_COLOR, 1.6),
        _ln(*t2, _TOTAL_COLOR, 1.6),
        _text(lx, ly, label, fs, _TOTAL_COLOR, 700, rotate=vertical),
    ])


def _furniture_svg(item: dict, font: float, placer: _Placer) -> str:
    """家具偵測框：模型偵測＝虛線橙框＋信心分數；使用者定義＝實線綠框＋「✔ 自訂」。"""
    x, y, w, h = item["bbox"]
    fs = font * 0.8
    tag = f' data-furn="{item["id"]}"' if item.get("id") else ""
    user = bool(item.get("user_defined"))
    color = _USER_COLOR if user else _FURN_COLOR
    dash = "" if user else ' stroke-dasharray="7,4"'
    label = f"{item['label']} ✔ 自訂" if user else f"{item['label']} {item['score']:.2f}"
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
        f'fill="none" stroke="{color}" stroke-width="{2.4 if user else 2}"{dash}{tag}/>'
        + _placed_text(placer, x + w / 2, y - fs * 0.4, label, fs, color, 600, extra=tag)
    )


def _uncertain_svg(item: dict, font: float, placer: _Placer) -> str:
    """無法辨識物件：灰色點狀框＋「？」標籤，提示已存入 uncertain 資料夾。"""
    x, y, w, h = item["bbox"]
    fs = font * 0.75
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
        f'fill="none" stroke="{_UNC_COLOR}" stroke-width="1.6" stroke-dasharray="2,4"/>'
        + _placed_text(placer, x + w / 2, y - fs * 0.4, f"？{item['id']}", fs,
                       _UNC_COLOR, 600)
    )


def _room_box_svg(r: dict) -> str:
    """空間範圍框：第二軌拆出的機能空間畫虛線外框，讓範圍一目瞭然。"""
    x, y, w, h = r["bbox"]
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'fill="{_ROOM_COLOR}" fill-opacity="0.04" stroke="{_ROOM_COLOR}" '
            f'stroke-width="2" stroke-dasharray="13,7" stroke-opacity="0.7" '
            f'data-roombox="{r["id"]}"/>')


def _room_svg(r: dict, font: float, placer: _Placer) -> str:
    """空間面積標籤：空間名稱（可由前端動態更名）、面積、±5% 區間與外框寬高。

    空間標籤為版面錨點——原位保留並向佈局器佔位，其餘標籤閃避它。
    """
    cx, cy = r.get("label_pos") or r["centroid"]
    fs1, fs2 = font * 1.15, font * 0.85
    name = f"{r['id']}　{r['room_type']}" if r.get("room_type") else f"{r['id']}　未判定"
    if r.get("area_m2") is not None:
        line2 = f"{r['area_m2']:.2f} m²（±5%：{r['area_m2_min']:.2f}–{r['area_m2_max']:.2f}）"
        line3 = f"約 {r['w_m'] * 100:.1f} × {r['h_m'] * 100:.1f} cm"
    else:
        a = r["area_px"]
        line2 = f"{a:,} px²（±5%：{a * 0.95:,.0f}–{a * 1.05:,.0f}）"
        line3 = f"約 {r['bbox'][2]} × {r['bbox'][3]} px"
    w_max = max(_est_w(name, fs1), _est_w(line2, fs2), _est_w(line3, fs2))
    placer.reserve((cx - w_max / 2, cy - fs1 * 1.6, cx + w_max / 2, cy + fs2 * 2.5))
    tag = f' data-roomlabel="{r["id"]}"'   # 三行都可整組移除，供前端切割空間後重繪
    return (
        _text(cx, cy - fs1 * 0.7, name, fs1, _ROOM_COLOR,
              extra=f' data-room="{r["id"]}"{tag}')
        + _text(cx, cy + fs2 * 0.6, line2, fs2, _ROOM_COLOR, 600, extra=tag)
        + _text(cx, cy + fs2 * 1.9, line3, fs2, _ROOM_COLOR, 600, extra=tag)
    )


def _grid(x0: float, y0: float, x1: float, y1: float, step: float) -> str:
    """參考格線：每 5 格加深一次。"""
    parts = []
    for i in range(math.floor(x0 / step), math.ceil(x1 / step) + 1):
        x = i * step
        major = i % 5 == 0
        parts.append(
            f'<line x1="{x:.1f}" y1="{y0:.1f}" x2="{x:.1f}" y2="{y1:.1f}" '
            f'stroke="{_GRID_MAJOR if major else _GRID_MINOR}" '
            f'stroke-width="{1.4 if major else 0.7}"/>')
    for j in range(math.floor(y0 / step), math.ceil(y1 / step) + 1):
        y = j * step
        major = j % 5 == 0
        parts.append(
            f'<line x1="{x0:.1f}" y1="{y:.1f}" x2="{x1:.1f}" y2="{y:.1f}" '
            f'stroke="{_GRID_MAJOR if major else _GRID_MINOR}" '
            f'stroke-width="{1.4 if major else 0.7}"/>')
    return "".join(parts)


def render_png_svg(result: dict, background: str = "original") -> str:
    """PNG 標註圖。background='original' 疊原圖；'structural' 疊屏蔽後結構圖。"""
    w, h = result["image_size"]
    t = result.get("wall_thickness_px", 12) or 12
    font = max(16.0, t * 1.2)
    offset = t * 1.1 + font * 0.9
    mmpp = (result.get("calibration") or {}).get("mm_per_px")
    step = (1000.0 / mmpp) if mmpp else 100.0  # 校準後每格 1 公尺；否則 100 px

    # 全長標註一律排在圖面外側：先排車道，再據以決定留白寬度
    tot_base, tot_step = font * 2.0, font * 2.4
    planned = _plan_totals(result.get("edge_totals", []), w, h)
    max_lane = max((p["lane"] for p in planned), default=-1)
    margin = max(48.0, font * 3.0,
                 tot_base + (max_lane + 1) * tot_step + font * 1.6)
    x0, y0 = -margin, -margin
    vw, vh = w + margin * 2, h + margin * 2
    b64 = result.get("original_png_b64") if background == "original" else result.get("structural_png_b64")

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0:.0f} {y0:.0f} {vw:.0f} {vh:.0f}" '
        f'width="100%" preserveAspectRatio="xMidYMid meet">',
        f'<rect x="{x0:.0f}" y="{y0:.0f}" width="{vw:.0f}" height="{vh:.0f}" fill="#FFFFFF"/>',
    ]
    if b64:
        parts.append(f'<image href="data:image/png;base64,{b64}" '
                     f'x="0" y="0" width="{w}" height="{h}" opacity="0.4"/>')
    # 參考格線（淺色，位於底圖之上、標註之下）
    parts.append(f'<g opacity="0.55">{_grid(x0, y0, x0 + vw, y0 + vh, step)}</g>')
    note = f"格線間距：{'100 cm' if mmpp else '100 px'}"
    note_fs = font * 0.85
    parts.append(_text(x0 + 8, y0 + vh - 10, note, note_fs, "#5E7780", 600, anchor="start"))

    # 佈局優先序：全長（位置固定於圖外，先佔位）→ 空間標籤 → 元素尺寸 → 家具 → 分區 → 待確認
    placer = _Placer()
    placer.reserve((x0, y0 + vh - 10 - note_fs, x0 + _est_w(note, note_fs) + 16, y0 + vh))
    total_parts = [_total_outside_svg(p, w, h, font, tot_base, tot_step, placer)
                   for p in planned]
    rooms = result.get("rooms", [])
    room_parts = [_room_svg(r, font, placer) for r in rooms]
    elem_parts = []
    for e in result["elements"]:
        stroke = max(3.0, (e.get("thickness_px") or t) * 0.55)
        elem_parts.append(_element_svg(e, stroke, font, offset, placer))
    furn_parts = [_furniture_svg(item, font, placer)
                  for item in result.get("furniture", [])]
    box_parts = [_room_box_svg(r) for r in rooms]
    unc_parts = [_uncertain_svg(item, font, placer)
                 for item in result.get("uncertain", [])]

    # 疊圖順序（下→上）：待確認 → 家具 → 空間框 → 空間標籤 → 元素 → 全長
    parts += unc_parts + furn_parts + box_parts + room_parts + elem_parts + total_parts
    parts.append("</svg>")
    return "".join(parts)


def render_dxf_svg(result: dict) -> str:
    elements = result["elements"]
    if not elements:
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"></svg>'
    xs = [p for e in elements for p in (e["p1"][0], e["p2"][0])]
    ys = [p for e in elements for p in (e["p1"][1], e["p2"][1])]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    span = max(max_x - min_x, max_y - min_y) or 1.0
    pad = span * 0.08
    # DXF 為 y 向上，SVG 為 y 向下：翻轉 y
    def fy(y: float) -> float:
        return (max_y - y) + pad

    def fx(x: float) -> float:
        return (x - min_x) + pad

    view_w = (max_x - min_x) + pad * 2
    view_h = (max_y - min_y) + pad * 2
    font = span * 0.024
    stroke = span * 0.006
    placer = _Placer()
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {view_w:.1f} {view_h:.1f}" '
             f'width="100%" preserveAspectRatio="xMidYMid meet">',
             f'<rect x="0" y="0" width="{view_w:.1f}" height="{view_h:.1f}" fill="#FFFFFF"/>',
             f'<g opacity="0.55">{_grid(0, 0, view_w, view_h, 1000.0)}</g>']
    for e in elements:
        proj = {**e, "p1": [fx(e["p1"][0]), fy(e["p1"][1])], "p2": [fx(e["p2"][0]), fy(e["p2"][1])]}
        parts.append(_element_svg(proj, stroke, font, font * 1.4, placer))
    parts.append("</svg>")
    return "".join(parts)
