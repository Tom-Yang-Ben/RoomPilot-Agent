"""fix_annotation_paths.py — 修復 Inkscape 編輯後的標注 SVG。

Inkscape 手修 testdata/Identify_ans/own_dataset/*/model.svg 時，房間（Space）或牆（Wall/Railing）
群組裡的 <polygon> 可能被改存成 <path> 或 <rect>（矩形工具、路徑編輯都會），
縮放/移動則會存成群組或形狀上的 transform="matrix(...)" 屬性。
CubiCasa 的 House 解析器只認 <polygon> 子節點且完全忽略 transform——
前者直接 StopIteration、後者座標落在錯誤空間。本腳本做兩件無損正規化：
1. 「僅含直線段的閉合 path」與 rect 轉回 polygon（M/m L/l H/h V/v Z/z；曲線報錯不動檔案）
2. transform（matrix/translate/scale 組合）烘焙進座標點後移除屬性
   （rotate/skew 報錯不動檔案；上層群組帶 transform 亦報錯——移除會波及兄弟節點）

用法：python scripts/fix_annotation_paths.py [--check] [--dir DIR]
    --check 只掃描回報，不寫檔
    --dir   標注根目錄（預設 testdata/Identify_ans/own_dataset；own_eval 審定後亦須跑）
"""
import argparse
import glob
import re
import sys
from xml.dom import minidom

# 字母全捕捉：不支援的指令（曲線 C/Q/A/S/T 等）必須進 else 報錯，
# 只捕捉 MLHVZ 會讓曲線的數字靜默混入前一個指令、形狀畫歪
TOKEN = re.compile(r"([A-Za-z])|(-?\d*\.?\d+(?:[eE][-+]?\d+)?)")


def path_to_points(d):
    """把僅含直線段的 path d 轉成絕對座標點列，非直線指令丟 ValueError。"""
    tokens = TOKEN.findall(d)
    nums, cmds = [], []
    for cmd, num in tokens:
        if cmd:
            cmds.append((cmd, nums := []))
        else:
            nums.append(float(num))

    points, cur = [], (0.0, 0.0)
    for cmd, ns in cmds:
        if cmd in "Zz":
            continue
        if cmd in "Hh":
            for x in ns:
                cur = (x if cmd == "H" else cur[0] + x, cur[1])
                points.append(cur)
        elif cmd in "Vv":
            for y in ns:
                cur = (cur[0], y if cmd == "V" else cur[1] + y)
                points.append(cur)
        elif cmd in "MmLl":
            pairs = list(zip(ns[::2], ns[1::2]))
            for i, (x, y) in enumerate(pairs):
                absolute = cmd in "ML" or (not points and i == 0)
                cur = (x, y) if absolute else (cur[0] + x, cur[1] + y)
                points.append(cur)
        else:
            raise ValueError(f"不支援的指令 {cmd!r}（曲線需手動處理）: {d[:80]}")
    if len(points) < 3:
        raise ValueError(f"點數不足 {len(points)}: {d[:80]}")
    return points


NUM = re.compile(r"-?\d*\.?\d+(?:[eE][-+]?\d+)?")
IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def mat_mul(m1, m2):
    """2x3 仿射矩陣連乘（先套 m2 再套 m1，同 SVG transform 串接語意）。"""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (a1 * a2 + c1 * b2, b1 * a2 + d1 * b2,
            a1 * c2 + c1 * d2, b1 * c2 + d1 * d2,
            a1 * e2 + c1 * f2 + e1, b1 * e2 + d1 * f2 + f1)


def parse_transform(s):
    """transform 屬性 → 2x3 仿射；rotate/skew 不支援丟 ValueError。"""
    m = IDENTITY
    if not s:
        return m
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", s):
        ns = [float(v) for v in NUM.findall(args)]
        if name == "matrix" and len(ns) == 6:
            t = tuple(ns)
        elif name == "translate" and 1 <= len(ns) <= 2:
            t = (1, 0, 0, 1, ns[0], ns[1] if len(ns) > 1 else 0)
        elif name == "scale" and 1 <= len(ns) <= 2:
            t = (ns[0], 0, 0, ns[1] if len(ns) > 1 else ns[0], 0, 0)
        else:
            raise ValueError(f"不支援的 transform: {name}({args})")
        m = mat_mul(m, t)
    return m


def is_identity(m):
    return all(abs(a - b) < 1e-9 for a, b in zip(m, IDENTITY))


def check_ancestors_clean(e):
    """上層群組不得帶 transform——烘焙後移除會波及兄弟節點，只能報錯。"""
    p = e.parentNode
    while p is not None and p.nodeType == 1:
        if p.getAttribute("transform"):
            raise ValueError(
                f"上層 <{p.nodeName}> 帶 transform，不支援自動烘焙")
        p = p.parentNode


def rect_points(e):
    """rect 的 x/y/width/height → 四角頂點（rx/ry 圓角忽略，取外接矩形）。"""
    x = float(e.getAttribute("x") or 0)
    y = float(e.getAttribute("y") or 0)
    w = float(e.getAttribute("width"))
    h = float(e.getAttribute("height"))
    if w <= 0 or h <= 0:
        raise ValueError(f"rect 尺寸非正: {w}x{h}")
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def points_of(poly_attr):
    """polygon points 屬性 → [(x, y)]。"""
    nums = [float(v) for v in NUM.findall(poly_attr)]
    return list(zip(nums[::2], nums[1::2]))


def needs_polygon(e):
    if e.nodeName != "g":
        return False
    return e.getAttribute("id") in ("Wall", "Railing") \
        or "Space " in e.getAttribute("class")


def fix_svg(svg_path, check_only):
    doc = minidom.parse(svg_path)
    converted, errors = [], []
    changed = False
    for e in doc.getElementsByTagName("g"):
        if not needs_polygon(e):
            continue
        label = e.getAttribute("class").strip() or e.getAttribute("id")
        kids = [c for c in e.childNodes if c.nodeType == 1]
        shapes = [k for k in kids if k.nodeName in ("polygon", "path", "rect")]
        if not shapes:
            errors.append(f"{label} 既無 polygon 也無 path/rect")
            continue
        try:
            check_ancestors_clean(e)
            gmat = parse_transform(e.getAttribute("transform"))
        except ValueError as ex:
            errors.append(f"{label}: {ex}")
            continue
        group_ok = True
        for p in shapes:
            try:
                mat = mat_mul(gmat, parse_transform(p.getAttribute("transform")))
                if p.nodeName == "path":
                    pts = path_to_points(p.getAttribute("d"))
                elif p.nodeName == "rect":
                    pts = rect_points(p)
                else:
                    pts = points_of(p.getAttribute("points"))
            except ValueError as ex:
                errors.append(f"{label}: {ex}")
                group_ok = False
                continue
            baked = not is_identity(mat)
            if baked:
                a, b, c, d, tx, ty = mat
                pts = [(a * x + c * y + tx, b * x + d * y + ty)
                       for x, y in pts]
            if p.nodeName in ("path", "rect") or baked:
                poly = doc.createElement("polygon")
                # 保留所有非幾何屬性（fill/stroke/style/opacity…）——
                # 只複製 style 會讓屬性式配色的圖形變成預設黑色實心
                GEOM = {"d", "points", "x", "y", "width", "height",
                        "rx", "ry", "transform"}
                for i in range(p.attributes.length):
                    attr = p.attributes.item(i)
                    if attr.name not in GEOM:
                        poly.setAttribute(attr.name, attr.value)
                poly.setAttribute("points",
                                  " ".join(f"{x:g},{y:g}" for x, y in pts) + " ")  # 尾空格：House get_polygon 會砍最後一項
                e.replaceChild(poly, p)
                changed = True
                tags = ([p.nodeName] if p.nodeName != "polygon" else []) \
                    + (["transform"] if baked else [])
                converted.append(f"{label}[{'+'.join(tags)}]")
        gt_attr = e.getAttribute("transform")
        if group_ok and gt_attr:
            for k in kids:                       # text 等非形狀子節點：
                if k.nodeName in ("polygon", "path"):
                    continue                     # 矩陣前綴保持渲染等價
                k.setAttribute("transform",
                               (gt_attr + " " + k.getAttribute("transform"))
                               .strip())
            e.removeAttribute("transform")       # 形狀已烘焙、其餘已前綴
            changed = True
    if changed and not check_only:
        with open(svg_path, "w", encoding="utf-8") as f:
            doc.writexml(f)
    return converted, errors


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="只掃描不寫檔")
    ap.add_argument("--dir", default="testdata/Identify_ans/own_dataset",
                    help="標注根目錄（own_eval 審定後亦須跑）")
    a = ap.parse_args()

    total, bad = 0, 0
    for svg in sorted(glob.glob(a.dir.rstrip("/") + "/*floor*/model.svg")):
        converted, errors = fix_svg(svg, a.check)
        if converted:
            total += len(converted)
            verb = "可轉換" if a.check else "已轉換"
            print(f"{svg}: {verb} {len(converted)} 個 path → polygon"
                  f"（{', '.join(converted)}）")
        for msg in errors:
            bad += 1
            print(f"{svg}: [無法自動修復] {msg}", file=sys.stderr)
    print(f"\n合計轉換 {total} 個，無法處理 {bad} 個")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
