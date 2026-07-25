# 模組規格與測試案例 - RoomPilot-Agent 核心模組

> **版本:** v1.0 | **更新:** 2026-07-25 | **狀態:** 草稿

**對應架構文件**: [./05_architecture_and_design_document.md](./05_architecture_and_design_document.md)
**對應 BDD Feature**: [./03_behavior_driven_development_guide.md](./03_behavior_driven_development_guide.md)

---

## 文件範圍與測試策略總述

本文件為 RoomPilot-Agent 挑選 5 個核心模組/函式撰寫契約式設計（DbC）規格與測試案例：

| # | 模組 / 函式 | 位置 | 現有自動化測試 |
| :- | :--- | :--- | :--- |
| 1 | 權重供應鏈 `_ensure_cc_weights` | `floorplan2room.py:336`（含 `_resolve_weights_url`:312、`_gh_token`:289） | `tests/test_cc_weights_download.py`（7 例，全 mock 網路） |
| 2 | 房間切割 `segment_rooms` | `scripts/floorplan2dxf_color.py:1098`（呼叫端 `build_rooms`＝`floorplan2room.py:476`） | 無單元測試；由 `scripts/eval_rooms_cc.py` 評測守門 |
| 3 | 辨識式房型命名 `classify_rooms_cc` | `floorplan2room.py:382` | 無單元測試；由 `eval_rooms_cc.py --gt-seg` 解耦評測守門 |
| 4 | 評分 harness `eval_rooms_cc`（`match_rooms`/`norm_label`/`confusion`） | `scripts/eval_rooms_cc.py` | `tests/test_eval_rooms_cc.py`（5 例）＋`tests/test_eval_rooms_own.py`（8 例） |
| 5 | 窗偵測 `detect_windows` 與評分 `eval_windows` | 灰階 `scripts/floorplan2dxf.py:436`（凍結）；彩色 `scripts/floorplan2dxf_color.py:500`；評分 `scripts/eval_windows.py` | 無單元測試；由 `eval_windows.py` 對 `Identify_ans/pngans/` 評分守門 |

**測試策略的專案現實**：本專案是影像管線，核心邏輯（切割、窗偵測、房型投票）的正確性無法用少量合成輸入斷言——真正的品質閘門是**評測 harness 對人工標注 GT 的跑分**（`.claude/rules/` 評測鐵律：改 chk/dxf 邏輯前必先跑 `eval_windows.py` 對 `pngans/` 評分，不得退化後覆蓋）。因此本文件對每個模組同時列出：

- **單元層 TC**：可用 pytest＋合成輸入驗證的契約（已存在的引用真實測試函式名；建議新增的標「建議新增」）
- **評測層 TC**：以真實資料集跑分的回歸門檻（引用 2026-07-25 v2.16 現況數字）

`.claude/rules/testing.md` 要求 80% 覆蓋率；本專案現況為 6 個 pytest 檔（`tests/conftest.py`、`test_cc_weights_download.py`、`test_eval_rooms_cc.py`、`test_eval_rooms_own.py`、`test_symbol_match.py`、`test_annotation_drafts.py`）＋評測 harness 補位，逐行覆蓋率未量測（待確認），以「評分不得退化」作為等效閘門。

執行方式：

```bash
python -m pytest tests/ -v                       # 單元層（無網路、無 GPU、無權重檔需求）
python scripts/eval_windows.py                   # 窗偵測評分（灰階，預設 pngans/gray）
python scripts/eval_rooms_cc.py --own-eval       # 房型評分（own_eval 12 題保留集）
```

---

## 模組 1: 權重供應鏈（floorplan2room）

### 規格: `_ensure_cc_weights()`

**描述**: CubiCasa 微調權重 `model_finetuned_v5.pkl`（約 200MB，不進版控）缺檔時，自動從 GitHub Release（tag `weights-v5`）下載並做 SHA-256 校驗。公開 repo 走直鏈；私有 repo 以 token 向 asset API 換 S3 簽名鏈。使用者以 `CC_WEIGHTS` 環境變數明確指定的權重**缺了就報錯，不代抓**（避免默默換檔造成 A/B 驗收失真）。

**契約式設計 (DbC)**:

| 類型 | 條件 |
| :--- | :--- |
| **前置條件** | 1. 模組常數 `CC_WEIGHTS`（目標路徑）、`CC_WEIGHTS_SHA256`（`b7a280d2…f4cf`）、`CC_WEIGHTS_URL`、`CC_WEIGHTS_ASSET_API` 已定義 2. 呼叫時不需網路——無管道時函式自行降級回傳 `False` |
| **後置條件** | 1. 回傳 `True` ⟺ `CC_WEIGHTS` 路徑存在檔案，且（若經下載）其 SHA-256 等於 `CC_WEIGHTS_SHA256` 2. 回傳 `False` 時不留任何部分下載殘檔（`*.part` 必被清除） 3. 校驗失敗的下載內容**絕不**落地成正式檔名 4. 環境變數 `CC_WEIGHTS` 有設定且檔案缺失 → 直接 `False`，全程零網路請求 |
| **不變性** | 1. 永不拋出例外——所有失敗路徑印警告後回傳 `False`，由呼叫端 `ensure_cc_masks()` 降級為「房型退回面積規則」 2. 下載採 temp-then-rename（`.part` → `os.replace`），正式檔名要嘛不存在、要嘛完整且校驗通過 3. 不修改環境變數與任何全域狀態 |

### 測試案例（`tests/test_cc_weights_download.py`，7 例全數存在、全 mock 網路）

#### TC-101: 快取命中短路（`test_existing_file_short_circuits`）

- **Arrange**: `tmp_path` 下建立權重檔；monkeypatch `urllib.request.urlretrieve` 為一觸即 `AssertionError("不應下載")`
- **Act**: `fp._ensure_cc_weights()`
- **Assert**: 回傳 `True`；下載函式未被呼叫（否則 AssertionError 炸出）

#### TC-102: 使用者覆寫不代抓（`test_user_override_never_downloads`）

- **Arrange**: 設 `CC_WEIGHTS` 環境變數指向不存在的 `custom.pkl`；urlretrieve 同樣裝雷
- **Act**: `fp._ensure_cc_weights()`
- **Assert**: 回傳 `False`；零下載嘗試（覆寫權重缺失應報錯而非默默換檔）

#### TC-103: SHA-256 校驗失敗拒收（`test_checksum_mismatch_rejected`）

- **Arrange**: 期望雜湊設為 `sha256(b"expected")`；假下載器實際寫入 `b"tampered"`
- **Act**: `fp._ensure_cc_weights()`
- **Assert**: 回傳 `False`；正式檔 `w.pkl` 不存在；`w.pkl.part` 殘檔已清除

#### TC-104: 下載成功落地（`test_download_success`）

- **Arrange**: 期望雜湊＝`sha256(payload)`；假下載器寫入 `payload`
- **Act**: `fp._ensure_cc_weights()`
- **Assert**: 回傳 `True`；`w.pkl` 內容位元組級等於 `payload`；無 `.part` 殘留

#### TC-105: 下載中斷清理（`test_download_error_cleans_up`）

- **Arrange**: 假下載器先寫入 `b"partial"` 再 `raise OSError("網路中斷")`
- **Act**: `fp._ensure_cc_weights()`
- **Assert**: 回傳 `False`（例外被吞、不外拋）；`.part` 殘檔已清除

#### TC-106: 無下載管道明確失敗（`test_no_channel_returns_false`）

- **Arrange**: `_resolve_weights_url` monkeypatch 為回傳 `None`（模擬私有 repo 且無 token）；urlretrieve 裝雷
- **Act**: `fp._ensure_cc_weights()`
- **Assert**: 回傳 `False`；零下載嘗試

#### TC-107: token 解析優先序（`test_gh_token_env_priority`）

- **Arrange**: 設 `GITHUB_TOKEN=tok-env`
- **Act**: `fp._gh_token()`
- **Assert**: 回傳 `"tok-env"`（環境變數優先於 `git credential fill`；token 是密碼等級秘密，僅存在環境變數/git 憑證系統，勿進版控——見 `.claude/rules/security.md`）

---

## 模組 2: 房間切割（floorplan2dxf_color）

### 規格: `segment_rooms(rects, wins, doors, img_w, img_h, T, T_out, cm=1.0)`

**描述**: 把牆方塊圍出的內部切成一間間空間。流程：牆＋窗＋門洞畫實 → `_wall_gaps` 對 40~260cm 牆縫精準封口 → 閉運算封小縫（封口核 g∈{1.5, 2.5, 3.5, 4.5}×T 逐輪放大）→ 影像邊界灌水（floodFill）分內外 → 室內扣牆取連通塊＝房間。每輪以「覆蓋率(粗齒)、房間數、-g」為分數，取覆蓋合格中分割最細者——大核會把窄房間/走道填掉。

**契約式設計 (DbC)**:

| 類型 | 條件 |
| :--- | :--- |
| **前置條件** | 1. `rects` 為牆方塊清單 `[(x0,y0,x1,y1)]`（像素座標，x0≤x1、y0≤y1）；`wins` 為 `[(orient,x0,y0,x1,y1)]`；`doors` 為門弧 tuple（含圓心/半徑） 2. `T`＝牆厚（px）、`T_out`＝外牆厚、`cm`＝cm/px 比例尺，皆 > 0 3. `img_w`、`img_h` 與偵測來源影像一致 |
| **後置條件** | 1. 成功回傳 `(labels, rooms, outside)`：`labels` 為 `int32` 影像（0=非房間，i=第 i 間）、`rooms` 每項含 `id/area_px/bbox/cx/cy/aspect/touch_env`、`outside` 為建物外遮罩 2. 每間房面積 ≥ `max(0.003×牆bbox面積, 2×(2T)²)`（走道/玄關保留下限） 3. 驗收條件：房間總面積 ≥ 30% 牆 bbox 面積，且房間聯集跨幅 ≥ 55% bbox 寬與高——否則視為殼漏水，換下一輪封口核 4. 全部輪次皆不合格或 `rects` 為空 → 回傳 `(None, [], None)`，**不拋例外** 5. `rooms[i]["id"]` 與 `labels` 像素值一一對應且從 1 起連號 |
| **不變性** | 1. 不修改輸入 `rects/wins/doors`（僅讀取） 2. 房間連通塊彼此不重疊（`labels` 單值指派保證） 3. 「室中央的假門弧」（距最近牆 > 3T）不參與封口——家具/爐台弧線畫進去會把房間切碎 |

### 測試案例

#### TC-201: 正常路徑——田字四房（建議新增）

- **Arrange**: 合成 400×400 影像的牆 rects：外框四面牆＋十字內牆（T=10），無窗無門
- **Act**: `segment_rooms(rects, [], [], 400, 400, 10, 10, cm=1.0)`
- **Assert**: `rooms` 恰 4 間 / 各房 `bbox` 互不重疊 / `labels` 最大值 = 4 / 每間 `touch_env` 為 True（皆貼外框）

#### TC-202: 邊界情況——門洞封口後房間才分開（建議新增）

- **Arrange**: 兩房共用一道有 90px 缺口的內牆（缺口換算 90cm，落在 `_wall_gaps` 的 40~260cm 封口區間）
- **Act**: 執行切割
- **Assert**: 回傳 2 間房而非 1 間（缺口被 `_wall_gaps` 精準封口，而非靠大核閉運算）

#### TC-203: 無效輸入——空牆清單

- **Arrange**: `rects=[]`
- **Act**: `segment_rooms([], [], [], 100, 100, 5, 5)`
- **Assert**: 回傳 `(None, [], None)`；不拋例外（呼叫端 `build_rooms` 以 `labels is None` 分支處理，印「⚠ 無語意快取…」以外的降級訊息由上層決定）

#### TC-204: 業務規則——殼漏水換核不硬給（建議新增）

- **Arrange**: 外框留一個 300px 大破口（超出 260cm 封口上限，最大封口核 4.5T 也封不住）
- **Act**: 執行切割
- **Assert**: 灌水從破口漏進室內 → 覆蓋率驗收不過 → 回傳 `(None, [], None)`，而非把外部誤標成一間巨大房間

#### TC-205: 評測層回歸門檻（現行閘門）

- **Arrange**: `scripts/eval_rooms_cc.py`（CubiCasa `high_quality_architectural` val/test 樣本＋`--own-eval` 12 題保留集）
- **Act**: `python scripts/eval_rooms_cc.py`；報表落在 `json/eval_rooms/report*.json`
- **Assert**: 切割命中不得低於現況 **72.6%（53/73，配對 IoU 0.829）**；端對端 76.4%、IoU 0.875（v2.16，2026-07-25）。退化即擋 merge

---

## 模組 3: 辨識式房型命名（floorplan2room）

### 規格: `classify_rooms_cc(det, labels, rooms, cc_file)`

**描述**: user spec「放棄面積規則」——每個房間方塊切出來，以多層證據投票命名用途：(1) CubiCasa 語意像素佔比 (2) 已分類像素內相對多數票（typed≥0.05 時給 +0.12 加權）(3) 設備圖示絕對面積 cm²（馬桶≥150→浴室+0.5、浴缸≥500→+0.5、爐具+水槽→廚房、整間櫃密度≥8%→儲藏；設備尺寸是物理常數，不被大房間稀釋）(4) 古典符號模板證據（橢圓=馬桶/洗手台、床矩形、爐台燃燒圈等）。開放式客廳（客廳票≥0.15 且 >2×廚房票）不給廚房圖示加分。總分最高者勝；證據太弱（<0.15）標中性「空間」。

**契約式設計 (DbC)**:

| 類型 | 條件 |
| :--- | :--- |
| **前置條件** | 1. `cc_file` 為含 `room`、`icon` 兩通道的 `.npz`（呼叫端以 `_cc_ok()` 守門；舊版快取缺 `room` 通道會被判定重推） 2. `labels`/`rooms` 來自 `segment_rooms`（或 `--gt-seg` 模式的 GT 多邊形） 3. `det["cm"]` 比例尺已由 `refine_scale` 校正（門寬鐵律：單門 85cm/雙門 175cm/牆厚 17.5cm） |
| **後置條件** | 1. 每個 `room` dict 被**就地**補上：`label`（10 類之一或 `"room"`）、`label_zh`、`area_m2`、`cc_share`（≥0.02 的得分明細）、`icons_cm2`（≥20cm² 的圖示面積）、`symbols`（命中的古典符號計數） 2. `label ≠ "room"` ⟺ 最高分 ≥ 0.15 3. `label` ∈ `ROOM_ZH_EX` 鍵集合（kitchen/living/bed/bath/entry/storage/garage/outdoor/…＋room） |
| **不變性** | 1. 不修改 `labels` 影像與 `det` 偵測結果 2. `cc_room` 尺寸與 `labels` 不符時（彩圖管線可能放大 2 倍）以 `INTER_NEAREST` 縮放對齊，不改語意類別值 3. 桑拿椅圖示只記錄不採證（芬蘭訓練集特有，美式圖全是誤報） |

**注意**：本函式是就地修改 `rooms`（管線效能考量），與 `.claude/rules/coding-style.md` 不可變性原則衝突之處為既有設計債，重構時再議——新程式碼仍應遵守不可變原則。

### 測試案例

#### TC-301: 正常路徑——語意佔比壓倒性（建議新增）

- **Arrange**: 合成 npz：`room` 通道在房間 1 範圍 95% 像素標臥室類；`labels` 單一房間；空 `icon` 通道
- **Act**: `classify_rooms_cc(det, labels, rooms, cc_file)`
- **Assert**: `rooms[0]["label"] == "bed"` / `label_zh == "臥室"` / `cc_share["bed"] ≥ 0.9`

#### TC-302: 邊界情況——證據太弱標中性（建議新增）

- **Arrange**: `room` 通道全「未定義」、無圖示、無符號（線稿圖常態）
- **Act**: 執行命名
- **Assert**: `label == "room"`、`label_zh == ROOM_ZH_EX["room"]`（不硬猜房型）

#### TC-303: 業務規則——開放式客廳不被爐台翻盤（建議新增）

- **Arrange**: 客廳票 0.4、廚房票 0.1（滿足 votes[living]≥0.15 且 >2×votes[kitchen]），同房間放爐具圖示 ≥1200cm²
- **Act**: 執行命名
- **Assert**: `label == "living"`（客餐廚一體的大方塊命名為客廳，爐台水槽只是角落）

#### TC-304: 業務規則——馬桶鐵證（建議新增）

- **Arrange**: 語意票均弱（<0.1），`icon` 通道馬桶面積 200cm²（≥150 門檻）
- **Act**: 執行命名
- **Assert**: `score["bath"]` 獲 +0.5 → `label == "bath"`

#### TC-305: 評測層回歸門檻（現行閘門）

- **Arrange**: `python scripts/eval_rooms_cc.py --own-eval [--gt-seg]`；own_eval 12 題保留集**永不進訓練**
- **Act**: 跑分，報表 `json/eval_rooms/report_own*.json`
- **Assert**: v5 權重 own 尺具名命中不得低於 **0.788（52/66）**、具名 macro-F1 **0.473**（基線 0.215）；CubiCasa 尺 0.797。`--gt-seg` 模式解耦分割失敗，單評「0.15 門檻/圖示/符號權重」本身品質

---

## 模組 4: 評分 harness（eval_rooms_cc）

### 規格: `match_rooms(gt_masks, pred_masks, thr=0.5)`

**描述**: GT 房間遮罩 × 預測遮罩的 IoU 貪婪一對一配對——所有交集非零的 (gt, pred) 對按 IoU 由高到低排序，逐一鎖定未用過的雙方。評分公平性的地基：配對錯，混淆矩陣全錯。

**契約式設計 (DbC)**:

| 類型 | 條件 |
| :--- | :--- |
| **前置條件** | 1. `gt_masks`、`pred_masks` 為同尺寸 bool ndarray 清單 2. `0 < thr ≤ 1`（預設 0.5） |
| **後置條件** | 1. 回傳 `[(gi, pi, iou)]`，所有 `iou ≥ thr` 2. 每個 `gi` 與每個 `pi` 至多出現一次（一對一） 3. 貪婪最優先：IoU 較高的配對優先鎖定 |
| **不變性** | 1. 不修改輸入遮罩 2. 空輸入回傳空清單，不拋例外 |

### 規格: `norm_label(k)` 與 `confusion(pairs)`

**描述**: `norm_label` 把管線房型 key 正規化為評分 9 類（`CLASSES`）：`balcony`→`outdoor`、`room`/`None`/空字串→`space`；`confusion` 把配對後的 `[(gt_label, pred_label)]` 轉巢狀 dict 混淆矩陣。

| 類型 | 條件 |
| :--- | :--- |
| **前置條件** | `confusion` 輸入的 label 皆已經過 `norm_label`（∈ CLASSES 9 類） |
| **後置條件** | 1. `norm_label` 回傳值 ∈ `CLASSES` 2. 混淆矩陣 9×9 全鍵存在（含 0 計數），總和 = `len(pairs)` |
| **不變性** | 純函式，無副作用 |

### 測試案例（`tests/test_eval_rooms_cc.py` 5 例全數存在）

#### TC-401: 完全重疊配對（`test_match_perfect_overlap`）

- **Arrange**: GT 與預測遮罩完全相同
- **Act**: `match_rooms(gt, pred)`
- **Assert**: 配對成立且 IoU = 1.0

#### TC-402: 低於門檻剔除（`test_match_below_threshold_excluded`）

- **Arrange**: 交集面積使 IoU < 0.5
- **Act**: 以預設 `thr=0.5` 配對
- **Assert**: 回傳空清單（不硬配）

#### TC-403: 貪婪一對一（`test_match_greedy_one_to_one`）

- **Arrange**: 一個 GT 與兩個預測都有交集（IoU 一高一低）
- **Act**: 配對
- **Assert**: 只保留 IoU 較高者；GT 不被重複配對

#### TC-404: 房型正規化（`test_norm_label`）

- **Arrange / Act**: `norm_label` 分別餵 `None`、`""`、`"room"`、`"balcony"`、`"kitchen"`
- **Assert**: 前三者 → `"space"`；`"balcony"` → `"outdoor"`；`"kitchen"` 原樣通過

#### TC-405: 混淆矩陣計數（`test_confusion_counts`）

- **Arrange**: 已知的 (gt, pred) 配對清單
- **Act**: `confusion(pairs)`
- **Assert**: 對應格計數正確、其餘為 0、總和等於配對數

**補充**：`tests/test_eval_rooms_own.py`（8 例）另覆蓋 own_eval 保留集完整性（`test_pick_own_samples_twelve_complete`——12 題目錄/圖/標注缺漏即報錯不靜默跳過）、報表路徑組合（`test_report_path_for_all_modes`：`report[_own][_gtseg].json`）、SVG transform 烘焙與 `get_polygon` 尾空格陷阱（`test_all_annotation_polygons_have_trailing_space`，對應 Readme v2.15 House 相容陷阱）。

---

## 模組 5: 窗偵測與評分（floorplan2dxf / floorplan2dxf_color / eval_windows）

### 規格: `detect_windows(orig_bw, rects, cfg, T, doors=None, thin=None, soft=None)`

**描述**: 在牆的開口偵測窗。核心判準：開口長度被細線覆蓋 ≥ `win_cover_pct`（預設 70%）＝窗（玻璃線沿牆跨整段）；空的＝門/通道留開；落在偵測門附近＝門留開。線的結構還要「像窗」：≥2 群分開的貫穿線（玻璃畫法），或 1 條貫穿線＋≥2 條部分覆蓋線（梳齒窗）——推拉門（兩片各半、無貫穿線）與門檻線（孤零零一條）都被擋掉。淺灰玻璃線被 Otsu 消掉時，改用 `soft`（灰<200 寬鬆二值化）重測，但加嚴：≥2 群貫穿線、墨跡比例 ≤45%、必要時要求最外側線貼牆帶兩緣（`edge_hug`）。回傳 `[(orient, x0, y0, x1, y1)]`。

灰階版（`scripts/floorplan2dxf.py:436`）**已凍結不再修改**；彩色版（`scripts/floorplan2dxf_color.py:500`）為現行開發重點——彩窗召回 38% 是全系統最大缺口，調參方向為牆段配對 gap 與 covered 門檻的線寬適配（v2.16 待辦 #2）。

**契約式設計 (DbC)**:

| 類型 | 條件 |
| :--- | :--- |
| **前置條件** | 1. `orig_bw` 為二值化影像（0/255）；`soft` 可為 None（則跳過寬鬆重測） 2. `rects` 為牆方塊清單；`T` > 0 3. `cfg.win_cover_pct`、`cfg.win_min_pct` 已由 config.ini / config_color.ini 載入 |
| **後置條件** | 1. 回傳清單每項 `(orient, x0, y0, x1, y1)`，orient ∈ {"h","v"}（待確認：orient 具體編碼值，以 `write_json` 消費端為準） 2. 每個窗框落在牆的開口帶內，跨牆寬度 ≥ `(1 - win_min_pct/100) × 代表性牆厚`（代表性牆厚＝夠長真牆的中位數厚度） 3. 開口長度界於 `0.4T ~ 25T` 之外者不產出 |
| **不變性** | 1. 不修改 `orig_bw`/`rects`/`doors` 2. `cfg.windows=False` 時上游不呼叫本函式（產出零窗） 3. 偵測順序與輸出對 `rects` 排序穩定（同輸入同輸出，無隨機性） |

### 規格: `eval_windows.green_boxes(path, size=None)` 與 `matched(a, b)`

**描述**: 評分器從答案圖（`Identify_ans/pngans/*/*_ans.png`）與檢核圖（`training/chk/*/*_chk.png`）各抽「綠色框」再互相配對。綠色判準同時吃程式畫的 (0,170,0) 與小畫家綠 (34,177,76)：`g≥110 且 g−b≥45 且 g−r≥45`，5×5 膨脹把 2px 框線黏成一塊，面積 <30 px 視為雜點。`matched` 判兩框同窗：交集 ≥ 0.3×較小框面積，或任一框中心落在另一框內。一個答案框可由多個預測框共同覆蓋（算 1 個 TP 不重複計）。

| 類型 | 條件 |
| :--- | :--- |
| **前置條件** | 1. `path` 圖檔可讀（讀不到 `sys.exit`，屬 CLI 快速失敗設計） 2. `size=(w,h)` 時先縮放再抽框——彩色管線可能以 2 倍圖處理，chk 與答案圖尺寸不同 |
| **後置條件** | 1. `green_boxes` 回傳 `[(x0,y0,x1,y1)]`，皆為面積 ≥30 的連通塊 bbox 2. `matched` 為對稱判準（a,b 互換結果不變） 3. 總表輸出 TP/FP/FN 與精準率/召回率，FP/FN 附座標便於人工回看 |
| **不變性** | 純讀取，不寫入任何檔案 |

### 測試案例

#### TC-501: 正常路徑——標準雙線窗（建議新增）

- **Arrange**: 合成牆帶（T=10）中 100px 開口，開口內畫兩條貫穿全長的平行細線
- **Act**: `detect_windows(orig_bw, rects, cfg, T)`
- **Assert**: 產出恰 1 個窗框，且框覆蓋該開口範圍

#### TC-502: 邊界情況——推拉門不誤判為窗（建議新增）

- **Arrange**: 開口內畫兩片「各覆蓋一半、無貫穿線」的線段（推拉門畫法）
- **Act**: 執行偵測
- **Assert**: 產出零窗（`covered` 的 line_groups/partial 結構判準擋掉）

#### TC-503: 無效輸入——soft=None 時淺灰窗不強測（規格行為）

- **Arrange**: 玻璃線只存在寬鬆二值化中（orig_bw 上開口全空），呼叫時 `soft=None`
- **Act**: 執行偵測
- **Assert**: 不拋例外、該開口不產窗（`covered_soft` 首行 `soft is None → False`）——寧漏勿誤，符合「窗偵測保守原則」（density-based 改寫曾因誤報過多整批 revert）

#### TC-504: 評分配對規則（建議新增，直接測 `eval_windows.matched`）

- **Arrange**: (a) 兩框交集恰為較小框 30% (b) 交集 29% 但 a 中心落在 b 內 (c) 交集 29% 且中心互不包含
- **Act**: `matched(a, b)`
- **Assert**: (a) True / (b) True / (c) False；且 `matched(a,b) == matched(b,a)`

#### TC-505: 評測層回歸門檻（現行閘門，評測鐵律）

- **Arrange**: `python scripts/eval_windows.py`（灰階預設 `Identify_ans/pngans/gray` × `training/chk/gray`；彩色傳入對應目錄）
- **Act**: 對 38 張灰階＋29 張彩色 GT 跑分
- **Assert**: 灰窗不得低於 **96%/96%**（精準/召回）；彩窗現況 **P62/R38** 為待改善基線——任何彩色管線改動，彩窗分數只許升不許降，且**灰階分數不得因共用碼變動而退化**（灰階管線凍結）

---

## 不適用段落聲明（模板對映）

- **API/Service 類模組（如模板範例 ShoppingCartService）**: N/A——本專案無 Web 服務。對應物為上述 CLI 管線模組；跨模組契約以「函式簽名＋回傳 tuple/dict 結構＋JSON 報表 schema（`json/room/*_room.json`、`json/eval_rooms/report*.json`）」承擔，介面契約詳見 [./06_api_design_specification.md](./06_api_design_specification.md)。
- **BusinessRuleException 類例外設計**: N/A——管線模組的失敗約定是**結構化降級**而非拋例外：`segment_rooms` 失敗回 `(None, [], None)`、`_ensure_cc_weights` 失敗回 `False`、`eval_one` 失敗回 `{"status": "seg_fail"/"svg_mismatch"/…}`。唯一 fail-fast 的是資料完整性守門（`pick_own_samples` 對 own_eval 缺檔 `raise FileNotFoundError`——評分集缺題必須炸，不許靜默跳過）。
