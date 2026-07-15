"""eval_rooms_cc.py — 路線圖 A：房型答案集評分。

CubiCasa5k model.svg 的 Space 多邊形當 ground truth，對 floorplan2room
的房間方塊算「分割 IoU＋房型混淆矩陣」——房型權重從拍腦袋變可量測。

樣本：val/test 的 high_quality_architectural 單層樓樣本（train 留給微調）。
用法：python eval_rooms_cc.py [--n-test 40] [--n-val 30] [--smoke N] [--thr 0.5]
      [--gt-seg]（GT 分割解耦：GT 多邊形當房間，只評房型辨識層）
輸出：eval_rooms/report[_gtseg].json、eval_rooms/chk/<id>_{gt,pred,gtpred}.png
"""
import argparse
import json
import os
import shutil
import sys
from dataclasses import replace
from xml.dom import minidom

import cv2
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "CubiCasa5k"))
sys.path.insert(0, _ROOT)              # floorplan2room 在專案根目錄

DATA = "CubiCasa5k/data/cubicasa5k"
SUBSET = "high_quality_architectural"
IN_DIR = "eval_rooms/input"
CHK_DIR = "eval_rooms/chk"
REPORT = "eval_rooms/report.json"
CLASSES = ["kitchen", "living", "bed", "bath", "entry",
           "storage", "garage", "outdoor", "space"]


def norm_label(k):
    """管線房型 key → 評分 9 類：balcony 併 outdoor、room/None 併 space。"""
    if k in (None, "", "room"):
        return "space"
    return "outdoor" if k == "balcony" else k


def match_rooms(gt_masks, pred_masks, thr=0.5):
    """GT×預測 IoU 貪婪一對一配對，回傳 [(gi, pi, iou)]，iou≥thr。"""
    cand = []
    for gi, g in enumerate(gt_masks):
        ga = int(g.sum())
        for pi, p in enumerate(pred_masks):
            inter = int(np.logical_and(g, p).sum())
            if not inter:
                continue
            iou = inter / (ga + int(p.sum()) - inter)
            if iou >= thr:
                cand.append((iou, gi, pi))
    cand.sort(reverse=True)
    used_g, used_p, out = set(), set(), []
    for iou, gi, pi in cand:
        if gi in used_g or pi in used_p:
            continue
        used_g.add(gi)
        used_p.add(pi)
        out.append((gi, pi, iou))
    return out


def confusion(pairs):
    """[(gt_label, pred_label)] → 巢狀 dict 混淆矩陣。"""
    cm = {c: {c2: 0 for c2 in CLASSES} for c in CLASSES}
    for g, p in pairs:
        cm[g][p] += 1
    return cm


def pick_samples(n_test=40, n_val=30):
    """val/test 清單中 SUBSET 的單層樓樣本（無 F2），排序取前 N。"""
    out = []
    for split, n in (("test", n_test), ("val", n_val)):
        with open(os.path.join(DATA, split + ".txt")) as f:
            ids = [ln.strip().strip("/").split("/")[1] for ln in f
                   if ln.strip().startswith("/" + SUBSET + "/")]
        elig = [i for i in sorted(ids, key=int)
                if os.path.isfile(os.path.join(DATA, SUBSET, i, "F1_scaled.png"))
                and not os.path.exists(os.path.join(DATA, SUBSET, i,
                                                    "F2_original.png"))]
        out += [(split, i) for i in elig[:n]]
        print(f"{split}: 合格 {len(elig)} 張，取 {min(n, len(elig))}")
    return out


def parse_gt(svg_path, h, w):
    """model.svg Space 多邊形 → [(9類label, bool mask)]；對位不符回 None。

    多邊形座標＝F1_scaled.png 像素（實證疊圖驗證）；SVG 的 width/height
    宣告與圖面尺寸普遍不符（三子集抽查皆然），不可用來驗對位——
    改以「多邊形範圍不得超出圖面 2%」守門。"""
    from floortrans.loaders.house import rooms_selected
    from floortrans.loaders.svg_utils import get_polygon
    import floorplan2room as f2r
    doc = minidom.parse(svg_path)
    gt = []
    for e in doc.getElementsByTagName("g"):
        cls = e.getAttribute("class").split(" ")
        if not cls or cls[0] != "Space":
            continue
        cid = rooms_selected.get(cls[1] if len(cls) > 1 else "Undefined", 11)
        if cid in (0, 2, 8):                     # 背景/牆/欄杆不是房間
            continue
        rr, cc = get_polygon(e)
        if rr.max() > h * 1.02 or cc.max() > w * 1.02:
            return None                          # 座標超出圖面 → 對位不符
        m = np.zeros((h, w), bool)
        m[np.clip(rr, 0, h - 1), np.clip(cc, 0, w - 1)] = True
        if m.sum() < 100:                        # 退化多邊形
            continue
        gt.append((norm_label(f2r.CC_ROOM_LABEL.get(cid)), m))
    return gt


def run_pipeline(img_path, cfg_bw, cfg_color, build=True):
    """floorplan2room 內部呼叫鏈（同 process()，但不落 json、回傳記憶體物件）。
    build=False 只跑偵測/比例尺/符號（GT 解耦模式用，不切房間）。"""
    import floorplan2room as f2r
    is_color, _ = f2r.probe_color(img_path)
    if is_color:
        det = f2r.detect_color(replace(cfg_color, input=img_path,
                                       output="", preview=None))
    else:
        det = f2r.detect_bw(replace(cfg_bw, input=img_path,
                                    output="", preview=None))
    f2r.refine_scale(det)
    det["cc_file"] = f2r._cc_path(img_path)
    det["symbols"] = f2r.detect_symbols(det)
    if not build:
        return det, None, None
    labels, rooms, _b, _z, _e = f2r.build_rooms(det)
    return det, labels, rooms


def _overlay(bgr, masks_labels, path):
    """房型色塊半透明疊圖（GT 與預測共用；色表沿用管線）。"""
    import floorplan2room as f2r
    vis, fill = bgr.copy(), bgr.copy()
    for lab, m in masks_labels:
        fill[m] = f2r.ROOM_BGR_EX.get(lab, (150, 150, 150))
    vis = cv2.addWeighted(fill, 0.5, vis, 0.5, 0)
    cv2.imwrite(path, vis)


def eval_gt_seg(sid, gt, bgr, cfg_bw, cfg_color):
    """GT 分割解耦：GT 多邊形直接當房間方塊，只跑房型辨識層
    （語意投票＋圖示＋符號）——量「0.15 門檻/圖示/符號權重」本身的品質，
    不被牆偵測失敗遮蔽。注意 cm 比例尺仍來自管線（可能偏差），
    圖示/符號證據層受其影響，語意投票層不受。"""
    import floorplan2room as f2r
    img = os.path.join(IN_DIR, sid + ".png")
    h, w = bgr.shape[:2]
    det, _l, _r = run_pipeline(img, cfg_bw, cfg_color, build=False)
    labels = np.zeros((h, w), np.int32)
    rooms = []
    for i, (_lab, m) in enumerate(gt, 1):
        labels[m] = i                            # GT 多邊形間幾乎不重疊
        rooms.append({"id": i, "area_px": int(m.sum())})
    if not f2r._cc_ok(det["cc_file"]):
        return {"id": sid, "status": "no_cc_cache"}
    f2r.classify_rooms_cc(det, labels, rooms, det["cc_file"])
    preds = [(norm_label(r["label"]), labels == r["id"]) for r in rooms]
    matched = [(gt[i][0], preds[i][0]) for i in range(len(gt))]  # 配對=恆等
    _overlay(bgr, preds, os.path.join(CHK_DIR, sid + "_gtpred.png"))
    return {"id": sid, "status": "ok", "n_gt": len(gt), "n_pred": len(gt),
            "n_match": len(gt), "mean_iou": 1.0, "pairs": matched,
            "ious": [1.0] * len(gt)}


def eval_one(sid, cfg_bw, cfg_color, thr, gt_seg=False):
    """單樣本：GT 解析＋管線＋配對。回傳評分 dict（error/分割失敗亦結構化）。"""
    img = os.path.join(IN_DIR, sid + ".png")
    svg = os.path.join(DATA, SUBSET, sid, "model.svg")
    bgr = cv2.imread(img)
    h, w = bgr.shape[:2]
    gt = parse_gt(svg, h, w)
    if gt is None:
        return {"id": sid, "status": "svg_mismatch"}
    if not gt:
        return {"id": sid, "status": "no_gt_rooms"}
    if gt_seg:
        return eval_gt_seg(sid, gt, bgr, cfg_bw, cfg_color)
    det, labels, rooms = run_pipeline(img, cfg_bw, cfg_color)
    if labels is None or not rooms:
        _overlay(bgr, gt, os.path.join(CHK_DIR, sid + "_gt.png"))
        return {"id": sid, "status": "seg_fail", "n_gt": len(gt)}
    if labels.shape != (h, w):                   # 彩圖管線可能 2 倍
        labels = cv2.resize(labels.astype(np.int32), (w, h),
                            interpolation=cv2.INTER_NEAREST)
    preds = [(norm_label(r["label"]), labels == r["id"]) for r in rooms]
    pairs = match_rooms([m for _, m in gt], [m for _, m in preds], thr)
    matched = [(gt[gi][0], preds[pi][0]) for gi, pi, _ in pairs]
    _overlay(bgr, gt, os.path.join(CHK_DIR, sid + "_gt.png"))
    _overlay(bgr, preds, os.path.join(CHK_DIR, sid + "_pred.png"))
    return {"id": sid, "status": "ok", "n_gt": len(gt), "n_pred": len(preds),
            "n_match": len(pairs),
            "mean_iou": round(float(np.mean([i for _, _, i in pairs])), 4)
                        if pairs else 0.0,
            "pairs": matched,
            "ious": [round(float(i), 4) for _, _, i in pairs]}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--n-test", type=int, default=40)
    ap.add_argument("--n-val", type=int, default=30)
    ap.add_argument("--smoke", type=int, default=0,
                    help="只跑前 N 張（煙霧測試）")
    ap.add_argument("--thr", type=float, default=0.5)
    ap.add_argument("--gt-seg", action="store_true",
                    help="GT 分割解耦：GT 多邊形當房間，只評房型辨識層")
    a = ap.parse_args()
    report_path = REPORT.replace(".json", "_gtseg.json") if a.gt_seg else REPORT

    import floorplan2room as f2r
    import floorplan2dxf as fp_bw
    import floorplan2dxf_color as fp_c
    cfg_bw = fp_bw.load_config("config.ini")
    cfg_color = fp_c.load_config("config_color.ini")

    samples = pick_samples(a.n_test, a.n_val)
    if a.smoke:
        samples = samples[:a.smoke]
    os.makedirs(IN_DIR, exist_ok=True)
    os.makedirs(CHK_DIR, exist_ok=True)
    staged = []
    for _, sid in samples:
        dst = os.path.join(IN_DIR, sid + ".png")
        if not os.path.isfile(dst):
            shutil.copy(os.path.join(DATA, SUBSET, sid, "F1_scaled.png"), dst)
        staged.append(dst)
    f2r.ensure_cc_masks(staged)                  # 缺快取自動補（CPU ~1 分/張）

    results = []
    for n, (split, sid) in enumerate(samples, 1):
        print(f"[{n}/{len(samples)}] {split}/{sid}", end=" ", flush=True)
        try:
            r = eval_one(sid, cfg_bw, cfg_color, a.thr, gt_seg=a.gt_seg)
        except Exception as e:                   # 單張爆炸不拖垮批次，總表可追溯
            r = {"id": sid, "status": "error", "error": repr(e)}
        r["split"] = split
        results.append(r)
        print(r["status"],
              f'IoU {r.get("mean_iou", 0):.2f} 配對 {r.get("n_match", 0)}'
              f'/{r.get("n_gt", "?")}' if r["status"] == "ok" else "")

    ok = [r for r in results if r["status"] == "ok"]
    all_pairs = [tuple(p) for r in ok for p in r["pairs"]]
    all_ious = [i for r in ok for i in r["ious"]]
    n_gt = sum(r["n_gt"] for r in ok)
    n_pred = sum(r["n_pred"] for r in ok)
    cm = confusion(all_pairs)
    summary = {
        "n_images": len(results), "n_ok": len(ok),
        "n_seg_fail": sum(r["status"] == "seg_fail" for r in results),
        "n_skip": sum(r["status"] in ("svg_mismatch", "no_gt_rooms", "error")
                      for r in results),
        "gt_rooms": n_gt, "pred_rooms": n_pred, "matched": len(all_pairs),
        "hit_rate": round(len(all_pairs) / n_gt, 4) if n_gt else 0,
        "overseg": round(n_pred / n_gt, 4) if n_gt else 0,
        "mean_iou": round(float(np.mean(all_ious)), 4) if all_ious else 0,
        "confusion": cm, "iou_thr": a.thr, "gt_seg_mode": a.gt_seg,
    }
    per_cls = {}
    for c in CLASSES:
        tp = cm[c][c]
        gt_c = sum(cm[c].values())
        pred_c = sum(cm[g][c] for g in CLASSES)
        per_cls[c] = {"gt": gt_c,
                      "precision": round(tp / pred_c, 3) if pred_c else None,
                      "recall": round(tp / gt_c, 3) if gt_c else None}
    summary["per_class"] = per_cls

    with open(report_path, "w") as f:
        json.dump({"summary": summary, "images": results}, f,
                  ensure_ascii=False, indent=1)

    print(f"\n{'=' * 62}\n樣本 {len(results)} 張：評分 {len(ok)}、"
          f"分割失敗 {summary['n_seg_fail']}、跳過 {summary['n_skip']}")
    print(f"GT 房間 {n_gt}  預測 {n_pred}（過切率 {summary['overseg']:.2f}）"
          f"  命中 {len(all_pairs)}（{summary['hit_rate']:.1%}）"
          f"  配對平均 IoU {summary['mean_iou']:.3f}")
    print("\n房型混淆矩陣（列=GT、欄=預測，僅 IoU≥%.1f 配對）:" % a.thr)
    print("GT\\預測".ljust(8) + "".join(c[:6].rjust(8) for c in CLASSES))
    for g in CLASSES:
        if sum(cm[g].values()) == 0:
            continue
        print(g.ljust(8) + "".join(str(cm[g][p]).rjust(8) for p in CLASSES))
    print("\n逐類  P / R:")
    for c in CLASSES:
        s = per_cls[c]
        if s["gt"] or s["precision"] is not None:
            print(f"  {c:8s} P={s['precision']}  R={s['recall']}  (GT {s['gt']})")
    print(f"\n報表 → {report_path}   疊圖 → {CHK_DIR}/")


if __name__ == "__main__":
    main()
