# 路線圖 B：符號模板庫（extract_symbol_lib.py ＋ 模板比對證據層）設計

- 日期：2026-07-15
- 目標：從 CubiCasa5k model.svg 的 FixedFurniture 向量繪製萃取真實符號變體，
  以形狀比對（Hu moments 預篩＋chamfer 驗證）作為**與手寫幾何規則並行**的
  新證據來源——目標救回 X 圈爐台（floor44）與 5 張全空間圖（floor13/15/34/35/46）。

## 使用者決策（已確認）

- **並行互補**（非全面取代）：手寫規則不動；模板比對只補漏網，同類 20cm 內去重聯集
- **五類**：Toilet(5317)、IntegratedStove(3468)、Bathtub(395+6 Round)、
  Sink(5771)、Shower(4582)

## 關鍵事實（探索結論）

- FixedFurniture `<g>` 含 BoundaryPolygon（外框）＋ InnerPolygon（真實線稿：
  rect/polygon/path 貝茲）＋ transform 矩陣。**取 local 座標（不套 transform）
  即得標準方向的線稿**——不含牆線/文字污染，比裁圖乾淨
- IntegratedStove 的 class 是三 token（`FixedFurniture ElectricalAppliance
  IntegratedStove`）——類別判定用 token 集合比對，不能只看第二個 token
- 現行 detect_symbols 回傳 `[(kind, cx, cy)]`；classify_rooms_cc 第 4 層吃
  oval/tubrect/bedrect/stove 四種 kind

## 範圍

- 新增 `extract_symbol_lib.py`（萃取工具，一次性執行）＋ `symbol_lib.npz`（模板庫，進版控）
- 新增 `symbol_match.py`（比對模組，純函式為主）
- `floorplan2room.py` 最小修改：detect_symbols 之後聯集 match_symbols 結果
  （庫檔缺失＝行為完全不變，同 cc 快取模式）；classify_rooms_cc 增加
  shower/sink 兩個小權重證據（詳下）
- 不動：牆偵測、分割、比例尺、既有四種 kind 的計分權重

## 萃取（extract_symbol_lib.py）

- 樣本來源：**train.txt 全部 4200 樣本**（三子集皆用；val/test 完全不碰——
  評分集衛生與路線 A 一致）
- 每個目標類別的 `<g>`：
  - 渲染 InnerPolygon 子節點於 local 座標：rect/polygon → cv2.polylines；
    path → svgpathtools.parse_path 均勻取樣 ~100 點成折線；線寬 1px 白底黑線
  - 畫布 = BoundaryPolygon 尺寸，渲染後等比縮放置中到 48×48（留 2px 邊）
  - 記錄：class、W/H（svg 單位，供長寬比統計）、48×48 raster、
    最大外輪廓的 log-Hu 向量（7 維）
- 去重：同 class 且 raster 完全相同（bytes 相等）只留一份；預期數千 → 數百變體/類
- 輸出 `symbol_lib.npz`：rasters(N,48,48) uint8、hu(N,7) float32、
  labels(N) str、wh(N,2) float32；附建庫統計輸出到終端
- 萃取失敗的個體（空 InnerPolygon、退化路徑）跳過並計數回報

## 比對（symbol_match.py → floorplan2room 掛載）

- 候選：與 detect_symbols 同一細線層輪廓（len≥20），尺寸閘門用**類別長寬
  分佈的 cm 換算範圍**（由庫的 wh 統計 P5~P95 ＋ det["cm"]；物理常數守門，
  與現行風格一致）
- 兩階段：
  1. Hu 預篩：cv2.matchShapes(I1) 對庫內同類全部模板取最小距離，< HU_THR 進下一階
  2. chamfer 驗證：候選輪廓 crop 正規化 48×48，對模板 raster 的距離變換取平均
     邊緣距離，< CH_THR 才判命中（兩門檻以 43 題回歸集校準，起步保守）
- kind 映射（前三類零計分修改）：Toilet→`oval`、Bathtub→`tubrect`、
  IntegratedStove→`stove`；新 kind：Shower→`shower`（bath +0.3）、
  Sink→`sinkicon`（open_living 除外時 kitchen +0.15）——權重保守起步，
  由 gt-seg 評分驗證不傷 space precision
- 聯集去重：沿用現行「同 kind 20cm 內去重」；模板命中另記
  `r["symbols"]["tpl_*"]` 供 json 追溯

## 驗證

1. 單元測試（pytest）：渲染合成 SVG 片段（rect+path）產出非空 raster；
   模板對自身 matchShapes≈0；跨類（toilet vs stove）距離顯著大於同類
2. **43 題回歸關**：批次跑 floorplan2room，逐房比對版控 json 的 label——
   現有命名**零丟失**為硬性關卡；floor44 爐台/廚房、floor13/15/34/35/46
   出現 ≥1 命名房為目標（不達標記錄原因，不硬調）
3. gt-seg 評分重跑（分鐘級）：space precision 不得下降（新證據不能亂命名空房）

## 依賴

- 全部已在 .venv（svgpathtools/cv2/numpy/pytest）；不需 torch
