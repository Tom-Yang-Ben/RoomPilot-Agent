"""extract_room_crops.py — 房間裁切資料集（去 CubiCasa 分類器實驗用）。

從 own_dataset（訓練）與 own_eval（測試，永不進訓練）的 model.svg 取每個
Space 多邊形，以 bbox＋邊距從 F1_scaled.png 裁出房間圖塊，供「裁切分類」
路線（DINOv2 linear probe / VLM 探測）使用。標籤沿用 eval_rooms_cc 的
9 類正規化（Undefined→space、Balcony→outdoor…）。

用法：python scripts/extract_room_crops.py [--margin 0.15] [--out training/room_crops]
輸出：<out>/{train,test}/<floor>_<idx>_<label>.png ＋ <out>/manifest.json
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "training/CubiCasa5k"))
sys.path.insert(0, os.path.join(_ROOT, "backend", "floorplan"))

SETS = [("train", "testdata/Identify_ans/own_dataset", "own_train.txt"),
        ("test", "testdata/Identify_ans/own_eval", "eval_list.txt")]


def norm_label(k):
    if k in (None, "", "room"):
        return "space"
    return "outdoor" if k == "balcony" else k


def iter_rooms(svg_path):
    """model.svg → [(9類label, rr, cc)]；空群組/退化多邊形跳過。"""
    from xml.dom import minidom
    from floortrans.loaders.house import rooms_selected
    from floortrans.loaders.svg_utils import get_polygon
    import floorplan2room as f2r
    doc = minidom.parse(svg_path)
    for e in doc.getElementsByTagName("g"):
        cls = e.getAttribute("class").split(" ")
        if not cls or cls[0] != "Space":
            continue
        cid = rooms_selected.get(cls[1] if len(cls) > 1 else "Undefined", 11)
        if cid in (0, 2, 8):
            continue
        try:
            rr, cc = get_polygon(e)
        except StopIteration:
            continue
        if rr.size == 0:
            continue
        yield norm_label(f2r.CC_ROOM_LABEL.get(cid)), rr, cc


def crop_bbox(img, rr, cc, margin):
    """多邊形 bbox＋比例邊距裁切（含鄰接牆/門窗上下文）。"""
    h, w = img.shape[:2]
    r0, r1, c0, c1 = rr.min(), rr.max(), cc.min(), cc.max()
    mr, mc = int((r1 - r0) * margin), int((c1 - c0) * margin)
    r0, r1 = max(0, r0 - mr), min(h, r1 + mr)
    c0, c1 = max(0, c0 - mc), min(w, c1 + mc)
    return img[r0:r1, c0:c1], [int(r0), int(r1), int(c0), int(c1)]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--margin", type=float, default=0.15)
    ap.add_argument("--out", default="training/room_crops")
    a = ap.parse_args()

    manifest = []
    for split, root, listfile in SETS:
        out_dir = os.path.join(a.out, split)
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(root, listfile)) as f:
            ids = [ln.strip().strip("/") for ln in f if ln.strip()]
        for sid in ids:
            img = cv2.imread(os.path.join(root, sid, "F1_scaled.png"))
            if img is None:
                raise FileNotFoundError(f"{root}/{sid}/F1_scaled.png")
            for i, (label, rr, cc) in enumerate(
                    iter_rooms(os.path.join(root, sid, "model.svg"))):
                crop, bbox = crop_bbox(img, rr, cc, a.margin)
                if crop.size == 0:
                    continue
                name = f"{sid}_{i:02d}_{label}.png"
                cv2.imwrite(os.path.join(out_dir, name), crop)
                manifest.append({"split": split, "floor": sid, "idx": i,
                                 "label": label, "bbox": bbox,
                                 "path": os.path.join(out_dir, name)})
    with open(os.path.join(a.out, "manifest.json"), "w") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    for split in ("train", "test"):
        rows = [m for m in manifest if m["split"] == split]
        cnt = {}
        for m in rows:
            cnt[m["label"]] = cnt.get(m["label"], 0) + 1
        print(f"{split}: {len(rows)} 房  {dict(sorted(cnt.items()))}")
    print(f"manifest → {a.out}/manifest.json")


if __name__ == "__main__":
    main()
