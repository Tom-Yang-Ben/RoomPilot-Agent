# Runbook - Port 8002 被佔用／連到殘留舊服務

> **版本:** v1.0 | **更新:** 2026-08-07 | **狀態:** 活躍
> **Owner:** Bella（backend/server 啟動）
> **語域:** L3（工程）
> **定位:** uvicorn 綁不上 8002、或瀏覽器連到殘留舊進程的診斷與處置；啟動後 API 一直 503 另見 [runbook-postgres-catalog-unavailable.md](runbook-postgres-catalog-unavailable.md)。
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

- `uvicorn` 啟動即失敗，錯誤含 bind／`WinError 10048`（「通常每個通訊端位址只允許使用一次」；確切措辭隨語系與 uvicorn 版本而異）。
- 更隱蔽的變體：**啟動「成功」但驗到舊程式**——另一個殘留的舊版 uvicorn 還佔著 8002，你的新程式其實根本沒在服務。改了 code 卻「沒生效」時，先懷疑這一型。

## 2. Impact（影響）

| 項目 | 內容 |
| :--- | :--- |
| **受影響功能** | 服務起不來，或起來的是舊版程式（驗證結論全部作廢） |
| **嚴重程度判定** | 阻斷開發即為當下最高級；「驗到舊程式」型若已據以宣告驗證通過，屬證據污染，需重驗 |

## 3. Possible Causes（可能原因）

按發生機率排序：

1. **殘留的舊 uvicorn**：先前終端機沒關乾淨（`--reload` 的父子進程、背景視窗、多個並行 session）。
2. **同機多 worktree／多人共用機器**同時各起一份服務。
3. 其他應用剛好佔用 8002。

## 4. Diagnosis（診斷步驟）

```powershell
# 1. 誰在聽 8002
Get-NetTCPConnection -LocalPort 8002 -State Listen | Select-Object LocalAddress, OwningProcess

# 2. 那個 PID 是什麼（python.exe = 多半是 uvicorn）
Get-Process -Id <上一步的 OwningProcess> | Select-Object Id, ProcessName, Path, StartTime

# 3. 看它跑的是哪份程式（命令列含 repo 路徑與 --port）
Get-CimInstance Win32_Process -Filter "ProcessId = <PID>" | Select-Object CommandLine
```

判讀：`CommandLine` 含 `backend.server.main:app` 即殘留的 RoomPilot uvicorn；`StartTime` 比你這輪開發早很多的，就是「驗到舊程式」的元兇。

## 5. Mitigation（短期緩解）

1. **是自己的殘留 uvicorn** → 停掉再重啟（只停第 4 節確認過的 PID，不要整批殺 python）：

   ```powershell
   Stop-Process -Id <PID> -Confirm:$false
   .\dev.ps1
   ```

2. **不是自己的進程／不確定** → 不要殺，改用其他 port（README.md:37 慣例；`dev.ps1` 支援參數，`dev.ps1:2-3`）：

   ```powershell
   .\dev.ps1 8023
   # 或
   .\.venv\Scripts\python.exe -m uvicorn backend.server.main:app --host 127.0.0.1 --port 8023 --reload
   ```

   注意：換 port 後瀏覽器要連 `http://127.0.0.1:8023`，舊分頁連的還是 8002。
3. 更新程式版本前，養成先停舊 uvicorn 的習慣，避免「驗到舊程式」型再發。

## 6. Recovery（恢復確認）

- 啟動 log 出現 `Uvicorn running on http://127.0.0.1:<port>` 且無 bind 錯誤。
- `curl.exe -s http://127.0.0.1:<port>/api/health` 有回應。
- `Get-NetTCPConnection -LocalPort <port> -State Listen` 只有一個 PID，且 `StartTime` 是剛剛。

## 7. Escalation（升級路徑）

| 情況 | 找誰 | 管道 |
| :--- | :--- | :--- |
| 佔用者是隊友的 session（共用機器） | 該 session 使用者本人 | 團隊群組（現況無書面 on-call 制度，未查證到正式約定） |
| 換 port 後前端仍有異常 | Bella | 同上 |

事故結束後 48 小時內完成覆盤紀錄（正式覆盤文件依需增建）。

## 8. 追溯

| 項目 | ID |
| :--- | :--- |
| 對應告警 | 現況：無告警系統（[deployment_and_operations.md](deployment_and_operations.md) 監控段） |
| 對應 NFR | NFR-維運-01（`../01_requirements/srs.md` §2：本機 uvicorn 部署形態，預設 `127.0.0.1:8002`） |
| 相關來源 | README.md「快速啟動」段（port 8002 慣例與換 port 指引）、`dev.ps1` |
| 事故紀錄 | 無（postmortem 文件依需增建） |
