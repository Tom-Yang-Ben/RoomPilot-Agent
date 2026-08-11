# Runbook - 交付提案 503 delivery_engine_not_configured (Delivery Proposal 503) - RoomPilot

> **版本:** 0.1 | **更新:** 2026-08-11 | **狀態:** 草稿
> **Owner:** Bella（`backend/server/` owner，docs/TEAM_AI_OWNERSHIP.md:21；AI 衍生，人工核准前為 TO-BE）
> **語域:** L3（工程）
> **實例:** 每故障症狀一份（`runbook-<symptom>.md`，登錄簿 §4）
> **定位宣告:** 本文件回答「第 8 步『產出設計提案』回 503 `delivery_engine_not_configured` 時如何診斷與恢復」；不包含部署與啟動程序（見 [deployment_and_operations.md](./deployment_and_operations.md)）、502 `delivery_proposal_failed` 排版失敗的內容除錯，也不包含 API 契約本身（見 [../04_design/api_spec.md](../04_design/api_spec.md) §3）。
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

本專案是本機 Pilot，無 Grafana／告警系統；症狀來源是**使用者回報與 API 回應**：

- 使用者在第 8 步按「產出設計提案」後前端報錯，PDF 沒有產出。
- `POST /api/projects/{project_id}/delivery-proposal` 回 **503**，body 為
  `{"detail": {"code": "delivery_engine_not_configured", "message": "尚未安裝交付提案排版引擎：請執行 …"}}`（main.py:2399-2402）。
- `GET /api/delivery-proposal/status` 回 `{"available": false, "reason": "…"}`（main.py:2378-2381）。

這是**設計中的防護行為**：排版引擎不可用時拒絕產出殘缺 PDF（ACPT-011；design_manual_service.py:66-67「呼叫端應回 503，不得假成功」）。

## 2. Impact（影響）

| 項目 | 內容 |
| :--- | :--- |
| **受影響功能** | 僅第 8 步「產出設計提案」PDF（`delivery-proposal`）。八步其餘功能、AI 生圖、design-delivery 成果包 JSON、工程估價均不受影響 |
| **受影響對象** | 本機操作該專案的使用者（Pilot 內部工具，無外部客戶） |
| **嚴重程度判定** | 依 §5 安裝依賴後仍 503 → 依 §7 升級；回的是 502 `delivery_proposal_failed`（main.py:2403-2406）→ 不是本 runbook 的範圍，屬排版內容失敗，直接升級 |

## 3. Possible Causes（可能原因）

按發生機率排序（判定邏輯：delivery/__init__.py:50-56 與 design_manual_service.py:257-273）：

1. **`.venv` 未安裝 `playwright` 套件**（`requirements-delivery.txt` 從未跑過）：`importlib.util.find_spec("playwright") is None` → 直接回 503 附安裝指引（delivery/__init__.py:54-55、43-47）。
2. **`playwright` 套件裝了，但 Chromium 瀏覽器沒 `install chromium`**：預檢通過，排版 subprocess `build_pdf.py` 失敗且輸出含 "playwright" → 仍轉成 503（delivery/__init__.py:295-298、design_manual_service.py:270-272）。
3. **打包 skill 檔案缺失**：`backend/agent/skills/roompilot-delivery-pdf/scripts/build_pdf.py` 不存在（不完整 checkout／誤刪）→ 503，reason 為「找不到 roompilot-delivery-pdf 打包 skill」（delivery/__init__.py:40-41、52-53）。
4. **安裝後伺服器行程還沒重啟**：套件是伺服器啟動後才裝進 `.venv`，import 快取可能讓 `find_spec` 仍看不到（待確認：實際是否必須重啟，見 §6）。

## 4. Diagnosis（診斷步驟）

在 repo 根目錄 `C:\RoomPilot-Agent` 的 PowerShell 執行（port 以實際啟動為準，api_spec §1 記 `http://127.0.0.1:8000`）：

```powershell
# 1. 先問引擎狀態端點，reason 會直接講缺什麼（main.py:2378-2381）
curl.exe -s http://127.0.0.1:8000/api/delivery-proposal/status
# 期望（故障中）：{"available": false, "reason": "尚未安裝交付提案排版引擎：…"}

# 2. playwright 套件是否在 .venv（對應原因 1；delivery/__init__.py:54）
.\.venv\Scripts\python.exe -c "import importlib.util; print(importlib.util.find_spec('playwright'))"
# 印 None → 原因 1

# 3. Chromium 瀏覽器是否已下載（對應原因 2；套件在才跑得動）
.\.venv\Scripts\playwright.exe install --dry-run chromium
# 輸出的 Install location 目錄不存在 → 原因 2

# 4. 打包 skill 是否在（對應原因 3；delivery/__init__.py:40-41）
Test-Path backend\agent\skills\roompilot-delivery-pdf\scripts\build_pdf.py
# False → 原因 3：checkout 不完整，git status / git checkout 還原該路徑
```

## 5. Mitigation（短期緩解）

原因 1／2 的修復即 503 訊息與 README.md:111-117 附的安裝指引（依賴清單見 requirements-delivery.txt:11-12：`playwright==1.62.0` 必要、`pikepdf` 選配缺少時自動略過）：

```powershell
# 在 C:\RoomPilot-Agent（.venv 由 uv 管理，用 uv pip，不用裸 pip）
uv pip install --python .venv\Scripts\python.exe -r requirements-delivery.txt
.\.venv\Scripts\playwright.exe install chromium
```

- 原因 3：`git checkout -- backend/agent/skills/roompilot-delivery-pdf/` 還原打包 skill 檔案（先 `git status` 確認不覆蓋本機未提交變更）。
- 原因 4：重啟 FastAPI 伺服器行程後重試。
- **不要**繞過 503 改回假成功——「不得假成功」是驗收條件本身（ACPT-011）。

## 6. Recovery（恢復確認）

1. `curl.exe -s http://127.0.0.1:8000/api/delivery-proposal/status` 回 `{"available": true, "reason": ""}`（delivery/__init__.py:56）。仍 `false` → 重啟伺服器再查一次（§3 原因 4）。
2. 前端第 8 步重按「產出設計提案」，`POST /api/projects/{project_id}/delivery-proposal` 回 **201**，回應含 `proposal.download_url`（main.py:2410-2418）。
3. 開 `GET /api/projects/{project_id}/delivery-proposal/pdf` 能下載 PDF（main.py:2421-2437）。
4. 留意回應 `proposal.warnings`：含「文案走離線底稿（LLM 未套用）」表示未設 `OPENROUTER_API_KEY`，PDF 仍成立，屬另一件事（delivery/__init__.py:106-112）。

## 7. Escalation（升級路徑）

無 on-call 系統，依 docs/TEAM_AI_OWNERSHIP.md 的目錄 owner 分工直接找人：

| 情況 | 找誰 | 依據 |
| :--- | :--- | :--- |
| §5 安裝完成、伺服器已重啟仍 503 | Bella（`backend/server/` API 層與 503 轉換） | TEAM_AI_OWNERSHIP.md:21、design_manual_service.py:257-273 |
| status 回 available 但 502 `delivery_proposal_failed`／排版逾時 180 秒 | Yen（`backend/agent/` delivery skill 與 build_pdf 流程），Bella 協作 | TEAM_AI_OWNERSHIP.md:28、delivery/__init__.py:293-300 |
| `roompilot-delivery-pdf` 打包 skill 檔案在 repo 內遺失 | Yen（skill 內容）＋ Bella（整合） | TEAM_AI_OWNERSHIP.md:28 |

事故結束後 48 小時內完成覆盤紀錄（正式覆盤文件依需增建）。

## 8. 追溯

| 項目 | ID／來源 |
| :--- | :--- |
| 對應告警 | 無（本機 Pilot 無告警系統）；症狀來源為使用者回報＋`GET /api/delivery-proposal/status` |
| 對應需求 | REQ-012 → FR-012（[../00-registry.md](../00-registry.md) §2） |
| 對應驗收 | ACPT-011（缺 Playwright Chromium 時回 503 附安裝指引，不產出殘缺 PDF）；情境 SCN-007 |
| 對應 NFR | 登錄簿無交付可用性專屬 NFR（待確認：是否需新增由 owner 拍板，本文件不自創 ID） |
| 程式碼證據 | main.py:2378-2437、design_manual_service.py:66-73、242-280、backend/agent/skills/delivery/__init__.py:40-56、273-305、requirements-delivery.txt、README.md:111-117 |
| 事故紀錄 | 尚無（postmortem 依需增建） |
| 下游 | [../05_qa/test_plan.md](../05_qa/test_plan.md)（ACPT-011 驗證案例）、[deployment_and_operations.md](./deployment_and_operations.md)（安裝與啟動程序） |
