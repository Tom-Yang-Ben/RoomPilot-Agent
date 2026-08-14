# Runbook - 生圖供應商失效 (GenPic Provider Failure) - RoomPilot

> **版本:** v1.0 ｜ **更新:** 2026-08-12 ｜ **狀態:** 草稿（待 owner 核准）
> **Owner:** Bella（MOD-SRV-RENDER，`backend/server/ai_render_service.py`；`docs/TEAM_AI_OWNERSHIP.md:9,21`）；重試次數與 notices 文字屬 Yen（MOD-AGT，`backend/agent/`；`TEAM_AI_OWNERSHIP.md:13,28`）
> **語域:** L3（工程）
> **實例:** 每故障症狀一份（`runbook-<symptom>.md`）；本份編號 **RB-002**
>
> **本文件回答**：第 7 步色卡比較圖或第 8 步逐房生圖／改圖失敗（503 未設金鑰、502 上游拒絕、`GenPicFailure`）時，怎麼分辨是四種形態的哪一種、怎麼恢復、恢復不了找誰。
> **本文件不含**：端點欄位契約（去 [`api_spec.md`](../04_design/api_spec.md)、[`openapi-render-delivery-v1.yaml`](../04_design/openapi-render-delivery-v1.yaml)）、為什麼生圖一律由伺服器治理（去 [`ADR-009`](../03_architecture/adr/ADR-009-server-governed-ai-generation.md)）、畫面文案與互動細節（去 [`ui_spec-step7-proposal-review.md`](../02_ux_ui/ui_spec-step7-proposal-review.md)、[`ui_spec-step8-ai-render.md`](../02_ux_ui/ui_spec-step8-ai-render.md)）、交付 PDF 排版引擎缺席（去 [`runbook-delivery-pdf-engine-missing.md`](./runbook-delivery-pdf-engine-missing.md)，RB-005）、家具擺不下（去 [`runbook-placement-blocked.md`](./runbook-placement-blocked.md)，RB-007）、啟動與部署程序（去 [`deployment_and_operations.md`](./deployment_and_operations.md)）。
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

---

## 1. Symptoms（症狀）

**無告警來源。** 本 repo 無監控、無 dashboard、無告警規則、無 on-call 輪值；`backend/server/main.py`、`backend/server/ai_render_service.py`、`backend/agent/llm.py` 三檔**零 `logging` 呼叫**（`rg -c "logging|logger\." → 0`），伺服器端只有 uvicorn 存取日誌。**失敗原因只存在於 HTTP 回應 body 與瀏覽器畫面文案**，故障入口是使用者回報。

| 觀察點 | 使用者看到的字 | 佐證 |
| :--- | :--- | :--- |
| S8 服務狀態列 | `尚未設定生圖服務` | `scene_v2.js:16655-16658` |
| S8 單張生圖 | `生圖失敗：<原因>` | `scene_v2.js:17069` |
| S8 一鍵全生 | 部分失敗 `一鍵生圖完成 N 房、失敗 M 房；失敗的可單獨重試。`／整批中止 `一鍵生圖失敗：<原因>` | `scene_v2.js:17119-17126` |
| S7 色卡 | 模型全敗 `色卡比較圖生成失敗，請稍後再試。`／HTTP 層失敗 `色卡比較圖建立失敗：<原因>` | `scene_v2.js:16739-16742,16751` |

| HTTP 表現 | 端點 | 佐證 |
| :--- | :--- | :--- |
| **503** `openrouter_api_key_not_configured` | `ai-renders`／`palette-renders`／`edit` | `main.py:2109-2116`、`2183-2190`、`2262-2269` |
| **502** `ai_edit_failed`（改圖主＋備援皆敗） | `.../ai-renders/{room_id}/edit` | `main.py:2270-2274` |
| **201** 但 `results[].status:"failed"` ＋ `notices[]` | `ai-renders`／`palette-renders` | `ai_render_service.py:376-385`、`470-475` |
| **201** 且多一個 `night_notices`（只有夜景敗） | `ai-renders` | `ai_render_service.py:412-413` |
| **409** `palette_already_generated` | `palette-renders` | `main.py:2148-2155` |

`notices[]` 是唯一的根因線索，形狀固定：`<model> 第 <n> 次失敗：<reason>`（`genpic_agent.py:168`）、`主模型 <m> 已達 3 次失敗上限，改用備援模型 <f> 重試。`（`genpic_agent.py:185-189`）。`<reason>` 原文只有三種來源：`OpenRouter 回應 <HTTP 碼>：<body 前 300 字>`、`OpenRouter 連線失敗：<例外>`、`生圖模型未回傳影像內容`（`agent/llm.py:194-198,272`）。

## 2. Impact（影響）

失敗政策由程式強制：主模型最多 3 次 → 備援模型再 3 次 → 拋 `GenPicFailure`（`genpic_agent.py:29-31,144-190`；NFR-012）。四種形態的處置完全不同：

| # | 形態 | 判定 | 阻塞範圍 | 可逆性 | 嚴重度 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| A | **單房失敗** | 201，該房 `status:"failed"`，其他房 `completed` | 只有該房；其餘照常交付 | 可逆：該房單獨重生 | 低 |
| B | **夜景失敗** | 201，日光圖正常，多一個 `night_notices` | 只少客廳夜間圖（設計手冊少一張） | 半可逆：**無夜景單獨重試路徑**，只能重生整個客廳（會覆蓋日光圖） | 低 |
| C | **全批失敗** | 503（未設金鑰）或全房 `failed` | 第 8 步整步卡死；`workflow.complete("ai_render")` 不會發生（`scene_v2.js:17061,17115-17117`） | 可逆：修好設定後重跑 | **高** |
| D | **色卡全失敗** | 201，`already_generated:false`，**不寫鎖定旗標** | 第 7 步不能進第 8 步 | 可逆：可直接重試（`main.py:2191-2198`） | 中 |

**不可逆的邊界**：色卡只要**有一張成功**就寫入 `palette_render.generated:true`，每案僅此一次；失敗的那幾張永遠不會補（`main.py:2148-2155,2199-2214`；FR-056、DEC-010）。要重生必須走 §5 的解鎖動作，屬成本政策，需 owner 同意。

**副作用警告（已驗證）**：`ai-renders` 以 `{"ai_render": {"rooms": [...]}}` 寫回 workflow（`main.py:2117-2126`），而深合併對 list 是**整條取代**（`project_store.py:18-25`）。因此**單房重生會把 `ai_render.rooms` 換成只剩該房**，其餘房的 `lock_manifest` 消失，那些房再按「修改」會得到 409 `room_not_generated`（`main.py:2237-2241`）。見 §7.2。

## 3. Possible Causes（可能原因）

按發生機率排序：

1. **`OPENROUTER_API_KEY` 未設或 `.env` 未建立** → `gateway.available` 為 False → `AiRenderNotConfigured` → 503（`agent/llm.py:133,151-153`；`ai_render_service.py:342-343,441-442`）。`.env` 只在模組 import 時載入一次（`services/cloud_images.py:16-18`，由 `main.py:100` 匯入），**改完必須重啟行程**。
2. **上游明確拒絕**：額度用盡（402）、rate limit（429）、模型下線（404）、供應商 5xx → `OpenRouter 回應 <碼>：…`，主＋備援共 6 次全敗（`agent/llm.py:189-196`；`genpic_agent.py:161-190`）。
3. **併發放大 rate limit**：一鍵全生以 `max_workers = 房數` 同時打出 N 個請求（`ai_render_service.py:423-426`；NFR-018），單張生圖只送 1 房（`scene_v2.js:16982-16990`）。房數多時 A 形態會集中出現。
4. **連線或逾時**：TLS／DNS／代理問題走 `OpenRouter 連線失敗：…`；單次逾時預設 120 秒，由 `ROOMPILOT_AGENT_LLM_TIMEOUT` 控制（`agent/llm.py:147-149,157-165,197-198`）。模型只回文字不回圖則是 `生圖模型未回傳影像內容`（`agent/llm.py:266-272`）。
5. **模型 id 覆蓋錯誤**：`ROOMPILOT_GENPIC_MODEL`／`ROOMPILOT_GENPIC_FALLBACK_MODEL` 指到不存在的 id（沒設時的內建預設 `x-ai/grok-imagine-image-2.0` ＋ `google/gemini-2.5-flash-image`）；第 7 步色卡另用一顆較高階模型（預設 `google/gemini-3-pro-image-preview`），由 `ROOMPILOT_GENPIC_PALETTE_MODEL` 控制——**S7 壞、S8 好**幾乎一定是這條。哪個功能吃哪個變數見 `backend/model_config.py` 的 `REGISTRY`。
6. **模型 id 存在但沒出現在預設模型清單**：OpenRouter 的 `/api/v1/models` **不含生圖模型**，要 `?output_modalities=image` 才查得到（45 顆）。用預設清單驗證會誤判成「模型不存在」。生圖一律送 `/api/v1/images`（`agent/llm.py:37`），不是 `chat/completions`。
7. **不是本 runbook**：422 `scene_required`／`room_views_required`／`reference_png_required` 是前置條件不足（`main.py:2084-2106`），請使用者回第 6／7 步；`/api/projects/{id}/render-jobs` 的 503／502 屬另一套遠端渲染商（`main.py:2033-2057`、`REMOTE_RENDER_CONTRACT.md`），與 GenPic 無關。

## 4. Diagnosis（診斷步驟）

在 repo 根目錄 `D:\RoomPilot-Agent` 開 PowerShell；服務位址 `http://127.0.0.1:8002`（`README.md:45-49`）。

```powershell
# 1. 生圖服務有沒有金鑰、用哪顆模型（不外洩 token；main.py:2064-2067、ai_render_service.py:65-74）
curl.exe -s http://127.0.0.1:8002/api/ai-render/status
#   {"configured":false,...} → 原因 1，跳 §5 列 1
#   configured:true 但 model 不是預期的 id → 原因 5

# 2. 伺服器行程實際讀到什麼（金鑰只印布林，不印值）
.\.venv\Scripts\python.exe -c "from backend.agent.llm import OpenRouterGateway as G; g=G(); print(g.available, g.image_model, g.image_fallback_model, g.timeout_seconds)"

# 3. 直接對上游打一發最小請求，取回原始 reason（會計費一次；只有這步能區分原因 2/4）
.\.venv\Scripts\python.exe -c "from backend.agent.llm import OpenRouterGateway as G; r=G().generate_image('a plain white interior wall, photo'); print(r.model, len(r.image_b64))"
#   拋 LLMError 的訊息＝使用者 notices 裡的 <reason> 原文

# 4. 第 7 步色卡是另一顆模型，要另外驗（ai_render_service.py:289-296）
.\.venv\Scripts\python.exe -c "from backend.server.ai_render_service import _palette_gateway as p; g=p(); print(g.available, g.image_model, g.image_fallback_model)"

# 5. 這顆模型在 OpenRouter 上到底存不存在、能不能出圖（免費、不計費）
curl.exe -s "https://openrouter.ai/api/v1/models/<MODEL_ID>/endpoints" | .\.venv\Scripts\python.exe -c "import sys,json; d=json.load(sys.stdin)['data']; print(d['id'], d['architecture']['modality'], d['architecture']['output_modalities'])"
#   404 或 output_modalities 不含 image → 原因 5；查得到卻仍失敗 → 原因 2/4

# 6. 這個專案目前的鎖定狀態：色卡是否已鎖、哪幾房有 lock_manifest
.\.venv\Scripts\python.exe -c "import json,urllib.request as u; p=json.load(u.urlopen('http://127.0.0.1:8002/api/projects/<PROJECT_ID>'))['project']['workflow']; print(json.dumps({'palette_render':p.get('palette_render'),'ai_render_rooms':[r.get('room_id') for r in (p.get('ai_render') or {}).get('rooms') or []]},ensure_ascii=False))"
```

**取得 `notices` 原文**：伺服器不落地任何應用日誌，請使用者在瀏覽器 DevTools → Network 找 `POST /api/projects/<id>/ai-renders`（或 `palette-renders`），複製回應 body 的 `results[].notices` 與 `night_notices`。

## 5. Mitigation（短期緩解）

| 形態／原因 | 動作 | 佐證 |
| :--- | :--- | :--- |
| 未設金鑰（C） | 於 repo 根 `.env` 設 `OPENROUTER_API_KEY=...`（`Copy-Item .env.example .env`），**重啟 uvicorn**：`.\.venv\Scripts\python.exe -m uvicorn backend.server.main:app --host 127.0.0.1 --port 8002`。此時尚未寫入任何 `ai_render` 狀態，無須清理 | `README.md:45-49`；`services/cloud_images.py:16-18` |
| 上游拒絕／rate limit（A、C） | 改用「單張生圖」逐房送（併發降為 1），不要按一鍵全生；或等待後重試。若特定模型異常，在 `.env` 設 `ROOMPILOT_GENPIC_MODEL=<可用 id>`（S7 色卡另設 `ROOMPILOT_GENPIC_PALETTE_MODEL`）後重啟 | `ai_render_service.py:423-426,289-296`；`scene_v2.js:16982-16990`；`agent/llm.py:135-142` |
| 單房失敗（A） | 請使用者對該房重按生圖即可；成功後才會寫入該房 `lock_manifest`、改圖才可用。**先讀 §2 副作用警告**，必要時改為重跑整批 | `scene_v2.js:17036-17045`；`main.py:2117-2126,2237-2241` |
| 夜景失敗（B） | 無單獨重試路徑；只能重生整個客廳（日光圖會被覆蓋）。若日光圖已被使用者接受，建議**不重生**，接受少一張夜間圖 | `ai_render_service.py:395-413` |
| 色卡全失敗（D） | 直接請使用者重按；伺服器沒鎖，不需任何維運動作 | `main.py:2191-2198` |
| 色卡部分成功後要重生（**需 owner 同意**） | 把旗標寫回 false 再請使用者重生：<br>`.\.venv\Scripts\python.exe -c "import json,urllib.request as u; r=u.Request('http://127.0.0.1:8002/api/projects/<PROJECT_ID>/workflow',data=json.dumps({'workflow':{'palette_render':{'generated':False}}}).encode(),headers={'Content-Type':'application/json'},method='PUT'); print(u.urlopen(r).status)"`<br>（`workflow` 只需是物件、鍵不受白名單限制；深合併覆寫布林） | `main.py:1812-1814`；`project_store.py:18-25` |

**禁止事項**：不得以占位圖、舊圖或任何本地素材充當生成結果（DEC-017、NFR-014、`AI_RENDER_OPENROUTER_CONTRACT.md:39-41`）。不得在 `ai_render_service.py` 內另做一套重試——失敗政策的唯一權威是 `GenPicAgent`（`AI_RENDER_OPENROUTER_CONTRACT.md:9-11`）。

## 6. Recovery（恢復確認）

1. `curl.exe -s http://127.0.0.1:8002/api/ai-render/status` 回 `"configured":true` 且 `model` 為預期 id。
2. 使用者重跑後回應 `results[]` 中目標房 `status:"completed"` 且有 `image_data_url`；一鍵全生的 `失敗 M 房` 為 0（`scene_v2.js:17119-17126`）。所有房都 `submitted_at` 後前端才 `complete("ai_render")`、第 8 步才放行（`scene_v2.js:17115-17117`）；第 7 步則需 `palette_render.generated` 為 true 且 `cards[]` 有 `completed`。
3. 改圖可用性：§4 步驟 5 印出的 `ai_render_rooms` 應包含**所有已生圖房**；缺房代表 §2 副作用已發生，須整批重生才能恢復改圖。
4. **無 alert 可解除、無 SLO 可比對**：生圖端到端耗時與可用率目標值未定義（NFR-025）。

## 7. Escalation（升級路徑）

### 7.1 升級對象

本 repo **無 on-call 系統、無值班表、無 paging**；管道一律為直接聯絡對應 owner。

| 情況 | 找誰 | 依據 |
| :--- | :--- | :--- |
| 金鑰、`.env`、模型 id、adapter 編排、workflow 寫入副作用 | Bella（MOD-SRV-RENDER／MOD-SRV-STORE） | `TEAM_AI_OWNERSHIP.md:9,21` |
| 重試次數、fallback 切換、`notices` 文字、`GenPicFailure` 語意 | Yen（MOD-AGT，`backend/agent/`） | `TEAM_AI_OWNERSHIP.md:13,28`；`AI_RENDER_OPENROUTER_CONTRACT.md:9-11` |
| 色卡解鎖、改圖額度、重生成本 | 產品 owner（DEC-010、DEC-011，`requirements_tracker.xlsx` ①需求決策） | [`srs.md`](../01_requirements/srs.md) §1.1 |

事故結束後 48 小時內完成覆盤紀錄（正式覆盤文件依需增建）。

### 7.2 待確認（程式碼看不出答案）

| # | 待確認內容 | 目前可驗證的事實 |
| :--- | :--- | :--- |
| 1 | 單房重生使其他房 `lock_manifest` 消失，是刻意（重生＝新一批）還是缺陷 | `main.py:2117-2126` 整條覆寫 `rooms`；`project_store.py:18-25` list 不深合併；契約寫「每次重新生圖視為新一批」（`AI_RENDER_OPENROUTER_CONTRACT.md:32-33`）但未說明只重生一房的情形；與 OPEN-16 同源 |
| 2 | 色卡「每案一次」在維運上可否解鎖、由誰核可 | 伺服器強制 409（`main.py:2148-2155`）；repo 內無解鎖端點、無核可紀錄 |
| 3 | 生圖失敗率／端到端耗時的可接受門檻、OpenRouter 帳戶額度告警，以及**帳戶與計費由誰負責** | NFR-025 目標值未定義；本 repo 無監控與告警機制，亦無帳戶持有人紀錄 |

## 8. 追溯

| 項目 | ID／文件 |
| :--- | :--- |
| Runbook 編號 | **RB-002**（覆蓋 [`srs.md`](../01_requirements/srs.md) §9.2 的 S7、S8 兩列） |
| 對應告警／事故紀錄 | **無告警來源**（本 repo 無監控／告警／on-call、無 postmortem 紀錄）；觸發途徑為使用者回報與 §1 的畫面文案 |
| 上游 NFR | NFR-012（失敗政策）、NFR-014（503／502／409 誠實語意）、NFR-018（併發）、NFR-025（目標值未定義） |
| 上游 FR／DEC | FR-056、FR-058、FR-060、FR-067；DEC-010、DEC-011、DEC-017（見 [`brd.md`](../01_requirements/brd.md)） |
| 驗收與測試 | ACPT-048、ACPT-050、ACPT-052、ACPT-060（[`prd.md`](../01_requirements/prd.md)）；TC-048、TC-050、TC-052、TC-060（[`test_plan.md`](../05_qa/test_plan.md)） |
| 架構決策與契約 | [`ADR-009`](../03_architecture/adr/ADR-009-server-governed-ai-generation.md)、[`ADR-006`](../03_architecture/adr/ADR-006-appliances-render-context-only.md)、[`sad.md`](../03_architecture/sad.md) MOD-SRV-RENDER／MOD-AGT；`docs/contracts/AI_RENDER_OPENROUTER_CONTRACT.md` |
| 相鄰 runbook | [`runbook-delivery-pdf-engine-missing.md`](./runbook-delivery-pdf-engine-missing.md)（RB-005）、[`runbook-workflow-save-conflict-or-oversize.md`](./runbook-workflow-save-conflict-or-oversize.md)（RB-003）、[`runbook-placement-blocked.md`](./runbook-placement-blocked.md)（RB-007）；索引見 [`00-registry.md`](../00-registry.md) |
