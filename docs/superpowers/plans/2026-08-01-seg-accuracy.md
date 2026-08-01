# 灰階切割層調優實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use the Execute Plan phase of
> superpowers:sunnydata-design to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** own_eval 保留集切割命中率 76.4% → ≥95%（≥69/72），純幾何路線。

**Architecture:** 量測驅動迭代——先在 own_dataset 25 題開發集上建基線與
歸因表，依失誤類別逐輪修 `segment_rooms()`／`_wall_gaps()`／
`_merge_nondoor_bridges()`，每輪 A/B 對照淨正向才收，保留集只在收尾驗證。

**Tech Stack:** Python + OpenCV（純幾何）、pytest、既有量尺
`training/scripts/eval_rooms_cc.py`。

**Spec:** `docs/superpowers/specs/2026-08-01-seg-accuracy-design.md`

本計畫與一般功能計畫不同：階段二的具體程式變更**由階段一的歸因表決定**，
無法預先寫死。因此階段二定義的是每輪迭代的固定協定（步驟、命令、收斂
判準），協定本身是完整可執行的。

---

### Task 1: 開發集基線量測

**Files:**
- 產出: `temp/json/eval_rooms/report_own_own_dataset_segbase.json`（不進版控）
- 產出: `temp/eval_rooms/chk/*_pred.png`／`*_gt.png` 逐案疊圖

- [ ] **Step 1: 跑 own_dataset 25 題完整管線量尺**

```
.venv/Scripts/python.exe training/scripts/eval_rooms_cc.py \
    --own-dir testdata/Identify_ans/own_dataset --report-suffix segbase
```

Expected: 25 張全數評分，報表落在上述路徑，終端印出切割命中率與混淆矩陣。

- [ ] **Step 2: 記錄基線**

從報表 summary 抄錄：`gt_rooms`、`matched`、`hit_rate`、`mean_iou`、
`overseg`。此為後續所有 A/B 的對照基準。

### Task 2: 歸因分析

**Files:**
- Create: `docs/superpowers/plans/2026-08-01-seg-attribution.md`（歸因表，進版控）

- [ ] **Step 1: 列出全部切割失誤案例**

從報表 `images[]` 取 `n_match < n_gt` 或 `n_pred > n_gt` 的圖，逐案列出
未配對的 GT 房（房型、bbox）與多餘的預測房。

- [ ] **Step 2: 逐案看疊圖歸因**

對每個失誤案例，比對 `chk/<id>_pred.png` 與 `chk/<id>_gt.png`（必要時
重跑單圖或加臨時 debug 輸出），歸入下列類別之一並記下具體原因：

| 類別 | 定義 | 對應機制 |
| :--- | :--- | :--- |
| A. 鄰房誤併 | 開口未封，兩間 GT 房連成一塊 | `_wall_gaps` 封口範圍/條件 |
| B. 過切 | 假封口把一間房切成多塊 | 封口誤判、`_merge_nondoor_bridges` 未合併 |
| C. 低 IoU 落榜 | 有配對意圖但 IoU<0.5 | 牆厚侵蝕、bbox 偏移、閉運算變形 |
| D. 整間漏偵測 | 預測完全沒有這塊區域 | 灌水內外判定、外圍開放空間 |
| E. 圖面本質難點 | 無牆可封的開放式空間等 | 純幾何救不到，如實記錄 |

- [ ] **Step 3: 寫歸因表並提交**

歸因表格式：每列＝一個失誤（圖號、GT 房型、類別、具體原因、修復假設、
預估救回數）。按「同一原因可救回的房間數」排序，決定階段二的攻堅順序。

```
git add docs/superpowers/plans/2026-08-01-seg-attribution.md
git commit  # docs(eval): own_dataset 切割失誤歸因表
```

- [ ] **Step 4: 對照目標可行性**

若類別 E（本質難點）在開發集占比推估到保留集後使 95% 不可達，
**停下**，帶證據向使用者重談目標或路線（spec 的安全閥條款）。

### Task 3..N: 修復迭代（每輪一類失誤，依歸因表順序）

每輪嚴格走以下協定，一輪一 commit：

- [ ] **Step 1: 從歸因表取當前最高救回數的假設**，在歸因表該列標記「進行中」

- [ ] **Step 2: 先寫釘住測試（TDD）**

若修復是離散行為（新封口條件、新合併規則），在 `training/tests/` 對應
測試檔加案例，先跑確認**紅**：

```
.venv/Scripts/python.exe -m pytest training/tests/<對應測試檔> -q
```

若修復是連續參數調整（範圍閾值），以量尺 A/B 代替單元測試紅綠，
但既有測試仍須全綠。

- [ ] **Step 3: 實作最小變更**

只動 `floorplan2dxf_color.py`（`segment_rooms`/`_wall_gaps`/
`classify_rooms` 不碰命名部分）或 `floorplan2room.py`
（`_merge_nondoor_bridges`/`build_rooms`），單輪 diff 儘量小。

- [ ] **Step 4: 開發集 A/B**

```
.venv/Scripts/python.exe training/scripts/eval_rooms_cc.py \
    --own-dir testdata/Identify_ans/own_dataset --report-suffix segfix<N>
```

收斂判準（全部滿足才收）：
- 切割命中數淨增（目標案例救回、無新破壞或破壞數＜救回數）
- `mean_iou` 不低於基線 −0.005
- 命名層（配對房間的叫名正確數）無淨退步

- [ ] **Step 5: 全測試綠**

```
.venv/Scripts/python.exe -m pytest training/tests -q
```

Expected: 121+ 全數通過（新增釘住測試計入）。

- [ ] **Step 6: 彩色管線回歸**（改動觸及共用碼時必跑）

```
.venv/Scripts/python.exe training/scripts/eval_color_walls.py
```

Expected: 牆/窗量測數字與現況持平。

- [ ] **Step 7: 收或退**

淨正向 → 更新歸因表該列為「已修」→ commit（WHY/WHAT/IMPACT，附 A/B
數字）。未達判準 → `git checkout` 還原，歸因表記錄失敗假設與數據，
換下一個假設。**失敗的嘗試也要留紀錄**，避免重複踩坑。

- [ ] **Step 8: 迭代終止條件**

歸因表可修項目全數處理完，或連續兩個假設 A/B 皆淨負向且無新假設
——進 Task N+1。

### Task N+1: 收尾驗證

- [ ] **Step 1: 保留集最終驗證（整輪只跑這一次計分）**

```
.venv/Scripts/python.exe training/scripts/eval_rooms_cc.py \
    --own-eval --report-suffix segfinal
```

Expected: 切割命中 ≥69/72（95%）。未達 → 帶開發集/保留集落差數據
回報使用者，不回頭用保留集調參。

- [ ] **Step 2: 全測試綠 + 彩色回歸最終確認**

- [ ] **Step 3: Readme 更新**

常駐章節「切割」與「已知待辦」改寫現況數字，changelog 加新版號段落
（含歸因表摘要、各輪 A/B 數字表、失敗嘗試記錄）。

- [ ] **Step 4: 最終 commit + push**
