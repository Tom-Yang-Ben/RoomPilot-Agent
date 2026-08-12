# Runbook RB-001：家具型錄資料庫不可用 (Catalog Database Unavailable) - RoomPilot

> **版本:** v1.0 ｜ **更新:** 2026-08-12 ｜ **狀態:** 草稿（待 owner 核准）
> **Owner:** Kai（`backend/catalog/`、`scripts/sql/`、PostgreSQL）＋ Bella（`backend/server/` adapter），依 [`docs/TEAM_AI_OWNERSHIP.md`](../../docs/TEAM_AI_OWNERSHIP.md):12,21,25,27
> **語域:** L3（工程）
> **實例:** 每故障症狀一份（本檔＝症狀「第 6 步無法建立配置／型錄回報不可用」）
>
> **本文件回答**：型錄資料庫連不上時，怎麼在最短路徑上判斷是「服務沒起來、設定錯、驅動缺、view 空」哪一種，怎麼緩解，怎麼確認已恢復。
> **本文件不含**：為什麼 view 是唯一權威與 JSON 只能是顯式離線路徑（去 [`ADR-005`](../03_architecture/adr/ADR-005-postgres-catalog-source-of-truth.md)）、view 欄位與匯入流程（去 [`db_design.md`](../04_design/db_design.md)）、端點欄位契約（去 [`api_spec.md`](../04_design/api_spec.md)）、部署與環境全貌（去 [`deployment_and_operations.md`](./deployment_and_operations.md)）、家具擺不下（去 [`runbook-placement-blocked.md`](./runbook-placement-blocked.md)，RB-007）、GLB 載不到（去 [`runbook-glb-asset-missing.md`](./runbook-glb-asset-missing.md)，RB-008）。
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、2026-08-12 工作樹。行號隨程式碼演進，衝突時以原始碼為準。

## 目錄

- [1. Symptoms（症狀）](#1-symptoms症狀)
- [2. Impact（影響）](#2-impact影響)
- [3. Possible Causes（可能原因）](#3-possible-causes可能原因)
- [4. Diagnosis（診斷步驟）](#4-diagnosis診斷步驟)
- [5. Mitigation（短期緩解）](#5-mitigation短期緩解)
- [6. Recovery（恢復確認）](#6-recovery恢復確認)
- [7. Escalation（升級路徑）](#7-escalation升級路徑)
- [8. 追溯](#8-追溯)

## 1. Symptoms（症狀）

**無告警來源。** 本 repo 無監控、無 dashboard、無 alert 規則、無 on-call 輪值；本故障目前只靠使用者回報或下列畫面／API 回應被發現。

| 症狀 | 觀察位置 | 佐證 |
| :--- | :--- | :--- |
| 第 5 步按「確認全屋需求」後停住不進第 6 步，錯誤區顯示「目前無法連線 Kai 家具型錄，尚未取得所選家具的可用 GLB，因此不能建立可靠的 2D+3D 配置。」 | 瀏覽器 | `scene_v2.js:9112-9119` |
| 同畫面展開說明區塊並附「系統回報：`<reason>`」 | 瀏覽器 `#requirements-generation-help` | `scene_v2.js:9044-9048,9116`；`scene.html:595-596` |
| 狀態列紅字「Kai 家具型錄尚未就緒，已保留問卷答案並停止建立配置。」（問卷答案不會遺失） | 瀏覽器 | `scene_v2.js:9117-9118` |
| `GET /api/catalog/status` 的 `catalog_provider` 回 `available:false`、`ready:false`、`reason:"<例外類名>"` | API | `postgres_repository.py:842-850`；`main.py:3095-3146,3144-3146` |
| `GET /api/furniture` 回 500（例外自 `load_catalog()` 直接上拋，未轉成 503） | API | `main.py:917-921,1384-1385,3229-3279`；`postgres_repository.py:673-683` |
| uvicorn console 出現 `[RoomPilot] catalog cache warmup skipped: <例外>`（只在啟動時印一次） | 終端機 | `main.py:3322-3328` |

**3am 陷阱**：`reason` 是 `type(exc).__name__`，不是訊息字串（`postgres_repository.py:847`）。缺驅動時你看到的是 `RuntimeError`，**不會**看到 `postgres_driver_unavailable`（該字串只在例外訊息內，`postgres_repository.py:233-234`）。另外，live 路徑是 `backend/catalog/postgres_repository.py`（`main.py:106-109`），provider 名只會是 `kai_postgresql` 或 `json_offline`；`json_fallback` 屬未接線的 `backend/server/postgres_catalog.py:224-238`，舊文件與舊 runbook 指的是它，**看到它就是文件過時，不是程式行為**。

## 2. Impact（影響）

| 項目 | 內容 |
| :--- | :--- |
| **受影響功能** | 第 6 步配置建立完全阻斷（前端前置檢查直接擋，`scene_v2.js:9050-9064,9112-9119`）；家具瀏覽 `/api/furniture` 500；連帶第 7、8 步無法開始 |
| **仍可運作** | 第 1–5 步（建案、上傳、辨識、空間確認、問卷填寫）與既有專案讀取；FastAPI 不整體停擺（NFR-008），啟動期暖機失敗也不擋 app 啟動（`main.py:3322-3328`） |
| **受影響使用者** | 單機 Pilot 全部使用者（無多租戶、無分區） |
| **嚴重程度判定** | 第 6 步不可用＝本 Pilot 最高嚴重度（主要交付價值中斷）。**升級為 incident 的門檻、回應時限與覆盤義務本 repo 無明文政策 → 待確認（OPEN-02 承接處：[`deployment_and_operations.md`](./deployment_and_operations.md)）** |

## 3. Possible Causes（可能原因）

按發生機率排序（`reason` 欄＝ `/api/catalog/status` 會回的字串）：

| # | 原因 | reason | 佐證 |
| :--- | :--- | :--- | :--- |
| 1 | PostgreSQL 服務未啟動或網路不可達；連線逾時預設 3 秒 | `OperationalError` | `postgres_repository.py:211-223`（`DB_CONNECT_TIMEOUT` 預設 `3`） |
| 2 | `.env` 或環境變數的 `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD` 錯誤（環境變數優先於 repo 根 `.env`） | `OperationalError`／`ProgrammingError` | `postgres_repository.py:181-196,211-223`；`main.py:114`（`PROJECT_DIR`＝repo 根） |
| 3 | venv 未安裝 `psycopg2` | `RuntimeError` | `postgres_repository.py:230-234` |
| 4 | 連線池耗盡（`DB_POOL_MIN=1`／`DB_POOL_MAX=8`，NFR-007）或連線未歸還 | `PoolError` | `postgres_repository.py:238-260` |
| 5 | view `roompilot.furniture_catalog_current` 不存在或改名 | `UndefinedTable` | `postgres_repository.py:18-20,784-785,801-812` |
| 6 | view 存在但 furniture 0 列 → `available` 為 false（`count > 0` 判定）；整包載入另拋 `postgres_catalog_empty` | 無 reason，`available:false` | `postgres_repository.py:823-826,673-683` |
| 7 | **同源但不同症狀**：view 筆數 ≠ 8,675 時 `/api/catalog/status` 仍可能 `available:true`，家具 payload 卻已靜默落回 JSON | 無 | `main.py:917-921`；`cloud_catalog.py:18`（OPEN-06） |

## 4. Diagnosis（診斷步驟）

伺服器 base URL 為 `http://127.0.0.1:8002`（`README.md:49,63`；被占用時見 `README.md:68`）。以下逐步照跑，第一個回傳異常的步驟就是分歧點。

```powershell
# 1. 型錄探針（可直接在瀏覽器開）：http://127.0.0.1:8002/api/catalog/status
curl.exe -s http://127.0.0.1:8002/api/catalog/status
#   catalog_provider.provider = "json_offline"  → 有人設了 ROOMPILOT_CATALOG_PROVIDER，非故障，跳 §5.3
#   catalog_provider.available = false + reason → 照 reason 對 §3 表，往下走
#   available = true 但 count != 8675           → 原因 7，跳 §5.4

# 2. reason = OperationalError → PostgreSQL 服務在不在
Get-Service -Name "postgresql*"

# 3. reason = RuntimeError → 驅動在不在（缺驅動只會顯示 RuntimeError）
.\.venv\Scripts\python.exe -c "import psycopg2; print(psycopg2.__version__)"

# 4. 連線設定實際值（環境變數優先於 .env；密碼不要貼進聊天室或工單）
Get-Content D:\RoomPilot-Agent\.env | Select-String "^DB_|^ROOMPILOT_CATALOG_PROVIDER"
Get-ChildItem Env:DB_*

# 5. 用同一組設定直接打 view，確認可連、可讀、筆數
psql -h localhost -p 5432 -U postgres -d roompilot_db -c "SELECT to_regclass('roompilot.furniture_catalog_current');"
psql -h localhost -p 5432 -U postgres -d roompilot_db -c "SELECT count(*) FROM roompilot.furniture_catalog_current WHERE kind='furniture';"
#   NULL      → 原因 5（view 缺）
#   0         → 原因 6（view 空）
#   != 8675   → 原因 7（等值閘門，OPEN-06）

# 6. 確認家具 API 的實際狀態碼（500 = 例外未被轉成 503，符合 OPEN-06 的已知缺口）
curl.exe -s -o NUL -w "%{http_code}`n" "http://127.0.0.1:8002/api/furniture?page=1&page_size=1"

# 7. 看 uvicorn 終端機是否有啟動期 warmup 訊息（本專案唯一的伺服器端線索，無 log 檔）
#    [RoomPilot] catalog cache warmup skipped: <例外>
```

## 5. Mitigation（短期緩解）

1. **服務沒跑** → `Start-Service -Name "postgresql*"`，再重跑 §4 步驟 1。
2. **設定錯／驅動缺** → 修 repo 根 `.env` 的 `DB_*`（`postgres_repository.py:181-196`）；驅動缺則於 venv 安裝 `psycopg2`。
3. **DB 短期修不好、又必須繼續 demo** → **顯式**切離線 JSON（這是決策，不是自動故障轉移；`postgres_repository.py:199-208`）：在 `.env` 設 `ROOMPILOT_CATALOG_PROVIDER=json`。此時 `/api/catalog/status` 回 `provider:"json_offline"`、`available:true`、`reason:"explicit_json_mode"`（`postgres_repository.py:751-759`），JSON 路徑仍強制 8,675 筆／ID 唯一／與 manifest ID 集合一致（`main.py:456-462`；`cloud_catalog.py:58-96,67-75`）。**禁止**把 quarantine 資料補進來充數（`backend/catalog/AGENTS.md:6-9`；`tests/test_cloud_quarantine.py:23-40`）。
4. **筆數 ≠ 8,675** → 這是資料匯入問題，交 Kai 重跑 `scripts/sql/` 的交易式匯入；**不得**在伺服器端改 `main.py:919` 的常數把閘門讓過去。
5. **改完任何設定都要重啟 uvicorn**：provider 決策與家具 payload 掛在 `lru_cache` 上（`main.py:909-910,924-926`），process 不重啟看不到修復結果。

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload
   ```

6. **使用者側**：問卷答案在阻斷時已保留（`scene_v2.js:9117-9118`），恢復後請使用者重新整理 `/scene` 並再按一次「確認全屋需求」即可，不需重填。

## 6. Recovery（恢復確認）

四項全過才算恢復（對應 ACPT-037）：

```powershell
# 1. provider = kai_postgresql、available = true、ready = true、count = 8675
curl.exe -s http://127.0.0.1:8002/api/catalog/status
# 2. 家具 API 回 200 且 total 非 0
curl.exe -s -o NUL -w "%{http_code}`n" "http://127.0.0.1:8002/api/furniture?page=1&page_size=1"
# 3. 隔離區零外洩守護測試仍綠
.\.venv\Scripts\python.exe -m pytest tests/test_cloud_quarantine.py -q
```

4. 使用者側：`/scene` 第 6 步可建立方案 A／B，錯誤區與 `#requirements-generation-help` 皆已收起（`scene_v2.js:9036-9042`）。恢復判定**沒有量化基線可比對**（無延遲／錯誤率指標、無歷史 dashboard），只能以上述布林檢查為準；量化 SLA 待確認，承接 [`deployment_and_operations.md`](./deployment_and_operations.md)。

## 7. Escalation（升級路徑）

**本專案無 on-call 系統、無升級計時器、無事故追蹤工具**；下表的「管道」一律是直接聯繫該 owner。逾時門檻（例如常見的「緩解 30 分鐘無效即升級」）與事故覆盤義務本 repo 皆無政策 → 待確認；目前僅能把結論寫回 `requirements_tracker.xlsx` ②決策沿革與相關 ADR。

| 情況 | 找誰（MOD） | 管道與依據 |
| :--- | :--- | :--- |
| DB 連不上、view 缺／空、筆數不符、需重跑匯入 | Kai（MOD-CAT、MOD-SQL） | 直接聯繫；`TEAM_AI_OWNERSHIP.md:12,25,27` |
| `/api/catalog/status`、`/api/furniture` 或前端前置檢查行為與本檔描述不符 | Bella（MOD-SRV-API、MOD-WEB） | 直接聯繫；`TEAM_AI_OWNERSHIP.md:9,21,22` |
| 型錄已正常但第 6 步仍擺不出家具 | Ancai（MOD-ENG）→ 改走 [RB-007](./runbook-placement-blocked.md) | `TEAM_AI_OWNERSHIP.md:29` |
| 型錄正常但候選家具缺 GLB／三視角圖 | Kai → 改走 [RB-008](./runbook-glb-asset-missing.md) | `TEAM_AI_OWNERSHIP.md:12,26` |
| 要裁決「strict 503 vs 允許 JSON 回退」（OPEN-06） | 產品 owner ＋ Kai／Bella | [`requirements_tracker.xlsx`](../../VibeCoding_Workflow_Templates/01_requirements/requirements_tracker.xlsx) ②決策沿革；[`ADR-005`](../03_architecture/adr/ADR-005-postgres-catalog-source-of-truth.md) §5 |

## 8. 追溯

| 項目 | ID／文件 |
| :--- | :--- |
| Runbook 編號 | **RB-001**（[`srs.md`](../01_requirements/srs.md) §9.2，S6 列；索引見 [`00-registry.md`](../00-registry.md)） |
| 對應告警 | 無。本專案無監控與告警來源，觸發僅靠使用者回報或 §1 的畫面／API 回應 |
| 上游需求 | DEC-007、DEC-017；FR-040、FR-041（次要：FR-039、FR-042）；NFR-007、NFR-008 |
| 驗收與情境 | ACPT-037；SCN-024（[`prd.md`](../01_requirements/prd.md) 邊界場景「家具型錄不可用」） |
| 測試 | TC-037（[`test_plan.md`](../05_qa/test_plan.md)）；現有守護測試 `tests/test_cloud_quarantine.py:23-40` |
| 架構決策 | [`ADR-005`](../03_architecture/adr/ADR-005-postgres-catalog-source-of-truth.md)（權威與降級路徑）、[`sad.md`](../03_architecture/sad.md) |
| 影響模組 | MOD-CAT、MOD-SQL（Kai）；MOD-SRV-API、MOD-WEB（Bella）；MOD-OPS |
| 相關 runbook | [RB-007](./runbook-placement-blocked.md)、[RB-008](./runbook-glb-asset-missing.md)、[RB-004](./runbook-rag-model-cache-missing.md)（同為 PostgreSQL 相依） |
| 待確認 | **OPEN-06**：契約承諾的 `503 postgres_catalog_unavailable` 在程式碼零命中，實際為 500；`main.py:919` 的 `== 8675` 等值閘門是否與 live view 筆數一致。**本檔新增**：升級門檻／回應時限／覆盤義務無政策；`backend/server/postgres_catalog.py` 與 live 的 `backend/catalog/postgres_repository.py` 兩份 `catalog_provider_status()` 並存（前者僅 `tests/test_postgres_catalog_contract.py` 引用），舊文件引用的 `json_fallback` 為死碼字串——是否刪除待 Bella 裁決 |
