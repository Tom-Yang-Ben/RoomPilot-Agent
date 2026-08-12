# ADR-008: 檢索只做排序、模型 offline-only (Retrieval-Only Ranking with Offline Models) - RoomPilot

> **狀態:** 已接受（現況追認，待 owner 核准） ｜ **日期:** 2026-08-12 ｜ **決策者:** MOD-RAG owner（Django）＋ MOD-SRV-API owner（Bella，API 轉接）＋ 產品 owner（DEC-016／DEC-017 核准權）
> **語域:** L2（橋接）
> **實例:** 每決策一份（`ADR-008-rag-retrieval-only-offline-models.md`）
>
> **本文件回答**：為什麼家具向量檢索被限制成「只重排既有候選」、為什麼模型權重採 offline-only 而非在請求路徑下載，以及哪些替代方案被放棄與理由。
> **本文件不含**：檢索端點的欄位級契約（去 [`api_spec.md`](../../04_design/api_spec.md) 與 [`openapi-agent-rag-v1.yaml`](../../04_design/openapi-agent-rag-v1.yaml)）、第 5 步畫面降級表現（去 [`ui_spec-step5-requirements.md`](../../02_ux_ui/ui_spec-step5-requirements.md)）、幾何合法性歸屬（去 [`ADR-002`](./ADR-002-engine-sole-geometry-authority.md)）、型錄來源權威（去 [`ADR-005`](./ADR-005-postgres-catalog-source-of-truth.md)）、系統全貌（去 [`sad.md`](../sad.md)）。
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、2026-08-12 工作樹。行號隨程式碼演進，衝突時以原始碼為準。

---

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 執行計畫](#5-執行計畫)
- [6. 追溯](#6-追溯)

## 1. 背景與問題

- **上下文**：第 5 步問卷要把逐房家具推薦排出優先順序。`backend/spatial_data/rag/` 已具備 BGE-M3 embedding ＋ `bge-reranker-v2-m3` cross-encoder（`model_runtime.py:14-16`），PostgreSQL 側有 pgvector 表與 `roompilot.search_furniture_embeddings_filtered`（`rag_repository.py:131-164`）。同期第 6 步的擺位與合法性完全由 `backend/engine/` 決定（見 [`ADR-002`](./ADR-002-engine-sole-geometry-authority.md)）。
- **問題**：只要檢索被允許「新增候選」或「建議放哪」，就同時繞過兩道既有閘門——正式型錄與隔離區規則（DEC-007）、以及引擎的幾何權威（DEC-008）。另一面，檢索需常駐約 4.6 GB 本地權重（`docs/contracts/POSTGRESQL_FURNITURE_RAG_RUNTIME.md:102`）；權重缺席時系統要嘛在請求路徑下載，要嘛必須誠實失敗，兩者不能同時成立。
- **驅動因素**：DEC-016（檢索只排序）、DEC-017（外部相依壞掉要誠實中止）、[`AGENTS.md`](../../../AGENTS.md)`:53`（Graph RAG 不決定幾何、碰撞、淨空或結構合法性）。
- **約束**：`ROOMPILOT_RAG_ENABLED` 預設 `false`（`settings.py:76`）。「沒有檢索」必須是可長期運行的正常狀態，不能被設計成故障狀態。

## 2. 考量的選項

### 選項一: 不做向量檢索，順序全交給規則
- **描述**: 維持型錄預設順序 ＋ Yen 的選件潛規則（FR-050–052），不引入本地模型。
- **優點**: 零額外部署成本；無 4.6 GB 權重、無 GPU 需求；失敗面最小。
- **缺點**: 問卷寫的風格／氛圍自然語言無處著力，推薦順序與使用者敘述脫節。
- **成本/複雜度**: 低。**未選為目標狀態，但被刻意保留為降級路徑**——旗標關閉或任一 blocker 存在時，系統就落回此選項（`scene_v2.js:910-915`）。

### 選項二: 讓檢索／LLM 直接決定品項與擺放
- **描述**: 把 RAG 升格為代理，輸出家具清單與座標，第 6 步直接採用。
- **優點**: 一次呼叫產出完整方案，前端流程最短，看起來最「AI」。
- **缺點**: 與 `AGENTS.md:53`、DEC-008 直接衝突；碰撞與淨空的可重現性被機率性輸出取代；隔離區與 GLB 可用性失去單一守門點。
- **成本/複雜度**: 高（需重建整條幾何驗證的信任鏈）。**否決**：幾何權威不可分割，這正是 [`ADR-002`](./ADR-002-engine-sole-geometry-authority.md) 存在的理由。

### 選項三: 檢索可擴充候選集 ＋ 權重按需線上下載
- **描述**: 允許檢索補進候選集以外的型錄項目，模型未快取時於請求路徑向遠端取權重。
- **優點**: 召回上限較高；部署方不必預先備妥權重，第一次呼叫即可用。
- **缺點**: 候選集合一旦可變，DEC-007 的隔離區保證就無處可驗（`tests/test_cloud_quarantine.py:23-40` 只能守 API 出口）；請求路徑下載使第 5 步延遲不可預期，且 Pilot 綁 `--host 127.0.0.1`（NFR-019）不應假設外網可用；失敗時最可能的表現是「靜默給了不一樣的東西」，正是 DEC-017 要禁止的。
- **成本/複雜度**: 中。**否決**。

### 選項四: 只重排既有候選 ＋ 模型 offline-only ＋ 未就緒具名 blocker（採用）
- **描述**: 見 §3。
- **優點**: 候選集合可被斷言為不變；失敗語意單一；排序決定性可重現。
- **缺點**: 排序品質上限被候選集合與固定權重鎖死；部署需預先備妥權重。
- **成本/複雜度**: 中。

## 3. 決策

**選擇**: 選項四。三條硬約束：

| # | 約束 | 實作事實 | 佐證 |
| :--- | :--- | :--- | :--- |
| 1 | 不新增、不替換、不決定座標 | `rank_candidates` 只對傳入的 candidates 逐一加分後排序，長度與 `item_id` 集合不變；服務層只做去重與 `top_k` 截斷；顯示資料一律回 Kai 正式型錄補齊 | `ranking.py:114-154`；`service.py:408-427,429-433` |
| 2 | 硬條件走 SQL、軟偏好只影響排序 | room_type／categories／price／max_width_cm／max_height_cm／role／size_class 是 SQL function 參數；風格與氛圍只進評分 | `rag_repository.py:131-164`；`docs/contracts/POSTGRESQL_FURNITURE_RAG_RUNTIME.md:34` |
| 3 | 模型權重 offline-only | `SentenceTransformer`／`CrossEncoder` 皆帶 `local_files_only=True`；套件或快取缺席在載入前就拋 `RagDependencyError` | `model_runtime.py:102-105,116-128` |

**排序公式固定**：`0.60*rerank + 0.20*style + 0.10*mood + 0.10*confidence`（`ranking.py:16,133-138`），候選量固定 top-50 → rerank top-20（`is_inferred` 或 `role=="accent"` 取 12）（`ranking.py:11-13`；`service.py:184-187`），最後依 `item_id` 與 `duplicate_group` 去重（`service.py:408-427`）。

**未就緒不假成功**：`status()` 回 10 種具名 blocker 並自報 `boundary:"retrieval_only_no_geometry_legality"`，且刻意 `pop("cache_dir")` 不外洩伺服器檔案佈局（`service.py:66,76-130`，對應 NFR-020）；`_require_ready()` 見 blocker 即拋（`service.py:132-143`）；adapter 把 `RagDependencyError`／`RagDatabaseError` 映射 503、`RagUpstreamError` 映射 502 並標 `retryable`（`rag_api.py:37-57`）。

**第 5 步的接法**：`fast:true` 繞過 LLM parser 走 deterministic plan（`service.py:364-370`；`openrouter_parser.py:280-289`）；非同步工作佇列 202 ＋ 輪詢，單一 daemon worker 序列化、佇列上限 24（429 `rag_job_capacity_reached`）、完成後保留 3600 秒（`rag_api.py:28-34,121-137,178-221`）；前端只用命中 id 把既有推薦排前面，`failed` 或例外一律落 `status:"unavailable"` 且不阻塞問卷（`scene_v2.js:871-888,895-915`）。檢索結果**不寫入** `layout_json`／`scene_json`：全 repo 只有 `main.py:105,197` 掛載 router，`scene_service.py` 無任何 RAG 呼叫。

## 4. 後果

### 4.1 得到什麼

| 收益 | 可觀測形式 |
| :--- | :--- |
| 幾何權威不被稀釋 | 檢索輸出無座標欄位；第 6 步落點仍全由 `backend/engine/` 產出（ADR-002、FR-034） |
| 型錄與隔離區規則不被繞過 | 候選來自 SQL function 的 active 向量，顯示資料回正式型錄補齊；隔離區無新增入口（DEC-007） |
| 排序決定性 | 固定權重、固定 top-k、固定去重順序；同輸入同輸出，可寫成斷言（`ranking.py:11-16`） |
| 失敗語意單一 | 10 種具名 blocker ＋ 503／502 映射，第 5 步降級為「順序未套用」而非錯誤（ACPT-041、SCN-015） |

### 4.2 付出什麼

| 代價 | 具體約束 |
| :--- | :--- |
| 品質上限被候選集合鎖死 | rerank 只能改順序；SQL 硬篩沒撈到的東西，檢索永遠救不回來 |
| 部署前置變重 | 約 4.6 GB 權重需預先備妥，冷啟動 lazy-load 一次（`model_runtime.py:96-135`；契約 `:102`） |
| 併發天花板低且狀態易失 | 單 worker 序列化、上限 24、工作狀態存行程記憶體，重啟即失（`rag_api.py:28-34,121-137`，NFR-009） |
| 第 5 步查詢條件品質受限 | `fast:true` 不走 LLM，條件全靠關鍵字正規化（`openrouter_parser.py:280-289`） |
| 權重無線上調參機制 | `0.60/0.20/0.10/0.10` 是原始碼常數，改動＝改契約，無 A／B 或設定檔覆寫 |
| 集合不變性目前只靠程式碼閱讀 | `tests/test_rag_domain.py` 有 rerank 數量與去重測試（`:441,476`），但**沒有**測試斷言第 5 步重排前後候選集合相同——ACPT-042 的前端側尚無自動證據 |

### 4.3 什麼時候該重評

| 重評觸發（可觀測） | 觀測點 |
| :--- | :--- |
| 第 5 步 `roomRagJobs` 落 `unavailable` 的房間比例在 UAT 中偏高 | `scene_v2.js:896-899` 已把原因寫進 workflow，可直接統計 |
| 出現 429 `rag_job_capacity_reached` | `rag_api.py:186-191`；代表單 worker ＋ 24 上限不夠用 |
| 向量筆數與型錄 active 筆數脫鉤 | `/api/rag/status` 的 `database.current_embeddings` 對不上 `/api/catalog/status`（OPEN-43） |
| owner 核准把檢索接入第 6 步選件 | 一旦檢索可影響「選哪件」而非「先看哪件」，本 ADR 的約束 1 需重寫，並牽動 FR-050–052 |
| 具 8 GB 以上 VRAM 的 CUDA 環境到位 | 契約 `:101-103` 已標示此為主要加速路徑；屆時可重評單 worker 序列化 |
| 量測顯示重排對第 6 步最終選件無可測差異 | 若價值為零，應重評是否退回選項一以省下 4.6 GB 常駐成本 |

**影響範圍**：MOD-RAG（Django）為主；MOD-WEB 第 5 步降級表現、MOD-SRV-API 的錯誤映射、MOD-CAT 的向量表與 SQL function 皆受本決策約束。

## 5. 執行計畫

1. **收斂 OPEN-43**（本 ADR 最大的未決矛盾，兩件事）：
   - 契約 `docs/contracts/POSTGRESQL_FURNITURE_RAG_RUNTIME.md:13-15` 寫「第一版只供 `/rag` 驗證，不接入八步流程第 6 步」，但第 5 步問卷**已實際接入**（`scene_v2.js:871-875`）。需由 owner 裁定：契約應更新為「第 5 步排序已納入、第 6 步仍排除」，或第 5 步接入應撤除。**在裁定前，本 ADR 的範圍只涵蓋第 5 步排序。**
   - 向量筆數在契約之間有兩個數字：`POSTGRESQL_FURNITURE_EMBEDDINGS.md:9,12` 記 8,076（active／RAG-indexable），`QUESTIONNAIRE_RAG_HANDOFF.md:36-37` 的驗收條件記 `current_embeddings=7958`。**待確認**哪一個是驗收基準，承接於 [`db_design.md`](../../04_design/db_design.md)。
2. 補一條測試斷言「重排前後候選 id 集合完全相同、只有順序改變」，關掉 §4.2 最後一列的證據缺口（承接 [`test_plan.md`](../../05_qa/test_plan.md) 的 TC-042）。
3. 權重快取缺席的處置步驟維護在 [`runbook-rag-model-cache-missing.md`](../../06_ops/runbook-rag-model-cache-missing.md)（RB-004），本 ADR 不重複。
4. `ROOMPILOT_RAG_ENABLED` 在 Pilot 是否預設開啟，屬 DEC-014／DEC-016 的核准範圍，**待 owner 決定**；程式現況為 `false`。

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-08-12 | 待簽核（MOD-RAG owner／產品 owner） | 現況追認稿；OPEN-43 未收斂前不得視為已核准範圍 |

## 6. 追溯

| 項目 | ID／文件 |
| :--- | :--- |
| 上游決策 | DEC-016、DEC-017（[`brd.md`](../../01_requirements/brd.md)、[`srs.md`](../../01_requirements/srs.md) §1.1） |
| 觸發需求 | FR-046、FR-047、FR-048、FR-049；NFR-009、NFR-010、NFR-014、NFR-020 |
| 驗收對應 | ACPT-041、ACPT-042、ACPT-043；SCN-015、SCN-016（[`prd.md`](../../01_requirements/prd.md)） |
| 影響模組 | MOD-RAG（主）、MOD-WEB、MOD-SRV-API、MOD-CAT（[`sad.md`](../sad.md)） |
| 相關決策 | 幾何權威 [`ADR-002`](./ADR-002-engine-sole-geometry-authority.md)；型錄來源 [`ADR-005`](./ADR-005-postgres-catalog-source-of-truth.md)；外部 AI 服務治理 [`ADR-009`](./ADR-009-server-governed-ai-generation.md)；並存管線隔離 [`ADR-011`](./ADR-011-agent-pipeline-flag-isolation.md) |
| 取代關係 | 無（Supersedes: 無；Superseded-by: 無） |
| 待確認 | OPEN-43（契約範圍 ＋ 向量筆數 8,076 vs 7,958），登記於 [`srs.md`](../../01_requirements/srs.md) §8 與 `engineering_tracker.xlsx` ①規格追溯 |
