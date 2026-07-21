#!/usr/bin/env python3
"""我們的 CV 管線 vs CubiCasa5k，在 pngans/ 21 張人工答案上比分。
牆:像素級 P/R/F1(±3px 容差:precision 對膨脹GT算、recall 對膨脹預測算)。
窗:綠框配對(交集/較小框 ≥0.3 或中心落框內)，同 eval_windows.py 規則。
用法: python score_compare.py <repo_dir> <cc_out_dir>
"""
import glob, json, os, sys
import cv2
import numpy as np

REPO, CCOUT = sys.argv[1], sys.argv[2]
K = np.ones((7, 7), np.uint8)          # ±3px

def red_mask(img):                     # 答案圖的紅=牆(深紅 R≈115~136 也要吃)
    b, g, r = img[:, :, 0].astype(int), img[:, :, 1].astype(int), img[:, :, 2].astype(int)
    return ((r - np.maximum(g, b) >= 60) & (r >= 100)).astype(np.uint8)

def green_boxes_mask(mask):
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8))
    out = []
    for i in range(1, n):
        x, y, w, h, a = stats[i]
        if a >= 30:
            out.append((x, y, x + w, y + h))
    return out

def green_boxes_img(img):
    b, g, r = img[:, :, 0].astype(int), img[:, :, 1].astype(int), img[:, :, 2].astype(int)
    m = ((g >= 120) & (r <= 110) & (b <= 110)).astype(np.uint8)
    m = cv2.dilate(m, np.ones((3, 3), np.uint8))   # 框線連成一塊
    return green_boxes_mask(m)

def match(preds, gts):
    def hit(p, g):
        ix = max(0, min(p[2], g[2]) - max(p[0], g[0]))
        iy = max(0, min(p[3], g[3]) - max(p[1], g[1]))
        inter = ix * iy
        amin = min((p[2]-p[0])*(p[3]-p[1]), (g[2]-g[0])*(g[3]-g[1]))
        if amin > 0 and inter / amin >= 0.3:
            return True
        pcx, pcy = (p[0]+p[2])/2, (p[1]+p[3])/2
        gcx, gcy = (g[0]+g[2])/2, (g[1]+g[3])/2
        return (g[0] <= pcx <= g[2] and g[1] <= pcy <= g[3]) or \
               (p[0] <= gcx <= p[2] and p[1] <= gcy <= p[3])
    tp = sum(1 for g in gts if any(hit(p, g) for p in preds))
    fp = sum(1 for p in preds if not any(hit(p, g) for g in gts))
    fn = len(gts) - tp
    return tp, fp, fn

def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2*p*r/(p+r) if p+r else 0.0
    return p, r, f

def wall_pix(pred, gt):
    gt_d = cv2.dilate(gt, K); pr_d = cv2.dilate(pred, K)
    tp_p = int((pred & gt_d).sum()); fp = int(pred.sum()) - tp_p
    tp_r = int((gt & pr_d).sum());  fn = int(gt.sum()) - tp_r
    p = tp_p / max(1, pred.sum()); r = tp_r / max(1, gt.sum())
    f = 2*p*r/(p+r) if p+r else 0.0
    return p, r, f

rows, agg = [], {}
for ans in sorted(glob.glob(os.path.join(REPO, 'pngans/gray', '*_ans.png'))):
    base = os.path.basename(ans).replace('_ans.png', '')
    A = cv2.imread(ans)
    gt_wall = red_mask(A)
    gt_win = green_boxes_img(A)
    # ── 我們的管線:json/gray/ 的牆矩形 + 窗矩形
    d = json.load(open(os.path.join(REPO, 'json/gray', base + '.json')))
    ours_wall = np.zeros(gt_wall.shape, np.uint8)
    for w in d['walls']:
        x0, y0, x1, y1 = w['px']
        cv2.rectangle(ours_wall, (x0, y0), (x1, y1), 1, -1)
    ours_win = [tuple(w['px']) for w in d['windows']]
    # ── CubiCasa mask
    z = np.load(os.path.join(CCOUT, base + '_mask.npz'))
    cc_wall = z['wall'].astype(np.uint8)
    if cc_wall.shape != gt_wall.shape:
        cc_wall = cv2.resize(cc_wall, gt_wall.shape[::-1], interpolation=cv2.INTER_NEAREST)
    cc_win = green_boxes_mask(z['window'])

    ow = wall_pix(ours_wall, gt_wall); cw = wall_pix(cc_wall, gt_wall)
    om = prf(*match(ours_win, gt_win)); cm = prf(*match(cc_win, gt_win))
    rows.append((base, ow, cw, om, cm, len(gt_win)))

print(f"{'':10s} ── 牆 F1(像素±3px) ──   ── 窗 F1(框配對) ──")
print(f"{'圖':10s} {'我們':>6s} {'CubiCasa':>9s}   {'我們':>6s} {'CubiCasa':>9s}  GT窗數")
mo = mc = wo = wc = 0.0
for base, ow, cw, om, cm, ng in rows:
    flag = ' ◄' if cw[2] - ow[2] > 0.15 else ''
    print(f"{base:10s} {ow[2]:6.2f} {cw[2]:9.2f}   {om[2]:6.2f} {cm[2]:9.2f}  {ng:5d}{flag}")
    mo += ow[2]; mc += cw[2]; wo += om[2]; wc += cm[2]
n = len(rows)
print(f"{'平均':10s} {mo/n:6.2f} {mc/n:9.2f}   {wo/n:6.2f} {wc/n:9.2f}")
