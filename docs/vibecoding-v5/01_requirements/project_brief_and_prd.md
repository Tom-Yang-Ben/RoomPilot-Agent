# 專案簡報與產品需求文件 (PRD) - RoomPilot-Agent

> 本文件由 VibeCoding v5.0 模板 01_requirements/project_brief_and_prd.md 導入 RoomPilot-Agent | 基準：分支 django-skill、commit a2179f7e、日期 2026-08-04

> **版本:** v2.0 | **更新:** 2026-08-04 | **狀態:** 草稿
>
> 前一代導入版：`docs/vibecoding/02_project_brief_and_prd.md`（2026-07-26 對分支 bella-local-20260726 撰寫）。該版事實已過期（44 條路由、9,350 件正式型錄、10 顆步驟按鈕年代），本版所有數字均對現行工作樹重查，不沿用舊值。

---

## 1. 專案總覽

| 項目 | 內容 |
| :--- | :--- |
| **專案名稱** | RoomPilot-Agent（`pyproject.toml:2-3`：`roompilot-agent` 0.1.0；FastAPI 標題「AI 室內風格與家具配置展示系統」，`backend/server/main.py:214`） |
| **狀態** | 開發中（本文件基準：分支 `django-skill`、commit `a2179f7e`，commit 時間 2026-08-04 02:15:30 +0800） |
| **目標發布日期** | (未查證——repo 內查無任何發表日期紀錄；舊導入版註記的 2026-08-20 亦標示為口頭資訊，仍待正式來源) |
| **核心團隊** | 依 `docs/TEAM_AI_OWNERSHIP.md:7-15` 共 7 位：Bella=`backend/server/`+`backend/server/static/`（整合/FastAPI/正式 UI）、Cody=`backend/floorplan/`+`backend/upgrade3d/`、Django=`backend/spatial_data/`（含 RAG）、Kai=`backend/catalog/`（含 PostgreSQL）、Yen=`backend/agent/`、Ancai=`backend/engine/`、Ben=辨識 QA/evaluation。Git author 不可單獨視為 owner（同檔 :3） |

### 1.1 問題陳述

一般住戶拿到平面圖後，難以把「空間現況 + 生活需求」快速轉成可討論的室內設計方向；與設計師往返確認格局、風格與家具耗時，且從設計方案到工程估價之間又有一段人工斷層。RoomPilot 把「平面圖辨識 → 人工校正 → 逐房需求 → 家具資料庫 → 幾何配置 → 2D/3D 編輯 → 方案視角 → AI 渲染」整合成一個可恢復的網頁流程（`README.md` 自述：「RoomPilot 是 AIPE03 第四組的 AI 室內設計系統」），並在方案鎖定後由工程文件 MVP 延伸產出工程量、估價與排程文件（`docs/contracts/ENGINEERING_DOCUMENT_MVP.md`）。

### 1.2 目標用戶

| 用戶 | 使用情境 |
| :--- | :--- |
| 屋主/一般住戶 | 於 `/scene` 上傳自家平面圖，經視覺問卷表達需求，取得 2D/3D 家具配置、風格色卡與 AI 渲染成果 |
| 室內設計師 | 以同一流程與客戶即時確認空間方向；設計師確認鎖定版本後，於 `/engineering` 產生工程估算與文件（`engineering.html` 標題「工程估算與文件生成」） |
| 團隊/管理者 | 經 `/api/admin/furniture` 維護 PostgreSQL 家具型錄（Phase 2 CRUD，`backend/server/catalog_admin.py`）；經 `/rag` 測試台驗證家具 RAG 檢索品質（`rag.html`） |

### 1.3 主流程（程式碼權威順序）

UI 進度列為 **8 顆步驟按鈕**（`backend/server/static/scene.html:25-32`）；內部狀態機為 **11 個 step**（`scene_workflow.js:4-16`，`WORKFLOW_SCHEMA_VERSION=2`）：`recognition` 與 `calibration` 共用「確定尺寸」面板，`white_model_3d`/`realistic_3d` 有面板但無獨立按鈕（`WORKFLOW_PANEL_BY_STEP`，`scene_workflow.js:18-30`）。與舊導入版的 10 顆按鈕/11 步對照相比，現行 UI 已收斂為 8 步。

| # | UI 步驟 | 主要結果/伺服器行為（已對照程式碼） |
| :--- | :--- | :--- |
| 1 | 建立專案（project） | `POST /api/projects`（201，`main.py:2024`）；預設 SQLite 持久化，Phase 3 契約允許改用 PostgreSQL project store（`docs/contracts/POSTGRESQL_PROJECT_STORE_PHASE3.md`、`backend/server/postgres_project_store.py`） |
| 2 | 上傳平面圖（upload） | `POST /api/projects/{id}/floorplan`（201，`main.py:2097`）；副檔名限 `.dxf/.png/.jpg/.jpeg`（`FLOORPLAN_EXTENSIONS`，`main.py:164`）；平面圖上限 20MB（`MAX_FLOORPLAN_BYTES`，`main.py:180`） |
| 3 | 確定尺寸（recognition + calibration） | `POST /api/projects/{id}/floorplan/analyze`（`main.py:2315`）；兩點公分尺度校正；自動比例信心 < 0.8 需人工確認（`MIN_AUTOMATIC_SCALE_CONFIDENCE`，`backend/floorplan/vision/analysis.py:36`） |
| 4 | 空間與結構（space_confirmation） | 校正空間、牆、門、窗、樑與柱（`README.md` 八步流程第 4 步） |
| 5 | 需求問卷（requirements） | 先全屋風格/材質/冷氣範圍，再逐房用途/家具/尺寸/數量；視覺題庫 55 組（`backend/server/data/questionnaire_visual_catalog.json` 的 `question_count`=55，實測 questions 亦 55 筆） |
| 6 | 配置與預覽（layout_2d，含 white_model_3d/realistic_3d 面板） | `POST /api/scene/generate`（`main.py:3033`）；Yen 選件 + Ancai 引擎擺位驗證；同畫面 2D/3D 同步編輯；家具 GLB 由 CloudFront（`https://ddgsm1yg3xikc.cloudfront.net`，`main.py:2445`）交付 |
| 7 | 方案鎖定與視角（proposal_review） | 鎖定方案，逐空間選擇並微調生成視角 |
| 8 | AI 渲染與成果包（ai_render） | `POST /api/projects/{id}/render-jobs`（202，`main.py:2270`）；`mode` 僅限 `palette_comparison`/`room_final`（`SUPPORTED_RENDER_MODES`，`render_service.py:11`） |

方案鎖定後的延伸流程（不在 8 步 UI 內，經 `/engineering` 頁）：**snapshot → lock → packages → jobs → documents** 五段工程文件工作流（`backend/server/engineering/api.py`，8 條路由 prefix `/api/v1`；詳見 4. 功能範圍）。

### 1.4 系統邊界摘要

- 全站 HTTP 路由共 **63 條**：`main.py` 46 + `rag_api.py` 5 + `catalog_admin.py` 4 + `engineering/api.py` 8（grep 逐條列出核對；無 websocket）。
- HTML 頁面 6 頁：`/`（首頁）、`/styles`、`/library`、`/scene`（主工作流）、`/rag`（RAG 測試台）、`/engineering`（工程文件）。
- 啟動基準 port 8002（`README.md:30,46`；被占用改 8023，`README.md:35`）；port 由啟動指令決定，程式無硬編。

---

## 2. 商業目標

| 項目 | 內容 |
| :--- | :--- |
| **背景與痛點** | 平面圖到設計提案之間缺少可自助操作的工具：住戶不易描述需求、設計師往返確認成本高；提案到工程估價之間又需人工重算。RoomPilot 以單一網頁流程自動化「辨識 → 需求 → 配置 → 預覽 → 渲染」，並以工程文件 MVP 把已鎖定方案轉成工程量/估價/排程文件。 |
| **策略契合度** | AIPE03 結業專題；於成果發表展示完整工程能力（發表日期未查證，見 1. 專案總覽）。 |
| **成功指標** | 主要與次要 KPI 見下表。 |

| KPI | 目標值 | 依據 |
| :--- | :--- | :--- |
| 正式家具集合完整性（主要） | 恆等 **8,557** 件且 id 唯一，不符即拒絕載入 | `backend/catalog/cloud_catalog.py:15` `OFFICIAL_CATALOG_COUNT = 8_557` 與 :96-103 強制驗證；schema 版本 `official-json-8557-v3`（同檔 :221）。注意：8,557 的實際載入來源檔是 `JSON/furniture/furniture_official_catagory.json`（頂層 count=8557 實測，`main.py:137-139` `OFFICIAL_FURNITURE_CATALOG_PATH` → `CLOUD_CATALOG_PATH`）；`backend/catalog/data/furniture_catalog_cloud_9350.json`（count=9,350 實測）是另一份舊來源檔（`docs/owners/KAI.md:19` 定位為 PostgreSQL 不可用時的唯讀 fallback），**不是** 8,557 的正規化前身——舊導入版的 9,350 件目標已失效 |
| 隔離資料不外流（主要） | quarantine **1,514** 筆未對應家具不進網頁、Agent 與 3D 場景 | `backend/catalog/data/quarantine/unmatched_cloud_furniture/unmatched_catalog_items.json` 實測 count=1,514；`CLAUDE.md` 禁令「將 quarantine 資料視為正式家具」 |
| 渲染送出隱私剝除（主要） | 遠端渲染 payload 100% 剝除姓名、電話、Email 等私人欄位 | `backend/server/render_service.py:12` `PRIVATE_KEYS` 與 :60 過濾邏輯 |
| 自動化測試（次要） | `tests/` 99 支 pytest 檔 + `tests/static/` 3 支 Node 測試全數通過 | `find tests -maxdepth 1 -name "test_*.py" | wc -l` = 99、`ls tests/static/*.test.mjs | wc -l` = 3；另 `training/tests/` 11 支為辨識訓練用。完整 pytest 於本基準已實測：`pytest -q tests` = **811 passed / 1 failed / 9 skipped**（共 821）；repo 根 `pytest -q`（含 `training/`）= **916 passed / 3 failed / 9 skipped**。唯一 `tests/` 紅燈為 `tests/test_scene_v2_contract.py::test_scene_entrypoint_cache_key_matches_bundle_content`（cache-busting 雜湊守約，見 Q-002） |
| 平面圖辨識驗收基準（次要） | (未查證——舊導入版引用的 `floor04.png` 19 牆/5 門/5 窗/7 房基準已不在現行 `README.md`；離線評測工具 `backend/floorplan/eval_doors.py`、`eval_windows.py` 仍存在，正式門檻待補) | `grep '19 面牆' README.md` 無命中；`eval_doors.py` 72 行、`eval_windows.py` 101 行實存 |
| 房型分類品質（次要） | DINOv2 房間分類 own_eval 72 房 90.3%（vs 純管線 79.2%） | `backend/floorplan/room_classifier.py:1-13` docstring；缺 torch/權重即自動停用 |

---

## 3. 使用者故事與允收標準

註：本專案無 `.feature` 檔；「對應測試」欄為 `tests/` 內實際存在的 pytest 檔案（本次以 `ls` 逐一確認存在）。測試內部斷言未逐條重查者，以檔案級對應為準。

### Epic A：專案與平面圖（步驟 1–5）

| ID | 描述 (As a / I want to / So that) | 允收標準 | 對應測試 |
| :--- | :--- | :--- | :--- |
| US-001 | As a 屋主, I want to 建立專案並在重新整理後恢復進度, so that 不必一次做完全部流程。 | 1. `POST /api/projects` 回 201 2. `PUT /api/projects/{id}/workflow`（`main.py:2046`）保存工作流狀態 3. workflow JSON 超過 2MB 拒絕（`MAX_WORKFLOW_BYTES`，`project_store.py:13`） 4. 專案保存不可用時回 503 並於忙碌時附 `Retry-After: 2`（`main.py:226-243`） | `tests/test_project_workflow_api.py`、`tests/test_project_store_hardening.py` |
| US-002 | As a 屋主, I want to 上傳 PNG/JPG/DXF 平面圖, so that 系統以我的實際格局做提案。 | 1. 副檔名限 `.dxf/.png/.jpg/.jpeg`（`main.py:164`） 2. 平面圖上限 20MB（`main.py:180`） 3. `.dxf` 內容非可讀文字 DXF 時明確報錯（`main.py:1978`） | `tests/test_project_workflow_api.py`、`tests/test_scene_workflow.py` |
| US-003 | As a 屋主, I want to 用兩點校正公分尺度, so that 家具尺寸與空間比例正確。 | 1. 自動比例信心 < 0.8 時要求人工確認，不得默默採用（`analysis.py:36,498`） 2. 跨模組長度一律公分（`AGENTS.md` 契約、`backend/engine/schema.py` docstring） | `tests/test_floorplan_vision.py` |
| US-004 | As a 屋主, I want to 確認辨識出的空間、牆、門、窗、樑與柱, so that 後續配置建立在正確結構上。 | 1. 辨識止於 `layout_json`（`CLAUDE.md` 產品邊界） 2. 結構變更必須回到第 4 步並重新驗證目前家具（`README.md` 八步流程段） | `tests/test_floorplan_vision_api.py`、`tests/test_cody_room_recognition.py` |
| US-005 | As a 屋主, I want to 用視覺問卷表達全屋與逐房需求, so that 提案符合我的生活方式。 | 1. 題庫 55 組（實測） 2. 先全屋風格/材質/冷氣範圍，再逐房用途/家具/尺寸/數量（`README.md` 第 5 步） 3. 家電需求留在問卷與 `scene_json.render_context` 協助第 8 步生圖，不列入 2D/3D 擺設（`CLAUDE.md`） | `tests/test_questionnaire_visual_catalog.py` |

### Epic B：AI 配置、3D 與渲染（步驟 6–8）

| ID | 描述 (As a / I want to / So that) | 允收標準 | 對應測試 |
| :--- | :--- | :--- | :--- |
| US-006 | As a 屋主, I want to 讓 AI 依需求選家具, so that 不必自己逐件挑選。 | 1. LLM（OpenRouter）為可選；每房最多 8 種家具（`MAX_ITEMS_PER_ROOM`，`select.py:32`） 2. LLM 只決定選哪些件，不得捏造家具、跨房借用候選或輸出座標（`select.py` docstring） 3. 第 6 步家具資料以 PostgreSQL view `roompilot.furniture_catalog_current` 優先，資料庫不可用才回退已驗證 JSON（`CLAUDE.md`） | `tests/test_agent_select.py`、`tests/test_agent_selection_api.py` |
| US-007 | As a 屋主, I want to 系統自動擺位並自我修復失敗, so that 得到合法可行的配置。 | 1. 座標與合法性只由 `backend/engine/` 計算（`AGENTS.md` 契約；`place.py:6` docstring「本模組本身絕不計算或修改座標」） 2. 擺放失敗修復最多 3 輪（`resolve_placements` `max_rounds=3`，`place.py:137`） 3. 未處理的碰撞、淨空、超界或模型載入問題阻擋下一步（`README.md`） | `tests/test_placement.py`、`tests/test_clearance.py`、`tests/test_agent_place.py` |
| US-008 | As a 屋主, I want to 在 3D 場景切換風格與色卡, so that 比較不同方向。 | 1. 6 風格 × 3 色卡 = 18 張（`taiwan_style_cards.json` 實測：scandinavian/japanese/modern_minimal/cream/industrial/american 各 3） 2. GLB 由 CloudFront 交付（`main.py:2445`） 3. 家具型錄伺服器端分頁（`page_size` 1–80，預設 24，`main.py:2714`） | `tests/test_official_cloud_catalog.py`、`tests/test_library_mode1.py`、`tests/test_catalog_six_style_contract.py` |
| US-009 | As a 屋主, I want to 鎖定方案並送 AI 渲染, so that 拿到逐房寫實成果。 | 1. `POST /api/projects/{id}/render-jobs` 回 202（`main.py:2270`） 2. `mode` 僅限 `palette_comparison`/`room_final`（`render_service.py:11`） 3. 送出前剝除私人欄位（`render_service.py:12,60`） 4. `ROOMPILOT_RENDER_PROVIDER_URL` 有值時優先走遠端轉送，否則可用內建生圖供應者（`render_providers.py:16,55`） 5. 渲染 PNG 上限 20MB（`MAX_RENDER_BYTES`，`main.py:177`） | `tests/test_remote_render_workflow.py` |

### Epic C：家具 RAG 檢索（新子系統，舊導入版無）

| ID | 描述 (As a / I want to / So that) | 允收標準 | 對應測試 |
| :--- | :--- | :--- | :--- |
| US-010 | As a 團隊成員/設計師, I want to 用口語描述檢索家具, so that 驗證與調校選件品質。 | 1. `POST /api/rag/search`（`rag_api.py:146`）走「LLM parser → PostgreSQL pgvector → reranker」管線（`backend/spatial_data/rag/service.py:1`） 2. 非同步查詢 `POST /api/rag/search/jobs` 回 202，超過 active 上限回 429 `rag_job_capacity_reached`（`rag_api.py:155`） 3. 就緒守門：embedding 模型快取缺失或 pgvector 表無資料列為 blocker（`service.py:82-90`） 4. 受控詞彙：6 風格、24 氛圍詞、19 家具群組（`rag/data/taxonomy.json`、`category_groups.json` 實測） 5. embedding 模型 `BAAI/bge-m3`（`backend/catalog/rag_repository.py:12`） | `tests/test_rag_api.py`、`tests/test_rag_domain.py`、`tests/test_rag_frontend.py` |

### Epic D：工程文件 MVP（新子系統，舊導入版無）

| ID | 描述 (As a / I want to / So that) | 允收標準 | 對應測試 |
| :--- | :--- | :--- | :--- |
| US-011 | As a 設計師, I want to 鎖定設計版本並產生工程文件包, so that 交付工程量、估價與排程給客戶/廠商。 | 1. `PUT .../snapshot` path 與 payload 的 project_id/revision 不一致回 422 `PATH_PAYLOAD_MISMATCH`（`engineering/api.py:116-123`）；鎖定版本覆寫回 409 `LOCKED_REVISION_CANNOT_BE_OVERWRITTEN`（同檔 :126-133） 2. 未鎖定（`approval_status != "designer_confirmed"`）不得產包，回 409 `REVISION_NOT_LOCKED`（`api.py:180-198`） 3. 產包為 202 非同步 job，失敗分 `XLSX_ADAPTER_UNAVAILABLE`/`ENGINEERING_PACKAGE_FAILED`（`api.py:216-268`） 4. 文件下載僅允許 `.runtime/engineering` 之下實檔（路徑穿越防護，`api.py:295-303`），支援 .json/.html/.xlsx 5. 知識庫取自 `backend/catalog/data/engineering/`（14 項條目：10 份資料檔＋3 份說明文件＋`production_templates/` 目錄） | `tests/test_engineering_snapshot_api.py`、`tests/test_engineering_documents_api.py`、`tests/test_engineering_quantity_rules.py`、`tests/test_engineering_cost_schedule.py`、`tests/test_engineering_advanced_rag.py`、`tests/test_engineering_contract_exports.py`、`tests/test_engineering_frontend.py` |
| US-012 | As a 屋主, I want to 取得概念設計階段的工程概算, so that 及早掌握預算量級。 | 1. `POST /api/cost/estimate`（`main.py:3658`）以具來源的單價區間產生概算（`cost_estimation.py:1` docstring） 2. 單價資料由 Phase 4 runtime cost catalog 供應（`cost_estimation.py:9` 消費 `load_runtime_cost_catalog`） | `tests/test_cost_estimation_api.py` 等 cost_estimation 系列 2 支 |

### Epic E：型錄治理（新子系統，舊導入版無）

| ID | 描述 (As a / I want to / So that) | 允收標準 | 對應測試 |
| :--- | :--- | :--- | :--- |
| US-013 | As a 型錄管理者, I want to 經 API 維護家具型錄, so that 不必直接改 JSON 檔。 | 1. `/api/admin/furniture` CRUD 4 條（POST 201/GET/PATCH/DELETE，`catalog_admin.py:234-294`） 2. 寫入走交易式 admin repository：參照驗證、activation gate、樂觀併發與 audit record（`backend/catalog/postgres_admin_repository.py:1-6`） 3. 公開型錄維持唯讀；strict PostgreSQL 模式不靜默回退掃 JSON（`runtime_catalog_repository.py:1-6`） | `tests/test_postgres_*` / `test_catalog_*` / `test_runtime_catalog_phase4` 等資料層 8 支（實測：`test_catalog_connection_pool`、`test_catalog_data_hygiene`、`test_catalog_six_style_contract`、`test_postgres_catalog_contract`、`test_postgres_catalog_crud`、`test_postgres_project_store`、`test_postgres_single_source_phase5`、`test_runtime_catalog_phase4`） |

---

## 4. 範圍與限制

| 項目 | 內容 |
| :--- | :--- |
| **功能範圍** | 以下模組均見於現行工作樹（Python 行數為 `wc -l` 實測；六個領域模組合計 15,815 行，加 `backend/server/` 的 12,493 行後 `backend/` 全樹為 28,308 行）：<br>- 平面圖辨識：`backend/floorplan/`（9,313 行；PNG/JPG→牆門窗房間、DXF 轉換、DINOv2 房型分類、符號比對）<br>- DXF→3D 幾何：`backend/upgrade3d/`（305 行）<br>- 家具型錄與 PostgreSQL：`backend/catalog/`（3,199 行；8,557 件官方集合、Phase 1–5 repository、RAG adapter、表面材質處理）<br>- 空間資料與家具 RAG runtime：`backend/spatial_data/`（1,236 行，主體為 `rag/` 子套件；經 `backend/server/rag_api.py` 曝露 `/rag` 與 `/api/rag/*` 5 條路由）<br>- LLM 選件與擺位紀律：`backend/agent/`（1,045 行）<br>- 幾何擺放引擎：`backend/engine/`（717 行；幾何與規則唯一裁決者）<br>- FastAPI 整合：`backend/server/`（唯一 FastAPI，63 條路由；`main.py` 3,695 行，另含 `engineering/` 子套件、`rag_api.py`、`catalog_admin.py`，與新增 service 檔 `cost_estimation.py`/`render_providers.py`/`questionnaire_visuals.py`/`style_cards.py`）<br>- 正式前端：`backend/server/static/`（1,031 檔；6 HTML、頂層 JS 42 支、vendored Three.js 無 CDN 依賴；入口 bundle `scene_v2.js` 13,803 行 + `scene_viewer.js` 5,555 行）<br>- PostgreSQL 五階段：契約 `docs/contracts/POSTGRESQL_*.md` 對應 `scripts/sql/`（Phase 1/2/5）、`scripts/project_store/`（Phase 3）、`scripts/runtime_catalog/`（Phase 4）<br>- 專案 skill：`.claude/skills/` 四支進版控（roompilot-security／furniture-query／proposal／budget，追蹤檔 14 個，commit `3b2438dd` 起）<br>- 次要原型：`frontend3d/`（Vite+React 18+R3F，經 `/api` 代理共用同一後端；`frontend3d/AGENTS.md` 明定 secondary prototype） |
| **非功能需求** | 性能: 型錄伺服器端分頁（`page_size` 1–80 預設 24）；GZip 壓縮（`GZipMiddleware(minimum_size=1024)`，`main.py:215`）；靜態資產內容雜湊 cache-busting（`?v=sha256-` 前 12 碼，守約測試 `tests/test_scene_v2_contract.py:20-28`）／ 安全與隱私: 遠端渲染剝除私人欄位；`.env` 不提交（`.gitignore`；`.env.example` 93 行為契約，`tests/test_env_example_contract.py` 守門）；工程文件下載路徑穿越防護；風險基線與補強由 `roompilot-security` skill 承接（其 SKILL.md 明言現況「全端點無認證/授權」，見 Q-006）／ 可用性: OpenRouter 為可選能力（`OPENROUTER_API_KEY` + `OPENROUTER_INTAKE_ENABLED=1` 或 `OPENROUTER_SCENE_PLANNING_ENABLED=1`，`intake_service.py:138`、`scene_service.py:82`），未設定或失敗必須本地 fallback；專案保存/型錄不可用回 503 而非假成功（`main.py:226-266`）／ 一致性: 跨模組長度一律公分、新欄位 `_cm`、面積 `_m2`（根目錄 `AGENTS.md` 契約 11 條）；未更新兩端測試不得改公分制 payload（`CLAUDE.md`） |
| **不做什麼** | - 不建立第二套 FastAPI 或正式前端（`CLAUDE.md` 禁令）<br>- 幾何決策不移到 Graph RAG、瀏覽器或 LLM；Graph RAG 只補強關係與證據（`README.md:127`、`docs/TEAM_AI_OWNERSHIP.md:53`）<br>- quarantine 1,514 筆不進網頁、Agent 與 3D 場景<br>- 家電需求不列入 2D/3D 擺設（僅供第 8 步生圖 context）<br>- 本機 IKEA GLB 備援尚未完成：完成前不得在 `.env` 啟用本機模式、不得提交大型 GLB（`README.md` 開頭段）<br>- `.env`、模型權重、GLB/GLTF/BIN 不進版控（`.gitignore:73-78`，例外 `pbr_assets/**`） |
| **假設與依賴** | 假設: 使用者可提供 PNG/JPG/DXF 平面圖；DXF 缺可靠單位時自動比例為推測值需校正確認 ／ 依賴: CloudFront `https://ddgsm1yg3xikc.cloudfront.net`（GLB/圖片交付）、PostgreSQL 17（第 6 步型錄優先來源與 RAG pgvector）、OpenRouter（可選）、遠端渲染供應商（`ROOMPILOT_RENDER_PROVIDER_URL`/`TOKEN`/`NAME`，`render_service.py:42-44`；未設定時 `render_providers.py` 內建生圖轉接層）、BGE-M3 embedding（離線快取，`rag/model_runtime.py`）、Node.js（工程 XLSX 經 `engineering/workbook_builder.mjs`，由 `ROOMPILOT_ARTIFACT_NODE` 指定；`frontend3d/` 需 Node 24/npm 11）、Python 3.12 + `requirements.txt` 21 個 pin（2026-07-27 team baseline）；torch 為房型語意層選配（約 2GB，是否全隊必裝待拍板，`requirements.txt:46-57` 註解） |

---

## 5. 待辦問題與決策

| ID | 描述 | 狀態 | 負責人 |
| :--- | :--- | :--- | :--- |
| Q-001 | 目標發布/發表日期在 repo 內無任何紀錄（未查證），需補正式來源 | 待討論 | 全隊 |
| Q-002 | cache-busting 雜湊與實檔不符：`scene.html` 引 `scene_v2.js?v=sha256-27f24b6bede3`/`site.css?v=sha256-5693fe5d95c5`，實算前 12 碼為 `7d938e1fdc28`/`e362900c8195`；`library.html` 的 `library.js` 亦不符 → 守約測試 `test_scene_v2_contract.py` 預期紅燈；且全站混用日期版本 token（`index.html`/`styles.html` 與 `scene_v2.js` 內部），雜湊為手動維護、無自動重算腳本 | 待討論 | Bella |
| Q-003 | 舊導入版的 `floor04.png` 辨識驗收基準（19 牆/5 門/5 窗/7 房）已不在現行 `README.md`；辨識 KPI 門檻需重新拍板（評測工具 `eval_doors.py`/`eval_windows.py` 仍在） | 待討論 | Cody、Ben |
| Q-004 | `docs/TEAM_AI_OWNERSHIP.md` 分支對照寫 `origin/kai-with-bellatest1`，但遠端實際無此分支（現為 `origin/kai`、`origin/kai-new`），文件與遠端不一致 | 待討論 | Kai、Bella |
| Q-005 | `frontend3d/README.md:15`（另 :22 文字說明）範例 port 8000 與 `vite.config.js:8` proxy 8002 不一致 | 待討論 | Bella |
| Q-006 | `roompilot-security` skill 基線指出全端點無認證/授權、外部抓取無 SSRF 防護、DB 預設明文連線；2026-08-04 實測範圍已縮小為 59/63 條——`/api/admin/furniture` 寫入端點 4 條已有 Bearer token 認證（`catalog_admin.py:170-195`，`secrets.compare_digest`，失敗回 401），其餘 59 條（含全部 `/api/projects/*`、`/api/v1/*`、`/api/rag/*`）保護策略待定 | 待討論 | 全隊 |
| Q-007 | torch（DINOv2 房型語意層）是否列入全隊必裝 baseline 待拍板；缺它房型準確度由 90.3% 退回幾何猜測（`requirements.txt` 註解、`MAIN_SYNC_TODO.md`） | 待討論 | Ben |
| Q-008 | 完整 pytest 於本基準（a2179f7e）已實跑：`pytest -q tests` = 811 passed / 1 failed / 9 skipped（共 821）；repo 根 `pytest -q`（含 `training/`）= 916 passed / 3 failed / 9 skipped。除 Q-002 的雜湊紅燈外，`training/tests/test_annotation_drafts.py::test_house_round_trip` 與 `training/tests/test_room_office_stair.py::test_gt_label_separates_office_and_stairwell` 兩支缺模組依賴，處置待裁決 | 待討論 | 全隊 |
| D-001 | 正式家具集合固定 **8,557** 件（載入來源檔 `JSON/furniture/furniture_official_catagory.json`，非 `furniture_catalog_cloud_9350.json`），程式強制驗證不符即拒載；正式環境嚴格 `cloudfront` 模式（舊導入版 9,350 之值作廢） | 已決定 | Kai |
| D-002 | 主 UI 收斂為 8 步（內部狀態機 11 step 保留）；步驟順序以 `scene_workflow.js` 為準 | 已決定 | 全隊 |
| D-003 | 風格定案 6 風格 × 3 色卡 = 18 張（`taiwan_style_cards.json`） | 已決定 | 全隊 |
| D-004 | 跨模組幾何資料一律公分，新欄位 `_cm`、面積 `_m2`（根目錄 `AGENTS.md`） | 已決定 | 全隊 |
| D-005 | 第 6 步家具資料以 PostgreSQL view `roompilot.furniture_catalog_current` 優先；資料庫暫不可用才回退已驗證 JSON（`CLAUDE.md`、`AGENTS.md:56`） | 已決定 | Kai、Bella |
| D-006 | 工程文件產包必須先設計師鎖定（`approval_status == "designer_confirmed"`），未鎖定回 409；文件僅由 `.runtime/engineering` 交付 | 已決定 | Bella |
| D-007 | 家具 RAG 只做檢索與證據，不做幾何；查詢轉譯規範由 `roompilot-furniture-query` skill 承接（硬過濾/軟加權界線與放寬順序） | 已決定 | Django |
| D-008 | `.claude/skills/` 四支專案 skill 進版控共用（`.gitignore:43-46` 唯一例外 `!.claude/skills/`） | 已決定 | Django |

---

### 附註：依據與查證方式

本文件依 `README.md`、`docs/TEAM_AI_OWNERSHIP.md`、根目錄 `AGENTS.md`、`CLAUDE.md`、`docs/contracts/` 與程式碼實測（分支 `django-skill`、commit `a2179f7e`）撰寫。關鍵數字（63 條路由、8,557/9,350/1,514 件、55 題、18 色卡、每房 8 種、3 輪修復、2MB/20MB 上限、0.8 信心門檻、99+3 測試檔、21 個 pin）均於 2026-08-04 以工具讀檔或指令對現行工作樹實測核對；偵察底稿存於 scratchpad `vibemap/*.md`。標「(未查證)」者為 repo 內查無依據或本次未實際執行的項目。模板 `INDEX.md` 指向的 `software_development_documentation_guide_zh_tw.docx` 與 `docs/document-system/` 不在本 repo (未查證：來源不在 repo)。
