# Runbook：交付 PDF 排版引擎缺席 (Delivery PDF Engine Missing) - RoomPilot

> **版本:** v1.0 ｜ **更新:** 2026-08-12 ｜ **狀態:** 草稿（待 owner 核准）
> **Owner:** MOD-SRV-RENDER owner（Bella）；打包 skill 與文案層 MOD-AGT owner（Yen）
> **語域:** L3（工程）——直接寫端點、錯誤碼、指令與檔案路徑
> **實例:** 每故障症狀一份（本檔＝RB-005，登錄見 [`00-registry.md`](../00-registry.md)）
>
> **本文件回答**：第 8 步兩份 PDF（交付提案／設計手冊）產不出來或下載不到時，怎麼在五分鐘內判定是「引擎沒裝」「排版失敗」還是「檔案不見」，以及各自怎麼修。
> **本文件不含**：生圖供應商失敗（去 [`runbook-genpic-provider-failure.md`](./runbook-genpic-provider-failure.md)，RB-002）、`.runtime/` 容量成長（去 [`runbook-runtime-storage-growth.md`](./runbook-runtime-storage-growth.md)，RB-009）、安裝與啟動程序（去 [`deployment_and_operations.md`](./deployment_and_operations.md)）、端點欄位契約（去 [`api_spec.md`](../04_design/api_spec.md) 與 [`openapi-render-delivery-v1.yaml`](../04_design/openapi-render-delivery-v1.yaml)）。
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

> **無告警來源。** 本 repo 無 Prometheus／Grafana／Sentry／on-call 輪值，`main.py` 也未設定 `logging`；一切靠**使用者回報**、**畫面錯誤文案**（`scene_v2.js:17595-17596` 把 API 錯誤直接寫進 `#delivery-proposal-status`）與**啟動 uvicorn 的主控台輸出**。

| # | 使用者看到 | HTTP／錯誤碼 | 佐證 |
| :--- | :--- | :--- | :--- |
| S-A | 按「產出設計提案」立刻失敗，訊息含「尚未安裝交付提案排版引擎：請執行 `uv pip install …`」 | 503 `delivery_engine_not_configured` | `main.py:2399-2402`；`agent/skills/delivery/__init__.py:43-56` |
| S-B | 進入第 8 步面板時狀態列已預先顯示同一句安裝指引（尚未按產出） | `GET /api/delivery-proposal/status` → `available:false` | `main.py:2378-2381`；`design_manual_service.py:70-73`；`scene_v2.js:17557-17564` |
| S-C | 轉圈很久後失敗，訊息為「交付提案 PDF 排版逾時（180 秒）」或「交付提案 PDF 排版失敗：<末 5 行>」 | 502 `delivery_proposal_failed` | `main.py:2403-2406`；`agent/skills/delivery/__init__.py:293-300` |
| S-D | 「下載設計提案 PDF」連結按下去說「紀錄存在，但檔案已遺失，請重新產出」 | 410 `delivery_proposal_file_missing`／`design_manual_file_missing` | `main.py:2432-2436`（提案）；`main.py:2345-2349`（手冊） |
| S-E | 沒產出過就按下載 | 404 `delivery_proposal_not_found`／`design_manual_not_found` | `main.py:2426-2430`；`main.py:2340-2343` |
| S-F | 設計手冊 PDF 產得出來，但中文全是方框／空白 | 200（**無錯誤碼，靜默降級**） | `tools/render_pdf.py:29-58`（字型找不到就退回 Pillow 內建字型） |

**S-A 與 S-C 是設計中的防護行為**，不是崩潰：引擎不可用時寧可拒絕，也不輸出殘缺 PDF（`design_manual_service.py:66-67` 註記「呼叫端應回 503，不得假成功」）。

## 2. Impact（影響）

| 項目 | 內容 |
| :--- | :--- |
| **受影響功能** | 僅第 8 步收尾的兩份 PDF：交付提案（FR-062）與設計手冊（FR-061）。生圖（FR-058）、逐房改圖（FR-060）、成果包 JSON（FR-063）、工程概算（FR-064）與第 1–7 步**皆不受影響** |
| **受影響對象** | 本機 Pilot 操作者（`http://127.0.0.1:8002`，`README.md:49,66`）；無外部客戶、無多租戶 |
| **資料風險** | 無。503／502 皆在寫入 `workflow.delivery_proposal` 之前中止（`main.py:2390-2409`），專案 `revision` 不會被推進 |
| **嚴重程度判定** | S-A／S-B＝環境未安裝，照 §5 修即可，不算 incident；S-C 連續三次以上、或 S-D 反覆出現（檔案被外力清掉）＝升級，見 §7 |
| **對 UAT 的影響** | ACPT-053 無法驗；若 UAT 當日出現，該案例記「受阻」而非「失敗」 |

## 3. Possible Causes（可能原因）

按發生機率排序。判定邏輯集中在 `agent/skills/delivery/__init__.py:50-56` 與 `design_manual_service.py:257-273`。

| # | 原因 | 命中的症狀 | 判定依據 |
| :--- | :--- | :--- | :--- |
| C1 | `.venv` 沒裝 `playwright`（`requirements-delivery.txt` 從沒跑過） | S-A、S-B | `importlib.util.find_spec("playwright") is None` → 直接回 `_INSTALL_HINT`（`__init__.py:54-55`、`:43-47`） |
| C2 | `playwright` 套件裝了但 Chromium 沒下載 | S-A（延後到實際排版才觸發） | 預檢過關，子行程輸出含 `playwright` → 仍轉成 503（`__init__.py:295-298`；`design_manual_service.py:270-272`） |
| C3 | 打包 skill 檔案不在（checkout 不完整／誤刪） | S-A | `BUILD_PDF_SCRIPT.exists()` 為 False → reason「找不到 roompilot-delivery-pdf 打包 skill」（`__init__.py:40-41,52-53`） |
| C4 | Chromium 排版超過 180 秒（圖太多／太大、機器負載高） | S-C | `subprocess.run(..., timeout=180)` → `TimeoutExpired`（`__init__.py:276-294`） |
| C5 | 排版子行程非零離開（content.json 內容或 HTML 出錯） | S-C | `returncode != 0 or not out.is_file()` → 取 stderr／stdout 末 5 行回傳（`__init__.py:295-300`） |
| C6 | `.runtime/manuals/<project_id>/` 被清掉，但 SQLite 的 workflow 紀錄還在 | S-D | 下載端點只認 `record["filename"]` 再檢查檔案（`main.py:2424-2436`）；目錄定義見 `main.py:2290-2291`、`runtime_paths.py:20-25` |
| C7 | 主機無 CJK 字型且未設 `ROOMPILOT_PDF_FONT`（**只影響設計手冊**，Chromium 版提案不走這條） | S-F | `_font_path()` 候選清單找不到就 `ImageFont.load_default()`（`tools/render_pdf.py:29-58`） |
| C8 | 安裝完沒重啟 uvicorn，行程內 import 快取仍看不到新套件 | S-A（裝完仍 503） | **待確認**：`find_spec` 在既有行程中的行為未於本 repo 實測，見 §8 待確認 |

> 設計手冊（FR-061）**沒有**引擎預檢，任何失敗一律 502 `design_manual_failed`（`main.py:2320-2323`）；只有交付提案才會出現 503。看到 503 就代表問題在 Chromium 這條路徑上。

## 4. Diagnosis（診斷步驟）

在 repo 根目錄 `D:\RoomPilot-Agent` 開 PowerShell，逐條複製貼上。服務預設 `http://127.0.0.1:8002`（`README.md:49,66`）；若啟動時改過 `--port`，整段跟著換。

```powershell
# 1) 引擎狀態端點：reason 直接講缺什麼，這一步通常就結案（main.py:2378-2381）
curl.exe -s http://127.0.0.1:8002/api/delivery-proposal/status
#   {"available":true,"reason":""}                → 引擎正常，跳 4)
#   {"available":false,"reason":"尚未安裝…"}      → C1／C2
#   {"available":false,"reason":"找不到 roompilot-delivery-pdf…"} → C3

# 2) playwright 套件是否在 .venv（C1）
.\.venv\Scripts\python.exe -c "import importlib.util;print(importlib.util.find_spec('playwright'))"
#   None → C1

# 3) Chromium 是否已下載，且打包 skill 是否在（C2／C3）
.\.venv\Scripts\playwright.exe install --dry-run chromium
Test-Path backend\agent\skills\roompilot-delivery-pdf\scripts\build_pdf.py
#   Install location 目錄不存在 → C2；Test-Path 為 False → C3（git checkout 還原該路徑）

# 4) 引擎正常卻仍失敗：離線重現排版（C4／C5）。先撈一份既有 content.json 當輸入
Get-ChildItem -Recurse .runtime\manuals -Filter *.content.json | Select-Object -Last 1 FullName
.\.venv\Scripts\python.exe backend\agent\skills\roompilot-delivery-pdf\scripts\build_pdf.py `
  "<上一行印出的路徑>" -o "$env:TEMP\rp-probe.pdf" --keep-html
#   逾時／traceback 在此原形畢露；--keep-html 留下中繼 HTML 可用瀏覽器開來看版面

# 5) 檔案是否真的不見（C6；410 專用）
Get-ChildItem .runtime\manuals\<project_id>
curl.exe -s http://127.0.0.1:8002/api/projects/<project_id> | Select-String delivery_proposal
#   workflow 有 filename 但目錄裡沒該檔 → C6

# 6) 設計手冊中文變方框（C7）
.\.venv\Scripts\python.exe -c "from backend.agent.tools.render_pdf import _font_path;print(_font_path())"
#   None → C7：設 $env:ROOMPILOT_PDF_FONT 指向一個 CJK ttf/ttc 後重啟服務
```

## 5. Mitigation（短期緩解）

1. **C1／C2（最常見）**——照 503 訊息與 `README.md:111-117` 執行；`.venv` 由 uv 管理，用 `uv pip`，不要裸 `pip`：
   ```powershell
   uv pip install --python .venv\Scripts\python.exe -r requirements-delivery.txt
   .\.venv\Scripts\playwright.exe install chromium
   ```
   Linux／macOS 對應 `install.sh:48-51`（另有 `.venv/bin/playwright install-deps` 補系統庫）。`requirements-delivery.txt:9-12`：`playwright==1.62.0` 必要、`pikepdf==10.11.0` 選配（缺少時 `build_pdf.py` 自動略過中文碼位修正，不會失敗）。
2. **C3**——`git status` 確認是否誤刪，再 `git checkout -- backend/agent/skills/roompilot-delivery-pdf/`。
3. **C4**——先叫使用者改按「產出設計手冊」（`POST /api/projects/{id}/design-manual`，`main.py:2300-2331`）取得可交付的替代主件；Pillow 逐頁點陣路徑不經 Chromium，不受本故障影響（`tools/render_pdf.py:1-9,187-198`）。180 秒為程式常數，**不可由環境變數調整**，要改需改碼（`__init__.py:290`）。
4. **C5**——依 §4 步驟 4 的 traceback 修 content.json 來源資料；排版失敗常見於圖檔缺失（`build_pdf.py:520-528` 只印 ⚠️ 用佔位框代替，不致命）。
5. **C6／C8**——重新按一次「產出設計提案」即可覆蓋紀錄；裝完套件後重啟 uvicorn（`README.md:49`）。
6. **不要做的事**：不得為了「先給客戶一份」而手動塞 PDF 進 `.runtime/manuals/`——`filename` 由伺服器以 `roompilot-proposal-<projid8>-<uuid8>.pdf` 產生（`design_manual_service.py:261`），手放的檔不會被 workflow 紀錄指到。

## 6. Recovery（恢復確認）

按順序全部通過才算恢復：

1. `curl.exe -s http://127.0.0.1:8002/api/delivery-proposal/status` 回 `{"available":true,"reason":""}`。
2. 從畫面第 8 步按「產出設計提案」→ 201，狀態列出現「設計提案完成（含 N 房生圖）」（`scene_v2.js:17589-17594`）。若訊息含「文案走離線底稿（LLM 未套用）」，那是 `OPENROUTER_API_KEY` 未設，**屬正常降級、不是本故障**（`__init__.py:105-112`）。
3. `GET /api/projects/{id}/delivery-proposal/pdf` 回 200 且檔頭為 `%PDF`；同目錄應同時有 `<檔名>.content.json`（`__init__.py:113-114`）。
4. 迴歸測試 `.\.venv\Scripts\python.exe -m pytest -q tests/test_delivery_proposal_api.py`（引擎缺席時 e2e 那筆自動 skip，不算通過）。關鍵案例：`test_delivery_pdf_end_to_end`（`tests/test_delivery_proposal_api.py:285-300`，`skipif not PLAYWRIGHT_AVAILABLE`）、`test_engine_missing_reports_503`（`:340`）、`test_generate_then_download_proposal`（`:318`）。

## 7. Escalation（升級路徑）

無 on-call 系統；聯絡管道為團隊既有溝通管道，owner 分工見 [`TEAM_AI_OWNERSHIP.md`](../../docs/TEAM_AI_OWNERSHIP.md) 與 [`srs.md`](../01_requirements/srs.md) §2。

| 情況 | 找誰（MOD） | 依據 |
| :--- | :--- | :--- |
| §5 安裝步驟做完仍 503 | Bella（MOD-SRV-RENDER／MOD-OPS） | `srs.md` §2.8、§2.9；`docs/TEAM_AI_OWNERSHIP.md:9,21` |
| 502 排版失敗，traceback 指向 `build_pdf.py` 或 content.json 欄位 | Yen（MOD-AGT，打包 skill 與文案層） | `docs/TEAM_AI_OWNERSHIP.md:28`；`agent/skills/delivery/__init__.py:1-7` |
| 生圖本身失敗導致提案裡都是佔位框 | Bella（MOD-SRV-RENDER）→ 轉 [`RB-002`](./runbook-genpic-provider-failure.md) | `srs.md` §9.2 S8 列 |
| `.runtime/manuals/` 被誰清掉、保留多久、要不要備份 | **待確認（DEC-015 未核准）** | 見 §8 |
| 「哪一份 PDF 才是對客戶的正式主件」引發爭議 | 產品 owner（OPEN-10） | `srs.md` §8 |

事故結束後 48 小時內在 [`qa_tracker.xlsx`](../05_qa/qa_tracker.xlsx) 留一列；本 repo 無正式 postmortem 文件模板，需要時另建。

## 8. 追溯

| 項目 | ID／文件 |
| :--- | :--- |
| Runbook 編號 | **RB-005**（`srs.md` §9.2 S8 列：RB-002、RB-005） |
| 對應告警 | **無告警來源**；靠使用者回報、畫面錯誤文案與 uvicorn 主控台輸出 |
| 對應 FR | FR-061（設計手冊）、FR-062（交付提案 503／502）、FR-067（狀態端點群） |
| 對應 NFR | NFR-013（Chromium 子行程、逾時 180 秒、引擎缺席 503 附安裝指令）、NFR-014（誠實中止不假成功） |
| 對應 DEC | DEC-012（正式交付物只有一份主件）、DEC-017（外部相依壞掉要誠實中止） |
| 對應 ACPT／SCN／TC | ACPT-053、ACPT-060；SCN-032；TC-053、TC-060（[`test_plan.md`](../05_qa/test_plan.md)） |
| 對應 ADR | [`ADR-009`](../03_architecture/adr/ADR-009-server-governed-ai-generation.md)（伺服器治理 AI 產出）、[`ADR-012`](../03_architecture/adr/ADR-012-pilot-loopback-deployment.md)（Pilot loopback 部署） |
| 待確認 | **C8**：套件安裝後是否必須重啟 uvicorn，本 repo 無實測證據，暫記為假設。**保留與備份**：`.runtime/manuals/` 的保留期、備份與結案刪除政策未定，承接 DEC-015／[`deployment_and_operations.md`](./deployment_and_operations.md)。**主件歸屬**：三份交付物誰是正式主件見 OPEN-10。**逾時值**：180 秒無實測基準線，屬程式常數而非量測後的 SLA |
