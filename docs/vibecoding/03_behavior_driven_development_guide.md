# BDD 行為驅動情境指南

> 本文件由 VibeCoding 模板 03_behavior_driven_development_guide.md 導入 RoomPilot-Agent 生成 | 基準分支 bella-local-20260726 | 2026-07-26

> **版本:** v1.0 | **更新:** 2026-07-26

---

## Gherkin 語法速查

| 關鍵字 | 用途 |
| :--- | :--- |
| `Feature` | 高層次功能,對應 RoomPilot 主流程的一個步驟或跨步驟能力 |
| `Scenario` | 具體業務場景/測試案例 |
| `Given` | 初始狀態 (Arrange) |
| `When` | 使用者操作 (Act) |
| `Then` | 預期結果 (Assert) |
| `And/But` | 連接多個步驟 |
| `Background` | 所有 Scenario 共用的前置步驟 |
| `Scenario Outline` + `Examples` | 參數化多組資料測試 |

---

## 撰寫前必讀:主流程步驟序(以 backend/server 程式碼為準)

情境中的步驟名與先後順序,一律以下列程式碼為唯一依據,不沿用任何舊文件:

| # | 內部步驟鍵 | UI 標籤(scene.html) | 說明 |
| :-- | :--- | :--- | :--- |
| 1 | `project` | 1 建立專案 | `POST /api/projects` |
| 2 | `upload` | 2 上傳平面圖 | `POST /api/projects/{id}/floorplan` |
| 3 | `recognition` | 3 確定尺寸 | `POST /api/projects/{id}/floorplan/analyze` |
| 4 | `calibration` | (與 3 共用同一面板) | 兩點比例尺校正 |
| 5 | `space_confirmation` | 4 空間與結構 | 牆/門/窗/樑柱確認 |
| 6 | `requirements` | 5 需求問卷 | 引導式 intake + Test2 視覺問卷 |
| 7 | `layout_2d` | 6 2D 家具配置 | `POST /api/scene/generate` / `layout` / `validate` |
| 8 | `white_model_3d` | 7 3D 白模 | 3D 檢視(白模) |
| 9 | `realistic_3d` | 8 即時寫實 | 3D 檢視(PBR 寫實) |
| 10 | `proposal_review` | 9 方案鎖定 | 鎖定主視角與方案 |
| 11 | `ai_render` | 10 AI 渲染 | `POST /api/projects/{id}/render-jobs` |

依據(本次逐一讀檔確認):

- 有序步驟清單(11 個內部步驟)定義於 `backend/server/static/scene_workflow.js:4-16` 的 `WORKFLOW_STEPS`;`recognition` 與 `calibration` 依 `WORKFLOW_PANEL_BY_STEP`(同檔 18-30 行)共用 `scale` 面板,所以 UI 只顯示 10 顆步驟按鈕(`backend/server/static/scene.html:22-32`,`data-workflow-count="10"`)。
- 伺服器端 `backend/server/main.py:113-125` 的 `WORKFLOW_STEPS` 是同樣 11 個名稱的 set(無序),只在 `PUT /api/projects/{id}/workflow` 驗證步驟名(`main.py:1546-1547`)。
- 步驟前置依賴 `REQUIRED_COMPLETIONS` 只在前端強制(`scene_workflow.js:43-105`)。**已知落差:伺服器端不驗順序,無法阻止跳步驟寫入**——撰寫情境時,`Then` 不得宣稱「伺服器會擋跳步」。

---

## 範本

**檔案名稱**: `[feature_name].feature`(本 repo 目前無 `features/` 目錄,此為情境文件的建議命名;見文末〈落地方式〉)

以下用主流程步驟 1-2(建立專案、上傳平面圖)作為完整範本,保留模板的標籤結構(`@happy-path` / `@sad-path` / `@edge-case`):

```gherkin
Feature: 建立專案與上傳平面圖(步驟 project → upload)
  # 對應:backend/server/main.py:1520(POST /api/projects)、main.py:1593(POST /api/projects/{id}/floorplan)

  Background:
    Given RoomPilot 伺服器已啟動(uv run uvicorn backend.server.main:app --port 8002)

  @happy-path @smoke-test
  Scenario: 建立專案後上傳 DXF 平面圖
    Given 我已建立名為「三房示範」的專案並收到 201 與 project 資料
    When 我上傳副檔名為 .dxf 的平面圖檔
    Then 我應該收到 201,回應含 upload.filename 與 upload.source_url
    And 之後透過 GET /api/projects/{id}/floorplan/source 應能取回原始檔案

  @sad-path
  Scenario: 專案名稱空白被拒絕
    When 我送出名稱為空字串的建立專案請求
    Then 我應該收到 422,錯誤碼為 project_name_required,訊息為「請輸入專案名稱。」

  @sad-path
  Scenario: 上傳空檔案被拒絕
    Given 我已建立專案
    When 我上傳一個 0 位元組的 .png 檔
    Then 我應該收到 422,錯誤碼為 empty_floorplan

  @sad-path
  Scenario: 副檔名正確但內容不是圖片
    Given 我已建立專案
    When 我上傳一個副檔名 .png 但內容為亂碼的檔案
    Then 我應該收到 422,錯誤碼為 invalid_floorplan_image

  @sad-path
  Scenario: 兩個分頁同時操作同一專案
    Given 另一個分頁已先更新過這個專案(revision 已前進)
    When 我帶著過期的 expected_revision 上傳平面圖
    Then 我應該收到 409,錯誤碼為 project_revision_conflict
    And 回應應附上最新的 project 讓前端重新載入

  @edge-case
  Scenario Outline: 平面圖副檔名白名單
    Given 我已建立專案
    When 我上傳副檔名為 "<extension>" 的平面圖檔
    Then 我應該收到狀態碼 "<status>"

    Examples:
      | extension | status |
      | .dxf      | 201    |
      | .png      | 201    |
      | .jpg      | 201    |
      | .jpeg     | 201    |
      | .gif      | 415    |
      | .pdf      | 415    |
    # 白名單定義:backend/server/main.py:111 FLOORPLAN_EXTENSIONS = (".dxf", ".png", ".jpg", ".jpeg")
    # 415 錯誤碼 unsupported_floorplan_type,訊息「只支援 DXF、PNG、JPG 或 JPEG 平面圖。」(main.py:1602-1610)
```

---

## RoomPilot 主流程情境集

### Feature 2:平面圖辨識與比例尺(步驟 recognition + calibration)

```gherkin
Feature: 平面圖辨識與兩點比例尺
  # 對應:backend/server/main.py:1797(POST /api/projects/{id}/floorplan/analyze)
  # 比例尺 UI 行為:backend/server/static/scene_calibration.js(經 tests/test_scene_calibration.py 鎖定)

  Background:
    Given 我已建立專案並成功上傳平面圖

  @happy-path
  Scenario: DXF 平面圖辨識
    Given 我已在工作流中確認圖檔內容正確(workflow.floorplan_confirmation.confirmed = true)
    And 上傳的檔案是 .dxf
    When 我啟動平面圖辨識
    Then 我應該收到 analysis 與 geometry_engine 為 "dxf"
    And 工作流應被重設為 current_step = "recognition"、completed = [project, upload, recognition]
    And 下游步驟(calibration 之後)應標記為 stale(staleFrom = "calibration")

  @happy-path
  Scenario: PNG/JPG 平面圖走 Cody 視覺辨識
    Given 我已確認圖檔內容正確,且上傳的檔案是 .png
    When 我啟動平面圖辨識
    Then 我應該收到 geometry_engine 為 "cody"

  @sad-path
  Scenario: 未確認圖檔就辨識被擋下
    Given 我尚未確認圖檔內容
    When 我啟動平面圖辨識
    Then 我應該收到 409,錯誤碼為 floorplan_confirmation_required
    And 訊息為「請先確認圖檔內容正確，才能開始辨識。」(訊息內逗號為全形,照 main.py 原文)

  @sad-path
  Scenario Outline: 辨識失敗有明確錯誤碼
    Given 我已確認圖檔內容正確
    When 我對 "<file_kind>" 啟動辨識且引擎無法解析
    Then 我應該收到 422,錯誤碼為 "<code>"

    Examples:
      | file_kind        | code                     |
      | 無牆體幾何的 DXF | dxf_parse_failed         |
      | 無法辨識的影像   | cody_recognition_failed  |

  @happy-path
  Scenario: 兩點比例尺建立公分尺度
    Given 辨識已完成且預覽圖已顯示
    When 我在預覽圖上點選兩個點並輸入兩點的實際公分距離
    Then 比例尺校正應成立,座標以公分為單位
    And 「空間與結構」步驟應被解鎖
```

### Feature 3:工作流草稿保存與多分頁併發(貫穿全部步驟)

```gherkin
Feature: 工作流草稿保存(樂觀鎖)
  # 對應:backend/server/main.py:1542(PUT /api/projects/{id}/workflow)
  # 上限:backend/server/project_store.py:11 MAX_WORKFLOW_BYTES = 2 MB

  Background:
    Given 我已建立專案

  @happy-path
  Scenario: 保存合法步驟的草稿
    When 我以 current_step = "layout_2d" 保存工作流草稿
    Then 我應該收到 200 與更新後的 project

  @sad-path
  Scenario: 未知步驟名被拒絕
    When 我以 current_step = "not_a_step" 保存工作流草稿
    Then 我應該收到 422,錯誤為 invalid_workflow_step

  @sad-path
  Scenario: 草稿超過 2 MB
    When 我保存超過 2 MB 的 workflow JSON
    Then 我應該收到 413,錯誤碼為 workflow_too_large
    And 訊息為「專案草稿內容超過 2 MB，請移除大型暫存資料後再儲存。」(訊息內逗號為全形,照 main.py 原文)

  @sad-path
  Scenario: 另一分頁已更新,revision 衝突
    Given 另一個分頁已保存過這個專案
    When 我帶著過期的 expected_revision 保存草稿
    Then 我應該收到 409,錯誤碼為 project_revision_conflict,且回應附最新 project

  @edge-case
  Scenario: 離線補送(replay)必須綁定原始基準版本
    When 我以 replay_pending = true 但缺 base_updated_at 送出補送
    Then 我應該收到 422,錯誤為 pending_save_base_version_required
    # replay 只能對「當初開始編輯時的伺服器版本」成立,對過期版本會被原子拒絕
```

### Feature 4:需求問卷(步驟 requirements)

```gherkin
Feature: 引導式需求問卷與 Test2 視覺問卷
  # 對應:backend/server/main.py:2123(POST /api/agent/intake/answer)、intake_service.py:13-20(六步定義)
  # 視覺問卷:GET /api/questionnaire/visual-catalog(main.py:1984 起)

  @happy-path
  Scenario: 引導式 intake 依六步推進
    When 我啟動需求訪談(POST /api/agent/intake/start)
    Then 我應該收到 session_id、目前步驟與提問
    And 訪談步驟依序為 space_type → occupants → needs → style → materials → constraints

  @happy-path
  Scenario: 未設定 LLM 時自動降級而非報錯
    Given 環境未設定 OPENROUTER_API_KEY 與 OPENROUTER_INTAKE_ENABLED
    When 我啟動需求訪談
    Then 我應該收到 mode = "guided_fallback",訪談仍可完成(規則式抽取)

  @sad-path
  Scenario: 回答缺欄位被拒絕
    When 我送出缺少 step 或 answer 的回答
    Then 我應該收到 422,訊息為「step 與 answer 皆為必要欄位。」

  @happy-path
  Scenario: 已確認的房間預選共通問卷題
    Given 空間與結構步驟已確認出房間清單
    When 我進入 Test2 視覺問卷
    Then 各房共通且尚未作答的題目應被預選,不重複詢問

  @happy-path
  Scenario: 問卷狀態隨專案保存與重載
    Given 我已完成部分問卷
    When 我保存專案後重新載入
    Then 問卷已作答內容應完整還原
```

### Feature 5:2D 家具配置(步驟 layout_2d)

```gherkin
Feature: 2D 家具配置與拖曳驗證
  # 對應:backend/server/main.py:2284(POST /api/scene/generate)、2330(POST /api/scene/layout)、2607(POST /api/scene/validate)
  # 選件:main.py:2220(POST /api/agent/furniture/select)

  @happy-path
  Scenario: 由問卷產生場景
    Given 我已完成需求問卷
    When 我提交場景生成請求且未指定房間尺寸
    Then 系統應以預設 420 x 360 公分的房間生成
    And 回應應含 scene_objects 與擺位失敗修復報告(placement_resolution_report)

  @happy-path
  Scenario: 手動拖曳過的家具不被重排
    Given 場景中有一件我拖曳定位並標記 position_locked 的家具
    When 我要求引擎重算全場座標(POST /api/scene/layout)
    Then 該家具位置仍合法時應保持原位,其餘家具由引擎重排

  @edge-case
  Scenario Outline: 佈局變體參數
    When 我以 placement_variant = "<variant>" 要求重算
    Then 系統應以 "<effective>" 案執行

    Examples:
      | variant | effective |
      | A       | A         |
      | B       | B         |
      | c       | A         |
    # 非 A/B 一律視為 A(main.py:2345-2347)

  @sad-path
  Scenario: 拖曳落點超出房間
    When 我把一件家具拖到房間邊界之外並要求驗證
    Then 我應該收到 ok = false
    And reason 為「超出房間範圍(需完整放在某一間房內,不能跨牆)」

  @sad-path
  Scenario: LLM 選件違反房型規則時降級
    Given LLM 回傳的選件把餐桌配進浴室
    When 伺服器驗證這份選件
    Then 選件來源應降級為 "local_rules"(本地規則重選),不得沿用違規結果
```

### Feature 6:3D 檢視與自動軟裝(步驟 white_model_3d → realistic_3d)

```gherkin
Feature: 3D 檢視閘門與自動軟裝
  # 對應:backend/server/static/scene_workflow.js:43-105(前端閘門)、main.py:2453 起(POST /api/scene/decorate)

  @happy-path
  Scenario: 步驟閘門依序解鎖
    Given 我尚未完成 2D 家具配置
    When 我嘗試進入 3D 白模步驟
    Then 前端應阻擋並停留在未完成的步驟
    # 注意:此閘門只在前端強制,伺服器端不驗順序(見〈撰寫前必讀〉)

  @happy-path
  Scenario: 白模允許零家具方案
    Given 我在 2D 配置明確選擇不放任何家具
    When 我進入 3D 白模
    Then 白模應可生成,不因家具數為零而報錯

  @happy-path
  Scenario: 自動軟裝經引擎驗證後才入場
    Given 我已有一個客廳的 3D 場景
    When 我要求自動軟裝(地毯/植栽/燈具/窗簾)
    Then 回應的 decor_summary 應列出 requested 與實際 placed 的角色
    And engine 應為 "furniture_engine"
    And 放不下的軟裝應被移除,不得以失敗標記留在場景中

  @sad-path
  Scenario: 型錄無可用軟裝 GLB
    Given 型錄中找不到符合尺寸的軟裝模型
    When 我要求自動軟裝
    Then 我仍應收到 200,地毯與植栽照常配置
    And decor_summary.skipped 應列出 light 與略過原因

  @sad-path
  Scenario: 上游確認被修改時下游結果作廢
    Given 我已完成 3D 白模
    When 我回頭修改空間與結構的確認內容
    Then 下游步驟(問卷之後的結果)應被標記為失效,需重新產生
```

---

## 對照 tests/:情境如何落地

### 現況(本次實測)

- repo **沒有** Gherkin 執行器:`grep pytest-bdd|behave|gherkin` 於 `pyproject.toml` 與 `uv.lock` 零命中,也沒有 `features/` 目錄。
- BDD 實際落地方式 = **行為命名的 pytest 測試** + `fastapi.testclient.TestClient` 直接打路由(例:`tests/test_project_workflow_api.py`、`tests/test_floorplan_vision_api.py` 檔頭皆為 `client = TestClient(app)`)。測試函式名本身就是行為敘述,例如 `test_floorplan_analysis_explains_missing_confirmation_instead_of_stalling`。
- `tests/` 共 47 個 `test_*.py`(ls 實數)。執行方式:`uv run pytest tests/`(`pyproject.toml` 的 `[tool.pytest.ini_options]` 已設 `pythonpath = ["."]`)。

### 情境 ↔ 現有測試對照表(測試名皆為本次 grep 實查)

| 本文情境 | 對應現有測試 |
| :--- | :--- |
| 副檔名白名單(Feature 1 @edge-case) | `tests/test_project_workflow_api.py::test_floorplan_upload_accepts_only_dxf_png_and_jpeg` |
| 未確認圖檔先擋辨識(Feature 2 @sad-path) | `tests/test_project_workflow_api.py::test_floorplan_analysis_explains_missing_confirmation_instead_of_stalling`、`tests/test_scene_workflow.py::test_floorplan_confirmation_and_completed_upload_are_required_before_analysis` |
| 重新辨識作廢下游 | `tests/test_project_workflow_api.py::test_rerunning_floorplan_analysis_invalidates_stale_structure_confirmation` |
| DXF 輸出公分契約與房間區域 | `tests/test_project_workflow_api.py::test_dxf_analysis_returns_canonical_centimeter_geometry_and_room_regions` |
| 兩點比例尺(Feature 2 @happy-path) | `tests/test_scene_calibration.py::test_two_image_points_and_known_length_create_scale_calibration`、`::test_calibration_action_is_ready_after_two_points_and_centimeter_value` |
| 比例確認解鎖空間確認 | `tests/test_scene_workflow.py::test_confirmed_scale_unlocks_space_confirmation_and_state_can_be_restored` |
| 樂觀鎖與離線補送(Feature 3) | `tests/test_project_workflow_api.py::test_pending_save_replay_rejects_a_stale_server_version_atomically`、`tests/test_scene_workflow.py::test_pending_save_replays_only_against_the_server_version_it_started_from` |
| 十步 UI/單面板共用 | `tests/test_scene_workflow.py::test_scene_exposes_the_final_ten_step_workflow`、`::test_nine_step_workflow_uses_one_panel_for_recognition_and_calibration` |
| 步驟閘門(Feature 6) | `tests/test_scene_workflow.py::test_each_gate_blocks_the_next_stage_until_confirmation_is_valid` |
| 上游改動作廢下游(Feature 6 @sad-path) | `tests/test_scene_workflow.py::test_editing_upstream_confirmation_invalidates_downstream_results` |
| 問卷房間預選(Feature 4) | `tests/test_questionnaire_visual_catalog.py::test_confirmed_room_prefills_only_shared_unanswered_questions` |
| 問卷狀態保存重載(Feature 4) | `tests/test_questionnaire_visual_catalog.py::test_questionnaire_state_survives_project_save_and_reload` |
| 極端偏好影響家具規格 | `tests/test_questionnaire_visual_catalog.py::test_extreme_preferences_change_furniture_specs_before_layout` |
| LLM 選件降級(Feature 5 @sad-path) | `tests/test_project_workflow_api.py::test_agent_furniture_selection_falls_back_when_llm_violates_room_rules`、`::test_agent_furniture_selection_uses_server_side_local_rules_without_llm` |
| 選件白名單/房型/副件規則 | `tests/test_agent_select.py`(17 個測試,含 `test_parse_applies_room_affinity_and_companion_dependency`) |
| 2D 拖曳走引擎驗證(Feature 5) | `tests/test_project_workflow_api.py::test_2d_layout_and_drag_validation_use_the_engine_with_editor_geometry`、`tests/test_scene_layout_regions.py::test_manual_wall_snap_is_resolved_by_the_backend_layout_engine` |
| 佈局變體 B(Feature 5 @edge-case) | `tests/test_scene_layout_regions.py::test_layout_variant_b_uses_a_different_engine_validated_candidate` |
| 擺位碰撞/淨空幾何基礎 | `tests/test_placement.py`(18 個測試)、`tests/test_clearance.py`(10 個測試) |
| 白模零家具(Feature 6) | `tests/test_scene_workflow.py::test_white_model_allows_an_explicit_zero_furniture_plan` |
| 自動軟裝(Feature 6) | `tests/test_scene_soft_decor.py::test_auto_decor_adds_four_visible_glbs_through_the_engine`、`::test_empty_room_does_not_receive_scattered_decor` |

### 新行為的落地流程

1. 先以本檔格式寫 Gherkin 情境(收進本檔或 PR 描述),步驟名與順序對照〈撰寫前必讀〉的表。
2. 翻譯成 `tests/test_*.py` 的行為命名測試:`Given` = 建 `TestClient` 與前置資料、`When` = 呼叫路由、`Then` = 斷言狀態碼 + 錯誤 `code` 欄位(錯誤碼與訊息以 `backend/server/main.py` 實作為準,不自創)。
3. 執行 `uv run pytest tests/` 驗證。
4. 待辦(未決策):是否引入 pytest-bdd 讓 `.feature` 檔可直接執行——目前無此依賴,引入與否待團隊裁決。

---

## 最佳實踐

1. **一個 Scenario 只測一件事**
2. **使用陳述式** -- `Then 我應該收到 409,錯誤碼為 project_revision_conflict`(非 `Then 系統回傳衝突`)
3. **避免 UI 細節** -- `When 我確認平面圖內容正確`(非 `When 我點選綠色確認按鈕`)
4. **從使用者角度編寫** -- 非技術人員也能讀懂
5. **(RoomPilot 補充)步驟名與順序只認程式碼** -- 內部步驟鍵以 `backend/server/static/scene_workflow.js` 的 `WORKFLOW_STEPS` 為準;錯誤碼以 `backend/server/main.py` 為準;舊文件(含曾出現的「問卷開頭」「八步驟」口徑)一律不採用
