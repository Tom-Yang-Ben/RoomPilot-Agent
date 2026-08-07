# 軟體需求規格書 (SRS) - RoomPilot

> **版本:** v1.0 | **更新:** 2026-08-07 | **狀態:** 草稿
> **Owner:** Bella（整合／系統分析）；各 FR 由對應模組 owner（Cody／Django／Kai／Yen／Ancai）共同審閱
> **定位:** 把 `AGENTS.md`「不可違反的契約」與現行八步流程正式化為可驗收的 FR／NFR／UC。業務動機與價值歸 [brd](./brd.md)／[prd](./prd.md)；架構落法歸 [sad](../03_architecture/sad.md)；測試計畫與場景（SCN-\*）歸 [test_plan](../05_qa/test_plan.md)。
> **語域:** L2（橋接）
> **實例:** 單例（整個系統一份）
> **生成:** 2026-08-07 由 VibeCoding_Workflow_Templates/01_requirements/srs.md 導入 | 基準 docs/vibecoding-restructure @ 1268b2b4

---

## 目錄

- [1. 功能需求 (Functional Requirements)](#1-功能需求-functional-requirements)
- [2. 非功能需求 (NFR)](#2-非功能需求-nfr)
- [3. 資料需求 (Data Requirements)](#3-資料需求-data-requirements)
- [4. 外部介面 (External Interfaces)](#4-外部介面-external-interfaces)
- [5. 使用案例 (Use Case Specification)](#5-使用案例-use-case-specification)
- [6. 驗收標準 (Acceptance Criteria)](#6-驗收標準-acceptance-criteria)
- [7. 追溯](#7-追溯)

## 1. 功能需求 (Functional Requirements)

產品流程以 `README.md`「現行八步流程」為準：核心八步（1 建立專案 → 8 AI 渲染）之外，前有帳戶端入口（步驟 0 登入／選專案）、後有成果報告延伸（步驟 9 `/engineering`）。本節依領域分組；每條 FR 的「來源」欄指向契約或程式碼證據，不重抄契約內文（SSOT 見各契約檔）。

### 1.1 帳戶與專案（AUTH／PROJ）

| ID | 需求描述 | 來源 | Owner | 優先級 | 驗收標準 ID |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FR-AUTH-01 | 進入八步流程前必須登入。系統角色：`designer`（建立編輯專案、鎖版出報告）、`client`（僅檢視被分享專案）、`admin`（跨帳號維運）；專案成員角色：`editor`／`viewer` | `README.md` 帳戶端段 | Bella | Must | ACPT-AUTH-01 |
| FR-AUTH-02 | `/api/projects/*` 與 `/api/v1/*` 每個端點都掛 `auth.dependencies` 守衛；**非成員與不存在的專案一律回 404 而非 403**（403 會洩漏專案存在性——業務語意：外人連「這個專案存在」都不該知道） | `AGENTS.md` 不可違反契約；`backend/server/auth/dependencies.py:60-66` | Bella | Must | ACPT-AUTH-02 |
| FR-AUTH-03 | 帳號生命週期由 admin 維運：重設密碼（設臨時密碼、口頭告知）、停用／恢復（停用立即生效、既有 token 全部失效、不能停用自己）；使用者改密碼成功即撤銷所有既有 session | `README.md` 帳戶端段；`backend/server/auth/api.py` | Bella | Should | ACPT-AUTH-03 |
| FR-PROJ-01 | 專案可建立、保存、中斷後恢復（可恢復的網頁流程）；專案一律有 owner，不存在無主專案 | `AGENTS.md` 契約；`README.md` | Bella | Must | ACPT-PROJ-01 |
| FR-PROJ-02 | 專案可分享給其他帳號，成員角色限 `editor`（可編輯）或 `viewer`（唯讀） | `README.md` 帳戶端段 | Bella | Should | ACPT-PROJ-02 |

### 1.2 平面圖辨識與空間（FP／LAYOUT）

| ID | 需求描述 | 來源 | Owner | 優先級 | 驗收標準 ID |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FR-FP-01 | 上傳 PNG／JPG／DXF 平面圖，辨識牆、門、窗、房間，輸出 `layout_json`。**辨識止於 `layout_json`**：只描述空間本身（牆門窗房間、尺度、信心），不得含家具、材質、渲染或風格決策 | `docs/contracts/LAYOUT_SCENE_BOUNDARY_CONTRACT.md`「layout_json」節 | Cody | Must | ACPT-FP-01 |
| FR-FP-02 | 使用者以兩點標定確認公分尺度（第 3 步）；尺度未確認前不得進入後續配置 | `README.md` 八步流程第 3 步 | Cody | Must | ACPT-FP-02 |
| FR-FP-03 | 第 4 步由使用者人工校正空間、牆、門、窗，並手動標定樑與柱（樑柱不依賴自動辨識，屬設計決策而非辨識缺口） | `README.md` 八步流程第 4 步 | Cody | Must | ACPT-FP-03 |
| FR-LAYOUT-01 | 空間尺寸、房間關係與 layout evaluation 由 `backend/spatial_data/` 依既定 schema 提供，供方案生成與檢索使用 | `docs/contracts/LAYOUT_EVALUATION_SCHEMA.md`；`AGENTS.md` 目錄責任表 | Django | Should | ACPT-LAYOUT-01 |

### 1.3 方案生成與場景編輯（SCENE）

| ID | 需求描述 | 來源 | Owner | 優先級 | 驗收標準 ID |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FR-SCENE-01 | 方案生成與編輯的輸出一律是 `scene_json`（家具、材質、燈光、渲染設定等設計決策）；`layout_json` ↔ `scene_json` 的內容邊界依契約，不得互相越界 | `docs/contracts/LAYOUT_SCENE_BOUNDARY_CONTRACT.md`「scene_json」節 | Bella | Must | ACPT-SCENE-01 |
| FR-SCENE-02 | 第 6 步同一畫面同步編輯 2D／3D 家具並走動預覽；未處理的家具碰撞、淨空、超界或模型載入問題會阻擋下一步 | `README.md` 八步流程第 6 步與其後段落 | Bella | Must | ACPT-SCENE-02 |
| FR-SCENE-03 | 結構變更（牆門窗樑柱）必須回到第 4 步，系統重新驗證目前家具的合法性 | `README.md` 八步流程段 | Bella | Must | ACPT-SCENE-03 |

### 1.4 家具型錄與資料邊界（CATALOG）

| ID | 需求描述 | 來源 | Owner | 優先級 | 驗收標準 ID |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FR-CATALOG-01 | 第 6 步正式家具以 Kai PostgreSQL view `roompilot.furniture_catalog_current` 為優先來源，預設即 strict postgres；資料庫不可用時回 503（`postgres_catalog_unavailable`），第 6 步選件受阻，不靜默混用 JSON。回退已驗證 JSON 屬維運人工切換：明確設定 provider 為 `json` 才走離線模式（`AGENTS.md` 契約原文「不可用才回退」的語感與現行 strict 行為有落差——多來源不一致，待 owner 對齊） | `AGENTS.md` 契約；`backend/catalog/postgres_repository.py:201-206`；`backend/server/main.py:517-525`；`backend/catalog/runtime_catalog_repository.py:48-84` | Kai | Must | ACPT-CATALOG-01 |
| FR-CATALOG-02 | 隔離區（quarantine）或未匹配資料不得進 API 或場景，也不得被視為正式家具 | `AGENTS.md` 契約；`backend/catalog/data/quarantine/` | Kai | Must | ACPT-CATALOG-02 |
| FR-CATALOG-03 | 冰箱、洗衣機等**家電不進 2D／3D 自動配置與正式家具 API**；家電需求保留在問卷並隨 `scene_json.render_context.appliance_requirements` 傳遞，只供第 8 步 AI 生圖當上下文 | `AGENTS.md` 契約；`backend/server/scene_service.py:213-215`（正規化入口攔截）、`:3048-3052`（render_context） | Bella／Yen | Must | ACPT-CATALOG-03 |
| FR-CATALOG-04 | 燈具走獨立 lane：`roompilot.lighting_assets_current` view，經 `surface_overrides.lighting_ids` 引用；不參與第 6 步家具自動選件與碰撞計算 | `docs/contracts/LIGHTING_CEILING_CATALOG_CONTRACT.md` | Kai | Should | ACPT-CATALOG-04 |

### 1.5 檢索、選件與幾何判定（RAG／AGENT／ENGINE）

| ID | 需求描述 | 來源 | Owner | 優先級 | 驗收標準 ID |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FR-RAG-01 | Graph RAG 只檢索房間、家具、風格、材質與限制的**關係與證據**；不決定幾何、碰撞、淨空或結構合法性 | `AGENTS.md` 契約 | Django | Must | ACPT-RAG-01 |
| FR-RAG-02 | 家具向量 RAG 只解析需求、檢索與排序 Kai PostgreSQL 家具；不得取代 Yen 選件決策或 Ancai 幾何判定。受控詞彙：6 風格 × 3 色卡 = 18、24 氛圍詞、19 家具群組 | `AGENTS.md` 契約；`backend/spatial_data/rag/`；詞彙實測見 §3 | Django | Must | ACPT-RAG-02 |
| FR-AGENT-01 | 問卷證據結構化為需求與排序選件；保留房間身分、使用者指定家具與延後決定；回覆解釋與修復意圖，**不產生座標** | `backend/agent/AGENTS.md` | Yen | Must | ACPT-AGENT-01 |
| FR-AGENT-02 | LLM 輔助為可選能力；LLM 輸出必須先驗入本地 schema 才可使用，選件結果標示 `selection_source` 以區分來源 | `backend/agent/AGENTS.md`；`backend/agent/place.py:266-268` | Yen | Must | ACPT-AGENT-02 |
| FR-ENGINE-01 | 家具合法位置**只由 `backend/engine/` 判定**（配置、碰撞、淨空、移動與幾何合法性）；前端 fallback 不得悄悄取代後端演算法，整合端不得重做幾何邏輯 | `AGENTS.md` 契約 | Ancai | Must | ACPT-ENGINE-01 |

### 1.6 渲染與成果報告（RENDER／REPORT）

| ID | 需求描述 | 來源 | Owner | 優先級 | 驗收標準 ID |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FR-RENDER-01 | 第 7 步鎖定方案並逐房選視角；第 8 步 AI 渲染依問卷、家具、材質、色卡與視角產生逐房成果。遠端生圖唯一入口是 `POST /api/projects/{id}/render-jobs`，`mode` 限 `palette_comparison`／`room_final`；瀏覽器不得自行指定遠端網址或攜帶供應商金鑰 | `docs/contracts/REMOTE_RENDER_CONTRACT.md`；`README.md` 第 7–8 步 | Bella | Must | ACPT-RENDER-01 |
| FR-RENDER-02 | 渲染 payload 送往外部供應商前剝除姓名、電話、Email 等私人欄位；供應商未設定時如實回錯（503），不得假成功 | `backend/server/render_service.py:17`（PRIVATE_KEYS）、`backend/server/main.py:301,323,519` | Bella | Must | ACPT-RENDER-02 |
| FR-REPORT-01 | 第 9 步 `/engineering` 把鎖定版 ProjectSnapshot 轉成 HTML／XLSX／JSON 三份成果文件（設計語彙、家具採購明細、工程施工費與初步工期） | `README.md` 第 9 步段；`backend/server/engineering/api.py:66`（`/api/v1` 路由群） | Bella | Must | ACPT-REPORT-01 |
| FR-REPORT-02 | 家具採購金額與工程施工費**分開列示、不合計**；查無價格的工項 `subtotal` 為 null（pending_quote），不以已知小計冒充總價 | `AGENTS.md` 契約；`backend/server/engineering/cost.py:80-96` | Bella | Must | ACPT-REPORT-02 |
| FR-REPORT-03 | 設計語彙知識庫屬團隊內部編纂，`confidence` 上限 `medium`；報告裡的數字一律來自鎖定版快照與工程知識庫，不由語彙模板產生 | `AGENTS.md` 契約；`backend/catalog/data/design/` | Kai（保管）／Bella（消費） | Must | ACPT-REPORT-03 |

---

## 2. 非功能需求 (NFR)

量化指標與驗證方法維護在本表與 [`../03_architecture/sad.md`](../03_architecture/sad.md) 非功能段。**效能類 NFR 目前在 repo 內沒有量測基準，一律標 TO-BE**，不填模板範例值。

| ID | 類別 | 適用範圍與指標 | 現況 |
| :--- | :--- | :--- | :--- |
| NFR-一致性-01 | 資料一致性 | 跨模組幾何一律公分；新長度／座標欄位 `_cm`、面積 `_m2`；舊欄位 `width`/`depth`/`pos_x`/`pos_y` 必帶 `coordinate_unit: "cm"` 與 schema version | 已定義（`AGENTS.md` 契約；`tests/test_scene_v2_contract.py` 等契約測試存在） |
| NFR-安全-01 | 機敏資訊 | 不提交 `.env`、密碼、個資、模型權重；對外渲染剝除私人欄位（機制見 FR-RENDER-02）；專案存在性不洩漏（機制見 FR-AUTH-02） | 已定義 |
| NFR-安全-02 | 憑證管理 | Token 簽章金鑰（`ROOMPILOT_AUTH_SECRET`）必須明確設定，否則各節點自產金鑰、token 無法跨節點驗證；access／refresh TTL 可配置 | 已定義（`README.md` 帳戶端段） |
| NFR-可用性-01 | 降級韌性 | 型錄資料庫不可用時明確回 503、第 6 步家具選件受阻，不靜默混用舊資料；回退已驗證 JSON 為維運人工切換 provider，非系統自動（機制見 FR-CATALOG-01）。LLM 未設定或失敗時本地規則承接、流程不中斷（機制見 FR-AGENT-02） | 已定義 |
| NFR-相容-01 | 向後相容 | 專案保存狀態向後相容；schema 變更必須帶版本 | 已定義（`backend/server/AGENTS.md`） |
| NFR-效能-01 | API 延遲 | 各端點 p95 回應時間門檻 | **TO-BE**（repo 內無量測基準與門檻決議） |
| NFR-效能-02 | 3D 載入 | 第 6 步 3D 場景首次載入時間門檻 | **TO-BE**（未在 repo 留下量測證據；門檻待 Ben 拍板） |
| NFR-維運-01 | 部署形態 | 本機 uvicorn 單體服務，預設 `127.0.0.1:8002`；Docker 已於 2026-08-06 整套移除（commit `09891216`），達標後才重新評估容器化 | 已定義（`README.md` 快速啟動；git log 實查） |
| NFR-資源-01 | 資源上限 | 單次 render-jobs 任務總量有上限：風格卡 ≤ 18、逐房視角 ≤ 24，超量回 422 明確拒絕，不靜默截斷（機制見 FR-RENDER-01） | 已定義（`backend/server/render_service.py:15-16`，commit `2d5111be`） |

---

## 3. 資料需求 (Data Requirements)

保留政策全數**未定義（待補）**——repo 內查無任何資料保留年限決議。筆數為 2026-08-07 對本機 PostgreSQL 的實測值；跨文件出現的其他口徑一併註記。

| 資料實體 | 來源系統 | 實測規模（2026-08-07） | 保留政策 | 敏感等級 |
| :--- | :--- | :--- | :--- | :--- |
| 正式家具型錄 | Kai 匯入 → PostgreSQL view `roompilot.furniture_catalog_current` | 7,958 筆可選（官方 JSON 交付 8,557 筆，見 `docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md`；舊文件之 9,349／9,350 為已退役雲端集合口徑——多來源不一致，以 view 實測為準） | 待補 | 低（無個資） |
| 燈具資產 | PostgreSQL `roompilot.lighting_assets_current` | 637 筆可用（基表 793，差額 156 筆待 Kai 分流） | 待補 | 低 |
| 專案資料（workflow／`layout_json`／`scene_json`） | 本系統（PostgreSQL project store，見 `docs/contracts/POSTGRESQL_PROJECT_STORE_PHASE3.md`） | 依使用量成長 | 待補 | 中（含使用者平面圖與需求） |
| 使用者帳號 | 本系統 auth（使用者與成員資料表） | 依使用量成長 | 待補 | 高（Email、密碼雜湊——個資） |
| 設計語彙知識庫 | `backend/catalog/data/design/`（Kai 保管） | 團隊編纂、`confidence` ≤ medium | 待補 | 低 |
| 隔離區資料 | `backend/catalog/data/quarantine/` | 不得進 API／場景（FR-CATALOG-02） | 待補 | 低 |
| 檢索受控詞彙 | `backend/catalog/data/taiwan_style_cards.json`（6 風格 × 3 色卡 = 18，實測）；`backend/spatial_data/rag/data/taxonomy.json`（24 氛圍詞，實測）；`category_groups.json`（19 群組，實測） | 如左 | 待補 | 低 |
| 快照與報告契約 | `docs/contracts/project_snapshot.schema.json`、`report_payload.schema.json`、`risk_results.schema.json` | JSON Schema 訂版 | 隨 repo | 低 |

---

## 4. 外部介面 (External Interfaces)

| 介面 | 方向 | 協議 | 契約文件 |
| :--- | :--- | :--- | :--- |
| CloudFront 家具模型交付（GLB＋三視角 PNG） | 出 | HTTPS | `docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md` |
| 遠端渲染供應商（AI 生圖） | 出 | REST（經後端代理，未設定回 503） | `docs/contracts/REMOTE_RENDER_CONTRACT.md` |
| LLM 供應商（OpenRouter，可選） | 出 | REST（失敗降級本地規則，見 FR-AGENT-02） | `backend/agent/AGENTS.md`；`backend/spatial_data/rag/settings.py` |
| PostgreSQL（本機 17.10 + pgvector 0.8.2，實測） | 內部依賴 | SQL | `docs/contracts/POSTGRESQL_*.md` 系列（Phase 1–5） |
| 瀏覽器前端（`frontend/` 原生 ES module＋自帶 `vendor/three/`，無建置步驟、無 CDN 依賴） | 內部 | HTTP／WebGL | `backend/paths.py:25`（`STATIC_DIR` 唯一路徑來源）；詳見 [api_spec](../04_design/api_spec.md) |

---

## 5. 使用案例 (Use Case Specification)

> 只展開牽動跨模組契約的案例；一般功能由 prd 的 User Story 與 test_plan 場景承接。

### UC-001: 屋主端到端完成八步流程

| 項目 | 內容 |
| :--- | :--- |
| **Actor** | 屋主（`designer` 角色） |
| **Preconditions** | 已登入、已建立專案（FR-AUTH-01、FR-PROJ-01） |
| **Main Flow** | 1. 上傳平面圖並辨識（FR-FP-01） 2. 兩點標定公分尺度（FR-FP-02） 3. 校正空間結構（FR-FP-03） 4. 全屋風格與逐房需求問卷 5. 產生配置並在 2D／3D 同步編輯（FR-SCENE-01、FR-SCENE-02） 6. 鎖定方案、逐房選視角 7. AI 渲染逐房成果（FR-RENDER-01） 8. 產出成果報告（FR-REPORT-01） |
| **Alternative Flow** | A1. 家具碰撞／淨空未解 → 阻擋下一步（FR-SCENE-02） A2. 結構變更 → 退回第 4 步重新驗證家具（FR-SCENE-03） A3. 型錄資料庫不可用 → 系統回 503、第 6 步家具選件受阻；如需續行，由維運人工切換 provider 至已驗證 JSON（FR-CATALOG-01） |
| **Postconditions** | 專案含鎖定版 `scene_json` 與逐房渲染成果，可隨時恢復 |
| **引用規則** | BR-\*（見 [`brd.md`](./brd.md)） |

### UC-002: 非成員嘗試存取他人專案

| 項目 | 內容 |
| :--- | :--- |
| **Actor** | 已登入但非該專案成員的帳號 |
| **Preconditions** | 目標專案存在且 actor 不在成員名單 |
| **Main Flow** | 1. Actor 呼叫任一 `/api/projects/{id}/*` 端點 2. 系統回 404（與專案不存在時同一回應，FR-AUTH-02） |
| **Alternative Flow** | A1. 專案 owner 分享並指定 `viewer` → actor 可唯讀檢視（FR-PROJ-02） |
| **Postconditions** | 專案存在性未被洩漏；無任何資料變動 |
| **引用規則** | BR-\*（見 [`brd.md`](./brd.md)） |

### UC-003: 問卷含家電需求的方案生成

| 項目 | 內容 |
| :--- | :--- |
| **Actor** | 屋主；系統（選件與擺位） |
| **Preconditions** | 問卷含冰箱／洗衣機等家電需求 |
| **Main Flow** | 1. 需求結構化（FR-AGENT-01） 2. 家電在 `required_furniture` 正規化入口被攔下，不進自動配置（FR-CATALOG-03） 3. 家電需求寫入 `scene_json.render_context` 4. 第 8 步 AI 生圖把家電當上下文呈現 |
| **Alternative Flow** | A1. 型錄側家電被誤標為家具型別 → 型錄保險再攔一次（FR-CATALOG-03 來源碼） |
| **Postconditions** | 2D／3D 場景無家電物件；渲染圖可含家電語境 |
| **引用規則** | BR-\*（見 [`brd.md`](./brd.md)） |

---

## 6. 驗收標準 (Acceptance Criteria)

AC 用 Given／When／Then 落在 [`prd.md`](./prd.md) 各 Epic 的 US-\* 允收欄與 [test_plan](../05_qa/test_plan.md)；ACPT ID 由本表定義，並維護 FR ↔ 場景（SCN-\*）對照。SCN 編號由 prd 定義（與 test_plan、uat_plan 的權威宣告一致），狀態**「待對齊」表示與 test_plan 案例的對應待承接確認**。「現有測試證據」為 2026-08-07 實查存在的 pytest 檔（全 repo 113 檔、1,053 個收集測試）。

| ACPT ID | 對應 FR | Scenario（SCN-\*） | 現有測試證據 | 狀態 |
| :--- | :--- | :--- | :--- | :--- |
| ACPT-AUTH-01 | FR-AUTH-01 | SCN-AUTH-01 | `tests/test_auth_core.py` | 待對齊 |
| ACPT-AUTH-02 | FR-AUTH-02 | SCN-AUTH-02 | `tests/test_project_authorization.py` | 待對齊 |
| ACPT-AUTH-03 | FR-AUTH-03 | SCN-AUTH-03 | `tests/test_auth_lifecycle.py` | 待對齊 |
| ACPT-PROJ-01 | FR-PROJ-01 | SCN-PROJ-01 | `tests/test_project_workflow_api.py` | 待對齊 |
| ACPT-PROJ-02 | FR-PROJ-02 | SCN-PROJ-02 | `tests/test_project_authorization.py` | 待對齊 |
| ACPT-FP-01 | FR-FP-01 | SCN-FP-01 | `tests/test_floorplan_vision.py`、`tests/test_floorplan_vision_api.py` | 待對齊 |
| ACPT-FP-02 | FR-FP-02 | SCN-FP-02 | `tests/test_floorplan_vision.py` | 待對齊 |
| ACPT-FP-03 | FR-FP-03 | SCN-FP-03 | 待補（人工校正屬 UI 流程，需瀏覽器 QA） | 待驗證 |
| ACPT-LAYOUT-01 | FR-LAYOUT-01 | SCN-LAYOUT-01 | 待補 | 待驗證 |
| ACPT-SCENE-01 | FR-SCENE-01 | SCN-SCENE-01 | `tests/test_scene_v2_contract.py` | 待對齊 |
| ACPT-SCENE-02 | FR-SCENE-02 | SCN-SCENE-02 | `tests/test_scene_workflow.py`＋瀏覽器 QA | 待對齊 |
| ACPT-SCENE-03 | FR-SCENE-03 | SCN-SCENE-03 | 待補 | 待驗證 |
| ACPT-CATALOG-01 | FR-CATALOG-01 | SCN-CATALOG-01 | `tests/test_runtime_catalog_phase4.py` | 待對齊 |
| ACPT-CATALOG-02 | FR-CATALOG-02 | SCN-CATALOG-02 | 待補 | 待驗證 |
| ACPT-CATALOG-03 | FR-CATALOG-03 | SCN-CATALOG-03 | 待補（攔截碼在 `scene_service.py:213-215`，測試對應待 test_plan 盤點） | 待驗證 |
| ACPT-CATALOG-04 | FR-CATALOG-04 | SCN-CATALOG-04 | 待補 | 待驗證 |
| ACPT-RAG-01 | FR-RAG-01 | SCN-RAG-01 | 待補（邊界屬架構約束，宜以架構審查＋契約測試把關） | 待驗證 |
| ACPT-RAG-02 | FR-RAG-02 | SCN-RAG-02 | 待補 | 待驗證 |
| ACPT-AGENT-01 | FR-AGENT-01 | SCN-AGENT-01 | `tests/test_agent_select.py`、`tests/test_agent_place.py`、`tests/test_agent_requirement_chain.py` | 待對齊 |
| ACPT-AGENT-02 | FR-AGENT-02 | SCN-AGENT-02 | 待補 | 待驗證 |
| ACPT-ENGINE-01 | FR-ENGINE-01 | SCN-ENGINE-01 | `tests/test_placement.py`、`tests/test_clearance.py` | 待對齊 |
| ACPT-RENDER-01 | FR-RENDER-01 | SCN-RENDER-01 | `tests/test_remote_render_workflow.py` | 待對齊 |
| ACPT-RENDER-02 | FR-RENDER-02 | SCN-RENDER-02 | `tests/test_remote_render_workflow.py`、`tests/test_render_direct_provider.py` | 待對齊 |
| ACPT-REPORT-01 | FR-REPORT-01 | SCN-REPORT-01 | `tests/test_engineering_documents_api.py`、`tests/test_engineering_snapshot_api.py` | 待對齊 |
| ACPT-REPORT-02 | FR-REPORT-02 | SCN-REPORT-02 | `tests/test_engineering_cost_schedule.py` | 待對齊 |
| ACPT-REPORT-03 | FR-REPORT-03 | SCN-REPORT-03 | `tests/test_engineering_contract_exports.py` | 待對齊 |

## 7. 追溯

| 項目 | ID |
| :--- | :--- |
| 上游 | [prd](./prd.md) 的 US-\*／REQ-\*；[brd](./brd.md) 的 BR-\*；`AGENTS.md`「不可違反的契約」全表；`docs/contracts/` 各契約檔 |
| 本文件產出 | FR-\<AREA\>-NN、NFR-\<類\>-NN、UC-001～003、ACPT-\<AREA\>-NN 對照表 |
| 下游 | [sad](../03_architecture/sad.md) 需求摘要段、[test_plan](../05_qa/test_plan.md)／[uat_plan](../05_qa/uat_plan.md) 的 SCN-\*、`engineering_tracker.xlsx` ①規格追溯 |
