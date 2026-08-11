# 文件登錄簿 (Document Registry) - RoomPilot

> **版本:** 1.0 | **更新:** 2026-08-11 | **狀態:** 活躍
> **Owner:** 文件系統（AI 衍生，人工核准前為 TO-BE）
> **語域:** L2（橋接：業務詞與工程詞並列）
> **實例:** 單例——整套文件共用的唯一 ID 真相源
> **定位宣告:** 本文件回答「這套文件的穩定 ID 骨幹、ADR/runbook 清單、術語對照與輸出檔案計畫是什麼」；不包含需求細節（見 prd/srs）、架構論述（見 sad/ADR-*）與操作步驟（見 runbook-*）。

## 目錄

- [1. 專案資訊](#1-專案資訊)
- [2. 穩定 ID 骨幹](#2-穩定-id-骨幹)
- [3. ADR 清單](#3-adr-清單)
- [4. Runbook 症狀清單](#4-runbook-症狀清單)
- [5. 術語表](#5-術語表)
- [6. 輸出檔案計畫](#6-輸出檔案計畫)
- [7. 追溯](#7-追溯)

## 1. 專案資訊

| 欄位 | 值 |
|---|---|
| 專案名稱 | RoomPilot（AIPE03 第四組 AI 室內設計系統） |
| 階段 | Pilot |
| 來源版本 | git `yen`@`8863a36c` |
| 生成日期 | 2026-08-11 |
| 生成方式 | AI 由程式碼與現有文件衍生（事實檔 `01-product.md`、`02-api.md`、`03-engine.md`、`04-frontend.md`、`05-data.md`、`06-ops.md`），人工核准前所有內容視為 TO-BE |

## 2. 穩定 ID 骨幹

### 2.1 REQ（業務需求）

| ID | 一行標題 | 證據 |
|---|---|---|
| REQ-001 | 專案可建立、保存並跨瀏覽器工作階段恢復，八步進度不遺失 | 01-product §5 |
| REQ-002 | 上傳 PNG/JPG/DXF 平面圖並自動辨識牆/門/窗/房間與信心度 | 01-product §2 步 2 |
| REQ-003 | 兩點標定把平面圖換算為公分尺度 | 01-product §2 步 3 |
| REQ-004 | 人工校正結構並確認，產出鎖定的 layout_json；改結構須回第 4 步 | 01-product §2 步 4 |
| REQ-005 | 逐房問卷收集需求、家電需求與三張風格色卡選擇 | 01-product §2 步 5 |
| REQ-006 | 依 layout_json＋需求＋catalog 自動產生方案 A/B 家具配置（scene_json） | 03-engine §5 |
| REQ-007 | 2D/3D 同步編輯家具；碰撞、淨空、超界問題阻擋下一步 | 01-product §2 步 6、README:154-155 |
| REQ-008 | 材質、天花、燈光微調與 3D 走動預覽 | 04-frontend §5 |
| REQ-009 | 鎖定方案與逐房生成視角，供第 8 步生圖參考 | 01-product §2 步 7 |
| REQ-010 | 第 7 步代表房色卡低解析比較圖，每專案只能成功一次 | 02-api main.py:2135-2140 |
| REQ-011 | 第 8 步逐房 AI 寫實生圖，每房一次改圖額度，客廳另有夜間圖 | 04-frontend §7 |
| REQ-012 | 交付成果包：交付提案 PDF、設計手冊、工程報告與台灣行情估價 | 02-api §1.6 |
| REQ-013 | 家具只來自 8,675 件已驗證官方 catalog，含 CloudFront GLB 與三視角圖 | 05-data §3、§5 |
| REQ-014 | 家電需求只影響第 8 步生圖，不出現在 2D/3D 擺設 | AGENTS.md:56、scene_service.py:715-740 |

### 2.2 FR / NFR（功能／非功能需求）

| ID | 一行標題 | 證據 |
|---|---|---|
| FR-001 | ProjectStore：workflow JSON 深合併保存與 `GET /api/projects/{id}` 恢復 | main.py:1806、project_store.py:18 |
| FR-002 | 平面圖辨識 API 產出 analysis＋layout_json | main.py:2981、4106-4146 |
| FR-003 | 前端 `scene_calibration.js` 兩點標定，結果隨 workflow JSON 保存 | 01-product §2 步 3 |
| FR-004 | `POST /api/floorplan/confirm` 套用人工修正並回 layout_json | main.py:4149-4159 |
| FR-005 | Agent intake 訪談（`/api/agent/intake/start|answer`）＋問卷視覺題庫 | main.py:3336、3343、3195 |
| FR-006 | `POST /api/scene/generate` 支援 `placement_variant` A/B（B 反轉錨點嘗試順序） | main.py:3630-3639、scene_service.py:2539-2545 |
| FR-007 | `/api/scene/layout`（重排／validate_only）與 `/api/scene/validate`（拖曳落點）由引擎裁決 | main.py:3647-3709、3998 |
| FR-008 | 材質套用走 `whiteViewer.updateRoomSurfaces`；風格軟裝走 `/api/scene/decorate` | scene_v2.js:14049、main.py:3799 |
| FR-009 | 第 7 步鎖定視角＋3D 截圖上傳 `POST /api/projects/{id}/renders` | main.py:1937、scene.html:943 |
| FR-010 | `POST /api/projects/{id}/palette-renders`，重複生成回 409 | main.py:2135-2140 |
| FR-011 | `POST /api/projects/{id}/ai-renders` 與 `/ai-renders/{room_id}/edit`（額度用完 409） | main.py:2070、2224 |
| FR-012 | delivery-proposal／design-delivery／design-manual PDF 與 `POST /api/cost/estimate` | main.py:2384、2947、2300、4162 |
| FR-013 | `GET /api/furniture` 走 PostgreSQL view，含分頁/風格/分組過濾 | main.py:3229、postgres_repository.py:590-637 |
| FR-014 | 問卷家電進 `scene_json.render_context.appliance_requirements` | scene_service.py:3058-3062 |
| FR-015 | MasterAgent 並存管線：start/submit/undo/status/reconcile（HITL） | main.py:3504-3575 |
| NFR-001 | 公分制契約：跨模組長度/座標一律 `_cm`，payload 帶 `coordinate_unit: "cm"`；角度用度數 | AGENTS.md:50-51、scene_service.py:3020 |
| NFR-002 | 可恢復保存：workflow JSON 單一快照 ≤2MB＋revision 樂觀鎖（落後回 409） | project_store.py:12、28-33 |
| NFR-003 | catalog 優先序：預設 PostgreSQL，須回滿 8,675 筆才採用；DB 失敗必須可見，只有明確設定才走 JSON | main.py:909-926、README:299-304 |
| NFR-004 | 幾何合法性單一權威：家具座標、碰撞、淨空只由 `backend/engine/` 計算；RAG/LLM/前端不決定幾何 | AGENTS.md:53、scene_service.py:2228-2230 |
| NFR-005 | quarantine 與 inactive（599 件）資料不進正式 API、RAG 與場景 | backend/catalog/AGENTS.md:6-8、README:282 |
| NFR-006 | 測試預設決定論、離線；外部資產/DB/網路顯式 opt-in 或安全 skip | tests/AGENTS.md |

### 2.3 ACPT（驗收條件）

| ID | 一行標題 |
|---|---|
| ACPT-001 | 重開瀏覽器後 `GET /api/projects/{id}` 還原到 `current_step`，原圖與渲染圖可重取 |
| ACPT-002 | 上傳平面圖後 analyze 回應含 `analysis`＋`layout_json`，且 layout_json 不含家具/材質欄位 |
| ACPT-003 | 兩點標定後所有下游幾何欄位為公分（`_cm`） |
| ACPT-004 | 第 4 步確認後結構鎖定；改結構強制回第 4 步並重新驗證家具 |
| ACPT-005 | 問卷完成後 client_brief（schema 1.1）含硬/軟需求與家電三分流 |
| ACPT-006 | 同一輸入下方案 B 與方案 A 的家具擺設不同（placement_variant 生效） |
| ACPT-007 | 拖曳家具到門前 75cm 淨空、窗前採光帶（高 ≥90cm）或房外時被拒且有分流訊息 |
| ACPT-008 | `validate_only=true` 時每件座標照舊、絕不重排，只回報合法與否 |
| ACPT-009 | 色卡比較圖每專案僅一次，二次請求回 409 `palette_already_generated` |
| ACPT-010 | 每房改圖僅一次額度，超過回 409 |
| ACPT-011 | 缺 Playwright Chromium 時交付提案回 503 附安裝指引，不產出殘缺 PDF |
| ACPT-012 | postgres 模式回傳不足 8,675 筆時不採用 DB 結果，且失敗狀態可由 `/api/catalog/status` 查見 |
| ACPT-013 | `scene_objects` 不含任何家電；家電僅存在於 `render_context.appliance_requirements` |
| ACPT-014 | 兩分頁同時保存時，落後的 revision 收到 409 `project_revision_conflict`，不覆寫他人變更 |
| ACPT-015 | 未設 `ROOMPILOT_AGENT_PIPELINE` 時管線 start 回錯誤；status 永遠可查 |
| ACPT-016 | 全套 `pytest -q` 通過（對照 yen 分支 HEAD 既有失敗基準）＋`git diff --check` 乾淨 |

### 2.4 SCN（關鍵情境）

| ID | 一行標題 |
|---|---|
| SCN-001 | 使用者中途關閉瀏覽器，隔天重開恢復到第 6 步繼續編輯 |
| SCN-002 | 上傳 → 辨識 → 校正 → 確認 layout_json 的全鏈 happy path |
| SCN-003 | 使用者逐房在 A/B 之間切換並合成回單一方案（座標鎖定不漂移） |
| SCN-004 | 使用者把衣櫃拖進門前淨空區，系統拒絕並提示讓開動線 |
| SCN-005 | 確認白模（confirmWhiteModel）帶 validate_only，家具不被整屋重排 |
| SCN-006 | PostgreSQL 斷線時第 6 步家具查詢的可見失敗與明確回退路徑 |
| SCN-007 | 第 7 步鎖定視角 → 第 8 步逐房生圖 → 一次改圖 → 成果包 PDF |
| SCN-008 | 家電（冰箱/洗衣機）只出現在生圖 prompt context，2D/3D 場景不見蹤影 |
| SCN-009 | 兩個分頁同時編輯同一專案，落後方收到 409 並重載 |
| SCN-010 | 開啟 ROOMPILOT_AGENT_PIPELINE 後管線與 step6 並行，reconcile 對帳覆蓋率 |

### 2.5 REQ → FR/NFR → ACPT → SCN 對照表

| REQ | FR/NFR | ACPT | SCN |
|---|---|---|---|
| REQ-001 | FR-001、NFR-002 | ACPT-001、ACPT-014 | SCN-001、SCN-009 |
| REQ-002 | FR-002 | ACPT-002 | SCN-002 |
| REQ-003 | FR-003、NFR-001 | ACPT-003 | SCN-002 |
| REQ-004 | FR-004 | ACPT-004 | SCN-002 |
| REQ-005 | FR-005 | ACPT-005 | SCN-008 |
| REQ-006 | FR-006、NFR-004 | ACPT-006 | SCN-003 |
| REQ-007 | FR-007、NFR-004 | ACPT-007、ACPT-008 | SCN-004、SCN-005 |
| REQ-008 | FR-008 | ACPT-016 | SCN-005 |
| REQ-009 | FR-009 | ACPT-016 | SCN-007 |
| REQ-010 | FR-010 | ACPT-009 | SCN-007 |
| REQ-011 | FR-011 | ACPT-010 | SCN-007 |
| REQ-012 | FR-012 | ACPT-011 | SCN-007 |
| REQ-013 | FR-013、NFR-003、NFR-005 | ACPT-012 | SCN-006 |
| REQ-014 | FR-014 | ACPT-013 | SCN-008 |
| （橫切） | FR-015、NFR-006 | ACPT-015、ACPT-016 | SCN-010 |

## 3. ADR 清單

只收程式碼／文件中有證據的既成決策；檔案落在 `RoomPilot_Docs/03_architecture/adr/`。

| ID | Slug | 標題 | 核心證據 |
|---|---|---|---|
| ADR-001 | layout-json-scene-json-boundary | 平面圖辨識止於 layout_json，設計方案用 scene_json，兩者是唯一模組邊界產物 | docs/contracts/LAYOUT_SCENE_BOUNDARY_CONTRACT.md、AGENTS.md:52 |
| ADR-002 | geometry-legality-engine-only | 家具幾何合法性只在 backend/engine 計算，不移到 Graph RAG、瀏覽器或 LLM | AGENTS.md:53、scene_service.py:2228-2230 |
| ADR-003 | catalog-postgres-first-json-fallback | 家具 catalog 以 PostgreSQL view `roompilot.furniture_catalog_current` 優先，DB 失敗必須可見，僅顯式設定才回退已驗證 JSON | main.py:909-926、postgres_repository.py:20、README:299-304 |
| ADR-004 | appliances-render-context-only | 家電只進問卷與 scene_json.render_context 供生圖，不進 2D/3D 擺設與正式家具 API | AGENTS.md:56、scene_service.py:715-740、3058-3062 |
| ADR-005 | agent-pipeline-parallel-flag | MasterAgent 管線以 ROOMPILOT_AGENT_PIPELINE flag 與 step6 並存，可隨時回退，不取代正式路徑 | agent_pipeline_service.py:1-11、main.py:3514 |
| ADR-006 | static-frontend-as-production | 正式前端是 backend/server/static 單頁八步精靈；frontend3d/ 與 frontend/ 為次要原型 | AGENTS.md:58、scene.html:7 |
| ADR-007 | workflow-json-single-snapshot-store | 八步狀態併入單一 workflow JSON 快照（≤2MB）存 ProjectStore，revision 樂觀鎖防多分頁互踩 | project_store.py:12、18、28-33 |
| ADR-008 | hybrid-shapely-raster-engine | 兩套幾何引擎並存：Shapely 提議候選、5cm 柵格為碰撞判定唯一權威 | layout_model.py:3-5、raster.py:18-20、scene_service.py:2269-2286 |

## 4. Runbook 症狀清單

檔案落在 `RoomPilot_Docs/06_ops/`，命名 `runbook-<slug>.md`。

| Slug | 症狀 | 證據 |
|---|---|---|
| delivery-proposal-503 | 第 8 步「產出設計提案」回 503 `delivery_engine_not_configured`（缺 Playwright Chromium） | requirements-delivery.txt:2、README:111-117、main.py:2384 |
| catalog-db-unavailable | 第 6 步家具清單為空或 provider 回報 `json_fallback, available=False`（PostgreSQL 不可用/回傳不足 8,675 筆） | main.py:909-926、postgres_catalog.py:229-238 |
| workflow-revision-conflict | 保存工作流回 409 `project_revision_conflict`（多分頁/多 session 互踩） | main.py:1806-1867、project_store.py:28-33 |
| rag-model-cache-missing | /rag 檢索不可用，status 回報 blockers（模型快取缺失即 raise RagDependencyError、offline-only 不自動下載） | model_runtime.py:104-131、service.py:76-108 |

## 5. 術語表

| 中文 | 程式碼／英文名詞 | 說明與證據 |
|---|---|---|
| 平面圖辨識結果 | `layout_json` | 只描述空間本身（牆/門/窗/樑/柱/房間），不含設計決策；辨識邊界終點（LAYOUT_SCENE_BOUNDARY_CONTRACT.md:16-34） |
| 設計方案 | `scene_json` | layout_json＋需求＋catalog＋規則的產物；含家具座標、材質、render_context（scene_service.py:2995-3088） |
| 白模 | white model（`#white-model-viewer`、`confirmWhiteModel`） | 第 6 步無材質 3D 檢視與確認（scene.html、scene_v2.js） |
| 色卡 | style card／palette（`palette-renders`、`taiwan_style_cards.json`） | 6 風格 × 3 色卡共 18 張；第 7 步代表房低解析比較圖 |
| 方案 A/B | `placement_variant`（server 端）／STRATEGIES（agent 端） | server 端 B 只反轉錨點嘗試順序；agent 端 A=動線優先、B=收納優先，語意不同（03-engine §5） |
| 走動預覽 | walk mode（`setWalkRoom`、`setViewMode`） | 第 6 步 3D 第一人稱檢視（scene_viewer.js） |
| 淨空 | clearance（`DOOR_CLEARANCE_CM=75` 等） | 門前 75、窗前 40、櫃正面 50 等禁放規則（constraints.py、engine/clearance.py） |
| 工作流快照 | workflow JSON（`workflow_json` 欄位） | 八步狀態單一快照，≤2MB，深合併更新（project_store.py） |
| 版本鎖 | revision／`expected_revision` | 樂觀鎖，落後回 409（project_store.py:28-33） |
| 生圖上下文 | `render_context.appliance_requirements` | 家電唯一合法去處，只供第 8 步生圖 prompt |
| 隔離區 | quarantine（`backend/catalog/data/quarantine/`） | 未驗證/未匹配家具，執行期程式不得載入 |
| 家具目錄 | catalog view `roompilot.furniture_catalog_current` | 8,675 件官方家具的唯一正式讀取面（schema.sql:386-471） |
| 生圖 | AI render（`ai-renders`、nano banana via OpenRouter） | 第 8 步逐房寫實圖 |
| 改圖 | revision／edit（`/ai-renders/{room_id}/edit`） | 每房一次額度的整批修圖 |
| 只驗不排 | `validate_only` | 信任使用者配置、座標照舊只回報合法性（scene_service.py:2188-2191） |
| 視角鎖定 | viewpoint（`lock-master-view`、`viewpoint_version`） | 第 7 步鎖定的相機狀態，生圖 img2img 參考 |
| 交付成果包 | design delivery（`/design-delivery`、schema 1.1） | 第 8 步五章 JSON＋提案 PDF |
| 併存管線 | agent pipeline（`ROOMPILOT_AGENT_PIPELINE`、MasterAgent） | HITL state machine，與 step6 並行不取代 |

## 6. 輸出檔案計畫

全部落在 `D:\RoomPilot-Agent\RoomPilot_Docs\`，結構依 `VibeCoding_Workflow_Templates/INDEX.md` 的 Pilot 文件組；多實例模板依實例化規則展開（ADR 每決策一份、runbook 每症狀一份）。

| 路徑 | 模板 | 實例規則 |
|---|---|---|
| `RoomPilot_Docs/00-registry.md` | （本檔） | 單例 |
| `RoomPilot_Docs/01_requirements/brd.md` | brd | 單例 |
| `RoomPilot_Docs/01_requirements/prd.md` | prd | 單例 |
| `RoomPilot_Docs/01_requirements/srs.md` | srs | 單例 |
| `RoomPilot_Docs/02_ux_ui/ux_research_and_journey.md` | ux_research_and_journey | 單例 |
| `RoomPilot_Docs/02_ux_ui/information_architecture.md` | information_architecture | 單例 |
| `RoomPilot_Docs/02_ux_ui/ui_spec-scene.md` | ui_spec | 每頁面一份（八步精靈 `/scene` 為主頁面） |
| `RoomPilot_Docs/03_architecture/sad.md` | sad | 單例 |
| `RoomPilot_Docs/03_architecture/adr/ADR-001-layout-json-scene-json-boundary.md` | adr | 每決策一份 |
| `RoomPilot_Docs/03_architecture/adr/ADR-002-geometry-legality-engine-only.md` | adr | 每決策一份 |
| `RoomPilot_Docs/03_architecture/adr/ADR-003-catalog-postgres-first-json-fallback.md` | adr | 每決策一份 |
| `RoomPilot_Docs/03_architecture/adr/ADR-004-appliances-render-context-only.md` | adr | 每決策一份 |
| `RoomPilot_Docs/03_architecture/adr/ADR-005-agent-pipeline-parallel-flag.md` | adr | 每決策一份 |
| `RoomPilot_Docs/03_architecture/adr/ADR-006-static-frontend-as-production.md` | adr | 每決策一份 |
| `RoomPilot_Docs/03_architecture/adr/ADR-007-workflow-json-single-snapshot-store.md` | adr | 每決策一份 |
| `RoomPilot_Docs/03_architecture/adr/ADR-008-hybrid-shapely-raster-engine.md` | adr | 每決策一份 |
| `RoomPilot_Docs/04_design/api_spec.md` | api_spec | 單例（約定） |
| `RoomPilot_Docs/04_design/openapi-roompilot-v1.yaml` | openapi | 每服務一份（單一 FastAPI app） |
| `RoomPilot_Docs/04_design/db_design.md` | db_design | 單例 |
| `RoomPilot_Docs/04_design/lld.md` | lld | 單例（狀態機依 Aggregate 分節） |
| `RoomPilot_Docs/05_qa/test_plan.md` | test_plan | 單例 |
| `RoomPilot_Docs/05_qa/UAT_RoomPilot_Pilot_內部_2026-08-11.md` | uat_plan | 每驗收輪次一份（首輪） |
| `RoomPilot_Docs/06_ops/deployment_and_operations.md` | deployment_and_operations | 單例 |
| `RoomPilot_Docs/06_ops/runbook-delivery-proposal-503.md` | runbook | 每症狀一份 |
| `RoomPilot_Docs/06_ops/runbook-catalog-db-unavailable.md` | runbook | 每症狀一份 |
| `RoomPilot_Docs/06_ops/runbook-workflow-revision-conflict.md` | runbook | 每症狀一份 |
| `RoomPilot_Docs/06_ops/runbook-rag-model-cache-missing.md` | runbook | 每症狀一份 |

## 7. 追溯

- 上游：事實檔 `01-product.md`、`02-api.md`、`03-engine.md`、`04-frontend.md`、`05-data.md`、`06-ops.md`（git `yen`@`8863a36c`）；實例化規則 `VibeCoding_Workflow_Templates/INDEX.md`；六要素 `VibeCoding_Workflow_Templates/_meta/template_standard.md`。
- 下游：§6 全部輸出文件——每份文件引用本檔的 `REQ-*/FR-*/NFR-*/ACPT-*/SCN-*/ADR-*` ID，不得另行造 ID。
- 待確認：本登錄簿為 AI 衍生，REQ 優先序與範圍尚未經 `requirements_tracker.xlsx` ①需求決策 owner 核准；ProjectStore 實際為 SQLite 而契約稱 PostgreSQL Phase 3（見 01-product §5 待確認項）。
