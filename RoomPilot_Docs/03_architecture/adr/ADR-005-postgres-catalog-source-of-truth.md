# ADR-005: PostgreSQL view 為家具型錄唯一權威，JSON 只是降級路徑 (PostgreSQL View as the Single Catalog Source of Truth) - RoomPilot

> **狀態:** 已接受（現況追認，待 owner 核准） ｜ **日期:** 2026-08-12 ｜ **決策者:** Kai（catalog／SQL）＋ Bella（FastAPI），待產品 owner 於 [`requirements_tracker.xlsx`](../../../VibeCoding_Workflow_Templates/01_requirements/requirements_tracker.xlsx) ③Gate 簽核
> **語域:** L2（橋接） ｜ **實例:** 每決策一份
>
> **本文件回答**：第 6 步的家具資料為什麼以 PostgreSQL view 為權威、JSON 為什麼只能是顯式離線路徑、隔離區資料為什麼永不外洩，以及被放棄的替代方案是什麼。
> **本文件不含**：view 欄位與索引（去 [`db_design.md`](../../04_design/db_design.md)）、端點欄位契約（去 [`api_spec.md`](../../04_design/api_spec.md)、[`openapi-project-workflow-v1.yaml`](../../04_design/openapi-project-workflow-v1.yaml)）、資料庫掛掉的處置步驟（去 [`runbook-catalog-db-unavailable.md`](../../06_ops/runbook-catalog-db-unavailable.md)）、系統全貌（去 [`sad.md`](../sad.md)）。
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、2026-08-12 工作樹。行號隨程式碼演進，衝突時以原始碼為準。

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 執行計畫](#5-執行計畫)
- [6. 追溯](#6-追溯)

## 1. 背景與問題

- **上下文**：第 6 步的每一件家具都要有正式 ID、尺寸、GLB 與三視角圖；這些資料同時存在於 Kai 的 PostgreSQL `roompilot` schema 與版控 JSON／CSV。兩份都可讀，就會出現「同一個 furniture_id 在兩個地方長得不一樣」的分裂。
- **問題**：型錄不只餵瀏覽頁。同一份資料被 `_furniture_payload_cache()` 供給篩選（`main.py:1385`）、明細（`main.py:3303`）與軟裝自動配置（`main.py:3736`），亦即它直接決定 `scene_json` 裡放進去的是什麼東西。來源一旦在請求中途換手，使用者看到的家具就會在無提示的情況下改變。
- **驅動因素／約束**：
  - 型錄約 8,675 筆，FastAPI 不得為了篩選、計數、facet 或分頁把整份載入記憶體（`postgres_repository.py:1-6`）。
  - 隔離區（`unmatched_cloud_furniture` 1,514 筆、`sf3d_legacy` 1,509 筆）一律不得出現在任何 API 或場景，也不得替其猜測 `model_url`（`backend/catalog/AGENTS.md:6-9`）。
  - Pilot 是單機部署，開發與離線展示場合不保證有 PostgreSQL；`pytest` 現況即有多筆測試因本機未啟資料庫而失敗（[`srs.md`](../../01_requirements/srs.md) NFR-024）。
  - `backend/catalog/` 是 Kai 的邊界，Bella 與 Yen 不得直接改寫型錄（`backend/catalog/AGENTS.md:12`）。

## 2. 考量的選項

### 2.1 選項 A：版控 JSON／CSV 為唯一權威，PostgreSQL 只當匯入暫存

- **描述**：保留 `cloud_catalog.build_official_catalog()` 這條檔案管線（`cloud_catalog.py:58-96`）作為正式來源，資料庫只服務向量檢索。
- **優點**：無外部相依、可完全離線、資料變更走 Git review、載入時即驗證（總數 8,675、ID 唯一、與交付 manifest 的 ID 集合一致）。
- **缺點**：篩選、facet 與分頁只能在 Python 端整包掃描，違反 `postgres_repository.py:1-6` 的明文約束；型錄與 pgvector 檢索被迫分處兩個世界，無法用 SQL join 收斂；資料更新一律要重啟或清 cache。
- **成本／複雜度**：低（維持現狀），但天花板明確。
- **不選的理由**：把「效能與檢索一致性」的問題永久留在應用層。

### 2.2 選項 B：嚴格 PostgreSQL，完全刪除 JSON 路徑

- **描述**：Phase 5 契約的原案——SQL 異常時家具 API 直接回 `503 postgres_catalog_unavailable`，禁止任何檔案接手（`docs/contracts/POSTGRESQL_SINGLE_SOURCE_PHASE5.md:28-34`）。
- **優點**：故障可見，來源絕不分裂，最符合 DEC-017 的誠實邊界。
- **缺點**：Pilot 單機展示與無資料庫的開發環境會整段不可用；`AGENTS.md:55` 現行規則反而明文允許回退已驗證 JSON，兩者需先由 owner 裁決。
- **成本／複雜度**：中（須補 503 分支與全部呼叫點的錯誤傳遞）。
- **不選的理由**：**此選項尚未實作**，`postgres_catalog_unavailable` 這個字串在整個 repo 只出現於契約文件、程式碼零命中（2026-08-12 全域搜尋）。列為 OPEN-06。

### 2.3 選項 C：雙寫鏡像（每次匯入同步產生 runtime JSON 熱備）

- **描述**：匯入器寫 PostgreSQL 的同時輸出一份 runtime 快照檔，資料庫失效時自動接手。
- **優點**：故障轉移無感。
- **缺點**：兩份可寫來源必然漂移；隔離區過濾規則要在兩條管線各實作一次，`tests/test_cloud_quarantine.py:33-42` 的零外洩保證因此加倍脆弱。
- **成本／複雜度**：高。
- **不選的理由**：用一個新的分裂來源，去解決分裂來源造成的問題。

## 3. 決策

**選擇**：選項 B 的資料權威 ＋ 選項 A 的顯式離線路徑——view 為唯一權威，JSON 需**明確設定**才啟用，不是自動故障轉移。

**理由與現行實作**：

| 決策點 | 現行行為 | 佐證 |
| :--- | :--- | :--- |
| 權威來源 | `_VIEW = "roompilot.furniture_catalog_current"`，全部查詢 `WHERE kind = 'furniture'` | `postgres_repository.py:18-20,645,663,678,707,784-785` |
| provider 決策 | `ROOMPILOT_CATALOG_PROVIDER ∈ {json,local,fallback}` → json；其餘（含未設定）→ postgres | `postgres_repository.py:199-208` |
| 降級不得靜默 | 函式 docstring 明訂「資料庫失敗必須可見，不得在使用者底下悄悄換掉問卷與場景資料」 | `main.py:909-916` |
| JSON 路徑仍受驗證 | 離線分支走 `load_official_catalog()`，載入時強制 8,675 筆、ID 唯一、與 manifest ID 集合一致，不符即 `ValueError` | `main.py:457-462`；`cloud_catalog.py:18,58-96` |
| 隔離區零外洩 | `web_policy == "excluded_until_verified"`，1,514 筆隔離 ID 與線上有模型集合必須 disjoint | `tests/test_cloud_quarantine.py:21-42` |
| 連線邊界 | 連線池 1–8、連線逾時 3 秒；缺驅動拋 `postgres_driver_unavailable` | `postgres_repository.py:211-223,230-245` |
| 狀態誠實揭露 | `/api/catalog/status` 只回 provider、筆數、資產統計與 `reason` 型別名，不含任何連線設定；異常時 `available=false` | `main.py:3095-3146`；`postgres_repository.py:748-759,823-850` |
| 空表不當可用 | view 查得 0 列即 `RuntimeError("postgres_catalog_empty")` | `postgres_repository.py:673-683` |

## 4. 後果

### 4.1 得到什麼

- 篩選、計數、facet 與分頁全在 SQL 完成（`postgres_repository.py:456-471,686-745`），`GET /api/furniture` 的 `page_size` 1–80 邊界不需整包載入（`main.py:3229-3279`，NFR-006）。
- 型錄與 pgvector 檢索共用同一批 `item_id`，第 5 步檢索排序的候選必然存在於第 6 步型錄（FR-044、FR-047）。
- 資料庫掛掉時 Web 服務不整體停擺，`/api/catalog/status` 回 `available=false` ＋ reason（NFR-008）；啟動期暖機失敗亦只印訊息不擋 app 啟動（`main.py:3322-3328`）。
- 隔離區規則有可執行的守護測試，不是紙上規定（ACPT-040）。

### 4.2 付出什麼

- **等值閘門是一顆未拆的引信**：`main.py:917-921` 只有在 `len(items) == OFFICIAL_CATALOG_COUNT`（8_675，`cloud_catalog.py:18`）時才採用 PostgreSQL 結果，否則**靜默**落回 JSON。程式讀的是 `furniture_catalog_current`，但 `README.md:282` 與 `docs/TEAM_AI_OWNERSHIP.md:59` 記載的 8,076 筆 active 是 `furniture_catalog_api_current` 的數字——兩個 view 名稱不同，此閘門是否會誤觸發，未連 live DB 無法判定（OPEN-06）。
- **契約承諾的 503 尚未實作**：`postgres_catalog_unavailable` 在程式碼零命中；DB 不可用時 `load_catalog()` 拋出的例外沒有被轉成 503，`/api/furniture` 的實際狀態碼未經驗證（OPEN-06）。
- **契約與程式對 view 名稱不一致**：契約表列 `roompilot.furniture_catalog_api_current`（`docs/contracts/POSTGRESQL_SINGLE_SOURCE_PHASE5.md:61`），程式用相容 view `furniture_catalog_current` 並註明「等 Django 接手 api_current migration 前先留在這裡」（`postgres_repository.py:18-20`）。
- **契約承諾的 hot refresh 與程式不符**：契約寫 PostgreSQL 分支不使用 process-lifetime cache（`docs/contracts/POSTGRESQL_SINGLE_SOURCE_PHASE5.md:114-117`），實際 `_furniture_payload_for_provider` 與 `_furniture_payload_cache` 都掛 `lru_cache`（`main.py:909,924-926`），資料更新後不重啟看不到。
- **上位規則彼此打架**：`AGENTS.md:55` 允許「資料庫不可用時回退已驗證 JSON」，Phase 5 契約則把 `PostgreSQL error → JSON fallback → HTTP 200` 列為禁止流程（`docs/contracts/POSTGRESQL_SINGLE_SOURCE_PHASE5.md:28-34`）。哪一份是權威，待 owner 裁決。

### 4.3 什麼時候該重評

| 觸發條件（可觀測） | 為什麼要重評 |
| :--- | :--- |
| `SELECT COUNT(*) FROM roompilot.furniture_catalog_current WHERE kind='furniture'` 不等於 8,675 | `main.py:919` 的等值閘門會讓正式資料被 JSON 靜默取代，DEC-007 的「來源可信」即失效 |
| Django 接手 `furniture_catalog_api_current` migration | `postgres_repository.py:18-20` 註解的相容前提消失，`_VIEW` 必須改指並重驗全部查詢 |
| DEC-014 核准 Pilot 走多人或外網 | 靜默降級不再可接受，須落實選項 B 的 503 分支並更新 [`runbook-catalog-db-unavailable.md`](../../06_ops/runbook-catalog-db-unavailable.md) |
| 出現第二個消費型錄的服務（非本 FastAPI） | JSON 離線路徑不再能保證兩端看到同一份資料，須改為純 SQL |
| 隔離區筆數變動（現為 1,514／1,509）或 `tests/test_cloud_quarantine.py` 需改參數 | 零外洩保證的基準線移動，須重新確認過審流程而非就地改斷言 |

## 5. 執行計畫

1. **裁決 OPEN-06**：owner 選定 `AGENTS.md:55` 或 Phase 5 契約其一為權威；結論寫回 [`requirements_tracker.xlsx`](../../../VibeCoding_Workflow_Templates/01_requirements/requirements_tracker.xlsx) ②決策沿革。
2. **量測等值閘門**：連 live DB 取 `furniture_catalog_current` 的 furniture 筆數，確認 `main.py:919` 是否正在誤觸發；結果登記於 [`test_plan.md`](../../05_qa/test_plan.md) TC-037。
3. **若裁決為 strict**：實作 503 `postgres_catalog_unavailable`、拆除等值閘門的靜默 fallback、補一條 DB 中斷的整合測試。
4. **若裁決為允許 fallback**：把降級改為**顯式可見**（回應中標示 provider 與降級原因），並更新 Phase 5 契約的禁止流程段落。
5. **收斂 view 名稱與 hot refresh 落差**：兩者擇一——改程式對齊契約，或改契約對齊程式；不得兩份並存。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-08-12 | 待 owner | 現況追認；OPEN-06 未決前不得視為已核准規格 |

## 6. 追溯

| 項目 | ID／文件 |
| :--- | :--- |
| 觸發來源 | DEC-007、DEC-017（[`brd.md`](../../01_requirements/brd.md)）；FR-039–045、NFR-006–008（[`srs.md`](../../01_requirements/srs.md) §2.5、§3） |
| 驗收綁定 | ACPT-036–040（[`prd.md`](../../01_requirements/prd.md) §3.6）；SCN-024 |
| 影響範圍 | MOD-CAT、MOD-SQL（owner：Kai）；MOD-SRV-SCENE（Bella）；`postgres_repository.py`、`cloud_catalog.py`、`main.py` 型錄段 |
| 契約文件 | `docs/contracts/POSTGRESQL_SINGLE_SOURCE_PHASE5.md`、`docs/contracts/POSTGRESQL_CATALOG_READ_PHASE1.md`、`backend/catalog/AGENTS.md`、[`AGENTS.md`](../../../AGENTS.md) §不可違反的契約 |
| 下游 | [`sad.md`](../sad.md)、[`db_design.md`](../../04_design/db_design.md)、[`api_spec.md`](../../04_design/api_spec.md)、[`test_plan.md`](../../05_qa/test_plan.md)、[`runbook-catalog-db-unavailable.md`](../../06_ops/runbook-catalog-db-unavailable.md)（RB-001） |
| 相關 ADR | [`ADR-008`](./ADR-008-rag-retrieval-only-offline-models.md)（共用同一批 `item_id`）、[`ADR-006`](./ADR-006-appliances-render-context-only.md)（家電不進型錄擺設） |
| 待確認 | OPEN-06：`main.py:919` 等值閘門與 view 實際筆數是否一致；契約承諾的 503 `postgres_catalog_unavailable` 是否曾實作；`AGENTS.md:55` 與 Phase 5 契約的 fallback 立場衝突 |
