# 路線圖 B：符號模板庫 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use the Execute Plan phase of
> superpowers:sunnydata-design to implement this plan task-by-task.

**Goal:** 從 train 樣本的 FixedFurniture 向量線稿建符號模板庫，Hu＋chamfer 兩階段比對作為與手寫幾何規則並行的證據，救回指名盲區。

**Architecture:** `extract_symbol_lib.py`（一次性建庫 → symbol_lib.npz）＋`symbol_match.py`（比對純函式）；`floorplan2room.detect_symbols` 尾端聯集模板命中（庫缺失＝零行為變化）；`classify_rooms_cc` 加 shower/sink 兩個保守權重。

**Tech Stack:** 既有 .venv（cv2/numpy/svgpathtools/pytest），不需 torch

**對齊 spec:** docs/superpowers/specs/2026-07-15-symbol-lib-design.md

## 原型已驗證的事實（程式碼直接引用）

- 目標節點可見繪圖元素只有四種：`rect / path / polygon / circle`
- 細節不只在 InnerPolygon（爐台燃燒圈在 OuterCircle 群的 `<circle>`）→
  渲染=遞迴走訪，排除 `display: none`（Direction/Name）與 `fill=none stroke=none`
  （隱形 BoundaryPolygon）
- local 座標即標準方向；Toilet/Shower 渲染品質已目測確認
- IntegratedStove class 是三 token，判定用 token 集合

## 檔案結構

- Create: `extract_symbol_lib.py`（建庫工具）
- Create: `symbol_match.py`（渲染共用函式＋比對）
- Create: `tests/test_symbol_match.py`
- Modify: `floorplan2room.py`（detect_symbols 尾端 ~8 行；classify_rooms_cc ~6 行）
- Output: `symbol_lib.npz`（進版控）

### Task 1: 渲染與比對純函式＋測試（RED→GREEN）

`symbol_match.py` 核心（供建庫與比對共用）：

```python
CANVAS = 48
TARGETS = {"Toilet": "oval", "Bathtub": "tubrect", "BathtubRound": "tubrect",
           "IntegratedStove": "stove", "Sink": "sinkicon", "Shower": "shower"}

def collect_primitives(e):  # 遞迴走訪，回傳 [np.ndarray 折線]
def render_polylines(polys, canvas=CANVAS):  # 正規化置中 → uint8 raster
def hu_of(raster):  # 最大外輪廓 log-Hu (7,)
def hu_dist(hu_a, hu_b):  # cv2.matchShapes I1 等價：sum |1/a - 1/b|
def chamfer_score(cand_raster, tpl_raster):  # 距離變換平均邊緣距離(px)
def match_symbols(det, lib):  # 細線層候選 → [(kind, cx, cy)]
```

測試（先寫先跑 FAIL）：合成 minidom 片段（rect+circle）渲染非空且含圓；
同 raster 自比對 hu_dist≈0、chamfer≈0；馬桶形 vs 四圈爐台形距離 > 同類距離 5 倍。

### Task 2: extract_symbol_lib.py 建庫

- train.txt 全 4200 樣本 × 6 類 token；per-symbol：collect_primitives（local 座標，
  不套 transform）→ render_polylines → 48×48
- 去重：(label, raster bytes) 相同者合併並計數；記 wh（BoundaryPolygon 尺寸）
- 存 npz：rasters/hu/labels/wh/count；終端印每類「總數→變體數」
- Run: `.venv/bin/python extract_symbol_lib.py` → symbol_lib.npz
- 抽查：每類前 8 個變體拼圖輸出 scratchpad 目測

### Task 3: 比對接入 floorplan2room

- `match_symbols`：thin 層輪廓（len≥20）→ bbox 實體尺寸落在該類 wh 分佈
  P5~P95×cm（±20%）才算候選 → Hu 預篩（HU_THR=0.15 起步）→ 候選 crop
  正規化 48×48 chamfer 驗證（CH_THR=2.0px 起步）→ 命中取最近類
- `detect_symbols` 尾端：`syms += match_symbols(det, _load_lib())`（模組級
  lazy load，檔案不存在回 None → 不比對）；沿用既有同 kind 20cm 去重
- `classify_rooms_cc`：n 增加 "shower"/"sinkicon"；shower→score["bath"]+=0.3；
  sinkicon 且非 open_living→score["kitchen"]+=0.15
- pytest 全綠後 commit

### Task 4: 43 題回歸關（硬性）

- 批次：`.venv/bin/python floorplan2room.py png/ <scratch>/reg_room`（json 輸出
  到 json/，跑完 `git diff json/` 逐房比對 label）
- **硬性關卡**：版控 json 中已命名（label != room/空間）的房間零丟失、零改名
  （改名視同回歸，除非肉眼確認新名正確）
- 攻擊目標驗收：floor44 出現 stove/廚房；floor13/15/34/35/46 ≥1 命名房
- 未達標 → 調 HU_THR/CH_THR 迭代（放寬救回 vs 誤報，以回歸關為界）；
  結果如實記錄
- 回歸乾淨後 commit（含 json/ 若有合法新增命名）

### Task 5: gt-seg 評分驗證＋收尾

- `.venv/bin/python eval_rooms_cc.py --gt-seg`（分鐘級）→ 對比
  report_gtseg.json：space precision 不得下降；混淆矩陣變化記錄
- README v2.8 章節（建庫統計/回歸結果/評分對比）＋路線 B 條目更新
- 最終 commit

## Plan Self-Review

- spec 覆蓋：五類 ✓、train-only ✓、並行聯集 ✓、兩階段比對 ✓、三道驗證 ✓
- 介面一致：match_symbols 回傳 [(kind,cx,cy)] 與 detect_symbols/classify 相容 ✓
- 無占位符；門檻值為起步值，校準迴圈在 Task 4 明定
