# color 答案集歸一收尾：文字/色彩推 class → path→polygon → 裁畫布 →
# 三層（class/text/fill）對齊標準 → 刪微小殘筆（有報告不靜默）。
import os
import re
import sys
from xml.dom import minidom

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fix_annotation_paths import parse_transform, mat_mul, IDENTITY

CANON = {"Kitchen": "#e8843c", "LivingRoom": "#7dc37d", "Bedroom": "#4a90d9",
         "Bath": "#3dbdbd", "Entry": "#8f5fc6", "Storage": "#b8a06a",
         "Garage": "#909090", "Balcony": "#b5368f", "Stair": "#a89cc8",
         "Hallway": "#c9a0dc"}
TEXT_ALIAS = {"outdoor": "Balcony", "living room": "LivingRoom",
              "livingroom": "LivingRoom", "washroom": "Bath"}
MIN_AREA = 2000.0


def nearest_class(hexc):
    try:
        v = np.array([int(hexc[i:i + 2], 16) for i in (1, 3, 5)], float)
    except Exception:
        return None
    best, bd = None, 1e9
    for k, c in CANON.items():
        w = np.array([int(c[i:i + 2], 16) for i in (1, 3, 5)], float)
        d = float(np.abs(v - w).sum())
        if d < bd:
            best, bd = k, d
    return best if bd <= 60 else None


def path_to_points(d):
    toks = re.findall(r'([MmLlHhVvZzCcSsQqTtAa])|(-?\d+\.?\d*(?:e-?\d+)?)', d)
    seq = [("cmd", c) if c else ("num", float(n)) for c, n in toks]
    if any(k == "cmd" and v in "CcSsQqTtAa" for k, v in seq):
        raise ValueError("含曲線指令，無法直轉")
    pts, cur, cmd = [], np.zeros(2), None
    i = 0
    while i < len(seq):
        kind, v = seq[i]
        if kind == "cmd":
            cmd = v
            i += 1
            continue
        if cmd in ("M", "L"):
            cur = np.array([seq[i][1], seq[i + 1][1]]); i += 2
            pts.append(cur.copy())
            if cmd == "M":
                cmd = "L"
        elif cmd in ("m", "l"):
            base = cur if pts else np.zeros(2)
            cur = base + np.array([seq[i][1], seq[i + 1][1]]); i += 2
            pts.append(cur.copy())
            cmd = "l"
        elif cmd == "H":
            cur = np.array([seq[i][1], cur[1]]); i += 1; pts.append(cur.copy())
        elif cmd == "h":
            cur = cur + np.array([seq[i][1], 0]); i += 1; pts.append(cur.copy())
        elif cmd == "V":
            cur = np.array([cur[0], seq[i][1]]); i += 1; pts.append(cur.copy())
        elif cmd == "v":
            cur = cur + np.array([0, seq[i][1]]); i += 1; pts.append(cur.copy())
        else:
            raise ValueError(f"未支援 {cmd}")
    return np.array(pts)


def poly_area(pts):
    return 0.5 * abs(np.dot(pts[:, 0], np.roll(pts[:, 1], 1))
                     - np.dot(pts[:, 1], np.roll(pts[:, 0], 1)))


def group_text(g):
    out = []
    for t in g.getElementsByTagName("text"):
        parts = [nd.data for nd in t.childNodes if nd.nodeType == 3]
        for ts in t.getElementsByTagName("tspan"):
            parts += [nd.data for nd in ts.childNodes if nd.nodeType == 3]
        v = "".join(parts).strip()
        if v:
            out.append(v)
    return out


def _label_pole(pts, W, H):
    """標籤位置：外接框中心（視覺置中，使用者規格）；L 形等凹多邊形
    中心落在房外時，退回距離變換極點（房內最深處）。"""
    import cv2
    m = np.zeros((int(H), int(W)), np.uint8)
    cv2.fillPoly(m, [pts.astype(np.int32)], 255)
    if not m.any():
        return float(pts[:, 0].mean()), float(pts[:, 1].mean())
    bx = (pts[:, 0].min() + pts[:, 0].max()) / 2.0
    by = (pts[:, 1].min() + pts[:, 1].max()) / 2.0
    iy, ix = int(round(by)), int(round(bx))
    if 0 <= iy < m.shape[0] and 0 <= ix < m.shape[1] and m[iy, ix]:
        return float(bx), float(by)
    dt = cv2.distanceTransform(m, cv2.DIST_L2, 3)
    iy, ix = np.unravel_index(int(dt.argmax()), dt.shape)
    return float(ix), float(iy)


def normalize(svg_path, W, H):
    doc = minidom.parse(svg_path)
    fill_re = re.compile(r'fill:\s*([^;"\s]+)')
    n = 0
    report = []
    pending_labels = []
    for g in doc.getElementsByTagName("g"):
        cls = g.getAttribute("class")
        if not cls.startswith("Space "):
            continue
        n += 1
        tok = cls.split()[1]
        texts = group_text(g)
        fills = set()
        for tag in ("polygon", "path", "rect"):
            for p in g.getElementsByTagName(tag):
                m = fill_re.search(p.getAttribute("style") or "")
                if m:
                    fills.add(m.group(1).lower())
                f = p.getAttribute("fill")
                if f and f != "none":
                    fills.add(f.lower())
        # 推 class：文字優先 → 色彩 → 既有 token
        target = None
        for t in texts:
            key = t.strip().lower()
            if key in TEXT_ALIAS:
                target = TEXT_ALIAS[key]
                break
            for k in CANON:
                if key == k.lower():
                    target = k
                    break
            if target:
                break
        if target is None:
            for f in sorted(fills):
                target = nearest_class(f)
                if target:
                    break
        if target is None and tok in CANON:
            target = tok
        if target is None:
            report.append(f"{n}: 無法判別 class（token={tok} text={texts} "
                          f"fill={sorted(fills)}）← 需人工")
            continue
        g.setAttribute("class", f"Space {target}")
        style = (f"fill:{CANON[target]};fill-opacity:0.4;"
                 f"stroke:#000000;stroke-width:1")
        # path → polygon（刪 <MIN_AREA 殘筆）
        for p in list(g.getElementsByTagName("path")):
            try:
                pts = path_to_points(p.getAttribute("d"))
            except ValueError as e:
                report.append(f"{n}: path 無法轉換（{e}）← 需人工")
                continue
            if len(pts) < 3 or poly_area(pts) < MIN_AREA:
                g.removeChild(p)
                report.append(f"{n}: 刪殘筆 path（{len(pts)} 點，"
                              f"面積 {poly_area(pts) if len(pts)>=3 else 0:.0f}px）")
                continue
            pts[:, 0] = np.clip(pts[:, 0], 0, W)
            pts[:, 1] = np.clip(pts[:, 1], 0, H)
            poly = doc.createElement("polygon")
            pts = np.vstack([pts, pts[0]])       # floortrans 閉合慣例：尾點重複首點
            poly.setAttribute("points",
                              " ".join(f"{x:.2f},{y:.2f}" for x, y in pts))
            poly.setAttribute("style", style)
            g.replaceChild(poly, p)
            report.append(f"{n}: path→polygon {len(pts)} 點 → {target}")
        for p in list(g.getElementsByTagName("polygon")):
            raw = p.getAttribute("points").replace(",", " ").split()
            pts = np.array([float(v) for v in raw], float).reshape(-1, 2)
            # transform 烘焙（fix_own_floor 慣例）：Inkscape 縮放/搬移常寫成
            # transform 而非改點，量尺 get_polygon 不讀 transform 會讀到舊形
            mt = IDENTITY
            anc, node = [], p
            while node is not None and node.nodeType == 1:
                t = node.getAttribute("transform")
                if t: anc.append((node, parse_transform(t)))
                node = node.parentNode
            for _nd, m_ in reversed(anc):
                mt = mat_mul(mt, m_)
            if anc:
                a_, b_, c_, d_, e_, f_ = mt
                px = a_*pts[:,0] + c_*pts[:,1] + e_
                py = b_*pts[:,0] + d_*pts[:,1] + f_
                pts = np.stack([px, py], 1)
                for nd, _m in anc:
                    if nd is p or nd is g:
                        nd.removeAttribute("transform")
                    else:
                        report.append(f"{n}: 上層 <{nd.nodeName}> 帶 transform"
                                      f"，已烘焙但未移除 ← 檢查是否波及他物")
                p.setAttribute("points",
                               " ".join(f"{x:.2f},{y:.2f}" for x, y in pts))
                report.append(f"{n}: transform 烘焙進座標")
            if len(pts) >= 3 and not np.allclose(pts[0], pts[-1]):
                pts = np.vstack([pts, pts[0]])
                p.setAttribute("points",
                               " ".join(f"{x:.2f},{y:.2f}" for x, y in pts))
                report.append(f"{n}: polygon 補閉合點")
            if len(pts) < 3 or poly_area(pts) < MIN_AREA:
                g.removeChild(p)
                report.append(f"{n}: 刪殘筆 polygon（面積過小）")
                continue
            clipped = ""
            if (pts[:, 0].max() > W + 1 or pts[:, 1].max() > H + 1
                    or pts.min() < -1):
                pts[:, 0] = np.clip(pts[:, 0], 0, W)
                pts[:, 1] = np.clip(pts[:, 1], 0, H)
                if not np.allclose(pts[0], pts[-1]):
                    pts = np.vstack([pts, pts[0]])
                p.setAttribute("points",
                               " ".join(f"{x:.2f},{y:.2f}" for x, y in pts))
                clipped = "（裁畫布）"
            p.setAttribute("style", style)
            if p.getAttribute("fill"):
                p.removeAttribute("fill")
            report.append(f"{n}: polygon 標準化 → {target}{clipped}")
        # 文字標籤：群組內的舊文字一律移除，統一收到文件末端的
        # RoomLabels 層（SVG 後畫者在上——埋在群組內會被後續群組的
        # 形狀壓住；散在各群組的殘留樣式也是字型混亂的來源）
        for t in list(g.getElementsByTagName("text")):
            t.parentNode.removeChild(t)
        polys1 = g.getElementsByTagName("polygon")
        if polys1:
            raw = polys1[0].getAttribute("points").replace(",", " ").split()
            pp = np.array([float(v) for v in raw], float).reshape(-1, 2)
            pending_labels.append((target, _label_pole(pp, W, H)))
    # 標籤層：先清舊層再重建，附加為 <svg> 最後子節點（浮在最上）
    root = doc.documentElement
    for old in list(doc.getElementsByTagName("g")):
        if old.getAttribute("id") == "RoomLabels":
            old.parentNode.removeChild(old)
    layer = doc.createElement("g")
    layer.setAttribute("id", "RoomLabels")
    for name, (cx, cy) in pending_labels:
        t = doc.createElement("text")
        t.setAttribute("x", f"{cx:.0f}")
        t.setAttribute("y", f"{cy:.0f}")
        t.setAttribute("style",
                       "font-family:Arial;font-size:36px;font-weight:bold;"
                       "text-anchor:middle;fill:#000000")
        t.appendChild(doc.createTextNode(name))
        layer.appendChild(t)
    root.appendChild(layer)
    report.append(f"標籤層重建：{len(pending_labels)} 個房名（統一樣式、最上層）")
    open(svg_path, "w", encoding="utf-8", newline="").write(doc.toxml())
    return report


if __name__ == "__main__":
    svg, w, h = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    for line in normalize(svg, w, h):
        print(line)
    print("寫入完成")
