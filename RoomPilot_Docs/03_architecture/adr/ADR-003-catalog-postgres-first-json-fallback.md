# ADR-003: 家具 catalog 以 PostgreSQL view 優先，DB 失敗必須可見，僅顯式設定才回退 JSON

> **狀態:** 已接受（AI 衍生，待人工核准） | **日期:** 2026-08-11 | **Owner／決策者:** Kai（`backend/catalog/`、SQL owner）＋ Bella（`backend/server/` FastAPI adapter owner），依 docs/TEAM_AI_OWNERSHIP.md
> **語域:** L2（橋接）
> **實例:** 每決策一份（`ADR-NNN-<slug>.md`）
> **定位宣告:** 本文件回答「第 6 步家具 catalog 為何以 PostgreSQL view `roompilot.furniture_catalog_current` 為預設唯一來源、為何拒絕自動 failover、JSON 備援的合法使用條件」；不包含資料表欄位設計（見 [../../04_design/db_design.md](../../04_design/db_design.md)）、API 契約（見 [../../04_design/api_spec.md](../../04_design/api_spec.md)）與 DB 斷線操作步驟（見 [../../06_ops/runbook-catalog-db-unavailable.md](../../06_ops/runbook-catalog-db-unavailable.md)）。
> **生成:** AI 由程式碼與文件衍生（既成決策補記）｜來源版本 git yen@8863a36c

---

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 追溯](#5-追溯)

## 1. 背景與問題

- **上下文**: 8,675 件官方家具（REQ-013）最初以已驗證 JSON 檔交付；Phase 1 起 Kai 把 catalog 匯入 PostgreSQL，正式讀取面收斂為 view `roompilot.furniture_catalog_current`（postgres_repository.py:20）。問卷推薦、方案生成與家具庫 UI 全部消費同一份 payload cache（main.py:909-926）。
- **問題**: 同一系統存在兩份 8,675 筆來源（PostgreSQL 與 JSON）。若容許執行期悄悄切換來源，問卷與 scene 生成的家具資料會在使用者不知情下改變，且 DB 資料異常（缺筆、斷線）會被 JSON 遮蔽而無人發現（main.py:911-916 docstring 明言此風險）。
- **驅動因素/約束**:
  - 家具資料的 source of truth 屬 Kai 的 PostgreSQL（docs/TEAM_AI_OWNERSHIP.md：「Kai 資料庫為第 6 步家具主來源」）。
  - filter/count/facet/pagination 必須下推 SQL，不得整包載入 Python 再篩（postgres_repository.py:1-5、Phase 1 契約驗收清單）。
  - Web server 在沒有 PostgreSQL 的機器上仍須可啟動供離線開發（postgres_catalog.py:237 註解）。
  - inactive／quarantine 資料不得進正式 API（NFR-005）。

## 2. 考量的選項

### 選項一: 維持已驗證 JSON 為唯一來源
- **描述**: 沿用 Phase 1 之前的現狀：`_merged_furniture_catalog_cached()` 讀 repo 內 JSON，全部過濾在 Python 進行。
- **優點**: 零部署依賴、離線可跑、資料隨版控可追溯。
- **缺點**: 8,675 筆全載入記憶體再逐筆篩選；資料更新要重新 commit JSON；無法與 Phase 2 CRUD／Phase 4 runtime catalog 匯入流程銜接；與「Kai 資料庫為主來源」的責任分工矛盾。
- **成本/複雜度**: 低（但技術債高）

### 選項二: PostgreSQL 優先、失敗自動 failover 到 JSON
- **描述**: DB 可用走 SQL，任何失敗（斷線、driver 缺失）自動改讀 JSON，使用者無感。早期曾存在 `auto → JSON` 行為，Phase 5 明文移除（POSTGRESQL_CATALOG_READ_PHASE1.md:97）。
- **優點**: 可用性最高，前端永遠拿得到資料。
- **缺點**: DB 故障被靜默吞掉——問卷與方案生成的資料來源在底下換掉而無人察覺（main.py:913-915 docstring 指明拒絕理由）；兩來源若有 drift（如 active 集合差異）會產出不一致的設計方案。
- **成本/複雜度**: 中

### 選項三（採用）: strict PostgreSQL 預設＋失敗可見＋顯式 JSON 離線模式
- **描述**: `ROOMPILOT_CATALOG_PROVIDER` 未設定即為 `postgres` strict mode（postgres_repository.py:199-204 預設值 `"postgres"`）；DB／driver／view 不可用時家具 API 依契約回 503，不混用 JSON（README:299-300、POSTGRESQL_CATALOG_READ_PHASE1.md:16、85）；狀態隨時可由 `GET /api/catalog/status` 查見（main.py:3144-3146、postgres_catalog.py:224-238）；只有 `.env` 明確設 `ROOMPILOT_CATALOG_PROVIDER=json`（或 `local`/`fallback`）才走 JSON（postgres_repository.py:202-203、README:302-304）。
- **優點**: 單一 source of truth、失敗可診斷、離線開發仍有明確出口。
- **缺點**: 正式模式對 DB 有硬依賴；開發者首次啟動必須先完成匯入或明確選 JSON。
- **成本/複雜度**: 中

## 3. 決策

**選擇**: 選項三。

**理由**: 選項一與 SQL 下推、CRUD、runtime catalog 各 Phase 的既定路線衝突；選項二把資料完整性風險轉嫁給看不見的靜默切換，違反「DB 失敗必須可見」的底線（main.py:911-916）。選項三以三道防線落地：(1) provider 預設 strict `postgres`；(2) postgres 模式回傳筆數必須等於 `OFFICIAL_CATALOG_COUNT`（8,675）才採用 DB 結果（main.py:917-920，ACPT-012）；(3) `load_catalog` 空結果即 raise `postgres_catalog_empty`、連線失敗正常拋錯（postgres_catalog.py:205-221），失敗態由 `/api/catalog/status` 回報 `{"provider": "json_fallback", "available": False, "reason": ...}`（postgres_catalog.py:229-238）。

## 4. 後果

- **正面**: 問卷、方案生成、家具庫三個消費端永遠讀同一顯式選定的來源（main.py:909-926 的 `lru_cache` 以 provider 為 key）；DB 資料異常在第 6 步立即暴露而非潛伏；離線 demo 路徑仍存在且可審計（`.env` 一行可見）。
- **負面**: 正式環境多一個必須維運的依賴（PostgreSQL＋匯入流程）；payload 為 process-lifetime `lru_cache`，重新匯入資料後需重啟 server 才可見（README:318 稱 Phase 5 已移除此 cache，與 main.py:909-926 現行程式不符——待確認）。
- **影響範圍**: `backend/server/main.py`（consumer adapter，Bella）、`backend/catalog/postgres_repository.py` 與 `scripts/sql/`（producer，Kai）、`backend/server/postgres_catalog.py`（相容 shim，新程式應直接引用 repository）、第 6 步前端家具庫（scene_v2.js:9052 讀 `/api/catalog/status`）。
- **重新評估觸發**:
  - 官方 catalog 總數不再是 8,675（`OFFICIAL_CATALOG_COUNT` 需同步，否則 postgres 結果會被整批拒用）。
  - runtime 讀取面由 `furniture_catalog_current` 改為 `furniture_catalog_api_current`（postgres_repository.py:18-19 註解標明此為過渡）。
  - Phase 5「移除 process-lifetime cache、未設 provider 也 strict」全面落地時，本 ADR 的 cache 描述需覆核改寫。

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| TO-BE | Kai／Bella | 人工核准前本 ADR 為 AI 衍生補記 |

## 5. 追溯

| 項目 | ID |
| :--- | :--- |
| 觸發來源 | REQ-013、NFR-003、NFR-005；契約 docs/contracts/POSTGRESQL_CATALOG_READ_PHASE1.md |
| 影響範圍 | FR-013（`GET /api/furniture` SQL 路徑）、ACPT-012、SCN-006；[api_spec](../../04_design/api_spec.md)、[db_design](../../04_design/db_design.md)、[runbook-catalog-db-unavailable](../../06_ops/runbook-catalog-db-unavailable.md) |
| 取代關係 | 無 |
