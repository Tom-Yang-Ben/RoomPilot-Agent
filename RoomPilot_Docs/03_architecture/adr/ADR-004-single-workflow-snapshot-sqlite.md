# ADR-004: 單一 workflow_json 快照存 SQLite，不做事件流 (Single workflow_json Snapshot on SQLite) - RoomPilot

> **狀態:** 已接受（現況追認，待 owner 核准） ｜ **日期:** 2026-08-12 ｜ **決策者:** MOD-SRV-STORE owner（Bella）提案，架構師合成本文件；上游 DEC-002 由產品 owner 於 [`requirements_tracker.xlsx`](../../01_requirements/requirements_tracker.xlsx) ①需求決策拍板
> **語域:** L2（橋接）——業務詞與工程詞並列，跨層一律用穩定 ID
> **實例:** 每決策一份（`ADR-NNN-<slug>.md`）
>
> **本文件回答**：八步狀態為什麼收斂成 `projects.workflow_json` 一個 TEXT 欄位、為什麼用「深合併寫入＋2 MB 上限＋`revision` 樂觀鎖」，以及為什麼**沒有**版本歷史表或事件流。
> **本文件不含**：端點欄位級契約（去 [`api_spec.md`](../../04_design/api_spec.md) 與 [`openapi-project-workflow-v1.yaml`](../../04_design/openapi-project-workflow-v1.yaml)）、資料表 DDL 與索引（去 [`db_design.md`](../../04_design/db_design.md)）、系統全貌與模組切分（去 [`sad.md`](../sad.md)）、衝突與超量的現場處置步驟（去 [`RB-003`](../../06_ops/runbook-workflow-save-conflict-or-oversize.md)）、`layout_json`／`scene_json` 的內容邊界（去 [`ADR-001`](./ADR-001-layout-json-scene-json-boundary.md)）。
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、2026-08-12 工作樹。行號隨程式碼演進，衝突時以原始碼為準。

---

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 執行計畫與驗證](#5-執行計畫與驗證)
- [6. 追溯](#6-追溯)

## 1. 背景與問題

- **上下文**：DEC-002 要求「每個案子有可保存、可恢復的身分，中途離開不遺失進度」。八步（對內 11 個 `WORKFLOW_STEPS`，`main.py:164-176`）各自產生異質狀態：辨識結果、標定、`layout_json`、問卷、`scene_json`、視角與生圖紀錄，欄位高頻演進。
- **問題**：(1) 逐步建正規化 schema 會讓每次前端欄位變動連動 DDL；(2) 使用者常開多分頁，後寫者可能靜默覆蓋先寫者的整包狀態；(3) 曾發生顯示字串損壞導致快照無限膨脹（`project_store.py:51` docstring 明載此動機），需要大小預算。
- **驅動因素與約束**：

| # | 約束 | 佐證 |
| :--- | :--- | :--- |
| C1 | 存取模式是「整包讀、整包合併寫」，無依家具物件或事件查詢的正式需求 | `docs/contracts/POSTGRESQL_PROJECT_STORE_PHASE3.md:125` |
| C2 | 保存層不得成為第二套幾何真相；幾何合法性只由 `backend/engine/` 判定 | [`AGENTS.md`](../../../AGENTS.md):52-54 |
| C3 | Pilot 單機部署，須零外部依賴即可啟動；DB 是 runtime 目錄下的檔案 | `project_store.py:80,84-93` |
| C4 | 前端存檔是自動、高頻、可能在關閉分頁時中斷的操作，且快照必須有硬上限 | `scene_v2.js:1327-1359,19167-19171`；`project_store.py:11,39-48,51-74` |

## 2. 考量的選項

### 選項一：單一 `workflow_json` 快照＋`revision` 樂觀鎖（採用）
- **描述**：整包狀態存 `projects.workflow_json TEXT`，同表帶 `revision INTEGER`（`project_store.py:100-113`）。寫入在 `BEGIN IMMEDIATE` 內完成版本比對→深合併→壓縮→序列化→2 MB 檢查→`UPDATE … AND revision = ?`（`project_store.py:199-243`）。
- **優點**：schema 零遷移即可演進前端狀態；`GET /api/projects/{id}` 一次讀回全貌；版本比對與寫入為原子操作。**缺點**：狀態子欄位無法用 SQL 查詢或局部更新；2 MB 是硬牆；無歷史可回溯。**成本**：低。

### 選項二：正規化拆表＋事件流（`project_scene_objects` / `scene_object_events`）
- **描述**：把 `scene_json` 家具物件與每次編輯拆成資料列與事件列，狀態由事件重播得出。
- **不選的理由**：無 C1 的查詢需求；拆表會讓家具幾何在 DB 內另有一份表述，直接違反 C2。此方案**已被契約明文擱置**：「Phase 3 不建立 `project_scene_objects` 或 `scene_object_events`……日後若需要跨專案家具統計、事件回放或局部更新，再以 versioned contract 從 `scene_json` 衍生，不能成為第二套幾何真相」（`POSTGRESQL_PROJECT_STORE_PHASE3.md:125`）。
- **成本/複雜度**：高。

### 選項三：workflow 版本歷史表（append-only，仿 `render_outputs`）
- **描述**：每次存檔 insert 一列 `(project_id, revision, workflow_json, created_at)`，`projects` 只存指標。**同一個 store 內已有此模式的先例**：`render_outputs` 是 append-only、依 `created_at DESC` 回傳最新在前，舊 render 不被覆蓋（`project_store.py:126-141,337-403,405-413`）。
- **不選的理由**：現行前端每次自動存檔都送整包（`scene_v2.js:1296-1300` 的 `workflow: workflowPayload()`），append 歷史等於每次寫入複製近 1 MB；現場單一專案 `revision` 已達 458（§5 實測），歷史體積會是快照的數百倍，而 PRD 未承諾任何「回到舊版本」或「誰改了什麼」的功能。渲染成果保留歷史是因為它是**交付物**，工作流草稿不是。
- **成本/複雜度**：中（實作低、儲存與維運成本高）。

### 選項四：不設版本欄位，純 last-write-wins
- **描述**：`PUT` 直接覆寫，不做任何版本比對。
- **不選的理由**：多分頁互踩會靜默遺失工作，違反 SCN-002 的可觀察承諾與「保護使用者工作」底線。成本低但風險不可接受。
- **誠實註記**：伺服器**有能力**拒絕過期寫入，但正式前端一般存檔路徑**未使用**該能力（見 §4「付出什麼」與 OPEN-14）。就實際行為而言，一般存檔目前落在選項四這一格。

## 3. 決策

**選擇：選項一。** 八步狀態存成 `projects.workflow_json` 單欄快照，深合併寫入、2 MB 上限、`revision` 樂觀鎖；不建版本歷史表，不做事件溯源。

**理由**：存取模式（C1）與單快照完全對齊；深合併讓每一步只送自己的增量而不必重送全貌；`BEGIN IMMEDIATE` 使版本比對與更新成為單一原子操作，加上 `UPDATE … WHERE revision = ?` 二次防護（`project_store.py:201,229-242`）；一個整數欄位就換到「落後方收 409、不覆寫他人變更」的能力。選項二在無查詢需求下只增加漂移面與 C2 風險，選項三的儲存成本無對應的產品承諾支撐。

**機制細節與佐證**：

| 機制 | 行為 | 佐證 |
| :--- | :--- | :--- |
| 深合併 | dict 遞迴合併，list 與純量整個取代；**無法靠省略鍵刪除欄位** | `project_store.py:18-25` |
| 大小預算 | `MAX_WORKFLOW_BYTES = 2 MB`，序列化後檢查，超過在交易內拋出、整筆不落地 | `project_store.py:11,220-225` |
| 膨脹防護 | `name`／`label`／`title` 等顯示欄位超過 512 字元時以 `normalized_type`／`furniture_id` 取代 | `project_store.py:39-48,51-74` |
| 樂觀鎖（兩套） | `expected_revision` 不符 → 409 dict `project_revision_conflict` 並附最新 project；`replay_pending`＋`base_updated_at` 不符 → 409 裸字串 `project_version_conflict` | `main.py:1828-1858`；`project_store.py:206-218` |
| 輸入驗證與超量 | `current_step` 不在 `WORKFLOW_STEPS`／`workflow` 非物件 → 422；超量 → 413 `workflow_too_large` | `main.py:164-176,1809-1814,1859-1866` |
| 落地保障 | 每條連線 `PRAGMA foreign_keys = ON`、`journal_mode = WAL` | `project_store.py:92-93` |
| 前端補償與重播 | 先寫 `localStorage` pending，再以序列化 Promise 串鏈送出（重試 3 次、180 ms×n），離開前攔截；重開專案時只有 `base_updated_at` 與伺服器 `updated_at` 完全相同才重播，否則丟棄並告知 | `scene_v2.js:1290-1302,1305-1325,1327-1359,19167-19171,19267-19293`；`scene_workflow.js:32-41` |

## 4. 後果

**得到什麼**

- 前端狀態欄位演進零 DDL；整個八步共用一條版本序（上傳與 render metadata 也遞增同一個 `revision`，`project_store.py:257-295,341-398`）。ACPT-002（超量整筆被拒、上一版完好）與 ACPT-003（過期存檔被安全拒絕並回報最新狀態）在 store 層與 API 層都可自動驗證（見 §5）；恢復路徑只有一次讀取，無重播成本，Pilot 單機零外部依賴。

**付出什麼**

| 代價 | 具體表現 | 佐證／承接 |
| :--- | :--- | :--- |
| 無歷史、無審計 | 存檔即覆蓋，無法回到任一舊版本，也答不出「誰在何時改了什麼」。整個 store 只有 `projects` 與 `render_outputs` 兩張表 | `project_store.py:98-141` |
| 樂觀鎖只在一條路徑生效 | **正式前端存檔路徑不含 `expected_revision`**，一般存檔等同 last-write-wins，SCN-002 目前只在 `replay_pending` 重播路徑成立；辨識、生圖、額度等 6 處伺服器端寫入同樣不帶版本 | `scene_v2.js:1290-1359` 全段（`rg expected_revision backend/server/static/scene_v2.js backend/server/static/scene_workflow.js` 零命中）；`main.py:2117,2199,2279,2324,2407,3036` → **OPEN-14**。註：次要原型 bundle `static/frontend3d/assets/index-Dmvb1nQv.js` **有**實作 `expected_revision`（15 處）與 409 後重讀 `revision` 再存的重試路徑，是 repo 內既有先例 |
| 深合併語意 | 刪欄位必須寫入覆蓋值；list 一律整取代，局部更新不可能 | `project_store.py:18-25` |
| 無 schema 與查詢能力 | 快照只有應用層約束，壞資料靠 `_compact_workflow_value` 事後補丁；跨專案統計須全表讀出並 parse JSON | `project_store.py:51-74`；本文件 §5 實測即以此方式取得 |
| 單檔無備份 | `projects.sqlite3` 現場 66 MB 且持續成長，無配額、無輪替、無備份腳本、無專案刪除 API | NFR-022、ACPT-058；**OPEN-13**（[`brd.md`](../../01_requirements/brd.md) §9） |

**什麼時候該重評這個決策**（任一條可觀測事件成立即重評）

1. 任一專案 `workflow_json` 序列化超過 1.6 MB（上限 80%），或現場出現任何一次 413 `workflow_too_large`。現況最大 1,224,258 bytes（58%），尚有餘裕。
2. OPEN-14 被 owner 判定為「遺漏」→ 前端補送 `expected_revision`，本 ADR §4 的 last-write-wins 段落須改寫，SCN-002 的驗收才成立。
3. PRD 新增「回到某一步的舊版本」「操作稽核軌跡」類承諾（新 DEC-* 或 UAT 腳本出現）→ 選項三重新上桌。
4. 同一專案的並行編輯者從「同一人多分頁」變成「多人」（DEC-014 核准需帳號，或多人欄位進入正式 schema）→ 樂觀鎖粒度不足，須重評。
5. Phase 3 實際啟動（`backend/server/postgres_project_store.py` 重新出現、`workflow_json` 轉 `JSONB`）→ 選項二成本重算；或寫入頻率高到 `BEGIN IMMEDIATE` 造成可觀測排隊、`sqlite3.connect(timeout=10)` 逾時（`project_store.py:88`）。

**影響範圍**：MOD-SRV-STORE（實作）、MOD-SRV-API（`PUT /api/projects/{id}/workflow`）、MOD-WEB（所有步驟的存檔與重播）、[`RB-003`](../../06_ops/runbook-workflow-save-conflict-or-oversize.md)、[`db_design.md`](../../04_design/db_design.md)。**已知例外**：Agent 管線另有自己的單檔 JSON 快照與 checkpoint `undo()`（`agent_pipeline_service.py:69-111`；`backend/agent/master.py:145-155`），不走本 ADR 的 store，其隔離條件見 [`ADR-011`](./ADR-011-agent-pipeline-flag-isolation.md)。

## 5. 執行計畫與驗證

本決策**已在程式碼中生效**，本文件為現況追認。既有驗證：

| 驗證對象 | 測試 | 斷言 |
| :--- | :--- | :--- |
| 過期寫入不覆蓋 | `tests/test_project_store_hardening.py:37-58` | 拋 `ProjectVersionConflict`，且既有 workflow 保持前一版 |
| 2 MB 上限原子性 | `tests/test_project_store_hardening.py:103-117` | `revision` 未遞增、超量鍵未落地 |
| API 層 409／413、WAL 與外鍵 | `tests/test_project_store_hardening.py:158-187`、`:26-35` | 409 `project_revision_conflict`、413 `workflow_too_large`；PRAGMA 生效 |
| pending 重播 | `tests/test_project_workflow_api.py:199-249` | 過期重播 409 裸字串且伺服器狀態完好；相符重播 200 |

**現場實測（2026-08-12，唯讀查詢 `.runtime/projects.sqlite3`）**：741 筆專案、`max(length(workflow_json))` = 1,224,258、`max(revision)` = 458、DB 檔 69,287,936 bytes。（[`srs.md`](../../01_requirements/srs.md) NFR-001 記同日稍早的 728 筆，差異為當日新增，非量測衝突。）

**待確認（本文件承接，不自創新編號）**：

- **OPEN-14**：正式前端一般存檔不帶 `expected_revision` 是刻意取捨（相信「同一人多分頁」風險可接受）還是實作遺漏。owner 拍板前，NFR-003 只能記為「伺服器具備能力」，不得記為「系統保證」。裁決時可參考次要原型 `frontend3d` bundle 的既有作法（帶 `expected_revision`，收 409 後重讀最新 `revision` 自動重存，見 §4），移植成本已有先例可估。
- **OPEN-13**：備份頻率、保留期、結案刪除與責任人全部空白，本 ADR 的「單檔無歷史」在無備份下風險加倍；屬業務決策（DEC-015），非工程待辦。
- **無 OPEN 編號者（本 ADR 新提）**：(a) `POSTGRESQL_PROJECT_STORE_PHASE3.md:9` 宣稱 `backend/server/postgres_project_store.py` 與 `scripts/project_store/` 仍存在，但本分支兩者皆無（後者僅剩 `__pycache__`）——Phase 3 是 TO-BE，該契約「現行可用性」段已過時，須由 MOD-SRV-STORE owner 更新或標註失效。(b) `.runtime/projects.sqlite3` 現存 `users`、`refresh_tokens`、`project_members` 三張表，但本分支 `backend/server/` 無任何對應建表程式碼，研判為他分支執行後遺留在共用 runtime；是否代表多人協作 schema 已在別處推進（觸發 §4 重評條件 4），待確認。

## 6. 追溯

| 項目 | ID／文件 |
| :--- | :--- |
| 上游業務決策 | DEC-002（[`brd.md`](../../01_requirements/brd.md)）；DEC-015 為關聯未決項 |
| 觸發需求 | FR-003、FR-004、FR-022；NFR-001、NFR-003、NFR-004（[`srs.md`](../../01_requirements/srs.md) §2.1、§2.3、§3） |
| 驗收條件與場景 | ACPT-002、ACPT-003、ACPT-020（關聯 ACPT-001、ACPT-058）；SCN-001、SCN-002、SCN-003（[`prd.md`](../../01_requirements/prd.md)） |
| 受約束模組 | MOD-SRV-STORE、MOD-SRV-API、MOD-WEB（[`sad.md`](../sad.md)） |
| 相關決策 | [`ADR-001`](./ADR-001-layout-json-scene-json-boundary.md)（快照內兩種 JSON 的邊界）、[`ADR-011`](./ADR-011-agent-pipeline-flag-isolation.md)（管線另存快照的例外） |
| 下游文件 | [`db_design.md`](../../04_design/db_design.md)、[`api_spec.md`](../../04_design/api_spec.md)、[`openapi-project-workflow-v1.yaml`](../../04_design/openapi-project-workflow-v1.yaml)、[`ui_spec-step1-project.md`](../../02_ux_ui/ui_spec-step1-project.md)、[`test_plan.md`](../../05_qa/test_plan.md)、[`RB-003`](../../06_ops/runbook-workflow-save-conflict-or-oversize.md)、[`deployment_and_operations.md`](../../06_ops/deployment_and_operations.md) |
| 待確認 | OPEN-14（本 ADR 主責）、OPEN-13（[`brd.md`](../../01_requirements/brd.md) 主責）、§5 兩項無編號待確認 |
| 取代關係 | 無（Supersedes：舊版 `ADR-007-workflow-json-single-snapshot-store.md`，已隨舊 ID 體系退役） |
