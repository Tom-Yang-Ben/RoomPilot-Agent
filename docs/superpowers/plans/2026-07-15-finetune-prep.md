# 路線圖 C 準備 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use the Execute Plan phase of
> superpowers:sunnydata-design to implement this plan task-by-task.

**Goal:** 43 張 png/ 的 CubiCasa 格式標注初稿＋資料打包＋Colab 微調 notebook。

**Architecture:** `make_annotation_drafts.py`（重用 eval_rooms_cc.run_pipeline 取得 det/labels/rooms → 組 model.svg → House round-trip 驗證）；`pack_finetune_data.py`（hq_arch train 300＋own×3 → zip）；`colab/finetune_cubicasa.ipynb`（nbformat 產生）。

**對齊 spec:** docs/superpowers/specs/2026-07-15-finetune-prep-design.md

## 探索補充的實作事實

- `PolygonWall.get_points` 用 `split(' ')[:-1]`——**Wall/Window/Door 的
  points 屬性必須以尾隨空格結尾**，否則丟最後一個頂點
- 牆多邊形任一軸 <4px 會 raise "small wall"（House 會跳過，可容忍）
- 門位多邊形用 build_rooms 的 zones quad（80~95/160~190cm 門）；
  det["doors"] 是弧偵測原始格式，不直接用
- own 樣本目錄同時放 F1_scaled.png 與 F1_original.png（同檔複本，
  loader txt 模式只讀 scaled，original 備 original_size 用）

### Task 1: 測試（RED）→ make_annotation_drafts.py（GREEN）

- tests/test_annotation_drafts.py：
  - 房型映射完整性：fp_c.ROOM_ZH ∪ f2r.ROOM_ZH_EX 全 key 有 CubiCasa class
  - build_svg 合成輸入（2 牆 1 窗 1 房）→ minidom 可解析、Wall points
    尾隨空格、Space class 正確
  - House round-trip：合成 svg 寫暫存 → House(path,h,w) 牆像素>0
- make_annotation_drafts.py：
  - `to_cubicasa_class(label)` 映射（room/None→Undefined）
  - `room_polygons(labels, rooms)`：每房 mask→findContours 最大外輪廓
    →approxPolyDP(eps=2)
  - `build_svg(w, h, rects, wins, zones, spaces, symbols)`→minidom Document
  - main：逐張跑管線（cc 快取已有）→寫 own_dataset/<名>/{F1_scaled.png,
    F1_original.png,model.svg}→House 回讀驗證→own_train.txt（43）／
    own_val.txt（5 張：floor01/10/20/30/40）
- 驗收：pytest 綠；43 張全產出、House 回讀 43/43 通過

### Task 2: pack_finetune_data.py

- hq_arch train 前 300（排序決定性）＋ own_dataset 43
- staging：finetune_data/{own/<名>/, high_quality_architectural/<id>/,
  train.txt(own 行×3＋hq 行), val.txt(own_val 5 行)}
- zip 並列印尺寸/清單統計；zip 與 staging 進 .gitignore（own_dataset/ 進版控——
  它是人工修正的工作底稿）
- 驗收：zip 產出、清單統計正確（train 行數 = 300 + 43*3）

### Task 3: colab/finetune_cubicasa.ipynb（nbformat 產生）＋收尾

- cells：GPU 檢查→clone+pip→Drive 掛載解壓→sed format='lmdb'→'txt'（2 處）
  →微調（--weights 基底 --l-rate 1e-4 --n-epoch 20 --batch-size 8
  --image-size 256，參數 cell 揭露）→checkpoint 回 Drive→sanity 推論疊圖
  →尾註：本機驗收流程（換權重→eval_rooms_cc --gt-seg 對比）
- nbformat.validate 通過；README v2.9＋路線 C 條目更新；commit

## Self-Review

spec 全覆蓋（草稿/打包/notebook/驗證四節）✓；尾隨空格陷阱已記 ✓；
own 樣本不進正式評分集 ✓
