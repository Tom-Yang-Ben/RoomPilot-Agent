# 測試計畫與測試案例 (Test Plan / Test Cases) - RoomPilot

> **版本:** v1.0 | **更新:** 2026-08-07 | **狀態:** 草稿
> **Owner:** 各模組測試由對應目錄 owner 維護（Bella／Cody／Django／Kai／Yen／Ancai，對照 `AGENTS.md` 目錄責任表）；端到端整合門檻由 Bella 維護；`testdata/` 辨識測資 QA 由 Ben 負責
> **原則:** 測試證明系統符合需求；沒接到需求 ID 的測試是裝飾品。案例狀態與執行證據維護在 `qa_tracker.xlsx`（角色追蹤簿，本輪不實例化、由 owner 啟用，見 [INDEX](../../../VibeCoding_Workflow_Templates/INDEX.md)）。
> **定位:** 本文件回答「RoomPilot 測什麼、用什麼層級測、完成怎麼判定」。客戶驗收輪次歸 [uat_plan](uat_plan.md)；資安檢查基線見 [security_and_readiness 2026-07-26 參考版](../../vibecoding/05_qa/security_and_readiness.md)（未對現行程式碼複核）；最低驗證門檻的權威是 [`AGENTS.md`](../../../AGENTS.md) 驗證矩陣，本文不重抄。
> **語域:** L3（工程）
> **實例:** 單例（策略一份；案例與證據在 `qa_tracker.xlsx`）
> **生成:** 2026-08-07 由 VibeCoding_Workflow_Templates/05_qa/test_plan.md 導入 | 基準 docs/vibecoding-restructure @ 1268b2b4

---

## 目錄

- [1. 測試範圍與策略](#1-測試範圍與策略)
- [2. 測試案例格式](#2-測試案例格式)
- [3. 缺陷回報格式 (Bug Report)](#3-缺陷回報格式-bug-report)
- [4. 測試報告結論 (QA Report)](#4-測試報告結論-qa-report)
- [5. 追溯](#5-追溯)

## 1. 測試範圍與策略

### 1.1 範圍表

| 項目 | 內容 |
| :--- | :--- |
| **範圍內** | FR-AUTH-01～03、FR-PROJ-01～02、FR-FP-01～03、FR-LAYOUT-01、FR-SCENE-01～03、FR-CATALOG-01～04、FR-RAG-01～02、FR-AGENT-01～02、FR-ENGINE-01、FR-RENDER-01～02、FR-REPORT-01～03；NFR-一致性-01、NFR-安全-01/02、NFR-可用性-01、NFR-相容-01（ID 權威：[srs](../01_requirements/srs.md)） |
| **範圍外** | 效能與負載測試（NFR-效能-01/02 門檻 TO-BE，無量測基準可判定）；滲透測試與正式安全審查（現況基線見 2026-07-26 版 security_and_readiness，屬參考）；UAT 業務驗收（歸 [uat_plan](uat_plan.md)）；渲染成圖的美感主觀評價（無可判定準則） |
| **測試層級** | 單元／契約（pytest）→ API 整合（FastAPI TestClient）→ 前端 DOM 行為（node jsdom）→ 人工瀏覽器 QA（Three.js 視覺與互動，依 `AGENTS.md` 驗證矩陣為靜態前端變更的必要項） |
| **環境** | Windows 本機、`.venv` Python 3.12、pytest 9.1.1；伺服器本機 uvicorn `127.0.0.1:8002`（Docker 已於 2026-08-06 整套移除）；測試預設離線隔離，見 §1.4 |
| **進入條件** | `.venv` 依 README 建妥；`pytest --collect-only` 無收集錯誤；不需要 PostgreSQL、OpenRouter 金鑰或網路（預設模式） |
| **退出條件** | 範圍內自動化案例全執行且 0 失敗；瀏覽器 QA 項有目視紀錄；阻擋缺陷 = 0；狀態判定交 `/verify` |

### 1.2 測試資產現況（2026-08-07 實測）

以 `.\.venv\Scripts\python.exe -m pytest -q --collect-only` 實收：

- **1,053 個 pytest 案例、113 個 `tests/test_*.py`**（collect 實數，非執行結果；舊文件的 392/389 是 2026-07-26 數據，不可沿用）。
- **3 支 jsdom DOM 行為測試**（`tests/static/*.test.mjs`：page_boot_failure、pending_actions、render_errors），由 `tests/test_scene_pending_actions_dom.py` 以 `node --test` 帶起；本機無 node 或未裝 jsdom 時整組跳過（`tests/test_scene_pending_actions_dom.py:19-30`）。
- 前端路徑解析統一走 `tests/static/paths.mjs`（`AGENTS.md` 契約），測試不得自行拼相對路徑。

依檔名歸群的案例分布（近似值，歸群規則見備註）：

| 領域（AREA） | 案例數 | 主要 owner | 代表測試檔 |
| :--- | ---: | :--- | :--- |
| SCENE（八步流程、scene_json、前端契約） | 395 | Bella | `test_scene_v2_contract.py`（150）、`test_scene_workflow.py`、`test_project_workflow_api.py` |
| CATALOG（型錄、PostgreSQL、雲端資產） | 163 | Kai | `test_postgres_catalog_crud.py`、`test_catalog_data_hygiene.py`、`test_cloud_models.py` |
| ENGINE（擺放、碰撞、淨空、幾何） | 129 | Ancai | `test_placement.py`（18）、`test_clearance.py`、`test_vertical_span.py`（30） |
| FP（平面圖辨識、DXF、房型） | 103 | Cody | `test_floorplan_vision.py`（23）、`test_cody_room_recognition.py` |
| AGENT（需求結構化、選件） | 54 | Yen | `test_agent_select.py`（19）、`test_agent_place.py`、`test_agent_requirement_chain.py` |
| REPORT（工程文件、估價、設計語彙） | 48 | Bella | `test_engineering_*.py`（7 檔）、`test_furniture_estimate.py`、`test_design_knowledge.py` |
| RAG（檢索、詞彙、語意快取） | 40 | Django | `test_rag_api.py`、`test_rag_domain.py`、`test_shortlist_query_refinement.py` |
| AUTH（帳戶、授權、成員隔離） | 36 | Bella | `test_auth_core.py`、`test_auth_lifecycle.py`、`test_project_authorization.py` |
| RENDER（遠端渲染、render-jobs） | 31 | Bella | `test_render_direct_provider.py`（22）、`test_remote_render_workflow.py` |
| 跨模組守門（輸入強化、家電邊界、env 契約等） | 54 | 對應 owner | `test_api_input_hardening.py`、`test_appliance_boundary_contract.py`、`test_roompilot_quality_guardrails.py` |

> 備註：分布以檔名前綴歸群（如 `test_scene_*` → SCENE），單檔可能橫跨多領域，僅供盤點量級；權威歸屬看 `AGENTS.md` 目錄責任表。合計 1,053 與 collect 實數一致。

### 1.3 測試層級與驗證門檻

各變更類型的**最低**驗證項只在 [`AGENTS.md`](../../../AGENTS.md) 驗證矩陣維護（Python 模組、FastAPI、靜態前端、辨識、Catalog/SQL、文件各有對應門檻），本文不重抄。最終整合指令同樣以該檔為準：`pytest -q` 全綠＋`git diff --check`＋`git status --short`。

本專案沒有 Gherkin 執行器（無 pytest-bdd/behave 依賴）；BDD 的落地方式是**行為命名的 pytest 測試**＋TestClient 直打路由，情境寫法見 [bdd_guide 2026-07-26 參考版](../../vibecoding/01_requirements/bdd_guide.md)（其步驟表與測試對照為 7/26 快照，引用前需對現行程式碼複核）。

### 1.4 測試環境與預設隔離（`tests/conftest.py` 實查）

預設測試模式刻意離線且確定（deterministic），與正式環境的差異如下：

| 面向 | 測試預設 | 正式環境 | 切回真實路徑的開關 |
| :--- | :--- | :--- | :--- |
| 專案儲存 | SQLite（暫存目錄，session 級隔離） | PostgreSQL 優先 | `ROOMPILOT_TEST_POSTGRES_MAIN=1`（conftest.py:12） |
| 家具型錄 provider | JSON | PostgreSQL view `roompilot.furniture_catalog_current` 優先 | `ROOMPILOT_TEST_POSTGRES_CATALOGS=1`（conftest.py:15） |
| runtime 型錄 provider | JSON | PostgreSQL | `ROOMPILOT_TEST_POSTGRES_RUNTIME_CATALOGS=1`（conftest.py:18） |
| LLM 選件 | 關閉（離線） | 隨 `OPENROUTER_API_KEY` 啟用 | `ROOMPILOT_TEST_OPENROUTER_SELECTION=1`（conftest.py:23） |
| RAG 語意模型預載 | 關閉（bge-m3 載入約 34 秒、常駐數 GB） | 開啟 | `ROOMPILOT_TEST_RAG_PRELOAD=1`（conftest.py:28） |
| API 身分 | TestClient 自動帶 admin JWT（真實驗證路徑，非繞過；匿名用 `anonymous_client` fixture） | 一般使用者角色 | —（conftest.py:71-151） |
| PostgreSQL CRUD 實連 | 跳過 | — | `ROOMPILOT_TEST_POSTGRES_CRUD=1`（test_postgres_catalog_crud.py:354） |

**已知風險**：預設 JSON provider 使 PostgreSQL 專屬行為（view 欄位、詞彙差異、連線池）在日常全綠中不可見；postgres 路徑必須以上表開關明確 opt-in 執行，發表前至少跑一輪。另外終端機的 `ROOMPILOT_*_PROVIDER` 環境變數會蓋過 `.env`，驗證前先清掉再跑。

### 1.5 已知覆蓋缺口（待補案例）

| 缺口 | 對應 ID | 現況 |
| :--- | :--- | :--- |
| 第 4 步人工校正與樑柱手繪（UI 流程） | SCN-FP-03 | 無自動化；屬人工瀏覽器 QA，執行紀錄待建 |
| 結構變更後家具重驗的端到端目視 | SCN-SCENE-03 | 契約測試存在（見 TC-SCENE-03），瀏覽器目視未排 |
| layout evaluation schema 的專屬契約案例 | SCN-LAYOUT-01 | 候選 `test_floorplan_room_evaluation.py`，對應性待 Django 確認 |
| 第 8 步生圖 → 按鈕 → 成果報告的端到端目視 | SCN-RENDER-01/02、SCN-REPORT-01 | 自動化止於 API 契約；瀏覽器段未執行 |
| 效能門檻（API p95、3D 首載） | NFR-效能-01/02 | TO-BE：無門檻即無案例，待 owner 拍板 |

## 2. 測試案例格式

單一案例的完整格式（登錄於 `qa_tracker.xlsx` ①測試設計）：

| 項目 | 內容 |
| :--- | :--- |
| **ID** | TC-\<AREA\>-NN（AREA 與 SCN/FR 同字首） |
| **Scenario** | 對應 [prd](../01_requirements/prd.md) 的 SCN-\<AREA\>-NN |
| **Preconditions** | 前置狀態（含 §1.4 的環境開關） |
| **Steps** | 1. … 2. … 3. … |
| **Expected Result** | 可觀察結果（狀態碼＋錯誤 `code` 欄位以 `backend/server/` 實作為準，不自創） |
| **Actual Result** | 執行時填 |
| **Severity / Priority** | Blocker／Major／Minor |
| **Evidence** | pytest 輸出、截圖或 log 路徑 |

填寫範例（以 TC-PROJ-02 的實測行為為例，全部欄位可對回程式碼）：

| 項目 | 內容 |
| :--- | :--- |
| **ID** | TC-PROJ-02 |
| **Scenario** | SCN-PROJ-02（並行編輯不互相覆蓋） |
| **Preconditions** | 已登入（測試環境由 conftest 帶預設身分）、已建立專案並保存過一版工作流 |
| **Steps** | 1. 保存工作流取得基準 `updated_at` 2. 再保存一次讓伺服器版本前進 3. 帶著過期 `base_updated_at` 與 `replay_pending: true` 補送舊內容 |
| **Expected Result** | 回 409、`detail` 為 `project_version_conflict`；伺服器保持步驟 2 的內容不被覆蓋（原子拒絕）；改帶最新 `base_updated_at` 補送則回 200。一般（非 replay）過期保存的錯誤碼是 `project_revision_conflict`（`backend/server/projects_api.py:376`） |
| **Actual Result** | （執行時填） |
| **Severity / Priority** | Blocker（覆蓋等於遺失使用者工作） |
| **Evidence** | `tests/test_project_workflow_api.py:199-248` |

案例清單（TC → SCN → 現有自動化對照；測試檔與函式名皆 2026-08-07 實查存在）：

| ID | Scenario | 驗證重點 | 現有自動化 | 狀態 |
| :--- | :--- | :--- | :--- | :--- |
| TC-AUTH-01 | SCN-AUTH-01 | 註冊／登入；首帳號成為 admin | `tests/test_auth_core.py`、`tests/test_auth_lifecycle.py` | 自動化存在 |
| TC-AUTH-02 | SCN-AUTH-02 | 非成員存取回 404 不洩漏專案存在性 | `tests/test_project_authorization.py` | 自動化存在 |
| TC-AUTH-03 | SCN-AUTH-03 | admin 重設密碼／停用；改密碼撤銷 session | `tests/test_auth_lifecycle.py`（對應性沿用 srs 盤點） | 自動化存在 |
| TC-PROJ-01 | SCN-PROJ-01 | 專案保存／中斷恢復；草稿超限明確拒絕 | `tests/test_project_workflow_api.py`、`tests/test_scene_workflow.py` | 自動化存在 |
| TC-PROJ-02 | SCN-PROJ-02 | 樂觀鎖：過期 revision 被拒、離線補送綁基準版本 | `tests/test_project_workflow_api.py:199`（`test_pending_save_replay_rejects_a_stale_server_version_atomically`） | 自動化存在 |
| TC-FP-01 | SCN-FP-01 | 上傳副檔名白名單、空檔與壞圖拒絕 | `tests/test_project_workflow_api.py:251`（`test_floorplan_upload_accepts_only_dxf_png_and_jpeg`）、`tests/test_floorplan_vision_api.py` | 自動化存在 |
| TC-FP-02 | SCN-FP-02 | 兩點標定建立公分尺度；未確認不得續行 | `tests/test_scene_calibration.py` | 自動化存在 |
| TC-FP-03 | SCN-FP-03 | 第 4 步人工校正空間結構、手繪樑柱 | 無（UI 人工流程） | 待補瀏覽器 QA |
| TC-LAYOUT-01 | SCN-LAYOUT-01 | layout evaluation schema 契約 | 候選 `tests/test_floorplan_room_evaluation.py`（待 Django 確認對應性） | 待確認 |
| TC-SCENE-01 | SCN-SCENE-01 | `scene_json` 契約、公分制欄位 | `tests/test_scene_v2_contract.py` | 自動化存在 |
| TC-SCENE-02 | SCN-SCENE-02 | 步驟閘門依序解鎖；白模允許零家具 | `tests/test_scene_workflow.py:598`、`:738` | 自動化存在（3D 目視另列人工 QA） |
| TC-SCENE-03 | SCN-SCENE-03 | 上游結構確認被改時下游結果作廢 | `tests/test_scene_workflow.py:691`（`test_editing_upstream_confirmation_invalidates_downstream_results`） | 自動化存在 |
| TC-CATALOG-01 | SCN-CATALOG-01 | 預設 strict postgres；DB 不可用回 503 `postgres_catalog_unavailable`（不靜默回退）；明確設 provider=json 才走離線 JSON | `tests/test_runtime_catalog_phase4.py`、`tests/test_postgres_catalog_contract.py` | 自動化存在（實連 CRUD 需 opt-in，§1.4） |
| TC-CATALOG-02 | SCN-CATALOG-02 | 隔離區資料不進 API 與場景 | `tests/test_cloud_quarantine.py:33`（`test_quarantined_furniture_is_not_in_the_web_model_set`） | 自動化存在 |
| TC-CATALOG-03 | SCN-CATALOG-03 | 家電不進 2D/3D 配置與正式家具 API | `tests/test_appliance_boundary_contract.py`（含使用者確認過的家電仍拒收） | 自動化存在 |
| TC-CATALOG-04 | SCN-CATALOG-04 | 燈具獨立 lane 不入自動選件 | `tests/test_lighting_assets_catalog.py` | 自動化存在 |
| TC-RAG-01 | SCN-RAG-01 | RAG 只回關係與證據，不決定幾何 | `tests/test_rag_api.py`、`tests/test_rag_domain.py` | 自動化存在 |
| TC-RAG-02 | SCN-RAG-02 | 受控詞彙（風格／色卡／氛圍／家具群組）契約 | `tests/test_catalog_vocabulary_contract.py`、`tests/test_room_type_vocabulary.py` | 自動化存在（JSON 預設下 postgres 詞彙差異不可見，§1.4） |
| TC-AGENT-01 | SCN-AGENT-01 | 選件房型規則、副件依賴、使用者指定不被移除 | `tests/test_agent_select.py`、`tests/test_agent_place.py`、`tests/test_agent_requirement_chain.py` | 自動化存在 |
| TC-AGENT-02 | SCN-AGENT-02 | LLM 選件違規時降級 `local_rules` 並標示來源 | `tests/test_project_workflow_api.py:28`（`test_agent_furniture_selection_falls_back_when_llm_violates_room_rules`） | 自動化存在 |
| TC-ENGINE-01 | SCN-ENGINE-01 | 擺放合法性、碰撞、淨空、垂直佔用 | `tests/test_placement.py`、`tests/test_clearance.py`、`tests/test_geometry_core.py`、`tests/test_vertical_span.py` | 自動化存在 |
| TC-RENDER-01 | SCN-RENDER-01 | 鎖定方案、逐房視角保存 | `tests/test_remote_render_workflow.py` | 自動化存在（窄房鏡頭目視待排） |
| TC-RENDER-02 | SCN-RENDER-02 | render-jobs 入口唯一、任務量上限、私人欄位剝除、供應商未設回 503 | `tests/test_render_direct_provider.py`、`tests/test_remote_render_workflow.py` | 自動化存在 |
| TC-REPORT-01 | SCN-REPORT-01 | 鎖定版快照轉 HTML/XLSX/JSON 三份文件 | `tests/test_engineering_documents_api.py`、`tests/test_engineering_snapshot_api.py` | 自動化存在 |
| TC-REPORT-02 | SCN-REPORT-02 | 家具採購與施工費分列不合計；無價 `subtotal` 為 null | `tests/test_engineering_cost_schedule.py` | 自動化存在 |
| TC-REPORT-03 | SCN-REPORT-03 | 設計語彙 confidence 上限 medium；數字只出自快照 | `tests/test_design_knowledge.py` | 自動化存在 |

> 「自動化存在」只描述案例由列出的測試承載，本欄不宣告通過；執行結果只認 §4.1 的實跑紀錄與 `/verify` 的證據（本輪全套實跑見 §4.1）。SCN 定義的權威在 prd；若編號有出入，以 prd 為準並回改本表。

## 3. 缺陷回報格式 (Bug Report)

| 項目 | 內容 |
| :--- | :--- |
| **重現步驟** | 環境（含 §1.4 開關狀態與 `ROOMPILOT_*` 環境變數）、帳號角色、步驟 |
| **預期 vs 實際** | 預期以 FR/SCN 的可觀察結果描述；實際附狀態碼與錯誤 `code` |
| **嚴重程度** | Blocker（擋八步流程或資料損毀）／Major（功能錯但可繞）／Minor |
| **關聯** | TC-\* ／ FR-\* ／ SCN-\* |

缺陷登錄通道目前未定：repo 內無 issue tracker 使用慣例的紀錄（未查證團隊是否在 repo 外追蹤）；暫以 `qa_tracker.xlsx` ②執行證據併記，通道由 owner 拍板後補入本節。

## 4. 測試報告結論 (QA Report)

### 4.1 本輪執行紀錄（2026-08-07，基準 1268b2b4）

| 項目 | 內容 |
| :--- | :--- |
| **收集** | 1,053 案例／113 檔（`pytest --collect-only` 實跑，無收集錯誤） |
| **執行** | 全套 `.\.venv\Scripts\python.exe -m pytest -q` 實跑（2026-08-07，預設隔離模式）：**1,043 通過、10 跳過、0 失敗**，460.18 秒，exit code 0；deprecation／xFormers 警告 10 則，無失敗 |
| **跳過項** | 10 個跳過的逐項原因本輪未盤點（-rs 明細待補）；已知的 opt-in 跳過來源見 §1.4（postgres 實連 CRUD 等）。**跳過 ≠ 通過** |
| **歷史數據** | 2026-07-26 的 389 通過／2 失敗／1 跳過是舊基準（bella-local-20260726）數據，樣本數與現行 1,053 已不可比，不得沿用 |
| **未執行項** | postgres opt-in 路徑（§1.4 全部開關）、LLM 實連選件、RAG 語意模型載入路徑、瀏覽器 QA（§1.5） |
| **缺陷狀態** | 本輪無新登錄缺陷；既有開放項見 §4.2 |
| **上線建議** | 不在本文件判定——GO/NO-GO 由 `/verify` 依實跑證據與 [uat_plan](uat_plan.md) 驗收結果給出。本輪預設模式全綠只背書離線隔離路徑 |

### 4.2 殘餘風險

- **預設綠 ≠ postgres 綠**：§1.4 的隔離設計讓日常全綠無法背書 PostgreSQL 路徑；發表前需一輪 opt-in 實連執行。
- **前端視覺無自動化護欄**：Three.js 場景正確性最終靠人工瀏覽器 QA；自動化只覆蓋契約與 DOM 行為層。
- **效能無門檻**：NFR-效能-01/02 為 TO-BE，任何效能退化目前不會被測試攔下。
- **安全基線過期**：security_and_readiness 為 2026-07-26 快照，其後新增的 auth、render-jobs、`/api/v1` 端點未入該基線；資安複審待排（該檔行動項亦未逐項銷結）。

> 只有實際執行過的測試能出現在報告裡；狀態判定交給 `/verify`。

## 5. 追溯

| 項目 | ID |
| :--- | :--- |
| 上游 | FR-\*／NFR-\*（[srs](../01_requirements/srs.md) §2–§3）、SCN-\*（[prd](../01_requirements/prd.md) 使用者故事段）、ACPT-\*（srs 追溯表） |
| 案例與證據 | TC-\*（本文件 §2 清單）→ `qa_tracker.xlsx` ①測試設計／②執行證據（owner 啟用後遷入） |
| 下游 | [uat_plan](uat_plan.md)（客戶驗收輪次）、`/verify` 完成判定 |
