# BDD 行為驅動情境指南

> 本文件由 VibeCoding v5.0 模板 01_requirements/bdd_guide.md 導入 RoomPilot-Agent | 基準：分支 django-skill、commit a2179f7e、日期 2026-08-04

> **版本:** v2.0 | **更新:** 2026-08-04
>
> 先行素材：`docs/vibecoding/03_behavior_driven_development_guide.md`（2026-07-26 對舊分支撰寫）。該版的「十步 UI」「44 條路由」「47 支測試」等數字已過期（port 8002 不在過期之列，至今仍是啟動基準），本文件所有數字、行號、錯誤碼均對現行工作樹重查；沿用的情境僅保留結構，事實逐條更新。

---

## Gherkin 語法速查

| 關鍵字 | 用途 |
| :--- | :--- |
| `Feature` | 高層次功能，對應 RoomPilot 主流程的一個步驟、或一個獨立子系統（工程文件、RAG、型錄管理） |
| `Scenario` | 具體業務場景/測試案例 |
| `Given` | 初始狀態 (Arrange) |
| `When` | 使用者操作 (Act) |
| `Then` | 預期結果 (Assert) |
| `And/But` | 連接多個步驟 |
| `Background` | 所有 Scenario 共用的前置步驟 |
| `Scenario Outline` + `Examples` | 參數化多組資料測試 |

---

## 撰寫前必讀：主流程步驟序（以 backend/server 程式碼為準）

情境中的步驟名與先後順序，一律以下列程式碼為唯一依據，不沿用任何舊文件（含舊導入版的「十步 UI」口徑——現行 UI 已收斂為 **8 顆步驟按鈕**）：

| # | 內部步驟鍵 | UI 標籤（scene.html） | 說明 |
| :-- | :--- | :--- | :--- |
| 1 | `project` | 1 建立專案 | `POST /api/projects`（main.py:2024） |
| 2 | `upload` | 2 上傳平面圖 | `POST /api/projects/{id}/floorplan`（main.py:2097） |
| 3 | `recognition` | 3 確定尺寸 | `POST /api/projects/{id}/floorplan/analyze`（main.py:2315） |
| 4 | `calibration` | （與 3 共用 `scale` 面板） | 兩點比例尺校正 |
| 5 | `space_confirmation` | 4 空間與結構 | 牆/門/窗/樑柱確認 |
| 6 | `requirements` | 5 需求問卷 | 引導式 intake + Test2 視覺問卷 |
| 7 | `layout_2d` | 6 配置與預覽 | `POST /api/scene/generate`（main.py:3033）/ `layout`（3136）/ `validate`（3492） |
| 8 | `white_model_3d` | （有面板、無獨立按鈕） | 3D 白模檢視 |
| 9 | `realistic_3d` | （有面板、無獨立按鈕） | 3D 即時寫實檢視 |
| 10 | `proposal_review` | 7 方案鎖定與視角 | 鎖定主視角與方案 |
| 11 | `ai_render` | 8 AI 渲染與成果包 | `POST /api/projects/{id}/render-jobs`（202；main.py:2270） |

依據（本次逐一讀檔確認）：

- 有序步驟清單（11 個內部步驟）定義於 `backend/server/static/scene_workflow.js:4-16` 的 `WORKFLOW_STEPS`；面板對映 `WORKFLOW_PANEL_BY_STEP`（同檔 18-30 行）讓 `recognition` 與 `calibration` 共用 `scale` 面板、`white_model_3d`/`realistic_3d` 各有面板但無獨立按鈕，所以 UI 只顯示 **8 顆**步驟按鈕（`backend/server/static/scene.html:24-33`，`data-workflow-count="8"`）。
- 伺服器端 `backend/server/main.py:183-195` 的 `WORKFLOW_STEPS` 是同樣 11 個名稱的 set（無序），只在 `PUT /api/projects/{id}/workflow` 驗證步驟名（main.py:2050-2051，非法回 422 `invalid_workflow_step`）。
- 步驟前置依賴只在前端強制（`scene_workflow.js` 的 validCompletion 與 markDownstreamStale）。**已知落差：伺服器端不驗順序，無法阻止跳步驟寫入**——撰寫情境時，`Then` 不得宣稱「伺服器會擋跳步」。
- 全站 HTTP 路由共 **63 條**（main.py 46 ＋ rag_api.py 5 ＋ catalog_admin.py 4 ＋ engineering/api.py 8；grep 逐條核對）。啟動基準 port **8002**（README.md:30、46；被占用改 8023，README.md:35）。

---

## 範本

**檔案名稱**: `[feature_name].feature`（本 repo 目前無 `features/` 目錄，此為情境文件的建議命名；見文末〈對照 tests/〉）

以下用主流程步驟 1-2（建立專案、上傳平面圖）作為完整範本，保留模板的標籤結構（`@happy-path` / `@sad-path` / `@edge-case`）：

```gherkin
Feature: 建立專案與上傳平面圖（步驟 project → upload）
  # 對應：backend/server/main.py:2024（POST /api/projects）、main.py:2097（POST /api/projects/{id}/floorplan）

  Background:
    Given RoomPilot 伺服器已啟動（uvicorn backend.server.main:app --host 127.0.0.1 --port 8002）

  @happy-path @smoke-test
  Scenario: 建立專案後上傳 DXF 平面圖
    Given 我已建立名為「三房示範」的專案並收到 201 與 project 資料
    When 我上傳副檔名為 .dxf 的平面圖檔
    Then 我應該收到 201
    And 之後透過 GET /api/projects/{id}/floorplan/source 應能取回原始檔案

  @sad-path
  Scenario: 專案名稱空白被拒絕
    When 我送出名稱為空字串的建立專案請求
    Then 我應該收到 422，錯誤碼為 project_name_required（main.py:2031）

  @sad-path
  Scenario: 上傳空檔案被拒絕
    Given 我已建立專案
    When 我上傳一個 0 位元組的 .png 檔
    Then 我應該收到 422，錯誤碼為 empty_floorplan（main.py:1957）

  @sad-path
  Scenario: 副檔名正確但內容不是圖片
    Given 我已建立專案
    When 我上傳一個副檔名 .png 但內容為亂碼的檔案
    Then 我應該收到 422，錯誤碼為 invalid_floorplan_image（main.py:1990）

  @sad-path
  Scenario: 兩個分頁同時操作同一專案
    Given 另一個分頁已先更新過這個專案（revision 已前進）
    When 我帶著過期的 expected_revision 上傳平面圖
    Then 我應該收到 409，錯誤碼為 project_revision_conflict（main.py:2130）
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
    # 白名單定義：backend/server/main.py:164 FLOORPLAN_EXTENSIONS = (".dxf", ".png", ".jpg", ".jpeg")
    # 415 錯誤碼 unsupported_floorplan_type，回應附 allowed_extensions（main.py:2106-2112）
```

---

## RoomPilot 主流程情境集

### Feature 2：平面圖辨識與比例尺（步驟 recognition + calibration）

```gherkin
Feature: 平面圖辨識與兩點比例尺
  # 對應：backend/server/main.py:2315（POST /api/projects/{id}/floorplan/analyze）
  # 比例尺 UI 行為：backend/server/static/scene_calibration.js（經 tests/test_scene_calibration.py 鎖定）

  Background:
    Given 我已建立專案並成功上傳平面圖

  @happy-path
  Scenario: DXF 平面圖辨識
    Given 我已在工作流中確認圖檔內容正確
    And 上傳的檔案是 .dxf
    When 我啟動平面圖辨識
    Then 我應該收到 geometry_engine 為 "dxf"（main.py:2351）
    And 下游步驟的舊確認結果應被標記為失效

  @happy-path
  Scenario: PNG/JPG 平面圖走 Cody 視覺辨識
    Given 我已確認圖檔內容正確，且上傳的檔案是 .png
    When 我啟動平面圖辨識
    Then 我應該收到 geometry_engine 為 "cody"（main.py:2368）

  @sad-path
  Scenario: 未確認圖檔就辨識被擋下
    Given 我尚未確認圖檔內容
    When 我啟動平面圖辨識
    Then 我應該收到 409，錯誤碼為 floorplan_confirmation_required
    And 訊息為「請先確認圖檔內容正確，才能開始辨識。」（逗號為全形，照 main.py:2320-2327 原文）

  @sad-path
  Scenario Outline: 辨識失敗有明確錯誤碼
    Given 我已確認圖檔內容正確
    When 我對 "<file_kind>" 啟動辨識且引擎無法解析
    Then 我應該收到 422，錯誤碼為 "<code>"

    Examples:
      | file_kind        | code                    |
      | 無牆體幾何的 DXF | dxf_parse_failed        |
      | 無法辨識的影像   | cody_recognition_failed |
    # 錯誤碼出處：main.py:2341、main.py:2363

  @happy-path
  Scenario: 兩點比例尺建立公分尺度
    Given 辨識已完成且預覽圖已顯示
    When 我在預覽圖上點選兩個點並輸入兩點的實際公分距離
    Then 比例尺校正應成立，座標以公分為單位
    And 「空間與結構」步驟應被解鎖
```

### Feature 3：工作流草稿保存與多分頁併發（貫穿全部步驟）

```gherkin
Feature: 工作流草稿保存（樂觀鎖）
  # 對應：backend/server/main.py:2046（PUT /api/projects/{id}/workflow）
  # 上限：backend/server/project_store.py:13 MAX_WORKFLOW_BYTES = 2 MB

  Background:
    Given 我已建立專案

  @happy-path
  Scenario: 保存合法步驟的草稿
    When 我以 current_step = "layout_2d" 保存工作流草稿
    Then 我應該收到 200 與更新後的 project

  @sad-path
  Scenario: 未知步驟名被拒絕
    When 我以 current_step = "not_a_step" 保存工作流草稿
    Then 我應該收到 422，錯誤為 invalid_workflow_step（main.py:2051）

  @sad-path
  Scenario: 草稿超過 2 MB
    When 我保存超過 2 MB 的 workflow JSON
    Then 我應該收到 413，錯誤碼為 workflow_too_large
    And 訊息為「專案草稿內容超過 2 MB，請移除大型暫存資料後再儲存。」（逗號為全形，照 main.py:2087-2093 原文）

  @sad-path
  Scenario: 另一分頁已更新，revision 衝突
    When 我帶著過期的 expected_revision 保存草稿
    Then 我應該收到 409，錯誤碼為 project_revision_conflict，且回應附最新 project（main.py:2080）

  @edge-case
  Scenario: 離線補送（replay）必須綁定原始基準版本
    When 我以 replay_pending = true 但缺 base_updated_at 送出補送
    Then 我應該收到 422，錯誤為 pending_save_base_version_required（main.py:2066）
    # replay 只能對「當初開始編輯時的伺服器版本」成立；前端判斷見 scene_workflow.js shouldReplayPendingSave
```

### Feature 4：需求問卷（步驟 requirements）

```gherkin
Feature: 引導式需求問卷與 Test2 視覺問卷
  # 對應：backend/server/main.py:2842（POST /api/agent/intake/start）、2849（POST /api/agent/intake/answer）
  # 六步定義：backend/server/intake_service.py:13-20
  # 視覺問卷：GET /api/questionnaire/visual-catalog（main.py:2619）

  @happy-path
  Scenario: 引導式 intake 依六步推進
    When 我啟動需求訪談（POST /api/agent/intake/start）
    Then 我應該收到 session_id、目前步驟與提問
    And 訪談步驟依序為 space_type → occupants → needs → style → materials → constraints

  @happy-path
  Scenario: 未設定 LLM 時自動降級而非報錯
    Given 環境未設定 OPENROUTER_API_KEY 或 OPENROUTER_INTAKE_ENABLED != "1"
    When 我啟動需求訪談
    Then 我應該收到 mode = "guided_fallback"，訪談仍可完成（規則式抽取；intake_service.py:157-164）

  @sad-path
  Scenario: 回答缺欄位被拒絕
    When 我送出缺少 step 或 answer 的回答
    Then 我應該收到 422，訊息為「step 與 answer 皆為必要欄位。」（main.py:2855）

  @happy-path
  Scenario: 已確認的房間預選共通問卷題
    Given 空間與結構步驟已確認出房間清單
    When 我進入 Test2 視覺問卷
    Then 各房共通且尚未作答的題目應被預選，不重複詢問

  @happy-path
  Scenario: 問卷狀態隨專案保存與重載
    Given 我已完成部分問卷
    When 我保存專案後重新載入
    Then 問卷已作答內容應完整還原
```

### Feature 5：2D 家具配置（步驟 layout_2d）

```gherkin
Feature: 2D 家具配置與拖曳驗證
  # 對應：backend/server/main.py:3033（POST /api/scene/generate）、3136（POST /api/scene/layout）、3492（POST /api/scene/validate）
  # 選件：main.py:2948（POST /api/agent/furniture/select）
  # 合法性唯一裁決者：backend/engine/（CLAUDE.md 產品邊界）

  @happy-path
  Scenario: 由問卷產生場景
    Given 我已完成需求問卷
    When 我提交場景生成請求且未指定房間尺寸
    Then 系統應以預設 420 x 360 公分的房間生成（main.py:3074-3084）
    And 回應應含 scene_objects 與擺位失敗修復報告 placement_resolution_report（main.py:3214）

  @happy-path
  Scenario: 手動拖曳過的家具不被重排
    Given 場景中有一件我拖曳定位並標記 position_locked 的家具
    When 我要求引擎重算全場座標（POST /api/scene/layout）
    Then 該家具位置仍合法時應保持原位，其餘家具由 furniture_engine 重排（main.py:3138-3141、3191）

  @edge-case
  Scenario Outline: 佈局變體參數
    When 我以 placement_variant = "<variant>" 要求重算
    Then 系統應以 "<effective>" 案執行

    Examples:
      | variant | effective |
      | A       | A         |
      | B       | B         |
      | c       | A         |
    # 非 A/B 一律視為 A（main.py:3152-3154）

  @sad-path
  Scenario: 拖曳落點超出房間
    When 我把一件家具拖到房間邊界之外並要求驗證
    Then 我應該收到 ok = false 與可讀的拒絕理由

  @sad-path
  Scenario: LLM 選件違反房型規則時降級
    Given LLM 回傳的選件把餐桌配進浴室
    When 伺服器驗證這份選件
    Then 選件來源應降級為 "local_rules"（本地規則重選，main.py:3007），不得沿用違規結果
```

### Feature 6：3D 檢視與自動軟裝（步驟 white_model_3d → realistic_3d）

```gherkin
Feature: 3D 檢視閘門與自動軟裝
  # 對應：backend/server/static/scene_workflow.js（前端閘門）、main.py:3316（POST /api/scene/decorate）

  @happy-path
  Scenario: 步驟閘門依序解鎖
    Given 我尚未完成 2D 家具配置
    When 我嘗試進入 3D 白模面板
    Then 前端應阻擋並停留在未完成的步驟
    # 注意：此閘門只在前端強制，伺服器端不驗順序（見〈撰寫前必讀〉）

  @happy-path
  Scenario: 白模允許零家具方案
    Given 我在 2D 配置明確選擇不放任何家具
    When 我進入 3D 白模
    Then 白模應可生成，不因家具數為零而報錯

  @happy-path
  Scenario: 自動軟裝經引擎驗證後才入場
    Given 我已有一個客廳的 3D 場景
    When 我要求自動軟裝（POST /api/scene/decorate）
    Then 回應的 decor_summary 應列出實際入場的角色，engine 應為 "furniture_engine"（main.py:3479-3487）
    And 放不下或找不到模型的軟裝應列入 decor_summary.skipped 並附原因（main.py:3265、3300），不得以失敗標記留在場景中

  @sad-path
  Scenario: 上游確認被修改時下游結果作廢
    Given 我已完成 3D 白模
    When 我回頭修改空間與結構的確認內容
    Then 下游步驟的結果應被標記為失效，需重新產生
```

---

## 新子系統情境集（舊導入版未涵蓋）

### Feature 7：工程文件 MVP（backend/server/engineering/）

契約：`docs/contracts/ENGINEERING_DOCUMENT_MVP.md`。流程固定為 **snapshot → lock → packages → jobs → documents**，8 條路由掛在 prefix `/api/v1`（engineering/api.py:50）。

```gherkin
Feature: 設計師鎖定後產生工程文件包
  # 對應：backend/server/engineering/api.py（PUT/GET snapshot:107/153、POST lock:325、
  #   POST engineering-packages:172（202）、GET jobs/{id}:271、GET packages/{id}:281、GET documents/{id}/download:294）

  Background:
    Given 專案已完成方案鎖定並具備某 revision 的場景資料

  @happy-path
  Scenario: snapshot → lock → package 的完整旅程
    When 我 PUT 該 revision 的 snapshot
    And 我 POST lock 並附 confirmed_by
    And 我 POST engineering-packages
    Then 我應該收到 202 與 status = "queued" 的 job（job_id 形如 job_<12 碼 hex>）
    And 輪詢 GET /api/v1/jobs/{job_id} 直到完成後，應取得 package_id 與 documents 清單

  @sad-path
  Scenario: 路徑與 payload 不一致
    When 我 PUT snapshot 但 URL 的 project_id/revision 與 payload 不一致
    Then 我應該收到 422，error_code 為 PATH_PAYLOAD_MISMATCH（api.py:120）

  @sad-path
  Scenario: 已鎖定的 revision 不可被覆寫
    Given 該 revision 已鎖定
    When 我再次 PUT 同一 revision 的 snapshot
    Then 我應該收到 409，error_code 為 LOCKED_REVISION_CANNOT_BE_OVERWRITTEN（api.py:130）

  @sad-path
  Scenario: 專案已前進，快照過期
    Given 專案 revision 已前進
    When 我對舊 revision 執行 snapshot 或 lock
    Then 我應該收到 409，error_code 為 SNAPSHOT_SOURCE_REVISION_STALE（api.py:138、348）

  @sad-path
  Scenario: 未鎖定就要求產包
    Given snapshot 存在但 approval_status 不是 "designer_confirmed"（api.py:191）
    When 我 POST engineering-packages
    Then 我應該收到 409，error_code 為 REVISION_NOT_LOCKED（api.py:195）

  @sad-path
  Scenario Outline: 查無資源的一致錯誤碼
    When 我查詢不存在的 "<resource>"
    Then 我應該收到 404，error_code 為 "<code>"

    Examples:
      | resource | code               |
      | snapshot | SNAPSHOT_NOT_FOUND |
      | job      | JOB_NOT_FOUND      |
      | package  | PACKAGE_NOT_FOUND  |

  @edge-case
  Scenario: 文件下載限定在工程輸出目錄內
    When 我以竄改過的 document_id 嘗試下載 .runtime/engineering 之外的檔案
    Then 下載應被拒絕（路徑以 is_relative_to 防護，api.py:295-303）
```

### Feature 8：家具 RAG 檢索（backend/spatial_data/rag/ 經 rag_api.py）

契約：`docs/contracts/POSTGRESQL_FURNITURE_RAG_RUNTIME.md`。管線：LLM parser → PostgreSQL pgvector → reranker（service.py:1）。

```gherkin
Feature: 家具 RAG 檢索與非同步 job
  # 對應：backend/server/rag_api.py（GET /rag:136、GET /api/rag/status:141、POST /api/rag/search:146、
  #   POST /api/rag/search/jobs:155（202）、GET /api/rag/search/jobs/{job_id}:187）

  @happy-path
  Scenario: 就緒狀態先於檢索
    When 我查詢 GET /api/rag/status
    Then 回應應揭露就緒 blocker（如 embedding 模型快取缺失、pgvector 表無資料）

  @happy-path
  Scenario: 非同步檢索 job 輪詢
    When 我 POST /api/rag/search/jobs 提交受控詞彙檢索句
    Then 我應該收到 202 與 job_id
    And 輪詢 GET /api/rag/search/jobs/{job_id} 應回報進度與最終結果

  @sad-path
  Scenario: 同時 job 超過容量上限
    Given 已有 1 個進行中的檢索 job（RAG_JOB_MAX_ACTIVE = 1，rag_api.py:30）
    When 我再提交一個 job
    Then 我應該收到 429，錯誤碼為 rag_job_capacity_reached（rag_api.py:163-166）

  @sad-path
  Scenario: 查詢不存在的 job
    When 我查詢一個不存在的 job_id
    Then 我應該收到 404，錯誤碼為 rag_job_not_found（rag_api.py:194）

  @edge-case
  Scenario: 上游失敗細節不外洩
    Given 上游（LLM/DB）失敗
    When 我輪詢該 job
    Then 回應只含服務層級錯誤，不含上游內部細節
    # 由 tests/test_rag_api.py::test_rag_job_api_hides_upstream_failure_detail 鎖定
```

撰寫檢索句時，口語需求 → 受控詞彙的對映規則使用專案 skill `.claude/skills/roompilot-furniture-query/`（六風格十八色卡、24 氛圍詞、19 家具群組；0 筆時放寬順序固定為尺寸 → 價格 → 品項 → 房型，SKILL.md:162-168），並以 `lint_query.py` 核對後才寫進情境的 `When`。

### Feature 9：型錄管理 CRUD（backend/server/catalog_admin.py）

契約：`docs/contracts/POSTGRESQL_CATALOG_CRUD_PHASE2.md`（PostgreSQL 五階段之一；Phase1/3/4/5 見 docs/contracts/POSTGRESQL_*.md 與 scripts/sql/、scripts/project_store/、scripts/runtime_catalog/）。

```gherkin
Feature: 家具型錄管理寫入（fail-closed）
  # 對應：backend/server/catalog_admin.py，prefix /api/admin/furniture（:29）
  #   POST:234（201）、GET:252、PATCH:274、DELETE:294

  @sad-path
  Scenario: 未設定 token 時整組 API 關閉
    Given 伺服器未設定管理 token
    When 我呼叫任一 /api/admin/furniture 端點
    Then 我應該收到 401，錯誤碼為 catalog_admin_unauthorized（catalog_admin.py:195-200）

  @sad-path
  Scenario: 樂觀鎖衝突
    Given 另一位管理者已更新同一筆家具
    When 我帶過期版本 PATCH 這筆家具
    Then 我應該收到 409（CatalogAdminConflict → 409，catalog_admin.py:214-215）

  @sad-path
  Scenario Outline: 寫入錯誤分級
    When 寫入觸發 "<error_kind>"
    Then 我應該收到狀態碼 "<status>"

    Examples:
      | error_kind                       | status |
      | 查無該筆（NotFound）             | 404    |
      | 參照/上架門檻不符（Reference/Activation） | 422 |
      | 其他資料庫故障                   | 503    |
    # 對映：catalog_admin.py:211-230；503 錯誤碼 postgres_catalog_write_unavailable

  @happy-path
  Scenario: 刪除是軟刪除
    When 我 DELETE 一筆家具
    Then 該筆應被停用而非物理刪除
    # 由 tests/test_postgres_catalog_crud.py::test_admin_delete_is_a_soft_delete_command 鎖定
```

### Feature 10：工程概算（backend/server/cost_estimation.py）

```gherkin
Feature: 概念工程概算
  # 對應：POST /api/cost/estimate（main.py:3658）

  @happy-path
  Scenario: 以版控內行情估算，不打外網
    When 我提交含 items 清單的估算請求
    Then 回應應以版控內的台灣公開行情資料計算，且過程不需要網路
    # 由 tests/test_cost_estimation_api.py::test_cost_api_uses_versioned_online_sources_without_live_network 鎖定

  @sad-path
  Scenario: 缺 items 清單
    When 我提交沒有 items 陣列的請求
    Then 我應該收到 422，錯誤為 cost_items_required（main.py:3662-3663）
```

---

## 對照 tests/：情境如何落地

### 現況（本次實測）

- repo **沒有** Gherkin 執行器：`grep pytest-bdd|behave|gherkin` 於 `pyproject.toml` 與 `uv.lock` 零命中，也沒有 `features/` 目錄。
- BDD 實際落地方式 = **行為命名的 pytest 測試** + `fastapi.testclient.TestClient` 直接打路由。測試函式名本身就是行為敘述，例如 `test_floorplan_analysis_explains_missing_confirmation_instead_of_stalling`。
- 測試規模：`tests/` 共 **99** 支 `test_*.py`（`ls tests/test_*.py | wc -l`），另有 `tests/static/` 3 支前端 `.test.mjs`（Node 執行）與 `training/tests/` 11 支（辨識訓練用，不在主 tests/）。執行方式：`uv run pytest tests/`（pyproject.toml:61 鎖 `pytest>=9.1.1`，`[tool.pytest.ini_options]` 已設 pythonpath）。

### 情境 ↔ 現有測試對照表（測試名皆為本次 grep 實查）

| 本文情境 | 對應現有測試 |
| :--- | :--- |
| 副檔名白名單（Feature 1 @edge-case） | `tests/test_project_workflow_api.py::test_floorplan_upload_accepts_only_dxf_png_and_jpeg` |
| 未確認圖檔先擋辨識（Feature 2 @sad-path） | `tests/test_project_workflow_api.py::test_floorplan_analysis_explains_missing_confirmation_instead_of_stalling`、`tests/test_scene_workflow.py::test_floorplan_confirmation_and_completed_upload_are_required_before_analysis` |
| 重新辨識作廢下游 | `tests/test_project_workflow_api.py::test_rerunning_floorplan_analysis_invalidates_stale_structure_confirmation` |
| DXF 輸出公分契約與房間區域 | `tests/test_project_workflow_api.py::test_dxf_analysis_returns_canonical_centimeter_geometry_and_room_regions` |
| 兩點比例尺（Feature 2 @happy-path） | `tests/test_scene_calibration.py::test_two_image_points_and_known_length_create_scale_calibration` |
| 比例確認解鎖空間確認 | `tests/test_scene_workflow.py::test_confirmed_scale_unlocks_space_confirmation_and_state_can_be_restored` |
| 樂觀鎖與離線補送（Feature 3） | `tests/test_project_workflow_api.py::test_pending_save_replay_rejects_a_stale_server_version_atomically`、`tests/test_scene_workflow.py::test_pending_save_replays_only_against_the_server_version_it_started_from` |
| 八步 UI/單面板共用 | `tests/test_scene_workflow.py::test_scene_exposes_the_final_eight_step_workflow`（:530）、`::test_nine_step_workflow_uses_one_panel_for_recognition_and_calibration`（:428） |
| 步驟閘門（Feature 6） | `tests/test_scene_workflow.py::test_each_gate_blocks_the_next_stage_until_confirmation_is_valid` |
| 上游改動作廢下游（Feature 6 @sad-path） | `tests/test_scene_workflow.py::test_editing_upstream_confirmation_invalidates_downstream_results` |
| 問卷房間預選（Feature 4） | `tests/test_questionnaire_visual_catalog.py::test_confirmed_room_prefills_only_shared_unanswered_questions` |
| 問卷狀態保存重載（Feature 4） | `tests/test_questionnaire_visual_catalog.py::test_questionnaire_state_survives_project_save_and_reload` |
| 極端偏好影響家具規格 | `tests/test_questionnaire_visual_catalog.py::test_extreme_preferences_change_furniture_specs_before_layout` |
| LLM 選件降級（Feature 5 @sad-path） | `tests/test_project_workflow_api.py::test_agent_furniture_selection_falls_back_when_llm_violates_room_rules`、`::test_agent_furniture_selection_uses_server_side_local_rules_without_llm` |
| 選件白名單/房型/副件規則 | `tests/test_agent_select.py`（18 個測試） |
| 2D 拖曳走引擎驗證（Feature 5） | `tests/test_project_workflow_api.py::test_2d_layout_and_drag_validation_use_the_engine_with_editor_geometry`、`tests/test_scene_layout_regions.py::test_manual_wall_snap_is_resolved_by_the_backend_layout_engine` |
| 佈局變體 B（Feature 5 @edge-case） | `tests/test_scene_layout_regions.py::test_layout_variant_b_uses_a_different_engine_validated_candidate` |
| 擺位碰撞/淨空幾何基礎 | `tests/test_placement.py`（18 個測試）、`tests/test_clearance.py`（10 個測試） |
| 白模零家具（Feature 6） | `tests/test_scene_workflow.py::test_white_model_allows_an_explicit_zero_furniture_plan` |
| 自動軟裝（Feature 6） | `tests/test_scene_soft_decor.py::test_auto_decor_adds_four_visible_glbs_through_the_engine`、`::test_empty_room_does_not_receive_scattered_decor` |
| 工程 snapshot/lock 不可變（Feature 7） | `tests/test_engineering_snapshot_api.py::test_snapshot_save_lock_and_locked_revision_is_immutable`、`::test_snapshot_cannot_lock_after_source_project_revision_changes`、`::test_snapshot_rejects_meter_contract_and_path_mismatch` |
| 未鎖定擋產包/端到端產包（Feature 7） | `tests/test_engineering_documents_api.py::test_unlocked_revision_returns_required_409`、`::test_demo_e2e_generates_html_json_and_two_sheet_artifact_xlsx`、`::test_production_report_has_pending_quotes_and_no_fake_total` |
| RAG 狀態/失敗對映/job（Feature 8） | `tests/test_rag_api.py::test_rag_page_status_success_and_validation`、`::test_rag_api_maps_failures`、`::test_rag_job_api_reports_progress_and_result`、`::test_rag_job_api_hides_upstream_failure_detail` |
| 型錄管理 fail-closed 與 CRUD（Feature 9） | `tests/test_postgres_catalog_crud.py`（含 `test_admin_api_fails_closed_when_token_is_not_configured`、`test_admin_patch_maps_optimistic_lock_conflict_to_409`、`test_admin_delete_is_a_soft_delete_command`） |
| 工程概算（Feature 10） | `tests/test_cost_estimation_api.py::test_cost_api_uses_versioned_online_sources_without_live_network`、`tests/test_cost_estimation.py` |

### 新行為的落地流程

1. 先以本檔格式寫 Gherkin 情境（收進本檔或 PR 描述），步驟名與順序對照〈撰寫前必讀〉的表。
2. 翻譯成 `tests/test_*.py` 的行為命名測試：`Given` = 建 `TestClient` 與前置資料、`When` = 呼叫路由、`Then` = 斷言狀態碼 + 錯誤 `code`/`error_code` 欄位（主流程錯誤碼以 `backend/server/main.py` 為準；工程文件用大寫 `error_code`（engineering/api.py）、RAG 與型錄管理用小寫 `code`——不自創、不混用）。
3. 跨 owner 目錄的行為（如 server ↔ engine、server ↔ catalog）先按根目錄 `AGENTS.md` 的跨資料夾修改格式聲明兩端測試，再動手。
4. 執行 `uv run pytest tests/` 驗證；前端行為另跑 `tests/static/` 的 Node 測試。
5. 待辦（未決策）：是否引入 pytest-bdd 讓 `.feature` 檔可直接執行——目前無此依賴，引入與否待團隊裁決。

---

## 最佳實踐

1. **一個 Scenario 只測一件事**
2. **使用陳述式** -- `Then 我應該收到 409，錯誤碼為 project_revision_conflict`（非 `Then 系統回傳衝突`）
3. **避免 UI 細節** -- `When 我確認平面圖內容正確`（非 `When 我點選綠色確認按鈕`）
4. **從使用者角度編寫** -- 非技術人員也能讀懂
5. **（RoomPilot 補充）步驟名與順序只認程式碼** -- 內部步驟鍵以 `backend/server/static/scene_workflow.js` 的 `WORKFLOW_STEPS` 為準；錯誤碼以各路由檔實作為準；舊文件（含舊導入版的「十步 UI」「44 條路由」口徑）一律不採用
6. **（RoomPilot 補充）Then 不得宣稱程式碼沒有的保證** -- 例如伺服器端不驗步驟順序、全端點無認證（catalog_admin 除外，見 roompilot-security skill 的風險基線），情境不可假裝這些防護存在
