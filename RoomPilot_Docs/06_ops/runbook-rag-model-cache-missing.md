# Runbook - RAG 模型快取缺失（/rag 檢索不可用）

> **版本:** 0.1 | **更新:** 2026-08-11 | **狀態:** 草稿
> **Owner:** Django（`backend/spatial_data/rag/` 模型 runtime，TEAM_AI_OWNERSHIP.md:24）＋ Bella（`backend/server/rag_api.py` HTTP adapter，TEAM_AI_OWNERSHIP.md:55）——AI 衍生，人工核准前為 TO-BE
> **語域:** L3（工程）
> **實例:** 每故障症狀一份（本份對應 [00-registry.md](../00-registry.md) §4 slug `rag-model-cache-missing`）
> **定位宣告:** 本文件回答「/rag 檢索因 BGE-M3／reranker 模型快取或套件缺失而不可用時，如何診斷與恢復」；不包含 PostgreSQL pgvector 故障（blocker `postgresql_unavailable`，屬 catalog DB 症狀，見 [runbook-catalog-db-unavailable.md](./runbook-catalog-db-unavailable.md)）、parser API key 缺失（blocker `*_api_key_missing`，設定問題見 [deployment_and_operations.md](./deployment_and_operations.md)）與 RAG 檢索品質問題。
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

本專案為本機 Pilot，無 Grafana／告警系統；症狀來源是**使用者回報與 API 回應**：

- `/rag` 測試頁搜尋失敗，畫面顯示「RAG 必要套件、模型或設定尚未就緒。」（rag_api.py:52 的 503 訊息）。
- `POST /api/rag/search` 回 **503**，`detail.code = "rag_dependency_unavailable"`（errors.py:12-13、rag_api.py:51-52）。
- job 模式（`POST /api/rag/search/jobs`）建立成功（202），但輪詢 `GET /api/rag/search/jobs/{job_id}` 得到 `status: "failed"`，`error.code = "rag_dependency_unavailable"`（rag_api.py:97-108）。
- `GET /api/rag/status` 回 `ready: false`，`blockers` 陣列含 `embedding_model_cache_missing` 或 `reranker_model_cache_missing`（service.py:86-89）。
- 伺服器例外訊息：`RagDependencyError("RAG model weights are not cached")`（model_runtime.py:104-105）或 `("RAG model weights could not be loaded")`（model_runtime.py:130-131）。

**關鍵背景**：模型 runtime 是 offline-only——載入時 `local_files_only=True`（model_runtime.py:120、127），伺服器**絕不會在請求期間自動下載模型**（README:107）。快取一旦缺失，只能人工補齊。

## 2. Impact（影響）

| 項目 | 內容 |
| :--- | :--- |
| **受影響功能** | 僅 `/rag` 測試頁與 `/api/rag/search`（含 job 模式）。第一版 `/rag` 不接管第 6 步候選家具（TEAM_AI_OWNERSHIP.md:55），**八步主工作流完全不受影響** |
| **不受影響** | `GET /api/rag/status` 永遠可查（service.py:62-130）；第 6 步 `GET /api/furniture`、場景生成、生圖、交付全部照常 |
| **嚴重程度判定** | Pilot 內部工具，非 incident 等級。展示／驗收前需要 RAG demo 時才升為阻塞事項 |

## 3. Possible Causes（可能原因）

按發生機率排序（各原因對應的 `blockers` code 見 service.py:84-89）：

1. **模型從未下載**：新機器／新 clone，約 9 GB 的 BGE-M3＋reranker 快取不存在（README:94-100）→ `embedding_model_cache_missing`、`reranker_model_cache_missing`。
2. **快取目錄指錯位置**：`.env` 的 `ROOMPILOT_RAG_MODEL_CACHE` 或環境變數 `HF_HOME` 指向沒有模型的目錄；未設定時預設 `~/.cache/huggingface`（settings.py:59-60、96）。注意 `.env` 的值**優先於** process 環境變數（settings.py:23-28）。
3. **快取被清理／不完整**：目錄存在但 `snapshots/*/config.json` 缺失——判定標準就是 config.json 是否存在（model_runtime.py:23-39）。
4. **RAG 套件未安裝**：torch／sentence_transformers 不在 venv（model_runtime.py:64-71、102-103）→ blocker 是 `rag_model_packages_missing`，**不是** cache_missing——處置不同，見 §4 步驟 4。
5. **快取存在但權重損壞**：cache 檢查通過但載入拋例外，包成 `RagDependencyError("RAG model weights could not be loaded")`（model_runtime.py:130-131）。

## 4. Diagnosis（診斷步驟）

以下指令在 repo 根目錄 `C:\RoomPilot-Agent` 執行；伺服器預設 port 8002（README:49），實際 port 依啟動指令調整。

```powershell
# 1. 打 status 端點，看 blockers 陣列（永遠可查，不需要模型就緒）
curl.exe -s http://127.0.0.1:8002/api/rag/status | .\.venv\Scripts\python.exe -m json.tool
```

讀法（service.py:76-89）：

| blockers 內容 | 含義 | 下一步 |
| :--- | :--- | :--- |
| `embedding_model_cache_missing` / `reranker_model_cache_missing` | **本 runbook 的主症狀**：模型快取缺失 | 步驟 2-3 |
| `rag_model_packages_missing` | torch／sentence_transformers 未安裝（依賴缺失，非快取缺失） | 步驟 4 |
| `feature_disabled` | `.env` 未設 `ROOMPILOT_RAG_ENABLED=true` | 設定問題，非本 runbook |
| `postgresql_unavailable` / `furniture_embeddings_empty` | pgvector 側故障 | [runbook-catalog-db-unavailable.md](./runbook-catalog-db-unavailable.md) |

status 回應的 `models.embedding_cached` / `models.reranker_cached` 布林值直接告訴你哪一顆模型缺（model_runtime.py:42-47）。注意 API 回應刻意**不含** `cache_dir` 欄位（service.py:65-66），要查實際目錄用步驟 2。

```powershell
# 2. 在伺服器本機解析實際使用的快取目錄與快取狀態（走與伺服器完全相同的邏輯）
.\.venv\Scripts\python.exe -c "from pathlib import Path; from backend.spatial_data.rag.settings import load_rag_settings; from backend.spatial_data.rag.model_runtime import model_cache_status; s = load_rag_settings(Path('.')); print(model_cache_status(s.model_cache_dir))"
# 輸出範例：{'cache_dir': 'C:\\Users\\<user>\\.cache\\huggingface', 'embedding_cached': False, 'reranker_cached': True}
```

```powershell
# 3. 目視檢查快取目錄結構（cache_dir 用步驟 2 的輸出替換）
#    合格標準（model_runtime.py:23-39）：models--BAAI--bge-m3 與 models--BAAI--bge-reranker-v2-m3
#    目錄下的 snapshots\<hash>\config.json 存在
$cache = "$env:USERPROFILE\.cache\huggingface"   # ← 換成步驟 2 印出的 cache_dir
Get-ChildItem "$cache\hub" -Filter "models--BAAI--*" -ErrorAction SilentlyContinue
Get-ChildItem "$cache\hub\models--BAAI--bge-m3\snapshots" -Recurse -Filter config.json -ErrorAction SilentlyContinue
Get-ChildItem "$cache\hub\models--BAAI--bge-reranker-v2-m3\snapshots" -Recurse -Filter config.json -ErrorAction SilentlyContinue
```

```powershell
# 4. 分辨「依賴缺失」：import 成功 = 套件在，剩下就是快取問題
.\.venv\Scripts\python.exe -c "import torch, sentence_transformers; print('packages OK', torch.__version__)"
```

```powershell
# 5.（快取檢查全過但 search 仍 503 時）確認 .env 沒有把快取目錄改指他處
Select-String -Path .\.env -Pattern "ROOMPILOT_RAG_MODEL_CACHE|ROOMPILOT_RAG_ENABLED|ROOMPILOT_RAG_DEVICE"
echo $env:HF_HOME
```

## 5. Mitigation（短期緩解）

1. **快取目錄指錯** → 在 `.env` 設 `ROOMPILOT_RAG_MODEL_CACHE=<有模型的目錄>`（或移除該行改用預設 `HF_HOME`／`~/.cache/huggingface`，settings.py:59-60、96），重啟 uvicorn。不需重新下載。
2. **快取真的不存在／不完整** → 依 README:94-100 補齊：

   ```powershell
   uv pip install --python .venv\Scripts\python.exe -r requirements-rag.txt
   .\.venv\Scripts\python.exe scripts/rag/prefetch_models.py            # 只檢查
   .\.venv\Scripts\python.exe scripts/rag/prefetch_models.py --download # 確認約 9 GB 空間後才執行
   ```

   **待確認**：`requirements-rag.txt` 與 `scripts/rag/prefetch_models.py` 在 yen@8863a36c 分支上**不存在**（README:97-100 有記載但檔案缺失，疑在 Django 的分支）。本分支上無法照 README 重新下載——找 Django owner 取得腳本或從已就緒的機器整包複製快取目錄（`models--BAAI--bge-m3`＋`models--BAAI--bge-reranker-v2-m3` 兩個資料夾）到 cache_dir。
3. **套件缺失**（`rag_model_packages_missing`）→ 同上安裝 `requirements-rag.txt`（同受待確認限制）。
4. **暫時放棄 RAG** → 不需任何動作：RAG 不在八步主流程上，`.env` 設 `ROOMPILOT_RAG_ENABLED=false` 可讓 status 明確回報 `feature_disabled`，避免使用者誤認為故障。

## 6. Recovery（恢復確認）

1. 補齊快取或修正目錄後**重啟 uvicorn**（settings 每請求重讀 `.env`，但已快取的 `_load_key` 綁定 cache 路徑，重啟最乾淨；model_runtime.py:96-99）。
2. `curl.exe -s http://127.0.0.1:8002/api/rag/status` 確認 `ready: true`、`blockers: []`、`models.embedding_cached: true`、`models.reranker_cached: true`。
3. `/rag` 頁執行一次實際搜尋（或 `POST /api/rag/search`）確認回 200 且 `blocks` 非空——首次請求會 lazy-load 模型，BGE-M3＋reranker 約需 4.6 GB 常駐記憶體（README:106-107），機器記憶體不足會在此步以 `RAG model weights could not be loaded` 再次失敗。

## 7. Escalation（升級路徑）

本機 Pilot 無 on-call 系統，管道為團隊直接聯繫；分工依 docs/TEAM_AI_OWNERSHIP.md：

| 情況 | 找誰 | 依據 |
| :--- | :--- | :--- |
| 快取補齊後仍載入失敗、模型版本／品質問題、需要 prefetch 腳本 | **Django**（RAG 解析／檢索／排序、BGE-M3 與 reranker 品質） | TEAM_AI_OWNERSHIP.md:11、24、55 |
| `/rag` 頁面、`/api/rag/*` 路由、job 佇列行為異常 | **Bella**（HTTP/UI adapter） | TEAM_AI_OWNERSHIP.md:55 |
| blockers 出現 `postgresql_unavailable`／`furniture_embeddings_empty`（pgvector 側） | **Kai**（正式家具、metadata 與 pgvector 查詢） | TEAM_AI_OWNERSHIP.md:55；另見 [runbook-catalog-db-unavailable.md](./runbook-catalog-db-unavailable.md) |

事故結束後 48 小時內完成覆盤紀錄（正式覆盤文件依需增建）。

## 8. 追溯

| 項目 | ID／來源 |
| :--- | :--- |
| 症狀登錄 | [00-registry.md](../00-registry.md) §4 slug `rag-model-cache-missing` |
| 對應 NFR | NFR-004（RAG 不決定幾何——status／search 皆帶 `boundary: retrieval_only_no_geometry_legality`，service.py:129、499）、NFR-006（離線預設——runtime offline-only 是同一原則的執行面） |
| 對應 ACPT | 無直接對應 ACPT（RAG 檢索不在 00-registry §2.3 驗收清單內；本症狀不阻擋 ACPT-001~016 任一項） |
| 對應告警 | 無（本機 Pilot 無告警系統；來源為使用者回報＋`GET /api/rag/status`） |
| 程式碼證據 | model_runtime.py:104-105、120、127、130-131；service.py:76-108；rag_api.py:48-57、97-108；settings.py:23-28、59-60、96 |
| 相鄰文件 | [deployment_and_operations.md](./deployment_and_operations.md)、[runbook-catalog-db-unavailable.md](./runbook-catalog-db-unavailable.md)、[../04_design/api_spec.md](../04_design/api_spec.md) |
| 事故紀錄 | postmortem 依需增建 |
