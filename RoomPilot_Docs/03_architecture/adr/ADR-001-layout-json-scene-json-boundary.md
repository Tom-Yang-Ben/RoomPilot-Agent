# ADR-001: 辨識產物 layout_json 與方案產物 scene_json 的邊界 (Layout / Scene Artifact Boundary) - RoomPilot

> **狀態:** 已接受（現況追認，待 owner 核准） ｜ **日期:** 2026-08-12 ｜ **決策者:** Bella（`docs/contracts/` 整合 owner，`AGENTS.md:46`）＋ Cody（`layout_json` 生產端，`AGENTS.md:37`）、Ancai（`backend/engine/`，`AGENTS.md:41`）、Yen（`backend/agent/`，`AGENTS.md:40`）
> **語域:** L2（橋接）
> **實例:** 每決策一份（`ADR-NNN-<slug>.md`）
>
> **本文件回答**：為什麼辨識管線的輸出止於 `layout_json`、家具方案與使用者編輯只寫 `scene_json`，以及兩者為何是單向、不互相回寫。
> **本文件不含**：兩份產物的欄位級 schema（去 [`api_spec.md`](../../04_design/api_spec.md) 與 `openapi-*`）、幾何合法性為何只由引擎裁決（去 [`ADR-002`](./ADR-002-engine-sole-geometry-authority.md)）、八步狀態為何只存一份快照（去 [`ADR-004`](./ADR-004-single-workflow-snapshot-sqlite.md)）、家電為何只進 `render_context`（去 [`ADR-006`](./ADR-006-appliances-render-context-only.md)）、公分單位契約（去 [`ADR-007`](./ADR-007-centimeter-unit-contract.md)）、系統全貌（去 [`sad.md`](../sad.md)）。
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、工作樹日期 2026-08-12；行號隨程式碼演進，衝突時以原始碼為準。

---

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 執行計畫與待確認](#5-執行計畫與待確認)
- [6. 追溯](#6-追溯)

## 1. 背景與問題

- **上下文**: 八步流程橫跨四個 owner 目錄——辨識在 `backend/floorplan/`（Cody）、方案與 API 在 `backend/server/`（Bella）、幾何裁決在 `backend/engine/`（Ancai）、需求與選件在 `backend/agent/`（Yen）（`AGENTS.md:36-41`）。但整條流程的狀態**只有一個持久化容器**：`projects.workflow_json` 單欄快照（`project_store.py:98-142`；[`ADR-004`](./ADR-004-single-workflow-snapshot-sqlite.md)）。因此「兩份產物」不是兩個資料庫，而是同一份快照裡兩組不同的節點與一條單向資料流。
- **問題**: 若辨識結果與設計結果混成同一個持續長大的物件，(a) 使用者回頭重跑辨識或改結構時，「哪些下游成果該作廢」無法列舉，畫面上會留下看起來還在、其實已對不上的舊配置（DEC-018）；(b) 資料 owner 與模組 owner 對不上，任一端加欄位都會拖到其他人的模組。
- **驅動因素/約束**:
  - `AGENTS.md:52` 已把「辨識輸出是 `layout_json`；方案生成與編輯輸出是 `scene_json`」列為不可違反的契約，且明列允許／禁止內容（`docs/contracts/LAYOUT_SCENE_BOUNDARY_CONTRACT.md:22-34`）。
  - 幾何合法性只能由 `backend/engine/` 裁決（`AGENTS.md:54`），所以邊界不能讓任一方各自算座標。
  - 兩份產物共用同一個 2 MB 快照上限（`project_store.py:11,223-225`；NFR-001），邊界設計不能靠複製整包資料來解耦。
  - 既有前端讀取路徑不得一次斷裂，需保留相容欄位並存期。

## 2. 考量的選項

### 選項一: 單一 analysis payload 一路長大（歷史基線，已放棄）

- **描述**: 沿用 analyze 回傳的 `analysis` 頂層物件，設計階段直接在同一物件上疊家具、材質與 render 欄位。
- **它至今仍留下的痕跡**: `_layout_json_from_analysis()` 只是 passthrough——`analysis.floorplan` 存在就回它、否則整包回傳（`main.py:4099-4103`），測試明文釘住 `layout_json == analysis`（`tests/test_project_workflow_api.py:318`）。
- **優點**: 零遷移成本；前端一個物件讀到底。
- **缺點**: 沒有可以整支設為 null 的下游節點，DEC-018 的「改結構就讓下游失效」無法界定範圍；schema 演進四方互踩。
- **為何不選**: 它擋不住本 ADR 要解的那個問題（作廢範圍不可列舉），只延後代價。
- **成本/複雜度**: 低（短期）／高（長期）

### 選項二: `layout_json` 為唯一可變權威，第 4／6 步編輯回寫（已放棄）

- **描述**: 使用者改牆門窗或拖家具後，把結果回寫進 `layout_json`，讓它永遠等於「現場真相」，下游只讀不寫。
- **優點**: 只有一份空間真相，不必處理辨識結果與使用者編輯的分歧。
- **缺點**: 回寫會污染辨識證據——`scale.source`／`confidence`／`issues`／`spatial_report` 記的是「電腦看到什麼」（`vision/analysis.py:634-666`），被使用者編輯覆蓋後就再也回答不了 FR-013、FR-015 的「這個數字哪來的」；且辨識可重跑，重跑會把使用者編輯整批洗掉。
- **為何不選**: 現況改採第 4 步另存 `floorplan_editor` 快照（`scene_v2.js:2216-2245`）；`state.analysis` 全檔只在辨識回傳、比例標定與還原三處被賦值（`scene_v2.js:1832,2186,19304`），第 6 步以後永不回寫。
- **成本/複雜度**: 中（改動量）／高（不可逆的證據遺失風險）

### 選項三: 兩份單向產物 ＋ 重跑辨識即作廢下游（採用）

- **描述**: 辨識端只寫 `workflow.recognition`（＝`layout_json`），方案端只寫 `layout_2d`／`white_model_3d`／`realistic_3d`（＝`scene_json` 及其衍生），資料只從 layout 流向 scene；重跑辨識時七個下游節點顯式寫 null。
- **優點**: 作廢範圍可列舉、可測；owner 邊界＝資料邊界。
- **缺點**: 相容欄位需雙份並存；邊界內容目前靠慣例而非 schema 強制（見 §4）。
- **成本/複雜度**: 中

## 3. 決策

**選擇**: 選項三——`layout_json` 與 `scene_json` 為模組邊界的唯二顯名產物，資料單向流動。

**理由**: 只有這個選項能把 DEC-018 的業務承諾變成可驗收的行為。落地機制四條：

1. **辨識端只產空間事實**：`analyze_floorplan_image()` 的 result 只有牆／門／窗／房間／比例／信心／issues／`spatial_report`，無任何家具或材質欄位（`vision/analysis.py:634-677`），且公分正規化是最後一步（`analysis.py:671`）→ FR-012、ACPT-010。
2. **方案端只吃、不改空間事實**：`/api/scene/generate` 以問卷 ＋ `layout_json`／`floorplan_editor` 為輸入（`main.py:3592-3644`；`scene_service.py:2888-2913`），輸出含 `scene_objects`、`render_context`、`design_choices` 的 `scene_json`（`scene_service.py:2995-3088`），家具座標交由引擎計算（`scene_service.py:2936-2952`）→ FR-029、ACPT-027。
3. **不回寫**：`/api/scene/layout` 只回 `floorplan` 與 `scene_objects`，不寫入 recognition 節點（`main.py:3688-3709`）；`backend/engine/` 全目錄不出現 `layout_json`／`scene_json` 字樣（2026-08-12 全目錄檢索），引擎只認純幾何結構，兩份產物都不是它的相依。
4. **失效即作廢**：重跑辨識時 `confirmed_floorplan`／`calibration`／`space_confirmation`／`requirements`／`layout_2d`／`white_model_3d`／`realistic_3d` 七個節點顯式寫 null，並改寫 `_flow.staleFrom="calibration"`（`main.py:3036-3063`），回歸測試釘住還原後仍為 null（`tests/test_project_workflow_api.py:366-381`）→ FR-016、ACPT-014。

## 4. 後果

**得到什麼**

- 重跑辨識的作廢範圍是七個具名節點，可列舉、可測（`main.py:3041-3047`；`tests/test_project_workflow_api.py:377-381`），DEC-018 因此有驗收對象。
- owner 邊界＝資料邊界：MOD-FP 只碰 `recognition`、MOD-SRV-SCENE 只碰 `layout_2d`／`white_model_3d`、MOD-WEB 的第 4 步另存 `floorplan_editor`（`scene_v2.js:1215-1272,2216-2245`），四方可各自演進 schema。
- 並存 agent 管線只吃 `layout_json` 就能啟動（缺欄位 422，`main.py:3522-3527`；`agent/master.py:110-112`），不必碰第 6 步 live 路徑（[`ADR-011`](./ADR-011-agent-pipeline-flag-isolation.md)）。
- 部署期可沿產物切 worker（`LAYOUT_SCENE_BOUNDARY_CONTRACT.md:94-100`），不需先重構資料模型。

**付出什麼**

- **邊界只有命名，沒有 schema 強制**：`_layout_json_from_analysis()` 是 passthrough（`main.py:4099-4103`），契約第 22–34 行的允許／禁止清單目前**沒有任何程式碼或測試在執行**；「layout_json 不含家具欄位」是慣例而非約束。
- **相容欄位雙份並存**：analyze 同時回 `analysis` 與 `layout_json`（`main.py:3065-3068`）、generate 回 legacy 頂層 payload ＋ `scene_json` 的 `deepcopy`（`main.py:3641-3643`），前端讀 `payload?.scene_json || payload`（`scene_v2.js:670-672`）。回應體積加倍，而兩份都要進同一個 2 MB 快照上限（NFR-001）。
- **作廢只作用在下游**：`recognition` 節點本身走遞迴深合併（`project_store.py:18-25`），舊辨識產生、新辨識不再產生的鍵會殘留在快照裡；目前只有 list 型欄位（如 `doors`）因整支替換而被清乾淨（`tests/test_project_workflow_api.py:369-376`）。
- **跨界識別字不穩定**：`host_wall_id` 由辨識端以 `wall-{1-based index}` 產生（`floorplan/vision/openings.py:35-40`），第 4 步增刪牆後索引即失效，消費端 `openingBelongsToWall()` 仍優先信它（`scene_architecture.js:200-202`）——OPEN-29。

**什麼時候該重評這個決策**

1. 正式前端開始把 `layout_json` 送進 `/api/scene/generate`（現況送的是 `floorplan_editor`，`scene_v2.js:12714`）——邊界的實際輸入改變，契約第 58–64 行須同步修訂。
2. legacy 相容欄位（`analysis`、generate 頂層 payload）確定下線時：`main.py:4099-4103` 的 passthrough 必須改為白名單投影，並補「`layout_json` 不含家具／材質鍵」的測試。
3. `workflow_json` 序列化逼近 2 MB（現場最大 1,224,258 bytes，佔上限 58%，NFR-001）——「兩份產物共用一格快照」的前提先失效。
4. 出現必須跨界的欄位（例如辨識端要輸出風格建議，或方案端要修正牆線）：先改 `LAYOUT_SCENE_BOUNDARY_CONTRACT.md`，再動程式。
5. worker 化落地（`LAYOUT_SCENE_BOUNDARY_CONTRACT.md:94-100`）時，重新檢視兩份產物是否足以支撐進程切分。

## 5. 執行計畫與待確認

1. 本 ADR 為**現況追認**，不觸發程式碼變更；owner 核准前不得據此宣告邊界已被強制執行。
2. 待 §4「重評觸發 2」成立時，補一條契約測試把契約第 22–34 行的禁止清單變成可執行斷言。
3. 下列項目程式碼看不出答案，一律待確認，並在 `requirements_tracker.xlsx` ②決策沿革留一列：

| 待確認 | 目前可驗證的事實 | 承接處 |
| :--- | :--- | :--- |
| 正式前端不送 `layout_json`：契約列為 `scene_json` 的 required input（`LAYOUT_SCENE_BOUNDARY_CONTRACT.md:58-64`），但生產路徑送的是第 4 步的 `floorplan_editor`；`layout_json` 入口目前只有測試與並存管線在用。是刻意分工還是契約已過期？ | `scene_v2.js:12681-12724` 全 payload 無 `layout_json`；`main.py:3622` 仍讀該欄；`tests/test_project_workflow_api.py:575-588` 走 `layout_json` 路徑 | [`api_spec.md`](../../04_design/api_spec.md)、[`lld.md`](../../04_design/lld.md) |
| 邊界的禁止清單是否要程式化：目前 `layout_json` 等同 `analysis`，無白名單投影、無斷言 | `main.py:4099-4103`；`tests/test_project_workflow_api.py:318` | [`test_plan.md`](../../05_qa/test_plan.md) |
| OPEN-29：`host_wall_id` 在第 4 步編輯後失效，是否需要跨界重算機制 | `floorplan/vision/openings.py:35-40`；`scene_architecture.js:194-222` | [`ui_spec-step4-space-confirmation.md`](../../02_ux_ui/ui_spec-step4-space-confirmation.md) §10、[`lld.md`](../../04_design/lld.md) |

## 6. 追溯

| 項目 | ID／文件 |
| :--- | :--- |
| 觸發來源 | DEC-003、DEC-004、DEC-008、DEC-018；FR-010、FR-012、FR-016、FR-017、FR-029；NFR-001、NFR-017 |
| 驗收對象 | ACPT-010、ACPT-014、ACPT-015、ACPT-016、ACPT-027 |
| 影響範圍 | MOD-FP、MOD-SRV-SCENE、MOD-SRV-STORE、MOD-WEB、MOD-ENG、MOD-AGT；[`sad.md`](../sad.md)、[`api_spec.md`](../../04_design/api_spec.md)、[`lld.md`](../../04_design/lld.md)、[`openapi-project-workflow-v1.yaml`](../../04_design/openapi-project-workflow-v1.yaml)、[`openapi-scene-v1.yaml`](../../04_design/openapi-scene-v1.yaml) |
| 相依決策 | [`ADR-002`](./ADR-002-engine-sole-geometry-authority.md)（幾何權威）、[`ADR-004`](./ADR-004-single-workflow-snapshot-sqlite.md)（單一快照）、[`ADR-006`](./ADR-006-appliances-render-context-only.md)、[`ADR-007`](./ADR-007-centimeter-unit-contract.md)、[`ADR-011`](./ADR-011-agent-pipeline-flag-isolation.md) |
| 需求來源文件 | [`srs.md`](../../01_requirements/srs.md) §2.2／§2.4／§9.2、[`prd.md`](../../01_requirements/prd.md) §3.3–§3.6、[`brd.md`](../../01_requirements/brd.md) DEC-018 |
| 取代關係 | 無（Supersedes / Superseded-by 皆無） |
