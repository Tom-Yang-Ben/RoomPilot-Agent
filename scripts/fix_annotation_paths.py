"""fix_annotation_paths.py — 修復 Inkscape 編輯後的標注 SVG。

Inkscape 手修 own_dataset/*/model.svg 時，房間（Space）或牆（Wall/Railing）
群組裡的 <polygon> 可能被改存成 <path>（矩形工具、路徑編輯都會）。
CubiCasa 的 House 解析器只認 <polygon> 子節點，遇到 path 直接
StopIteration。本腳本把「僅含直線段的閉合 path」無損轉回 polygon。

只處理 M/m L/l H/h V/v Z/z 指令；遇到曲線（c/s/q/a）報錯不動檔案。

用法：python scripts/fix_annotation_paths.py [--check]
    --check 只掃描回報，不寫檔
"""
import argparse
import glob
import re
import sys
from xml.dom import minidom

TOKEN = re.compile(r"([MmLlHhVvZz])|(-?\d*\.?\d+(?:[eE][-+]?\d+)?)")


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


def needs_polygon(e):
    if e.nodeName != "g":
        return False
    return e.getAttribute("id") in ("Wall", "Railing") \
        or "Space " in e.getAttribute("class")


def fix_svg(svg_path, check_only):
    doc = minidom.parse(svg_path)
    converted, errors = [], []
    for e in doc.getElementsByTagName("g"):
        if not needs_polygon(e):
            continue
        kids = [c for c in e.childNodes if c.nodeType == 1]
        if any(k.nodeName == "polygon" for k in kids):
            continue
        paths = [k for k in kids if k.nodeName == "path"]
        if not paths:
            errors.append(f"{e.getAttribute('class') or e.getAttribute('id')}"
                          " 既無 polygon 也無 path")
            continue
        for p in paths:
            label = e.getAttribute("class").strip() or e.getAttribute("id")
            try:
                pts = path_to_points(p.getAttribute("d"))
            except ValueError as ex:
                errors.append(f"{label}: {ex}")
                continue
            poly = doc.createElement("polygon")
            poly.setAttribute("points",
                              " ".join(f"{x:g},{y:g}" for x, y in pts))
            if p.getAttribute("style"):
                poly.setAttribute("style", p.getAttribute("style"))
            e.replaceChild(poly, p)
            converted.append(label)
    if converted and not check_only:
        with open(svg_path, "w", encoding="utf-8") as f:
            doc.writexml(f)
    return converted, errors


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="只掃描不寫檔")
    a = ap.parse_args()

    total, bad = 0, 0
    for svg in sorted(glob.glob("own_dataset/floor*/model.svg")):
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
