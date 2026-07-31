#!/usr/bin/env python3
"""fix_own_floor.py — own 標注逐層修復：補 class、烘焙 transform、統一色。

處理 Inkscape 手修後的 model.svg 三類問題（floor01/02 驗證過的流程）：
1. 複製群組掉 class → 依文字標籤/填色最近鄰補回 Space class
2. transform 位移 → 烘焙進座標（House 會忽略 transform）
3. path/rect → polygon（保留全部非幾何屬性），Space 填色刷成統一色表

別名轉換：Terrace→Outdoor、Study→Office、Entrance→Entry；WashRoom 獨立 class
（house.py 需先套 apply_cubicasa_patches.py 的 WashRoom 補丁）。

用法：python scripts/fix_own_floor.py testdata/Identify_ans/own_dataset/floor03 \
        [--backup-dir DIR] [--render-dir DIR] [--dry-run]
產出：修復 model.svg（先備份）＋ House 視角渲染圖（人工驗收用）
"""
import argparse
import os
import re
import shutil
import sys
from xml.dom import minidom

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fix_annotation_paths import (path_to_points, points_of, rect_points,
                                  parse_transform, mat_mul, is_identity)

# 統一色表（與使用者 2026-07-24 定案；HSL 版見對話記錄/記憶）
SPACE_FILL = {"Bedroom": "#4a90d9", "Bath": "#3dbdbd", "WashRoom": "#d97a8f",
              "Kitchen": "#e8843c", "LivingRoom": "#7dc37d",
              "Outdoor": "#b5368f", "Storage": "#b8a06a", "Office": "#c9b458",
              "StairWell": "#a89cc8", "Entry": "#8f5fc6", "HallWay": "#c9a0dc",
              "Garage": "#909090", "Undefined": "#d9d9d9", "Dining": "#7dc37d"}
STRUCT_FILL = {"Wall": ("#cc2222", "0.45"), "Window": ("#22aa22", "0.6"),
               "Door": ("#ddaa00", "0.6")}
# 文字標籤 → class（別名正規化；比對時轉小寫去空白）
ALIAS = {"terrace": "Outdoor", "balcony": "Outdoor", "outdoor": "Outdoor",
         "study": "Office", "office": "Office", "entrance": "Entry",
         "entry": "Entry", "washroom": "WashRoom", "toilet": "WashRoom",
         "bath": "Bath", "bathroom": "Bath", "bedroom": "Bedroom",
         "bed": "Bedroom", "kitchen": "Kitchen", "living": "LivingRoom",
         "livingroom": "LivingRoom", "dining": "Kitchen",
         "storage": "Storage", "stor": "Storage", "closet": "Storage",
         "hallway": "HallWay", "hall": "HallWay", "stair": "StairWell",
         "stairwell": "StairWell", "garage": "Garage",
         "undefined": "Undefined"}
GEOM = {"d", "points", "x", "y", "width", "height", "rx", "ry", "transform"}
NUM = re.compile(r"-?\d*\.?\d+(?:[eE][-+]?\d+)?")
# 顯示文字＝class 名（使用者定案：名稱與顯示統一用 CubiCasa 合法名）
LABEL_FONT = "22"


def interior_point(xs, ys, holes=None):
    """多邊形內部最深點（距離變換 argmax）——L/T 形房間 bbox 中心會落在
    房外，改取真正在房內且離邊界最遠的位置。
    holes：要挖掉的多邊形（如牆帶）——房間常與牆重疊，標籤不落牆上。"""
    import numpy as np
    import cv2
    x0, y0 = min(xs), min(ys)
    # 寬高必須保持浮點——int 截斷會讓縮放後的填充貼到遮罩末列，
    # 底邊失去零像素邊界，距離變換 argmax 掉到邊緣（458 事件）
    w = max(2.0, max(xs) - x0); h = max(2.0, max(ys) - y0)
    scale = min(1.0, 400 / max(w, h))
    # ceil+3：多邊形最遠點落在 h*scale+1，外側必須再留一排零像素
    mask = np.zeros((int(np.ceil(h * scale)) + 3,
                     int(np.ceil(w * scale)) + 3), np.uint8)

    def to_px(pxs, pys):
        return np.array([[(x - x0) * scale + 1, (y - y0) * scale + 1]
                         for x, y in zip(pxs, pys)], np.int32)

    cv2.fillPoly(mask, [to_px(xs, ys)], 255)
    filled = mask.copy()
    for hx, hy in (holes or []):
        cv2.fillPoly(mask, [to_px(hx, hy)], 0)
    if not mask.any():                       # 牆蓋滿整房的極端情形：退回不挖
        mask = filled
    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 3)
    # 同深度的點常有一整條（矩形的中軸），取其中最靠近 bbox 中心者
    ys_i, xs_i = np.where(dist >= dist.max() - 0.5)
    mcy, mcx = mask.shape[0] / 2, mask.shape[1] / 2
    k = ((xs_i - mcx) ** 2 + (ys_i - mcy) ** 2).argmin()
    return (xs_i[k] - 1) / scale + x0, (ys_i[k] - 1) / scale + y0


def label_info(g, cls_sub, wall_holes=None):
    """移除 Space 群組內文字，回傳 (標籤, 中心x, 中心y)；Labels 頂層群組重建用。"""
    for t in [k for k in g.childNodes
              if k.nodeType == 1 and k.nodeName == "text"]:
        g.removeChild(t)
    poly = next((k for k in g.childNodes
                 if k.nodeType == 1 and k.nodeName == "polygon"), None)
    if poly is None:
        return None
    nums = [float(v) for v in NUM.findall(poly.getAttribute("points"))]
    xs, ys = nums[::2], nums[1::2]
    if not xs:
        return None
    cx, cy = interior_point(xs, ys, holes=wall_holes)
    return (cls_sub, cx, cy + 8)            # +8 = 22px 字基線補償


def rebuild_labels_group(doc, labels):
    """所有房型標籤集中到 SVG 末端的 Labels 群組——最後渲染＝最上層。
    群組無 class，House 解析自動忽略。"""
    svg = doc.documentElement
    for g in doc.getElementsByTagName("g"):
        if g.getAttribute("id") == "Labels":
            g.parentNode.removeChild(g)
    lg = doc.createElement("g")
    lg.setAttribute("id", "Labels")
    lg.setAttribute("inkscape:label", "Labels")
    for txt, cx, ty in labels:
        t = doc.createElement("text")
        t.setAttribute("x", f"{cx:.0f}")
        t.setAttribute("y", f"{ty:.0f}")
        t.setAttribute("font-size", LABEL_FONT)
        t.setAttribute("text-anchor", "middle")
        t.setAttribute("fill", "#000000")
        t.appendChild(doc.createTextNode(txt))
        lg.appendChild(t)
    svg.appendChild(lg)


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def get_fill(el):
    f = el.getAttribute("fill")
    if not f:
        m = re.search(r"fill:\s*(#[0-9a-fA-F]{3,6})", el.getAttribute("style"))
        f = m.group(1) if m else ""
    return f


def get_text(g):
    for t in g.getElementsByTagName("text"):
        s = "".join(n.data for n in t.childNodes if n.nodeType == 3).strip()
        if s:
            return s
    return ""


def nearest_class(fill_hex):
    """填色 → 距離最近的類別（含 Door/Window/Wall 結構色；無填色回 None）。
    使用者常複製門再改畫，填色最接近結構色時判為結構件而非房間。"""
    if not fill_hex:
        return None
    r, g, b = hex2rgb(fill_hex)
    candidates = dict(SPACE_FILL)
    candidates.update({k: v[0] for k, v in STRUCT_FILL.items()})
    best, bd = None, 1e9
    for cls, h in candidates.items():
        cr, cg, cb = hex2rgb(h)
        d = (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2
        if d < bd:
            best, bd = cls, d
    return best


def infer_space_class(g, poly_like):
    """優先文字標籤（含別名），其次填色最近鄰。"""
    txt = get_text(g).lower().replace(" ", "").replace("/", "")
    for key, cls in sorted(ALIAS.items(), key=lambda kv: -len(kv[0])):
        if key in txt:
            return cls, f'文字"{get_text(g)}"'
    cls = nearest_class(get_fill(poly_like))
    return cls, f"填色{get_fill(poly_like)}最近鄰" if cls else "無法判別"


def set_fill(el, hex_color, opacity):
    """style 與 fill 屬性並存時 CSS 由 style 勝出——兩邊都寫，避免檔案內
    新舊色並存造成閱讀混亂。"""
    if el.getAttribute("style"):
        s = el.getAttribute("style")
        s = re.sub(r"fill:\s*#[0-9a-fA-F]{3,6}", f"fill:{hex_color}", s)
        s = re.sub(r"stroke:\s*#[0-9a-fA-F]{3,6}", f"stroke:{hex_color}", s)
        s = re.sub(r"fill-opacity:\s*[\d.]+", f"fill-opacity:{opacity}", s)
        if "fill:" not in s:
            s += f";fill:{hex_color};fill-opacity:{opacity}"
        el.setAttribute("style", s)
    el.setAttribute("fill", hex_color)
    el.setAttribute("fill-opacity", opacity)
    el.setAttribute("stroke", hex_color)
    if not el.getAttribute("stroke-width"):
        el.setAttribute("stroke-width", "2")


def fix_floor(svg_path, dry=False):
    doc = minidom.parse(svg_path)
    report, manual, labels = [], [], []
    space_groups = []
    for g in doc.getElementsByTagName("g"):
        cls = g.getAttribute("class")
        gid = g.getAttribute("id")
        kids = [k for k in g.childNodes if k.nodeType == 1]
        shapes = [k for k in kids if k.nodeName in ("polygon", "path", "rect")]
        head = cls.split()[0] if cls else ""
        # 無 class 群組：有形狀才視為漏標房間
        if not cls and cls != "Model" and shapes:
            inferred, why = infer_space_class(g, shapes[0])
            if inferred is None:
                manual.append(f"{gid}: 無 class 且無法判別（{why}）——未動")
                continue
            if inferred in STRUCT_FILL:          # 門/窗/牆結構件
                g.setAttribute("class", inferred)
                cls = inferred
                head = inferred
                report.append(f"{gid}: 補 class={inferred}（{why}）")
            else:
                g.setAttribute("class", f"Space {inferred}")
                cls = f"Space {inferred}"
                head = "Space"
                report.append(f"{gid}: 補 class=Space {inferred}（{why}）")
        if head not in ("Wall", "Window", "Door", "Space", "Railing") \
                and g.getAttribute("id") not in ("Wall", "Railing"):
            continue
        if head == "Space" and not shapes:
            manual.append(f"{cls}: 群組無任何圖形（House 會 crash）"
                          "——需刪除或補畫，未動")
            continue
        # House 解析 Wall/Railing/Window/Door 是比對 id 而非 class
        # （house.py:394/404/419/461）；Inkscape 複製元素會改 id 導致漏讀，
        # 一律把 id 改回 class 名（SVG id 重複無妨，House 只做字串比對）
        if head in ("Wall", "Railing", "Window", "Door") \
                and g.getAttribute("id") != head:
            g.setAttribute("id", head)
            report.append(f"{head}: id 正規化（原 id={gid or '無'}）")
        # 別名 class 正規化（使用者直接把 class 寫成 Terrace 等）
        if head == "Space" and len(cls.split()) > 1:
            sub = cls.split()[1]
            norm = ALIAS.get(sub.lower())
            if norm and norm != sub:
                g.setAttribute("class", f"Space {norm}")
                cls = f"Space {norm}"
                report.append(f"class 正規化: {sub} → {norm}")
        gmat = parse_transform(g.getAttribute("transform"))
        for p in list(shapes):
            # Space 群組裡的無填色殘片：僅刪確定是向量化文字（點數多）
            # 或極小碎片——大形狀可能是漏填色的真房間，寧可留下待人工
            if head == "Space" and not get_fill(p) and len(shapes) > 1:
                d_attr = p.getAttribute("d") or p.getAttribute("points")
                n_pts = len(NUM.findall(d_attr)) // 2
                if n_pts > 50:
                    g.removeChild(p)
                    shapes.remove(p)
                    report.append(f"{cls}: 移除無填色殘片（{n_pts}點，向量文字）")
                    continue
                manual.append(f"{cls}: 無填色形狀（{n_pts}點）疑似漏填色房間——未動")
                continue
            try:
                mat = mat_mul(gmat, parse_transform(p.getAttribute("transform")))
                pts = (path_to_points(p.getAttribute("d"))
                       if p.nodeName == "path"
                       else rect_points(p) if p.nodeName == "rect"
                       else points_of(p.getAttribute("points")))
            except ValueError as ex:
                manual.append(f"{cls or gid}: {ex}——未動")
                continue
            baked = not is_identity(mat)
            if baked:
                a, b, c, d, tx, ty = mat
                pts = [(a * x + c * y + tx, b * x + d * y + ty)
                       for x, y in pts]
            if p.nodeName != "polygon" or baked:
                poly = doc.createElement("polygon")
                for i in range(p.attributes.length):
                    attr = p.attributes.item(i)
                    if attr.name not in GEOM:
                        poly.setAttribute(attr.name, attr.value)
                poly.setAttribute("points", " ".join(
                    f"{x:g},{y:g}" for x, y in pts) + " ")
                g.replaceChild(poly, p)
                shapes[shapes.index(p)] = poly
                report.append(f"{cls or gid}: {p.nodeName}→polygon"
                              + (" +烘焙" if baked else ""))
            else:                                # 尾空格保險
                pts_attr = p.getAttribute("points")
                if not pts_attr.endswith(" "):
                    p.setAttribute("points", pts_attr + " ")
                    report.append(f"{cls or gid}: 補尾空格")
        # 統一填色
        for p in shapes:
            if head == "Space":
                sub = cls.split()[1]
                cur = get_fill(p).lower()
                # Undefined 但填色幾乎等於某類標準色：使用者上色了但 class
                # 沒設（own_eval 常見）——填色為準改回（與使用者確認的慣例）
                if sub == "Undefined" and cur:
                    guess = nearest_class(cur)
                    if guess and guess not in ("Undefined",) \
                            and guess not in STRUCT_FILL:
                        r1, g1, b1 = hex2rgb(cur)
                        r2, g2, b2 = hex2rgb(SPACE_FILL[guess])
                        if (r1-r2)**2 + (g1-g2)**2 + (b1-b2)**2 < 2000:
                            g.setAttribute("class", f"Space {guess}")
                            cls = f"Space {guess}"
                            sub = guess
                            report.append(
                                f"Undefined→{guess}（填色 {cur} 即標準色）")
                target = SPACE_FILL.get(sub, "#d9d9d9")
                if cur and cur != target:
                    # 填色像別的類別 → 使用者意圖可能與 class 衝突，發旗標
                    guess = nearest_class(cur)
                    if guess and guess != sub and guess not in STRUCT_FILL:
                        manual.append(
                            f"{cls}: 原填色 {cur} 較接近 {guess}"
                            f"——已刷成 {sub} 色，若 {guess} 才是本意請告知")
                if cur != target:
                    set_fill(p, target, "0.35")
                    report.append(f"{cls}: 填色統一 → {target}")
            elif head in STRUCT_FILL and not get_fill(p):
                col, op = STRUCT_FILL[head]
                set_fill(p, col, op)
                report.append(f"{head}: 補標準色 {col}")
        gt = g.getAttribute("transform")
        if gt:
            for k in kids:
                if k.nodeName not in ("polygon", "path", "rect", "text") \
                        and k.parentNode is g:
                    k.setAttribute("transform",
                                   (gt + " " + k.getAttribute("transform"))
                                   .strip())
            g.removeAttribute("transform")
        # 文字標籤：先記下群組，主迴圈結束（牆烘焙完）後統一計算位置
        if head == "Space":
            space_groups.append((g, cls.split()[1]))
    # 牆帶遮罩（標籤避開牆）——此時全部 transform 已烘焙
    wall_holes = []
    for g in doc.getElementsByTagName("g"):
        if g.getAttribute("class") == "Wall" or g.getAttribute("id") == "Wall":
            for p in g.childNodes:
                if p.nodeType == 1 and p.nodeName == "polygon":
                    nums = [float(v)
                            for v in NUM.findall(p.getAttribute("points"))]
                    if nums:
                        wall_holes.append((nums[::2], nums[1::2]))
    for g, sub in space_groups:
        info = label_info(g, sub, wall_holes)
        if info:
            labels.append(info)
    if labels:
        rebuild_labels_group(doc, labels)
        report.append(f"Labels 頂層群組重建（{len(labels)} 個標籤）")
    if not dry:
        with open(svg_path, "w", encoding="utf-8") as f:
            doc.writexml(f)
    return report, manual


ID_FILL = {1: "Outdoor", 3: "Kitchen", 4: "LivingRoom", 5: "Bedroom",
           6: "Bath", 7: "Entry", 9: "Storage", 10: "Garage",
           11: "Undefined", 8: "Undefined"}


def render_house_view(floor_dir, out_png):
    import warnings
    warnings.filterwarnings("ignore")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(root, "training/CubiCasa5k"))
    import numpy as np
    import cv2
    from floortrans.loaders.house import House
    img = cv2.imread(os.path.join(floor_dir, "F1_scaled.png"))
    h, w = img.shape[:2]
    house = House(os.path.join(floor_dir, "model.svg"), h, w)
    seg = house.walls.astype(int)
    over = img.copy()
    for k in np.unique(seg):
        if k == 2:
            over[seg == 2] = (60, 60, 60)
        elif k in ID_FILL:
            r, g, b = hex2rgb(SPACE_FILL[ID_FILL[int(k)]])
            over[seg == k] = (b, g, r)
    blend = cv2.addWeighted(img, 0.5, over, 0.5, 0)
    scale = min(1.0, 1000 / max(h, w))
    if scale < 1.0:
        blend = cv2.resize(blend, (int(w * scale), int(h * scale)))
    cv2.imwrite(out_png, blend)
    return house.room_types, int(np.count_nonzero(seg == 2))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("floor_dir")
    ap.add_argument("--backup-dir", default=None)
    ap.add_argument("--render-dir", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    svg = os.path.join(a.floor_dir, "model.svg")
    name = os.path.basename(a.floor_dir.rstrip("/"))
    if a.backup_dir and not a.dry_run:
        os.makedirs(a.backup_dir, exist_ok=True)
        shutil.copy(svg, os.path.join(a.backup_dir, f"{name}_model.svg"))
    report, manual = fix_floor(svg, a.dry_run)
    print(f"=== {name} {'(dry-run)' if a.dry_run else ''} ===")
    for r in report:
        print("  -", r)
    for m in manual:
        print("  ⚠ 需人工:", m)
    print(f"共 {len(report)} 處修改，{len(manual)} 處待人工")
    if not a.dry_run:
        out = os.path.join(a.render_dir or a.floor_dir,
                           f"{name}_house_view.png")
        types, wall_px = render_house_view(a.floor_dir, out)
        print(f"House 驗證: room_types={types} 牆像素={wall_px}")
        print(f"渲染 → {out}")


if __name__ == "__main__":
    main()
