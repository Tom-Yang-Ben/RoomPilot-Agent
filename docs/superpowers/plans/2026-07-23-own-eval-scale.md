# own_eval 量尺 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use the Execute Plan phase of
> superpowers:sunnydata-design to implement this plan task-by-task.

**Goal:** eval_rooms_cc.py 增加 --own-eval 模式，用 own_eval 12 題保留集評房型命名層。

**Architecture:** 最小侵入擴充——新增樣本挑選函式與路徑切換參數，評分核心共用。

**Tech Stack:** Python（既有 .venv）、pytest。

---

### Task 1: 單元測試（RED）

**Files:**
- Create: `tests/test_eval_rooms_own.py`

- [x] **Step 1: 寫失敗測試**——`pick_own_samples()` 回傳 12 題 `("own", sid)`、
      每題目錄含 F1_scaled.png 與 model.svg；`report_path_for(own, gt_seg)` 四種組合。
- [x] **Step 2: 跑測試確認失敗**（`pick_own_samples` 尚不存在 → ImportError/AttributeError）

### Task 2: 實作（GREEN）

**Files:**
- Modify: `scripts/eval_rooms_cc.py`

- [x] **Step 1:** 常數 `OWN_DIR = "Identify_ans/own_eval"`；新增 `pick_own_samples()`
      讀 `eval_list.txt` → `[("own", sid)]`，守門：目錄/F1_scaled.png/model.svg 缺漏即報錯。
- [x] **Step 2:** 抽出 `report_path_for(own, gt_seg)`：`report[_own][_gtseg].json`。
- [x] **Step 3:** `eval_one(..., svg_path)` 參數化 GT 路徑；`main()` 依 `--own-eval`
      切樣本來源、staging 來源（own_eval 的 F1_scaled.png）與報表路徑。
- [x] **Step 4:** 跑測試通過；煙霧測試 `--own-eval --gt-seg --smoke 2`。

### Task 3: 實跑量尺（驗收）

- [x] **Step 1:** 基線：`python scripts/eval_rooms_cc.py --own-eval --gt-seg`
      → `json/eval_rooms/report_own_gtseg.json`
- [x] **Step 2:** v4：`CC_WEIGHTS=training/model_finetuned_v4.pkl
      CC_CACHE_DIR=training/cubicasa_room_ft4 python scripts/eval_rooms_cc.py --own-eval --gt-seg`
      → 快照 `report_own_gtseg_ft_v4.json`、還原基線報表
- [x] **Step 3:** 對比報告（基線 vs v4 逐類 P/R、具名 macro-F1）

### Task 4: 收尾

- [x] **Step 1:** 回歸：既有 CubiCasa 模式 `--gt-seg --smoke 2` 不受影響
- [x] **Step 2:** commit（WHY/WHAT/IMPACT）
