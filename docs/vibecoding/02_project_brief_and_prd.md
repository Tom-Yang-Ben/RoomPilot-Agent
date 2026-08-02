# 專案簡報與產品需求文件 (PRD) - RoomPilot-Agent

> 本文件由 VibeCoding 模板 02_project_brief_and_prd.md 導入 RoomPilot-Agent 生成 | 基準分支 bella-local-20260726 | 2026-07-26

> **版本:** v1.0 | **更新:** 2026-07-26 | **狀態:** 草稿

---

## 1. 專案總覽

| 項目 | 內容 |
| :--- | :--- |
| **專案名稱** | RoomPilot-Agent(`pyproject.toml`:`roompilot-agent` 0.1.0;FastAPI 標題「AI 室內風格與家具配置展示系統」,`backend/server/main.py:144`) |
| **狀態** | 開發中(本文件基準:分支 `bella-local-20260726`、commit `e48cd67`) |
| **目標發布日期** | 2026-08-20 成果發表(未查證——repo 內查無任何日期紀錄,此日期為團隊口頭資訊,待補正式來源) |
| **核心團隊** | 依 `README.md` 團隊目錄表共 6 位負責人:Cody=`backend/floorplan/`+`backend/upgrade3d/`、Kai=`backend/catalog/`、Django=`backend/spatial_data/`、Yen=`backend/agent/`、AN=`backend/engine/`、Bella=`backend/server/`+`frontend3d/` |

### 1.1 問題陳述

一般住戶拿到建商平面圖後,難以把「空間現況 + 生活需求」快速轉成可討論的室內設計方向;與設計師往返確認格局、風格與家具耗時。RoomPilot 把「上傳平面圖 → 尺度校正 → 空間結構確認 → 需求問卷 → AI 選件與擺位 → 3D 預覽 → 遠端渲染提案」串成單一網頁流程(入口 `/scene`),讓使用者在一次操作內得到可比較、可修改的室內設計提案。(`README.md` 自述:「RoomPilot 是 AIPE03 第四組的室內設計即時提案溝通 Agent」。)

### 1.2 目標用戶

| 用戶 | 使用情境 |
| :--- | :--- |
| 屋主/一般住戶 | 上傳自家平面圖,經問卷表達需求,取得 2D/3D 家具配置與風格提案 |
| 室內設計師 | 以同一流程與客戶即時確認空間方向、風格色卡與家具選件(`README.md`:「協助設計師快速和使用者確認空間方向」) |

### 1.3 主流程(程式碼權威順序)

順序以 `frontend/scene_workflow.js:4-16` 的 `WORKFLOW_STEPS` 為準,共 11 個內部步驟;其中 `recognition` 與 `calibration` 共用同一個「確定尺寸」UI 面板(`WORKFLOW_PANEL_BY_STEP`,同檔 18-30 行),因此 `/scene` 頁面只顯示 10 顆步驟按鈕(`scene.html:23-32`)。

| # | 內部步驟 | UI 名稱 | 主要結果/伺服器行為(已對照程式碼) |
| :--- | :--- | :--- | :--- |
| 1 | `project` | 建立專案 | `POST /api/projects`(201);SQLite 持久化於 `.runtime/projects.sqlite3` |
| 2 | `upload` | 上傳平面圖 | `POST /api/projects/{id}/floorplan`;副檔名限 `.dxf/.png/.jpg/.jpeg`(`main.py:111`),否則 415 |
| 3 | `recognition` | 確定尺寸(辨識) | `POST /api/projects/{id}/floorplan/analyze`;DXF 走 `dxf` 引擎、PNG/JPG 走 `cody` 引擎;未先確認圖檔內容回 409 `floorplan_confirmation_required` |
| 4 | `calibration` | 確定尺寸(校正) | 兩點公分尺度校正;自動比例信心 < 0.8 需人工確認(`MIN_AUTOMATIC_SCALE_CONFIDENCE`,`backend/floorplan/vision/analysis.py:35`) |
| 5 | `space_confirmation` | 空間與結構 | 確認房間、牆、門、窗與結構 |
| 6 | `requirements` | 需求問卷 | Test2 視覺問卷,題庫 55 組(`backend/server/data/questionnaire_visual_catalog.json` 的 `question_count`,實測 55) |
| 7 | `layout_2d` | 2D 家具配置 | `POST /api/scene/generate`;Yen 選件 + AN 引擎擺位與驗證 |
| 8 | `white_model_3d` | 3D 白模 | 以已確認格局與家具建立 3D 場景 |
| 9 | `realistic_3d` | 即時寫實 | 6 風格 × 3 色卡 = 18 張 StylePack + PBR 材質 + CloudFront GLB |
| 10 | `proposal_review` | 方案鎖定 | 核對方案並鎖定色卡比較視角 |
| 11 | `ai_render` | AI 渲染 | `POST /api/projects/{id}/render-jobs`(202)送遠端渲染 |

限制註記:步驟前置依賴(`REQUIRED_COMPLETIONS`)僅由前端 `scene_workflow.js:43-105` 強制;伺服器端 `main.py:113-125` 的 `WORKFLOW_STEPS` 是無序集合,只驗步驟名不驗順序(見 5. Q-007)。

---

## 2. 商業目標

| 項目 | 內容 |
| :--- | :--- |
| **背景與痛點** | 平面圖到設計提案之間缺少可自助操作的工具:住戶不易描述需求、設計師往返確認成本高;既有做法需人工繪製 2D/3D 與渲染。RoomPilot 以單一網頁流程自動化「辨識 → 需求 → 配置 → 預覽 → 渲染」。 |
| **策略契合度** | AIPE03 結業專題;於成果發表暨廠商面試展示完整工程能力(發表日期未查證,見 1. 專案總覽)。 |
| **成功指標** | 主要與次要 KPI 見下表。 |

| KPI | 目標值 | 依據 |
| :--- | :--- | :--- |
| 平面圖辨識驗收基準(主要) | 同一張 `floor04.png` 辨識出 19 面牆、5 扇門、5 扇窗、7 個房間 | `README.md`「組員同步 Bella」段落明訂之驗收基準 |
| 門誤判過濾率(主要) | ≥ 95%(門樣式圖不被誤判成窗) | `backend/floorplan/eval_doors.py`(離線評測,目標值寫在程式輸出) |
| 正式家具集合完整性(主要) | 恆等 9,350 件且每件具已驗證 CloudFront GLB;不符即拒絕載入 | `backend/catalog/cloud_catalog.py:18` `OFFICIAL_CATALOG_COUNT = 9_350` 與強制驗證;`furniture_catalog_cloud_9350.json` 實測 9,350 items |
| 自動化測試(次要) | 47 個測試檔、392 個收集測試全數通過 | `tests/` 實數 47 檔;`pytest --collect-only` 本次實測收集 392;完整 `uv run pytest` 本次實測:389 通過、2 失敗(`tests/test_scene_v2_contract.py` 兩項快取鍵比對)、1 跳過 |
| 窗偵測精準率/召回率(次要) | 目標門檻待補(評測工具已存在但未設定門檻) | `backend/floorplan/eval_windows.py`(輸出精準率與召回率) |

---

## 3. 使用者故事與允收標準

註:本專案無 `.feature` 檔;「對應測試」欄為 `tests/` 內實際存在的 pytest 檔案,關鍵斷言所在檔案已逐條 grep 核對;允收項在測試中沒有自動化斷言者,直接於該欄明註「無測試斷言」。

### Epic A:專案與平面圖(步驟 1–6)

| ID | 描述 (As a / I want to / So that) | 允收標準 | 對應測試 |
| :--- | :--- | :--- | :--- |
| US-001 | As a 屋主, I want to 建立專案並在重新整理後恢復進度, so that 不必一次做完全部流程。 | 1. `POST /api/projects` 回 201 2. `PUT /api/projects/{id}/workflow` 以 `expected_revision` 樂觀鎖保存,衝突回 409 `project_revision_conflict` 3. workflow JSON 超過 2MB 回 413(`project_store.py:11`) | `tests/test_project_workflow_api.py`;409/413 斷言在 `tests/test_project_store_hardening.py` |
| US-002 | As a 屋主, I want to 上傳 PNG/JPG/DXF 平面圖, so that 系統以我的實際格局做提案。 | 1. 副檔名限 `.dxf/.png/.jpg/.jpeg`,否則 415 2. 空檔或無效影像回 422 3. 檔案保存於 `.runtime/uploads/{project_id}/` | `tests/test_project_workflow_api.py`(415 副檔名斷言)、`tests/test_scene_workflow.py`;422 無測試斷言(程式行為在 `main.py` `_validate_floorplan_bytes`) |
| US-003 | As a 屋主, I want to 用兩點校正公分尺度, so that 家具尺寸與空間比例正確。 | 1. 手動兩點校正 confidence = 1.0 2. 自動比例信心 < 0.8 時系統加註 `scale_confirmation_required`,不得默默採用 | `tests/test_floorplan_vision.py` |
| US-004 | As a 屋主, I want to 確認辨識出的房間、牆、門、窗, so that 後續配置建立在正確結構上。 | 1. 未確認圖檔內容前呼叫 analyze 回 409 2. `floor04.png` 基準:19 牆/5 門/5 窗/7 房 3. 低信心或衝突結果須由使用者確認,圖示推測不覆蓋 OCR(`README.md`) | `tests/test_floorplan_vision_api.py`(analyze/confirm 流程);409 斷言在 `tests/test_project_workflow_api.py`;floor04 全項基準(19/5/5/7)無測試斷言,僅 `tests/test_floorplan_vision.py` 覆蓋 floor04 門弧偵測案例 |
| US-005 | As a 屋主, I want to 用視覺問卷表達逐房需求與風格偏好, so that 提案符合我的生活方式。 | 1. 題庫 55 組,依已確認空間類型顯示題目 2. 必填未完成不可進下一階段(`README.md`) 3. 問卷異動時既有 2D/3D 結果失效並要求重新產生 | `tests/test_questionnaire_visual_catalog.py` |

### Epic B:AI 配置、3D 與渲染(步驟 7–11)

| ID | 描述 (As a / I want to / So that) | 允收標準 | 對應測試 |
| :--- | :--- | :--- | :--- |
| US-006 | As a 屋主, I want to 讓 AI 依需求選家具, so that 不必自己逐件挑選。 | 1. LLM(OpenRouter)為可選;選擇結果經白名單驗證:每房最多 8 種、每種數量 1–6(`backend/agent/select.py`) 2. LLM 失敗自動降級本地規則,回應 `source` 標明 `openrouter`/`local_rules`/`local_rules_unvalidated` 3. 使用者指定家具受保護不被移除 | `tests/test_agent_select.py`(白名單上限斷言);`source` 值斷言在 `tests/test_project_workflow_api.py` |
| US-007 | As a 屋主, I want to 系統自動擺位並自我修復失敗, so that 得到合法可行的配置。 | 1. 座標只由 `backend/engine/` 計算(碰撞、淨空、邊界;`README.md` 共同規則 3) 2. 擺放失敗修復最多 3 輪(`resolve_placements` `max_rounds=3`,`backend/agent/place.py:137`) 3. 使用者指定家具失敗時只升級人工(escalate),不自動替換 | `tests/test_placement.py`、`tests/test_clearance.py`、`tests/test_agent_place.py` |
| US-008 | As a 屋主, I want to 在 3D 場景切換風格與色卡, so that 比較不同方向。 | 1. 6 風格 × 3 色卡 = 18 張(`taiwan_style_cards.json` 實測) 2. GLB 由 CloudFront 交付(預設 `cloudfront` 模式;`/api/furniture/{id}/model` 307 轉址) 3. 家具型錄伺服器端分頁(`page_size` 1–80,預設 24) | `tests/test_official_cloud_catalog.py`;分頁斷言在 `tests/test_library_mode1.py`;307 轉址無測試斷言(程式行為在 `main.py` `_model_response_for_merged_furniture`,`tests/test_catalog_six_style_contract.py` 只測 `local` 模式 GLB 回應) |
| US-009 | As a 屋主, I want to 鎖定方案並送遠端 AI 渲染, so that 拿到寫實提案圖。 | 1. `POST /api/projects/{id}/render-jobs` 回 202 2. `mode` 僅限 `palette_comparison`/`room_final` 3. 供應商未設定回 503,不得假成功 4. 送出前剝除姓名、電話、Email 等私人欄位(`render_service.py:12` `PRIVATE_KEYS`) | `tests/test_remote_render_workflow.py`(503 與兩種 mode 斷言;202 無測試斷言,狀態碼定義在 `main.py:1756` 路由裝飾器) |

---

## 4. 範圍與限制

| 項目 | 內容 |
| :--- | :--- |
| **功能範圍** | - 平面圖辨識與升維:`backend/floorplan/`(PNG/JPG → 牆門窗房間)、`backend/upgrade3d/`(DXF → 3D 結構) - 家具型錄與模型交付:`backend/catalog/`(9,350 件 CloudFront 正式集合 + 六風格 enrichment) - 需求 intake、選件與擺放修復策略:`backend/agent/` - 幾何擺放引擎(碰撞/淨空/邊界):`backend/engine/` - FastAPI 整合與十步驟前端:`backend/server/`(唯一 FastAPI,44 條路由 = 27 GET + 16 POST + 1 PUT,全在 `main.py`) - 獨立 R3F DXF 檢視器:`frontend3d/`(Vite 子專案,經 `/api` 代理共用同一後端) |
| **非功能需求** | 性能: 型錄伺服器端記憶體快取 + 分頁(`page_size` 1–80 預設 24);啟動時預熱快取(`main.py` startup) / 安全與隱私: 遠端渲染剝除私人欄位;`.env` 不提交;上傳渲染 PNG 上限 20MB、workflow JSON 上限 2MB / 可用性: OpenRouter 為可選能力,未設定或失敗必須本地 fallback,核心流程不中斷(`docs/RoomPilot_現行版本總覽.md`) / 一致性: 跨模組長度一律公分、面積 `_m2`、payload 帶 `coordinate_unit: "cm"` 與 `schema_version`;專案寫入以 revision 樂觀鎖防衝突 |
| **不做什麼** | - 不在本機做寫實渲染:AI 渲染由遠端供應商代理,未設定回 503 - 不建立第二套 FastAPI 或第二套前端;前端不得自行實作碰撞/淨空/座標演算法 - quarantine 的 1,514 筆未對應舊家具不進網頁、Agent 與 3D 場景 - `LAYOUT_EVALUATION_SCHEMA.md` 的完整 `status`/`violations`/`warnings`/`score` 評估 API 不在現行範圍(總覽明列「尚未完整接入」) - `backend/spatial_data/` 獨立空間計算模組尚未實作(目錄僅 `.gitkeep` 佔位) |
| **假設與依賴** | 假設: 使用者可提供 PNG/JPG/DXF 平面圖;DXF 無可靠單位資訊時自動比例為推測值(`scale_basis='normalized'` 以長邊 12 公尺正規化,非真實尺寸,`backend/upgrade3d/dxf_parser.py`) / 依賴: CloudFront(`https://ddgsm1yg3xikc.cloudfront.net`)交付 GLB、OpenRouter(可選,`OPENROUTER_API_KEY` + `OPENROUTER_INTAKE_ENABLED=1` 或 `OPENROUTER_SCENE_PLANNING_ENABLED=1`)、遠端渲染供應商(`ROOMPILOT_RENDER_PROVIDER_URL`/`TOKEN`)、unpkg CDN(`three@0.165.0`,`scene.html` importmap)、Python >= 3.12 + uv |

---

## 5. 待辦問題與決策

| ID | 描述 | 狀態 | 負責人 |
| :--- | :--- | :--- | :--- |
| Q-001 | `main.py:2446` 引用 `/static/models/roompilot-curtain.glb`,但 `frontend/` 下實測無任何 `.glb`;軟裝窗簾模型缺檔待處理(前端對載入失敗已有兜底:以同尺寸白色替代物顯示,`scene_viewer.js:2955-2957`,不中斷場景) | 待討論 | Bella |
| Q-002 | `surface_catalog.json` 的 `style_surface_profiles` 用 12 個舊風格 ID(實測:american、american_country、classical、eclectic、industrial、light_luxury、melad、minimalist_muji、modern、nordic_modern、scandinavian、wabi_sabi),與家具 6 風格體系不一致;6 個現行 style_id 中僅 `american`/`industrial`/`scandinavian` 有同名 profile,`japanese`/`modern_minimal`/`cream` 查無 → 落入 fallback `scandinavian`(`main.py:428`),映射是否有意設計待確認 | 待討論 | Kai、Bella |
| Q-003 | `main.py` `DATASET_DIR` 指向 repo 根 `dataset/`(不存在),實際 GLB 在 `data/dataset/`;`cloudfront` 模式不受影響,但 `local` 模式的本機解析路徑落空 | 待討論 | Bella |
| Q-004 | `docs/RoomPilot_現行版本總覽.md` 第 12 行寫「固定為八個步驟」但同檔表格列 10 步,為舊殘留,需修訂 | 待討論 | 文件維護(待補) |
| Q-005 | 目標發布/發表日期在 repo 內無任何紀錄(未查證),需補正式來源 | 待討論 | 本顥 |
| Q-006 | PostgreSQL 僅到 importer 階段(`scripts/sql/`),伺服器執行期型錄仍由 JSON + CSV 記憶體載入;是否接上執行期 API 待定 | 待討論 | Kai |
| Q-007 | 步驟前置依賴僅前端強制,伺服器端不驗順序,無法阻止跳步驟寫入;是否需伺服器端防護待議 | 待討論 | Bella |
| D-001 | 正式家具集合固定 9,350 件(cloud catalog 與 Manifest 一對一),程式強制驗證不符即拒載 | 已決定 | Kai |
| D-002 | 主流程順序以 `scene_workflow.js` 為準:上傳平面圖在需求問卷之前 | 已決定 | 全隊 |
| D-003 | 正式環境採嚴格 `cloudfront` 模式,連線失敗不自動改讀本機;離線備援須驗證後手動切 `local` | 已決定 | Kai、Bella |
| D-004 | 風格定案 6 風格 × 3 色卡 = 18 張(`taiwan_style_cards.json`) | 已決定 | 全隊 |
| D-005 | 跨模組幾何資料一律公分,新欄位以 `_cm` 命名,面積維持 `_m2`(`README.md` 共同規則 4) | 已決定 | 全隊 |

---

### 附註:依據與查證方式

本文件內容依 `README.md`、`docs/RoomPilot_現行版本總覽.md` 與程式碼實測(commit `e48cd67`)撰寫;所有路由、常數、數量(9,350 件、18 色卡、55 題、44 路由、392 收集測試)均以工具讀檔或指令實測核對,完整 pytest 亦已於 2026-07-26 實際執行(389 通過/2 失敗/1 跳過)。標「(未查證)」或「待補」者為 repo 內查無依據的項目。
