# ADR-007: 跨模組一律公分制的單位契約 (Centimeter Unit Contract) - RoomPilot

> **狀態:** 已接受（現況追認，待 owner 核准） ｜ **日期:** 2026-08-12 ｜ **決策者:** Bella（`docs/contracts/` 整合 owner，`AGENTS.md:46`）；受約束並共同確認者：Ancai（`backend/engine/`）、Cody（`backend/floorplan/`、`backend/upgrade3d/`）、Yen（`backend/agent/`）
> **Owner:** Bella（跨目錄公開契約）；規則正文載於 `AGENTS.md` §不可違反的契約（`AGENTS.md:48-51`）
> **語域:** L2（橋接）
> **實例:** 每決策一份（`ADR-NNN-<slug>.md`）
> **本文件回答**：為什麼所有長度與座標一律公分、五條命名規則各是什麼、單位轉換發生在哪幾個邊界、代價與重評條件。
> **本文件不含**：系統全貌（去 [`sad.md`](../sad.md)）、欄位級端點契約（去 [`api_spec.md`](../../04_design/api_spec.md) 與 `openapi-*`）、幾何合法性歸屬（去 [`ADR-002`](./ADR-002-engine-sole-geometry-authority.md)）、產物邊界（去 [`ADR-001`](./ADR-001-layout-json-scene-json-boundary.md)）、快照儲存（去 [`ADR-004`](./ADR-004-single-workflow-snapshot-sqlite.md)）。
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、2026-08-12 工作樹。行號隨程式碼演進，衝突時以原始碼為準。

---

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 執行計畫](#5-執行計畫)
- [6. 追溯](#6-追溯)

## 1. 背景與問題

- **上下文**: 八步工作流橫跨五個 owner 目錄（`AGENTS.md:34-46`），而每個目錄有各自的原生單位：DXF 解析器內部以公尺運算（`dxf_parser.py:33-34` 的 `WALL_HEIGHT = 2.7`／`WALL_THICK = 0.18`）；影像辨識原生是像素，靠 `cm_per_px` 換算（`vision/units.py:44-51`）；幾何引擎的通行常數直接寫成公分浮點數（`constraints.py:21-23` 的 75／40／90）；Three.js 世界座標本身無單位（`scene_viewer.js:245-249` 只做 z 軸取負、不縮放）。
- **問題**: 單位不一致的錯誤量級是 100 倍且靜默——同一份 payload 換個消費端，房間會變成 4.2 cm 或家具變成 100 倍大，而任何一端都不會拋例外。此陷阱已被寫進測試註解：`tests/test_generate_layout_characterization.py:236-237` 明記「不標 `coordinate_unit` 會被 `_floorplan_coordinate_scale_cm` 當成公尺並 ×100」。
- **驅動因素/約束**:
  - 家具合法性只由 `backend/engine/` 判定（[`ADR-002`](./ADR-002-engine-sole-geometry-authority.md)），引擎既有常數已是公分（`constraints.py:21-23`），改單位等於改判準。
  - 舊專案快照沒有單位欄位，遷移不得破壞既有存檔；`workflow_json` 另有 2 MB 上限（`project_store.py:11,224`）。
  - 台灣住宅裝修與家具型錄慣用公分（`docs/contracts/FURNITURE_ENGINEERING_RULES.md:10`、`LAYOUT_EVALUATION_SCHEMA.md:21`）。

## 2. 考量的選項

### 2.1 選項 A：公尺制（SI／CAD 原生）

- **描述**: 對外契約沿用 DXF 與早期辨識輸出的公尺欄位（`polygon_m`、`distance_m`、`m_per_px`、`width_m`）。
- **優點**: 免去 DXF 解析器的邊界轉換；與 CAD 世界同語言。
- **缺點**: 引擎常數全部變成 0.75／0.40 級小數，浮點比較與 raster 網格解析度都要重訂；此路線已被實作單向否決——遷移器不是雙軌並存，而是**刪掉**公尺欄位（`vision/units.py:73,78,81,103,109` 的 `pop`；`scene_unit_contracts.js:44-48` 的 `withoutMeterDimensions`）。
- **成本/複雜度**: 高（引擎與型錄全面改寫）

### 2.2 選項 B：逐值帶單位標籤（unit-tagged value）

- **描述**: 每個數值包成 `{value, unit}`，消費端自行換算，容許多單位共存。
- **優點**: 自我描述，永遠不會猜錯單位。
- **缺點**: payload 體積數倍成長，直接壓到 `workflow_json` 的 2 MB 硬上限（`project_store.py:11,224`，超過回 413）；JS 端每次讀值都要拆包，等於重寫全部幾何程式碼。
- **成本/複雜度**: 高

### 2.3 選項 C：各模組保留原生單位，只在兩兩邊界互轉

- **描述**: 不立全域契約，誰消費誰負責換算。
- **優點**: 各 owner 不必動既有程式。
- **缺點**: N×N 轉換點；且沒有標記可依據時只能**猜**——現存的 `inferredGeometryScale`（`scene_unit_contracts.js:137-164`）正是這個世界的殘骸：它比對觀測範圍與 `width_cm`，小於 1/20 就判定為公尺並 ×100，猜錯即 100 倍錯位。
- **成本/複雜度**: 低（短期）／高（長期，錯誤不可觀測）

### 2.4 選項 D：一律公分，轉換集中在管線邊界（採用）

- **描述**: 跨模組長度與座標一律公分；轉換只發生在四個顯名邊界（辨識管線末端、DXF→scene、第 4 步編輯器、前端讀檔正規化），內部不再換算。
- **優點**: 引擎、payload、3D 世界座標共用同一數值，`position_cm` 可直接餵給 Three.js（`scene_viewer.js:245-249`）；轉換點可測且冪等。
- **缺點**: 每個外部來源都要寫一個邊界轉換器；沒帶標記的舊資料仍需啟發式救援。
- **成本/複雜度**: 中

## 3. 決策

**選擇**: 選項 D——跨模組一律公分，五條規則如下，並以 `AGENTS.md:48-51` 為規則正文。

| # | 規則 | 佐證 file:line |
| :--- | :--- | :--- |
| R1 | 所有長度、尺寸、位置、位移與淨空一律公分；X 向右、Y 向上，position 指物件中心 | `engine/models.py:9-12`；`constraints.py:21-23` |
| R2 | 新增長度／座標欄位使用 `_cm` 後綴 | `AGENTS.md:50`；`scene_service.py:1845-1849`；`agent/tools/read_layout.py:8-9` |
| R3 | 面積使用 `_m2` | `AGENTS.md:50`；`floorplan2room.py:614`（`area_px * cm * cm / 1e4`） |
| R4 | 角度一律度數（非弧度），欄位名 `rotation_y_deg`；轉弧度只在渲染端做 | `engine/models.py:11,71`；`scene_layout2d.js:347`；`scene_unit_contracts.js:217` |
| R5 | 相容舊欄位（`width`/`depth`/`pos_x`/`pos_y`）必須同時帶 `coordinate_unit: "cm"` 與 schema version | `engine/schema.py:18-32`（`schema_version "2.0"`＋`coordinate_unit "cm"`）；`agent/tools/place_furniture.py:93-95` |

**轉換邊界（唯四）**：辨識管線最後一步 `canonicalize_analysis_cm`（`vision/analysis.py:671-677`；實作 `vision/units.py:30-41`，未標記者一律 ×100）；DXF 公尺→公分 `_canonicalize_floorplan_cm` 與 `parse_floorplan_with_engine`（`vision/confirmation.py:17-68,118`；`scene_service.py:2793-2806,2864-2866`）；第 4 步編輯器 payload（`scene_service.py:1756-1762`；前端 `scene_v2.js:2216-2241`）；前端讀舊檔正規化（`scene_unit_contracts.js:50-102,313-425`）。

**理由**: 相對選項 A，公分讓引擎判準與型錄尺寸維持整數量級、不必重訂 raster 精度；相對選項 B，它把單位資訊放在物件層而非每個數值，不觸 2 MB 上限；相對選項 C，它把「猜單位」限縮成只對**沒有標記的舊資料**成立的一段程式，而不是常態路徑。

## 4. 後果

### 4.1 得到什麼

- 3D 不需要單位縮放層：`position_cm` 直接就是 Three.js 世界座標（`scene_viewer.js:245-249`），只有格線輔助物需要 ×100 才變成公尺格（`scene_viewer.js:649-650`）。
- 遷移可測且冪等：舊公尺 payload 連跑兩次 `canonicalize_analysis_cm` 結果相同，有回歸測試釘住（`tests/test_floorplan_vision.py:630-653`）。
- 跨 owner payload 不需協商：agent 端擺放結果直接沿用引擎序列化（`agent/tools/place_furniture.py:93-95`），RAG 與型錄契約同樣以 `*_cm` ＋ `coordinate_unit` 表達（`docs/contracts/POSTGRESQL_FURNITURE_RAG_RUNTIME.md:74-75`）。

### 4.2 付出什麼

- **四個邊界轉換器要各自維護**，且捨入精度不一致：`vision/units.py` 取小數 2 位、`scene_service.py:2793-2806` 取 1 位、`engine/schema.py:29-30` 取 1 位——每次來回最多累積 0.05 cm 捨入誤差（算術上限，未實測其對淨空判定的影響，**待確認**）。
- **舊資料只能靠啟發式救援**：`scene_unit_contracts.js:9-15` 的預設縮放是 100（即「沒標記就當公尺」），`inferredGeometryScale`（同檔 `:137-164`）用 bbox 比例猜；此路徑猜錯不會報錯，只會畫出 100 倍錯位的場景。
- **殘留混單位出口（缺口）**：`/api/plan` 與 `/api/upload` 直接回傳解析器原生 payload（`main.py:4060-4086`），其中 `wall_height`／`wall_thickness`／`bbox` 是公尺、`width_cm`／`wall_segments` 是公分，且**不帶** `coordinate_unit`（`dxf_parser.py:364-388`）。八步主線不走這兩個端點（主線經 `vision/confirmation.py:17-68` 或 `scene_service.py:2758-2866` 轉換），但它們是公開端點。
- **GLB 資產不受本契約管**：模型原生單位一律被忽略，以外框非等比縮放到型錄 `size_cm`（`scene_visual_contracts.js:33-39`；`scene_viewer.js:3562-3575`）——型錄尺寸錯，模型就變形而非報錯。
- 無自動化檢查：repo 內沒有「新欄位是否帶 `_cm`」的 lint 或契約測試，規則只靠人工 review 與 `AGENTS.md:50-51`（**本 repo 無此機制**）。

### 4.3 什麼時候該重評

| 觸發條件（可觀測） | 重評方向 |
| :--- | :--- |
| 出現英制（吋）型錄或跨國型錄來源，`size_cm` 無法無損表達 | 是否需回到選項 B 的逐值單位標籤 |
| 匯入來源以公釐為原生精度（機械／櫥櫃 CAD），且 1 位小數捨入造成可觀測的淨空誤判 | 提高捨入位數或改公釐制 |
| 專案尺度超出住宅（單一 payload 範圍 >5,000 cm，如整層樓），出現深度精度或 z-fighting | 3D 世界單位與資料單位脫鉤 |
| 存量專案中缺 `coordinate_unit` 的比例降到 0 | 移除 `inferredGeometryScale` 啟發式與公尺 fallback，契約可簡化 |
| `AGENTS.md` §不可違反的契約 該兩條被修改，或 `schema_version` 由 `"2.0"` 升版 | 本 ADR 同步改版或被取代 |

## 5. 執行計畫

1. **已落地（本 ADR 為現況追認）**：R1–R5 五條規則、四個邊界轉換器、冪等回歸測試（見 §3、§4.1 佐證）。
2. **缺口 1**：`/api/plan`、`/api/upload` 的混單位 payload 補 `coordinate_unit` 與 `*_cm` 欄位，或明文標註為內部除錯端點——需 Cody（`backend/upgrade3d/`）與 Bella 共同確認，承接 [`api_spec.md`](../../04_design/api_spec.md)。
3. **缺口 2**：新增契約測試斷言四個邊界轉換器的輸出皆帶 `coordinate_unit: "cm"`，承接 [`test_plan.md`](../../05_qa/test_plan.md)。
4. **待確認（無既有 OPEN 編號可掛）**：(a) 三處捨入位數是否統一為 2 位；(b) 存量專案中缺 `coordinate_unit` 的實際比例，決定啟發式何時可下線。兩項須於 `requirements_tracker.xlsx` ②決策沿革留列後才可寫成規格。
5. **既有待確認連動**：`cm_per_px` 的推導有兩套並存邏輯（OPEN-28，見 [`srs.md`](../../01_requirements/srs.md) §8）——本契約只規範「轉換後是公分」，不規範「比例尺怎麼算」；OPEN-28 未解前，公分值的**正確性**不由本 ADR 保證。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-08-12 | 待 owner 簽核 | AI 由程式碼衍生之現況追認，尚未人工核准 |

## 6. 追溯

| 項目 | ID／文件 |
| :--- | :--- |
| 觸發來源 | DEC-003、DEC-004、DEC-008；NFR-017（單位契約）；FR-012、FR-017、FR-018 |
| 驗收對應 | ACPT-010（對外一律公分）、ACPT-015（DXF 公分 client 版線段）、ACPT-016（結構編輯結果以公分表達） |
| 影響範圍 | MOD-FP、MOD-U3D、MOD-ENG、MOD-SRV-SCENE、MOD-SRV-API、MOD-WEB、MOD-AGT、MOD-CAT（幾乎全模組；`AGENTS.md:50-51` 為規則正文） |
| 上游文件 | [`srs.md`](../../01_requirements/srs.md) §1.2「公分」列與 §3 NFR-017、[`prd.md`](../../01_requirements/prd.md) ACPT-010／015／016、[`sad.md`](../sad.md) |
| 下游文件 | [`api_spec.md`](../../04_design/api_spec.md)、[`lld.md`](../../04_design/lld.md)、[`db_design.md`](../../04_design/db_design.md)、[`test_plan.md`](../../05_qa/test_plan.md) |
| 相依 ADR | 依賴 [`ADR-001`](./ADR-001-layout-json-scene-json-boundary.md)（產物邊界即轉換邊界）、[`ADR-002`](./ADR-002-engine-sole-geometry-authority.md)（引擎為公分判準持有者）；約束 [`ADR-003`](./ADR-003-dual-path-shapely-raster-engine.md)（raster 網格解析度以公分定義）、[`ADR-004`](./ADR-004-single-workflow-snapshot-sqlite.md)（2 MB 快照上限排除逐值單位標籤） |
| 取代關係 | 無（Supersedes: 無；Superseded-by: 無） |
