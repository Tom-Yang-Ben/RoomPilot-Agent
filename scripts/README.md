# scripts/ 腳本說明

本目錄共 16 個 Python 腳本，依功能分為五組。整體工作流：

**主管線**（floorplan2dxf_color）產出 → **eval 系列**守門評分 → **infer 系列**提供 DL 證據融合 → **路線圖 B/C 腳本**建符號庫與微調資料。

> 根目錄另有 `floorplan2room.py`（房型辨識）與 `cabinet_designer.py`（櫃體設計入口），不在本目錄範圍。

---

## 核心轉換管線

### floorplan2dxf.py（約 1400 行）
黑白建築平面圖 PNG → DXF 主程式。不描輪廓（會歪），改用「偵測線條後強制建構成純水平/垂直線」的正交策略——H 線兩端共用同一個 y、V 線兩端共用同一個 x。參數全在 `config.ini`。

```bash
python3 floorplan2dxf.py            # 使用 config.ini
python3 floorplan2dxf.py 別的.ini
```

**注意：此檔已凍結，不再修改。**

### floorplan2dxf_color.py（約 1900 行）
彩色平面圖版本，目前的開發主力。用獨立的 `config_color.ini`，輸出一律進 `chk/color/`、`dxf_scale/color/`、`json/color/`、`json/color_arch/` 等 color 子目錄，與黑白管線（`chk/gray/`、`dxf_scale/gray/`、`json/gray/`、`json/arch/`）完全隔離、不互相覆蓋。

```bash
python3 floorplan2dxf_color.py      # 批次 color_png/ → dxf_scale/color/
```

---

## 深度學習推論

### infer_cubicasa.py
CubiCasa5k 模型推論：PNG → 牆/窗/門 bool mask ＋ 房間語意/圖示類別圖（原圖尺寸），輸出 `<名>_mask.npz` 與 `<名>_cc.png` 疊圖。只借用 floortrans 的模型定義，不碰其過舊的 loader；checkpoint 以 `weights_only=True` 安全載入。

```bash
python infer_cubicasa.py <weights.pkl> <out_dir> <img1> [img2 ...]
```

### infer_mitunet.py
MitUNet（smp.Unet + mit_b4 編碼器 + scSE）牆體分割推論。輸出格式與 infer_cubicasa.py 一致，可直接餵 `eval_cc_masks.py` 評分，或設 `config_color.ini` 的 `cc_mask_dir` 做融合。

**權重為 CC-BY-NC 4.0（禁商用），僅供評估比較。**

```bash
python3 infer_mitunet.py <weights.pth> <out_dir> <img1> [img2 ...] [--size 512]
```

### apply_cubicasa_patches.py
CubiCasa5k 程式庫的 numpy 2.x 相容補丁（上游 `np.matrix` 拆行指派會 ValueError）。因 `CubiCasa5k/` 不進版控，clone 後跑一次即可；已補丁則自動跳過，可重複執行。

```bash
python apply_cubicasa_patches.py [--dir CubiCasa5k]
```

---

## 評分／驗證（eval 系列）

### eval_windows.py
用 `pngans/gray/` 人工答案評 `chk/gray/` 的窗戶偵測：兩邊抽綠框互相配對算 TP/FP/FN（交集/較小框 ≥ 0.3 或中心落框內）。**覆蓋 chk/dxf 前必跑的守門腳本。**

```bash
python3 eval_windows.py [答案目錄] [chk目錄]
```

### eval_doors.py
用 `door/` 的門樣式圖驗證「門不會被誤判成窗」——只要輸出任何窗框就算漏過濾。過濾率目標 ≥ 95%。

```bash
python3 eval_doors.py [door目錄]
```

### eval_color_walls.py
彩色管線牆體（含建築基柱）偵測評分：`pngans/color/` 的純色 RGB(136,0,21) 標註 vs `detect_walls()` 矩形化輸出，算像素級精準率/召回率/IoU。`--vis` 另存差異圖（白=TP、紅=FP、綠=FN）。

```bash
python3 eval_color_walls.py [名稱 ...] [--vis]
```

### eval_cc_masks.py
與 eval_color_walls.py 同一套指標，但評的是 `cubicasa/color/<名>_mask.npz` 的 DL 原始 wall mask（不經矩形化）——判斷深度學習遮罩本身實力，決定融合策略。

```bash
python3 eval_cc_masks.py [名稱 ...] [--dir 目錄] [--vis]
```

### eval_rooms_cc.py
路線圖 A：用 CubiCasa5k model.svg 的 Space 多邊形當 ground truth，對 floorplan2room 的房間方塊算「分割 IoU＋房型混淆矩陣」。樣本取 val/test 的 high_quality_architectural 單層樓（train 留給微調）。`--gt-seg` 可解耦：GT 多邊形當房間，只評房型辨識層。

```bash
python eval_rooms_cc.py [--n-test 40] [--n-val 30] [--smoke N] [--thr 0.5] [--gt-seg]
# 輸出：eval_rooms/report[_gtseg].json、eval_rooms/chk/<id>_{gt,pred,gtpred}.png
```

### score_compare.py
我們的 CV 管線 vs CubiCasa5k 正面對決：在 `pngans/` 21 張人工答案上比牆（像素級 P/R/F1，±3px 容差）與窗（綠框配對，同 eval_windows.py 規則）。

```bash
python score_compare.py <repo_dir> <cc_out_dir>
```

---

## 符號比對（路線圖 B）

### extract_symbol_lib.py
一次性腳本：走訪 CubiCasa5k train.txt 全部樣本的 model.svg，萃取六類 FixedFurniture（Toilet/Bathtub/BathtubRound/IntegratedStove/Sink/Shower）向量線稿，渲染成 48×48 標準模板（方向標準化、零污染），去重後存 `symbol_lib.npz`。val/test 樣本完全不碰（評分集衛生）。

```bash
python extract_symbol_lib.py [--out symbol_lib.npz]
```

### symbol_match.py
模板庫的渲染與比對引擎：查詢圖細線層輪廓以 Hu moments 預篩 ＋ chamfer 距離驗證兩階段比對，作為手寫幾何規則（`floorplan2room.detect_symbols`）的並行互補證據來源。`symbol_lib.npz` 缺失時回空清單，管線行為不變。

---

## 微調資料製作（路線圖 C）

### make_annotation_drafts.py
把 `png/` 每張圖的管線輸出（牆矩形/窗/門位/房間方塊+房型/符號命中）組成 CubiCasa model.svg 格式標注初稿，存 `own_dataset/<名>/`，供人工用 Inkscape 修正。產出後逐張以 `House()` 回讀驗證。

```bash
python make_annotation_drafts.py [--png-dir png] [--out own_dataset]
```

### fix_annotation_paths.py
修復 Inkscape 手修後把 `<polygon>` 存成 `<path>` 的問題（CubiCasa 解析器只認 polygon，遇 path 直接 StopIteration）。把「僅含直線段的閉合 path」無損轉回 polygon；遇曲線指令報錯不動檔案。

```bash
python scripts/fix_annotation_paths.py [--check]   # --check 只掃描回報，不寫檔
```

### pack_finetune_data.py
打包微調資料 zip：own_dataset 43 張（人工修正後）＋ hq_arch train 前 300 張（防災難性遺忘），own 樣本 ×3 過採樣混合。own_val.txt 僅作訓練監控，正式驗收永遠走路線 A 的 val/test 評分集。

```bash
python pack_finetune_data.py [--n-hq 300] [--oversample 3]
# 產出：finetune_data.zip（本機訓練解壓用；亦可上傳雲端環境）
```
