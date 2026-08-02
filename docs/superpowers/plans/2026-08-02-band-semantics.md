# 帶級 DINO 語意判別實作計畫（白牆萃取品質輪）

> **For agentic workers:** REQUIRED SUB-SKILL: Use the Execute Plan phase of
> sunnydata-design to implement this plan task-by-task. Steps use checkbox
> (`- [ ]`) syntax for tracking.

**Goal:** 量測「帶級 DINO 語意」能否分離彩圖白牆帶的真/假，若可分則外科接入白牆救援輪，拉升彩 dev 命中（75.0% → 78%+）。

**Architecture:** 三階段量測驅動——階段 0 離線標定（GT 弱標籤＋留一張 CV 量 AUC）→ 階段 1 管線外科接入（`band_probe.npz` 資產＋救援輪帶過濾）→ 階段 2 A/B 收割。spec 見 `docs/superpowers/specs/2026-08-02-band-semantics-design.md`。

**Tech Stack:** DINOv2 ViT-S/14（重用 `room_classifier._load` 骨幹）、numpy logistic probe、既有 `fp_c.white_wall_rects`／`eval_rooms_cc` 基建。

---

### Task 1: 弱標籤器與帶特徵抽取（TDD）

**Files:**
- Create: `training/scripts/probe_band_semantics.py`
- Test: `training/tests/test_band_semantics.py`

- [ ] **Step 1**: 寫失敗測試——`band_gt_label`（合成 GT 遮罩：帶 90% 在房內→"fake"、帶在兩房夾縫→"true"、55%→None）與 `band_region`（水平/垂直帶的側翼展開 bbox 正確、越界裁剪）。
- [ ] **Step 2**: 實作 `band_gt_label(band, gt_masks, lo=0.3, hi=0.7)` 與 `band_region(band, T, shape)`（帶 bbox 沿法向 ±2.5T 展開）。
- [ ] **Step 3**: 測試通過後實作 DINO 帶特徵 `band_dino_features(model, bgr, band, T)`：region 裁切（垂直帶先轉置）→ resize 到 (42, 14·k)（k≤37）→ `get_intermediate_layers(x, 1, reshape=True)` → 3 patch 列分聚合 → `[mean(帶身), mean(側翼), 帶身−側翼]` 串接（384×3 維）。
- [ ] **Step 4**: 手工特徵 `band_hand_features`（長厚比、th/T、兩側 tint 佔比、暗牆網端接數、帶內 mean chroma/L）——邏輯借 `white_wall_rects` 既有採樣式。

### Task 2: 階段 0 標定主流程

**Files:**
- Modify: `training/scripts/probe_band_semantics.py`

- [ ] **Step 1**: 19 張彩 dev 逐張：`run_pipeline(build=False)` 拿 det → 1x `bgr`＋`T/sc`＋暗牆 rects（照 `floorplan2room.py:1838` 的呼叫式）→ `fp_c.white_wall_rects` 出帶。
- [ ] **Step 2**: `parse_gt`（1x 座標）→ 弱標籤；逐帶抽 DINO＋手工特徵。
- [ ] **Step 3**: 留一張 CV logistic probe（numpy 手寫 GD 即可，特徵 z-score 正規化）×3 組（DINO/手工/合併），輸出 AUC 與逐帶明細 `temp/json/band_semantics.json`。
- [ ] **Step 4**: 閘門判讀——合併 AUC ≥0.65 進 Task 3；否則試特徵變體（取樣密度/側翼距離/聚合），仍不可分即回報使用者轉方向 B。

### Task 3: 權重出貨與管線接入（階段 1，AUC 過線才做）

**Files:**
- Create: `backend/floorplan/band_probe.npz`（probe 權重資產）
- Modify: `backend/floorplan/floorplan2room.py`（救援輪帶過濾鉤）
- Test: `training/tests/test_band_semantics.py`（行為契約：無權重檔＝過濾停用零行為變化；分數低於門檻的帶被剔）

- [ ] **Step 1**: 全 dev 訓練最終 probe →`band_probe.npz`（weight/bias/norm/backbone 名，比照 room_head 慣例）。
- [ ] **Step 2**: `floorplan2room` 救援路徑：`white_wall_rects` 輸出後、採用閘前，帶語意分數 < 門檻者剔除（門檻由 dev A/B 掃 0.3/0.5/0.7 定）。缺權重檔→出聲停用、行為不變。
- [ ] **Step 3**: 行為契約測試＋`test_symbol_gate` 全綠。

### Task 4: A/B 收割（階段 2）

- [ ] **Step 1**: 彩 dev 逐張 A/B（`--report-suffix bandsem1`）：主戰場 07/08/09 轉化數、其餘 16 張零退化。
- [ ] **Step 2**: 灰 dev 跑一次確認零接觸（白牆線不走灰路）。
- [ ] **Step 3**: 有出貨則 plan/Readme 補記；commit 依 WHY/WHAT/IMPACT 拆（工具/資產＋接入/文件）。
