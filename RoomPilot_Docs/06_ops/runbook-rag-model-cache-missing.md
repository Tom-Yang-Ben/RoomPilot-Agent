# Runbook：檢索模型快取缺失與檢索降級 (Runbook - RAG Model Cache Missing) - RoomPilot

> **版本:** v1.0 ｜ **更新:** 2026-08-12 ｜ **狀態:** 草稿（待 owner 核准）
> **Owner:** MOD-RAG owner（Django，模型與檢索品質）＋ MOD-SRV-API owner（Bella，HTTP adapter 與佇列）
> **語域:** L3（工程）——直接寫端點、錯誤碼、環境變數與檔案路徑
> **實例:** 每故障症狀一份（`runbook-rag-model-cache-missing.md`，編號 **RB-004**）
>
> **本文件回答**：第 5 步問卷的 RAG 排序不可用時，怎麼在五分鐘內判斷是哪一個 blocker、要不要動作、找誰。
> **本文件不含**：檢索與排序演算法（去 [`ADR-008`](../03_architecture/adr/ADR-008-rag-retrieval-only-offline-models.md) 與 [`lld.md`](../04_design/lld.md)）、端點欄位契約（去 [`api_spec.md`](../04_design/api_spec.md) 與 [`openapi-agent-rag-v1.yaml`](../04_design/openapi-agent-rag-v1.yaml)）、第 5 步畫面規格（去 [`ui_spec-step5-requirements.md`](../02_ux_ui/ui_spec-step5-requirements.md)）、型錄 DB 故障（去 [`RB-001`](./runbook-catalog-db-unavailable.md)）。
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

| 觀察點 | 實際會看到什麼 | 佐證 |
| :--- | :--- | :--- |
| 狀態端點 | `GET /api/rag/status` 回 `ready:false` ＋ `blockers[]` 具名清單；本身不載模型也不呼叫 LLM | `rag/service.py:75-109`；`rag_api.py:164-166` |
| 同步檢索 | `POST /api/rag/search` 回 **503** `rag_dependency_unavailable`（`retryable:true`），訊息「RAG 必要套件、模型或設定尚未就緒。」 | `rag_api.py:48-57,169-175`；`rag/errors.py:12-13` |
| 非同步工作 | 佇列已滿回 **429** `rag_job_capacity_reached`；工作過期或行程重啟後輪詢回 **404** `rag_job_not_found` | `rag_api.py:183-191,211-221` |
| 第 5 步畫面 | 房間導覽鈕停在 `is-rag-pending`（`queued`／`running`），失敗後 `state.roomRagJobs[roomId].status` 轉 `unavailable` | `scene_v2.js:7798-7804,895-904,910-915` |
| 畫面文案 | 「目前使用基本推薦；RAG 服務尚未就緒，不影響繼續填寫。」／「目前保留原本的推薦順序；RAG 排序暫時無法完成，但不影響繼續填寫。」 | `scene_v2.js:901,913` |
| 進第 6 步 | 12 秒仍未收斂 → 紅字「RAG 尚在整理部分家具；本次先保留可用的推薦，完成後會同步更新。」，**仍然放行** | `scene_v2.js:918-936` |

> **告警來源：無。** 本 repo 沒有監控、沒有告警、沒有 on-call 輪值——`backend/server/main.py:195-197` 只建立 FastAPI app 與 GZip middleware，全檔無 `logging.basicConfig`，`backend/server/*.py` 無 prometheus／sentry／opentelemetry 匯出（2026-08-12 實跑 `rg "logging.basicConfig|prometheus|sentry|opentelemetry" backend/server/*.py` 零命中）。**唯一發現途徑是使用者回報或上表的畫面文案。**

## 2. Impact（影響）

| 項目 | 內容 |
| :--- | :--- |
| **受影響功能** | 只有第 5 步「家具推薦排序」。命中的 `item_id` 只被排到前面，候選集合不增不減（`scene_v2.js:881-888`）；排序消失＝回到原本推薦順序 |
| **不受影響** | 問卷填寫與逐房確認、第 6 步選件與擺位、家具合法性（一律由 `backend/engine/` 裁決）、第 7–8 步 |
| **降級是設計行為** | 檢索失敗一律降級 `unavailable` 並**不阻塞問卷**——`catch` 區塊註解明寫 `RAG is an enhancement to ranking; questionnaire completion never blocks on it.`（`scene_v2.js:910-915`）；`settleQuestionnaireRagForLayout()` 逾時仍回傳並放行（`scene_v2.js:925-935`）。看到 `unavailable` **不等於**系統故障，對應 FR-049、ADR-008 |
| **嚴重程度判定** | 預設 P3（品質降級，不中斷交付）。升級為 incident 的條件只有三種：①`/api/rag/status` 本身 5xx 或逾時；②使用者**確實被擋住**無法確認房間需求（現況程式不會發生，若發生即為 regression）；③blocker 含 `postgresql_unavailable` 且 `/api/catalog/status` 同時 `available:false`——那是型錄故障，改走 [`RB-001`](./runbook-catalog-db-unavailable.md) |

## 3. Possible Causes（可能原因）

按發生機率排序（blocker 字串即根因標籤，不必猜）：

1. **功能未啟用**：`ROOMPILOT_RAG_ENABLED` 預設 `false` → blocker `feature_disabled`，且**只有這一項**時拋 `RagDisabledError`（503 `rag_disabled`）而非 dependency 錯誤。`rag/settings.py:76`；`rag/service.py:76-77,134-139`
2. **模型權重未快取**：`embedding_model_cache_missing`／`reranker_model_cache_missing`。runtime 是 offline-only（`local_files_only=True`），未快取直接 `RagDependencyError`，**絕不在請求路徑下載**。`model_runtime.py:19-47,104-105,116-128`；常駐約 4.6 GB（`docs/contracts/POSTGRESQL_FURNITURE_RAG_RUNTIME.md:101-102`）
3. **推論套件缺**：`torch`／`sentence_transformers` 未安裝 → `rag_model_packages_missing`。`model_runtime.py:64-71`；`rag/service.py:84-85`
4. **PostgreSQL 不可用**：`postgresql_unavailable`（`embedding_status()` 拋例外時整段降級）。`rag/service.py:91-106`；`catalog/rag_repository.py:53-89`
5. **向量資料未匯入或 SQL function 缺**：`furniture_embeddings_empty`（`current_embeddings <= 0`）／`filtered_search_function_missing`（`roompilot.search_furniture_embeddings_filtered` 不存在）。`rag/service.py:93-96`；`catalog/rag_repository.py:56-89`
6. **Parser 設定不全**：`parser_provider_invalid`／`{provider}_api_key_missing`／`{provider}_package_missing`（provider 僅接受 `openai`／`anthropic`／`openrouter`；`openrouter` 走標準函式庫故無套件前置）。`rag/service.py:67-83`
7. **佇列打滿（429）**：只有**一條 daemon worker** 序列化所有檢索，`queued`＋`running` 合計達 24 即拒收；完成／失敗工作保留 3600 秒後清除。`rag_api.py:28-34,121-137,183-191`
8. **改了環境變數卻沒生效**：`_setting()` **先讀專案 `.env`、再 fallback `os.getenv`**——shell 的 export 蓋不掉 `.env` 內既有的鍵。`rag/settings.py:23-28`
9. **行程重啟**：工作狀態只存行程記憶體 `RAG_JOBS`，重啟即失，前端輪詢得 404。`rag_api.py:28,211-221`（NFR-009）

## 4. Diagnosis（診斷步驟）

服務位址固定 `http://127.0.0.1:8002`（`README.md:49`）。整條路徑的**唯一權威判讀點是 blocker 清單**，第 1 步就會給出答案。

```bash
# 1. 一次看完所有 blocker（此端點不載模型、不呼叫 LLM，可安全重複打）
curl -s http://127.0.0.1:8002/api/rag/status
curl -s http://127.0.0.1:8002/api/rag/status | python -m json.tool   # 要格式化時
# PowerShell: (Invoke-RestMethod http://127.0.0.1:8002/api/rag/status).blockers

# 2. blocker 含 postgresql_unavailable / furniture_embeddings_empty → 交叉確認型錄 DB，改走 RB-001
curl -s http://127.0.0.1:8002/api/catalog/status

# 3. blocker 含 *_model_cache_missing → 在「伺服器主機」上找快取（status 刻意不回 cache_dir，service.py:64-66）
#    目錄優先序：.env 的 ROOMPILOT_RAG_MODEL_CACHE > HF_HOME > ~/.cache/huggingface（settings.py:59-60,96）
ls -d "${HF_HOME:-$HOME/.cache/huggingface}"/hub/models--BAAI--bge-m3 \
      "${HF_HOME:-$HOME/.cache/huggingface}"/hub/models--BAAI--bge-reranker-v2-m3 2>/dev/null
find "${HF_HOME:-$HOME/.cache/huggingface}" -name config.json -path "*BAAI*" | head   # 判定條件＝snapshots 底下有 config.json

# 4. blocker 含 rag_model_packages_missing → 用「該服務的」直譯器確認，不是系統 python
./.venv/Scripts/python.exe -c "import importlib.util as u; print(u.find_spec('torch'), u.find_spec('sentence_transformers'))"

# 5. 收到 429 → 看有幾筆卡住（單 worker，滿了只能等；上限 24 是契約值）
grep -n "RAG_JOB_MAX_QUEUED\|RAG_JOB_TTL_SECONDS" backend/server/rag_api.py

# 6. 端到端最小驗證（fast 路徑，與第 5 步同一組參數）
curl -s -X POST http://127.0.0.1:8002/api/rag/search/jobs \
  -H "content-type: application/json" \
  -d '{"query":"三人沙發 淺色布","top_k":6,"fast":true}'
curl -s http://127.0.0.1:8002/api/rag/search/jobs/<job_id>

# 7. 想知道使用者當時的降級狀態 → 從已保存的專案 payload 撈（前端 state 不對外暴露）
curl -s http://127.0.0.1:8002/api/projects/<project_id> | rg -o '"rag_jobs":.{0,240}'
```

第 7 步的 `rag_jobs` 由前端寫入 `/api/scene/generate` 請求與 `scene_json.questionnaire`（`scene_v2.js:12681-12711,12758-12766`），並在第 8 步 render context 逐房保留一份 `rag`（`scene_v2.js:16091`）——可用來回溯「哪幾房是降級跑完的」。

## 5. Mitigation（短期緩解）

1. **先判斷要不要動作。** blocker 只影響排序時，正確處置是**告知使用者可繼續填寫**，不做任何操作（§2）。半夜不需要為 P3 叫醒第二個人。
2. **想讓狀態明確可解釋**：把 `ROOMPILOT_RAG_ENABLED=false` 寫進**專案根目錄 `.env`**（不是 shell export，見 §3-8）。blocker 會收斂成單一 `feature_disabled`，錯誤碼由 `rag_dependency_unavailable` 變 `rag_disabled`，前端一樣走 `unavailable` 降級。`rag/settings.py:23-28,76`；`rag/service.py:134-139`
3. **429**：等待現有工作跑完即可，完成／失敗工作 3600 秒後自動清除。**不要調大 `RAG_JOB_MAX_QUEUED`**——24 與單 worker 是 NFR-009 的契約值，改它會讓兩個 CPU 模型工作互搶資源。`rag_api.py:28-34,121-137`
4. **PostgreSQL 類 blocker**：本 runbook 到此為止，交棒 [`RB-001`](./runbook-catalog-db-unavailable.md)。
5. **不得做的事**：不得為了「讓它動」而移除 `local_files_only=True`（`model_runtime.py:120,127`）——請求路徑內下載 GB 級權重會把秒級延遲變成長時間阻塞；不得以假結果或隨機排序補位（NFR-014、ADR-009 的誠實中止原則）。

> **待確認（無新編號）**：模型權重由誰提供、放在哪個路徑、版本如何驗證——本 repo **無下載腳本、無安裝步驟**（`AGENTS.md:59` 明文禁止提交模型權重；全 repo 僅 `rag/settings.py:59` 提及 `HF_HOME`），因此本節無法給出「取得權重」的可執行指令。此項連同 OPEN-43（檢索契約寫「不接入八步流程」但第 5 步已接入）一併待 owner 裁決，承接於 [`deployment_and_operations.md`](./deployment_and_operations.md) 與 [`ADR-008`](../03_architecture/adr/ADR-008-rag-retrieval-only-offline-models.md)。

## 6. Recovery（恢復確認）

- **補齊權重或修正 `.env` 後不需要重啟服務**：`/api/rag/status` 每次呼叫都重新掃檔（`model_runtime.py:42-47`）並重讀專案 `.env`（`rag/settings.py:23-28,58-98`）；模型只在**成功載入時**才寫入行程快取（鍵為 `(cache_dir, device)`，`model_runtime.py:96-99,132-135`），失敗不會留下毒化狀態。
- 恢復順序：①`curl /api/rag/status` 確認 `ready:true` 且 `blockers:[]` → ②送 §4-6 的最小 job 並輪詢到 `status:"completed"` → ③在第 5 步重新確認任一房間，導覽鈕應由 `is-rag-pending` 轉為 `is-confirmed`（`scene_v2.js:7799-7801`）。
- **沒有 alert 可以解除**（§1）。恢復基線＝上述三項全綠；無延遲基線可比對——生圖與檢索的端到端耗時目標值本 repo 未定義（NFR-025）。
- 事故結束後 48 小時內留一則覆盤紀錄；本 repo 無 postmortem 目錄，依需增建。

## 7. Escalation（升級路徑）

**本專案無 on-call 輪值、無值班系統、無告警管道**；下表的「管道」一律是團隊既有溝通方式加 repo issue，不存在自動派工。

| 情況（以 blocker 判斷） | 找誰 | 管道與依據 |
| :--- | :--- | :--- |
| `*_model_cache_missing`、`rag_model_packages_missing`、排序結果明顯異常但服務健康 | **Django**（MOD-RAG） | 家具 RAG 解析／檢索／排序與 BGE-M3、reranker 品質由其維護：`docs/TEAM_AI_OWNERSHIP.md:11,24,55` |
| `postgresql_unavailable`、`furniture_embeddings_empty`、`filtered_search_function_missing` | **Kai**（MOD-CAT／MOD-SQL） | 正式家具、metadata 與 pgvector 查詢：`docs/TEAM_AI_OWNERSHIP.md:12,25,27,55`；併走 [`RB-001`](./runbook-catalog-db-unavailable.md) |
| 429／404 佇列行為、`/api/rag/status` 本身 5xx、第 5 步降級文案或旗標錯誤 | **Bella**（MOD-SRV-API／MOD-WEB） | 只提供 HTTP／UI adapter：`docs/TEAM_AI_OWNERSHIP.md:9,21,22,55` |
| 排序回來但選件語意不合理（房型、成組、數量） | **Yen**（MOD-AGT） | 需求結構化、偏好與選件決策：`docs/TEAM_AI_OWNERSHIP.md:13,28` |
| 緩解 30 分鐘無效**且**使用者確實被擋住（非單純降級） | 產品 owner | 屬 DEC-016／DEC-017 邊界問題，於 [`requirements_tracker.xlsx`](../01_requirements/requirements_tracker.xlsx) ②決策沿革留一列 |

## 8. 追溯

| 項目 | ID／來源 |
| :--- | :--- |
| Runbook 編號 | **RB-004** |
| 對應告警 | **無告警來源**——本 repo 無監控／告警／on-call；發現途徑＝使用者回報或第 5 步畫面錯誤文案 |
| 對應步驟 | S5 需求問卷（[`srs.md`](../01_requirements/srs.md) §9.2） |
| 對應 FR | FR-046、FR-048、FR-049、FR-067 |
| 對應 NFR | NFR-009、NFR-010、NFR-014 |
| 對應 DEC | DEC-016、DEC-017 |
| 對應 ACPT／SCN | ACPT-041、ACPT-042、ACPT-043；SCN-014–016 |
| 對應 MOD（owner） | MOD-RAG（Django）、MOD-SRV-API／MOD-WEB（Bella）、MOD-CAT／MOD-SQL（Kai） |
| 對應 ADR | [`ADR-008`](../03_architecture/adr/ADR-008-rag-retrieval-only-offline-models.md)、[`ADR-009`](../03_architecture/adr/ADR-009-server-governed-ai-generation.md) |
| 對應 TC | TC-041、TC-042、TC-043（[`test_plan.md`](../05_qa/test_plan.md)） |
| 相關 runbook | [`RB-001`](./runbook-catalog-db-unavailable.md)（PostgreSQL 同根因）、[`RB-009`](./runbook-runtime-storage-growth.md)（模型快取磁碟占用） |
| 待確認 | OPEN-43；以及 §5 註記的「模型權重取得方式未定義」 |
| 事故紀錄 | 無（本 repo 無 postmortem 目錄，依需增建） |
