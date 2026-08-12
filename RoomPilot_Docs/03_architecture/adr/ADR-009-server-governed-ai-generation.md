# ADR-009: AI 生成一律由伺服器治理，前端不持金鑰 (Server-Governed AI Generation) - RoomPilot

> **狀態:** 已接受（現況追認，待 owner 核准） ｜ **日期:** 2026-08-12 ｜ **決策者:** MOD-SRV-RENDER owner（Bella）＋ MOD-AGT owner（Yen）；業務面待產品 owner 於 [`requirements_tracker.xlsx`](../../01_requirements/requirements_tracker.xlsx) ③Gate 簽核
> **語域:** L2（橋接）——業務承諾與強制點並列，跨層一律用穩定 ID
> **實例:** 每決策一份（`ADR-009-server-governed-ai-generation.md`）
>
> **本文件回答**：第 7／8 步的色卡、逐房生圖、改圖與交付文案為什麼一律由 FastAPI 行程呼叫模型、金鑰為什麼不下放瀏覽器、重試次數與失敗語意為什麼由伺服器而非模型或前端決定。
> **本文件不含**：端點欄位級契約（去 [`api_spec.md`](../../04_design/api_spec.md)、[`openapi-render-delivery-v1.yaml`](../../04_design/openapi-render-delivery-v1.yaml)）、畫面行為與文案（去 [`ui_spec-step7-proposal-review.md`](../../02_ux_ui/ui_spec-step7-proposal-review.md)、[`ui_spec-step8-ai-render.md`](../../02_ux_ui/ui_spec-step8-ai-render.md)）、模組全貌（去 [`sad.md`](../sad.md)）、事故處置（去 [`runbook-genpic-provider-failure.md`](../../06_ops/runbook-genpic-provider-failure.md)）。
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、2026-08-12 工作樹。行號隨程式碼演進，衝突時以原始碼為準。

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 執行計畫](#5-執行計畫)
- [6. 追溯](#6-追溯)

## 1. 背景與問題

- **上下文**：第 7／8 步共有四個外部模型呼叫點，全部落在同一個 FastAPI 行程內。

| 生成點 | 端點 | 伺服器側入口 | 模型決定處 |
| :--- | :--- | :--- | :--- |
| S7 代表房色卡比較 | `POST /api/projects/{id}/palette-renders` | `generate_palette_images` | `_palette_gateway()`（Nano Banana Pro，env 可覆蓋）`ai_render_service.py:289-296` |
| S8 逐房生圖＋客廳夜景 | `POST /api/projects/{id}/ai-renders` | `generate_room_images` | `OpenRouterGateway.image_model`／`image_fallback_model`，`agent/llm.py:135-142` |
| S8 改圖 | `POST /api/projects/{id}/ai-renders/{room_id}/edit` | `edit_room_image` | 同上 |
| S8 文案 LLM（設計手冊／交付提案） | `POST .../design-manual`、`.../delivery-proposal` | `ReportAgent`／`DeliverySkill` | `DEFAULT_REPORT_MODEL` 硬編 `openai/gpt-5.6-luna`，`agent/llm.py:43` |

- **問題**：影像由使用者的瀏覽器截圖起頭（第 7 步鎖定視角 PNG），最自然的作法是讓瀏覽器直接把截圖送給模型供應商——但那需要把 `OPENROUTER_API_KEY` 交到瀏覽器，且重試次數、一次性額度與「失敗要不要講實話」全部變成前端自律。此外 DEC-017 要求外部服務壞掉必須誠實中止（`brd.md`），而生圖是最容易以占位圖假裝成功的環節。
- **驅動因素／約束**：
  - 契約明文「瀏覽器不得自帶模型網址或金鑰」「未設定金鑰時回 503，不得回假圖或假成功」（`docs/contracts/AI_RENDER_OPENROUTER_CONTRACT.md:4-5,41`）。
  - 色卡每案僅能成功一次、改圖有限次（DEC-010、DEC-011），額度若存在前端等於不存在。
  - 正式前端是無建置流程的靜態單頁（見 [`ADR-010`](./ADR-010-static-frontend-and-eight-step-collapse.md)），無伺服器端渲染層可藏秘密。
  - Pilot 現況無認證、無 rate limit（NFR-019），任何下放的金鑰都等同公開。

## 2. 考量的選項

### 選項一：伺服器端同步呼叫（採用）
- **描述**：前端只送 `scene` ＋逐房 3D 截圖 data URL，FastAPI 在請求生命週期內呼叫 Gen_Pic Agent，回影像 data URL 與狀態。
- **優點**：金鑰只存在伺服器行程 env；額度與一次性旗標寫在 workflow；失敗語意集中一處可寫 runbook。
- **缺點**：長時間同步請求；伺服器承擔全部呼叫成本且無配額控管。
- **成本/複雜度**：低（沿用既有 `backend/agent/`）。

### 選項二：瀏覽器直連模型供應商
- **描述**：前端持金鑰或短期 token，截圖後直接呼叫 OpenRouter，成品再回傳伺服器保存。
- **優點**：伺服器不阻塞、天然併發、無單點逾時。
- **缺點**：靜態前端無處藏金鑰，Pilot 無認證等同公開金鑰；色卡「每案一次」與改圖額度只剩前端自律；失敗時前端可自行塞占位圖，違反 `AI_RENDER_OPENROUTER_CONTRACT.md:41`。
- **為何不選**：與契約 `:4-5` 直接衝突。本 repo 只保留一條瀏覽器影像入口——`POST /api/projects/{id}/renders` 且 `provider` 必須是 `browser_capture`，非此值即 422（`main.py:1944-1949`）；瀏覽器只能上傳自己畫的 PNG，不能上傳模型產物。

### 選項三：沿用泛用遠端渲染商的非同步 job 佇列
- **描述**：把第 8 步接到既有的 `POST /api/projects/{id}/render-jobs`（202 ＋輪詢，`main.py:2033-2057`），由 `ROOMPILOT_RENDER_PROVIDER_URL` 指定的外部渲染商處理。
- **優點**：請求立即返回，長任務不佔連線；已有 503／502 語意與 PII 剝除（`render_service.py:52-61`）。
- **缺點**：該路徑無 `lock_manifest`／img2img「只改指定內容」語意，也無逐房額度；預設 `configured=false`（`render_service.py:41-49`），Pilot 沒有可用供應商。
- **為何不選**：兩條路徑刻意並存（`AI_RENDER_OPENROUTER_CONTRACT.md:5`），第 8 步選同步 agent 路徑以換取鎖定清單與伺服器強制額度；job 佇列保留為未來的效能出口（見 §4.3）。

## 3. 決策

**選擇**：選項一——四個生成點全部由伺服器發起；瀏覽器只提供自己的 3D 截圖與文字回饋，永不接觸金鑰、模型名以外的設定、也無權決定重試或成敗。

**理由**：只有伺服器同時握有金鑰、workflow 快照與失敗語意三者時，DEC-010／DEC-011 的一次性額度與 DEC-017 的誠實中止才是可強制的，而不是可繞過的約定。選項二讓額度失去強制力，選項三讓「只改指定內容」失去載體。

| 決策要點 | 強制點（伺服器） | 佐證 |
| :--- | :--- | :--- |
| 金鑰只在伺服器行程 | `api_key` 由 `OPENROUTER_API_KEY` 讀入，僅用於 `Authorization` 標頭 | `agent/llm.py:133,167-183` |
| 狀態端點不外洩秘密 | `/api/ai-render/status` 只回 `configured` 布林與模型 id；前端據此顯示「尚未設定生圖服務」 | `ai_render_service.py:65-74`；`main.py:2064-2067`；`scene_v2.js:16655-16658` |
| 未設定＝503，不得假成功 | `AiRenderNotConfigured` → 503 `openrouter_api_key_not_configured`（生圖／色卡／改圖三處一致） | `ai_render_service.py:61-63,341-343`；`main.py:2109-2116,2262-2269` |
| 重試由程式強制、不交給 LLM | 主模型最多 3 次 → fallback 模型再 3 次 → 拋 `GenPicFailure` | `genpic_agent.py:29-31,144-190` |
| 上游拒絕＝502 | 改圖 `GenPicFailure` → 502 `ai_edit_failed`；交付提案排版失敗 → 502 | `main.py:2270-2274,2403-2406` |
| 額度／一次性旗標存伺服器 | 色卡第二次 409 `palette_already_generated`；改圖 `edit_used>=1` 回 409 `ai_edit_budget_exhausted` | `main.py:2147-2155,2237-2248,2275-2281` |
| 部分失敗誠實標記 | 單房失敗只 `status:"failed"`；夜景失敗只附 `night_notices`；色卡全失敗不寫 `generated` 旗標、可重試 | `ai_render_service.py:376-385,395-413`；`main.py:2191-2198` |
| 併發由伺服器決定 | 逐房與逐色卡各自 `ThreadPoolExecutor(max_workers=房數/卡數)`，順序對齊輸入 | `ai_render_service.py:423-429,485-487` |
| 文案 LLM 為受控例外 | LLM 不可用時 `_report_gateway` 回 `None`，走 deterministic 底稿仍出 PDF（不偽造 AI 文案）；排版引擎缺席則 503 附安裝指令 | `design_manual_service.py:205-207`；`agent/skills/delivery/__init__.py:43-56`；`main.py:2399-2402` |

## 4. 後果

### 4.1 得到什麼
- 金鑰零下放：靜態前端全域無 `OPENROUTER` 字樣，唯一模型設定痕跡是狀態端點回的模型 id（`scene_v2.js:16655-16658`）。
- 單一失敗語意表：503／502／409 三分法可直接寫成 NFR-014 的驗收與 RB-002 的判讀依據。
- 額度不可繞過：色卡一次性與改圖額度是 SQLite workflow 內的伺服器狀態，前端重整或改 JS 都無效。
- 部分成功可交付：一房失敗不影響其他房、夜景失敗不影響日光初稿（ACPT-050）。

### 4.2 付出什麼
- **同步長請求**：一鍵全生把 N 房塞進單一 HTTP 請求，前端自述「一至數分鐘」（`scene_v2.js:17084`）；單次 LLM 逾時預設 120 秒（`agent/llm.py:147-149`），最壞情況為 6 次嘗試 × 逾時。目前無進度回報、無取消、無 job 佇列。
- **成本與濫用全落伺服器**：Pilot 無認證與 rate limit（NFR-019），任何能連到 8002 埠的人都能消耗金鑰額度。
- **base64 走 HTTP body**：影像以 data URL 進出；workflow 只存旗標與 `lock_manifest`，避免撞 2 MB 上限（`main.py:2137-2139,2199-2214`）——代價是圖不落 DB，前端關掉即失。
- **供應商硬編**：`provider` 常數為 `"openrouter"`（`ai_render_service.py:68-70`），換供應商需改碼而非改設定。

### 4.3 重評觸發（可觀測）
- DEC-014 核准的服務邊界不再是「僅本機／內網」，或出現第二位並行使用者 → 必須補 rate limit 與成本歸屬，本決策的「無配額」前提失效。
- `/ai-renders` 單次請求 p95 超過反向代理或瀏覽器逾時（現無量測，NFR-025 目標值未定義）→ 改採選項三的 202 ＋輪詢模式。
- fallback 模型連續失敗、或 OpenRouter 模型 id 變更導致 `genpic_agent.py:144-190` 六次嘗試全滅成為常態 → 重評重試上限與供應商抽象。
- OPEN-16 定案為「整批一次」→ 伺服器強制點需由逐房 `edit_used` 改回批次計數。
- 出現第二個生圖供應商，或需求要求把生成搬到離線 GPU → 本決策的「同一行程內同步呼叫」不再成立。

### 4.4 待確認（不得寫成既成事實）
| 編號 | 內容 | 目前可驗證的事實 |
| :--- | :--- | :--- |
| OPEN-16 | 改圖額度是「整批一次」還是「逐房一次」——契約與程式相反，且同一函式的 docstring 與實作互相矛盾 | 契約寫整批共用一次（`AI_RENDER_OPENROUTER_CONTRACT.md:32-33`）；實作以 `room_state["edit_used"]>=1` 逐房擋（`main.py:2244-2248`），但 docstring 仍寫「整批一次改圖」（`main.py:2226`），回應的 `edit_remaining` 是常數 1／0（`main.py:2129,2284`），反映批次語意 |
| OPEN-16（延伸） | 逐房生圖會清掉其他房的 `lock_manifest` 與已用額度，是刻意或缺陷未確認 | 前端逐房送 `rooms:[單房]`（`scene_v2.js:16982-16990`），伺服器整段覆寫 `ai_render.rooms`（`main.py:2117-2126`），而 workflow 深合併對 list 是取代非合併（`project_store.py:18-25`）；結果先前房改圖會落到 409 `room_not_generated` |
| 待確認 | 生圖端到端耗時、可支撐併發數與成本上限的目標值 | repo 內無實測數據；沿用 srs §3 的 NFR-025「目標值未定義」，待 DEC-015／DEC-019 核准 |

## 5. 執行計畫

1. 由產品 owner 就 OPEN-16 拍板額度語意，並同步修正 `main.py:2226` docstring、`edit_remaining` 回應欄位與 `AI_RENDER_OPENROUTER_CONTRACT.md:32-33` 其中之一。
2. 修正 `ai_render.rooms` 覆寫行為（依 `room_id` 合併而非整段取代），並補一條逐房生圖後其他房仍可改圖的測試（TC-052）。
3. 在 [`test_plan.md`](../../05_qa/test_plan.md) 補三條負向案例：未設金鑰 503、上游拒絕 502、色卡二次 409；以 stub gateway 執行，不打真實供應商。
4. 量測 `/ai-renders` 單次耗時分佈，填入 NFR-025 後再判斷是否觸發 §4.3 的第二條重評條件。
5. DEC-014 核准服務邊界後，決定是否加上 rate limit 與呼叫審計，並回寫 [`deployment_and_operations.md`](../../06_ops/deployment_and_operations.md)。

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-08-12 | 待簽核 | 現況追認；本 ADR 只記錄程式碼已成立的事實與其代價 |

## 6. 追溯

| 項目 | ID／文件 |
| :--- | :--- |
| 觸發來源 | DEC-010、DEC-011、DEC-012、DEC-017（[`brd.md`](../../01_requirements/brd.md)）；FR-056、FR-058、FR-060、FR-061、FR-062、NFR-012、NFR-014、NFR-020（[`srs.md`](../../01_requirements/srs.md) §2.8、§3） |
| 驗收對應 | ACPT-048、ACPT-050、ACPT-052、ACPT-053、ACPT-060（[`prd.md`](../../01_requirements/prd.md)）；SCN-026–028、SCN-029–034 |
| 影響範圍 | MOD-SRV-RENDER、MOD-AGT、MOD-WEB（[`sad.md`](../sad.md)）；契約 `docs/contracts/AI_RENDER_OPENROUTER_CONTRACT.md`；[`api_spec.md`](../../04_design/api_spec.md)、[`openapi-render-delivery-v1.yaml`](../../04_design/openapi-render-delivery-v1.yaml)；[`ui_spec-step7-proposal-review.md`](../../02_ux_ui/ui_spec-step7-proposal-review.md)、[`ui_spec-step8-ai-render.md`](../../02_ux_ui/ui_spec-step8-ai-render.md) |
| 維運承接 | RB-002（[`runbook-genpic-provider-failure.md`](../../06_ops/runbook-genpic-provider-failure.md)）、RB-005（[`runbook-delivery-pdf-engine-missing.md`](../../06_ops/runbook-delivery-pdf-engine-missing.md)） |
| 相關決策 | [`ADR-006`](./ADR-006-appliances-render-context-only.md)（家電只進 `render_context` 供生圖）、[`ADR-010`](./ADR-010-static-frontend-and-eight-step-collapse.md)（靜態前端無處藏秘密）、[`ADR-012`](./ADR-012-pilot-loopback-deployment.md)（loopback 部署是唯一邊界） |
| 取代關係 | 無（Supersedes：無；Superseded-by：無） |
