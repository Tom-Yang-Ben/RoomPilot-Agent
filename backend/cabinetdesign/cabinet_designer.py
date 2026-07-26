#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系統櫃設計工具（單檔版）
================================
拖曳即可快速設計：弧形櫃 / 燈槽 / 免把手 / 櫥櫃
畫完櫃體可一鍵產出「施工圖 DXF」與「報價清單 CSV」，尺寸自動標註。

用法：
    python3 cabinet_designer.py            # 啟動後自動開瀏覽器
    python3 cabinet_designer.py --port 9000

操作：
    * 左側模組「按住拖曳」到牆面放開即放置（或點一下模組再點牆面）
    * 點選櫃體可拖曳移動、拉四周控制點改尺寸，自動對齊格線與鄰櫃
    * 右側面板改寬高深、免把手、弧形方向、門片數
    * Delete 刪除、Ctrl+D 複製、方向鍵微調 1cm（Shift=10cm）
    * 上方按鈕：施工圖(DXF)、報價清單、存檔/開啟(JSON)

單價都放在下方 PRICE / RATE 區，直接改數字即可套用到報價。
"""

import argparse
import datetime
import io
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import ezdxf
    HAS_EZDXF = True
except ImportError:
    HAS_EZDXF = False

# ============================================================================
# 報價參數（NTD，示意單價，請依實際行情修改）
# ============================================================================

RATE = {          # 櫃身板材：立面面積(寬×高 m²) × 單價 × 深度係數(深/60cm)
    "base":   5200,   # 下櫃（門片）
    "drawer": 6500,   # 抽屜櫃
    "wall":   4800,   # 吊櫃
    "tall":   5600,   # 高櫃
    "open":   3800,   # 開放櫃
    "arc":    6800,   # 弧形櫃
}
PRICE = {
    "hinge":        120,    # 緩衝鉸鏈/顆（每門 2 顆）
    "handle":       150,    # 一般把手/支
    "gola_per_m":   450,    # 免把手鋁槽/米
    "rail":         550,    # 緩衝滑軌/組（每抽 1 組）
    "arc_extra":    2500,   # 弧形加工費/座
    "led_per_m":    900,    # LED 燈條含變壓器/米
    "trough_per_m": 600,    # 燈槽板材/米
    "counter_per_m": 3200,  # 檯面/米
    "install_pct":  0.10,   # 施工安裝費（板材五金小計 ×10%）
    # ---- 內裝零件 ----
    "shelf":        450,    # 層板/片（含銅珠）
    "drawer_int":  1500,    # 內抽屜/組（含滑軌）
    "rod":          350,    # 吊桿/支
    "vdiv":         600,    # 直立隔板/片
}
PART_NAME = {"shelf": "層板", "drawer": "內抽屜", "rod": "吊桿", "vdiv": "隔板"}
PART_PRICE_KEY = {"shelf": "shelf", "drawer": "drawer_int", "rod": "rod", "vdiv": "vdiv"}

TYPE_NAME = {
    "base": "下櫃", "drawer": "抽屜櫃", "wall": "吊櫃", "tall": "高櫃",
    "open": "開放櫃", "arc": "弧形櫃", "light": "燈槽", "counter": "檯面",
}
DOOR_TYPES = {"base", "wall", "tall", "arc"}


def auto_doors(m):
    n = m.get("opts", {}).get("doors") or 0
    if n:
        return int(n)
    return max(1, round(m["w"] / 50.0))


def module_rows(m, idx):
    """回傳 (品名, 規格, 明細說明, 小計)"""
    t = m["type"]
    w_m, h_m = m["w"] / 100.0, m["h"] / 100.0
    d = m.get("d", 60)
    opts = m.get("opts", {})
    name = f"M{idx} {TYPE_NAME.get(t, t)}"
    spec = f"W{m['w']:.0f}×H{m['h']:.0f}×D{d:.0f}cm"
    details, total = [], 0.0

    if t == "light":
        led = PRICE["led_per_m"] * w_m
        trough = PRICE["trough_per_m"] * w_m
        details.append(f"LED燈條 {w_m:.2f}m×{PRICE['led_per_m']}")
        details.append(f"燈槽板材 {w_m:.2f}m×{PRICE['trough_per_m']}")
        total = led + trough
    elif t == "counter":
        total = PRICE["counter_per_m"] * w_m
        details.append(f"檯面 {w_m:.2f}m×{PRICE['counter_per_m']}")
    else:
        depth_k = max(0.5, d / 60.0)
        body = RATE.get(t, 4500) * w_m * h_m * depth_k
        details.append(f"櫃身 {w_m*h_m:.2f}m²×{RATE.get(t,4500)}×深度{depth_k:.2f}")
        total = body
        if t == "drawer":
            drawers = int(opts.get("drawers") or 4)
            total += PRICE["rail"] * drawers
            details.append(f"滑軌 {drawers}組×{PRICE['rail']}")
        elif t in DOOR_TYPES:
            doors = auto_doors(m)
            total += PRICE["hinge"] * 2 * doors
            details.append(f"鉸鏈 {doors*2}顆×{PRICE['hinge']}")
            if opts.get("handleless"):
                total += PRICE["gola_per_m"] * w_m
                details.append(f"免把手鋁槽 {w_m:.2f}m×{PRICE['gola_per_m']}")
            else:
                total += PRICE["handle"] * doors
                details.append(f"把手 {doors}支×{PRICE['handle']}")
        if t == "arc":
            total += PRICE["arc_extra"]
            details.append(f"弧形加工 {PRICE['arc_extra']}")
        if opts.get("led"):
            total += PRICE["led_per_m"] * w_m
            details.append(f"層板燈 {w_m:.2f}m×{PRICE['led_per_m']}")
        # 內裝零件計價
        pc = {}
        for p in m.get("parts", []):
            pc[p["kind"]] = pc.get(p["kind"], 0) + 1
        for k, n in pc.items():
            price = PRICE[PART_PRICE_KEY[k]]
            total += price * n
            details.append(f"{PART_NAME[k]} {n}×{price}")
    return name, spec, "、".join(details), round(total)


def build_quote(design):
    rows = []
    subtotal = 0
    for i, m in enumerate(design.get("modules", []), 1):
        name, spec, detail, total = module_rows(m, i)
        rows.append({"name": name, "spec": spec, "detail": detail, "subtotal": total})
        subtotal += total
    install = round(subtotal * PRICE["install_pct"])
    return {
        "rows": rows,
        "subtotal": subtotal,
        "install": install,
        "install_pct": int(PRICE["install_pct"] * 100),
        "grand": subtotal + install,
        "date": datetime.date.today().isoformat(),
    }


def quote_csv(design):
    q = build_quote(design)
    buf = io.StringIO()
    buf.write("\ufeff")  # BOM，Excel 直接開不亂碼
    import csv as _csv
    w = _csv.writer(buf)
    w.writerow([f"系統櫃報價單  {q['date']}"])
    w.writerow(["品名", "規格", "明細", "小計(NTD)"])
    for r in q["rows"]:
        w.writerow([r["name"], r["spec"], r["detail"], r["subtotal"]])
    w.writerow([])
    w.writerow(["板材五金小計", "", "", q["subtotal"]])
    w.writerow([f"施工安裝費({q['install_pct']}%)", "", "", q["install"]])
    w.writerow(["總計", "", "", q["grand"]])
    w.writerow([])
    w.writerow(["※ 單價為示意值，請於 cabinet_designer.py 開頭 PRICE/RATE 區修改"])
    return buf.getvalue().encode("utf-8")


# ============================================================================
# 施工圖 DXF（單位 mm，立面圖 + 自動標註 + 模組表 + 圖框）
# ============================================================================

def _dim_h(msp, x1, x2, y, off):
    """水平標註"""
    if abs(x2 - x1) < 1:
        return
    dim = msp.add_linear_dim(
        base=(x1, y - off), p1=(x1, y), p2=(x2, y), dimstyle="EZDXF",
        override={"dimtxt": 45, "dimasz": 25, "dimexo": 10, "dimexe": 15,
                  "dimclrd": 3, "dimclrt": 3},
        dxfattribs={"layer": "DIM"})
    dim.render()


def _dim_v(msp, y1, y2, x, off):
    """垂直標註"""
    if abs(y2 - y1) < 1:
        return
    dim = msp.add_linear_dim(
        base=(x - off, y1), p1=(x, y1), p2=(x, y2), angle=90, dimstyle="EZDXF",
        override={"dimtxt": 45, "dimasz": 25, "dimexo": 10, "dimexe": 15,
                  "dimclrd": 3, "dimclrt": 3},
        dxfattribs={"layer": "DIM"})
    dim.render()


def _rect(msp, x, y, w, h, layer):
    msp.add_lwpolyline(
        [(x, y), (x + w, y), (x + w, y + h), (x, y + h)],
        close=True, dxfattribs={"layer": layer})


def make_dxf(design):
    if not HAS_EZDXF:
        raise RuntimeError("未安裝 ezdxf，請先 pip install ezdxf")
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4  # mm
    for name, color in [("WALL", 8), ("CAB", 7), ("DOOR", 5), ("ARC", 1),
                        ("LIGHT", 2), ("DIM", 3), ("TEXT", 7), ("TITLE", 6),
                        ("PART", 4)]:
        doc.layers.add(name, color=color)
    # 中文字型樣式：預設 Standard 樣式無中文字形，CAD 會顯示 ????
    # 開圖電腦需有「微軟正黑體」(Windows 內建)；若無可改成 kaiu.ttf(標楷)、simsun.ttc 等
    doc.styles.add("CJK", font="msjh.ttc")
    msp = doc.modelspace()

    wall = design.get("wall", {"w": 360, "h": 240})
    W, H = wall["w"] * 10.0, wall["h"] * 10.0
    mods = design.get("modules", [])

    # 牆面 + 地板線
    _rect(msp, 0, 0, W, H, "WALL")
    msp.add_line((-300, 0), (W + 300, 0), dxfattribs={"layer": "WALL"})

    xs, ys = {0.0, W}, {0.0, H}
    for i, m in enumerate(mods, 1):
        x, y = m["x"] * 10.0, m["y"] * 10.0
        w, h = m["w"] * 10.0, m["h"] * 10.0
        t = m["type"]
        opts = m.get("opts", {})
        xs.update((round(x, 1), round(x + w, 1)))
        ys.update((round(y, 1), round(y + h, 1)))

        if t == "light":
            _rect(msp, x, y, w, h, "LIGHT")
            step = 120.0
            k = x + step
            while k < x + w:      # 燈槽斜線示意
                msp.add_line((k, y), (k - step * 0.6, y + h),
                             dxfattribs={"layer": "LIGHT"})
                k += step
        elif t == "counter":
            _rect(msp, x, y, w, h, "CAB")
        elif t == "arc":
            side = opts.get("arcSide", "right")
            r = min(w * 0.9, 300.0)
            if side == "right":
                pts = [(x + w - r, y), (x, y), (x, y + h), (x + w - r, y + h)]
                msp.add_lwpolyline(pts, dxfattribs={"layer": "ARC"})
                msp.add_arc((x + w - r, y + r), r, 270, 360, dxfattribs={"layer": "ARC"})
                msp.add_arc((x + w - r, y + h - r), r, 0, 90, dxfattribs={"layer": "ARC"})
                msp.add_line((x + w, y + r), (x + w, y + h - r), dxfattribs={"layer": "ARC"})
            else:
                pts = [(x + r, y), (x + w, y), (x + w, y + h), (x + r, y + h)]
                msp.add_lwpolyline(pts, dxfattribs={"layer": "ARC"})
                msp.add_arc((x + r, y + r), r, 180, 270, dxfattribs={"layer": "ARC"})
                msp.add_arc((x + r, y + h - r), r, 90, 180, dxfattribs={"layer": "ARC"})
                msp.add_line((x, y + r), (x, y + h - r), dxfattribs={"layer": "ARC"})
        else:
            _rect(msp, x, y, w, h, "CAB")
            if t == "drawer":
                n = int(opts.get("drawers") or 4)
                for j in range(1, n):
                    yy = y + h * j / n
                    msp.add_line((x, yy), (x + w, yy), dxfattribs={"layer": "DOOR"})
            elif t == "open":
                n = max(1, int(h // 350))
                for j in range(1, n + 1):
                    yy = y + h * j / (n + 1)
                    msp.add_line((x + 20, yy), (x + w - 20, yy),
                                 dxfattribs={"layer": "DOOR"})
            elif t in DOOR_TYPES:
                doors = auto_doors(m)
                for j in range(1, doors):
                    xx = x + w * j / doors
                    msp.add_line((xx, y), (xx, y + h), dxfattribs={"layer": "DOOR"})
                if opts.get("handleless"):   # 免把手斜溝
                    msp.add_line((x, y + h - 60), (x + w, y + h - 60),
                                 dxfattribs={"layer": "DOOR"})

        # ---- 內裝零件（層板/內抽/吊桿/隔板）----
        parts = m.get("parts", [])
        if parts:
            T2 = 20.0  # 板厚 2cm(mm)
            vxs = sorted(p["x"] * 10.0 for p in parts if p["kind"] == "vdiv")

            def bay_of(px_):
                lo = T2
                for vx in vxs:
                    if px_ < vx:
                        return lo, vx - 10
                    lo = vx + 10
                return lo, w - T2

            for p in parts:
                k = p["kind"]
                if k == "vdiv":
                    vx = p["x"] * 10.0
                    _rect(msp, x + vx - 10, y + T2, 20, h - 2 * T2, "PART")
                    continue
                b0, b1 = bay_of(p.get("x", 0) * 10.0)
                pyy = p.get("y", 0) * 10.0
                if k == "shelf":
                    _rect(msp, x + b0, y + pyy - 10, b1 - b0, 20, "PART")
                elif k == "drawer":
                    ph = p.get("h", 20) * 10.0
                    _rect(msp, x + b0, y + pyy, b1 - b0, ph, "PART")
                    cxm = x + (b0 + b1) / 2
                    msp.add_line((cxm - 60, y + pyy + ph * 0.6),
                                 (cxm + 60, y + pyy + ph * 0.6),
                                 dxfattribs={"layer": "PART"})
                elif k == "rod":
                    msp.add_line((x + b0 + 10, y + pyy), (x + b1 - 10, y + pyy),
                                 dxfattribs={"layer": "PART"})
                    msp.add_circle((x + b0 + 30, y + pyy), 15, dxfattribs={"layer": "PART"})
                    msp.add_circle((x + b1 - 30, y + pyy), 15, dxfattribs={"layer": "PART"})

        msp.add_text(f"M{i}", height=60, dxfattribs={"layer": "TEXT", "style": "CJK"}
                     ).set_placement((x + w / 2, y + h / 2), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

    # ---- 自動標註：下方鏈狀 + 總寬；左側鏈狀 + 總高 ----
    xs = sorted(xs)
    for a, b in zip(xs, xs[1:]):
        _dim_h(msp, a, b, 0, 200)
    _dim_h(msp, 0, W, 0, 450)
    ys = sorted(ys)
    for a, b in zip(ys, ys[1:]):
        _dim_v(msp, a, b, 0, 200)
    _dim_v(msp, 0, H, 0, 450)

    # ---- 模組表 ----
    tx, ty = W + 600, H
    msp.add_text("模組表", height=70, dxfattribs={"layer": "TEXT", "style": "CJK"}
                 ).set_placement((tx, ty + 100))
    for i, m in enumerate(mods, 1):
        opts = m.get("opts", {})
        tags = []
        if opts.get("handleless"):
            tags.append("免把手")
        if m["type"] == "arc":
            tags.append("弧形" + ("右" if opts.get("arcSide", "right") == "right" else "左"))
        if opts.get("led") or m["type"] == "light":
            tags.append("LED")
        pc = {}
        for p in m.get("parts", []):
            pc[p["kind"]] = pc.get(p["kind"], 0) + 1
        if pc:
            tags.append("+".join(f"{PART_NAME[k]}x{n}" for k, n in pc.items()))
        line = (f"M{i}  {TYPE_NAME.get(m['type'], m['type'])}  "
                f"W{m['w']:.0f}xH{m['h']:.0f}xD{m.get('d', 60):.0f}cm  "
                f"{' '.join(tags)}")
        msp.add_text(line, height=50, dxfattribs={"layer": "TEXT", "style": "CJK"}
                     ).set_placement((tx, ty - i * 100))

    # ---- 圖框 ----
    today = datetime.date.today().isoformat()
    title = design.get("title", "系統櫃立面施工圖")
    msp.add_text(f"{title}   比例1:20   單位:mm   日期:{today}",
                 height=80, dxfattribs={"layer": "TITLE", "style": "CJK"}
                 ).set_placement((0, -900))

    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


# ============================================================================
# 前端頁面（Canvas 拖曳設計器）
# ============================================================================

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>系統櫃設計</title>
<style>
:root{--bg:#1e2126;--panel:#282c34;--line:#3a4048;--fg:#e8eaed;--dim:#9aa3ad;--acc:#4da3ff;}
*{box-sizing:border-box;margin:0;padding:0;font-family:"Noto Sans TC","Microsoft JhengHei",sans-serif;}
body{background:var(--bg);color:var(--fg);height:100vh;display:flex;flex-direction:column;overflow:hidden;}
header{display:flex;align-items:center;gap:8px;padding:8px 12px;background:var(--panel);border-bottom:1px solid var(--line);flex-wrap:wrap;}
header h1{font-size:16px;margin-right:12px;}
header .sub{color:var(--dim);font-size:12px;margin-right:auto;}
button{background:#333a44;color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:6px 12px;font-size:13px;cursor:pointer;}
button:hover{background:#3d4550;border-color:var(--acc);}
header select{background:#333a44;color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:6px 10px;font-size:13px;cursor:pointer;}
header select:hover{border-color:var(--acc);}
button.primary{background:var(--acc);border-color:var(--acc);color:#08243f;font-weight:700;}
main{flex:1;display:flex;min-height:0;}
#palette{width:150px;background:var(--panel);border-right:1px solid var(--line);padding:10px;overflow-y:auto;}
#palette h2,#props h2{font-size:12px;color:var(--dim);margin-bottom:8px;letter-spacing:2px;}
.pal{border:1px solid var(--line);border-radius:8px;padding:8px;margin-bottom:8px;cursor:grab;background:#2f343d;user-select:none;text-align:center;}
.pal:hover{border-color:var(--acc);}
.pal svg{display:block;margin:0 auto 4px;}
.pal .t{font-size:13px;}
.pal .s{font-size:11px;color:var(--dim);}
#stage{flex:1;position:relative;min-width:0;}
canvas{position:absolute;inset:0;width:100%;height:100%;touch-action:none;}
#props{width:250px;background:var(--panel);border-left:1px solid var(--line);padding:10px;overflow-y:auto;font-size:13px;}
#props .row{display:flex;align-items:center;gap:6px;margin-bottom:8px;}
#props label{width:74px;color:var(--dim);flex:none;}
#props input[type=number],#props select,#props input[type=text]{flex:1;min-width:0;background:#1b1e23;color:var(--fg);border:1px solid var(--line);border-radius:4px;padding:4px 6px;font-size:13px;}
#props .hint{color:var(--dim);font-size:11px;line-height:1.7;margin-top:12px;border-top:1px solid var(--line);padding-top:8px;}
#ghost{position:fixed;pointer-events:none;border:2px dashed var(--acc);background:rgba(77,163,255,.15);border-radius:4px;display:none;z-index:50;}
#modal{position:fixed;inset:0;background:rgba(0,0,0,.55);display:none;align-items:center;justify-content:center;z-index:100;}
#modal .box{background:var(--panel);border:1px solid var(--line);border-radius:10px;max-width:780px;width:92%;max-height:84vh;display:flex;flex-direction:column;}
#modal .head{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;border-bottom:1px solid var(--line);}
#modal .body{padding:12px 16px;overflow:auto;}
#modal table{width:100%;border-collapse:collapse;font-size:13px;}
#modal th,#modal td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top;}
#modal td:last-child,#modal th:last-child{text-align:right;white-space:nowrap;}
#modal .detail{color:var(--dim);font-size:12px;}
#modal .foot{padding:12px 16px;border-top:1px solid var(--line);display:flex;gap:8px;justify-content:flex-end;}
.grand{font-size:16px;font-weight:700;color:var(--acc);}
</style>
</head>
<body>
<header>
  <h1>系統櫃設計</h1>
  <span class="sub">拖曳即可快速設計｜弧形櫃・燈槽・免把手・櫥櫃</span>
  <select id="selDemo"><option value="">📚 範例配置 ▾</option></select>
  <button id="btnClear">清空</button>
  <button id="btnSave">存檔</button>
  <button id="btnLoad">開啟</button>
  <input type="file" id="fileLoad" accept=".json" style="display:none">
  <button id="btnDone" class="primary" style="display:none">✔ 完成內裝</button>
  <button id="btn3D">3D 立體圖</button>
  <button id="btnDoors">3D門片:開</button>
  <button id="btnQuote">報價清單</button>
  <button id="btnDxf" class="primary">產出施工圖 DXF</button>
</header>
<main>
  <div id="palette"><h2>模組（拖到牆面）</h2></div>
  <div id="stage"><canvas id="cv" tabindex="0"></canvas></div>
  <div id="props">
    <h2>屬性</h2>
    <div id="propBody"><div style="color:var(--dim)">尚未選取櫃體。<br><br>牆面尺寸：</div>
    </div>
    <div class="row"><label>牆寬 cm</label><input type="number" id="wallW" value="360" min="60" max="1200"></div>
    <div class="row"><label>牆高 cm</label><input type="number" id="wallH" value="240" min="120" max="500"></div>
    <div id="selProps"></div>
    <div class="hint">
      <b>雙擊櫃體＝編輯內裝</b>（層板/抽屜/吊桿/隔板）<br>
      Delete 刪除選取｜Ctrl+D 複製<br>
      方向鍵微調 1cm（Shift = 10cm）<br>
      拖曳自動吸附格線與鄰櫃邊緣<br>
      尺寸標註自動更新<br>
      3D 立體圖：拖曳旋轉、滾輪縮放<br>
      「3D門片:開/關」一鍵看所有內裝<br>
      3D 中雙擊櫃體＝進入內裝編輯
    </div>
  </div>
</main>
<div id="ghost"></div>
<div id="modal"><div class="box">
  <div class="head"><b>報價清單</b><button onclick="closeModal()">✕</button></div>
  <div class="body" id="modalBody"></div>
  <div class="foot"><button id="btnCsv">下載 CSV</button><button class="primary" onclick="closeModal()">關閉</button></div>
</div></div>
<script>
"use strict";
/* ------------------ 資料模型（單位 cm，y 從地板起算） ------------------ */
const TYPES = {
  base:   {name:"下櫃",   w:90,  h:72,  d:60, y:10,  color:"#6f8faf"},
  drawer: {name:"抽屜櫃", w:60,  h:72,  d:60, y:10,  color:"#7f9f8f"},
  wall:   {name:"吊櫃",   w:90,  h:72,  d:35, y:145, color:"#8f7faf"},
  tall:   {name:"高櫃",   w:60,  h:220, d:60, y:10,  color:"#af8f6f"},
  open:   {name:"開放櫃", w:80,  h:120, d:30, y:60,  color:"#6fa3a3"},
  arc:    {name:"弧形櫃", w:45,  h:72,  d:60, y:10,  color:"#c98f9f"},
  light:  {name:"燈槽",   w:90,  h:6,   d:12, y:139, color:"#e8c96f"},
  counter:{name:"檯面",   w:90,  h:4,   d:62, y:82,  color:"#b8b8b8"},
};
const PARTS = {   // 內裝零件
  shelf: {name:"層板",     sub:"橫向隔層"},
  drawer:{name:"內抽屜",   sub:"含滑軌"},
  rod:   {name:"吊桿",     sub:"掛衣桿"},
  vdiv:  {name:"直立隔板", sub:"分隔左右"},
};
const INTERIOR_TYPES = ["base","wall","tall","open","arc"];
const T = 2;   // 板厚 cm
let design = {title:"系統櫃立面施工圖", wall:{w:360,h:240}, modules:[]};
let nextId = 1, selId = null;
let editM = null, selPart = null;      // 內裝編輯狀態
let ES = 1, EOX = 0, EOY = 0;          // 內裝編輯視圖轉換

function interior(m){return {x0:T, x1:m.w-T, y0:T, y1:m.h-T};}
function bays(m){   // 直立隔板切出的格（bay）清單 [[x0,x1],...]
  const iv=interior(m);
  const xs=(m.parts||[]).filter(p=>p.kind==="vdiv").map(p=>p.x).sort((a,b)=>a-b);
  const bs=[]; let L=iv.x0;
  for(const x of xs){bs.push([L,x-1]); L=x+1;}
  bs.push([L,iv.x1]); return bs;
}
function bayOf(m,x){
  for(const b of bays(m)) if(x>=b[0]-1.5&&x<=b[1]+1.5) return b;
  return bays(m)[0];
}

const cv = document.getElementById("cv"), ctx = cv.getContext("2d");
const stage = document.getElementById("stage"), ghost = document.getElementById("ghost");
let S = 1, OX = 0, OY = 0;   // 縮放與原點（畫布像素）

function fit(){
  const r = stage.getBoundingClientRect();
  cv.width = r.width * devicePixelRatio; cv.height = r.height * devicePixelRatio;
  ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);
  const mL=90, mR=40, mT=40, mB=90;   // 留標註空間
  S = Math.min((r.width-mL-mR)/design.wall.w, (r.height-mT-mB)/design.wall.h);
  OX = mL; OY = mT + design.wall.h*S;  // OY = 地板的像素 y
  draw();
}
window.addEventListener("resize", fit);

const px = (x)=> OX + x*S;
const py = (y)=> OY - y*S;            // 模型 y(離地) → 像素
const mx = (X)=> (X-OX)/S;
const my = (Y)=> (OY-Y)/S;

/* ------------------ 繪製 ------------------ */
function draw(){
  if(editM){mode3d?drawEdit3D():drawEdit();return;}
  if(mode3d){draw3D();return;}
  const r = stage.getBoundingClientRect();
  ctx.clearRect(0,0,r.width,r.height);
  const W=design.wall.w, H=design.wall.h;

  // 牆面底
  ctx.fillStyle="#23272e";
  ctx.fillRect(px(0),py(H),W*S,H*S);
  // 格線 10cm
  ctx.strokeStyle="rgba(255,255,255,.05)"; ctx.lineWidth=1;
  ctx.beginPath();
  for(let x=0;x<=W;x+=10){ctx.moveTo(px(x),py(0));ctx.lineTo(px(x),py(H));}
  for(let y=0;y<=H;y+=10){ctx.moveTo(px(0),py(y));ctx.lineTo(px(W),py(y));}
  ctx.stroke();
  // 牆框 + 地板
  ctx.strokeStyle="#aab2bd"; ctx.lineWidth=2;
  ctx.strokeRect(px(0),py(H),W*S,H*S);
  ctx.beginPath();ctx.moveTo(px(0)-30,py(0));ctx.lineTo(px(W)+30,py(0));ctx.stroke();

  for(const m of design.modules) drawModule(m);
  drawDims();
  const sel = getSel();
  if(sel) drawHandles(sel);
}

function roundedSidePath(m){
  // 弧形櫃：外側上下角以大圓角表現
  const x=px(m.x), y=py(m.y+m.h), w=m.w*S, h=m.h*S;
  const right = (m.opts.arcSide||"right")==="right";
  const r = Math.min(w*0.9, 30*S, h/2);
  ctx.beginPath();
  if(right){
    ctx.moveTo(x,y); ctx.lineTo(x+w-r,y); ctx.quadraticCurveTo(x+w,y,x+w,y+r);
    ctx.lineTo(x+w,y+h-r); ctx.quadraticCurveTo(x+w,y+h,x+w-r,y+h);
    ctx.lineTo(x,y+h); ctx.closePath();
  }else{
    ctx.moveTo(x+w,y); ctx.lineTo(x+r,y); ctx.quadraticCurveTo(x,y,x,y+r);
    ctx.lineTo(x,y+h-r); ctx.quadraticCurveTo(x,y+h,x+r,y+h);
    ctx.lineTo(x+w,y+h); ctx.closePath();
  }
}

function drawModule(m){
  const x=px(m.x), y=py(m.y+m.h), w=m.w*S, h=m.h*S;
  const c = TYPES[m.type].color;
  ctx.save();
  if(m.type==="light"){
    const g = ctx.createLinearGradient(x,y,x,y+h+14);
    g.addColorStop(0,"#e8c96f"); g.addColorStop(1,"rgba(232,201,111,0)");
    ctx.fillStyle=g; ctx.fillRect(x,y,w,h+14);
    ctx.fillStyle="#e8c96f"; ctx.fillRect(x,y,w,h);
    ctx.strokeStyle="#b89b4f"; ctx.strokeRect(x,y,w,h);
  }else if(m.type==="arc"){
    roundedSidePath(m);
    ctx.fillStyle=c+"cc"; ctx.fill();
    ctx.strokeStyle="#fff9"; ctx.lineWidth=1.5; ctx.stroke();
    // 層板示意
    ctx.strokeStyle="#ffffff44";
    const n=Math.max(1,Math.round(m.h/36));
    for(let i=1;i<n;i++){const yy=y+h*i/n;ctx.beginPath();ctx.moveTo(x+4,yy);ctx.lineTo(x+w-6,yy);ctx.stroke();}
  }else{
    ctx.fillStyle=c+"cc"; ctx.fillRect(x,y,w,h);
    ctx.strokeStyle="#fff9"; ctx.lineWidth=1.5; ctx.strokeRect(x,y,w,h);
    ctx.strokeStyle="#ffffff55"; ctx.lineWidth=1;
    if(m.type==="drawer"){
      const n=m.opts.drawers||4;
      for(let i=1;i<n;i++){const yy=y+h*i/n;ctx.beginPath();ctx.moveTo(x,yy);ctx.lineTo(x+w,yy);ctx.stroke();}
      for(let i=0;i<n;i++){const yy=y+h*(i+0.5)/n;ctx.fillStyle="#ffffff66";ctx.fillRect(x+w/2-10,yy-1,20,2);}
    }else if(m.type==="open"){
      const n=Math.max(1,Math.round(m.h/35));
      for(let i=1;i<n;i++){const yy=y+h*i/n;ctx.beginPath();ctx.moveTo(x+3,yy);ctx.lineTo(x+w-3,yy);ctx.stroke();}
    }else if(m.type!=="counter"&&m.type!=="light"&&!m.opts.hideDoor){
      const doors=m.opts.doors||Math.max(1,Math.round(m.w/50));
      for(let i=1;i<doors;i++){const xx=x+w*i/doors;ctx.beginPath();ctx.moveTo(xx,y);ctx.lineTo(xx,y+h);ctx.stroke();}
      if(m.opts.handleless){
        ctx.strokeStyle="#00000088"; ctx.lineWidth=3;
        ctx.beginPath();ctx.moveTo(x,y+4);ctx.lineTo(x+w,y+4);ctx.stroke();
      }else{
        ctx.fillStyle="#ffffff88";
        for(let i=0;i<doors;i++){const xx=x+w*(i+0.5)/doors;ctx.fillRect(xx-2,y+8,4,Math.min(24,h*0.3));}
      }
    }
  }
  if(INTERIOR_TYPES.includes(m.type)) drawParts2D(m);
  // 名稱
  if(h>14&&w>36){
    ctx.fillStyle="#ffffffcc"; ctx.font="11px sans-serif"; ctx.textAlign="center";
    ctx.fillText(TYPES[m.type].name+(m.opts.handleless?"·免把手":""), x+w/2, y+h/2+4);
  }
  ctx.restore();
}

function drawHandles(m){
  const x=px(m.x), y=py(m.y+m.h), w=m.w*S, h=m.h*S;
  ctx.strokeStyle="#4da3ff"; ctx.lineWidth=1.5; ctx.setLineDash([4,3]);
  ctx.strokeRect(x-2,y-2,w+4,h+4); ctx.setLineDash([]);
  ctx.fillStyle="#4da3ff";
  for(const [hx,hy] of handlePts(m)) ctx.fillRect(hx-4,hy-4,8,8);
  // 尺寸浮標
  ctx.fillStyle="#4da3ff"; ctx.font="bold 12px sans-serif"; ctx.textAlign="center";
  ctx.fillText(`${m.w}×${m.h}  離地${m.y}`, x+w/2, y-8);
}
function handlePts(m){
  const x=px(m.x), y=py(m.y+m.h), w=m.w*S, h=m.h*S;
  return [[x,y],[x+w/2,y],[x+w,y],[x,y+h/2],[x+w,y+h/2],[x,y+h],[x+w/2,y+h],[x+w,y+h]];
}
const CURS=["nwse-resize","ns-resize","nesw-resize","ew-resize","ew-resize","nesw-resize","ns-resize","nwse-resize"];

/* ------------------ 自動標尺寸 ------------------ */
function drawDim(x1,x2,Y,txt){
  const a=px(x1),b=px(x2);
  ctx.beginPath();ctx.moveTo(a,Y-4);ctx.lineTo(a,Y+4);ctx.moveTo(b,Y-4);ctx.lineTo(b,Y+4);
  ctx.moveTo(a,Y);ctx.lineTo(b,Y);ctx.stroke();
  ctx.beginPath();ctx.moveTo(a-3,Y+3);ctx.lineTo(a+3,Y-3);ctx.moveTo(b-3,Y+3);ctx.lineTo(b+3,Y-3);ctx.stroke();
  if((b-a)>18) ctx.fillText(txt,(a+b)/2,Y-4);
}
function drawDimV(y1,y2,X,txt){
  const a=py(y1),b=py(y2);
  ctx.beginPath();ctx.moveTo(X-4,a);ctx.lineTo(X+4,a);ctx.moveTo(X-4,b);ctx.lineTo(X+4,b);
  ctx.moveTo(X,a);ctx.lineTo(X,b);ctx.stroke();
  ctx.beginPath();ctx.moveTo(X-3,a-3);ctx.lineTo(X+3,a+3);ctx.moveTo(X-3,b-3);ctx.lineTo(X+3,b+3);ctx.stroke();
  if((a-b)>16){ctx.save();ctx.translate(X-4,(a+b)/2);ctx.rotate(-Math.PI/2);ctx.fillText(txt,0,0);ctx.restore();}
}
function drawDims(){
  ctx.strokeStyle="#7fc97f"; ctx.fillStyle="#7fc97f";
  ctx.lineWidth=1; ctx.font="11px sans-serif"; ctx.textAlign="center";
  const W=design.wall.w,H=design.wall.h;
  const xs=new Set([0,W]), ys=new Set([0,H]);
  for(const m of design.modules){
    xs.add(Math.round(m.x*10)/10); xs.add(Math.round((m.x+m.w)*10)/10);
    ys.add(Math.round(m.y*10)/10); ys.add(Math.round((m.y+m.h)*10)/10);
  }
  const X=[...xs].sort((p,q)=>p-q), Y=[...ys].sort((p,q)=>p-q);
  for(let i=0;i<X.length-1;i++){const d=X[i+1]-X[i]; if(d>=1) drawDim(X[i],X[i+1],py(0)+22,String(Math.round(d)));}
  drawDim(0,W,py(0)+48,String(W));
  for(let i=0;i<Y.length-1;i++){const d=Y[i+1]-Y[i]; if(d>=1) drawDimV(Y[i],Y[i+1],px(0)-24,String(Math.round(d)));}
  drawDimV(0,H,px(0)-52,String(H));
}

/* ------------------ 內裝細部設計（雙擊櫃體進入） ------------------ */
function drawParts2D(m){   // 在整體立面上疊畫內裝零件
  if(!m.parts||!m.parts.length) return;
  const doorCover=["base","wall","tall","arc"].includes(m.type)&&!m.opts.hideDoor;
  ctx.save(); ctx.globalAlpha=doorCover?0.25:0.9;
  ctx.strokeStyle="#ffe9c9"; ctx.fillStyle="#ffe9c9"; ctx.lineWidth=1.5;
  const iv=interior(m);
  for(const p of m.parts){
    if(p.kind==="vdiv"){
      ctx.fillRect(px(m.x+p.x)-1,py(m.y+iv.y1),2,(iv.y1-iv.y0)*S);
    }else{
      const [b0,b1]=bayOf(m,p.x), X0=px(m.x+b0), X1=px(m.x+b1);
      if(p.kind==="shelf") ctx.fillRect(X0,py(m.y+p.y)-1,X1-X0,2);
      else if(p.kind==="rod"){ctx.beginPath();ctx.moveTo(X0+2,py(m.y+p.y));ctx.lineTo(X1-2,py(m.y+p.y));ctx.stroke();}
      else if(p.kind==="drawer"){
        ctx.strokeRect(X0,py(m.y+p.y+p.h),X1-X0,p.h*S);
        ctx.fillRect((X0+X1)/2-8,py(m.y+p.y+p.h*0.6)-1.5,16,3);
      }
    }
  }
  ctx.restore();
}
const epx=x=>EOX+x*ES, epy=y=>EOY-y*ES;
function enterEdit(m){
  editM=m; selPart=null; setPalette("parts");
  document.getElementById("btnDone").style.display="";
  renderProps(); draw();
}
function exitEdit(){
  editM=null; selPart=null; setPalette("modules");
  document.getElementById("btnDone").style.display="none";
  renderProps(); draw();
}
function drawEdit(){
  const m=editM, r=stage.getBoundingClientRect();
  ctx.clearRect(0,0,r.width,r.height);
  ctx.fillStyle="#1a1d22"; ctx.fillRect(0,0,r.width,r.height);
  ES=Math.min((r.width-260)/m.w,(r.height-150)/m.h);
  EOX=(r.width-m.w*ES)/2; EOY=(r.height+m.h*ES)/2-20;
  const iv=interior(m);
  // 桶身（板厚可見）
  ctx.fillStyle=TYPES[m.type].color+"cc";
  ctx.fillRect(epx(0),epy(m.h),m.w*ES,m.h*ES);
  ctx.fillStyle="#15171b";
  ctx.fillRect(epx(iv.x0),epy(iv.y1),(iv.x1-iv.x0)*ES,(iv.y1-iv.y0)*ES);
  ctx.strokeStyle="#fff9"; ctx.lineWidth=2;
  ctx.strokeRect(epx(0),epy(m.h),m.w*ES,m.h*ES);
  // 零件
  for(const p of m.parts||[]) drawPartE(m,p);
  // 每格高度鏈標註（模仿拆料圖）
  ctx.strokeStyle="#7fc97f"; ctx.fillStyle="#7fc97f";
  ctx.font="11px sans-serif"; ctx.textAlign="center"; ctx.lineWidth=1;
  for(const [b0,b1] of bays(m)){
    const brk=new Set([iv.y0,iv.y1]);
    for(const p of m.parts||[]){
      if(p.kind==="vdiv") continue;
      const b=bayOf(m,p.x);
      if(b[0]!==b0) continue;
      if(p.kind==="drawer"){brk.add(p.y);brk.add(p.y+p.h);}
      else brk.add(p.y);
    }
    const ys=[...brk].sort((a,c)=>a-c);
    const X=epx(b0)+14;
    for(let i=0;i<ys.length-1;i++){
      const gap=ys[i+1]-ys[i]; if(gap<2) continue;
      const A=epy(ys[i]),B=epy(ys[i+1]);
      ctx.beginPath();ctx.moveTo(X-4,A);ctx.lineTo(X+4,A);ctx.moveTo(X-4,B);ctx.lineTo(X+4,B);
      ctx.moveTo(X,A);ctx.lineTo(X,B);ctx.stroke();
      if(A-B>15){ctx.save();ctx.translate(X-5,(A+B)/2);ctx.rotate(-Math.PI/2);ctx.fillText(String(Math.round(gap)),0,0);ctx.restore();}
    }
  }
  // 外框總尺寸
  ctx.fillStyle="#9aa3ad"; ctx.font="13px sans-serif"; ctx.textAlign="center";
  ctx.fillText(`${TYPES[m.type].name}  W${m.w}×H${m.h}×D${m.d}cm`, r.width/2, epy(m.h)-14);
  ctx.font="12px sans-serif";
  ctx.fillText("內裝編輯：左側拖入零件｜拖曳調位置｜Delete 刪除｜Esc 或「完成內裝」返回", r.width/2, r.height-14);
}
function drawPartE(m,p){
  const iv=interior(m), sel=p===selPart;
  const col=sel?"#4da3ff":"#e0c9a0";
  ctx.lineWidth=sel?2.5:1.5;
  if(p.kind==="vdiv"){
    ctx.fillStyle=col;
    ctx.fillRect(epx(p.x-1),epy(iv.y1),2*ES,(iv.y1-iv.y0)*ES);
    return;
  }
  const [b0,b1]=bayOf(m,p.x);
  if(p.kind==="shelf"){
    ctx.fillStyle=col; ctx.fillRect(epx(b0),epy(p.y+1),(b1-b0)*ES,2*ES);
  }else if(p.kind==="drawer"){
    ctx.fillStyle=sel?"rgba(77,163,255,.3)":"rgba(224,201,160,.25)";
    ctx.fillRect(epx(b0),epy(p.y+p.h),(b1-b0)*ES,p.h*ES);
    ctx.strokeStyle=col;
    ctx.strokeRect(epx(b0),epy(p.y+p.h),(b1-b0)*ES,p.h*ES);
    ctx.fillStyle=col;
    ctx.fillRect(epx((b0+b1)/2)-14,epy(p.y+p.h*0.6)-2,28,4);
  }else if(p.kind==="rod"){
    ctx.strokeStyle=col; ctx.lineWidth=4;
    ctx.beginPath();ctx.moveTo(epx(b0+1),epy(p.y));ctx.lineTo(epx(b1-1),epy(p.y));ctx.stroke();
    ctx.lineWidth=1.5;
    ctx.beginPath();ctx.arc(epx(b0+2),epy(p.y),4,0,7);ctx.arc(epx(b1-2),epy(p.y),4,0,7);ctx.stroke();
  }
  if(sel){
    ctx.fillStyle="#4da3ff"; ctx.font="bold 12px sans-serif"; ctx.textAlign="center";
    ctx.fillText(`${PARTS[p.kind].name} 離櫃底 ${Math.round(p.y)}cm`, epx((b0+b1)/2), epy(p.y)-10);
  }
}
function hitPart(X,Y){
  const m=editM;
  for(let i=(m.parts||[]).length-1;i>=0;i--){
    const p=m.parts[i];
    if(p.kind==="vdiv"){
      if(Math.abs(X-epx(p.x))<8&&Y<=epy(interior(m).y0)&&Y>=epy(interior(m).y1)) return p;
      continue;
    }
    const [b0,b1]=bayOf(m,p.x);
    if(X<epx(b0)-6||X>epx(b1)+6) continue;
    if(p.kind==="drawer"){if(Y<=epy(p.y)+6&&Y>=epy(p.y+p.h)-6) return p;}
    else if(Math.abs(Y-epy(p.y))<9) return p;
  }
  return null;
}
function addPartAt(k,x,y){   // x,y = 櫃內座標(cm，相對櫃左下角)
  const m=editM, iv=interior(m);
  x=Math.max(iv.x0,Math.min(iv.x1,x));
  y=Math.round(Math.max(iv.y0,Math.min(iv.y1-1,y)));
  let p;
  if(k==="vdiv") p={kind:k, x:Math.round(Math.max(iv.x0+8,Math.min(iv.x1-8,x)))};
  else if(k==="drawer") p={kind:k, x, y:Math.min(y,iv.y1-20), h:20};
  else p={kind:k, x, y};
  (m.parts=m.parts||[]).push(p); selPart=p; draw();
}

/* ---- 3D 內裝編輯 ---- */
function P3E(){   // 以編輯中櫃體為中心的 3D 投影
  const m=editM, r=stage.getBoundingClientRect();
  const cy=Math.cos(yaw),sy=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch);
  const s=Math.min(r.width/(m.w*2.4), r.height/(m.h*1.6))*zoom3;
  const cx=r.width/2, cyy=r.height/2;
  const ox=m.x+m.w/2, oy=m.y+m.h/2, oz=m.d/2;
  return (X,Y,Z)=>{
    const x=X-ox, y=Y-oy, z=Z-oz;
    const x1=x*cy+z*sy, z1=-x*sy+z*cy;
    const y1=y*cp-z1*sp, z2=y*sp+z1*cp;
    return [cx+x1*s, cyy-y1*s, z2];
  };
}
function pointInPoly(X,Y,pts){
  let inside=false;
  for(let i=0,j=pts.length-1;i<pts.length;j=i++){
    const xi=pts[i][0],yi=pts[i][1],xj=pts[j][0],yj=pts[j][1];
    if((yi>Y)!==(yj>Y)&&X<(xj-xi)*(Y-yi)/(yj-yi)+xi) inside=!inside;
  }
  return inside;
}
function basisE(){   // 櫃體正面平面的螢幕基底（正交投影 → 仿射可逆）
  const p=P3E(), m=editM, zc=m.d/2;
  const O=p(m.x,m.y,zc), U=p(m.x+1,m.y,zc), V=p(m.x,m.y+1,zc);
  return {O, ux:U[0]-O[0], uy:U[1]-O[1], vx:V[0]-O[0], vy:V[1]-O[1]};
}
function solveUV(dx,dy,b){
  const det=(b.ux*b.vy-b.uy*b.vx)||1e-9;
  return [(dx*b.vy-dy*b.vx)/det, (-dx*b.uy+dy*b.ux)/det];
}
function hitPart3D(X,Y){
  const m=editM, p=P3E(), parts=m.parts||[];
  for(let i=parts.length-1;i>=0;i--){
    for(const f of partFaces(m,parts[i]))
      if(pointInPoly(X,Y,f.pts.map(q=>p(q[0],q[1],q[2])))) return parts[i];
  }
  return null;
}
function hit3D(X,Y){   // 3D 主畫面點選櫃體
  const p=P3();
  for(let i=design.modules.length-1;i>=0;i--){
    const m=design.modules[i];
    const fs=m.type==="arc"?arcFaces(m):boxFaces(m.x,m.y,0,m.x+m.w,m.y+m.h,m.d);
    for(const f of fs)
      if(pointInPoly(X,Y,f.pts.map(q=>p(q[0],q[1],q[2])))) return m;
  }
  return null;
}
function drawEdit3D(){
  const m=editM, r=stage.getBoundingClientRect();
  ctx.clearRect(0,0,r.width,r.height);
  ctx.fillStyle="#1a1d22"; ctx.fillRect(0,0,r.width,r.height);
  const p=P3E(), base=TYPES[m.type].color;
  const x0=m.x,x1=m.x+m.w,y0=m.y,y1=m.y+m.h;
  const all=[];
  const rec=(f,fill,part)=>{
    const scr=f.pts.map(q=>p(q[0],q[1],q[2]));
    all.push({scr, depth:scr.reduce((a,q)=>a+q[2],0)/scr.length, fill, part});
  };
  const fs=boxFaces(x0,y0,0,x1,y1,m.d).filter(f=>f.k!=="front");
  fs.push({pts:[[x0+T,y0+T,1.5],[x1-T,y0+T,1.5],[x1-T,y1-T,1.5],[x0+T,y1-T,1.5]],
           n:[0,0,1], k:"backin"});
  for(const f of fs) rec(f, f.k==="backin"?"#1d2126":shade(base,f.n,false), null);
  for(const q of m.parts||[])
    for(const f of partFaces(m,q))
      rec(f, shade(q.kind==="drawer"?base:"#c9a978",f.n,false), q);
  all.sort((a,b)=>a.depth-b.depth);
  for(const f of all){
    ctx.beginPath();
    f.scr.forEach((q,i)=>i?ctx.lineTo(q[0],q[1]):ctx.moveTo(q[0],q[1]));
    ctx.closePath();
    ctx.fillStyle=f.fill; ctx.fill();
    const sel=f.part&&f.part===selPart;
    ctx.strokeStyle=sel?"#4da3ff":"rgba(0,0,0,.35)"; ctx.lineWidth=sel?2:1; ctx.stroke();
  }
  if(selPart&&selPart.kind!=="vdiv"){
    const [b0,b1]=bayOf(m,selPart.x);
    const c=p(m.x+(b0+b1)/2, m.y+(selPart.y??0), m.d);
    ctx.fillStyle="#4da3ff"; ctx.font="bold 12px sans-serif"; ctx.textAlign="center";
    ctx.fillText(`${PARTS[selPart.kind].name} 離櫃底 ${Math.round(selPart.y??0)}cm`, c[0], c[1]-14);
  }
  ctx.fillStyle="#9aa3ad"; ctx.font="13px sans-serif"; ctx.textAlign="center";
  ctx.fillText(`內裝編輯(3D)：${TYPES[m.type].name}  W${m.w}×H${m.h}×D${m.d}cm`, r.width/2, 24);
  ctx.font="12px sans-serif";
  ctx.fillText("拖零件＝移動｜拖空白＝旋轉｜滾輪縮放｜左側拖入新零件｜Delete 刪除｜Esc 返回", r.width/2, r.height-14);
}

/* ------------------ 3D 立體圖（純 Canvas 軟體渲染） ------------------ */
let mode3d=false, yaw=-0.55, pitch=0.32, zoom3=1, doors3d=true;
const LIGHT_DIR=(()=>{const v=[0.35,0.8,0.5],l=Math.hypot(v[0],v[1],v[2]);return v.map(a=>a/l);})();
function P3(){  // 世界(cm: X右, Y上, Z出牆) → 螢幕投影
  const r=stage.getBoundingClientRect(), W=design.wall.w, H=design.wall.h;
  const cy=Math.cos(yaw),sy=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch);
  const s=Math.min(r.width/(W*1.55), r.height/(H*1.7))*zoom3;
  const cx=r.width/2, cyy=r.height/2;
  return (X,Y,Z)=>{
    const x=X-W/2, y=Y-H/2, z=Z-40;
    const x1=x*cy+z*sy, z1=-x*sy+z*cy;
    const y1=y*cp-z1*sp, z2=y*sp+z1*cp;
    return [cx+x1*s, cyy-y1*s, z2];
  };
}
function shade(hex,n,emis){
  const r=parseInt(hex.slice(1,3),16),g=parseInt(hex.slice(3,5),16),b=parseInt(hex.slice(5,7),16);
  if(emis) return `rgb(${r},${g},${b})`;
  let d=n[0]*LIGHT_DIR[0]+n[1]*LIGHT_DIR[1]+n[2]*LIGHT_DIR[2];
  d=0.52+0.48*Math.max(0,d);
  return `rgb(${r*d|0},${g*d|0},${b*d|0})`;
}
function lerp2(a,b,t){return [a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t];}
function boxFaces(x0,y0,z0,x1,y1,z1){
  return [
    {pts:[[x0,y0,z1],[x1,y0,z1],[x1,y1,z1],[x0,y1,z1]], n:[0,0,1], k:"front"},
    {pts:[[x0,y1,z1],[x1,y1,z1],[x1,y1,z0],[x0,y1,z0]], n:[0,1,0], k:"top"},
    {pts:[[x0,y0,z0],[x0,y0,z1],[x0,y1,z1],[x0,y1,z0]], n:[-1,0,0], k:"side"},
    {pts:[[x1,y0,z1],[x1,y0,z0],[x1,y1,z0],[x1,y1,z1]], n:[1,0,0], k:"side"},
    {pts:[[x0,y0,z0],[x1,y0,z0],[x1,y0,z1],[x0,y0,z1]], n:[0,-1,0], k:"bottom"},
  ];
}
function arcFaces(m){  // 弧形櫃：平面圓角輪廓垂直擠出
  const x0=m.x, x1=m.x+m.w, y0=m.y, y1=m.y+m.h, d=m.d;
  const right=(m.opts.arcSide||"right")==="right";
  const R=Math.min(m.w*0.9, d*0.9);
  const prof=[];
  if(right){
    prof.push([x0,0],[x0,d]);
    for(let i=0;i<=8;i++){const a=Math.PI/2*(1-i/8);prof.push([x1-R+R*Math.cos(a), d-R+R*Math.sin(a)]);}
    prof.push([x1,0]);
  }else{
    prof.push([x0,0]);
    for(let i=0;i<=8;i++){const a=Math.PI-(Math.PI/2)*(i/8);prof.push([x0+R+R*Math.cos(a), d-R+R*Math.sin(a)]);}
    prof.push([x1,d],[x1,0]);
  }
  const faces=[];
  for(let i=0;i<prof.length-1;i++){
    const [ax,az]=prof[i],[bx,bz]=prof[i+1];
    const nx=-(bz-az), nz=bx-ax, l=Math.hypot(nx,nz)||1;
    faces.push({pts:[[ax,y0,az],[bx,y0,bz],[bx,y1,bz],[ax,y1,az]], n:[nx/l,0,nz/l], k:"side"});
  }
  faces.push({pts:prof.map(([a,c])=>[a,y1,c]), n:[0,1,0], k:"top"});
  faces.push({pts:prof.slice().reverse().map(([a,c])=>[a,y0,c]), n:[0,-1,0], k:"bottom"});
  return faces;
}
function partFaces(m,p){   // 內裝零件的 3D 箱體
  const iv=interior(m), d=m.d;
  if(p.kind==="vdiv")
    return boxFaces(m.x+p.x-1, m.y+iv.y0, 2, m.x+p.x+1, m.y+iv.y1, d-3);
  const [b0,b1]=bayOf(m,p.x);
  if(p.kind==="shelf")
    return boxFaces(m.x+b0, m.y+p.y-1, 2, m.x+b1, m.y+p.y+1, d-3);
  if(p.kind==="drawer")
    return boxFaces(m.x+b0+0.5, m.y+p.y, d-4, m.x+b1-0.5, m.y+p.y+p.h, d-0.5);
  return boxFaces(m.x+b0+1, m.y+p.y-1.5, d/2-1.5, m.x+b1-1, m.y+p.y+1.5, d/2+1.5); // rod
}
function fill3(p,pts,fill,stroke){
  ctx.beginPath();
  pts.forEach((q,i)=>{const s=p(q[0],q[1],q[2]); i?ctx.lineTo(s[0],s[1]):ctx.moveTo(s[0],s[1]);});
  ctx.closePath(); ctx.fillStyle=fill; ctx.fill();
  if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=1.5;ctx.stroke();}
}
function line3(p,a,b){
  const s1=p(a[0],a[1],a[2]), s2=p(b[0],b[1],b[2]);
  ctx.beginPath();ctx.moveTo(s1[0],s1[1]);ctx.lineTo(s2[0],s2[1]);ctx.stroke();
}
function frontDetails3(f){
  const m=f.m, s=f.scr, BL=s[0],BR=s[1],TR=s[2],TL=s[3], t=m.type;
  ctx.strokeStyle="rgba(0,0,0,.3)"; ctx.lineWidth=1;
  const vline=u=>{const a=lerp2(BL,BR,u),b=lerp2(TL,TR,u);ctx.beginPath();ctx.moveTo(a[0],a[1]);ctx.lineTo(b[0],b[1]);ctx.stroke();};
  const hline=v=>{const a=lerp2(BL,TL,v),b=lerp2(BR,TR,v);ctx.beginPath();ctx.moveTo(a[0],a[1]);ctx.lineTo(b[0],b[1]);ctx.stroke();};
  if(t==="drawer"){const n=m.opts.drawers||4;for(let i=1;i<n;i++)hline(i/n);}
  else if(t==="open"){const n=Math.max(1,Math.round(m.h/35));for(let i=1;i<n;i++)hline(i/n);}
  else if(["base","wall","tall"].includes(t)){
    const doors=m.opts.doors||Math.max(1,Math.round(m.w/50));
    for(let i=1;i<doors;i++)vline(i/doors);
    if(m.opts.handleless){ctx.strokeStyle="rgba(0,0,0,.55)";ctx.lineWidth=2;hline(0.93);}
    else{
      ctx.fillStyle="rgba(255,255,255,.85)";
      for(let i=0;i<doors;i++){
        const u=(i+0.5)/doors, a=lerp2(BL,BR,u), b=lerp2(TL,TR,u), q=lerp2(a,b,0.82);
        ctx.beginPath();ctx.arc(q[0],q[1],2.5,0,7);ctx.fill();
      }
    }
  }
}
function draw3D(){
  const r=stage.getBoundingClientRect();
  ctx.clearRect(0,0,r.width,r.height);
  const p=P3(), W=design.wall.w, H=design.wall.h;
  const D=Math.max(120,...design.modules.map(m=>m.d||60))+60;
  // 背牆與地板
  fill3(p,[[0,0,0],[W,0,0],[W,H,0],[0,H,0]],"#2c313a","#454c57");
  fill3(p,[[0,0,0],[W,0,0],[W,0,D],[0,0,D]],"#22262d","#3a4048");
  ctx.strokeStyle="rgba(255,255,255,.05)";ctx.lineWidth=1;
  for(let x=0;x<=W;x+=30){line3(p,[x,0,0],[x,0,D]);line3(p,[x,0,0],[x,H,0]);}
  for(let z=30;z<=D;z+=30)line3(p,[0,0,z],[W,0,z]);
  for(let y=30;y<=H;y+=30)line3(p,[0,y,0],[W,y,0]);
  // 收集所有面 → 依深度排序（畫家演算法）
  const all=[];
  const push=(m,f,fill)=>{
    const scr=f.pts.map(q=>p(q[0],q[1],q[2]));
    all.push({scr, depth:scr.reduce((a,q)=>a+q[2],0)/scr.length,
      fill, m, k:f.k, sel:m.id===selId});
  };
  for(const m of design.modules){
    const emis=m.type==="light", base=emis?"#ffd97a":TYPES[m.type].color;
    const hollow=INTERIOR_TYPES.includes(m.type)&&(m.type==="open"||m.opts.hideDoor||!doors3d);
    let fs;
    if(m.type==="arc") fs=arcFaces(m);
    else if(hollow){
      const x0=m.x,x1=m.x+m.w,y0=m.y,y1=m.y+m.h;
      fs=boxFaces(x0,y0,0,x1,y1,m.d).filter(f=>f.k!=="front");
      fs.push({pts:[[x0+T,y0+T,1.5],[x1-T,y0+T,1.5],[x1-T,y1-T,1.5],[x0+T,y1-T,1.5]],
               n:[0,0,1], k:"backin"});
    }else fs=boxFaces(m.x,m.y,0,m.x+m.w,m.y+m.h,m.d);
    for(const f of fs)
      push(m,f, f.k==="backin" ? "#1d2126" : shade(base,f.n,emis));
    if(hollow&&m.parts)
      for(const q of m.parts)
        for(const f of partFaces(m,q))
          push(m,f, shade(q.kind==="drawer"?base:"#c9a978",f.n,false));
  }
  all.sort((a,b)=>a.depth-b.depth);
  for(const f of all){
    ctx.beginPath();
    f.scr.forEach((q,i)=>i?ctx.lineTo(q[0],q[1]):ctx.moveTo(q[0],q[1]));
    ctx.closePath();
    ctx.fillStyle=f.fill; ctx.fill();
    ctx.strokeStyle=f.sel?"#4da3ff":"rgba(0,0,0,.35)"; ctx.lineWidth=f.sel?1.6:1; ctx.stroke();
    if(f.k==="front") frontDetails3(f);
  }
  // 燈槽下打光暈
  for(const m of design.modules){
    if(m.type!=="light") continue;
    const a=p(m.x,m.y,2), b=p(m.x+m.w,m.y,2);
    const c=p(m.x+m.w,m.y-34,2), d2=p(m.x,m.y-34,2);
    const g=ctx.createLinearGradient(a[0],a[1],d2[0],d2[1]);
    g.addColorStop(0,"rgba(255,217,122,.45)"); g.addColorStop(1,"rgba(255,217,122,0)");
    ctx.beginPath();ctx.moveTo(a[0],a[1]);ctx.lineTo(b[0],b[1]);ctx.lineTo(c[0],c[1]);ctx.lineTo(d2[0],d2[1]);ctx.closePath();
    ctx.fillStyle=g; ctx.fill();
  }
  ctx.fillStyle="#9aa3ad"; ctx.font="12px sans-serif"; ctx.textAlign="left";
  ctx.fillText("3D 預覽：拖曳旋轉｜滾輪縮放｜編輯請切回 2D", 12, r.height-12);
}
const btn3D=document.getElementById("btn3D");
function setMode3d(v){
  mode3d=v; btn3D.textContent=v?"回 2D 編輯":"3D 立體圖";
  cv.style.cursor=v?"grab":"default"; draw();
}
btn3D.onclick=()=>setMode3d(!mode3d);
document.getElementById("btnDone").onclick=()=>exitEdit();
const btnDoors=document.getElementById("btnDoors");
btnDoors.onclick=()=>{
  doors3d=!doors3d;
  btnDoors.textContent=doors3d?"3D門片:開":"3D門片:關";
  draw();
};
cv.addEventListener("wheel",e=>{
  if(!mode3d) return; e.preventDefault();
  zoom3=Math.max(0.4,Math.min(3,zoom3*Math.pow(1.0015,-e.deltaY))); draw();
},{passive:false});

/* ------------------ 互動 ------------------ */
function getSel(){return design.modules.find(m=>m.id===selId)||null;}
function hit(X,Y){
  for(let i=design.modules.length-1;i>=0;i--){
    const m=design.modules[i];
    const x=px(m.x),y=py(m.y+m.h),w=m.w*S,h=m.h*S;
    if(X>=x-3&&X<=x+w+3&&Y>=y-3&&Y<=y+h+3) return m;
  }
  return null;
}
function snap(v,others){
  for(const o of others) if(Math.abs((v-o)*S)<7) return o;
  return Math.round(v);
}
function edgeCandidates(skip){
  const xs=[0,design.wall.w], ys=[0,design.wall.h];
  for(const m of design.modules){
    if(m.id===skip) continue;
    xs.push(m.x,m.x+m.w); ys.push(m.y,m.y+m.h);
  }
  return {xs,ys};
}

let drag=null;   // {mode:"move"|"resize"|"place", ...}
cv.addEventListener("pointerdown",e=>{
  cv.focus(); cv.setPointerCapture(e.pointerId);
  const R=cv.getBoundingClientRect(), X=e.clientX-R.left, Y=e.clientY-R.top;
  if(editM&&mode3d){
    const p=hitPart3D(X,Y); selPart=p;
    if(p) drag={mode:"epart3",p,sx:X,sy:Y,x0:p.x,y0:p.y??0};
    else{drag={mode:"orbit",sx:X,sy:Y,y0:yaw,p0:pitch};cv.style.cursor="grabbing";}
    draw(); return;
  }
  if(editM){
    const p=hitPart(X,Y); selPart=p;
    if(p) drag={mode:"epart",p};
    draw(); return;
  }
  if(mode3d){drag={mode:"orbit",sx:X,sy:Y,y0:yaw,p0:pitch};cv.style.cursor="grabbing";return;}
  const sel=getSel();
  if(sel){
    const pts=handlePts(sel);
    for(let i=0;i<8;i++){
      if(Math.abs(X-pts[i][0])<7&&Math.abs(Y-pts[i][1])<7){
        drag={mode:"resize",h:i,m:sel,ox:sel.x,oy:sel.y,ow:sel.w,oh:sel.h,sx:X,sy:Y};
        return;
      }
    }
  }
  const m=hit(X,Y);
  if(m){
    selId=m.id;
    drag={mode:"move",m,dx:mx(X)-m.x,dy:my(Y)-m.y};
  }else selId=null;
  renderProps(); draw();
});
cv.addEventListener("pointermove",e=>{
  const R=cv.getBoundingClientRect(), X=e.clientX-R.left, Y=e.clientY-R.top;
  if(drag&&drag.mode==="epart3"){
    const m=editM, iv=interior(m), p=drag.p;
    const [du,dv]=solveUV(X-drag.sx,Y-drag.sy,basisE());
    if(p.kind==="vdiv"){
      p.x=Math.round(Math.max(iv.x0+8,Math.min(iv.x1-8,drag.x0+du)));
    }else{
      p.x=Math.max(iv.x0,Math.min(iv.x1,drag.x0+du));
      const maxY=p.kind==="drawer"?iv.y1-p.h:iv.y1-1;
      p.y=Math.round(Math.max(iv.y0,Math.min(maxY,drag.y0+dv)));
    }
    draw(); return;
  }
  if(drag&&drag.mode==="epart"){
    const m=editM, iv=interior(m), p=drag.p;
    const x=(X-EOX)/ES, y=(EOY-Y)/ES;
    if(p.kind==="vdiv"){
      p.x=Math.round(Math.max(iv.x0+8,Math.min(iv.x1-8,x)));
    }else{
      p.x=Math.max(iv.x0,Math.min(iv.x1,x));
      const maxY=p.kind==="drawer"?iv.y1-p.h:iv.y1-1;
      p.y=Math.round(Math.max(iv.y0,Math.min(maxY,y)));
    }
    draw(); return;
  }
  if(drag&&drag.mode==="orbit"){
    yaw=Math.max(-1.25,Math.min(1.25,drag.y0+(X-drag.sx)*0.008));
    pitch=Math.max(0.03,Math.min(1.15,drag.p0+(Y-drag.sy)*0.008));
    draw(); return;
  }
  if(editM&&mode3d){cv.style.cursor=hitPart3D(X,Y)?"move":"grab";return;}
  if(editM){cv.style.cursor=hitPart(X,Y)?"move":"default";return;}
  if(mode3d){cv.style.cursor="grab";return;}
  if(!drag){
    const sel=getSel(); let cur="default";
    if(sel){const pts=handlePts(sel);
      for(let i=0;i<8;i++) if(Math.abs(X-pts[i][0])<7&&Math.abs(Y-pts[i][1])<7) cur=CURS[i];}
    if(cur==="default"&&hit(X,Y)) cur="move";
    cv.style.cursor=cur; return;
  }
  const W=design.wall.w,H=design.wall.h;
  if(drag.mode==="move"){
    const m=drag.m, c=edgeCandidates(m.id);
    let nx=mx(X)-drag.dx, ny=my(Y)-drag.dy;
    nx=snap(nx,c.xs); ny=snap(ny,c.ys);
    nx=snap(nx+m.w,c.xs)-m.w; ny=snap(ny+m.h,c.ys)-m.h;
    m.x=Math.max(0,Math.min(W-m.w,Math.round(nx)));
    m.y=Math.max(0,Math.min(H-m.h,Math.round(ny)));
    renderProps(); draw();
  }else if(drag.mode==="resize"){
    const m=drag.m, c=edgeCandidates(m.id), i=drag.h;
    const dX=(X-drag.sx)/S, dY=(drag.sy-Y)/S;   // dY: 模型向上為正
    let x=drag.ox,y=drag.oy,w=drag.ow,h=drag.oh;
    const L=[0,3,5].includes(i), Rt=[2,4,7].includes(i);
    const T=[0,1,2].includes(i), B=[5,6,7].includes(i);
    if(L){const nx=snap(x+dX,c.xs); w=w+(x-nx); x=nx;}
    if(Rt){w=snap(x+w+dX,c.xs)-x;}
    if(T){h=snap(y+h+dY,c.ys)-y;}
    if(B){const ny=snap(y-(-dY),c.ys); h=h+(y-ny); y=ny;}  // 拉下緣
    w=Math.max(10,Math.round(w)); h=Math.max(3,Math.round(h));
    x=Math.max(0,Math.min(design.wall.w-w,Math.round(x)));
    y=Math.max(0,Math.min(design.wall.h-h,Math.round(y)));
    Object.assign(m,{x,y,w,h});
    renderProps(); draw();
  }
});
cv.addEventListener("pointerup",()=>{drag=null;if(mode3d)cv.style.cursor="grab";});

/* 調色盤拖曳放置（模組 / 內裝零件 兩種模式） */
const palette=document.getElementById("palette");
function palItem(html,onDrop,gw,gh){
  const el=document.createElement("div");
  el.className="pal"; el.innerHTML=html; palette.appendChild(el);
  el.addEventListener("pointerdown",e=>{
    e.preventDefault(); el.setPointerCapture(e.pointerId);
    const move=ev=>{
      ghost.style.display="block";
      ghost.style.left=(ev.clientX-gw()/2)+"px";
      ghost.style.top=(ev.clientY-gh()/2)+"px";
      ghost.style.width=gw()+"px"; ghost.style.height=gh()+"px";
    };
    const up=ev=>{
      ghost.style.display="none";
      el.removeEventListener("pointermove",move);
      el.removeEventListener("pointerup",up);
      const R=cv.getBoundingClientRect();
      if(ev.clientX>=R.left&&ev.clientX<=R.right&&ev.clientY>=R.top&&ev.clientY<=R.bottom)
        onDrop(ev.clientX-R.left, ev.clientY-R.top);
    };
    el.addEventListener("pointermove",move);
    el.addEventListener("pointerup",up);
  });
}
function setPalette(mode){
  palette.innerHTML = mode==="parts"
    ? '<h2>內裝零件（拖入櫃內）</h2>' : '<h2>模組（拖到牆面）</h2>';
  if(mode==="parts"){
    for(const [k,def] of Object.entries(PARTS)){
      palItem(`<div class="t">${def.name}</div><div class="s">${def.sub}</div>`,(X,Y)=>{
        if(!editM) return;
        if(mode3d){
          const b=basisE(), [u,v]=solveUV(X-b.O[0],Y-b.O[1],b);
          addPartAt(k,u,v);
        }else{
          addPartAt(k,(X-EOX)/ES,(EOY-Y)/ES);
        }
      }, ()=>k==="vdiv"?10:90, ()=>k==="vdiv"?90:(k==="drawer"?28:10));
    }
  }else{
    for(const [t,def] of Object.entries(TYPES)){
      palItem(`<div class="t">${def.name}</div><div class="s">${def.w}×${def.h}×${def.d}</div>`,(X,Y)=>{
        if(mode3d) setMode3d(false);   // 3D 中放模組 → 自動切回 2D 編輯
        addModule(t, mx(X)-def.w/2, undefined);
      }, ()=>def.w*S, ()=>def.h*S);
    }
  }
}
setPalette("modules");
function addModule(t,x,y){
  const def=TYPES[t];
  const m={id:nextId++,type:t,
    x:Math.max(0,Math.min(design.wall.w-def.w,Math.round(x??20))),
    y:Math.max(0,Math.min(design.wall.h-def.h,Math.round(y??def.y))),
    w:def.w,h:def.h,d:def.d,parts:[],
    opts:t==="drawer"?{drawers:4}:t==="arc"?{arcSide:"right",handleless:true}:{handleless:false}};
  design.modules.push(m); selId=m.id;
  renderProps(); draw();
  return m;
}

/* ------------------ 屬性面板 ------------------ */
const selProps=document.getElementById("selProps");
function bindNum(id,get,set){
  const el=document.getElementById(id); if(!el) return;
  el.addEventListener("change",()=>{set(parseFloat(el.value)||get());renderProps();draw();});
}
function renderProps(){
  if(editM){
    const pc={};
    for(const p of editM.parts||[]) pc[p.kind]=(pc[p.kind]||0)+1;
    const list=Object.entries(pc).map(([k,n])=>`${PARTS[k].name}×${n}`).join("、")||"（空）";
    document.getElementById("propBody").firstElementChild.innerHTML =
      `<b style="color:var(--fg)">內裝編輯：${TYPES[editM.type].name}</b>`;
    selProps.innerHTML=`<div style="color:var(--dim);line-height:1.8">已放零件：${list}<br><br>
      左側拖入零件到櫃內<br>拖曳調整位置（自動歸格）<br>
      可按「3D 立體圖」切換 2D/3D 編輯<br>3D 中拖空白處＝旋轉<br>
      Delete 刪除選取零件<br>Esc 或「完成內裝」返回</div>`;
    return;
  }
  const m=getSel();
  document.getElementById("propBody").firstElementChild.innerHTML =
    m?`<b style="color:var(--fg)">${TYPES[m.type].name} (M${design.modules.indexOf(m)+1})</b>`:'尚未選取櫃體。<br><br>牆面尺寸：';
  if(!m){selProps.innerHTML="";return;}
  const isDoor=["base","wall","tall","arc"].includes(m.type);
  let html=`
  <div class="row"><label>離左牆 cm</label><input type="number" id="pX" value="${m.x}"></div>
  <div class="row"><label>離地 cm</label><input type="number" id="pY" value="${m.y}"></div>
  <div class="row"><label>寬 cm</label><input type="number" id="pW" value="${m.w}"></div>
  <div class="row"><label>高 cm</label><input type="number" id="pH" value="${m.h}"></div>
  <div class="row"><label>深 cm</label><input type="number" id="pD" value="${m.d}"></div>`;
  if(isDoor) html+=`
  <div class="row"><label>門片數</label><input type="number" id="pDoors" value="${m.opts.doors||Math.max(1,Math.round(m.w/50))}" min="1" max="8"></div>
  <div class="row"><label>免把手</label><input type="checkbox" id="pHl" ${m.opts.handleless?"checked":""}></div>
  <div class="row"><label>層板燈</label><input type="checkbox" id="pLed" ${m.opts.led?"checked":""}></div>
  <div class="row"><label>隱藏門片</label><input type="checkbox" id="pHide" ${m.opts.hideDoor?"checked":""}></div>`;
  if(INTERIOR_TYPES.includes(m.type)) html+=`
  <div class="row"><button id="pEdit" style="flex:1">✏ 編輯內裝（層板/抽屜/吊桿）</button></div>`;
  if(m.type==="arc") html+=`
  <div class="row"><label>弧形方向</label><select id="pArc">
    <option value="right" ${m.opts.arcSide!=="left"?"selected":""}>右側收圓</option>
    <option value="left" ${m.opts.arcSide==="left"?"selected":""}>左側收圓</option></select></div>`;
  if(m.type==="drawer") html+=`
  <div class="row"><label>抽屜數</label><input type="number" id="pDrw" value="${m.opts.drawers||4}" min="1" max="8"></div>`;
  html+=`<div class="row"><button id="pDel" style="flex:1">刪除此櫃</button><button id="pDup" style="flex:1">複製</button></div>`;
  selProps.innerHTML=html;
  const clampX=v=>Math.max(0,Math.min(design.wall.w-m.w,v));
  const clampY=v=>Math.max(0,Math.min(design.wall.h-m.h,v));
  bindNum("pX",()=>m.x,v=>m.x=clampX(Math.round(v)));
  bindNum("pY",()=>m.y,v=>m.y=clampY(Math.round(v)));
  bindNum("pW",()=>m.w,v=>{m.w=Math.max(10,Math.round(v));m.x=clampX(m.x);});
  bindNum("pH",()=>m.h,v=>{m.h=Math.max(3,Math.round(v));m.y=clampY(m.y);});
  bindNum("pD",()=>m.d,v=>m.d=Math.max(10,Math.round(v)));
  bindNum("pDoors",()=>m.opts.doors||1,v=>m.opts.doors=Math.max(1,Math.round(v)));
  bindNum("pDrw",()=>m.opts.drawers||4,v=>m.opts.drawers=Math.max(1,Math.round(v)));
  const hl=document.getElementById("pHl");
  if(hl) hl.addEventListener("change",()=>{m.opts.handleless=hl.checked;draw();});
  const led=document.getElementById("pLed");
  if(led) led.addEventListener("change",()=>{m.opts.led=led.checked;draw();});
  const arc=document.getElementById("pArc");
  if(arc) arc.addEventListener("change",()=>{m.opts.arcSide=arc.value;draw();});
  const hd=document.getElementById("pHide");
  if(hd) hd.addEventListener("change",()=>{m.opts.hideDoor=hd.checked;draw();});
  const pe=document.getElementById("pEdit");
  if(pe) pe.onclick=()=>enterEdit(m);
  document.getElementById("pDel").onclick=()=>{removeSel();};
  document.getElementById("pDup").onclick=()=>{duplicateSel();};
}
function removeSel(){
  design.modules=design.modules.filter(m=>m.id!==selId);
  selId=null; renderProps(); draw();
}
function duplicateSel(){
  const m=getSel(); if(!m) return;
  const n=JSON.parse(JSON.stringify(m));
  n.id=nextId++; n.x=Math.min(design.wall.w-n.w,n.x+n.w);
  design.modules.push(n); selId=n.id; renderProps(); draw();
}
cv.addEventListener("dblclick",e=>{
  if(editM) return;
  const R=cv.getBoundingClientRect(), X=e.clientX-R.left, Y=e.clientY-R.top;
  const m=mode3d?hit3D(X,Y):hit(X,Y);
  if(m&&INTERIOR_TYPES.includes(m.type)){selId=m.id;enterEdit(m);}
});
cv.addEventListener("keydown",e=>{
  if(editM){
    if(e.key==="Escape"){exitEdit();e.preventDefault();return;}
    if((e.key==="Delete"||e.key==="Backspace")&&selPart){
      editM.parts=editM.parts.filter(q=>q!==selPart);
      selPart=null; draw(); e.preventDefault();
    }
    return;
  }
  if(mode3d) return;
  const m=getSel(); if(!m) return;
  const st=e.shiftKey?10:1;
  if(e.key==="Delete"||e.key==="Backspace"){removeSel();e.preventDefault();}
  else if(e.key==="ArrowLeft"){m.x=Math.max(0,m.x-st);}
  else if(e.key==="ArrowRight"){m.x=Math.min(design.wall.w-m.w,m.x+st);}
  else if(e.key==="ArrowUp"){m.y=Math.min(design.wall.h-m.h,m.y+st);}
  else if(e.key==="ArrowDown"){m.y=Math.max(0,m.y-st);}
  else if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="d"){duplicateSel();e.preventDefault();}
  else return;
  renderProps(); draw(); e.preventDefault();
});

/* 牆面尺寸 */
for(const [id,key] of [["wallW","w"],["wallH","h"]]){
  document.getElementById(id).addEventListener("change",e=>{
    design.wall[key]=Math.max(60,parseInt(e.target.value)||design.wall[key]);
    e.target.value=design.wall[key]; fit();
  });
}

/* ------------------ 工具列 ------------------ */
document.getElementById("btnClear").onclick=()=>{
  if(design.modules.length&&!confirm("清空所有櫃體？")) return;
  design.modules=[]; selId=null; renderProps(); draw();
};
/* 範例配置（10 種情境；格式 [type,x,y,w,h,opts,parts]） */
const SH=(x,y)=>({kind:"shelf",x,y}), DR=(x,y,h)=>({kind:"drawer",x,y,h}),
      RD=(x,y)=>({kind:"rod",x,y}), VD=x=>({kind:"vdiv",x});
const DEMOS=[
 {name:"玄關鞋櫃牆", wall:{w:240,h:240}, mods:[
  ["tall",0,10,60,220,{handleless:true},[SH(30,30),SH(30,60),SH(30,90),SH(30,120),SH(30,150),SH(30,180)]],
  ["tall",60,10,60,220,{handleless:true},[SH(30,30),SH(30,60),SH(30,90),SH(30,120),SH(30,150),SH(30,180)]],
  ["base",120,10,120,50,{handleless:true}],
  ["counter",120,60,120,4],
  ["open",120,120,120,60,{},[VD(60),SH(30,30),SH(90,30)]],
  ["light",120,114,120,6],
  ["wall",120,190,120,40,{handleless:true}]]},
 {name:"客廳電視牆", wall:{w:400,h:250}, mods:[
  ["drawer",0,10,80,50,{drawers:3}],
  ["base",80,10,120,50,{handleless:true}],
  ["drawer",200,10,80,50,{drawers:3}],
  ["base",280,10,120,50,{handleless:true}],
  ["counter",0,60,400,4],
  ["open",20,120,100,60,{},[SH(50,30)]],
  ["wall",140,190,240,45,{handleless:true,led:true}],
  ["light",140,184,240,6]]},
 {name:"餐廳餐邊櫃", wall:{w:300,h:240}, mods:[
  ["base",0,10,100,72,{handleless:true}],
  ["drawer",100,10,60,72,{drawers:4}],
  ["base",160,10,100,72,{handleless:true}],
  ["arc",260,10,40,72,{arcSide:"right"}],
  ["counter",0,82,300,4],
  ["wall",0,160,130,60,{handleless:true,led:true}],
  ["wall",130,160,130,60,{handleless:true,led:true}],
  ["light",0,154,260,6],
  ["open",260,160,40,60,{},[SH(20,30)]]]},
 {name:"臥室衣櫃", wall:{w:300,h:250}, mods:[
  ["tall",0,10,100,230,{handleless:true},[DR(50,2,20),DR(50,22,20),SH(50,160),RD(50,195)]],
  ["tall",100,10,100,230,{handleless:true,hideDoor:true},[SH(50,60),RD(50,100),RD(50,195)]],
  ["tall",200,10,100,230,{handleless:true},[SH(50,40),SH(50,80),SH(50,120),SH(50,160),SH(50,195)]]]},
 {name:"書房書牆", wall:{w:360,h:240}, mods:[
  ["base",0,10,120,72,{handleless:true}],
  ["drawer",120,10,60,72,{drawers:4}],
  ["base",180,10,120,72,{handleless:true}],
  ["open",300,10,60,72,{},[SH(30,36)]],
  ["counter",0,82,360,4],
  ["open",0,120,120,100,{},[VD(60),SH(30,33),SH(30,66),SH(90,33),SH(90,66)]],
  ["open",120,120,120,100,{},[VD(60),SH(30,33),SH(30,66),SH(90,33),SH(90,66)]],
  ["open",240,120,120,100,{},[VD(60),SH(30,33),SH(30,66),SH(90,33),SH(90,66)]],
  ["light",0,114,360,6]]},
 {name:"一字型廚房", wall:{w:300,h:240}, mods:[
  ["base",0,10,80,72,{handleless:true}],
  ["drawer",80,10,60,72,{drawers:4}],
  ["base",140,10,80,72,{handleless:true}],
  ["base",220,10,80,72,{handleless:true}],
  ["counter",0,82,300,4],
  ["wall",0,155,100,65,{handleless:true}],
  ["wall",100,155,100,65,{handleless:true}],
  ["wall",200,155,100,65,{handleless:true}],
  ["light",0,149,300,6]]},
 {name:"洗衣工作陽台", wall:{w:240,h:240}, mods:[
  ["tall",0,10,60,220,{handleless:true},[SH(30,45),SH(30,90),SH(30,135),SH(30,180)]],
  ["counter",60,100,90,4],
  ["wall",60,160,90,60,{handleless:true}],
  ["base",150,10,90,72,{handleless:true}],
  ["counter",150,82,90,4],
  ["wall",150,160,90,60,{handleless:true}],
  ["light",60,154,180,6]]},
 {name:"兒童房收納", wall:{w:300,h:240}, mods:[
  ["drawer",0,10,75,60,{drawers:3}],
  ["open",75,10,75,120,{},[VD(37),SH(18,40),SH(18,80),SH(56,40),SH(56,80)]],
  ["drawer",150,10,75,60,{drawers:3}],
  ["base",225,10,75,60,{handleless:true}],
  ["open",225,80,75,80,{},[SH(37,40)]],
  ["wall",150,170,150,50,{handleless:true}],
  ["light",150,164,150,6]]},
 {name:"開放更衣室", wall:{w:360,h:250}, mods:[
  ["tall",0,10,90,230,{hideDoor:true},[RD(45,100),RD(45,195)]],
  ["tall",90,10,90,230,{hideDoor:true},[DR(45,2,20),DR(45,22,20),DR(45,42,20),SH(45,90),RD(45,195)]],
  ["tall",180,10,90,230,{hideDoor:true},[SH(45,45),SH(45,90),SH(45,135),RD(45,195)]],
  ["open",270,10,90,230,{},[VD(45),SH(22,60),SH(22,120),SH(22,180),SH(67,60),SH(67,120),SH(67,180)]]]},
 {name:"展示收藏牆", wall:{w:320,h:250}, mods:[
  ["arc",0,10,45,230,{arcSide:"left"}],
  ["arc",275,10,45,230,{arcSide:"right"}],
  ["base",45,10,230,60,{handleless:true}],
  ["counter",45,70,230,4],
  ["open",45,130,230,110,{led:true},[VD(77),VD(154),SH(38,37),SH(38,74),SH(115,37),SH(115,74),SH(192,37),SH(192,74)]],
  ["light",45,124,230,6]]},
];
function loadDemo(i){
  const dm=DEMOS[i];
  if(design.modules.length&&!confirm(`載入「${dm.name}」會取代目前設計，繼續？`)) return;
  if(editM) exitEdit();
  design={title:dm.name+"施工圖", wall:{...dm.wall}, modules:[]};
  nextId=1;
  for(const [t,x,y,w,h,opts,parts] of dm.mods){
    design.modules.push({id:nextId++,type:t,x,y,w,h,d:TYPES[t].d,
      parts:parts?JSON.parse(JSON.stringify(parts)):[],
      opts:Object.assign(t==="drawer"?{drawers:4}:{handleless:false},opts||{})});
  }
  document.getElementById("wallW").value=design.wall.w;
  document.getElementById("wallH").value=design.wall.h;
  selId=null; renderProps(); fit();
}
const selDemo=document.getElementById("selDemo");
DEMOS.forEach((d,i)=>{
  const o=document.createElement("option");
  o.value=i; o.textContent=`${i+1}. ${d.name}`;
  selDemo.appendChild(o);
});
selDemo.addEventListener("change",()=>{
  if(selDemo.value!=="") loadDemo(+selDemo.value);
  selDemo.value="";
});
document.getElementById("btnSave").onclick=()=>{
  const blob=new Blob([JSON.stringify(design,null,1)],{type:"application/json"});
  dl(blob,"系統櫃設計.json");
};
document.getElementById("btnLoad").onclick=()=>document.getElementById("fileLoad").click();
document.getElementById("fileLoad").addEventListener("change",e=>{
  const f=e.target.files[0]; if(!f) return;
  f.text().then(t=>{
    design=JSON.parse(t);
    nextId=Math.max(0,...design.modules.map(m=>m.id))+1;
    document.getElementById("wallW").value=design.wall.w;
    document.getElementById("wallH").value=design.wall.h;
    selId=null; renderProps(); fit();
  });
  e.target.value="";
});
function dl(blob,name){
  const a=document.createElement("a");
  a.href=URL.createObjectURL(blob); a.download=name; a.click();
  setTimeout(()=>URL.revokeObjectURL(a.href),5000);
}
async function post(url){
  const r=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify(design)});
  if(!r.ok) throw new Error(await r.text());
  return r;
}
document.getElementById("btnDxf").onclick=async()=>{
  if(!design.modules.length){alert("還沒放任何櫃體喔");return;}
  try{
    const r=await post("/api/dxf");
    dl(await r.blob(),`系統櫃施工圖_${new Date().toISOString().slice(0,10)}.dxf`);
  }catch(err){alert("產圖失敗："+err.message);}
};
document.getElementById("btnQuote").onclick=async()=>{
  if(!design.modules.length){alert("還沒放任何櫃體喔");return;}
  const r=await post("/api/quote");
  const q=await r.json();
  let html=`<table><tr><th>品名</th><th>規格</th><th>明細</th><th>小計</th></tr>`;
  for(const row of q.rows)
    html+=`<tr><td>${row.name}</td><td>${row.spec}</td><td class="detail">${row.detail}</td><td>${row.subtotal.toLocaleString()}</td></tr>`;
  html+=`<tr><td colspan="3">板材五金小計</td><td>${q.subtotal.toLocaleString()}</td></tr>`;
  html+=`<tr><td colspan="3">施工安裝費（${q.install_pct}%）</td><td>${q.install.toLocaleString()}</td></tr>`;
  html+=`<tr><td colspan="3" class="grand">總計 NTD</td><td class="grand">${q.grand.toLocaleString()}</td></tr></table>`;
  html+=`<p class="detail" style="margin-top:8px">※ 單價為示意值，可在 cabinet_designer.py 開頭 PRICE / RATE 區修改。</p>`;
  document.getElementById("modalBody").innerHTML=html;
  document.getElementById("modal").style.display="flex";
};
document.getElementById("btnCsv").onclick=async()=>{
  const r=await post("/api/quote.csv");
  dl(await r.blob(),`系統櫃報價單_${new Date().toISOString().slice(0,10)}.csv`);
};
function closeModal(){document.getElementById("modal").style.display="none";}
document.getElementById("modal").addEventListener("click",e=>{
  if(e.target.id==="modal") closeModal();
});

fit(); renderProps();
</script>
</body>
</html>
"""


# ============================================================================
# HTTP 伺服器
# ============================================================================

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/plain; charset=utf-8", download=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if download:
            self.send_header("Content-Disposition", f'attachment; filename="{download}"')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, INDEX_HTML.encode("utf-8"), "text/html; charset=utf-8")
        else:
            self._send(404, b"not found")

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            design = json.loads(self.rfile.read(n).decode("utf-8"))
            if self.path == "/api/dxf":
                self._send(200, make_dxf(design), "application/dxf", "plan.dxf")
            elif self.path == "/api/quote":
                body = json.dumps(build_quote(design), ensure_ascii=False).encode("utf-8")
                self._send(200, body, "application/json; charset=utf-8")
            elif self.path == "/api/quote.csv":
                self._send(200, quote_csv(design), "text/csv; charset=utf-8", "quote.csv")
            else:
                self._send(404, b"not found")
        except Exception as e:  # noqa: BLE001
            self._send(500, str(e).encode("utf-8"))

    def log_message(self, fmt, *args):
        pass  # 安靜


def main():
    ap = argparse.ArgumentParser(description="系統櫃設計工具")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true", help="不自動開瀏覽器")
    args = ap.parse_args()

    if not HAS_EZDXF:
        print("⚠ 未安裝 ezdxf，施工圖 DXF 功能無法使用（pip install ezdxf）")

    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"✅ 系統櫃設計已啟動：{url}   (Ctrl+C 結束)")
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n再見！")


if __name__ == "__main__":
    main()
