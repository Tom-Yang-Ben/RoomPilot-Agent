# scripts/ 腳本說明

本目錄共 21 個 Python 腳本，依功能分為六組。整體工作流：

**主管線**（`backend/floorplan/`）產出 → **eval 系列**守門評分 → **infer 系列**提供 DL 證據融合 → **路線圖 B/C 腳本**建符號庫與微調資料。

> **2026-07-27 目錄重整**：管線主程式已移至 `backend/floorplan/` —— `floorplan2dxf.py`、
> `floorplan2dxf_color.py`、`floorplan2room.py`（房型辨識）、`eval_windows.py`、`eval_doors.py`
> 與 `config.ini`／`config_color.ini` 皆在該處；櫃體設計入口在 `backend/cabinetdesign/cabinet_designer.py`。
> 本目錄保留研發／評測／資料製作工具。

---

## 核心轉換管線（已移至 backend/floorplan/）

### backend/floorplan/floorplan2dxf.py（約 1400 行）
黑白建築平面圖 PNG → DXF 主程式。不描輪廓（會歪），改用「偵測線條後強制建構成純水平/垂直線」的正交策略——H 線兩端共用同一個 y、V 線兩端共用同一個 x。參數全在 `backend/floorplan/config.ini`。

```bash
python3 backend/floorplan/floorplan2dxf.py            # 批次 testdata/png/ → testdata/dxf/ + training/chk/gray/
python3 backend/floorplan/floorplan2dxf.py 別的.ini
```

**注意：此檔演算法凍結（2026-07-27 經評測驗證的 gmin_win 開口下限修正除外），修改必跑雙評分。**

### backend/floorplan/floorplan2dxf_color.py（約 1900 行）
彩色平面圖版本，目前的開發主力。用獨立的 `config_color.ini`，輸出進 `training/chk/color/`、`testdata/dxf/`、`training/json/color/`、`training/json/color_arch/`，與黑白管線（`training/chk/gray/`、`training/json/gray/`、`training/json/arch/`）完全隔離、不互相覆蓋。

```bash
python3 backend/floorplan/floorplan2dxf_color.py      # 批次 testdata/color_png/ → testdata/dxf/
```

---

## 深度學習推論

### infer_cubicasa.py
CubiCasa5k 模型推論：PNG → 牆/窗/門 bool mask ＋ 房間語意/圖示類別圖（原圖尺寸），輸出 `<名>_mask.npz` 與 `<名>_cc.png` 疊圖。只借用 floortrans 的模型定義，不碰其過舊的 loader；checkpoint 以 `weights_only=True` 安全載入。`floorplan2room.ensure_cc_masks()` 以 subprocess 呼叫本腳本補快取。

```bash
python infer_cubicasa.py <weights.pkl> <out_dir> <img1> [img2 ...]
```

### apply_cubicasa_patches.py
CubiCasa5k 程式庫的 numpy 2.x 相容補丁（上游 `np.matrix` 拆行指派會 ValueError）。因 `training/CubiCasa5k/` 不進版控，clone 後跑一次即可；已補丁則自動跳過，可重複執行。

```bash
python apply_cubicasa_patches.py [--dir CubiCasa5k]
```

---

## 評分／驗證（eval 系列）

### backend/floorplan/eval_windows.py（隨管線同移）
用 `testdata/Identify_ans/pngans/gray/` 人工答案評 `training/chk/gray/` 的窗戶偵測：兩邊抽綠框互相配對算 TP/FP/FN（交集/較小框 ≥ 0.3 或中心落框內）。**覆蓋 chk/dxf 前必跑的守門腳本。**

```bash
python3 backend/floorplan/eval_windows.py [答案目錄] [chk目錄]
```

### backend/floorplan/eval_doors.py（隨管線同移）
用 `testdata/Asset/door/` 的門樣式圖（86 張，door_001–086）驗證「門不會被誤判成窗」——只要輸出任何窗框就算漏過濾。過濾率目標 ≥ 95%，現行基準 84/86 = 98%（door_001/door_007 為已知困難樣本）。

```bash
python3 backend/floorplan/eval_doors.py [door目錄]
```

### eval_color_walls.py
彩色管線牆體（含建築基柱）偵測評分：`testdata/Identify_ans/pngans/color/` 的純色 RGB(136,0,21) 標註 vs `detect_walls()` 矩形化輸出，算像素級精準率/召回率/IoU。`--vis` 另存差異圖（白=TP、紅=FP、綠=FN）。

```bash
python3 scripts/eval_color_walls.py [名稱 ...] [--vis]
```

### eval_cc_masks.py
與 eval_color_walls.py 同一套指標，但評的是 `cubicasa/color/<名>_mask.npz` 的 DL 原始 wall mask（不經矩形化）——判斷深度學習遮罩本身實力，決定融合策略。

```bash
python3 scripts/eval_cc_masks.py [名稱 ...] [--dir 目錄] [--vis]
```

### eval_rooms_cc.py
路線圖 A：用 CubiCasa5k model.svg 的 Space 多邊形當 ground truth，對 floorplan2room 的房間方塊算「分割 IoU＋房型混淆矩陣」。樣本取 val/test 的 high_quality_architectural 單層樓（train 留給微調）。`--gt-seg` 可解耦：GT 多邊形當房間，只評房型辨識層；`--own-eval` 用 own_eval 12 題保留集當 GT。

```bash
python scripts/eval_rooms_cc.py [--n-test 40] [--n-val 30] [--smoke N] [--thr 0.5] [--gt-seg] [--own-eval]
# 輸出：training/json/eval_rooms/report[_own][_gtseg].json、training/eval_rooms/chk/<id>_{gt,pred,gtpred}.png
```

### score_compare.py
我們的 CV 管線 vs CubiCasa5k 正面對決：在 `testdata/Identify_ans/pngans/` 21 張人工答案上比牆（像素級 P/R/F1，±3px 容差）與窗（綠框配對，同 eval_windows.py 規則）。

```bash
python scripts/score_compare.py <repo_dir> <cc_out_dir>
```

---

## 符號比對（路線圖 B）

### extract_symbol_lib.py
一次性腳本：走訪 CubiCasa5k train.txt 全部樣本的 model.svg，萃取六類 FixedFurniture（Toilet/Bathtub/BathtubRound/IntegratedStove/Sink/Shower）向量線稿，渲染成 48×48 標準模板（方向標準化、零污染），去重後存 `backend/floorplan/symbol_lib.npz`（推論期資產，與消費它的 symbol_match 同目錄）。val/test 樣本完全不碰（評分集衛生）。

```bash
python training/scripts/extract_symbol_lib.py [--out <路徑>]   # 預設 = symbol_match.LIB_PATH
```

### symbol_match.py
模板庫的渲染與比對引擎：查詢圖細線層輪廓以 Hu moments 預篩 ＋ chamfer 距離驗證兩階段比對，作為手寫幾何規則（`floorplan2room.detect_symbols`）的並行互補證據來源。`backend/floorplan/symbol_lib.npz` 缺失時回空清單、**不報錯**（靜默停用），管線行為不變。

---

## 微調資料製作（路線圖 C）

### make_annotation_drafts.py
把 `testdata/png/` 每張圖的管線輸出（牆矩形/窗/門位/房間方塊+房型/符號命中）組成 CubiCasa model.svg 格式標注初稿，存 `testdata/Identify_ans/own_dataset/<名>/`，供人工用 Inkscape 修正。產出後逐張以 `House()` 回讀驗證。

```bash
python scripts/make_annotation_drafts.py [--png-dir testdata/png] [--out testdata/Identify_ans/own_dataset]
```

### fix_annotation_paths.py
修復 Inkscape 手修後把 `<polygon>` 存成 `<path>` 的問題（CubiCasa 解析器只認 polygon，遇 path 直接 StopIteration）。把「僅含直線段的閉合 path」無損轉回 polygon；遇曲線指令報錯不動檔案。

```bash
python scripts/fix_annotation_paths.py [--check]   # --check 只掃描回報，不寫檔
```

### sync_room_labels.py
把 Inkscape 人工改的房型「文字標籤」同步回 `class` 屬性（Inkscape 一般介面看不到 class，人工標注後兩者必脫節；解析器只讀 class）。文字寫法正規化映射進 CubiCasa 詞彙（Living Room→LivingRoom、Study→Office…），逐 g-id 定點替換不重排版，改完 House 回讀驗證。與 fix_annotation_paths.py 同屬「Inkscape 手修後必跑」工序。

```bash
python scripts/sync_room_labels.py [--dry-run] [--no-validate]
```

### pack_finetune_data.py
打包微調資料 zip：testdata/Identify_ans/own_dataset（人工修正後）＋ hq_arch train 前 300 張（防災難性遺忘），own 樣本 ×3 過採樣混合。own_val.txt 僅作訓練監控，正式驗收永遠走路線 A 的 val/test 評分集。

```bash
python scripts/pack_finetune_data.py [--n-hq 300] [--oversample 3]
# 產出：training/finetune_data.zip（本機訓練解壓用；亦可上傳雲端環境）
```

---

## 門偵測增強

四支後處理腳本，全部只讀寫 `training/json/gray`（凍結的主管線零接觸）、可重複執行。背景：弧偵測（detect_doors）在 26 題 own GT 上候選天花板 recall 僅 0.189；`build_rooms` 的門位 zones 實測 R 0.877/P 0.798。融合結果（門檻 0.85）：P 0.361/R 0.132 → **P 0.588/R 0.858**。

### extract_door_lib.py
`testdata/Asset/door/` 人工剪裁門樣式圖 → `training/door_lib.npz`（48×48、8 向展開去重，與 symbol_lib 同規格；實心牆段 erode-subtract 轉輪廓與查詢側同正規化）。

```bash
python scripts/extract_door_lib.py [--src testdata/Asset/door] [--out door_lib.npz]
```

### door_match.py
弧候選鉸鏈四象限窗 × 模板對稱 chamfer 重評分：命中（≤1.5，真門中位 1.02 vs 非門 2.16）把 `score_fused` 保底到 0.90，絕不降分；原 `score` 不動。

```bash
python scripts/door_match.py [名 ...]        # 預設掃 training/json/gray 全部
```

### door_propose.py
門位 zone 提名器：跑偵測（不切房間）＋ `build_rooms` 取 zones，去重後以 `score_fused=0.88`、`src="zone"` 追加進 doors。模板對 zone 真假無區分力（門扇窗被牆線污染），故不摻模板分數。**先 door_match 再 door_propose**（提名對已入選候選去重）。

```bash
python scripts/door_propose.py [名 ...]
```

### eval_door_match.py
A/B 評分器：GT = testdata/Identify_ans/own_dataset 26 題人工校正 Door quad；比 `score` 與 `score_fused` 兩種門檻策略的 P/R。

```bash
python scripts/eval_door_match.py [--thr 0.85] [--tol 12]
```
