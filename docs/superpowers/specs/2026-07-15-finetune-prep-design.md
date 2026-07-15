# 路線圖 C 準備：標注初稿產生器＋Colab 微調環境 設計

- 日期：2026-07-15
- 目標：C（微調 CubiCasa 模型）的兩項前置就緒——
  (1) 43 張 png/ 題目的 CubiCasa 格式標注初稿（管線輸出→人工修正）
  (2) Colab 微調 notebook＋資料打包腳本（免費 T4 可跑）

## 核心設計決策

**標注格式＝CubiCasa model.svg**（非 LabelMe）：FloorplanSVG loader 支援
`format='txt'`（樣本目錄現場解析 SVG），訓練端零改碼（僅 train.py 的
lmdb→txt 一行、notebook 內 sed）；junction heatmap 標注由 House 從 SVG
自動推導，不必手標；人工修正用 Inkscape 等任何 SVG 編輯器。

## 範圍

- 新增 `make_annotation_drafts.py`：png/ 43 張 → `own_dataset/<名>/`
  （F1_scaled.png 複本＋model.svg 草稿）＋ own_train.txt / own_val.txt
- 新增 `pack_finetune_data.py`：打包 finetune_data.zip
  （own_dataset ＋ hq_arch train 子集 ＋ 混合 txt 清單）
- 新增 `colab/finetune_cubicasa.ipynb`：環境→資料→微調→取回 checkpoint
- 不動管線程式碼；不在本機跑訓練（GPU 在 Colab）

## 標注初稿內容（單張，全部來自既有管線輸出）

| SVG 元素 | 來源 | 品質預期 |
| :--- | :--- | :--- |
| `<g id="Wall">` 4 點多邊形 | det["rects"] 牆矩形 | 高（IoU 83%+ 的偵測） |
| `<g id="Window">` / `<g id="Door">` | det["wins"] / det["doors"] | 高（99%/94%） |
| `<g class="Space <類>">` 房間多邊形 | labels 連通塊輪廓（approxPolyDP）＋房型映射 | 中（38% 有名，餘 Undefined 待人工） |
| `<g class="FixedFurniture <類>">` | detect_symbols 命中（oval→Toilet 等） | 低（草稿提示，人工補） |

- 房型映射（管線 label → CubiCasa class）：bed→Bedroom、bath→Bath、
  kitchen→Kitchen、living→LivingRoom、entry→Entry、storage→Storage、
  garage→Garage、outdoor→Outdoor、room/None→Undefined
- SVG 座標=圖像素（與資料集慣例一致，路線 A 已實證）；svg width/height
  寫圖面尺寸
- 產出後以 House() 解析回讀驗證（round-trip：能 load、牆/房間像素數>0）
  ——草稿保證訓練管線可直接吃

## Colab notebook（cell 級規劃）

1. GPU 檢查（T4）＋ clone CubiCasa5k ＋ pip 安裝（torch 已內建，補
   lmdb/svgpathtools/scikit-image/tensorboardX）
2. Drive 掛載，解壓 finetune_data.zip；基底權重 model_best_val_loss_var.pkl
   從 Drive 讀（使用者上傳一次）
3. sed train.py：format='lmdb'→'txt'（兩處）
4. 微調指令：`train.py --weights <基底> --data-path <合併資料> --new-hyperparams
   --l-rate 1e-4 --n-epoch 20 --batch-size 8 --image-size 256`（起步值，
   notebook 內以參數 cell 揭露可調）
5. checkpoint 存回 Drive；快速 sanity 推論（借 infer_cubicasa.py 邏輯對
   一張 own_dataset 圖出房間 argmax 疊圖目測）
6. 帶回本機後的驗收路徑寫在 notebook 尾註：權重換檔重跑
   `eval_rooms_cc.py --gt-seg` 對比 report_gtseg.json（路線 A 量尺）

## 資料配比（可調預設）

- hq_arch train 子集 300 樣本（防災難性遺忘）＋ own_dataset 43 張
  **×3 過採樣**（清單重複行；43:300 直混會被淹沒）
- own_val.txt：own 43 抽 5 張（僅訓練監控用；正式驗收仍走路線 A 的
  val/test 評分，own 樣本永不進那套）

## 驗證

1. pytest：房型映射完整性（管線 label 全集皆有映射）、SVG 草稿
   round-trip（House 解析回讀非空）
2. make_annotation_drafts 全量 43 張成功產出；抽 2 張 Inkscape 相容性
   （XML 合法、可開啟）以 xmllint/minidom 驗證
3. pack_finetune_data.py 產出 zip，內容清單與配比列印確認
4. notebook 本機不執行（無 GPU），以 nbformat 驗證 JSON 結構合法
