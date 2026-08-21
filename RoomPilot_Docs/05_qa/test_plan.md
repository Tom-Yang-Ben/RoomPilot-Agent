# 測試計畫與測試案例 (Test Plan / Test Cases) - RoomPilot

> **版本:** v1.0 ｜ **更新:** 2026-08-12 ｜ **狀態:** 草稿（待 owner 核准）
> **Owner:** QA；TC 與 ACPT 的對應權威為 [`srs.md`](../01_requirements/srs.md) §9.2，案例狀態與執行證據維護在 [`qa_tracker.xlsx`](qa_tracker.xlsx)
> **語域:** L3（工程）——直接寫測試檔、函式與失敗訊息
> **實例:** 單例（策略與對照一份；逐次執行證據在 `qa_tracker.xlsx` ②執行證據）
>
> **本文件回答**：ACPT-001..060 各由哪一條 TC 承接、該 TC 屬哪個測試層級、repo 內現有哪一支測試可以佐證、以及哪些是**尚無測試的缺口**；並登記 2026-08-12 的可驗證性基準線。
> **本文件不含**：驗收條件內文（去 [`prd.md`](../01_requirements/prd.md)）、可測行為與 file:line 需求佐證（去 [`srs.md`](../01_requirements/srs.md)）、內部人工驗收腳本（去 [`UAT 計畫`](UAT_RoomPilot_Pilot_內部_2026-08-12.md)）、失效當下的處置動作（去 `../06_ops/` 各 runbook）。
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、2026-08-12 工作樹；本文件所有測試檔行號與基準線數字皆為當日實跑或實讀。

## 目錄

- [1. 測試範圍與策略](#1-測試範圍與策略)
- [2. 可驗證性基準線](#2-可驗證性基準線)
- [3. 測試案例對照](#3-測試案例對照)
- [4. BDD 場景對照](#4-bdd-場景對照)
- [5. 測試缺口與待確認](#5-測試缺口與待確認)
- [6. 缺陷回報格式](#6-缺陷回報格式)
- [7. 測試報告結論](#7-測試報告結論)
- [8. 追溯](#8-追溯)

---

## 1. 測試範圍與策略

| 項目 | 內容 |
| :--- | :--- |
| **範圍內** | ACPT-001..060 全部（對應 TC-001..060）；FR-001..067、NFR-001..025；SCN-001..042 |
| **範圍外** | `frontend3d/` React 原型（次要原型，非正式產品）；效能／負載／滲透測試（NFR-025 目標值未定義，無可驗對象）；多人協作與權限（Pilot 無認證，NFR-019） |
| **測試層級** | **單元**（`backend/engine/`、agent 規則、cost 純函式）／**整合**（FastAPI `TestClient`）／**契約**（靜態檔字串與 manifest 斷言、Node 執行單一 JS 函式）／**端到端**（跨步 API 串接）／**人工**（實際瀏覽器操作，證據入 `qa_tracker.xlsx`） |
| **前端測試的實際性質** | 前端幾乎不執行：`tests/test_scene_v2_contract.py`、`tests/test_render_image_stage.py` 等以正規式／字串比對 `scene.html` 與 `scene_v2.js` 原始碼；只有兩類真的跑 JS——`node --check` 語法檢查（`tests/test_scene_3d_lifecycle_contract.py:28`）與以 Node 匯入單一函式求值（`tests/test_scene_v2_contract.py:1996`–`2010` 執行 `planCmToLayerPixel`）。**互動、渲染與 3D 行為無自動化覆蓋，一律列人工。** |
| **環境** | 本機 Windows，`.venv`（實測 Python 3.13.5，與 `pyproject.toml:5` 宣告的 `>=3.12`／安裝腳本釘 3.12 有落差，NFR-023）；PostgreSQL **未啟動**；OpenRouter 金鑰未設定，生圖路徑一律以 fake gateway 注入；Playwright chromium 已安裝 |
| **進入條件** | 工作樹乾淨或已知差異；`.runtime/` 存在；執行 `.\.venv\Scripts\python.exe -m pytest -q`（[`AGENTS.md`](../../AGENTS.md) §驗證矩陣的最終整合指令） |
| **退出條件** | **待 DEC-019 核准**——「幾間房、跑哪些真實案例、什麼算通過」屬產品 owner 權責，本文件不得代填。目前僅能以 §2 的基準線作為**回歸比較基準**，不作為通過門檻 |

---

## 2. 可驗證性基準線

### 2.1 pytest 實跑（2026-08-12，NFR-024／ACPT-059）

| 項目 | 數值 | 取得方式 |
| :--- | :--- | :--- |
| 收集 | 947 | `.venv\Scripts\python.exe -m pytest -q --collect-only` → `947 tests collected in 4.30s` |
| 結果 | **35 failed／905 passed／7 skipped**，耗時 182.16 s | `.venv\Scripts\python.exe -m pytest -q -p no:randomly` |
| 測試設定 | `pyproject.toml:63-64` 僅 `pythonpath = ["."]`——無 marker、無 `addopts`、無覆蓋率門檻 | 實讀 |

### 2.2 35 筆紅燈分類（逐筆以 `--tb=line` 取回原因）

| 類別 | 筆數 | 代表佐證 | 判定 |
| :--- | :--- | :--- | :--- |
| PostgreSQL 未啟動 | **23** | `psycopg2.OperationalError: connection to server at "localhost" … port 5432 failed`（`tests/test_official_cloud_catalog.py`、`test_library_mode1.py`、`test_scene_soft_decor.py` 等 6 檔） | 環境缺前置，非程式缺陷 |
| 辨識管線真實缺陷 | 4 | `tests/test_cody_room_recognition.py:32,45,60,251`；根因 `backend/floorplan/floorplan2room.py:280` `TypeError: 'numpy.int32' object is not iterable`，被 `backend/floorplan/cody_adapter.py:1032` 吞成 fallback、`recognize_cody_rooms()` 回 `None` | **缺陷**，影響 TC-012 |
| 前端契約測試過時（DOM id 已改名） | 3 | `tests/test_render_image_stage.py:43,54,71` 期待 `id="ai-openrouter-gallery"`／`showRenderGallery`，現行實作為 `#ai-render-image-stage`（`backend/server/static/scene.html:958`、`scene_v2.js:571,19001`） | **測試過時**，非產品退步 |
| 前端契約測試過時（字串比對） | 4 | `tests/test_scene_v2_contract.py:494,505,3213,3588`；例如 `:3213` 期待 `$("#exit-project").addEventListener(...)`，實作已改為可選鏈 `$("#exit-project")?.addEventListener(...)`（`scene_v2.js:17747`） | **測試過時** |
| 問卷畫面契約 | 1 | `tests/test_questionnaire_visual_catalog.py:257` 期待 `id="whole-house-air-conditioning-all"` 不在 `scene.html` | 待 MOD-WEB owner 判定過時或退步 |

7 筆 skip 全部有具名理由：`tests/test_catalog_10550_sql.py:8-10` 整檔 skip（理由字串寫「10,550 筆舊 catalog 已由 **9,350** 筆正式家具與獨立家電問卷流程取代」）4 筆、`tests/test_catalog_six_style_contract.py:94`（未設定外部離線 GLB 備援包）1 筆、`tests/test_semantic_cache_alignment.py:111,122`（需要 floor01 測資與語意快取）2 筆。

### 2.3 缺席的品質機制（皆為「本 repo 無此機制」）

| 機制 | 現況 | 佐證 |
| :--- | :--- | :--- |
| CI | 無：`.github/` 目錄不存在，無任何 pipeline 設定 | `ls -d .github` → No such file or directory |
| 覆蓋率 | 無：未安裝 `pytest-cov`，`pyproject.toml` 無覆蓋率設定或門檻 | `pyproject.toml:63-64` |
| Lint／型別檢查 | 無：查無 `ruff.toml`／`.ruff.toml`／`mypy.ini`／`setup.cfg`／`tox.ini`／`.pre-commit-config.yaml` | 目錄實查 |
| 前端測試工具鏈 | 無：repo 根目錄無 `package.json`，前端驗證全靠 Python 端字串斷言 | 目錄實查 |
| 效能／負載基準 | 無：NFR-025 目標值未定義，無 benchmark 腳本 | [`srs.md`](../01_requirements/srs.md) NFR-025 |

---

## 3. 測試案例對照

TC 編號與 ACPT 同號一對一（TC-0NN ↔ ACPT-0NN），分組依 [`srs.md`](../01_requirements/srs.md) §9.2 的八步 × TC 分配，**不另起編號**。狀態欄：**綠**＝有對應測試且本次實跑通過；**紅**＝有測試但失敗；**部分**＝主路徑有測試、關鍵分支無斷言；**缺口**＝repo 內查無對應測試。

### 3.1 S1 建立專案（TC-001–TC-003）

| TC | ACPT | FR／NFR | 層級 | 現有測試佐證 | 狀態 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC-001 | ACPT-001 | FR-001、FR-002 | 整合 | `tests/test_project_workflow_api.py:186` | 綠 |
| TC-002 | ACPT-002 | FR-003、NFR-001、NFR-005 | 單元＋整合 | `tests/test_project_store_hardening.py:103`（>2 MB 交易內原子拒收）、`:158`（API 端 revision 與 size guard）、`tests/test_project_workflow_api.py:145`（超長標籤壓縮） | 部分——`WORKFLOW_STEPS` 白名單外步驟名的 422 無伺服器端斷言 |
| TC-003 | ACPT-003 | FR-004、NFR-003、NFR-004 | 單元＋整合 | `tests/test_project_store_hardening.py:26`（WAL＋`foreign_keys`）、`:37`（`expected_revision` 拒絕過期且不覆蓋）、`tests/test_project_workflow_api.py:199`（pending 重播原子拒絕） | 部分——正式前端一般存檔不帶 `expected_revision`（OPEN-14），該落差無測試 |

### 3.2 S2 上傳平面圖（TC-004、TC-005、TC-015）

| TC | ACPT | FR／NFR | 層級 | 現有測試佐證 | 狀態 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC-004 | ACPT-004 | FR-005、NFR-002 | 整合 | `tests/test_project_workflow_api.py:251`（只收 `.dxf/.png/.jpg/.jpeg`） | 綠 |
| TC-005 | ACPT-005 | FR-006 | 整合 | 僅 `tests/test_project_workflow_api.py:275` 斷言 `source_url` 結尾 | 部分——`floorplan_missing` 409 與實體檔遺失 410 無測試 |
| TC-015 | ACPT-015 | FR-017、NFR-017 | 單元＋整合 | `tests/test_dxf_room_units.py:6,26`（公尺→公分）、`tests/test_wall_openings.py:34,47,60,78`（開口帶與牆體）、`tests/test_project_workflow_api.py:384`（DXF 分析回公分幾何與房間區域） | 綠 |

### 3.3 S3 確定尺寸（TC-009–TC-014）

| TC | ACPT | FR／NFR | 層級 | 現有測試佐證 | 狀態 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC-009 | ACPT-009 | FR-010、FR-011 | 整合＋端到端 | `tests/test_project_workflow_api.py:282`（未勾確認即辨識）、`:322`（重跑辨識）；`tests/test_floorplan_vision_api.py:24,176`（影像端到端） | 紅——`test_floorplan_vision_api.py:24` 等 3 筆本次失敗（PostgreSQL 未啟動） |
| TC-010 | ACPT-010 | FR-012、NFR-017 | 單元 | `tests/test_floorplan_vision.py:208`（房名與座標正規化為公分）、`:630`（legacy 公尺只遷移一次）、`tests/test_cody_pipeline_modules.py:36`（11 步模組逐一可載） | 綠 |
| TC-011 | ACPT-011 | FR-013 | 單元＋契約 | `tests/test_floorplan_vision.py:97`（630 cm 標定）、`:124`（無錨點須確認）、`:136`（OCR 低信心要求手動）；前端 `tests/test_scene_calibration.py:35,72,90` | 綠 |
| TC-012 | ACPT-012 | FR-014 | 單元 | `tests/test_cody_room_recognition.py:99,128,282,301,319`（語意層只填空位／不覆蓋確信型別／面積規則墊底）、`tests/test_floorplan_room_icons.py` | **紅**——同檔 `:32,45,60,251` 失敗，根因見 §2.2 |
| TC-013 | ACPT-013 | FR-015 | 單元＋契約 | `tests/test_recognition_review_wiring.py:53`（四種 reason 皆有前端標籤）、`:63`（第 4 步呈現 review_items）；`tests/test_floorplan_vision.py:239`（高信心房不整批要求確認） | 綠 |
| TC-014 | ACPT-014 | FR-016 | 整合 | `tests/test_project_workflow_api.py:322`（重跑辨識作廢已確認結構）、`tests/test_scene_workflow.py:606`（上游改動作廢下游） | 綠 |

### 3.4 S4 空間與結構（TC-006、TC-016、TC-017）

| TC | ACPT | FR／NFR | 層級 | 現有測試佐證 | 狀態 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC-006 | ACPT-006 | FR-007 | 整合 | `tests/test_recognition_review_wiring.py:126`（未確認即宣告完成被拒）、`:142`、`:154`（房被刪視為已處理）、`:166`（僅宣告完成時才啟動閘門） | 綠 |
| TC-016 | ACPT-016 | FR-018、NFR-017 | 契約 | `tests/test_scene_workflow.py:109,156,183`（樑柱幾何與尺寸驗證）、`:249`（樑拖曳吸附）、`tests/test_scene_shell_geometry.py:32,52,74`（窗符號聚合） | 綠 |
| TC-017 | ACPT-017 | FR-019 | 契約 | `tests/test_scene_shell_geometry.py:155,286,336`（開口填塞與門楣落在牆縫）、`tests/test_scene_visual_regressions.py:88`（已確認門扇平貼於門洞）、`:281`（step4 確認後只補微縫） | 綠 |

### 3.5 S5 需求問卷（TC-024–TC-026、TC-041–TC-043）

| TC | ACPT | FR／NFR | 層級 | 現有測試佐證 | 狀態 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC-024 | ACPT-024 | FR-026 | 整合＋契約 | `tests/test_questionnaire_visual_catalog.py:160`（API 回 planned／ready）、`:141`（ready 影像為有效資產）、`:269`（JSON 為版本化來源） | 紅——同檔 `:257` 失敗（畫面契約，見 §2.2） |
| TC-025 | ACPT-025 | FR-027 | 單元＋契約 | `tests/test_scene_room_requirements.py:38`（房層級且版本化）、`:66`（逐房獨立副本）、`:147`（全房確認前不出 RAG payload）、`tests/test_questionnaire_visual_catalog.py:288`（雙閘門） | 綠 |
| TC-026 | ACPT-026 | FR-028 | 整合＋契約 | `tests/test_scene_furniture_retrieval.py:145`（家電型錄退出第 6 步）、`:154`（前端不再把家電對映到 API）；`tests/test_ai_render_openrouter.py:69` 以 `appliance_requirements` 為生圖輸入 | 部分——缺「家電不得出現在 `scene_objects`」的反向斷言（見 [`ui_spec-step5-requirements.md`](../02_ux_ui/ui_spec-step5-requirements.md) 待確認 5） |
| TC-041 | ACPT-041 | FR-046、NFR-010 | 整合 | `tests/test_rag_api.py:41`（status 與驗證）、`:70`（失敗碼對映狀態碼）、`:115`（不外洩上游細節）；`tests/test_rag_frontend.py:47`（狀態與邊界可見） | 綠 |
| TC-042 | ACPT-042 | FR-047、FR-049 | 單元 | `tests/test_rag_domain.py:143`（預算硬篩與加權公式）、`:441`（依 role 取 top-20／12 重排）、`:476`（去重與 hydrate） | 部分——**缺「重排前後候選 id 集合完全相同」的集合等值斷言**（[ADR-008](../03_architecture/adr/ADR-008-rag-retrieval-only-offline-models.md) 已登記為待補） |
| TC-043 | ACPT-043 | FR-048、NFR-009 | 整合 | `tests/test_rag_api.py:95`（job 進度與結果）、`:132`（多房排隊） | 部分——佇列上限 24 的 429 `rag_job_capacity_reached` 無測試 |

### 3.6 S6 配置與預覽（TC-027–TC-040、TC-044、TC-045）

| TC | ACPT | FR／NFR | 層級 | 現有測試佐證 | 狀態 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC-027 | ACPT-027 | FR-029 | 整合 | `tests/test_project_workflow_api.py:461`（以使用者確認的平面為權威幾何）、`tests/test_questionnaire_visual_catalog.py:380`（generate 保留完整問卷） | 紅——兩筆本次皆因 PostgreSQL 未啟動失敗 |
| TC-028 | ACPT-028 | FR-030 | 單元 | `tests/test_generate_layout_characterization.py:261`（各房家具落在自己房內）、`:284`（無 id 走 `ROOM_AFFINITY`）、`:304`（無親和退最大區域）、`:318`（逐房保序） | 綠 |
| TC-029 | ACPT-029 | FR-031 | 單元＋整合 | `tests/test_generate_layout_characterization.py:159`（B 是合法替代配置）、`tests/test_roompilot_quality_guardrails.py:118`（B 的 payload 與 A 不同）、`tests/test_scene_design_schemes.py:15`（A／B 共用同一份已確認結構） | 綠 |
| TC-030 | ACPT-030 | FR-032 | 單元 | `tests/test_generate_layout_characterization.py:104`（`validate_only` 不動座標、不塌陷）、`:135`（`preserve_existing_count` 保留前段） | 綠 |
| TC-031 | ACPT-031 | FR-033、FR-034、NFR-015 | 單元＋整合 | `tests/test_clearance.py:115`（本體檢查優先）、`:122`（反向檢查）、`:83`–`:104`（撞牆／撞本體／淨空互撞）；`tests/test_placement.py:75,82,89`；`tests/test_project_workflow_api.py:591`（2D 與拖曳皆走引擎） | 綠 |
| TC-032 | ACPT-032 | FR-035 | 單元 | `tests/test_clearance.py:57`（front 淨空前伸 60 cm 且與家具同寬）、`:71`（隨旋轉改向）；`backend/server/tests/test_cabinet_clearance.py:61,76,92,100,106`（有櫃家具正面帶） | 部分——門前 75 cm（`backend/engine/constraints.py:21` `DOOR_CLEARANCE_CM`）、窗前 40 cm／高度 ≥90 cm 條件與背牆 5 cm 皆無獨立斷言 |
| TC-033 | ACPT-033 | FR-036 | 單元 | `tests/test_placement.py:169,177`（單軸受阻仍成功）、`:190`、`:201`、`:211`（旋轉合法）、`:218`（旋轉撞牆還原） | 綠 |
| TC-034 | ACPT-034 | FR-024、FR-037、NFR-016 | 單元＋整合 | `tests/test_generate_layout_characterization.py:218`（失敗回報 reason）、`tests/test_roompilot_quality_guardrails.py:178`（`placement_resolution_report`）、`:244`（保護 `user_required`）、`tests/test_agent_place.py:115,129,158`（換小件／移除／保護升級） | 部分——`unavailable_types[]` 與第 6→7 步 `getDiagnostics()` 硬閘僅有字串存在性斷言（`tests/test_scene_v2_contract.py:3578`） |
| TC-035 | ACPT-035 | FR-038 | 整合 | `tests/test_scene_soft_decor.py:140,201,221,259,384,431` | 紅——本檔 6 筆本次皆因 PostgreSQL 未啟動失敗 |
| TC-036 | ACPT-036 | FR-039、NFR-006 | 整合 | `tests/test_library_mode1.py:57,79`（facet 與可載入模型） | 紅（PostgreSQL）＋部分——`page<1`／`page_size>80` 的 422 邊界無測試 |
| TC-037 | ACPT-037 | FR-040、FR-041、NFR-007、NFR-008 | 整合 | `tests/test_postgres_catalog_contract.py:4`（列→契約對映）；前端 `tests/test_scene_6_8_wizard_contract.py:72,80`（開工前先解釋型錄不可用） | **缺口**——`/api/catalog/status` 端點本身、provider 決策與 8,675／8,076／9,350 三個筆數口徑（OPEN-06）皆無測試 |
| TC-038 | ACPT-038 | FR-042 | 單元＋契約 | `tests/test_external_glb_resolution.py:11,28,45,62`（外部 GLB 解析與備援包邊界）、`tests/test_cloud_image_previews.py:27,47` | 部分——`model.gltf`／`buffer.bin` 於 cloudfront 模式回 410 無測試 |
| TC-039 | ACPT-039 | FR-043、FR-044 | 契約 | `tests/test_official_catalog_sql.py:48`（無資料庫下驗證全部官方資產）、`:83`（替換為原子）、`tests/test_image_manifest_contract.py:39,115`（每件三視圖與 GLB manifest）、`tests/test_furniture_embeddings_sql.py:84`（雜湊／維度／L2 norm） | 綠 |
| TC-040 | ACPT-040 | FR-045 | 契約 | `tests/test_cloud_quarantine.py:21`（1,514 筆隔離包）、`:33`（隔離 id 不在 web 模型集合） | 紅——`:33` 需連 DB 取家具集合，本次因 PostgreSQL 未啟動失敗 |
| TC-044 | ACPT-044 | FR-050 | 單元＋整合 | `tests/test_agent_select.py:98,187,264`（白名單驗證與整批降級）、`tests/test_project_workflow_api.py:28`（LLM 違規時退回規則）、`:55`（無 LLM 走本地規則） | 綠 |
| TC-045 | ACPT-045 | FR-051、FR-052 | 單元 | `tests/test_agent_select.py:121,128,137,145,210,226`；`backend/server/tests/test_furniture_selection_rules.py:18`（客廳三件）、`:50`（不兩床）、`:81,92,102`（餐椅人數與桌寬）；`tests/test_agent_knowledge.py:40`（陽台不放櫃） | 部分——兩套並存的選件規則（OPEN-39）只有多房路徑被完整覆蓋 |

### 3.7 S7 方案鎖定與視角（TC-008、TC-047–TC-049）

| TC | ACPT | FR／NFR | 層級 | 現有測試佐證 | 狀態 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC-008 | ACPT-008 | FR-009、NFR-002 | 單元＋整合 | `tests/test_project_store_hardening.py:119`（僅追加、最新在前）、`:189`（存檔／列表／下載 PNG） | 部分——20 MB 上限與 PNG magic 檢查的 413 無測試 |
| TC-047 | ACPT-047 | FR-055 | 契約＋整合 | `tests/test_scene_workflow.py:466`（未鎖主相機不得進生圖步）、`tests/test_remote_render_workflow.py:67`（逐房相機未鎖被拒）、`:76`（鎖定後接受） | 綠 |
| TC-048 | ACPT-048 | FR-056 | 整合 | `tests/test_palette_renders_openrouter.py:185`（每案僅能成功一次，`:196` 斷言 `palette_already_generated`）、`:199`（全失敗不鎖定可重試）、`:212`（未設定回 503）、`:148`（三張併發） | 綠 |
| TC-049 | ACPT-049 | FR-057 | 契約 | `tests/test_taiwan_style_cards.py:20,28,56`（色卡 id 唯一、可安全交接進場景）、`tests/test_ai_render_openrouter.py:169`（用正式色卡而非場景 pack 色） | 紅——`test_taiwan_style_cards.py` 3 筆本次因 PostgreSQL 未啟動失敗 |

### 3.8 S8 AI 渲染與成果包（TC-050–TC-055、TC-060）

| TC | ACPT | FR／NFR | 層級 | 現有測試佐證 | 狀態 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC-050 | ACPT-050 | FR-058、NFR-012、NFR-018 | 整合 | `tests/test_ai_render_openrouter.py:147`（客廳加夜景）、`:161`（非客廳無夜景）、`:219`（單房失敗其餘照回）、`:230`（各房一次派發）、`:311`（缺 room_views 回 `room_views_required`） | 綠 |
| TC-051 | ACPT-051 | FR-059 | 單元 | `backend/agent/tests/test_agent_genpic_description.py:85,89,101`（提示詞剝除尺寸）、`:108`（佔位材質不入提示詞）、`:114`（描述鎖定） | 部分——「家電只在提示詞出現、不在擺設清單」的成對斷言由 [ADR-006](../03_architecture/adr/ADR-006-appliances-render-context-only.md) 登記為待補 |
| TC-052 | ACPT-052 | FR-060 | 整合 | `tests/test_ai_render_openrouter.py:261`（生成後改圖額度，`:292` 斷言 `ai_edit_budget_exhausted`）、`tests/test_scene_step4_to_8_integration.py:190,217`（逐房各一次修訂） | 部分——契約寫「整批一次」與程式「逐房一次」的落差未被測試釘住（OPEN-16）；[ADR-009](../03_architecture/adr/ADR-009-server-governed-ai-generation.md) 另登記 `ai_render.rooms` 覆寫待補測試 |
| TC-053 | ACPT-053 | FR-061、FR-062、NFR-013 | 整合＋人工 | `tests/test_design_manual_api.py:112`（離線九章）、`:153`（LLM 可用時潤稿）、`:180`（產出後可下載）、`:218`（未產出回 404）；`tests/test_delivery_proposal_api.py:308`（PDF 端到端，需 Playwright）、`:361`（引擎缺席回 503）、`:297`（離線文案誠實回報）、`:159`（金額只在報價單章節） | 綠 |
| TC-054 | ACPT-054 | FR-063、NFR-020 | 整合 | `tests/test_delivery_proposal_api.py:408`（成果包含提案紀錄）、`:457`（專案不符拒絕）、`tests/test_scene_step4_to_8_integration.py:220`（逐房打包）；`tests/test_remote_render_workflow.py:48`（遠端渲染請求剝除身分欄位） | 部分——成果包側 `DELIVERY_SENSITIVE_KEYS` 脫敏**無直接斷言** |
| TC-055 | ACPT-055 | FR-064 | 單元＋整合 | `tests/test_cost_estimation.py:4`（可追溯的低／基／高概算）、`:62`（費率來源附連結與排除項）、`tests/test_cost_estimation_api.py:9`（版本化線上來源、不打即時網路）、`tests/test_scene_delivery.py:78`（家具與工程估價分離） | 綠 |
| TC-060 | ACPT-060 | NFR-011、NFR-014 | 整合 | `tests/test_ai_render_openrouter.py:295`（未設定回 503）、`tests/test_palette_renders_openrouter.py:212`（同上）、`tests/test_delivery_proposal_api.py:340`（引擎缺席 503）、`tests/test_remote_render_workflow.py:92`（未設定遠端渲染回 503）、`:86`（逾時值非法退安全預設） | 部分——502（上游明確拒絕）與 LLM 逾時（120 s／8 s 兩套）無測試 |

### 3.9 SX 跨步（TC-007、TC-018–TC-023、TC-046、TC-056–TC-059）

| TC | ACPT | FR／NFR | 層級 | 現有測試佐證 | 狀態 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC-007 | ACPT-007 | FR-008 | 整合 | `tests/test_project_workflow_api.py:79`（worktree 共用主 repo runtime）、`:108`（legacy worktree 連上傳檔一起遷移）、`tests/test_project_store_hardening.py:60`（舊庫遷移為 revision 0） | 綠 |
| TC-018 | ACPT-018 | FR-020 | 契約 | `tests/test_scene_workflow.py:447`（對外八步）、`:343`（辨識與校正共用一個面板）、`:412`（每個已確認步驟一個面板） | 綠 |
| TC-019 | ACPT-019 | FR-021 | 契約 | `tests/test_scene_workflow.py:513`（逐關卡阻擋）、`:571`（辨識前置）、`:606`（上游改動作廢下游）、`:653`（顯式零家具方案可放行） | 綠 |
| TC-020 | ACPT-020 | FR-022 | 契約＋整合 | `tests/test_scene_workflow.py:25`（pending 只對起始版本重播）、`tests/test_project_workflow_api.py:199`（伺服器端原子拒絕）、`tests/test_scene_workflow.py:300`（狀態可還原） | 綠 |
| TC-021 | ACPT-021 | FR-023 | 契約（Node 求值） | `tests/test_scene_v2_contract.py:1996`–`2010`（以 Node 執行 `planCmToLayerPixel`，比對到小數兩位） | 部分——`viewBox` 對齊 `<img>` content rect 與 footprint 最小 28 px 無斷言 |
| TC-022 | ACPT-022 | FR-024、NFR-021 | 契約 | `tests/test_scene_3d_lifecycle_contract.py:40`（GLB 只載一次、清場不 dispose）、`:52,84`（增量操作）、`:63`（`updateRoomSurfaces`）、`:104`（兩層跳過鍵）、`:148`（面材快取）；`tests/test_scene_v2_contract.py:18`–`27`（`?v=sha256-` 快取鍵等於實檔雜湊） | 綠 |
| TC-023 | ACPT-023 | FR-025 | 契約 | `tests/test_render_image_stage.py:35,49,66`（疊層 DOM、gallery／single 兩模式、縮圖點擊） | **紅**——3 筆全紅，但屬測試過時（期待舊 id `ai-openrouter-gallery`，實作為 `#ai-render-image-stage`，見 §2.2） |
| TC-046 | ACPT-046 | FR-053、FR-054、NFR-018 | 單元 | `backend/server/tests/test_agent_pipeline_service.py:17`（旗標開關）、`:28`（側寫持久化可重載）、`:40,45`（前置與非法輸入）；`backend/server/tests/test_agent_reconcile_service.py:33`（對帳一致且合法）、`:45` | 部分——**「旗標未設時四支專案路由回 404、`/status` 仍 200」無路由層測試**（[ADR-011](../03_architecture/adr/ADR-011-agent-pipeline-flag-isolation.md) 已登記） |
| TC-056 | ACPT-056 | FR-065、FR-067、NFR-019、NFR-020、NFR-023 | 契約＋人工 | `tests/test_env_example_contract.py:20`（`.env.example` 記載 OpenRouter 與型錄預設）；`tests/test_rag_frontend.py:25`（RAG 頁不出現在正式導覽） | 部分——`install.ps1`／`install.sh` 與 `127.0.0.1` 綁定、狀態端點不外洩金鑰皆**無自動化測試**，只能人工 |
| TC-057 | ACPT-057 | FR-066 | 人工 | **缺口**——repo 內查無針對 `docker-compose.yml` `db` 服務的測試；`tests/test_docker_split_contract.py` 只驗容器拆解契約（build target、RAG／PDF 的環境變數開關），不涵蓋 DB 供應與 dump 還原 | 缺口 |
| TC-058 | ACPT-058 | NFR-022、NFR-025 | 人工 | **缺口**——無配額、輪替、備份或刪除機制可測；2026-08-12 實測 `.runtime/uploads` 115 MB、`manuals` 45 MB、`projects.sqlite3` 67 MB，`backend/server/main.py` 內查無任何 `DELETE` 路由 | 缺口（受阻於 DEC-015） |
| TC-059 | ACPT-059 | NFR-024 | 人工 | 本文件 §2 即為該案例的執行證據；每次回歸重跑 `pytest -q` 並與 §2.1 比對 | 綠（基準線已登記） |

---

## 4. BDD 場景對照

SCN 的**情境內文權威在 [`prd.md`](../01_requirements/prd.md) §3**（六個關鍵卡點展開見 [`ux_research_and_journey.md`](../02_ux_ui/ux_research_and_journey.md) §5）；ID 索引與已知缺口見 [`00-registry.md`](../00-registry.md) §2.1、§2.2（registry 本身不含任何 ID 內文）。本節只維護 SCN → TC → ACPT 的對照與可觀察表徵的出處。

| 步 | SCN | 承接的 TC | 內文已被釘住的場景（出處） |
| :--- | :--- | :--- | :--- |
| S1 | SCN-001–003 | TC-001–003 | SCN-001 關瀏覽器再回來、SCN-002 兩分頁同時編輯、SCN-003 進度資料膨脹（[`ux_research_and_journey.md`](../02_ux_ui/ux_research_and_journey.md) §7） |
| S2 | SCN-004、005、012 | TC-004、005、015 | SCN-004 格式或壞圖被擋、SCN-005 手機翻拍上傳後預覽（[`ui_spec-step2-upload.md`](../02_ux_ui/ui_spec-step2-upload.md)） |
| S3 | SCN-006–009、011 | TC-009–014 | SCN-006 未勾確認即辨識 409、SCN-008 比例信心不足要求兩點標定、SCN-011 重跑辨識作廢下游（[`ui_spec-step3-recognition.md`](../02_ux_ui/ui_spec-step3-recognition.md)）；SCN-007、009 內文待 `prd.md` owner 補（缺口登記見 registry §2.2） |
| S4 | SCN-010、013 | TC-006、016、017 | SCN-010 旗標房未確認被擋、SCN-013 新增牆與門後 3D 單一門洞（[`ui_spec-step4-space-confirmation.md`](../02_ux_ui/ui_spec-step4-space-confirmation.md)） |
| S5 | SCN-014–016 | TC-024–026、041–043 | SCN-014 家電只在第 8 步可見、SCN-015 檢索不可用仍可完成問卷、SCN-016 檢索塞車不阻塞（[`ui_spec-step5-requirements.md`](../02_ux_ui/ui_spec-step5-requirements.md)） |
| S6 | SCN-017–025、040–042 | TC-027–040、044、045 | SCN-021 拖入門前淨空被拒、SCN-022 家具擺不下、SCN-023 缺 GLB 顯示替身、SCN-024 型錄不可用（[`ui_spec-step6-layout-2d.md`](../02_ux_ui/ui_spec-step6-layout-2d.md)、[`prd.md`](../01_requirements/prd.md) §4）；SCN-017–020、025、040–042 內文待 `prd.md` owner 補（缺口登記見 registry §2.2） |
| S7 | SCN-026–028 | TC-008、047–049 | SCN-026 逐房鎖定後才可前進、SCN-027 色卡每案一次、SCN-028 全失敗可重試（[`ui_spec-step7-proposal-review.md`](../02_ux_ui/ui_spec-step7-proposal-review.md)） |
| S8 | SCN-029–034、037 | TC-050–055、060 | SCN-030 未設金鑰 503、SCN-031 改圖第二次 409、SCN-032 PDF 引擎缺席 503（[`ui_spec-step8-ai-render.md`](../02_ux_ui/ui_spec-step8-ai-render.md)）；SCN-029、033、034、037 內文待 `prd.md` owner 補（缺口登記見 registry §2.2） |
| SX | SCN-035、036、038、039 | TC-007、018–023、046、056–059 | SCN-038 回頭改結構使第 7／8 步成果需重做、SCN-039 導覽恆八顆（[`information_architecture.md`](../02_ux_ui/information_architecture.md)）；SCN-035、036 內文待 `prd.md` owner 補（缺口登記見 registry §2.2） |

ACPT-008、039、040、046、051、058、059 屬非使用者可觀察面，不對應 SCN，由同號 TC 直接承接（[`srs.md`](../01_requirements/srs.md) §7 註）。

---

## 5. 測試缺口與待確認

| 編號 | 內容 | 影響 TC | 承接處 |
| :--- | :--- | :--- | :--- |
| OPEN-46 | **35 筆紅燈的處置方針**：23 筆 PostgreSQL 相依應改為 `skipif`（維持本機可全綠），或把 PostgreSQL 列為 `pytest` 必要前置（維持嚴格但本機必紅）？另 12 筆非 DB 紅燈中，7 筆已證實為測試過時、4 筆為真實辨識缺陷、1 筆待 owner 判定——三者處置不同，需一次裁決 | TC-009、012、023–024、027、035–037、040、049、059 | 本節；[`deployment_and_operations.md`](../06_ops/deployment_and_operations.md) |
| OPEN-25 | `README.md` 記載的分割模型融合與 94%／92% 辨識精準／召回（21 張測資）在本分支查無對應程式與測資基準，**不得作為驗收指標引用**；本次 4 筆 cody 紅燈進一步顯示辨識主路徑在無快取條件下會退回 `None` | TC-009、012、059 | 本節；[`srs.md`](../01_requirements/srs.md) §8 |
| GAP-01 | `/api/catalog/status` 端點、provider 決策與型錄筆數口徑無測試；且 repo 內同時存在 **8,675**（官方匯入驗證）、**8,076**（active／向量）、**9,350**（`tests/test_catalog_10550_sql.py:9` 的 skip 理由字串）三個數字 | TC-037、TC-039 | [ADR-005](../03_architecture/adr/ADR-005-postgres-catalog-source-of-truth.md)（OPEN-06） |
| GAP-02 | RAG 重排「候選集合不增不減」無集合等值斷言；檢索佇列 429 無測試 | TC-042、TC-043 | [ADR-008](../03_architecture/adr/ADR-008-rag-retrieval-only-offline-models.md) |
| GAP-03 | Agent 並存管線的**路由層**旗標隔離（四支 404／`/status` 200）無測試 | TC-046 | [ADR-011](../03_architecture/adr/ADR-011-agent-pipeline-flag-isolation.md) |
| GAP-04 | 成果包 `DELIVERY_SENSITIVE_KEYS` 脫敏無直接斷言；上傳／輸出容量上限（2 MB 已測、20 MB PNG 未測）不對稱 | TC-054、TC-008 | [`api_spec.md`](../04_design/api_spec.md) |
| GAP-05 | 維運面（安裝腳本、Docker 供應、執行資料成長、備份與刪除）**完全無自動化測試**，且部分機制根本不存在 | TC-056–058 | [`deployment_and_operations.md`](../06_ops/deployment_and_operations.md)、[`runbook-runtime-storage-growth.md`](../06_ops/runbook-runtime-storage-growth.md) |
| GAP-06 | 前端互動、3D 渲染與拖曳行為只有原始碼字串斷言，無瀏覽器層自動化；第 6 步以後的可用性只能靠人工 | TC-021–023、034 | [`UAT 計畫`](UAT_RoomPilot_Pilot_內部_2026-08-12.md) |

**退出條件與通過門檻（DEC-019）未核准前，本文件不宣告任何 GO／NO-GO。**

---

## 6. 缺陷回報格式

| 項目 | 內容 |
| :--- | :--- |
| **重現步驟** | 分支與 HEAD、`pytest` 節點 id 或八步操作序列、輸入檔（`testdata/` 路徑）、環境差異（PostgreSQL 是否啟動、金鑰是否設定） |
| **預期 vs 實際** | 預期引用 ACPT-*／FR-*；實際貼原始輸出（HTTP 狀態碼＋`detail.code`，或 pytest `--tb=line` 單行） |
| **嚴重程度** | Blocker（阻擋八步前進或產生假成果）／Major（單步功能失效但有繞道）／Minor（顯示與文案） |
| **關聯** | TC-*／FR-*／NFR-*／SCN-*／RB-*；若屬環境或測試過時，明寫「非產品缺陷」並註明分類（見 §2.2） |

---

## 7. 測試報告結論

| 項目 | 內容 |
| :--- | :--- |
| **執行摘要** | 947 收集／905 passed／35 failed／7 skipped（2026-08-12，182.16 s）。35 筆紅燈：23 環境（PostgreSQL）、7 測試過時、4 真實缺陷、1 待判定 |
| **缺陷狀態** | 開放：辨識管線 `numpy.int32` 解包缺陷（`backend/floorplan/floorplan2room.py:280`）。待處置：`tests/test_render_image_stage.py`、`tests/test_scene_v2_contract.py` 共 7 筆過時斷言。待判定：`tests/test_questionnaire_visual_catalog.py:257` |
| **殘餘風險** | 前端互動與 3D 行為無自動化（GAP-06）；型錄筆數口徑三個版本並存（GAP-01）；維運面零測試且部分機制不存在（GAP-05）；效能與備份無任何量測基礎（NFR-025） |
| **上線建議** | **不判定**——退出條件屬 DEC-019，尚待產品 owner 核准；在此之前本文件只提供基準線與缺口清單 |

> 只有實際執行過的測試能出現在報告裡；完成判定交給 `/verify` 與 [`qa_tracker.xlsx`](qa_tracker.xlsx) ②執行證據。

---

## 8. 追溯

| 項目 | ID／文件 |
| :--- | :--- |
| **上游** | DEC-019（驗收案例與通過門檻，待核准）、[`prd.md`](../01_requirements/prd.md) 的 ACPT-001..060 與 SCN-001..042、[`srs.md`](../01_requirements/srs.md) 的 FR-001..067／NFR-001..025／UC-001..003 與 §9.2 的 TC 分配 |
| **本文件產出** | TC-001..060 的層級、佐證與狀態；§2 的 NFR-024／ACPT-059 基準線；GAP-01..06 |
| **下游** | [`UAT 計畫`](UAT_RoomPilot_Pilot_內部_2026-08-12.md)（人工案例）、[`qa_tracker.xlsx`](qa_tracker.xlsx) ①測試設計／②執行證據、[`engineering_tracker.xlsx`](../03_architecture/engineering_tracker.xlsx) ①規格追溯 |
| **架構與設計** | [`sad.md`](../03_architecture/sad.md)、[ADR-005](../03_architecture/adr/ADR-005-postgres-catalog-source-of-truth.md)、[ADR-006](../03_architecture/adr/ADR-006-appliances-render-context-only.md)、[ADR-008](../03_architecture/adr/ADR-008-rag-retrieval-only-offline-models.md)、[ADR-009](../03_architecture/adr/ADR-009-server-governed-ai-generation.md)、[ADR-011](../03_architecture/adr/ADR-011-agent-pipeline-flag-isolation.md)；[`api_spec.md`](../04_design/api_spec.md)、[`lld.md`](../04_design/lld.md)、[`db_design.md`](../04_design/db_design.md) |
| **維運承接** | RB-001..RB-009（`../06_ops/`）；型錄 RB-001、生圖 RB-002、存檔 RB-003、檢索 RB-004、PDF RB-005、辨識 RB-006、擺位 RB-007、GLB RB-008、儲存成長 RB-009 |
| **待確認** | OPEN-25、OPEN-46（本文件主責）；OPEN-06、OPEN-14、OPEN-16、OPEN-39、OPEN-43（他份文件主責，本文件只記缺口） |
