# Runbook - ROOMPILOT_*_PROVIDER 行程環境變數蓋過 .env

> **版本:** v1.0 | **更新:** 2026-08-07 | **狀態:** 活躍
> **Owner:** Bella（backend/server 設定機制）
> **語域:** L3（工程）
> **定位:** 「改了 `.env` 卻不生效、provider 模式與預期不符」的診斷與處置；資料庫本身連不上另見 [runbook-postgres-catalog-unavailable.md](runbook-postgres-catalog-unavailable.md)。
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

- `.env` 明明寫 `ROOMPILOT_CATALOG_PROVIDER=postgres`，但 `GET /api/health` 回 `status: "offline"`、`source_of_truth: "versioned_files"`。
- `GET /api/catalog/status` 的 runtime catalog 狀態顯示 json／offline 模式。
- 改 `.env` 後重啟 uvicorn，行為仍不變。
- 家具筆數與預期不符：離線 JSON 是 8,557 筆、DB view 是 7,958 筆——筆數對不上常是模式錯了，不是資料壞了。

## 2. Impact（影響）

| 項目 | 內容 |
| :--- | :--- |
| **受影響功能** | provider 模式錯亂：型錄走錯來源、專案存進 SQLite 而非 PostgreSQL（兩邊資料不互通）、驗證結果誤判 |
| **嚴重程度判定** | 單人開發時是時間損耗；若在「以為驗過 postgres 模式」的狀態下交付驗證結論，屬證據污染，需重驗 |

## 3. Possible Causes（可能原因）

1. **啟動 uvicorn 的終端機行程帶著 `ROOMPILOT_*_PROVIDER` 環境變數**。三個 provider 的讀取一律是「行程環境變數優先、`.env` 只是 fallback」：
   - `ROOMPILOT_CATALOG_PROVIDER`：`os.getenv(name, file_values.get(name, default))`（`backend/catalog/postgres_repository.py:196-198`，預設 `postgres`）。
   - `ROOMPILOT_RUNTIME_CATALOG_PROVIDER`（`backend/catalog/runtime_catalog_repository.py:50-55`；空值時繼承 catalog provider）。
   - `ROOMPILOT_PROJECT_STORE_PROVIDER`（`backend/server/project_store.py:651-661`，預設 `sqlite`；值非法會 raise `invalid_project_store_provider`）。
2. 變數來源常是**行程繼承**（父 shell 曾 export），不一定在 User／Machine scope，也不一定在 PowerShell profile——2026-07-31 實案即此型態（團隊工作紀錄，未入版控）。

## 4. Diagnosis（診斷步驟）

```powershell
# 1. 看目前終端機行程帶了哪些 ROOMPILOT_ 變數
Get-ChildItem Env: | Where-Object { $_.Name -like 'ROOMPILOT_*' }

# 2. 與 .env 逐鍵比對（有出入的鍵就是被蓋掉的鍵）
Select-String -Path .env -Pattern 'ROOMPILOT_.*_PROVIDER'

# 3. 追變數來源：確認是否 User / Machine scope（都是空 = 行程繼承）
[Environment]::GetEnvironmentVariable('ROOMPILOT_CATALOG_PROVIDER', 'User')
[Environment]::GetEnvironmentVariable('ROOMPILOT_CATALOG_PROVIDER', 'Machine')

# 4. 服務端實際生效值
curl.exe -s http://127.0.0.1:8002/api/health
```

## 5. Mitigation（短期緩解）

1. 在**啟動 uvicorn 的同一個終端機**清掉變數，再重啟服務（環境變數在行程啟動時繼承，清掉後必須重啟才生效）：

   ```powershell
   Remove-Item Env:\ROOMPILOT_CATALOG_PROVIDER -ErrorAction SilentlyContinue
   Remove-Item Env:\ROOMPILOT_RUNTIME_CATALOG_PROVIDER -ErrorAction SilentlyContinue
   Remove-Item Env:\ROOMPILOT_PROJECT_STORE_PROVIDER -ErrorAction SilentlyContinue
   .\dev.ps1
   ```

2. 或直接開一個**全新終端機**啟動（不繼承髒環境）。
3. 長期：不要在 profile、啟動腳本或共用終端 export `ROOMPILOT_*_PROVIDER`；本機模式切換一律寫 `.env`。

## 6. Recovery（恢復確認）

- `Get-ChildItem Env: | Where-Object { $_.Name -like 'ROOMPILOT_*_PROVIDER' }` 無輸出（或值與 `.env` 一致）。
- `GET /api/health` 的 `source_of_truth` 與 `.env` 期望一致（正式模式為 `postgresql`、`status: "ready"`）。
- 之前在錯誤模式下做過的驗證結論標記重驗。

## 7. Escalation（升級路徑）

| 情況 | 找誰 | 管道 |
| :--- | :--- | :--- |
| 清掉變數後行為仍不符 `.env` | Bella | 團隊群組（現況無書面 on-call 制度，未查證到正式約定） |
| 懷疑 provider 解析邏輯本身有誤 | Bella（server）＋Kai（catalog） | 同上 |

事故結束後 48 小時內完成覆盤紀錄（正式覆盤文件依需增建）。

## 8. 追溯

| 項目 | ID |
| :--- | :--- |
| 對應告警 | 現況：無告警系統（[deployment_and_operations.md](deployment_and_operations.md) 監控段） |
| 對應 NFR | NFR-維運-01（`../01_requirements/srs.md` §2：部署形態與組態解析） |
| 相關契約 | `docs/contracts/POSTGRESQL_SINGLE_SOURCE_PHASE5.md`（provider 契約） |
| 事故紀錄 | 2026-07-31 實案（團隊工作紀錄，未入版控；postmortem 文件依需增建） |
