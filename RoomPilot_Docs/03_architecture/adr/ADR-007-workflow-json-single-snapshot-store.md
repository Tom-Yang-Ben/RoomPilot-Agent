# ADR-007: 八步狀態併入單一 workflow JSON 快照（≤2MB）存 ProjectStore，revision 樂觀鎖防多分頁互踩

> **狀態:** 已接受（AI 衍生，待人工核准） | **日期:** 2026-08-11 | **決策者:** Bella（`backend/server/` 專案保存 owner，docs/TEAM_AI_OWNERSHIP.md；AI 衍生，人工核准前為 TO-BE）
> **語域:** L2（橋接）
> **定位:** 本文件回答「為什麼八步工作流狀態用單一 JSON 快照＋樂觀鎖保存，而不是正規化資料表或無鎖寫入」；儲存後端遷移（SQLite→PostgreSQL）歸 [docs/contracts/POSTGRESQL_PROJECT_STORE_PHASE3.md](../../../docs/contracts/POSTGRESQL_PROJECT_STORE_PHASE3.md)，端點契約歸 [api_spec.md](../../04_design/api_spec.md)，系統全貌歸 [sad.md](../sad.md)。
> **實例:** 每決策一份（`ADR-NNN-<slug>.md`）
> **生成:** AI 由程式碼與文件衍生｜來源版本 git yen@8863a36c

---

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 追溯](#5-追溯)

## 1. 背景與問題

- **上下文**: 八步精靈（REQ-001）要求專案可跨瀏覽器工作階段恢復：平面圖辨識、標定、layout_json、問卷、scene_json、視角鎖定等狀態都必須落地保存，且使用者常開多個分頁或多個 session 編輯同一專案。
- **問題**: (1) 八步狀態欄位異質且高頻演進，逐步建正規化 schema 會讓每次前端欄位變動都連動 DDL；(2) 多分頁同時 `PUT /api/projects/{id}/workflow` 時，後寫者會靜默覆蓋先寫者的整包狀態（main.py:1806-1867 的寫入路徑是整包合併寫入）。
- **驅動因素/約束**:
  - API 每次以完整 workflow／project ID 讀寫，無依家具物件或事件查詢的正式需求（POSTGRESQL_PROJECT_STORE_PHASE3.md:125）。
  - 幾何真相只有一套（NFR-004）：保存層不得成為第二套幾何結構。
  - Pilot 階段單機部署，需可離線、零外部依賴啟動（ProjectStore 以 SQLite 檔案落地，project_store.py:78、84）。
  - 損壞的顯示字串曾使快照無限膨脹，需要大小預算（`_compact_workflow_value` docstring，project_store.py:52）。

## 2. 考量的選項

### 選項一: 單一 workflow JSON 快照＋revision 樂觀鎖（現行）
- **描述**: 整個八步狀態存 `projects.workflow_json` 單欄（project_store.py:105）；更新時 `BEGIN IMMEDIATE` 內深合併（`_merge_dict`，project_store.py:18）、壓縮異常長字串（project_store.py:51-74）、序列化後檢查 `MAX_WORKFLOW_BYTES = 2MB`（project_store.py:11、224-225）；呼叫端帶 `expected_revision`，落後即拋 `ProjectVersionConflict`（project_store.py:28-33、209-213），API 轉為 409 `project_revision_conflict`（main.py:1848-1858），超額轉 413 `workflow_too_large`（main.py:1859-1866）。
- **優點**: schema 零遷移即可演進前端狀態；恢復（`GET /api/projects/{id}`）一次讀回全貌；衝突可偵測、不覆寫他人變更（ACPT-014）。
- **缺點**: 無法對狀態子欄位做 SQL 查詢或局部更新；2MB 上限要求前端剔除大型暫存資料。
- **成本/複雜度**: 低

### 選項二: 正規化拆表（project_scene_objects / scene_object_events）
- **描述**: 把 scene_json 家具物件與編輯事件拆成獨立資料表，支援局部更新與跨專案統計。
- **優點**: 可做家具級查詢、事件回放、細粒度並發。
- **缺點**: 目前無此查詢需求；拆表會製造第二套幾何真相的風險，違反 NFR-004。已被契約明文擱置：「Phase 3 不建立 `project_scene_objects` 或 `scene_object_events`」（POSTGRESQL_PROJECT_STORE_PHASE3.md:125）。
- **成本/複雜度**: 高

### 選項三: 無鎖 last-write-wins 或悲觀鎖（推測）
- **描述**: （推測——程式碼與文件無此方案的遺跡）不帶版本檢查直接覆寫，或以長時 lock 阻塞第二分頁。
- **優點**: 實作最簡（前者）；無衝突回應要處理（後者）。
- **缺點**: last-write-wins 會讓多分頁互踩靜默遺失工作（違反 golden rule「保護使用者工作」與 SCN-009）；悲觀鎖在瀏覽器分頁隨時關閉的情境下無可靠釋放時機。
- **成本/複雜度**: 低（但風險不可接受）

## 3. 決策

**選擇**: 選項一——單一 workflow JSON 快照（≤2MB）＋`revision` 樂觀鎖。

**理由**: 存取模式是「整包讀、整包合併寫」，單快照與其完全對齊；深合併讓各步驟可只送自己的增量。樂觀鎖以一個整數欄位換到「落後方收 409、不覆寫他人變更」的保證，且 `BEGIN IMMEDIATE` 使版本比對與更新成為原子操作（project_store.py:200-201 註解）；pending replay 另以 `expected_updated_at` 比對（project_store.py:214-218、main.py:1836-1839）。選項二在無查詢需求下只增加漂移面；選項三的資料遺失風險不可接受。

## 4. 後果

- **正面**: 前端狀態欄位演進零 DDL；ACPT-001（跨 session 恢復）與 ACPT-014（落後 revision 收 409 `project_revision_conflict`）皆可驗證；上傳與 render metadata 寫入沿用同一 revision 序（衝突檢查 project_store.py:269-273、367-368；上傳遞增 project_store.py:292），整專案共用一條版本序。
- **負面**: 2MB 預算是硬牆，超過即 413，前端須自行清暫存（main.py:1859-1866 的使用者訊息）；快照內欄位無 DB 層 schema 驗證，壞資料只能靠 `_compact_workflow_value` 這類事後補丁；深合併語意下「刪除欄位」需寫入覆蓋值，無法靠省略欄位達成（`_merge_dict` 只增改不刪，project_store.py:18-25）。
- **影響範圍**: `backend/server/project_store.py`（儲存實作）、`PUT /api/projects/{id}/workflow` 等專案寫入端點（main.py:1806-1867）、前端所有步驟的保存邏輯（須攜帶 `expected_revision`）、runbook [runbook-workflow-revision-conflict.md](../../06_ops/runbook-workflow-revision-conflict.md)。
- **重新評估觸發**:
  - 出現跨專案家具統計、事件回放或局部更新的正式需求（契約預留：屆時以 versioned contract 從 scene_json 衍生，POSTGRESQL_PROJECT_STORE_PHASE3.md:125）。
  - 快照常態逼近 2MB 上限，或 413 成為常見使用者路徑。
  - Phase 3 遷 PostgreSQL JSONB 落地時（**待確認**：現行程式為 SQLite `projects.sqlite3`，project_store.py:78、84；契約稱 Phase 3 改 `workflow_json JSONB`＋`SELECT ... FOR UPDATE`（POSTGRESQL_PROJECT_STORE_PHASE3.md:20、78），且 migration 腳本目前不存在於 repository（POSTGRESQL_PROJECT_STORE_PHASE3.md:9-12、91-98））——快照與樂觀鎖模型契約上保留不變，仍應回頭驗證本決策。

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-08-11 | （待人工核准） | AI 衍生補記，尚未經 owner 審核 |

## 5. 追溯

| 項目 | ID |
| :--- | :--- |
| 觸發來源 | REQ-001、NFR-002（快照 ≤2MB＋樂觀鎖）、FR-001（ProjectStore 深合併保存／恢復） |
| 影響範圍 | ACPT-001、ACPT-014；SCN-001、SCN-009；[api_spec.md](../../04_design/api_spec.md) §2 並發控制、[db_design.md](../../04_design/db_design.md)、[runbook-workflow-revision-conflict.md](../../06_ops/runbook-workflow-revision-conflict.md) |
| 取代關係 | 無 |
