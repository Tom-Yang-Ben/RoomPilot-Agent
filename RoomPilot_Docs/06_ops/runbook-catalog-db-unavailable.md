# Runbook - catalog-db-unavailable（第 6 步家具 catalog 資料庫不可用） - RoomPilot

> **版本:** 0.1 | **更新:** 2026-08-11 | **狀態:** 草稿
> **Owner:** Kai（`backend/catalog/`、PostgreSQL）＋ Bella（`backend/server/` adapter），依 docs/TEAM_AI_OWNERSHIP.md:12、21、25（AI 衍生，人工核准前為 TO-BE）
> **語域:** L3（工程）
> **實例:** 每故障症狀一份（本檔對應 [00-registry](../00-registry.md) §4 slug `catalog-db-unavailable`）
> **定位宣告:** 本文件回答「第 6 步家具清單為空或 catalog provider 回報 `json_fallback, available=False` 時怎麼診斷與恢復」；不包含 catalog 架構決策（見 [ADR-003](../03_architecture/adr/ADR-003-catalog-postgres-first-json-fallback.md)）、DB schema（見 [db_design](../04_design/db_design.md)）與部署全貌（見 [deployment_and_operations](./deployment_and_operations.md)）。
> **生成:** AI 由程式碼與文件衍生｜來源版本 git yen@8863a36c

---

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

本專案是本機 Pilot，**無 Grafana／告警系統**；症狀來源只有使用者回報與 API 回應。

| 症狀 | 來源 | 證據 |
| :--- | :--- | :--- |
| 第 6 步家具清單為空、或問卷確認被擋（前端顯示 catalog not ready） | 使用者回報；前端 `configurationCatalogReadiness()` 讀 `/api/catalog/status`，`available === false` 即擋 | scene_v2.js:9050-9064 |
| `GET /api/catalog/status` 回 `catalog_provider: {"provider": "json_fallback", "available": false, "reason": "<例外類名>"}` | API 回應 | postgres_catalog.py:224-238、main.py:3144-3146 |
| `GET /api/catalog/status` 回 `kai_postgresql` 但 `count` ≠ 8,675 | API 回應（此時家具 payload 已改採 JSON，見 §3 原因 3） | main.py:917-921 |
| `GET /api/furniture` 拋伺服器錯誤（500） | API 回應；`load_postgres_catalog` 連線例外未被 payload 路徑捕捉 | main.py:917-918、postgres_catalog.py:205-221 |

## 2. Impact（影響）

| 項目 | 內容 |
| :--- | :--- |
| **受影響功能** | 第 6 步家具查詢／方案生成（REQ-013：家具只來自 8,675 件官方 catalog）；問卷確認進第 6 步會被前端 readiness 檢查擋下（scene_v2.js:9050-9064） |
| **受影響使用者** | 本機 Pilot 全部使用者（單機部署，無多租戶） |
| **嚴重程度判定** | 第 6 步完全不可用即為本 Pilot 最高嚴重度；第 1–5 步（上傳、辨識、標定、校正、問卷填寫）不依賴 catalog，仍可運作 |

## 3. Possible Causes（可能原因）

按發生機率排序：

1. **PostgreSQL 服務未啟動或不可連線** — `reason` 為 `OperationalError` 之類的例外類名（postgres_catalog.py:237-238；connect_timeout 預設 3 秒，postgres_catalog.py:95）。
2. **`.env` 連線設定錯誤** — `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` 讀自環境變數或專案根 `.env`（postgres_catalog.py:83-98；README:287-297 範例）。
3. **View 回傳筆數不足 8,675** — 匯入不完整或 view 內容異動；payload 路徑要求 `len(items) == OFFICIAL_CATALOG_COUNT`（8,675，cloud_catalog.py:18）才採用 DB，否則落回 JSON（main.py:917-921）。status 探針此時仍可能回 `kai_postgresql, available=true`（只檢查 `count > 0`，postgres_catalog.py:236）——所以要看 `count` 數字，不能只看 provider 名。
4. **psycopg2 driver 未安裝** — `reason: "postgres_driver_unavailable"`（postgres_catalog.py:226-229、210-211）。
5. **View 存在但 0 筆** — `load_catalog` 拋 `postgres_catalog_empty`（postgres_catalog.py:219-220）。

## 4. Diagnosis（診斷步驟）

伺服器 base URL 依實際啟動 port：README 開發指令用 `--port 8002`（README.md:49），[api_spec](../04_design/api_spec.md) §1 約定 `http://127.0.0.1:8000`。以下以 8000 示範，port 不對就換。

```powershell
# 1. 先問 status 探針：provider 是誰、available 是否 true、count 是否 8675
curl.exe -s http://127.0.0.1:8000/api/catalog/status
#    => 看 catalog_provider：
#       {"provider":"json_fallback","available":false,"reason":"..."} → 連線層問題，看 reason
#       {"provider":"kai_postgresql","available":true,"count":N}      → N != 8675 仍是故障（原因 3）

# 2. reason = OperationalError 類 → 確認 PostgreSQL 服務有沒有在跑
Get-Service -Name "postgresql*"
#    STOPPED → Start-Service 該服務名（見 §5）

# 3. reason = postgres_driver_unavailable → 確認 venv 裝了 psycopg2
.\.venv\Scripts\python.exe -c "import psycopg2; print(psycopg2.__version__)"

# 4. 確認連線設定：讀專案根 .env（環境變數優先於 .env，postgres_catalog.py:86-87）
Get-Content C:\RoomPilot-Agent\.env
#    對照必要鍵：DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD、
#    ROOMPILOT_CATALOG_PROVIDER（README.md:287-297）

# 5. 用同一組設定直接查 view 的筆數（門檻 = 8675）
psql -h localhost -p 5432 -U postgres -d roompilot_db `
  -c "SELECT count(*) FROM roompilot.furniture_catalog_current WHERE kind = 'furniture';"

# 6. 確認家具 API 本身的行為
curl.exe -s "http://127.0.0.1:8000/api/furniture?page=1&page_size=1"
#    500 → postgres 模式下連線例外直接上拋（main.py:917-918）
#    200 但 status 的 count != 8675 → 正在吃 JSON fallback payload（main.py:919-921）
```

## 5. Mitigation（短期緩解）

1. **PostgreSQL 服務沒跑** → 啟動它：

   ```powershell
   Start-Service -Name "postgresql*"
   ```

2. **設定錯誤** → 修 `C:\RoomPilot-Agent\.env` 的 `DB_*` 鍵（範本見 README.md:289-297）。
3. **DB 短時間修不好、又必須離線 demo** → 明確切 JSON 備援（這是**顯式決策**，不是預設；NFR-003、README:299-304）：

   ```dotenv
   ROOMPILOT_CATALOG_PROVIDER=json
   ```

   JSON 備援同為 8,675 筆已驗證資料（README.md:284）。**禁止**把 quarantine 資料當正式家具補進來（NFR-005、backend/catalog/AGENTS.md:6-8）。
4. **筆數不足 8,675** → 這是資料匯入問題，不要在伺服器端 hack 門檻常數；找 Kai 重新執行 `scripts/sql/` 的 transactional import（owner 分工見 §7）。
5. **上述任何一項改完都必須重啟 uvicorn**：家具 payload 與 provider 決策掛在 `lru_cache` 上（main.py:909、924-926），process 不重啟看不到修復結果。README 開發啟動指令：

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload
   ```

## 6. Recovery（恢復確認）

依序全部通過才算恢復（對應 ACPT-012）：

```powershell
# 1. status 探針：provider=kai_postgresql、available=true、count=8675
curl.exe -s http://127.0.0.1:8000/api/catalog/status

# 2. 家具 API 回 200 且 total 合理（active 家具，非 0）
curl.exe -s "http://127.0.0.1:8000/api/furniture?page=1&page_size=1"
```

3. 使用者側：重新整理 `/scene` 第 6 步，家具清單有資料、問卷確認不再被 readiness 檢查擋下（scene_v2.js:9050-9064）。
4. 若動用了 `ROOMPILOT_CATALOG_PROVIDER=json` 的緩解：DB 修復後**改回 `postgres` 並再重啟**，不得讓 JSON 模式殘留成常態（ADR-003）。

## 7. Escalation（升級路徑）

無 on-call 系統；依 docs/TEAM_AI_OWNERSHIP.md 的目錄責任直接找 owner。

| 情況 | 找誰 | 依據 |
| :--- | :--- | :--- |
| DB 服務／schema／view 筆數／匯入問題 | Kai（`backend/catalog/`、`scripts/sql/`、PostgreSQL 資料交付） | TEAM_AI_OWNERSHIP.md:12、25、27 |
| API adapter 行為（status 端點、payload cache、500/503 語意） | Bella（`backend/server/`） | TEAM_AI_OWNERSHIP.md:9、21 |
| 家具 RAG 檢索連帶異常 | Django（查詢 schema）＋ Kai（pgvector） | TEAM_AI_OWNERSHIP.md:55 |

事故結束後 48 小時內完成覆盤紀錄（正式覆盤文件依需增建）。

**待確認（文件與程式碼疑似漂移，留給人工）：**

- README:299 與 TEAM_AI_OWNERSHIP.md:61 稱 postgres 模式 DB 不可連線時家具 API「回 503」；但 yen@8863a36c 的 payload 路徑（main.py:917-921）無 503 轉換，連線例外會直接上拋成 500。
- TEAM_AI_OWNERSHIP.md:59 稱正式 API view 為 `furniture_catalog_api_current`（8,076 筆 active）；程式碼實際讀 `roompilot.furniture_catalog_current`（postgres_catalog.py:15）且門檻為 8,675 全量。
- README:318 的 Phase 5 稱已移除 process-lifetime cache；本分支程式碼仍有 `lru_cache`（main.py:909、924-926），故本 runbook 保留「重啟才生效」步驟。

## 8. 追溯

| 項目 | ID／來源 |
| :--- | :--- |
| 對應症狀登錄 | [00-registry](../00-registry.md) §4 `catalog-db-unavailable` |
| 對應 NFR | NFR-003（8,675 門檻與可見失敗）、NFR-005（quarantine 不回填） |
| 對應 ACPT | ACPT-012 |
| 對應 SCN | SCN-006 |
| 對應 ADR | [ADR-003](../03_architecture/adr/ADR-003-catalog-postgres-first-json-fallback.md) |
| 上游證據 | main.py:909-926、3095-3146；postgres_catalog.py:83-98、205-238；scene_v2.js:9050-9064；README.md:280-304 |
| 下游文件 | [deployment_and_operations](./deployment_and_operations.md)、[test_plan](../05_qa/test_plan.md) |
