#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_symbol_quality.py — 模板庫逐模板品質掃描（偵測層強化輪，2026-08-01）。

背景：symbol_lib.npz 943 條模板只啟用 kstove/ksink 兩類（v2.18 §4），
浴具/沙發/床全數停用——核心 5 類的 18 件切割漏切中 ~17 件卡在符號
證據缺失。本工具把「哪些模板在真實圖面上有效」變成可量測：

  對 own_dataset 24 題，以全類別啟用跑 match_symbols 等價流程，
  記錄每個命中（kind、模板序號、chamfer、位置），再用 GT 房型
  多邊形當弱標籤歸類——命中落在該 kind 的預期房型內＝TP，
  落在別的房型＝FP，落在室外/無 GT＝ignore。

產出 temp/json/symbol_quality.json：逐 kind 與逐模板的 TP/FP 統計，
供決定（1）哪些 kind 可以啟用（2）哪些模板該剪除（3）門檻要不要分級。
量尺紀律：只掃開發集，own_eval 保留集不碰。
"""
import json
import os
import sys
from collections import defaultdict

import cv2
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "backend", "floorplan"))
sys.path.insert(0, os.path.join(_ROOT, "training", "scripts"))

import eval_rooms_cc as ev
import floorplan2dxf as fp_bw
import floorplan2dxf_color as fp_c
import symbol_match as sm

ALL_KINDS = ("basin", "bed", "chair", "dtable", "ksink", "kstove",
             "sofa", "tub", "wc", "wardrobe")
# kind → 預期 GT 房型（弱標籤）。dtable 依使用者裁決屬廚房系，但餐桌
# 實際常擺在 GT LivingRoom（餐區歸客廳慣例），兩者皆算 TP。
EXPECT = {"basin": {"Bath"}, "tub": {"Bath"}, "wc": {"Bath"},
          "kstove": {"Kitchen"}, "ksink": {"Kitchen"},
          "dtable": {"Kitchen", "LivingRoom"},
          "sofa": {"LivingRoom"}, "chair": {"LivingRoom", "Bedroom"},
          "bed": {"Bedroom"}, "wardrobe": {"Bedroom", "Storage"}}
OUT = "temp/json/symbol_quality.json"


def match_verbose(det, lib):
    """match_symbols 等價，但回傳 (kind, tpl_global_idx, chamfer, cx, cy)
    且不因 best_ch > CH_THR 丟棄——門檻分析交給下游。"""
    thin, cm = det.get("thin"), det["cm"]
    if lib is None or thin is None:
        return []
    boxes = det.get("text_boxes") or ()
    closed = cv2.morphologyEx(thin, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    labels = lib["labels"]
    idx_of = {k: [i for i, l in enumerate(labels) if l == k]
              for k in lib["size"]}
    hits = []
    for c in cnts:
        if len(c) < 20:
            continue
        x, y, w, h = cv2.boundingRect(c)
        if sm._in_text_box(x, y, w, h, boxes):
            continue
        lo, hi = sorted((w * cm, h * cm))
        ok = [k for k, ((s5, s95), (l5, l95)) in lib["size"].items()
              if s5 * 0.8 <= lo <= s95 * 1.2 and l5 * 0.8 <= hi <= l95 * 1.2]
        if not ok:
            continue
        cand = sm.crop_to_canvas(closed, x, y, w, h)
        if cand is None:
            continue
        dt_cand = sm.dist_transform(cand)
        best = (None, -1, 1e9)
        for k in ok:
            for i in idx_of[k]:
                ch = sm.chamfer_dt(cand, dt_cand, lib["rasters"][i],
                                   lib["dt"][i])
                if ch < best[2]:
                    best = (k, i, ch)
        if best[0] is not None:
            hits.append((best[0], best[1], best[2],
                         x + w / 2.0, y + h / 2.0))
    return hits


def main():
    lib = sm.load_lib(kinds=ALL_KINDS)
    assert lib is not None, "模板庫載入失敗"
    cfg_bw = fp_bw.load_config("config.ini")
    cfg_color = fp_c.load_config("config_color.ini")
    ev.OWN_DIR = "testdata/Identify_ans/own_dataset"
    samples = [sid for _sp, sid in ev.pick_own_samples()]
    per_kind = defaultdict(lambda: {"tp": 0, "fp": 0, "outside": 0,
                                    "fp_rooms": defaultdict(int)})
    per_tpl = defaultdict(lambda: {"tp": 0, "fp": 0})
    details = []
    for n, sid in enumerate(samples, 1):
        img = os.path.join(ev.IN_DIR, sid + ".png")
        if not os.path.isfile(img):
            print(f"skip {sid}（無圖）")
            continue
        det, _l, _r = ev.run_pipeline(img, cfg_bw, cfg_color, build=False)
        bgr = det["bgr"]
        gt = ev.parse_gt(
            os.path.join(ev.OWN_DIR, sid, "model.svg"), *bgr.shape[:2])
        hits = match_verbose(det, lib)
        for kind, ti, ch, cx, cy in hits:
            iy, ix = int(round(cy)), int(round(cx))
            room = next((lab for lab, m in gt
                         if 0 <= iy < m.shape[0] and 0 <= ix < m.shape[1]
                         and m[iy, ix]), None)
            room = ev.norm_label(room) if room else None
            ok = room in EXPECT[kind] if room else None
            cat = "tp" if ok else ("fp" if room else "outside")
            per_kind[kind][cat] += 1
            if cat == "fp":
                per_kind[kind]["fp_rooms"][room] += 1
            if room:
                per_tpl[ti]["tp" if ok else "fp"] += 1
            details.append({"img": sid, "kind": kind, "tpl": int(ti),
                            "chamfer": round(ch, 3), "room": room,
                            "cat": cat})
        print(f"[{n}/{len(samples)}] {sid}: {len(hits)} hits")
    rep = {
        "per_kind": {k: {"tp": v["tp"], "fp": v["fp"],
                         "outside": v["outside"],
                         "fp_rooms": dict(v["fp_rooms"])}
                     for k, v in sorted(per_kind.items())},
        "per_template": {str(i): v for i, v in sorted(per_tpl.items())},
        "details": details,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(rep, open(OUT, "w", encoding="utf-8"), ensure_ascii=False,
              indent=1)
    print(f"\n報表 → {OUT}")
    print(f'{"kind":9} {"TP":>4} {"FP":>4} {"室外":>4}')
    for k, v in sorted(per_kind.items()):
        print(f'{k:9} {v["tp"]:4} {v["fp"]:4} {v["outside"]:4}  '
              f'FP分佈 {dict(v["fp_rooms"])}')


if __name__ == "__main__":
    main()
