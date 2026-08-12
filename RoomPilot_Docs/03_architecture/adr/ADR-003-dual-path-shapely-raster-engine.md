# ADR-003: Shapely 與 raster 雙路徑並存的碰撞引擎 (Dual-Path Collision Engine) - RoomPilot

> **狀態:** 已接受（現況追認，待 owner 核准）｜ **日期:** 2026-08-12 ｜ **決策者:** MOD-ENG owner（Ancai）＋ MOD-SRV-SCENE owner（Bella，整合面）
> **語域:** L2（橋接）——業務詞與工程詞並列，跨層一律用穩定 ID
> **實例:** 每決策一份（`ADR-NNN-<slug>.md`）
>
> **本文件回答**：為什麼 `backend/engine/` 同時存在 Shapely 解析幾何與 5 cm 布林柵格兩條碰撞路徑、裁決權為何歸柵格、兩條路徑目前不一致在哪裡。
> **本文件不含**：引擎在系統中的位置與模組邊界（去 [`../sad.md`](../sad.md)）、「幾何合法性只歸引擎」這條上位決策（去 [`ADR-002`](ADR-002-engine-sole-geometry-authority.md)）、公分單位契約（去 [`ADR-007`](ADR-007-centimeter-unit-contract.md)）、擺位演算法逐步細節（去 [`../../04_design/lld.md`](../../04_design/lld.md)）、需求條文（去 [`../../01_requirements/srs.md`](../../01_requirements/srs.md)）。
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、工作樹日期 2026-08-12。行號隨程式碼演進，衝突時以原始碼為準。

---

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 執行計畫](#5-執行計畫)
- [6. 追溯](#6-追溯)

## 1. 背景與問題

- **上下文**：引擎 v0.1 是純 Shapely 解析幾何——家具與牆轉成旋轉多邊形做交集判斷（`engine/geometry.py:1-6,14-36`），合法性走七段固定順序、只回最先命中者（`engine/clearance.py:118-143`；順序表 `engine/README.md:40-52`）。其後依 `docs/擺位計算邏輯.md` §3 另建柵格路徑：房間環掃描線填充、牆／門窗線段以歐氏距離描粗成布林佔用網格（`engine/raster.py:70-98,100-127`），碰撞改為「格心反旋轉進 OBB 本地座標後查表」（`engine/obb.py:86-106`）。兩套資料模型是**明文並存**，不是過渡狀態（`engine/layout_model.py:1-5`）。
- **問題**：同一個落點，兩套可以給出不同答案。柵格出現前，房間邊界、門前動線與窗前採光帶的檢查分散在 Shapely 三處各自為政（`scene_service.py:1366-1370` 的收斂註解記錄了前身狀態），跨房、斜擺與成組家具的判定會互相打臉，違反 [`AGENTS.md`](../../../AGENTS.md)`:54`「家具合法位置只由 `backend/engine/` 判定」的單一權威意圖。
- **驅動因素／約束**：
  - Shapely 側已累積提議能力：中心向外擴散的 first-fit（`engine/placement.py:26-47`）、貼附主家具（`:72-112`）、地毯 overlay（`:50-69`），並有既有測試覆蓋（`tests/test_placement.py` 18 案、`tests/test_clearance.py` 10 案）。整組重寫成本高。
  - 柵格把房間環、門窗淨空、視聽走廊一次烘進遮罩，之後每次判定只是布林查表，且天然支援多房 MultiPolygon 聯集（`scene_service.py:1391-1394,1451-1462`）。
  - 精度是格徑的函數：格徑 5 cm、單軸最多 1200 格（超過即自動放大格徑）、牆線描粗 12 cm（`engine/raster.py:18-21,62`）→ NFR-015。
  - 兩套相依都已在依賴宣告中（`pyproject.toml:7-10`），移除任一套都是依賴層級的變更。

## 2. 考量的選項

### 2.1 選項一：全面沿用並擴充純 Shapely 解析幾何

- **描述**：在 v0.1 多邊形交集之上補門前動線、採光帶、多房聯集等規則，維持單一解析幾何實作。
- **優點**：單一機制；判定精確到浮點，無格徑量化誤差。
- **缺點**：淨空與動線規則逐條寫成多邊形運算，三段分散檢查已被實作端判定為難以維持一致（`scene_service.py:1366-1370`）；非矩形房、走道連通性與門扇開闔弧本來就是 v0.1 的未實作項（`engine/README.md:75-83`）。
- **成本／複雜度**：高。**未採用。**

### 2.2 選項二：整組改寫為純柵格、淘汰 Shapely

- **描述**：依 `docs/擺位計算邏輯.md` 全規格實作柵格擺位，`engine/geometry.py`、`engine/placement.py` 與 `engine/clearance.py` 一併退役。
- **優點**：只有一個事實源，提議與裁決同一組資料結構，本 ADR §4.2 的全部不一致自動消失。
- **缺點**：丟掉已驗證的提議能力（成組貼附、overlay、first-fit 掃描）；格徑 5 cm 的量化對「找最佳位置」是重寫而非移植；規格文件目前只寫規則擺位，未涵蓋提議搜尋。
- **成本／複雜度**：高。**未採用。**（此選項未見於 repo 任何文件，係由 `engine/layout_model.py:1-5` 的「並存」措辭反推的落選路線，標**推測**。）

### 2.3 選項三：並存分工——Shapely 提議、柵格裁決

- **描述**：Shapely 路徑產生候選座標，每個候選必須通過布林網格才算合法（`scene_service.py:2269-2286`，docstring 原句「Shapely 提議、柵格裁決」）；被否決時改走帶裁決回呼的網格散點掃描（`scene_service.py:1235-1282,2631-2640`）。
- **優點**：保留提議資產；裁決收斂為單一 `obb_blocked`；新紀律只需再疊一張遮罩。
- **缺點**：兩套型別、兩套座標與旋轉約定長期並存，維護者必須同時理解。
- **成本／複雜度**：中。**採用。**

## 3. 決策

**選擇**：選項三——雙路徑並存，**布林柵格是碰撞判定的最終裁決者**。

**理由**：`build_raster_context` 把房間環、門前 75 cm 動線與窗前 40 cm 採光帶全部烘進遮罩，取代原本分散的三段 Shapely 檢查（`scene_service.py:2228-2230`）；`generate_layout` 中每個 Shapely 候選都得再過 `_raster_accepts`（`scene_service.py:2269-2286`）。相對選項一，規則判定統一成查表；相對選項二，不必重寫已驗證的提議能力。

**兩處明文例外**（不是遺漏，是現況）：

| 例外 | 行為 | 佐證 |
| :--- | :--- | :--- |
| 建不出房間環 | `build_raster_context` 回 `None`，呼叫端退回 Shapely 路徑；`raster_free(ctx=None)` 直接回 `True` | `scene_service.py:1378-1382,1519-1520` |
| 拖曳落點驗證（FR-033） | `/api/scene/validate` → `validate_single_placement` **全程只走 Shapely**，未建柵格脈絡 | `main.py:3998-4009`；`scene_service.py:2111-2155` |

## 4. 後果

### 4.1 得到什麼

- 自動擺位的合法性答案唯一：房外／牆體／門前動線／採光帶／已放家具一次判完（`scene_service.py:1504-1550`）。
- 多房整屋驗證可行：房間遮罩取所有房的聯集，避免「只鋪最大房的柵格把其他房家具全誤殺」（`scene_service.py:1391-1394`）。
- 新增紀律成本低——視聽走廊（`scene_service.py:2232-2267`）與落地窗通行縫（`scene_service.py:1425-1431,1455-1459`）都只是再疊一張遮罩。
- 決定性可維持：候選邊以 `(-length, mid.y, mid.x)` 完整 tie-break、多處 `+0.0` 消負零（`engine/rules.py:49-53`；`engine/obb.py:20-27`）→ NFR-016。

### 4.2 付出什麼

| 代價 | 可觀察事實 | 佐證 | 掛號 |
| :--- | :--- | :--- | :--- |
| 量化誤差 | 重疊判定的解析度＝格徑（預設 5 cm），不是解析幾何；bbox 單軸超過 1200 格時格徑自動放大 | `engine/obb.py:126-134`；`engine/raster.py:18-21,62` | NFR-015 |
| 正面朝向慣例相反 | Shapely 路徑 `_SIDE_OFFSETS["front"] = (0, 1)`（本地 **+y**，`engine/README.md:34` 亦如此宣告）；柵格路徑 `front_vector(r) = (sin r, −cos r)`（本地 **−y**）。同一份測試檔內兩種註記並存 | `engine/clearance.py:46-52`；`engine/obb.py:1-5,30-36`；`backend/server/tests/test_cabinet_clearance.py:68,81` | OPEN-21 |
| 淨空需求表三份、鍵空間不同 | `CLEARANCE_BY_TYPE` 以 `normalized_type` 為鍵（衣櫃 50、書櫃／餐邊櫃 40、書桌 50）；`CLEARANCE_OF` 以引擎 `kind` 為鍵（衣櫃 60、矮櫃／梳妝台 45、床頭櫃 35）；第三份是柵格側常數 `CABINET_FRONT_CLEARANCE_CM = 50`。衣櫃在三處是 50／60／50；床頭櫃在 agent 側有 35 cm 正面淨空，engine 側被明文排除 | `catalog/style_db.py:185-190`；`agent/clearance.py:21-26`；`engine/clearance.py:24,28-32` | OPEN-22 |
| 窗前淨空兩個數字 | 柵格：`WINDOW_CLEARANCE_CM = 40`＋家具高 ≥90 cm 才受限；Shapely 拖曳路徑：`window_clearance_zones(depth_cm=70.0)` 預設 70 cm，改以型別豁免表處理。FR-035 只記 40 cm | `engine/constraints.py:21-23`；`scene_service.py:1308-1315,1318-1321,2137-2147` | 尚無 OPEN 編號，待 owner 於 `requirements_tracker.xlsx` ②決策沿革指派 |
| 座標與旋轉轉換是常態 bug 面 | 中心原點 ↔ 角落原點、進柵格一律取負角（`-rotation_deg`），兩路徑各自維護同一約定 | `scene_service.py:1526-1529,2273-2275` | NFR-017 |
| 沒有等價測試 | 兩路徑各有測試（`tests/test_clearance.py` 10 案、`tests/test_placement.py` 18 案 ｜ `tests/test_layout_spec.py` 33 案），但 repo 內**沒有**「同一輸入、兩路徑同答案」的等價測試；唯一同時觸及兩者的檔案是分段各驗、非交叉比對 | `backend/server/tests/test_cabinet_clearance.py:1-111` | 承接 [`../../05_qa/test_plan.md`](../../05_qa/test_plan.md) |

### 4.3 什麼時候該重評這個決策

| 觸發條件（可觀察） | 應走的方向 |
| :--- | :--- |
| 出現可重現的「拖曳說可以、自動擺位說不行」（或反之）回報 ≥1 件 | 先消 §4.2 第 4 列的窗前淨空落差，並評估讓 FR-033 也走柵格裁決 |
| OPEN-21 導致淨空畫錯側的實例再現（前例：電視櫃、床頭櫃已各調校一次，`engine/clearance.py:28-32`） | 由 MOD-ENG owner 拍板單一正面約定，另一側改為轉接 |
| 房間 bbox 單軸 > 60 m（＝1200 格 × 5 cm）出現在真實案件，格徑自動放大 | NFR-015 的「5 cm」不再成立，需改寫 NFR-015 或改採分區網格 |
| `engine/placement.py` 連續兩次迭代都只為配合柵格而修改 | 提議能力已無獨立價值，收斂到選項二 |
| `docs/擺位計算邏輯.md` 補上提議搜尋演算法 | 選項二的最大障礙消失，重新評估淘汰 Shapely |

## 5. 執行計畫

1. 現況已上線，**無遷移動作**；本 ADR 為既成決策追認。
2. 補一支等價測試：同一房、同一件家具、同一落點，兩路徑必須同答案；第一個鎖定案例為衣櫃正面方向（對應 OPEN-21）。
3. OPEN-21／OPEN-22 由 MOD-ENG owner 於 `requirements_tracker.xlsx` ②決策沿革拍板：哪一側是規格正面、三份淨空表誰是權威；結論回寫 [`../../04_design/lld.md`](../../04_design/lld.md) 與本 ADR §4.2。
4. 決策未貫徹處（`/api/scene/validate` 不走柵格）由 MOD-SRV-SCENE owner 決定：接上柵格裁決，或明文記為「拖曳採寬鬆判定、最終確認才嚴格」的刻意設計。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-08-12 | （待 owner 核准） | 由程式碼現況追認；§2.2 的選項二為推測重建，待 MOD-ENG owner 確認當時是否確實考量過 |

## 6. 追溯

| 項目 | ID／連結 |
| :--- | :--- |
| 觸發來源 | DEC-008、DEC-009；[`../../01_requirements/srs.md`](../../01_requirements/srs.md) §2.4、§3 |
| 實現的需求 | FR-032、FR-033、FR-034、FR-035、FR-036、FR-037 |
| 受約束的品質屬性 | NFR-015、NFR-016、NFR-017 |
| 驗收對應 | ACPT-030、ACPT-031、ACPT-032、ACPT-033、ACPT-034 |
| 影響範圍 | MOD-ENG、MOD-SRV-SCENE、MOD-AGT；系統全貌見 [`../sad.md`](../sad.md) |
| 相關決策 | [`ADR-002`](ADR-002-engine-sole-geometry-authority.md)（幾何權威歸引擎，本 ADR 為其實作分歧）、[`ADR-007`](ADR-007-centimeter-unit-contract.md)（公分契約）、[`ADR-011`](ADR-011-agent-pipeline-flag-isolation.md)（並存管線同樣消費本引擎） |
| 取代關係 | 無（Supersedes：無；Superseded-by：無） |
| 待確認 | OPEN-21、OPEN-22；窗前淨空 40 cm／70 cm 落差尚無編號 |
| 下游文件 | [`../../04_design/lld.md`](../../04_design/lld.md)、[`../../05_qa/test_plan.md`](../../05_qa/test_plan.md)、[`../../06_ops/runbook-placement-blocked.md`](../../06_ops/runbook-placement-blocked.md) |
