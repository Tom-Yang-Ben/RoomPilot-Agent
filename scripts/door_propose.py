"""door_propose.py — 門位 zone 提名器：把 build_rooms 的牆開口推理接進 doors。

診斷（26 題 own GT，106 門）：
  - detect_doors 弧偵測的候選天花板 recall 僅 0.189（86 門連候選都沒有）
  - floorplan2room.build_rooms 的門位 zones（牆端連線封口推理）實測
    recall 0.877、precision 0.798——管線裡早就有高召回門位來源，只是
    從未接進 training/json/gray 的 doors 清單
  - 門樣式模板（door_lib.npz）對 zone 真假無區分力（真門 zone 的門扇
    窗被牆線污染，chamfer 中位 2.14 vs 假門 2.06）——因此 zone 提名
    不做模板加減分；模板訊號只用在 door_match.py 的弧候選重評分

每個 zone → doors 新增一筆：score=0（非弧吻合）、score_fused=ZONE_SCORE、
src="zone"。原候選一律不動；可重複執行（先清舊 src="zone"/"tpl"）。

用法：python scripts/door_propose.py [名 ...]     # 預設掃 training/json/gray/*.json
"""
import argparse
import contextlib
import glob
import io
import json
import os
import sys

import numpy as np

_scripts = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _scripts)
sys.path.insert(0, os.path.join(os.path.dirname(_scripts), "backend", "floorplan"))   # 管線模組在 backend/floorplan/

ZONE_SCORE = 0.88   # 高於白模端 0.85 門檻、低於弧偵測滿分——來源可回溯
DEDUP = 0.6         # 與既有高分候選的去重距離（相對 zone 長邊）


def propose_zones(src):
    """跑偵測（不切房間）→ build_rooms → zones quad 清單。"""
    import floorplan2dxf as fp_bw
    import floorplan2dxf_color as fp_c
    import floorplan2room as f2r
    from eval_rooms_cc import run_pipeline
    cfg_bw = fp_bw.load_config("config.ini")
    cfg_color = fp_c.load_config("config_color.ini")
    with contextlib.redirect_stdout(io.StringIO()):   # 比例尺列印靜音
        det, _, _ = run_pipeline(src, cfg_bw, cfg_color, build=False)
        _l, _r, _b, zones, _e = f2r.build_rooms(det)
    return [np.array(q, np.float32) for q, _d in zones]


def rebuild_file(jpath, png_dir):
    data = json.load(open(jpath))
    src = os.path.join(png_dir, data["image"]["file"])
    if not os.path.isfile(src):
        return None
    doors = [d for d in data.get("doors", [])
             if d.get("src") not in ("zone", "tpl")]   # 冪等：清舊提名
    h = data["image"]["height_px"]
    cmpp = data["scale"]["cm_per_px"]
    exist = [(d["px"]["cx"], d["px"]["cy"]) for d in doors
             if d.get("score_fused", d["score"]) >= 0.85]
    n_new = 0
    for qa in propose_zones(src):
        cx, cy = map(float, qa.mean(0))
        long_ = float(max(np.ptp(qa[:, 0]), np.ptp(qa[:, 1])))
        if any((cx - ex) ** 2 + (cy - ey) ** 2 < (DEDUP * long_) ** 2
               for ex, ey in exist):
            continue
        doors.append({
            "px": {"cx": round(cx, 1), "cy": round(cy, 1),
                   "width": round(long_, 1)},
            "cm": {"cx": round(cx * cmpp, 2), "cy": round((h - cy) * cmpp, 2),
                   "width": round(long_ * cmpp, 1)},
            "score": 0.0,
            "score_fused": ZONE_SCORE,
            "src": "zone",
        })
        n_new += 1
    data["doors"] = doors
    with open(jpath, "w") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)
    return n_new


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("names", nargs="*", help="圖名（不含副檔名）；預設全部")
    ap.add_argument("--png-dir", default="testdata/png")
    ap.add_argument("--json-dir", default="training/json/gray")
    a = ap.parse_args()

    jpaths = ([os.path.join(a.json_dir, n + ".json") for n in a.names]
              if a.names else sorted(glob.glob(os.path.join(a.json_dir, "*.json"))))
    tot = 0
    for jp in jpaths:
        n = rebuild_file(jp, a.png_dir)
        if n is None:
            print(f"跳過（找不到原圖）：{os.path.basename(jp)}")
            continue
        tot += n
        print(f"{os.path.basename(jp):24} zone 提名 {n:3d}")
    print(f"\n共提名 {tot} 個門位候選（score_fused={ZONE_SCORE}）")


if __name__ == "__main__":
    main()
