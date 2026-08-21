# 軟體需求規格 (Software Requirements Specification) - RoomPilot

> **版本:** v1.0 ｜ **更新:** 2026-08-12 ｜ **狀態:** 草稿（待 owner 核准）
> **Owner:** 系統分析（架構師合成）；DEC-* 與優先序欄位權威為產品 owner（[`requirements_tracker.xlsx`](../../VibeCoding_Workflow_Templates/01_requirements/requirements_tracker.xlsx) ①需求決策），工程師與 QA 共同審閱
> **語域:** L2（橋接）——業務詞與工程詞並列，跨層一律用穩定 ID
> **實例:** 單例（整個 RoomPilot 專案一份）
>
> **本文件回答**：[`brd.md`](./brd.md)／[`prd.md`](./prd.md) 的每一條業務承諾（DEC-*）在程式碼裡對應到哪些可測行為（FR-*）與可量測約束（NFR-*），以及每條需求的佐證落在哪一行。
> **本文件不含**：業務動機與價值論述（去 `brd.md`）、產品範圍與里程碑（去 `prd.md`）、驗收條件內文（去 `prd.md` 的 ACPT 段）、架構取捨理由（去 [`sad.md`](../03_architecture/sad.md) 與 `adr/`）、端點欄位級契約（去 [`api_spec.md`](../04_design/api_spec.md) 與 `openapi-*`）。
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、2026-08-12 工作樹。行號隨程式碼演進，衝突時以原始碼為準。

## 目錄

- [1. 中介層總表：DEC → FR/NFR](#1-中介層總表dec--frnfr)
- [2. 功能需求 (Functional Requirements)](#2-功能需求-functional-requirements)
- [3. 非功能需求 (NFR)](#3-非功能需求-nfr)
- [4. 資料需求 (Data Requirements)](#4-資料需求-data-requirements)
- [5. 外部介面 (External Interfaces)](#5-外部介面-external-interfaces)
- [6. 使用案例 (Use Case Specification)](#6-使用案例-use-case-specification)
- [7. 驗收標準對照 (Acceptance Criteria)](#7-驗收標準對照-acceptance-criteria)
- [8. 假設與待確認](#8-假設與待確認)
- [9. 追溯](#9-追溯)

---

## 1. 中介層總表：DEC → FR/NFR

### 1.1 業務承諾逐條翻譯

> DEC-* 的**狀態一律「待 owner 核准」**；本表只做翻譯，不代表業務決策已拍板。

| DEC | 業務承諾（L1 一句話） | 翻成的 FR | 翻成的 NFR | 步 |
| :--- | :--- | :--- | :--- | :--- |
| DEC-001 | 一張既有平面圖走完八步就拿到成套成果，不另開第二條交付路徑 | FR-009, FR-020, FR-023, FR-053, FR-054 | NFR-002, NFR-021 | S1–S8 |
| DEC-002 | 每個案子有可保存、可恢復的身分，中途離開不遺失進度 | FR-001–004, FR-008, FR-022 | NFR-001, NFR-003, NFR-004, NFR-005 | S1, SX |
| DEC-003 | 用手上的照片或 DXF 就能開案，不必重畫圖 | FR-005, FR-006, FR-017 | NFR-017 | S2 |
| DEC-004 | 電腦看圖的結果必須由人確認過才算數 | FR-007, FR-010–016, FR-018, FR-019 | NFR-017 | S3–S4 |
| DEC-005 | 需求用問卷收集，使用者不必懂專業術語 | FR-026, FR-027 | — | S5 |
| DEC-006 | 家電只影響最終效果圖，不進平面與立體擺設 | FR-028, FR-059 | — | S5, S8 |
| DEC-007 | 家具一律來自已驗證正式型錄，隔離區資料不得出現 | FR-039–045, FR-050–052, FR-066 | NFR-006, NFR-007 | S6 |
| DEC-008 | 家具必須真的放得下、走得過去，放不下要用中文說原因 | FR-029–038 | NFR-015, NFR-016, NFR-017 | S6 |
| DEC-009 | 同一空間提供 A／B 兩套配置，兩套過同樣的合法性檢查 | FR-031 | NFR-016 | S6 |
| DEC-010 | 生圖前先鎖視角；代表房先出色卡，每案只做一次以控成本 | FR-055, FR-056, FR-057 | NFR-001 | S7 |
| DEC-011 | 每房一張效果圖（客廳加夜景），不滿意可有限次修改 | FR-058, FR-060 | NFR-012, NFR-018 | S8 |
| DEC-012 | 對客戶的正式交付物只能有一份主件 | FR-061, FR-062, FR-063 | NFR-013 | S8 |
| DEC-013 | 費用只給公開行情概算並明講需現場丈量，不臆造價格 | FR-064 | — | S8 |
| DEC-014 | Pilot 服務邊界（僅本機／內網、是否需帳號）由 owner 明文界定 | FR-065, FR-067 | NFR-019, NFR-020, NFR-023 | SX |
| DEC-015 | 客戶案件資料存哪、誰備份、保留多久、結案怎麼刪 | FR-008 | NFR-022, NFR-025 | SX |
| DEC-016 | AI 檢索只排序既有候選，不新增、不替換、不決定放哪 | FR-046–049 | NFR-009, NFR-010 | S5 |
| DEC-017 | 外部服務壞掉要誠實中止並說明，不以假資料充數 | FR-040, FR-046, FR-062, FR-067 | NFR-008, NFR-011, NFR-012, NFR-014 | S6–S8 |
| DEC-018 | 第 4 步之後改結構會讓既有配置與生圖失效，要讓使用者知道重做哪些 | FR-016, FR-021 | — | S4, SX |
| DEC-019 | Pilot 驗收跑哪些案例、什麼算通過、綠燈基準線是什麼 | — | NFR-024, NFR-025 | SX |

### 1.2 業務詞 ↔ 工程詞對照

> 這張表是 L1 與 L3 之間唯一合法的轉換通道。左欄是業主與 PM 講的話，右欄是可執行、可斷言的東西。

| 業務詞（L1） | 工程詞（L3） | 佐證 | 綁定 ID |
| :--- | :--- | :--- | :--- |
| 「家具放得下」 | 七段固定順序檢查（出界→穿牆→本體重疊→淨空撞牆→淨空撞他人本體→淨空互撞→反向），只回最先命中者 | `backend/engine/clearance.py:118-143` | FR-034, ACPT-031 |
| 「走得過去」 | 門前 75 cm／窗前 40 cm（家具高 ≥90 cm 才受限）／有櫃家具正面 50 cm／背牆 5 cm 五個公分常數 | `backend/engine/constraints.py:21-23`；`clearance.py:24,33-37` | FR-035, ACPT-032 |
| 「不遺失進度」 | 單一 `workflow_json` 快照（深合併寫入、2 MB 上限）＋`revision` 樂觀鎖＋前端 `localStorage` pending 雙寫 | `project_store.py:11,199-243`；`scene_v2.js:1285-1375` | FR-003, FR-004, FR-022, ADR-004 |
| 「兩人同時改不會蓋掉彼此」 | `expected_revision` 不符回 409 `project_revision_conflict` 並附最新 project | `main.py:1848-1858` | FR-004, NFR-003 |
| 「人確認過才算數」 | `spatial_report.review_items` 與 `rooms[].confirmed` 比對，未清空時 422 `recognition_review_unresolved` | `main.py:1737-1781` | FR-007, ACPT-006 |
| 「比例對不對」 | `scale.source` 三來源與 confidence（手動 1.0／OCR 分數／門寬交叉檢核 0.9\|0.7），<0.8 產生 `scale_confirmation_required` | `vision/analysis.py:476-544` | FR-013, ACPT-011 |
| 「換張圖要重做」 | 七個 workflow 節點顯式寫入 `null` 並改寫前端 `_flow` | `main.py:3036-3063` | FR-016, FR-021 |
| 「A 案 B 案」 | `placement_variant` 只反轉類型錨點嘗試順序，B 走完全相同的碰撞與淨空驗證 | `scene_service.py:2539-2545`；`main.py:3630-3632` | FR-031, ACPT-029 |
| 「家電不要畫進平面」 | 只寫 `scene_json.render_context.appliance_requirements`，不進 `scene_objects` 與 `/api/furniture` | `scene_service.py:3043-3072`；`main.py:930-931` | FR-028, ADR-006 |
| 「用真的家具」 | PostgreSQL view `roompilot.furniture_catalog_current` 為優先來源，quarantine 集合零外洩 | `postgres_repository.py:199-204`；`tests/test_cloud_quarantine.py:23-40` | FR-041, FR-045, ADR-005 |
| 「AI 幫我挑」 | 向量檢索 ＋ `0.60*rerank+0.20*style+0.10*mood+0.10*confidence` 決定性排序；候選 id 集合不增不減 | `ranking.py:114-154`；`rag_repository.py:131-164` | FR-047, FR-049, ADR-008 |
| 「壞掉要講實話」 | 503（未設定／不可連線）、502（上游明確拒絕）、409（額度／版本衝突）；禁止假成功 | `main.py:2049-2057,2109-2116,2400-2408` | NFR-014, ADR-009 |
| 「一案只出一次色卡」 | 伺服器端旗標，第二次呼叫 409 `palette_already_generated`；全失敗不鎖定 | `main.py:2135-2221` | FR-056, ACPT-048 |
| 「不亂報價」 | 查無費率或單位不符列入 `needs_quote`，金額為 null 並附 `disclaimer_zh` | `cost_estimation.py:20-107` | FR-064, ACPT-055 |
| 「公分」 | 跨模組長度與座標一律公分，新欄位 `_cm`、面積 `_m2`、角度度數；相容欄位須帶 `coordinate_unit:"cm"` | [`AGENTS.md`](../../AGENTS.md) §不可違反的契約；`engine/schema.py:18-32` | NFR-017, ADR-007 |

---

## 2. 功能需求 (Functional Requirements)

> **優先級欄不在此文件填寫**：優先序、範圍納入／排除與里程碑屬產品 owner 權責，於 `requirements_tracker.xlsx` ①需求決策拍板、③Gate 簽核。本節只登記「系統實際做了什麼、在哪一行」。
> 分節依 [`AGENTS.md`](../../AGENTS.md) §目錄責任與資料邊界的 owner 切分；模組代號對應 [`sad.md`](../03_architecture/sad.md) 的 MOD-*。

### 2.1 MOD-SRV-API／MOD-SRV-STORE（owner：Bella；S1–S2、SX）

| ID | 需求（可觀察行為） | 上游 | 佐證 file:line | ACPT |
| :--- | :--- | :--- | :--- | :--- |
| FR-001 | `POST /api/projects` 建專案並回 `project_id/current_step/workflow/revision`；空名稱 422 `project_name_required` | DEC-002 | `main.py:1784-1797`；`project_store.py:146-166` | ACPT-001 |
| FR-002 | `GET /api/projects/{id}` 唯讀取回專案並強制 `Cache-Control: no-store`；不存在 404 `project_not_found` | DEC-002 | `main.py:1800-1803` | ACPT-001 |
| FR-003 | `PUT /api/projects/{id}/workflow` 以遞迴深合併寫入單一快照；步驟須在 `WORKFLOW_STEPS` 白名單、非物件 422、序列化 >2 MB 回 413 | DEC-002 | `main.py:1806-1867`；`project_store.py:18-25,220-225` | ACPT-002 |
| FR-004 | 樂觀鎖兩套：`expected_revision` 不符回 409 `project_revision_conflict`（附最新 project）；`replay_pending`+`base_updated_at` 失敗回裸字串 `project_version_conflict` | DEC-002 | `main.py:1828-1858`；`project_store.py:199-243` | ACPT-003 |
| FR-005 | `POST /api/projects/{id}/floorplan` 只收 `.dxf/.png/.jpg/.jpeg`（415）、拒空檔與壞圖（422），寫入 `uploads/<id>/floorplan<ext>` 並 revision+1 | DEC-003 | `main.py:153,1870-1916`；`project_store.py:275-297` | ACPT-004 |
| FR-006 | `GET /api/projects/{id}/floorplan/source` 回原始檔；未上傳 409 `floorplan_missing`、實體檔遺失 410 | DEC-003 | `main.py:1685-1707,1919-1926` | ACPT-005 |
| FR-007 | 第 4 步複核閘門：宣告 `space_confirmation` 完成時比對 `spatial_report.review_items` 與 `rooms[].confirmed`，任一未確認回 422 並附 `focus`／`rooms` | DEC-004 | `main.py:1737-1781,1815-1827` | ACPT-006 |
| FR-008 | 啟動時 `import_runtime()` 合流 legacy worktree 的執行資料：以 `updated_at` 決勝、上傳檔 `copy2`、render `INSERT OR IGNORE`、來源檔遺失保留現值 | DEC-002, DEC-015 | `project_store.py:433-561`；`main.py:147-149` | ACPT-007 |
| FR-009 | `POST /api/projects/{id}/renders` 收瀏覽器輸出 PNG（≤20 MB、PNG magic 檢查、`provider` 僅 `browser_capture`），並提供列表與下載 | DEC-001 | `main.py:163,1937-2025`；`project_store.py:349-416` | ACPT-008 |

### 2.2 MOD-FP／MOD-U3D（owner：Cody；S3）

| ID | 需求（可觀察行為） | 上游 | 佐證 file:line | ACPT |
| :--- | :--- | :--- | :--- | :--- |
| FR-010 | `POST /api/projects/{id}/floorplan/analyze`：DXF 走 `parse_floorplan_with_engine`（失敗 422 `dxf_parse_failed`）、影像走 `analyze_floorplan_image`（失敗 422 `cody_recognition_failed`） | DEC-004 | `main.py:2981-3069`；`scene_service.py:2758` | ACPT-009 |
| FR-011 | 辨識前置閘門：未勾「圖檔內容正確」回 409 `floorplan_confirmation_required` | DEC-004 | `main.py:2967-2993` | ACPT-009 |
| FR-012 | 影像辨識 11 步管線輸出 `layout_json`（`schema_version 1.0`、公分／左下原點／y 向上）；公分轉換是管線最後一步 | DEC-004 | `vision/analysis.py:438-677`；`vision/units.py:30-41` | ACPT-010 |
| FR-013 | 比例尺三來源（`manual_confirmation` 1.0／`dimension_ocr` OCR 分數／`cody_config`\|`cody_wall_min` 0.9\|0.7）；自動信心 <0.8 產生 issue `scale_confirmation_required` | DEC-004 | `analysis.py:476-544`；`cody_adapter.py:756,775-776` | ACPT-011 |
| FR-014 | 房型判定四層證據與固定覆蓋優先序：印刷房名／七格局 > DINOv2 語意 > 圖示「待確認」> 面積規則；語意層只能填空位或覆蓋 `furniture_icon_inference` | DEC-004 | `analysis.py:168-194,42-58` | ACPT-012 |
| FR-015 | 產生 `spatial_report`（逐房尺寸、信心分級 high≥0.8／medium≥0.6、四種 `review_items` reason、固定 assumptions）與 `requires_confirmation` 旗標 | DEC-004 | `vision/spatial_report.py:110-208` | ACPT-013 |
| FR-016 | 辨識成功後把 `confirmed_floorplan`／`calibration`／`space_confirmation`／`requirements`／`layout_2d`／`white_model_3d`／`realistic_3d` 全部重設為 null 並改寫 `_flow` | DEC-018 | `main.py:3036-3063` | ACPT-014 |
| FR-017 | DXF → 幾何 payload：牆線、牆體多邊形、門窗線段、`wall_solids`、`opening_geometry`（公尺、平面中心原點），另輸出 ×100 的公分 client 版線段 | DEC-003 | `dxf_parser.py:344-390`；`wall_openings.py:138-218` | ACPT-015 |

### 2.3 MOD-WEB（owner：Bella；S4、SX）

| ID | 需求（可觀察行為） | 上游 | 佐證 file:line | ACPT |
| :--- | :--- | :--- | :--- | :--- |
| FR-018 | 第 4 步結構編輯（房間節點、牆、門、窗、樑、柱）輸出 `floorplan_editor`（`coordinate_unit:"cm"`、`width_cm/depth_cm/room_height_cm`、`rooms[]`、`structures{}`） | DEC-004 | `scene_v2.js:2216-2241`；`scene_structure_geometry.js:212` | ACPT-016 |
| FR-019 | 已確認的門（`step4_confirmed`）在 3D 不切牆洞；開口依序取 `persisted_step4_wall_gap` → `confirmed_wall_gap` → `projected_wall_line` → `unresolved_closed_leaf` | DEC-004 | `scene_architecture.js:241-272`；`scene_viewer.js:1798-1801` | ACPT-017 |
| FR-020 | 內部 11 步狀態機對外折疊為 8 步導覽（`calibration→recognition`、`white_model_3d`\|`realistic_3d→layout_2d`） | DEC-001 | `scene_v2.js:311-322`；`main.py:164-176` | ACPT-018 |
| FR-021 | 前進條件 `REQUIRED_COMPLETIONS` 逐步檢查；`complete()` 自動作廢下游已完成步驟並刪其 data | DEC-018 | `scene_workflow.js:43-187`；`scene_v2.js:1376-1400` | ACPT-019 |
| FR-022 | 雙寫持久化：先寫 `localStorage` pending，再以序列化 Promise 串鏈呼叫 `PUT /workflow`（重試 3 次、180 ms×n 退避），離開前攔截未完成存檔；`base_updated_at` 相符才重播 | DEC-002 | `scene_v2.js:1285-1375,19255-19294`；`scene_workflow.js:32-41` | ACPT-020 |
| FR-023 | 2D 疊層與座標轉換：`viewBox` 對齊 `<img>` content rect、`planCmToLayerPixel` y 軸翻轉、footprint 最小 28 px | DEC-001 | `scene_v2.js:1935-1980`；`scene_layout2d.js:293-326` | ACPT-021 |
| FR-024 | 3D viewer 唯一場景入口 `loadScene`（兩層跳過鍵）；`updateRoomSurfaces` 只重建房殼、保留家具與 GLB clone；`getDiagnostics()` 是第 6→7 步硬閘 | DEC-008 | `scene_viewer.js:3843,4142-4216`；`scene_v2.js:13941-13973` | ACPT-022, ACPT-034 |
| FR-025 | 生圖疊層 `#ai-render-image-stage` 支援 `single`／`gallery` 兩模式；第 7 步色卡疊層 `#proposal-review-image-stage` 是獨立一套 | DEC-011 | `scene_v2.js:17418-17494`；`scene.html:911-966` | ACPT-023 |

### 2.4 MOD-SRV-SCENE／MOD-ENG（owner：Bella ＋ Ancai；S5–S6）

| ID | 需求（可觀察行為） | 上游 | 佐證 file:line | ACPT |
| :--- | :--- | :--- | :--- | :--- |
| FR-026 | `GET /api/questionnaire/visual-catalog`（可依 `space_type`／`ready_only` 篩）與 `GET /api/questionnaire/visual-images/{id}` 提供視覺題庫 | DEC-005 | `main.py:3195-3226`；`questionnaire_visuals.py:139-183` | ACPT-024 |
| FR-027 | 逐房需求模型 `room_requirements`（`schema_version 1.0`）由問卷產生，含用途、家具、面材、天花、複核五段 | DEC-005 | `scene_room_requirements.js:1-363` | ACPT-025 |
| FR-028 | 家電需求只寫入 `scene_json.render_context.appliance_requirements`，不進 `scene_objects` 與正式家具 API | DEC-006 | `scene_service.py:3043-3072`；`main.py:930-931` | ACPT-026 |
| FR-029 | `POST /api/scene/generate` 由問卷＋`layout_json`／`floorplan_editor` 產出 `scene_json`（含 `placement_variant`，非法值退回 A） | DEC-008 | `main.py:3591-3644`；`scene_service.py:2888-3088` | ACPT-027 |
| FR-030 | 逐房擺位：依 `placement_room_id`（其次 `auto_decor_room_id`）分組，每房各自在自己邊界內擺；無 id 者由 `ROOM_AFFINITY` 路由並回寫房號 | DEC-008 | `scene_service.py:1981-2052` | ACPT-028 |
| FR-031 | A／B 方案：`placement_variant` 只反轉類型錨點嘗試順序，B 走完全相同的碰撞與淨空驗證 | DEC-009 | `scene_service.py:2539-2545`；`main.py:3630-3632` | ACPT-029 |
| FR-032 | `POST /api/scene/layout` 重排或驗證；`validate_only:true` 絕不改座標只回報合法性；指定單房時他房 passthrough | DEC-008 | `main.py:3647-3709`；`scene_service.py:2169,2188-2191` | ACPT-030 |
| FR-033 | `POST /api/scene/validate` 驗單件拖曳落點，回 `{ok, reason}` | DEC-008 | `main.py:3998-4009`；`scene_service.py:2111` | ACPT-031 |
| FR-034 | 引擎七段固定順序檢查（出界→穿牆→本體重疊→淨空撞牆→淨空撞他人本體→淨空互撞→反向），只回報最先命中者，理由為繁體中文字串 | DEC-008 | `backend/engine/clearance.py:118-143` | ACPT-031 |
| FR-035 | 淨空常數：門前 75 cm、窗前 40 cm（家具高 ≥90 cm 才受窗帶限制）、有櫃家具正面 50 cm、背牆間距 5 cm、窗台 90 cm | DEC-008 | `engine/constraints.py:21-23`；`engine/clearance.py:24,33-37`；`engine/rules.py:15` | ACPT-032 |
| FR-036 | 移動與旋轉合法性：X／Y 軸分離（單軸受阻仍 `success=true` 且該軸不動），旋轉 `%360` 正規化、不合法即還原 | DEC-008 | `engine/adjustment.py:11-68` | ACPT-033 |
| FR-037 | 擺位失敗必須回報 `placement.failed[]`／`placement.unavailable_types[]`／`placement_resolution_report[]`；第二輪 `resolve_placements` 換小件或移除，但保護 `user_specified`／`user_required`／`position_locked` | DEC-008 | `scene_service.py:2951-2983`；`agent/place.py:155-308` | ACPT-034 |
| FR-038 | `POST /api/scene/decorate` 依風格加軟裝，座標仍由引擎決定；找不到有 GLB 的候選列入 `decor_summary.unavailable` 不中斷 | DEC-008 | `main.py:3755-3762,3799-3995` | ACPT-035 |

### 2.5 MOD-CAT／MOD-SQL（owner：Kai；S6）

| ID | 需求（可觀察行為） | 上游 | 佐證 file:line | ACPT |
| :--- | :--- | :--- | :--- | :--- |
| FR-039 | `GET /api/furniture` 分頁查詢與 facet（`style/group/type/q/color/material/size/has_model/detail`；`page≥1`、`page_size` 1–80） | DEC-007 | `main.py:3229-3279` | ACPT-036 |
| FR-040 | `GET /api/catalog/status` 揭露型錄供應者、GLB 與圖片 manifest、面材與色卡數，且不外洩連線設定 | DEC-007, DEC-017 | `main.py:3095-3146`；`postgres_repository.py:748-850` | ACPT-037 |
| FR-041 | provider 決策：`ROOMPILOT_CATALOG_PROVIDER ∈ {json,local,fallback}` → JSON，其餘（含未設）→ postgres；第 6 步以 view `roompilot.furniture_catalog_current` 為優先來源 | DEC-007 | `postgres_repository.py:18-20,199-204`；[`AGENTS.md`](../../AGENTS.md) §不可違反的契約 | ACPT-037 |
| FR-042 | GLB／圖片交付：`/model` 遠端 URL 走 307；`model.gltf`／`buffer.bin`／`images/{i}` 在 cloudfront 模式回 410；載入失敗以 fallback proxy 呈現並附中文原因 | DEC-007 | `main.py:4012-4048`；`scene_viewer.js:4224-4277` | ACPT-038 |
| FR-043 | 官方型錄匯入驗證：總數 8,675、四份 CSV 與 catalog ID 集合一致、每件恰 3 張角色圖（front／side／angle-45）、交易內核對筆數 | DEC-007 | `import_official_catalog_to_postgres.py:310-466` | ACPT-039 |
| FR-044 | 向量匯入驗證：`item_id` 屬 8,076 active、`embedded_text`／`text_hash` 與官方 JSON 一致、維度 1024、L2 norm ∈ [0.98, 1.02] | DEC-007, DEC-016 | `import_furniture_embeddings_to_postgres.py:190-244` | ACPT-039 |
| FR-045 | quarantine 規則：`unmatched_cloud_furniture`（1,514）與 `sf3d_legacy`（1,509）不得出現在任何家具 API 或場景，且不得替其猜測 `model_url` | DEC-007 | `tests/test_cloud_quarantine.py:23-40`；`backend/catalog/AGENTS.md:8-9` | ACPT-040 |

### 2.6 MOD-RAG（owner：Django；S5）

| ID | 需求（可觀察行為） | 上游 | 佐證 file:line | ACPT |
| :--- | :--- | :--- | :--- | :--- |
| FR-046 | `GET /api/rag/status` 回 10 種具名 blocker（`feature_disabled`、模型快取缺、向量表空、SQL function 缺、DB 不可用…），不載模型也不呼叫 LLM | DEC-016, DEC-017 | `rag/service.py:76-130`；`rag_api.py:164-166` | ACPT-041 |
| FR-047 | 檢索：SQL 硬篩（room_type／category／price／尺寸／role／size_class）取 top-50 → rerank → `0.60*rerank+0.20*style+0.10*mood+0.10*confidence` → 依 `item_id`／`duplicate_group` 去重 | DEC-016 | `rag_repository.py:131-164`；`ranking.py:114-154`；`service.py:408-427` | ACPT-042 |
| FR-048 | 非同步工作佇列：`POST /api/rag/search/jobs`（202）＋輪詢；上限 24 → 429 `rag_job_capacity_reached`；完成後保留 3600 秒，逾時 404 | DEC-016 | `rag_api.py:28-32,178-221` | ACPT-043 |
| FR-049 | 第 5 步以 `fast:true` 呼叫檢索，結果只把命中 id 排前面（不增不刪候選）；失敗降級 `unavailable` 不阻塞問卷 | DEC-016 | `scene_v2.js:857-912` | ACPT-042 |

### 2.7 MOD-AGT（owner：Yen；S5–S6、SX）

| ID | 需求（可觀察行為） | 上游 | 佐證 file:line | ACPT |
| :--- | :--- | :--- | :--- | :--- |
| FR-050 | `POST /api/agent/furniture/select` 為伺服器端選件閘門：LLM 選擇需通過本地白名單驗證，未通過整批降級 `local_rules`，回 `source/model/warnings/rooms[]` | DEC-007 | `main.py:3440-3501`；`agent/select.py:352-376` | ACPT-044 |
| FR-051 | 選件潛規則：房型基礎家具、客廳三件（沙發＋茶几＋電視櫃）、同房同族一款、成組副件需主件、房型適配白／黑名單、戶外品排除、每房上限 8 件 | DEC-007 | `agent/knowledge.py:56-198`；`select.py:139-349`；`scene_service.py:175-222` | ACPT-045 |
| FR-052 | 餐椅數量：單房路徑 `min(max(2, 入住人數), 桌子可坐數)`；多房路徑桌寬 ≥140 cm→4 張、否則 2 張（兩套邏輯並存，見 OPEN-39） | DEC-007 | `scene_service.py:190-260`；`select.py:303-349`；`knowledge.py:103-113` | ACPT-045 |
| FR-053 | Agent 並存管線由 `ROOMPILOT_AGENT_PIPELINE` 旗標保護（未設＝關閉，四支路由回 404），`/status` 永遠可查，且不改動第 6 步 live 路徑 | DEC-001 | `agent_pipeline_service.py:1-11,32-51`；`main.py:3504-3588` | ACPT-046 |
| FR-054 | `POST /api/agent/pipeline/reconcile` 對帳兩路徑：比家族覆蓋與合法性（不比座標），回 `consistent` 與雙方 `placed/failed/families` | DEC-001 | `agent_reconcile_service.py:77-141` | ACPT-046 |

### 2.8 MOD-SRV-RENDER（owner：Bella；S7–S8）

| ID | 需求（可觀察行為） | 上游 | 佐證 file:line | ACPT |
| :--- | :--- | :--- | :--- | :--- |
| FR-055 | 逐房鎖定相機（`position_cm`／`target_cm`／`fov_deg>0`）與 `master_view`，未齊備不得完成 `proposal_review` | DEC-010 | `scene_workflow.js:150-157`；`scene_v2.js:232-241` | ACPT-047 |
| FR-056 | `POST /api/projects/{id}/palette-renders` 對代表房產出色卡比較圖，每專案僅能成功一次（409 `palette_already_generated`），全失敗不鎖定可重試；base64 不入 workflow | DEC-010 | `main.py:2135-2221`；`ai_render_service.py:432-488` | ACPT-048 |
| FR-057 | 選定色卡後寫入 `design_choices.style_card_id` 與 `style_card`，並套 STYLE_PACK 轉為寫實場景 | DEC-010 | `scene_v2.js:14014-14032,14447-14461` | ACPT-049 |
| FR-058 | `POST /api/projects/{id}/ai-renders` 逐房生圖（執行緒池併發、順序對齊輸入），客廳額外一張 `full_render_night`；單房失敗只標 `status:"failed"`，夜景失敗只附 `night_notices` | DEC-011 | `main.py:2070-2132`；`ai_render_service.py:319-429` | ACPT-050 |
| FR-059 | 生圖提示詞由 `GenPicInfoTool` deterministic 組裝，不含任何尺寸數字；家電只在此進入畫面描述 | DEC-006, DEC-011 | `tools/genpic_info.py:42-93,194-248` | ACPT-051 |
| FR-060 | `POST /api/projects/{id}/ai-renders/{room_id}/edit` 逐房各一次改圖；額度用罄 409 `ai_edit_budget_exhausted`、未生成 409 `room_not_generated`、上游拒絕 502 `ai_edit_failed` | DEC-011 | `main.py:2224-2287`（與契約「整批一次」有落差，見 OPEN-16） | ACPT-052 |
| FR-061 | `POST /api/projects/{id}/design-manual` 產出九章設計手冊 PDF（LLM 不可用走 deterministic 底稿），`GET .../pdf` 下載；紀錄在但檔不在回 410 | DEC-012 | `main.py:2300-2350`；`design_manual_service.py:211-239` | ACPT-053 |
| FR-062 | `POST /api/projects/{id}/delivery-proposal` 產出品牌交付提案 PDF；排版引擎未安裝回 503 `delivery_engine_not_configured`（附安裝指引），失敗 502 | DEC-012, DEC-017 | `main.py:2378-2437`；`agent/skills/delivery/__init__.py:43-120` | ACPT-053 |
| FR-063 | `POST /api/projects/{id}/design-delivery` 產出成果包 JSON（`schema_version 1.1`、`artifact_type roompilot.web_design_delivery.v1`、六章），並依 `DELIVERY_SENSITIVE_KEYS` 脫敏 | DEC-012 | `main.py:2475-2491,2919-2964` | ACPT-054 |
| FR-064 | 工程概算：費率目錄每個 source 需 `url`＋`retrieved_on`、輸入需 `quantity_evidence`；查無費率或單位不符列入 `needs_quote` 且不猜價 | DEC-013 | `cost_estimation.py:20-107` | ACPT-055 |

### 2.9 MOD-OPS（owner：Bella 整合；SX）

| ID | 需求（可觀察行為） | 上游 | 佐證 file:line | ACPT |
| :--- | :--- | :--- | :--- | :--- |
| FR-065 | 一鍵安裝與啟動：建虛擬環境 → 安裝相依 → Playwright chromium → npm；`uvicorn backend.server.main:app --host 127.0.0.1 --port 8002` | DEC-014 | `install.ps1:41-79`；`install.sh:33-65`；`README.md:49` | ACPT-056 |
| FR-066 | Docker PostgreSQL 供應：`pgvector/pgvector:pg17`、`pg_isready` healthcheck、空 volume 首次自動還原 dump | DEC-007 | `docker-compose.yml:14-39` | ACPT-057 |
| FR-067 | 狀態端點群作為健康檢查替代（catalog／render-provider／ai-render／delivery-proposal／scene provider／agent pipeline／rag），皆不外洩金鑰、token 或伺服器檔案佈局 | DEC-014, DEC-017 | `main.py:2028,2064,2378,3144,3331,3504`；`rag_api.py:164` | ACPT-056 |

---

## 3. 非功能需求 (NFR)

> 量化指標與驗證方法同步維護在 [`sad.md`](../03_architecture/sad.md) 的非功能需求段與 [`test_plan.md`](../05_qa/test_plan.md)。
> **每條的數值來源都標在「數值來源」欄**；無程式碼或實測依據者一律標「待確認」，不得在下游文件寫成既成事實。

| ID | 類別 | 需求（含數值） | 數值來源 | 上游 | ACPT |
| :--- | :--- | :--- | :--- | :--- | :--- |
| NFR-001 | 容量 | 單一 workflow 快照序列化後 ≤ 2 MB，超過在交易內拋出、整筆不落地（413 `workflow_too_large`） | `project_store.py:11,223-225`；現場 728 筆最大 1,224,258 bytes（2026-08-12 唯讀查詢，佔上限 58%） | DEC-002 | ACPT-002 |
| NFR-002 | 容量 | 瀏覽器輸出 PNG ≤ 20 MB 且需通過 PNG magic 檢查，超過 413 `render_too_large` | `main.py:163,1937-1997` | DEC-001 | ACPT-008 |
| NFR-003 | 一致性 | 樂觀鎖：`expected_revision` 不符回 409 並附伺服器最新 project | `main.py:1848-1858`；**現況正式前端一般存檔不帶該欄位（等同 last-write-wins），見 `scene_v2.js:1294-1338` 與 OPEN-14** | DEC-002 | ACPT-003 |
| NFR-004 | 一致性 | 儲存原子性：每次寫入 `BEGIN IMMEDIATE` 先取寫鎖，`UPDATE … AND revision = ?` 二次防護；連線設 WAL ＋ `foreign_keys=ON` | `project_store.py:92-93,199-243` | DEC-002 | ACPT-003 |
| NFR-005 | 一致性 | 顯示字串防爆：`name/name_en/name_zh/name_zh_raw/label/title` 超過 512 字元時以 `normalized_type`／`furniture_id`／`id` 取代 | `project_store.py:40-74` | DEC-002 | ACPT-002 |
| NFR-006 | 容量 | 型錄分頁 `page ≥ 1`、`page_size` 1–80，越界回 422 | `main.py:3229-3279`；`postgres_repository.py:590` | DEC-007 | ACPT-036 |
| NFR-007 | 效能 | 型錄 DB 連線池 `DB_POOL_MIN=1`／`DB_POOL_MAX=8`／`DB_CONNECT_TIMEOUT=3`（秒）；缺驅動拋 `postgres_driver_unavailable` | `postgres_repository.py:211-260,233-234` | DEC-007 | ACPT-037 |
| NFR-008 | 可用性 | 型錄 DB 不可用時 `catalog_provider_status()` 回 `available=False` ＋ reason，Web 服務不整體停擺 | `postgres_repository.py:842-850` | DEC-017 | ACPT-037 |
| NFR-009 | 併發 | 檢索併發：單一 daemon worker 序列化、佇列上限 24（429）、完成後保留 3600 秒；工作狀態存行程記憶體，重啟即失 | `rag_api.py:28-32,121-137,186-191` | DEC-016 | ACPT-043 |
| NFR-010 | 可用性 | 檢索模型 offline-only（`local_files_only=True`），未快取直接 `RagDependencyError` → 503；常駐約 4.6 GB | `model_runtime.py:104-127`；`docs/contracts/POSTGRESQL_FURNITURE_RAG_RUNTIME.md:101-102` | DEC-017 | ACPT-041 |
| NFR-011 | 效能 | LLM 逾時：agent 側 `ROOMPILOT_AGENT_LLM_TIMEOUT` 預設 120 秒；第 6 步場景規劃另有一套 8 秒逾時與獨立呼叫碼 | `agent/llm.py:147-149`；`scene_service.py:351-403` | DEC-017 | ACPT-060 |
| NFR-012 | 可用性 | 生圖失敗政策（程式強制）：主模型最多 3 次 → fallback 模型再 3 次 → 拋 `GenPicFailure`；夜景失敗不擋日光初稿 | `genpic_agent.py:29-31,144-190`；`ai_render_service.py:412-413` | DEC-011, DEC-017 | ACPT-050 |
| NFR-013 | 效能 | PDF 產出：交付提案走 Chromium 子行程、逾時 180 秒、引擎缺席 503 附安裝指令；設計手冊走逐頁點陣 A4@150dpi（文字不可選取） | `agent/skills/delivery/__init__.py:43-56,273-300`；`tools/render_pdf.py:1-45` | DEC-012 | ACPT-053 |
| NFR-014 | 可用性 | 外部相依不可用一律以 HTTP 狀態碼表達：503（未設定／不可連線）、502（上游明確拒絕）、409（版本或額度衝突）；禁止假成功與靜默降級 | `main.py:2049-2057,2109-2116,2400-2408`；`docs/contracts/AI_RENDER_OPENROUTER_CONTRACT.md:41` | DEC-017 | ACPT-060 |
| NFR-015 | 精度 | 碰撞判定解析度＝網格格徑 5 cm，單軸最多 1200 格（超過自動放大格徑），牆線描粗厚度 12 cm | `backend/engine/raster.py:18-21` | DEC-008 | ACPT-031 |
| NFR-016 | 一致性 | 擺位決定性：`candidate_edges` 以 `(-length, mid.y, mid.x)` 完整 tie-break、多處 `+0.0` 消負零；唯一隨機來源是 `choose_furniture_items` 的 seeded top-14 抽樣 | `engine/rules.py:52`；`engine/obb.py:22-27`；`scene_service.py:623-629` | DEC-008 | ACPT-034 |
| NFR-017 | 一致性 | 單位契約：跨模組長度與座標一律公分、新欄位 `_cm`、面積 `_m2`、角度度數；相容欄位須同時帶 `coordinate_unit:"cm"` 與 schema version | [`AGENTS.md`](../../AGENTS.md) §不可違反的契約；`engine/models.py:9-12`；`engine/schema.py:18-32` | DEC-008 | ACPT-010, ACPT-015, ACPT-016 |
| NFR-018 | 併發 | 生圖與色卡走執行緒池（`max_workers` ＝房數）；檢索走單一 worker；agent 並存管線用單一全域鎖序列化所有專案 | `ai_render_service.py:423-429`；`rag_api.py:121-137`；`agent_pipeline_service.py:28-30` | DEC-011 | ACPT-046, ACPT-050 |
| NFR-019 | 安全 | Pilot 現況：全 app 無認證、無 CORS、無 rate limit（檢索佇列上限除外），唯一邊界是 `--host 127.0.0.1` — **是否為既定範圍待 DEC-014 核准** | `main.py:195-197`；`README.md:49` | DEC-014 | ACPT-056 |
| NFR-020 | 安全 | 秘密與個資保護：成果包依 `DELIVERY_SENSITIVE_KEYS` 脫敏、遠端渲染請求剝除 address／email／name／phone、狀態端點只回布林、檢索狀態移除 `cache_dir` | `main.py:2475-2491`；`render_service.py:52-61`；`rag/service.py:66` | DEC-014 | ACPT-054, ACPT-056 |
| NFR-021 | 效能 | 前端資產快取：GLB 頁面級 LRU 上限 48；面材貼圖以 `url｜usage｜repeat｜colorSpace` 為鍵且無淘汰策略；`scene.html` 的 `?v=sha256-<前12碼>` 必須等於實檔雜湊 | `scene_viewer.js:49-85,892-916`；`tests/test_scene_v2_contract.py:20-28` | DEC-001 | ACPT-022 |
| NFR-022 | 維運 | 執行資料無配額、無輪替、無備份腳本、無專案刪除 API；現場 `uploads/` 114 MB、`manuals/` 45 MB、`projects.sqlite3` 67 MB 持續成長 | `du -sh .runtime/*`（2026-08-12 實測）；`rg "unlink\|rmtree\|DELETE FROM" backend/server/*.py` 僅命中失敗回滾 | DEC-015 | ACPT-058 |
| NFR-023 | 一致性 | 執行環境版本：`requires-python >= 3.12`、安裝腳本釘 3.12；**實測虛擬環境為 Python 3.13.5，落差待收斂** | `pyproject.toml:5`；`install.ps1:43`；`.venv/pyvenv.cfg` | DEC-014 | ACPT-056 |
| NFR-024 | 可驗證性 | 可驗證性基準：`pytest -q` 實測 947 收集／35 failed／905 passed／7 skipped（其中 23 筆因本機未啟動 PostgreSQL）；無 CI、無覆蓋率、無 lint／type-check | 2026-08-12 實跑；`pyproject.toml:63-64`；無 `.github/` 目錄 | DEC-019 | ACPT-059 |
| NFR-025 | 效能／維運 | 生圖端到端耗時、色卡耗時、可支撐併發使用者數、備份頻率、保留天數——**目標值未定義**：repo 內既無實測數據亦無備份腳本，無法由程式碼推導 | **無來源（目標值未定義）**；待 DEC-015、DEC-019 核准後補 | DEC-015, DEC-019 | ACPT-058 |

---

## 4. 資料需求 (Data Requirements)

| 資料實體 | 存放位置／來源 | 保留政策 | 敏感等級 | 佐證 |
| :--- | :--- | :--- | :--- | :--- |
| 專案與八步狀態快照 | `.runtime/projects.sqlite3` 的 `projects.workflow_json` 單欄（單一快照，無版本歷史表、無事件流） | **無 TTL、無刪除 API、無備份腳本（待 DEC-015）** | 中：可能含業主自填名稱與需求描述 | `project_store.py:98-142,199-243` |
| 原始平面圖 | `.runtime/uploads/<project_id>/floorplan<ext>` | 固定檔名，重傳直接覆蓋，無歷史 | 中：住宅平面可識別具體物件 | `project_store.py:275-278` |
| 瀏覽器輸出 PNG | `.runtime/renders/<project_id>/`＋`render_outputs` 表 | 僅追加、不覆蓋歷史 | 低 | `project_store.py:349-416` |
| 設計手冊／交付提案 PDF ＋文案側車 JSON | `.runtime/manuals/<project_id>/` | 僅追加；重出手冊只覆蓋 workflow 內的中繼資料，舊 PDF 檔留著 | 中：含業主聯絡資訊時須走脫敏路徑 | `design_manual_service.py:227-228,261-262` |
| Agent 並存管線側寫 | `.runtime/agent_pipeline/<project_id>.json`（刻意不進 workflow blob） | 隨旗標啟用而生；無清理 | 低 | `agent_pipeline_service.py:8-11,54-60` |
| 問卷影像查詢索引 | `.runtime/indexes/questionnaire_visuals.sqlite3` | 每次 `sync()` 先清表重灌，可重建 | 低 | `questionnaire_visuals.py:139-183` |
| 正式家具型錄 | PostgreSQL view `roompilot.furniture_catalog_current`（本系統唯讀消費，寫入由匯入器負責） | 由匯入器交易式重建；基準 8,675 筆／active 8,076 | 低（無個資） | `postgres_repository.py:199-260`；`import_official_catalog_to_postgres.py:310-466` |
| 家具向量 | PostgreSQL pgvector 表，8,076 筆 × 1024 維、L2 normalized | 同上，隨匯入器重建 | 低 | `import_furniture_embeddings_to_postgres.py:190-244` |
| 隔離區資料 | `unmatched_cloud_furniture`（1,514）、`sf3d_legacy`（1,509） | **永不進 API 或場景**，且不得替其猜測 `model_url` | 低 | `tests/test_cloud_quarantine.py:23-40` |
| 檢索模型權重快取 | 本機模型快取目錄，常駐約 4.6 GB，offline-only | 由部署方預先取得；未快取直接 503，不在請求路徑下載 | 低 | `model_runtime.py:104-127` |

> 個資邊界：業主姓名／電話／Email 若出現在 workflow，於**兩處**被剝除——遠端渲染請求（`render_service.py:52-61`）與成果包輸出（`DELIVERY_SENSITIVE_KEYS`，`main.py:2475-2491`）。此外系統不主動蒐集帳號資料（現況無認證，見 NFR-019）。保留期限、備份與交還／刪除政策**待 DEC-015 核准**，詳見 [`deployment_and_operations.md`](../06_ops/deployment_and_operations.md) 與 [`runbook-runtime-storage-growth.md`](../06_ops/runbook-runtime-storage-growth.md)。

---

## 5. 外部介面 (External Interfaces)

| 介面 | 方向 | 協議 | 失敗語意（本系統對外表現） | 契約文件 |
| :--- | :--- | :--- | :--- | :--- |
| 使用者瀏覽器（正式前端 `backend/server/static/`） | 入 | HTTP／JSON ＋ 靜態資產 | 由各端點的 4xx／5xx 語意承接 | [`api_spec.md`](../04_design/api_spec.md)、[`ui_spec-step1-project.md`](../02_ux_ui/ui_spec-step1-project.md)–[`ui_spec-step8-ai-render.md`](../02_ux_ui/ui_spec-step8-ai-render.md) |
| OpenRouter（色卡、逐房生圖、改圖、文案 LLM） | 出 | HTTPS REST | 未設金鑰 503；上游拒絕 502；主模型 3 次＋fallback 3 次後拋 `GenPicFailure` | [`openapi-render-delivery-v1.yaml`](../04_design/openapi-render-delivery-v1.yaml)、[`ADR-009`](../03_architecture/adr/ADR-009-server-governed-ai-generation.md) |
| PostgreSQL `roompilot` schema（型錄 view ＋ pgvector） | 出 | TCP／連線池 1–8、連線逾時 3 秒 | `/api/catalog/status` 回 `available=false` ＋ reason，服務不整體停擺 | [`db_design.md`](../04_design/db_design.md)、[`ADR-005`](../03_architecture/adr/ADR-005-postgres-catalog-source-of-truth.md) |
| CloudFront（GLB 模型與型錄圖片） | 出 | HTTPS | `/model` 307 導向；`model.gltf`／`buffer.bin`／`images/{i}` 回 410；載入失敗以 fallback proxy 呈現並附中文原因 | [`runbook-glb-asset-missing.md`](../06_ops/runbook-glb-asset-missing.md) |
| 本機檢索模型權重（embedding ＋ reranker） | 出 | 本機檔案系統，offline-only | 未快取 → `RagDependencyError` → 503，具名 blocker | [`ADR-008`](../03_architecture/adr/ADR-008-rag-retrieval-only-offline-models.md)、[`runbook-rag-model-cache-missing.md`](../06_ops/runbook-rag-model-cache-missing.md) |
| PDF 排版引擎（Chromium 子行程） | 出 | 子行程呼叫，逾時 180 秒 | 未安裝 503 `delivery_engine_not_configured`（附安裝指引）；失敗 502 | [`runbook-delivery-pdf-engine-missing.md`](../06_ops/runbook-delivery-pdf-engine-missing.md) |
| Docker 化 PostgreSQL 供應 | 出 | `docker compose`，`pg_isready` healthcheck | 空 volume 首次啟動自動還原 dump；健康檢查未過即不對外服務 | [`deployment_and_operations.md`](../06_ops/deployment_and_operations.md) |

> 本系統**不提供**對外整合 API：全部 65 條路由皆由自家單頁前端消費，無 webhook、無訊息佇列、無第三方推播。無生產前端呼叫的端點是否退役，見 OPEN-03。

---

## 6. 使用案例 (Use Case Specification)

> 只展開三條「例外路徑會改變業務結果」的流程；其餘功能由 §2 的 FR ＋ [`prd.md`](./prd.md) 的 ACPT／SCN 承接，不另寫使用案例。

### UC-001: 辨識平面圖並通過人工複核

| 項目 | 內容 |
| :--- | :--- |
| **Actor** | 設計流程操作者（屋主或設計顧問） |
| **Preconditions** | 專案已建立且已上傳 `.dxf/.png/.jpg/.jpeg` 平面圖（FR-005） |
| **Main Flow** | 1. 勾選「圖檔內容正確」→ 2. 呼叫 analyze，依副檔名分流 DXF／影像管線（FR-010）→ 3. 產出 `layout_json` 與 `spatial_report`（FR-012、FR-015）→ 4. 逐房確認尺寸與房型 → 5. 宣告 `space_confirmation` 完成通過閘門（FR-007） |
| **Alternative Flow** | A1. 未勾選即辨識 → 409 `floorplan_confirmation_required`（FR-011）；A2. 辨識失敗 → 422 `cody_recognition_failed`／`dxf_parse_failed`，不寫入任何下游節點；A3. 比例信心 <0.8 → 產生 `scale_confirmation_required`，要求兩點手動標定（FR-013）；A4. 有旗標房未確認即宣告完成 → 422 並回傳待處理房清單（FR-007）；A5. 重跑辨識 → 七個下游節點重設為 null（FR-016） |
| **Postconditions** | `layout_json` 存在且座標為公分；下游步驟狀態與辨識結果一致 |
| **引用規則** | DEC-003、DEC-004、DEC-018（見 [`brd.md`](./brd.md)） |

### UC-002: 自動配置家具並處理擺不下

| 項目 | 內容 |
| :--- | :--- |
| **Actor** | 設計流程操作者 |
| **Preconditions** | 第 4 步空間與結構已確認；第 5 步問卷已完成（FR-027） |
| **Main Flow** | 1. 呼叫 `scene/generate` 產出 `scene_json`（FR-029）→ 2. 依 `placement_room_id` 逐房擺位（FR-030）→ 3. 引擎七段檢查裁決每個落點（FR-034、FR-035）→ 4. 使用者拖曳微調，每次落點回打 `scene/validate`（FR-033）→ 5. 前往第 7 步前以 `validate_only:true` 做整屋確認（FR-032） |
| **Alternative Flow** | A1. 某件擺不下 → 進 `placement.failed[]`／`unavailable_types[]`，第二輪 `resolve_placements` 換小件或移除，但保護 `user_specified`／`user_required`／`position_locked`（FR-037）；A2. 切換方案 B → 只反轉錨點嘗試順序，仍走同一套驗證（FR-031）；A3. 型錄 DB 不可用 → `/api/catalog/status` 誠實回 `available=false`（NFR-008）；A4. 候選無 GLB → 3D 顯示 fallback 替身並附中文原因（FR-042） |
| **Postconditions** | 每件家具座標皆由 `backend/engine/` 產出；待處理清單為空才可進第 7 步（FR-024） |
| **引用規則** | DEC-007、DEC-008、DEC-009、DEC-017 |

### UC-003: 產出逐房效果圖與交付物

| 項目 | 內容 |
| :--- | :--- |
| **Actor** | 設計流程操作者 |
| **Preconditions** | 每個房間相機三元組已鎖定且 `fov_deg>0`（FR-055）；色卡已選定（FR-057） |
| **Main Flow** | 1. 呼叫 `palette-renders` 對代表房出色卡比較圖（FR-056）→ 2. 選定色卡套 STYLE_PACK → 3. 呼叫 `ai-renders` 逐房併發生圖，客廳另出夜景（FR-058）→ 4. 需要時逐房改圖一次（FR-060）→ 5. 產出成果包 JSON／交付提案 PDF／設計手冊 PDF（FR-061–063）與工程概算（FR-064） |
| **Alternative Flow** | A1. 未設金鑰 → 503，且不回傳任何影像（NFR-014）；A2. 單房生圖失敗 → 只該房 `status:"failed"`，其餘照常交付；A3. 夜景失敗 → 只附 `night_notices`，不影響日光圖；A4. 色卡再次產生 → 409 `palette_already_generated`；全失敗則不鎖定、可重試；A5. 同房第二次改圖 → 409 `ai_edit_budget_exhausted`；A6. PDF 排版引擎缺席 → 503 附安裝指引；A7. 查無費率 → 該工項進 `needs_quote`，金額 null |
| **Postconditions** | 交付物內容依 `DELIVERY_SENSITIVE_KEYS` 脫敏；概算附 `disclaimer_zh` 與 `status:"concept_estimate"` |
| **引用規則** | DEC-010、DEC-011、DEC-012、DEC-013、DEC-017 |

---

## 7. 驗收標準對照 (Acceptance Criteria)

驗收條件內文（Given／When／Then）維護在 [`prd.md`](./prd.md) 的 ACPT 段，BDD 場景維護在 [`test_plan.md`](../05_qa/test_plan.md)；此處只維護對照與狀態，**不重寫內文**。

| 步 | ACPT | 對應 FR／NFR | 對應 SCN | 狀態 |
| :--- | :--- | :--- | :--- | :--- |
| S1 建立專案 | ACPT-001–003 | FR-001–004、NFR-001、NFR-003–005 | SCN-001–003 | 待驗證 |
| S2 上傳平面圖 | ACPT-004、ACPT-005、ACPT-015 | FR-005、FR-006、FR-017、NFR-002、NFR-017 | SCN-004、SCN-005、SCN-012 | 待驗證 |
| S3 確定尺寸 | ACPT-009–014 | FR-010–016 | SCN-006–009、SCN-011 | 待驗證 |
| S4 空間與結構 | ACPT-006、ACPT-016、ACPT-017 | FR-007、FR-018、FR-019 | SCN-010、SCN-013 | 待驗證（觸發條件見 OPEN-32） |
| S5 需求問卷 | ACPT-024–026、ACPT-041–043 | FR-026–028、FR-046–049、NFR-009、NFR-010 | SCN-014–016 | 待驗證 |
| S6 配置與預覽 | ACPT-027–040、ACPT-044、ACPT-045 | FR-029–045、FR-050–052、NFR-006–008、NFR-015、NFR-016 | SCN-017–025、SCN-040–042 | 待驗證 |
| S7 方案鎖定與視角 | ACPT-008、ACPT-047–049 | FR-009、FR-055–057、NFR-001、NFR-002、NFR-012 | SCN-026–028 | 待驗證 |
| S8 AI 渲染與成果包 | ACPT-050–055、ACPT-060 | FR-058–064、NFR-011–014、NFR-018、NFR-020 | SCN-029–034、SCN-037 | 待驗證 |
| SX 跨步 | ACPT-007、ACPT-018–023、ACPT-046、ACPT-056、ACPT-057 | FR-008、FR-020–025、FR-053、FR-054、FR-065–067、NFR-019、NFR-021、NFR-023、NFR-024 | SCN-035、SCN-036、SCN-038、SCN-039 | 待驗證 |
| SX 受阻 | ACPT-058、ACPT-059 | NFR-022、NFR-024、NFR-025 | 無（由 TC-058／TC-059 承接） | **受阻：待 DEC-015／DEC-019 核准後才有可驗對象** |

> ACPT-008、ACPT-039、ACPT-040、ACPT-046、ACPT-051、ACPT-058、ACPT-059 屬非使用者可觀察面（上傳端點、資料匯入基準、隔離區、旁路旗標、提示詞內容、維運政策、測試基準線），不另立 SCN，由對應 TC-* 承接。

---

## 8. 假設與待確認

> 以下項目**程式碼看不出答案**，一律標為待確認；下游文件引用時不得寫成既成事實，並須在 `requirements_tracker.xlsx` ②決策沿革留一列。

| ID | 待確認內容 | 影響的 FR／NFR | 目前可驗證的事實 | 承接處 |
| :--- | :--- | :--- | :--- | :--- |
| OPEN-25 | `README.md` 記載的分割模型融合（`floorseg.onnx`／`_fuse_with_seg`／`FP2DXF_SEG`）在本分支**不存在**，`models/` 目錄未建立；辨識精準 94%／召回 92%（21 張測資）是否仍成立、`FP2DXF_DEBUG` 是否也一併遺失 | FR-010、FR-012、NFR-024 | `floorplan2dxf.py` 全檔無 `_fuse_with_seg`；`backend/floorplan/models` 目錄不存在；94%／92% 的最後實跑時間與程式版本無法由 repo 確認 | [`test_plan.md`](../05_qa/test_plan.md)、[`deployment_and_operations.md`](../06_ops/deployment_and_operations.md) |
| OPEN-28 | 比例尺**兩套獨立邏輯**並存：`derive_door_scale`（外牆 15 cm 下限，門寬只作交叉檢核 70–110 cm→high）vs `floorplan2room.refine_scale`（單門 85 cm／雙門 175 cm／牆厚 17.5 cm 錨）。哪一套是規格權威？ | FR-013 | 兩份實作同時存在且推導方式不同；`analysis.py:476-544` 只消費前者的 confidence | [`lld.md`](../04_design/lld.md)、本文件 §2.2 |
| OPEN-39 | 選件規則**兩套並存**：多房走 `select.parse_selections`（同族一款、餐椅依桌寬 ≥140 cm→4 張）、單房走 `choose_furniture_items`（無同族去重、餐椅依入住人數）。是刻意分工還是歷史殘留？並存管線的 `skills/furniture.choose()` 缺全部潛規則 | FR-051、FR-052、FR-053 | `select.py:245-248`（`families_used` 檢查）與 `scene_service.py:190-260` 兩條路徑規則不同；ACPT-045 目前只覆蓋多房路徑，單房餐椅測試待建 | [`lld.md`](../04_design/lld.md)、[`ADR-011`](../03_architecture/adr/ADR-011-agent-pipeline-flag-isolation.md) |
| OPEN-43 | 檢索契約寫「第一版只供 `/rag` 驗證、**不接入八步流程**」，但第 5 步問卷已實際接入；向量筆數在契約之間有 8,076 與 7,958 兩個數字 | FR-049、FR-044、NFR-024 | `scene_v2.js:857-912` 確有第 5 步呼叫；`docs/contracts/POSTGRESQL_FURNITURE_EMBEDDINGS.md:9` 記 8,076，`QUESTIONNAIRE_RAG_HANDOFF.md:36-37` 驗收條件記 7,958 | [`ADR-008`](../03_architecture/adr/ADR-008-rag-retrieval-only-offline-models.md)、[`db_design.md`](../04_design/db_design.md) |

其他直接影響本文件條目、但由他份文件主責承接的待確認項（此處只記索引，不重複內文）：

- **DEC-014 未核准前，NFR-019 的安全邊界只能記為現況、不能記為規格**（OPEN-02，承接 [`sad.md`](../03_architecture/sad.md)、[`deployment_and_operations.md`](../06_ops/deployment_and_operations.md)）。
- **NFR-003**：前端一般存檔不帶 `expected_revision`（等同 last-write-wins）是取捨還是遺漏（OPEN-14，承接 [`ADR-004`](../03_architecture/adr/ADR-004-single-workflow-snapshot-sqlite.md)）。
- **FR-060**：改圖額度「整批一次」（契約）vs「逐房一次」（程式）哪份權威（OPEN-16，承接 [`api_spec.md`](../04_design/api_spec.md)）。
- **FR-041**：`main.py:919` 的 `== 8675` 與健康 view 實際 8,076 不一致；契約承諾的 503 `postgres_catalog_unavailable` 是否曾實作（OPEN-06，承接 [`ADR-005`](../03_architecture/adr/ADR-005-postgres-catalog-source-of-truth.md)、[`runbook-catalog-db-unavailable.md`](../06_ops/runbook-catalog-db-unavailable.md)）。
- **FR-061–063**：三份交付物誰是對客戶的正式主件（OPEN-10，承接 [`prd.md`](./prd.md)、[`UAT 計畫`](../05_qa/UAT_RoomPilot_Pilot_內部_2026-08-12.md)）。
- **FR-034／FR-035**：引擎雙路徑正面朝向慣例相反（+y vs −y）、`CLEARANCE_BY_TYPE` 與 `CLEARANCE_OF` 鍵值不同（OPEN-21、OPEN-22，承接 [`ADR-003`](../03_architecture/adr/ADR-003-dual-path-shapely-raster-engine.md)、[`lld.md`](../04_design/lld.md)）。
- **NFR-024**：pytest 35 筆紅燈應改 skip 還是把 PostgreSQL 列為必要前置（OPEN-46，承接 [`test_plan.md`](../05_qa/test_plan.md)）。

---

## 9. 追溯

### 9.1 上游與下游

| 項目 | ID／文件 |
| :--- | :--- |
| 上游 | [`brd.md`](./brd.md) 的 DEC-001..019 業務承諾、[`prd.md`](./prd.md) 的產品範圍與 ACPT-001..060 |
| 本文件產出 | 正式編號 FR-001..067、NFR-001..025、UC-001..003，以及 §1.2 的業務詞↔工程詞對照 |
| 下游 | [`sad.md`](../03_architecture/sad.md) 需求摘要與 ADR-001..012、[`lld.md`](../04_design/lld.md)、[`api_spec.md`](../04_design/api_spec.md) ＋ `openapi-*`、[`db_design.md`](../04_design/db_design.md)、[`test_plan.md`](../05_qa/test_plan.md)、[`UAT 計畫`](../05_qa/UAT_RoomPilot_Pilot_內部_2026-08-12.md)、[`deployment_and_operations.md`](../06_ops/deployment_and_operations.md) 與 `runbook-*`、`engineering_tracker.xlsx` ①規格追溯 |
| 需求決策權威 | [`requirements_tracker.xlsx`](../../VibeCoding_Workflow_Templates/01_requirements/requirements_tracker.xlsx) ①需求決策（DEC-*）與 ③Gate；本文件登記的 DEC-* **全部為待 owner 核准** |

### 9.2 DEC → FR/NFR → ACPT 完整矩陣（八步 × owner × 失效模式）

| 步 | DEC | FR | NFR | ACPT | SCN | ADR | MOD（owner） | TC | RB |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| S1 建立專案 | DEC-002 | FR-001–004 | NFR-001、003、004、005 | ACPT-001–003 | SCN-001–003 | ADR-004 | MOD-SRV-STORE（Bella） | TC-001–003 | RB-003 |
| S2 上傳平面圖 | DEC-003 | FR-005、006、017 | NFR-002、017 | ACPT-004、005、015 | SCN-004、005、012 | ADR-001、007 | MOD-SRV-STORE、MOD-U3D（Bella／Cody） | TC-004、005、015 | RB-009 |
| S3 確定尺寸 | DEC-004 | FR-010–016 | NFR-017 | ACPT-009–014 | SCN-006–009、011 | ADR-001 | MOD-FP（Cody） | TC-009–014 | RB-006 |
| S4 空間與結構 | DEC-004、018 | FR-007、018、019 | NFR-017 | ACPT-006、016、017 | SCN-010、013 | ADR-001 | MOD-WEB、MOD-SRV-API（Bella） | TC-006、016、017 | RB-006 |
| S5 需求問卷 | DEC-005、006、016 | FR-026–028、046–049 | NFR-009、010 | ACPT-024–026、041–043 | SCN-014–016 | ADR-006、008 | MOD-SRV-SCENE、MOD-RAG、MOD-AGT（Bella／Django／Yen） | TC-024–026、041–043 | RB-004 |
| S6 配置與預覽 | DEC-007、008、009 | FR-029–045、050–052 | NFR-006–008、015、016 | ACPT-027–040、044、045 | SCN-017–025、040–042 | ADR-002、003、005 | MOD-ENG、MOD-CAT、MOD-SQL、MOD-AGT、MOD-SRV-SCENE（Ancai／Kai／Yen／Bella） | TC-027–040、044、045 | RB-001、007、008 |
| S7 方案鎖定與視角 | DEC-010 | FR-009、055–057 | NFR-001、002、012 | ACPT-008、047–049 | SCN-026–028 | ADR-009 | MOD-SRV-RENDER、MOD-WEB（Bella） | TC-008、047–049 | RB-002 |
| S8 AI 渲染與成果包 | DEC-011、012、013 | FR-058–064 | NFR-011–014、018、020 | ACPT-050–055、060 | SCN-029–034、037 | ADR-006、009 | MOD-SRV-RENDER、MOD-AGT（Bella／Yen） | TC-050–055、060 | RB-002、005 |
| SX 跨步 | DEC-001、014、015、017、018、019 | FR-008、020–025、053、054、065–067 | NFR-019、021–025 | ACPT-007、018–023、046、056–059 | SCN-035、036、038、039 | ADR-010、011、012 | MOD-WEB、MOD-OPS、MOD-TEST（Bella／各 owner） | TC-007、018–023、046、056–059 | RB-003、009 |

**孤兒檢查**：DEC-001..019 全部至少對到 1 條 FR 或 NFR（DEC-019 只對到 NFR-024／NFR-025，屬預期）；FR-001..067 與 NFR-001..025 全部出現在 §2／§3 的 ACPT 欄；ACPT-001..060 全部在 §7 被引用。
