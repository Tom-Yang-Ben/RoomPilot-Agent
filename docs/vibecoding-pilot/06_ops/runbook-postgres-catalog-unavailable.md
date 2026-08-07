# Runbook - PostgreSQL 型錄／專案保存不可用（503）

> **版本:** v1.0 | **更新:** 2026-08-07 | **狀態:** 活躍
> **Owner:** Kai（PostgreSQL／catalog）、Bella（FastAPI 整合）
> **語域:** L3（工程）
> **定位:** 正式 PostgreSQL 模式下資料庫失聯或未匯入時的診斷與處置；provider 環境變數錯亂另見 [runbook-provider-env-shadow.md](runbook-provider-env-shadow.md)。
> **實例:** 每故障症狀一份（`runbook-<symptom>.md`）
> **生成:** 2026-08-07 由 VibeCoding_Workflow_Templates/06_ops/runbook.md 導入 | 基準 docs/vibecoding-restructure @ 1268b2b4

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

- 第 6 步家具清單載不出來、首頁型錄統計為空，或專案存檔失敗。
- API 回 503，`detail.code` 是下列之一（各 code 的處置不同，見第 3、5 節）：
  - `postgres_catalog_unavailable` — 家具單筆／清單查詢失敗（`backend/server/main.py:517-525`）。
  - `runtime_catalog_unavailable` — style／surface／cost／家具 payload 讀不到（`backend/server/main.py:317-337`）。
  - `catalog_pool_busy` — 連線池瞬時滿載，帶 `Retry-After: 2`（同上；**不是**型錄沒匯入）。
  - `project_store_unavailable` / `project_store_busy` — PostgreSQL 專案保存失敗（`backend/server/main.py:297-314`）。
- `GET /api/health` 回 HTTP 503、`status: "unavailable"`（`backend/server/main.py:1103-1132`）。

## 2. Impact（影響）

| 項目 | 內容 |
| :--- | :--- |
| **受影響功能** | 正式 PostgreSQL 模式下：第 6 步家具選擇、風格／材質資料、成果報告費率、專案存讀全部停止 |
| **不會發生的事** | 系統**不會**靜默回退 JSON 再回 HTTP 200——Phase 5 契約明文禁止（`docs/contracts/POSTGRESQL_SINGLE_SOURCE_PHASE5.md` 「禁止流程」段） |
| **嚴重程度判定** | 單機開發環境：阻斷當前工作即為最高級；展示（demo）當下發生視同 incident |

## 3. Possible Causes（可能原因）

按發生機率排序：

1. **PostgreSQL 服務未啟動**（重開機後未自動啟動、服務當掉）。
2. **schema／view 未匯入**（新機、重灌 DB）：`roompilot.furniture_catalog_api_current` 等 view 不存在，或 `runtime_catalog_imports` 缺列（錯誤 reason 可見 `runtime_catalog_not_imported:<key>`，`backend/catalog/runtime_catalog_repository.py:95`）。
3. **連線池瞬時滿載**：`catalog_pool_busy`；池上限 `DB_POOL_MAX` 預設 24、借用等待 `DB_POOL_TIMEOUT` 預設 10 秒（`backend/catalog/postgres_repository.py:254-256`）。
4. **`.env` 的 `DB_*` 設定錯誤**：host／port／密碼；連線逾時 `DB_CONNECT_TIMEOUT` 預設 3 秒（`backend/catalog/postgres_repository.py:213-225`）。
5. **行程環境變數蓋掉 provider 設定** → 症狀相似但根因不同，改走 [runbook-provider-env-shadow.md](runbook-provider-env-shadow.md)。

## 4. Diagnosis（診斷步驟）

```powershell
# 1. 看整體健康（503 時 body 仍有完整診斷 payload）
curl.exe -s http://127.0.0.1:8002/api/health

# 2. PostgreSQL 服務是否在跑
Get-Service postgresql*

# 3. 能否連線（psql 在 PostgreSQL bin 目錄；-c 為唯讀查詢）
psql -U postgres -d roompilot_db -c "SELECT 1;"

# 4. view 是否存在（NULL = 未匯入）
psql -U postgres -d roompilot_db -c "SELECT TO_REGCLASS('roompilot.furniture_catalog_api_current');"

# 5. 資料量基準：view 應有 7,958 筆（8,557 中 599 筆 is_active=false 不進 view，
#    backend/catalog/data/README.md:14-15）
psql -U postgres -d roompilot_db -c "SELECT COUNT(*) FROM roompilot.furniture_catalog_api_current;"

# 6. Phase 4 runtime catalog（style/surface/cost）匯入紀錄
psql -U postgres -d roompilot_db -c "SELECT catalog_key FROM roompilot.runtime_catalog_imports;"
```

`GET /api/catalog/status` 也回報 provider、view readiness 與匯入 batch 資訊，不洩漏帳密（`backend/server/main.py:999-1100`）。

## 5. Mitigation（短期緩解）

1. **服務沒跑** → `Start-Service postgresql-x64-17`（服務名以 `Get-Service postgresql*` 實際輸出為準）。
2. **view／資料未匯入** → 依 `docs/NEW_MACHINE_SETUP.md` §6 執行匯入器（家具、embeddings、runtime catalog、lighting）；匯入入口清單見 `docs/contracts/POSTGRESQL_SINGLE_SOURCE_PHASE5.md` 「匯入入口」段。
3. **`catalog_pool_busy`** → 等 2 秒重試即可；頻繁發生才調 `DB_POOL_MAX`／`DB_POOL_TIMEOUT`（`.env`）。
4. **展示急用、DB 短期修不好** → 明確切離線模式後重啟 uvicorn（這是展示工具，不是故障轉移策略；正式環境不得以此遮蔽問題——`docs/contracts/POSTGRESQL_SINGLE_SOURCE_PHASE5.md` Rollback 段）：

   ```dotenv
   ROOMPILOT_CATALOG_PROVIDER=json
   ROOMPILOT_RUNTIME_CATALOG_PROVIDER=json
   ROOMPILOT_PROJECT_STORE_PROVIDER=sqlite
   ```

   注意：離線模式的家具集合是 JSON 8,557 筆，與 DB view 7,958 筆不同；專案資料改走 `.runtime/` SQLite，與 PostgreSQL 內的專案**不互通**。

## 6. Recovery（恢復確認）

- `GET /api/health` 回 HTTP 200、`ready: true`、`status: "ready"`、`source_of_truth: "postgresql"`。
- 第 6 步家具清單可載入、專案可存讀。
- `GET /api/catalog/status` 的 `catalog_provider.count` 與第 4 節基準（7,958）相符。

## 7. Escalation（升級路徑）

| 情況 | 找誰 | 管道 |
| :--- | :--- | :--- |
| view／匯入器／資料層問題 | Kai | 團隊群組（現況無書面 on-call 制度，未查證到正式約定） |
| FastAPI 錯誤處理／health 判定異常 | Bella | 同上 |
| 需要動 provider 契約本身 | Kai＋Bella 共同確認 | `docs/contracts/POSTGRESQL_SINGLE_SOURCE_PHASE5.md` 受影響 owner |

事故結束後 48 小時內完成覆盤紀錄（正式覆盤文件依需增建）。

## 8. 追溯

| 項目 | ID |
| :--- | :--- |
| 對應告警 | 現況：無告警系統（[deployment_and_operations.md](deployment_and_operations.md) 監控段） |
| 對應 NFR | NFR-可用性-01（`../01_requirements/srs.md` §2：DB 不可用顯式 503、回退為人工切換） |
| 相關契約 | `docs/contracts/POSTGRESQL_SINGLE_SOURCE_PHASE5.md`、`docs/contracts/POSTGRESQL_PROJECT_STORE_PHASE3.md` |
| 事故紀錄 | 無（postmortem 文件依需增建） |
