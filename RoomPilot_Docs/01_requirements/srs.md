# 軟體需求規格書 (SRS) - RoomPilot

> **版本:** 0.1 | **更新:** 2026-08-11 | **狀態:** 草稿
> **Owner:** Bella（`backend/server/` 與 `backend/server/static/` 跨模組整合，依 `AGENTS.md:32-46`）；各模組 owner（Cody/Django/Kai/Yen/Ancai）與 QA 共同審閱
> **語域:** L2（橋接：每條需求業務詞與工程詞並列，綁 REQ-* → FR/NFR-* → ACPT-* 對照）
> **實例:** 單例（整個系統一份）
> **定位宣告:** 本文件回答「RoomPilot 的正式功能／非功能需求、資料與外部介面、驗收對照是什麼」；業務目標見 [`brd.md`](./brd.md)，使用者故事與 ACPT 全文見 [`prd.md`](./prd.md)，架構論述見 [`../03_architecture/sad.md`](../03_architecture/sad.md)。所有 ID 沿用 [`../00-registry.md`](../00-registry.md)。
> **生成:** AI 由程式碼與文件衍生｜來源版本 git yen@8863a36c

---

## 目錄

- [1. 功能需求 (Functional Requirements)](#1-功能需求-functional-requirements)
- [2. 非功能需求 (NFR)](#2-非功能需求-nfr)
- [3. 資料需求 (Data Requirements)](#3-資料需求-data-requirements)
- [4. 外部介面 (External Interfaces)](#4-外部介面-external-interfaces)
- [5. 使用案例 (Use Case Specification)](#5-使用案例-use-case-specification)
- [6. 驗收標準 (Acceptance Criteria)](#6-驗收標準-acceptance-criteria)
- [7. 待確認](#7-待確認)
- [8. 追溯](#8-追溯)

## 1. 功能需求 (Functional Requirements)

每列格式：業務描述（L1 詞彙）——工程對應（L3 詞彙＋證據）。優先級全數「待核准」（見 §7 第 1 條）。

| ID | 需求描述（業務——工程） | 來源 | 優先級 | 驗收標準 ID |
| :--- | :--- | :--- | :--- | :--- |
| FR-001 | 專案可保存並跨瀏覽器工作階段恢復——ProjectStore 以 workflow JSON 深合併保存（`PUT /api/projects/{id}/workflow`，main.py:1806；`_merge_dict`，project_store.py:18），`GET /api/projects/{id}` 還原到 `current_step` | REQ-001 | 待核准 | ACPT-001 |
| FR-002 | 上傳平面圖後系統自動辨識牆/門/窗/房間——analyze API 回 `analysis`＋`layout_json`（main.py:2981、4106-4146），layout_json 不含設計決策 | REQ-002 | 待核准 | ACPT-002 |
| FR-003 | 兩點標定把圖面換算為實際公分尺度——前端 `scene_calibration.js` 計算，結果隨 workflow JSON 保存（01-product §2 步 3） | REQ-003 | 待核准 | ACPT-003 |
| FR-004 | 人工校正結構後確認鎖定——`POST /api/floorplan/confirm` 套用修正回 layout_json（main.py:4149-4159）；改結構須回第 4 步（README:154-155） | REQ-004 | 待核准 | ACPT-004 |
| FR-005 | 逐房問卷訪談收集需求與家電——Agent intake（`/api/agent/intake/start\|answer`，main.py:3336、3343）＋問卷視覺題庫（main.py:3195），產出 client_brief（schema 1.1） | REQ-005 | 待核准 | ACPT-005 |
| FR-006 | 一鍵產生 A/B 兩套家具方案——`POST /api/scene/generate` 帶 `placement_variant`，B 反轉錨點嘗試順序（main.py:3630-3639、scene_service.py:2539-2545） | REQ-006 | 待核准 | ACPT-006 |
| FR-007 | 拖曳家具即時判斷放不放得下——`/api/scene/layout`（重排／validate_only）與 `/api/scene/validate`（落點驗證）由引擎裁決（main.py:3647-3709、3998） | REQ-007 | 待核准 | ACPT-007、ACPT-008 |
| FR-008 | 材質與風格軟裝微調——材質走 `whiteViewer.updateRoomSurfaces`（scene_v2.js:14049）、軟裝走 `/api/scene/decorate`（main.py:3799），座標仍由引擎決定 | REQ-008 | 待核准 | ACPT-016 |
| FR-009 | 第 7 步鎖定視角供生圖參考——3D 截圖上傳 `POST /api/projects/{id}/renders`（main.py:1937、scene.html:943），帶 `viewpoint_version` | REQ-009 | 待核准 | ACPT-016 |
| FR-010 | 代表房色卡比較圖一次性生成——`POST /api/projects/{id}/palette-renders`，重複請求回 409（main.py:2135-2140） | REQ-010 | 待核准 | ACPT-009 |
| FR-011 | 逐房 AI 寫實生圖＋每房一次改圖——`POST .../ai-renders` 與 `/ai-renders/{room_id}/edit`，額度用完回 409（main.py:2070、2224） | REQ-011 | 待核准 | ACPT-010 |
| FR-012 | 交付成果包（提案 PDF／設計手冊／工程估價）——delivery-proposal（main.py:2384，需 Playwright Chromium）、design-delivery（main.py:2947）、design-manual（main.py:2300，非正式版）、`POST /api/cost/estimate`（main.py:4162） | REQ-012 | 待核准 | ACPT-011 |
| FR-013 | 家具只來自官方已驗證目錄——`GET /api/furniture` 走 PostgreSQL view `roompilot.furniture_catalog_current`，含分頁/風格/分組過濾（main.py:3229、postgres_repository.py:590-637） | REQ-013 | 待核准 | ACPT-012 |
| FR-014 | 家電需求只影響生圖不進擺設——問卷家電寫入 `scene_json.render_context.appliance_requirements`（scene_service.py:3058-3062），精選時家電類型跳過（scene_service.py:715-740） | REQ-014 | 待核准 | ACPT-013 |
| FR-015 | Agent 並存管線（HITL）——start/submit/undo/status/reconcile（main.py:3504-3575），需 `ROOMPILOT_AGENT_PIPELINE` flag，不取代正式 step6 | （橫切） | 待核准 | ACPT-015 |

## 2. 非功能需求 (NFR)

量化指標與驗證方法維護在本表與 [`../03_architecture/sad.md`](../03_architecture/sad.md) §2；獨立 NFR 文件依需增建。

| ID | 類別 | 適用範圍（業務——工程） |
| :--- | :--- | :--- |
| NFR-001 | 互通性 | 尺寸永遠是實際公分——跨模組長度/座標一律 `_cm`，payload 帶 `coordinate_unit: "cm"`，角度用度數（AGENTS.md:50-51、scene_service.py:3020） |
| NFR-002 | 可靠性 | 工作不因關瀏覽器而遺失——workflow JSON 單一快照 ≤2MB（project_store.py:12）＋revision 樂觀鎖，落後回 409（project_store.py:28-33） |
| NFR-003 | 資料一致性 | 家具資料以資料庫為準、失敗要看得見——預設 PostgreSQL，回滿 8,675 筆才採用；不悄悄回退 JSON，僅 `.env` 明確設定才用離線資料（main.py:909-926、README:299-304） |
| NFR-004 | 正確性（單一權威） | 家具放得合不合法只有一個裁判——碰撞、淨空、超界只由 `backend/engine/` 計算；RAG/LLM/前端不決定幾何（AGENTS.md:53、scene_service.py:2228-2230） |
| NFR-005 | 資料品質 | 未驗證家具不會出現在產品裡——quarantine 與 inactive（599 件）不進正式 API、RAG 與場景（backend/catalog/AGENTS.md:6-8、README:282） |
| NFR-006 | 可測試性 | 測試不依賴外網與外部資產——預設決定論、離線；外部 DB/網路顯式 opt-in 或安全 skip（tests/AGENTS.md） |

## 3. 資料需求 (Data Requirements)

保留政策與敏感等級均無專案證據（見 §7 第 3 條）。

| 資料實體 | 來源系統 | 保留政策 | 敏感等級 |
| :--- | :--- | :--- | :--- |
| 專案與工作流快照（`projects` 表：`workflow_json`≤2MB、`revision`、`current_step`） | 本系統 SQLite `.runtime/projects.sqlite3`（project_store.py:77-113） | 待確認 | 待確認 |
| 上傳平面圖檔（PNG/JPG/DXF） | 本系統 `.runtime/uploads/`（main.py:1870） | 待確認 | 待確認 |
| 渲染輸出（3D 截圖、色卡圖、AI 生圖、PDF） | 本系統 `.runtime/renders/`＋`render_outputs` 表（project_store.py:122-140） | 待確認 | 待確認 |
| 家具目錄（8,675 件官方 catalog，active 8,076） | Kai PostgreSQL view `roompilot.furniture_catalog_current`（docs/contracts/README.md 基準） | 待確認 | 公開商品資料（待確認） |
| 隔離區家具（quarantine／inactive 599 件） | `backend/catalog/data/quarantine/`；禁止進 API 與場景（AGENTS.md:57） | 待確認 | 待確認 |

## 4. 外部介面 (External Interfaces)

本系統自身 REST 介面全文見 [`../04_design/api_spec.md`](../04_design/api_spec.md)。

| 介面 | 方向 | 協議 | 契約文件 |
| :--- | :--- | :--- | :--- |
| PostgreSQL（家具 catalog read model） | 入（讀） | SQL | `docs/contracts/POSTGRESQL_CATALOG_READ_PHASE1.md` |
| OpenRouter（第 8 步生圖 nano banana＋LLM） | 出 | REST | `docs/contracts/AI_RENDER_OPENROUTER_CONTRACT.md` |
| CloudFront（家具 GLB 與三視角圖，307 redirect，main.py:4012） | 出 | HTTPS | `docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md` |
| 遠端渲染商（render-jobs，202 非同步） | 出 | REST | `docs/contracts/REMOTE_RENDER_CONTRACT.md` |
| Playwright Chromium（交付提案 PDF 引擎；缺時回 503 `delivery_engine_not_configured`） | 本機依賴 | — | main.py:2384、README:111-117 |

## 5. 使用案例 (Use Case Specification)

Pilot 階段不另編 UC-* 編號；關鍵流程以登錄簿 SCN-001～SCN-010 承載（[`../00-registry.md`](../00-registry.md) §2.4）。以下展開兩條代表性主鏈。

### 5.1 SCN-002: 上傳 → 辨識 → 校正 → 確認 layout_json

| 項目 | 內容 |
| :--- | :--- |
| **Actor** | 使用者／設計師 |
| **Preconditions** | 已建立專案（`POST /api/projects`，main.py:1784） |
| **Main Flow** | 1. 上傳平面圖（main.py:1870） 2. 辨識回 `analysis`＋`layout_json`（main.py:2981） 3. 兩點標定換算公分 4. 人工校正牆/門/窗並確認（main.py:4149-4159），layout_json 鎖定 |
| **Alternative Flow** | A1. 未先確認 floorplan 就辨識 → 409（main.py:3064-3067）；A2. 確認後再改結構 → 強制回第 4 步並重新驗證家具（README:154-155） |
| **Postconditions** | workflow JSON 含鎖定的 layout_json；layout_json 只描述空間、不含家具/材質（LAYOUT_SCENE_BOUNDARY_CONTRACT.md:16-34） |
| **引用規則** | NFR-001（公分制）、FR-002～FR-004 |

### 5.2 SCN-007: 鎖定視角 → 逐房生圖 → 一次改圖 → 成果包

| 項目 | 內容 |
| :--- | :--- |
| **Actor** | 使用者／設計師 |
| **Preconditions** | 第 6 步 scene_json 已確認且無阻擋問題（README:154-155） |
| **Main Flow** | 1. 第 7 步逐房鎖定視角＋3D 截圖上傳（main.py:1937） 2. 色卡比較圖（main.py:2135） 3. 第 8 步逐房 AI 生圖（main.py:2070） 4. 需要時每房一次改圖（main.py:2224） 5. 產出交付提案 PDF 與工程估價（main.py:2384、4162） |
| **Alternative Flow** | A1. 色卡已生成 → 409 `palette_already_generated`；A2. 改圖額度用完 → 409；A3. 缺 Playwright Chromium → 503 附安裝指引 |
| **Postconditions** | 渲染檔存 `.runtime/renders/`＋`render_outputs` 表；成果包五章 JSON（schema_version 1.1，main.py:2921） |
| **引用規則** | FR-009～FR-012、REQ-014（家電僅入生圖 context） |

## 6. 驗收標準 (Acceptance Criteria)

AC 全文（Given/When/Then）落在 [`prd.md`](./prd.md) 的 ACPT 段；此處維護 FR ↔ ACPT ↔ SCN 對照。狀態全數待驗證。

| ACPT ID | 對應 FR/NFR | Scenario（SCN-*） | 狀態 |
| :--- | :--- | :--- | :--- |
| ACPT-001 | FR-001、NFR-002 | SCN-001 | 待驗證 |
| ACPT-002 | FR-002 | SCN-002 | 待驗證 |
| ACPT-003 | FR-003、NFR-001 | SCN-002 | 待驗證 |
| ACPT-004 | FR-004 | SCN-002 | 待驗證 |
| ACPT-005 | FR-005 | SCN-008 | 待驗證 |
| ACPT-006 | FR-006、NFR-004 | SCN-003 | 待驗證 |
| ACPT-007 | FR-007、NFR-004 | SCN-004 | 待驗證 |
| ACPT-008 | FR-007、NFR-004 | SCN-005 | 待驗證 |
| ACPT-009 | FR-010 | SCN-007 | 待驗證 |
| ACPT-010 | FR-011 | SCN-007 | 待驗證 |
| ACPT-011 | FR-012 | SCN-007 | 待驗證 |
| ACPT-012 | FR-013、NFR-003、NFR-005 | SCN-006 | 待驗證 |
| ACPT-013 | FR-014 | SCN-008 | 待驗證 |
| ACPT-014 | FR-001、NFR-002 | SCN-009 | 待驗證 |
| ACPT-015 | FR-015 | SCN-010 | 待驗證 |
| ACPT-016 | FR-008、FR-009、NFR-006 | SCN-005、SCN-007、SCN-010 | 待驗證 |

## 7. 待確認

1. **FR 優先級**未經 `requirements_tracker.xlsx` ①需求決策 owner 核准，本表暫全標「待核准」（登錄簿 §7 同註）。
2. **保存機制口徑分歧**：Phase 3 契約稱 project/workflow 已搬 PostgreSQL JSONB（POSTGRESQL_PROJECT_STORE_PHASE3.md），但 yen 分支程式實際使用 SQLite ProjectStore（main.py:147、project_store.py:77-84），且 repo 缺 migration 腳本；本文件 §3 以程式現況（SQLite）為準。
3. **資料保留政策與敏感等級**：repo 內無任何保留年限或個資分級的文件證據，§3 兩欄全數待確認。
4. **待實作契約**：`STEP4_WALL_EDITING_CONTRACT.md`（第 4 步畫牆/門洞欄位）與 `QUESTIONNAIRE_STYLE_MATERIAL_GENERATIVE_SPACE_CONTRACT.md`（layout schema 2.0、`polygon_cm`）均標示待實作，未列入本 SRS 的正式 FR。
5. **design-manual 定位**：`POST .../design-manual` 為非正式版、UI 不觸發（AI_RENDER_OPENROUTER_CONTRACT.md:207-208）；FR-012 的正式交付以 delivery-proposal 與 design-delivery 為準。

## 8. 追溯

| 項目 | ID |
| :--- | :--- |
| 上游 | [`../00-registry.md`](../00-registry.md) §2（REQ-001～REQ-014）；[`prd.md`](./prd.md) US-*／ACPT-* 全文；事實檔 01-product／02-api／03-engine（git yen@8863a36c） |
| 本文件產出 | FR-001～FR-015、NFR-001～NFR-006 正式規格化；SCN-002／SCN-007 使用案例展開；§6 ACPT 對照表 |
| 下游 | [`../03_architecture/sad.md`](../03_architecture/sad.md) §4 需求摘要；[`../05_qa/test_plan.md`](../05_qa/test_plan.md)；`engineering_tracker.xlsx` ①規格追溯 |
