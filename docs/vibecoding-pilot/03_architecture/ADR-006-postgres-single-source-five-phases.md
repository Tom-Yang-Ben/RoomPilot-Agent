# ADR-006: PostgreSQL 以五階段成為正式 runtime 單一真相源

> **狀態:** 已接受 | **日期:** 2026-07-26～31（契約 2026-07-27 訂版、整合 commit 2026-07-31） | **決策者:** Kai（catalog／SQL 主導）＋Bella（FastAPI）＋Django（RAG runtime），依五份契約的 owner 欄；拍板會議（未查證） | **Owner:** Kai
> **語域:** L2（橋接）
> **定位:** 一個重大決策一份；記 context、選項、決定與後果。系統全貌歸 [sad.md](sad.md)，各階段細節歸 `docs/contracts/POSTGRESQL_*`，本文件只回答「為什麼這樣選」。
> **實例:** 每決策一份（`ADR-NNN-<slug>.md`）；本則為新增，舊 `docs/vibecoding/03_architecture/adr.md` 無對應
> **生成:** 2026-08-07 由 VibeCoding_Workflow_Templates/03_architecture/adr.md 導入 | 基準 docs/vibecoding-restructure @ 1268b2b4

---

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 追溯](#5-追溯)

## 1. 背景與問題

- **上下文**: [ADR-004](ADR-004-official-catalog-master-set.md)／[ADR-005](ADR-005-catalog-import-hardening.md) 時期，伺服器執行期從 JSON＋CSV 載入記憶體、專案保存在 SQLite；PostgreSQL 只是匯入工具階段的目標，不接執行期 API。
- **問題**: 多人正式 runtime 需要一致的查詢、篩選、關聯與併發控制；JSON 逐次掃描慢（Phase 1 契約明言 `/api/furniture/{item_id}` 不再掃描整份 Python list）；雙來源（DB 失效靜默回退 JSON）會讓資料不一致無聲發生。
- **驅動因素/約束**:
  - JSON 仍適合版控、review、seed 與離線開發，不能廢除（Phase 4 契約明文）。
  - 家具 RAG 需要 pgvector 向量檢索（`docs/contracts/POSTGRESQL_FURNITURE_RAG_RUNTIME.md`）。
  - 隔離資料與家電不得進正式 API（AGENTS.md 不可違反契約）。

## 2. 考量的選項

> 選項是由五份契約與 commit 順序回推整理，未必是當時逐一討論過的方案。

### 選項一: 維持 JSON/CSV 記憶體載入＋SQLite 專案保存
- **描述**: 不動。
- **優點**: 無 DB 依賴，離線可跑。
- **缺點**: 查詢全靠 Python 掃描；多人併發與稽核無交易保障；RAG 向量檢索無落點。
- **成本/複雜度**: 低

### 選項二: 一次性切換全部資料到 PostgreSQL
- **描述**: 單一大遷移。
- **優點**: 一步到位。
- **缺點**: 風險集中；家具、runtime 語彙、專案保存、向量、單一真相源五類關注點耦合在一次交付。
- **成本/複雜度**: 高

### 選項三: 五階段分層切換，每階段獨立契約與驗收
- **描述**: Read → 管理 CRUD → 專案保存 → runtime 語彙 → 移除雙來源，各立契約。
- **優點**: 每階段可獨立驗證與回退；owner 邊界清楚。
- **缺點**: 過渡期雙來源並存，文件與程式要標明當前階段。
- **成本/複雜度**: 中

## 3. 決策

**選擇**: 選項三。五份契約（更新日期 2026-07-27，`docs/contracts/`，2026-08-07 實讀）：

| 階段 | 契約 | 範圍一句話 |
|---|---|---|
| Phase 1 | `POSTGRESQL_CATALOG_READ_PHASE1.md` | `/api/furniture` 讀路徑改走 PostgreSQL，postgres 模式失敗回 503 不混用 JSON |
| Phase 2 | `POSTGRESQL_CATALOG_CRUD_PHASE2.md` | 管理者家具 CRUD（軟刪除、交易、稽核）；公開 API 保持唯讀 |
| Phase 3 | `POSTGRESQL_PROJECT_STORE_PHASE3.md` | 專案與 render metadata 從 SQLite 搬到 PostgreSQL（JSONB），503 不回寫 SQLite |
| Phase 4 | `POSTGRESQL_RUNTIME_CATALOG_PHASE4.md` | 風格色卡、材質、裝修單價、隔離區入庫；JSON 保留為版控／seed |
| Phase 5 | `POSTGRESQL_SINGLE_SOURCE_PHASE5.md` | 移除雙來源：禁止「PostgreSQL error → JSON fallback → HTTP 200」 |

整合 commit：`e1e22ddf`（2026-07-31 feat: 整合 Kai 的 PostgreSQL、家具 RAG 與工程報告功能，author ben）。向量與 RAG runtime 另見 `POSTGRESQL_FURNITURE_EMBEDDINGS.md` 與 `POSTGRESQL_FURNITURE_RAG_RUNTIME.md`（2026-07-29，Django）。

**現行碼複核（2026-08-07 實測）**：

- 家具型錄 provider 預設即 strict postgres：`catalog_provider_mode()` 預設 `"postgres"`，只有明確設 `json/local/fallback` 才走 JSON（`backend/catalog/postgres_repository.py:201-206`）。
- runtime 語彙 provider 同樣預設 strict postgres（`backend/catalog/runtime_catalog_repository.py:48-61`）。
- 專案保存 provider 程式碼預設 `sqlite`，由 `.env` 的 `ROOMPILOT_PROJECT_STORE_PROVIDER` 明確切 postgres，無靜默 fallback（`backend/server/project_store.py:651-671`，`build_project_store` docstring 明言 without silent fallback）。
- 三種 503 錯誤碼皆已落地：`postgres_catalog_unavailable`（main.py:517-521）、`project_store_unavailable`（main.py:298-305）、`runtime_catalog_unavailable`（main.py:318-327）。

## 4. 後果

- **正面**: 正式 runtime 單一真相源；資料庫失效顯式 503 而非靜默舊資料；pgvector 供家具 RAG（`roompilot.furniture_catalog_current` view 為第 6 步優先來源，AGENTS.md 契約）。
- **負面／已知不一致（2026-08-07 盤點）**:
  - README.md:246-247 仍寫「若…資料庫暫時不可連線，會自動使用已驗證 JSON 備援」、README.md:231 稱 JSON「目前為 API 與本機開發的預設資料來源」——與現行碼 strict postgres 預設＋503 行為**矛盾，README 待修**。
  - 工作階段記錄（repo 外）：本機 PostgreSQL 17.10＋pgvector 0.8.2、三個 provider 已切 postgres；終端環境變數 `ROOMPILOT_*_PROVIDER` 會蓋過 `.env`。本輪 `.env`／psql 不可讀取，**未複核**。
  - 契約文件筆數殘留 9,349（見 [ADR-004](ADR-004-official-catalog-master-set.md) 後果段）。
  - 離線開發需明確設 `ROOMPILOT_CATALOG_PROVIDER=json`，新成員未設會在無 DB 機器上拿到 503。
- **影響範圍**: `backend/catalog/`、`backend/server/`（保存與 health）、`backend/spatial_data/rag/`、`scripts/sql/`、部署環境變數。
- **重新評估觸發**: 多節點部署（連線池與 migration 策略）；provider 預設值變動；Phase 5 之後若出現任何新的 fallback 需求。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-08-07 | VibeCoding Pilot 導入 | 五契約實讀、provider 預設與 503 行為於現行碼複核；README 矛盾與 .env 未複核如實標註 |

## 5. 追溯

| 項目 | ID |
| :--- | :--- |
| 觸發來源 | FR-CATALOG-01（postgres 單一真相源與 503 行為，srs §1.4）、NFR-可用性-01（不靜默混用資料）、NFR-效能-01（查詢效能動機；srs §2 已定編、門檻仍 TO-BE）；「雙來源資料不一致」動機落地於 FR-CATALOG-01 與 Phase 5 契約；`docs/contracts/POSTGRESQL_CATALOG_READ_PHASE1.md` 問題陳述 |
| 影響範圍 | `docs/contracts/POSTGRESQL_*` 全部七份、db_design、api_spec 錯誤碼、deployment_and_operations 環境變數表 |
| 取代關係 | Phase 5 取代 ADR-004 時期「執行期從 JSON+CSV 載入、伺服器不連 Postgres」的過渡狀態；無舊編號對應 |
