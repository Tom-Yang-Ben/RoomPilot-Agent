# 測試計畫與測試案例 (Test Plan / Test Cases) - RoomPilot

> **版本:** 0.1 | **更新:** 2026-08-11 | **狀態:** 草稿
> **Owner:** 測試隨受測模組 owner；端到端整合閘門由 Bella 把關（tests/AGENTS.md:3-4）（AI 衍生，人工核准前為 TO-BE）
> **語域:** L3（工程）
> **實例:** 單例（策略一份；自動化案例即 pytest 套件本身，人工案例與證據維護於 `qa_tracker.xlsx`）
> **定位宣告:** 本文件回答「RoomPilot 的測試策略、分層現況、ACPT 覆蓋對映、執行環境與完成閘門是什麼」；不包含逐條驗收演練腳本（見 [UAT_RoomPilot_Pilot_內部_2026-08-11.md](./UAT_RoomPilot_Pilot_內部_2026-08-11.md)）、API 契約細節（見 [../04_design/api_spec.md](../04_design/api_spec.md)）與需求定義（見 [../00-registry.md](../00-registry.md)）。
> **生成:** AI 由程式碼與文件衍生｜來源版本 git yen@8863a36c

---

## 目錄

- [1. 測試範圍與策略](#1-測試範圍與策略)
- [2. 測試分層與現況](#2-測試分層與現況)
- [3. 測試套件盤點](#3-測試套件盤點)
- [4. 測試環境與執行方式](#4-測試環境與執行方式)
- [5. ACPT 範圍對映](#5-acpt-範圍對映)
- [6. 已知失敗基線（待確認）](#6-已知失敗基線待確認)
- [7. 測試案例與缺陷回報格式](#7-測試案例與缺陷回報格式)
- [8. 追溯](#8-追溯)

## 1. 測試範圍與策略

| 項目 | 內容 | 證據 |
| :--- | :--- | :--- |
| **範圍內** | REQ-001~014、FR-001~015、NFR-001~006、ACPT-001~016、SCN-001~010（[../00-registry.md](../00-registry.md) §2） | 本文件 §5 對映 |
| **範圍外** | 效能／負載測試（無案例）；資安滲測（Pilot 內部工具無認證，api_spec §4）；`frontend3d/` 次要原型的瀏覽器 E2E（僅靜態契約測試覆蓋） | 盤點 §3 無對應檔 |
| **測試紀律** | 預設決定論、離線；外部資產、PostgreSQL、OCR 權重、網路呼叫必須顯式 opt-in 或安全 skip（NFR-006）；行為測試優先於原始碼字串斷言；跨資料夾契約變更需 producer＋consumer 兩側測試；不得為接受回歸而弱化測試 | tests/AGENTS.md:5-11 |
| **進入條件** | `uv sync --extra server --extra vision --extra catalog --group dev` 完成（pyproject.toml:13-56）；`.env` 由 `.env.example` 複製（README:48）；`pytest --collect-only -q` 無收集錯誤 | §4 |
| **退出條件（最終閘門）** | focused tests 通過 → 全套 `python -m pytest -q` 對照基線（§6）無新增失敗 → `git diff --check` 乾淨（ACPT-016） | tests/AGENTS.md:13、README:121-125 |

## 2. 測試分層與現況

| 層級 | 現況 | 代表套件 | 缺口 |
| :--- | :--- | :--- | :--- |
| **單元（引擎／演算法）** | 完整：錨點、柵格、淨空、擺放規則逐條對 worked example 驗證 | `tests/test_layout_spec.py`（36）、`test_placement.py`（18）、`test_clearance.py`（10）、`test_wall_openings.py`（4） | — |
| **契約（跨模組資料／靜態資產）** | 大量：JS/HTML 靜態內容契約、payload schema、SQL/資產 manifest | `tests/test_scene_v2_contract.py`（192）、`test_furniture_engine_room_requirements_contract.py`、`test_image_manifest_contract.py`、`test_env_example_contract.py` | 字串型契約驗不到宣告存在與 CSS 選擇器命中（§6 附記） |
| **整合（FastAPI TestClient 級 API）** | 完整：八步 API 走真實 app、假外部服務（monkeypatch OpenRouter／Playwright） | `tests/test_project_workflow_api.py`（14）、`test_floorplan_vision_api.py`（7）、`test_ai_render_openrouter.py`（11）、`test_delivery_proposal_api.py`（12） | — |
| **E2E（HTTP 全鏈）** | 部分：analyze→confirm→scene HTTP 全鏈有案例；真瀏覽器操作無自動化 | `test_floorplan_vision_api.py::test_floorplan_analyze_then_confirm_http_e2e`（:24） | 無 Playwright 瀏覽器 E2E；PDF 端到端下載僅在 playwright 可用時執行（test_delivery_proposal_api.py:286） |
| **外部依賴實測（opt-in）** | 顯式 skip：PostgreSQL smoke、離線 GLB 備援、OCR 測資 | `test_catalog_10550_sql.py:95-100`、`test_catalog_six_style_contract.py:94`、`test_ocr_wiring.py:31` | 離線環境不驗 DB 真實回傳（影響 ACPT-012，見 §5） |

## 3. 測試套件盤點

`uv run pytest --collect-only -q`（2026-08-11 於 yen@8863a36c 實測）：**947 案例收集、無收集錯誤**（5.45s）。

| 位置 | 檔數 | 案例數 | 主題 |
| :--- | ---: | ---: | :--- |
| `tests/` | 81 | 865 | 下表分組 |
| `backend/agent/tests/` | 10 | 56 | MasterAgent 管線：genpic 描述（21）、master flow（7）、design knowledge（6）、furniture pipeline（5）、report／documents（8）、validation／skill docs／requirements／render pdf（9） |
| `backend/server/tests/` | 4 | 26 | 選件規則（12）、櫃體淨空（7）、agent pipeline service（4）、reconcile service（3） |

`tests/` 主題分組（括號為案例數）：

| 主題 | 代表檔案 |
| :--- | :--- |
| 場景精靈 UI／JS 契約 | `test_scene_v2_contract`（192）、`test_scene_visual_regressions`（29）、`test_scene_workflow`（15）、`test_scene_3d_lifecycle_contract`（9）、`test_scene_6_8_wizard_contract`（4）、`test_taiwan_style_cards`（7）、`test_scene_walk_edit_modes`（5） |
| 引擎與幾何 | `test_layout_spec`（36）、`test_generate_layout_characterization`（28）、`test_placement`（18）、`test_scene_layout_regions`（11）、`test_clearance`（10）、`test_scene_shell_geometry`（10）、`test_wall_openings`（4） |
| 平面圖辨識 | `test_floorplan_vision`（23）、`test_cody_room_recognition`（18）、`test_ocr_wiring`（11）、`test_floorplan_vision_api`（7）、`test_cody_pipeline_modules`（7）、`test_recognition_review_wiring`（6）、`test_floorplan_room_*`（13）、`test_dxf_room_units`（2） |
| Catalog／資料資產 | `test_cloud_models`（18）、`test_cloud_catalog_bridge`（10）、`test_catalog_six_style_contract`（8）、`test_official_catalog_sql`（7）、`test_official_cloud_catalog`（6）、`test_furniture_embeddings_sql`（6）、`test_image_manifest_contract`（6）、`test_catalog_10550_sql`（4）、`test_external_glb_resolution`（4）、`test_cloud_quarantine`（2）、`test_postgres_catalog_contract`（1） |
| 專案保存與工作流 API | `test_project_workflow_api`（14）、`test_project_store_hardening`（7）、`test_remote_render_workflow`（6）、`test_scene_calibration`（6） |
| 生圖與交付 | `test_delivery_proposal_api`（12）、`test_ai_render_openrouter`（11）、`test_palette_renders_openrouter`（8）、`test_design_manual_api`（7）、`test_render_image_stage`（5）、`test_scene_delivery`（5）、`test_cost_estimation`＋`_api`（3） |
| 問卷與需求 | `test_questionnaire_visual_catalog`（16）、`test_scene_room_requirements`（12）、`test_scene_soft_decor`（14） |
| Agent（repo 根側） | `test_agent_place`（30）、`test_agent_select`（19）、`test_agent_knowledge`（11） |
| RAG | `test_rag_domain`（13）、`test_rag_api`（6）、`test_rag_frontend`（4）、`test_semantic_cache_alignment`（6） |
| 治理／文件契約 | `test_roompilot_quality_guardrails`（7）、`test_team_ai_guidance`（4）、`test_env_example_contract`（1） |

## 4. 測試環境與執行方式

| 項目 | 內容 | 證據 |
| :--- | :--- | :--- |
| **Python** | `.venv` 為 uv 管理的 Python 3.14.6，**無 pip**（`python -m pip` 回 No module named pip，本輪實測）；README 記載的 baseline 3.12.13 與實際 .venv 版本不一致（待確認） | README:361 vs 本機實測 |
| **依賴安裝** | 一律走 uv：`uv sync --extra server --extra vision --extra catalog --group dev`；README 的 `pip install -r requirements.txt` 路徑在此環境不可用 | pyproject.toml:13-56 |
| **執行入口** | `uv run pytest -q`（等價於 README 的 `.\.venv\Scripts\python.exe -m pytest -q`） | README:122 |
| **pytest 版本** | 9.1.1 | README:369 |
| **焦點套件（README 指定）** | 辨識：`tests/test_floorplan_vision.py tests/test_floorplan_vision_api.py`；工作流：`tests/test_scene_workflow.py tests/test_project_workflow_api.py tests/test_scene_v2_contract.py` | README:130、136 |
| **管線陷阱** | `pytest ... \| tail` 的 exit code 是 tail 的，永遠 0，不可用來判定成敗 | 團隊實測慣例（待確認是否入 CI 文件） |

外部依賴 opt-in／safe-skip 對照（NFR-006 落地）：

| 依賴 | 預設行為 | 證據 |
| :--- | :--- | :--- |
| PostgreSQL（DB smoke） | 無 `.env` DB 設定或連不上即 skip | test_catalog_10550_sql.py:95-100 |
| 離線 GLB 備援包 | 未設定即 skip | test_catalog_six_style_contract.py:94 |
| Playwright Chromium | 未安裝即 skipif；API 層仍必測 503 | test_delivery_proposal_api.py:4、286、317 |
| OCR floor01 測資／快取 | 測資不存在即 skipif | test_ocr_wiring.py:31、155、test_semantic_cache_alignment.py:31-34 |
| OpenRouter（生圖） | 全程 monkeypatch 假 provider，不打網路；未設金鑰路徑測 503 | test_ai_render_openrouter.py:295 |

## 5. ACPT 範圍對映

狀態：**覆蓋**＝有直接自動化斷言；**部分**＝相鄰行為有測但驗收敘述的關鍵斷言缺；**缺口**＝無對應自動化測試（留給 UAT 或補測）。

| ACPT | 對應測試 | 狀態 |
| :--- | :--- | :--- |
| ACPT-001 | `tests/test_project_workflow_api.py::test_project_is_created_and_can_be_loaded_again`（:186） | 覆蓋 |
| ACPT-002 | `tests/test_floorplan_vision_api.py::test_floorplan_analyze_then_confirm_http_e2e`（:24；:72 斷言 `layout_json == analysis`）；「不含家具/材質欄位」的顯式負向斷言未找到 | 部分 |
| ACPT-003 | `tests/test_project_workflow_api.py::test_dxf_analysis_returns_canonical_centimeter_geometry_and_room_regions`（:384）、`test_floorplan_vision_api.py::test_builder_plan_630_two_point_calibration_can_be_confirmed`（:266）、`tests/test_scene_calibration.py` | 覆蓋 |
| ACPT-004 | `tests/test_project_workflow_api.py::test_rerunning_floorplan_analysis_invalidates_stale_structure_confirmation`（:322） | 覆蓋 |
| ACPT-005 | `client_brief` 僅作為 fixture 輸入出現（test_floorplan_vision_api.py:97 等）；schema 1.1 產出（硬/軟需求＋家電三分流）的斷言未找到 | 缺口 |
| ACPT-006 | `tests/test_generate_layout_characterization.py`、`test_scene_layout_regions.py`（`placement_variant` 分支行為） | 覆蓋 |
| ACPT-007 | `tests/test_clearance.py`、`test_placement.py`、`backend/server/tests/test_cabinet_clearance.py`、`test_layout_spec.py::test_clearance_conflict_messages_are_traditional_chinese`（:328）、`test_project_workflow_api.py::test_2d_layout_and_drag_validation_use_the_engine_with_editor_geometry`（:591） | 覆蓋 |
| ACPT-008 | `tests/test_generate_layout_characterization.py`（`validate_only` 不重排） | 覆蓋 |
| ACPT-009 | `tests/test_palette_renders_openrouter.py`（:191-196 斷言二次請求 409 `palette_already_generated`；:207 全失敗不鎖定可重試） | 覆蓋 |
| ACPT-010 | `tests/test_ai_render_openrouter.py::test_generate_then_single_batch_edit_budget`（:261） | 覆蓋 |
| ACPT-011 | `tests/test_delivery_proposal_api.py::test_engine_missing_reports_503`（:340；:356-357 斷言 `delivery_engine_not_configured`） | 覆蓋 |
| ACPT-012 | `tests/test_cloud_catalog_bridge.py::test_catalog_status_exposes_provider_and_verified_count`（:66）；8,675 筆閘門的 DB 實測在 `test_official_catalog_sql.py`／`test_catalog_10550_sql.py`，但預設環境 skip（§4） | 部分 |
| ACPT-013 | `tests/test_scene_furniture_retrieval.py::test_appliance_catalog_is_retired_from_step_six`（:145）驗家電 API 已退役；「`scene_objects` 不含家電、家電僅存在 `render_context.appliance_requirements`」的直接斷言未找到（render_context 僅出現在 fixture：test_ai_render_openrouter.py:68） | 部分 |
| ACPT-014 | `tests/test_project_store_hardening.py`（`expected_revision` 樂觀鎖）、`test_project_workflow_api.py::test_pending_save_replay_rejects_a_stale_server_version_atomically`（:199） | 覆蓋 |
| ACPT-015 | `backend/server/tests/test_agent_pipeline_service.py::test_pipeline_enabled_flag`（:17）；「status 永遠可查」的顯式斷言未逐一確認 | 部分 |
| ACPT-016 | 流程級閘門，非單一測試：全套 `pytest -q` 對照 §6 基線＋`git diff --check`（tests/AGENTS.md:13、README:121-125） | 流程 |

缺口處置：ACPT-005 與 ACPT-013 的缺失斷言列入補測候選；補上前由 [UAT](./UAT_RoomPilot_Pilot_內部_2026-08-11.md) 以人工步驟覆蓋。

## 6. 已知失敗基線（待確認）

yen 分支 HEAD 帶有**既有失敗測試**；ACPT-016 的判定是「對照基線無新增失敗」，不是全綠。**本輪（2026-08-11）未重跑全套驗證**，下表為最近一次實測（2026-08-06，yen@89ab4cd1，早於本文件基準 8863a36c 五個 commit），全部標待確認：

| 項目 | 值（待確認） |
| :--- | :--- |
| 全套結果 | 19 failed / 803 passed（2026-08-05 同 commit 為 21 failed / 787 passed，其後修掉 2 個 hash 契約） |
| 失敗分佈 | `test_scene_v2_contract`（約 11，多為 JS 靜態內容/hash 契約）、`test_scene_6_8_wizard_contract`（4）、舊 genpic 模板斷言 2（`test_genpic_prompt_carries_style_note`、`test_prompt_supplements_all_collected_info`）、`test_questionnaire_visual_catalog`（1）、`test_scene_room_requirements`（1） |
| 環境噪音 | 無 `.env` 的 worktree 會多 1 個 DB 連線失敗（`test_scene_generate_preserves_complete_test2_questionnaire`），比對基線時剔除 |

注意事項：

- 8863a36c 相對 89ab4cd1 新增了 step6/step8 功能與測試（收集數由約 810 增至 947），**基線數字必然已變動**；下次全套執行時應以 8863a36c（或當時 HEAD）重量測並更新本節。
- 取基線的可靠做法：`git worktree add`（短路徑）另開乾淨樹，用 `C:/RoomPilot-Agent/.venv/Scripts/python.exe -m pytest` 執行（`import backend` 靠 cwd 解析）。
- 既有失敗多為字串型契約測試漂移；修復時遵守 tests/AGENTS.md:11——不得為接受回歸而弱化測試。

## 7. 測試案例與缺陷回報格式

自動化案例即 pytest 套件本身（案例 ID＝`檔案::測試函式`，§5 直接引用）；人工案例（UAT）與執行證據維護於 `qa_tracker.xlsx`（①測試設計／②執行證據）。人工案例格式：

| 項目 | 內容 |
| :--- | :--- |
| **ID / Scenario** | TC-XXX，對應 SCN-*（[../00-registry.md](../00-registry.md) §2.4） |
| **Preconditions / Steps / Expected** | 前置狀態、步驟、可觀察結果 |
| **Evidence** | Screenshot / Log 路徑（Actual Result 執行時填） |

缺陷回報：重現步驟（環境＋步驟）、預期 vs 實際、嚴重度（Blocker / Major / Minor）、關聯 TC-*／FR-*／ACPT-*。測試報告結論（執行摘要、缺陷狀態、殘餘風險、GO/NO-GO）只收實際執行過的測試；狀態判定交給 `/verify`。

## 8. 追溯

| 項目 | ID／來源 |
| :--- | :--- |
| 上游 | REQ-001~014、FR-001~015、NFR-001~006、ACPT-001~016、SCN-001~010（[../00-registry.md](../00-registry.md) §2）；測試紀律 tests/AGENTS.md；驗證指令 README:119-137 |
| 對映 | §5：ACPT → pytest 案例（穩定 ID＝`檔案::測試函式`） |
| 下游 | [UAT_RoomPilot_Pilot_內部_2026-08-11.md](./UAT_RoomPilot_Pilot_內部_2026-08-11.md)（承接 §5 缺口）、`/verify` 完成判定、`qa_tracker.xlsx` 執行證據 |
| 待確認 | §6 基線全部；README Python 版本記載與實際 .venv 不一致（§4）；ACPT-005／013／015 缺失斷言的補測歸屬 owner |
