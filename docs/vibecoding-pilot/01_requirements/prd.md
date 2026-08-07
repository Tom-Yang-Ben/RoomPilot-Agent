# 產品需求文件 (PRD) - RoomPilot-Agent

> **版本:** v1.0 | **更新:** 2026-08-07 | **狀態:** 草稿
> **Owner:** Ben（文件導入與證據維護；需求決策 owner 於 repo 內無正式指派紀錄，核准權責待全隊確認）
> **語域:** L1（業務主述；允收標準與依據附註屬 L2 映射）
> **定位:** 回答「RoomPilot 解決什麼問題、給誰用、做到什麼才算數」——問題、使用者、範圍與允收標準的單一來源。商業背景與業務規則歸 [brd.md](./brd.md)；正式功能／非功能規格（FR/NFR 枚舉）歸 [srs.md](./srs.md)。
> **實例:** 單例（整個系統一份）
> **生成:** 2026-08-07 由 VibeCoding_Workflow_Templates/01_requirements/prd.md 導入 | 基準 docs/vibecoding-restructure @ 1268b2b4

---

## 目錄

- [1. 專案總覽](#1-專案總覽)
- [2. 商業目標](#2-商業目標)
- [3. 使用者故事與允收標準](#3-使用者故事與允收標準)
- [4. 範圍與限制](#4-範圍與限制)
- [5. 待辦問題與決策](#5-待辦問題與決策)
- [6. 追溯](#6-追溯)

---

## 1. 專案總覽

| 項目 | 內容 |
| :--- | :--- |
| **專案名稱** | RoomPilot-Agent（`pyproject.toml`：`roompilot-agent` 0.1.0；網站標題「AI 室內風格與家具配置展示系統」，`backend/server/main.py:244`） |
| **狀態** | 開發中（本文件基準：分支 `docs/vibecoding-restructure`、commit `1268b2b4`、2026-08-07） |
| **目標發布日期** | 2026-08-20 成果發表（未查證——repo 內無任何日期紀錄，團隊口述，待補正式來源） |
| **核心團隊** | 七位成員，依 `README.md`「團隊責任」表：Bella＝伺服器與正式網頁、Cody＝平面圖辨識與 3D 升維、Django＝空間關係與家具檢索、Kai＝家具型錄與雲端資產、Yen＝需求解析與選件、Ancai＝幾何擺放引擎、Ben＝測資 QA 與證據維護 |

### 1.1 問題陳述

一般住戶拿到建商平面圖後，難以把「空間現況＋生活需求」快速轉成可討論的室內設計方向；與設計師往返確認格局、風格與家具耗時。RoomPilot 讓使用者在一個可中斷、可恢復的網頁流程內，自助完成「平面圖 → 需求 → 配置 → 預覽 → 渲染 → 報告」，得到可比較、可修改的提案。（問題陳述沿用 2026-07-26 版草稿，無訪談數據支撐；商業背景、As-Is/To-Be 與利害關係人詳見 [brd.md](./brd.md) §1–§3，此處不重述。）

### 1.2 目標用戶

| 用戶 | 使用情境 |
| :--- | :--- |
| 屋主／一般住戶 | 上傳自家平面圖，經問卷表達需求，取得 2D/3D 家具配置、風格提案與成果報告 |
| 室內設計師 | 與客戶在同一流程即時確認空間方向、風格色卡與家具選件；鎖版產出報告 |
| 管理員 | 帳號維運：建立管理員、重設密碼、停用帳號（規則見 [brd.md](./brd.md) BR-006～BR-009） |

### 1.3 產品流程

正式流程稱「八步流程」：主畫面固定八個步驟按鈕（本輪已對現行網頁核對，`frontend/scene.html:25-32`），前置登入與「我的專案」選擇專案，後接「成果報告與明細」頁。**步驟清單的唯一權威是 `README.md`「現行八步流程」段**，本文件不重抄；本節之下的使用者故事以步驟區間分 Epic。內部技術步驟拆分（前端 11 個內部狀態，數個狀態共用同一畫面）屬工程細節，歸 srs 與 ui_spec。

---

## 2. 商業目標

| 項目 | 內容 |
| :--- | :--- |
| **背景與痛點** | 一句話：平面圖到設計提案之間缺少可自助操作的工具。完整商業背景與痛點歸 [brd.md](./brd.md) §1–§2。 |
| **策略契合度** | AIPE03 結業專題；於成果發表向評審與到場廠商展示完整工程能力（發表日未查證，見 §1）。 |
| **成功指標** | 見下表；舊版 KPI 中已失效者標明，不冒充現行目標。 |

| KPI | 目前狀態（2026-08-07 實測） | 判定方式 |
| :--- | :--- | :--- |
| 自動化測試全數通過（主要） | 測試庫收集 1,053 個測試／113 個測試檔（`tests/test_*.py` 計數，不含共用 `conftest.py`；`pytest --collect-only` 實測）；本輪僅收集未執行，通過狀態由 `/verify` 以完整執行證據判定 | `pytest -q` 全綠 |
| 正式家具資料一致性（主要） | 雲端型錄恆等 8,557 件且逐筆驗證，不符即拒絕載入（`backend/catalog/cloud_catalog.py:15`）；資料庫實際可選 7,958 件（599 件停用過濾，live 查詢實測） | 載入驗證＋資料庫核對 |
| 平面圖辨識品質（主要） | 舊驗收基準（floor04 圖：19 牆／5 門／5 窗／7 房）已自現行 `README.md` 移除，現行基準**待重新指定**（見 Q-004） | 待補 |
| 成果發表就緒（次要） | 八步流程加成果報告端到端可走（第 8 步生圖→報告目視 QA 尚有缺口，屬 `/verify` 範圍） | 端到端實走 |

---

## 3. 使用者故事與允收標準

允收標準一律 Given / When / Then，寫成使用者可觀察的行為；工程座標（檔案、常數、狀態碼）退到各 Epic 的「依據」附註，正式 FR/NFR 枚舉歸 [srs.md](./srs.md)。情境 ID `SCN-<AREA>-NN` 供測試設計引用。本專案無 `.feature` 檔。

### Epic AUTH：帳戶與存取（前置步驟）

| ID | 描述 (As a / I want to / So that) | 允收標準（Given / When / Then） | 情境ID |
| :--- | :--- | :--- | :--- |
| US-AUTH-01 | As a 新使用者, I want to 註冊帳號並登入, so that 我的專案有擁有者且進度可保存。 | 1. Given 尚無任何帳號，When 第一位使用者完成註冊，Then 該帳號自動成為管理員並收養既有專案（BR-008）2. Given 已註冊帳號，When 以正確帳密登入，Then 進入「我的專案」可建立或開啟專案 | SCN-AUTH-01 |
| US-AUTH-02 | As a 設計師, I want to 把專案分享給客戶或協作者, so that 對方能參與而不越權。 | 1. Given 專案已分享唯讀成員，When 該成員開啟專案，Then 只能檢視不能編輯 2. Given 未被分享的使用者，When 嘗試存取該專案，Then 系統表現如同專案不存在，不洩漏其存在性（BR-006） | SCN-AUTH-02 |

依據：`README.md`「帳戶端」段；守衛規則 `AGENTS.md`「不可違反的契約」（非成員回 404 非 403）；帳戶生命週期規則（改密碼撤銷 session、停用即時生效）歸 BR-007／BR-009，不在此重述。

### Epic PROJ：專案建立與恢復（第 1 步）

| ID | 描述 (As a / I want to / So that) | 允收標準（Given / When / Then） | 情境ID |
| :--- | :--- | :--- | :--- |
| US-PROJ-01 | As a 屋主, I want to 建立專案並隨時中斷後續作, so that 不必一次做完整個流程。 | 1. Given 已登入使用者，When 建立專案並完成部分步驟後關閉頁面，Then 再次開啟時已完成步驟與資料完整恢復 2. Given 專案進度資料超過保護上限，When 儲存，Then 明確拒絕並說明，不默默截斷 | SCN-PROJ-01 |
| US-PROJ-02 | As a 設計師, I want to 系統防止並行編輯互相覆蓋, so that 多視窗或多人操作不遺失工作。 | Given 同一專案在兩處開啟，When 兩邊先後儲存且後者基於較舊版本，Then 後者被拒絕並要求重新載入，不覆蓋已保存的進度 | SCN-PROJ-02 |

依據：進度上限 2MB（`backend/server/project_store.py:14`）；版本衝突以 revision 樂觀鎖拒絕（`projects_api.py:384` 一帶）；專案儲存支援 PostgreSQL 與本機兩種模式（`README.md`「帳戶端」段）。

### Epic FP：平面圖上傳、尺度與結構（第 2–4 步）

| ID | 描述 (As a / I want to / So that) | 允收標準（Given / When / Then） | 情境ID |
| :--- | :--- | :--- | :--- |
| US-FP-01 | As a 屋主, I want to 上傳 PNG/JPG/DXF 平面圖, so that 系統以我的實際格局做提案。 | 1. Given 支援格式的有效檔案，When 上傳，Then 接受並可進入辨識 2. Given 不支援的格式或內容無法讀取的檔案，When 上傳，Then 明確拒絕並說明原因 3. Given 超過大小上限的檔案，When 上傳，Then 以上限拒絕，服務不因此變慢或耗盡資源 | SCN-FP-01 |
| US-FP-02 | As a 屋主, I want to 確認公分尺度, so that 家具尺寸與空間比例正確。 | 1. Given 系統自動推得比例但信心低於門檻，When 進入確定尺寸步驟，Then 系統要求兩點標定人工確認，不得默默採用推測值 2. Given 使用者完成兩點標定，Then 以人工結果為準 | SCN-FP-02 |
| US-FP-03 | As a 屋主, I want to 確認辨識出的空間結構, so that 後續配置建立在正確結構上。 | 1. Given 辨識完成，When 檢視空間結構，Then 可逐項確認房間、牆、門、窗，並手動補畫樑與柱 2. Given 後續步驟中結構被大幅變更，Then 必須回到本步驟重新確認，系統重新驗證目前家具（BR-002） | SCN-FP-03 |

依據：副檔名白名單（`backend/server/projects_api.py:45`）；自動比例信心門檻 0.8（`backend/floorplan/vision/analysis.py:36`）；樑柱由使用者手繪標定屬設計決策（`README.md` 第 4 步敘述；團隊裁定，repo 內無獨立決策文件——待補 ADR 或決策紀錄）。

### Epic SCENE：需求問卷與 2D/3D 編輯（第 5–6 步）

| ID | 描述 (As a / I want to / So that) | 允收標準（Given / When / Then） | 情境ID |
| :--- | :--- | :--- | :--- |
| US-SCENE-01 | As a 屋主, I want to 用問卷表達全屋與逐房需求, so that 提案符合我的生活方式。 | 1. Given 已確認空間結構，When 進入需求問卷，Then 先選全屋風格、材質與冷氣範圍，再逐房確認用途、家具類型、尺寸與數量 2. Given 問卷含家電需求（冰箱、洗衣機等），Then 該需求保留給 AI 生圖反映，不出現在 2D/3D 自動擺設（BR-003） | SCN-SCENE-01 |
| US-SCENE-02 | As a 屋主, I want to 在同一畫面編輯 2D/3D 並走動預覽, so that 直觀比較不同方向。 | 1. Given 配置產生完成，When 在同一畫面編輯家具，Then 2D 與 3D 檢視同步更新，並可走動預覽 2. Given 使用者切換風格與色卡，Then 可在 6 風格 × 3 色卡＝18 種組合間比較 | SCN-SCENE-02 |

依據：`README.md`「現行八步流程」第 5–6 步；18 色卡（`backend/catalog/data/taiwan_style_cards.json` 實測 6 styles × 3 cards）；問卷結構與生圖上下文契約見 `docs/contracts/QUESTIONNAIRE_STYLE_MATERIAL_GENERATIVE_SPACE_CONTRACT.md`。

### Epic AGENT／CATALOG／RAG：AI 選件與家具資料（第 6 步）

| ID | 描述 (As a / I want to / So that) | 允收標準（Given / When / Then） | 情境ID |
| :--- | :--- | :--- | :--- |
| US-AGENT-01 | As a 屋主, I want to 讓 AI 依需求選家具, so that 不必自己逐件挑選。 | 1. Given 問卷完成，When 產生配置，Then 系統自動為各房選出家具，且單一房間家具種類有上限，不會塞爆房間 2. Given AI 選件服務不可用或失敗，Then 自動改用本地規則完成選件，結果標明實際來源，流程不中斷 3. Given 使用者已指定的家具，Then 不被系統擅自移除 | SCN-AGENT-01 |
| US-CATALOG-01 | As a 屋主, I want to 選到的家具都來自正式型錄, so that 每件都有可視化模型與可信資料。 | 1. Given 正式資料庫可用，When 第 6 步選家具，Then 家具來自團隊正式資料庫（本輪實測可選 7,958 件），模型由雲端交付 2. Given 資料庫暫時不可用，Then 系統明確回報家具選件暫時無法使用、不自行混用其他資料；改用已驗證備援清單須由團隊明確切換離線模式（BR-011）3. Given 隔離區或未匹配資料，Then 永不出現在選件、畫面與提案（BR-010） | SCN-CATALOG-01 |
| US-RAG-01 | As a 屋主, I want to 用日常語言描述想要的房間, so that 系統聽得懂並找出合適家具。 | 1. Given 屋主的口語描述，When 送出檢索，Then 得到符合房型、風格與預算的家具候選清單 2. Given 語意檢索模型尚未載入完成，Then 先回結構化過濾結果並標示可補算，不阻塞使用 | SCN-RAG-01 |

依據：每房家具種類上限 8（`backend/agent/select.py:32`）；選件來源標記（`backend/server/scene_api.py:358,363`）；資料庫可選數為 2026-08-07 live 查詢 `roompilot.furniture_catalog_current`；檢索服務背景預載與降級（`backend/server/main.py:292-294` 註解）；檢索詞彙 6 風格／24 氛圍詞／19 家具群組（`backend/spatial_data/rag/data/taxonomy.json:19`、`category_groups.json` 實測）。

### Epic ENGINE：幾何合法性（第 6 步）

| ID | 描述 (As a / I want to / So that) | 允收標準（Given / When / Then） | 情境ID |
| :--- | :--- | :--- | :--- |
| US-ENGINE-01 | As a 屋主, I want to 系統擋下不合法的擺放, so that 拿到的配置在現實中放得下、走得過。 | 1. Given AI 或使用者擺放家具，When 位置造成碰撞、淨空不足或超出邊界，Then 系統標示問題並阻擋進入下一步（BR-001）2. Given 自動擺放失敗，Then 系統自我修復重試至多三輪，仍失敗才升級人工處理；使用者指定的家具只升級、不自動替換 3. 家具位置是否合法只由幾何引擎判定，畫面顯示不得自行放寬 | SCN-ENGINE-01 |

依據：修復輪數上限（`backend/agent/place.py:137` `max_rounds=3`）；合法性唯一判定者 `backend/engine/`（`AGENTS.md`「不可違反的契約」）。

### Epic RENDER：視角鎖定與 AI 渲染（第 7–8 步）

| ID | 描述 (As a / I want to / So that) | 允收標準（Given / When / Then） | 情境ID |
| :--- | :--- | :--- | :--- |
| US-RENDER-01 | As a 屋主, I want to 逐空間選擇並微調生成視角, so that 成果圖拍在我想看的角度。 | Given 方案鎖定，When 逐空間選擇生成視角，Then 可微調並保存每個空間的視角，狹窄房間的鏡頭不會卡進牆內 | SCN-RENDER-01 |
| US-RENDER-02 | As a 屋主, I want to 送出 AI 渲染取得寫實成果, so that 提案看得見最終氛圍。 | 1. Given 已鎖定方案與視角，When 送出渲染，Then 系統受理並回報處理進度 2. Given 渲染供應商未設定，Then 明確回報不可用，不得假成功 3. 送出的資料剝除姓名、電話、Email 等私人欄位 4. 單次送出的任務量有上限，超量明確拒絕 | SCN-RENDER-02 |

依據：渲染受理與兩種模式（`backend/server/render_service.py:11`、`projects_api.py:563`）；私人欄位剝除（`render_service.py:17`）；任務總量上限（`render_service.py:12-14`，commit `2d5111be`）；窄房間鏡頭修正（commit `576590ac`）；遠端渲染契約見 `docs/contracts/REMOTE_RENDER_CONTRACT.md`。

### Epic REPORT：成果報告與明細（第 9 步）

| ID | 描述 (As a / I want to / So that) | 允收標準（Given / When / Then） | 情境ID |
| :--- | :--- | :--- | :--- |
| US-REPORT-01 | As a 設計師, I want to 把鎖定版方案轉成成果報告, so that 客戶拿到採購與施工的完整明細。 | 1. Given 已鎖版方案，When 在成果報告頁產出報告，Then 得到 HTML／XLSX／JSON 三種格式，內容含設計風格語彙、家具採購明細、工程施工費與初步工期 2. 家具採購與工程施工費分開列示、不予合計；查無價格者不以已知小計冒充總價（BR-004）3. 設計語彙如實標示團隊編纂之信心程度（BR-005）4. Given 本機缺 XLSX 轉換元件，Then 其他格式照常產出，並明確標示 XLSX 不可用而非整包失敗 | SCN-REPORT-01 |

依據：`README.md` 第 9 步說明；XLSX 缺席降級（`backend/server/engineering/api.py:337`、commits `791ded44`／`3f479c6b`）；報告資料契約見 `docs/contracts/ENGINEERING_DOCUMENT_MVP.md` 與 `report_payload.schema.json`。

---

## 4. 範圍與限制

| 項目 | 內容 |
| :--- | :--- |
| **功能範圍** | 對應 `README.md`「主要資料夾」與「團隊責任」表：平面圖辨識與 3D 升維（Cody）、空間關係與家具語意檢索（Django）、家具型錄與雲端模型交付（Kai）、需求解析與選件（Yen）、幾何擺放引擎（Ancai）、FastAPI 整合＋帳戶端＋八步網頁＋成果報告（Bella）、辨識測資（Cody，Ben 協作）、辨識 QA 與評估證據（Ben）——依 `docs/TEAM_AI_OWNERSHIP.md` 責任表，`testdata/` owner 為 Cody、Ben 為協作；README 團隊表把「測資與證據」歸 Ben，兩份文件待對齊（多來源不一致）。伺服器對外介面 2026-08-07 實測共 77 條路由（含 8 條頁面路由；API 端點 69。44 GET／28 POST／2 PUT／2 DELETE／1 PATCH，runtime 枚舉），逐路由規格歸 04_design/api_spec。 |
| **非功能需求** | 概述四類，正式枚舉與門檻歸 [srs.md](./srs.md)：安全隱私（渲染剝除私人欄位、專案存在性不洩漏、上傳與進度大小上限）／一致性（跨模組幾何公分制、`_cm`/`_m2` 與 schema version，`AGENTS.md`「不可違反的契約」）／可用性（LLM 與渲染供應商皆為可選外部依賴，失敗降級不中斷核心流程）／性能（型錄伺服器端分頁與快取、檢索模型背景預載） |
| **不做什麼** | - 不在本機做寫實渲染：由遠端供應商代理，未設定時明確回報不可用 - 不建第二套 FastAPI 或第二套正式前端；前端不自行實作幾何合法性判定 - 家電不進 2D/3D 自動配置（BR-003）- 隔離區資料不進正式功能（BR-010）- 容器化部署已於 2026-08-06 整套移除，達標後再議（D-001）- 樑柱自動辨識不在範圍：第 4 步由使用者手繪標定（見 Epic FP 依據） |
| **假設與依賴** | 假設：使用者可提供 PNG/JPG/DXF 平面圖。依賴：CloudFront 交付家具 GLB（正式模型唯一來源；IKEA 地端備援尚未完成，完成前不啟用本機模式，`README.md` 頂部）／OpenRouter LLM（可選）／遠端渲染供應商（需設定）／本機 PostgreSQL 17.10 + pgvector 0.8.2（2026-08-07 live 實測；資料庫不可用時系統明確回報、家具選件受阻，改用已驗證 JSON 備援須明確切換離線模式）／Python 3.12＋FastAPI，Three.js 由 repo 內建 vendor 載入，無執行期 CDN 依賴（`frontend/scene.html:1228-1235` importmap 實測） |

---

## 5. 待辦問題與決策

| ID | 描述 | 狀態 | 負責人 |
| :--- | :--- | :--- | :--- |
| Q-001 | 目標發表日 2026-08-20 在 repo 內無任何紀錄（未查證，團隊口述），需補正式來源 | 待補 | Ben |
| Q-002 | 型錄數量多來源不一致：資料檔名仍是 `furniture_catalog_cloud_9350.json`、多份舊文件寫 9,349/9,350，程式常數與 README 為 8,557，資料庫實際可選 7,958（599 件停用）；文件與檔名待收斂 | 待討論 | Kai |
| Q-003 | 燈具獨立表 2026-08-07 實測 637 件可用，另有 156 件待分流；分表偏離契約原文待四人確認（沿用 2026-08-02 紀錄，分流進度未複核） | 待討論 | Kai |
| Q-004 | 平面圖辨識驗收基準（舊 floor04：19 牆/5 門/5 窗/7 房）已自現行 README 移除，現行 KPI 待重新指定 | 待討論 | Cody、Ben |
| Q-005 | 2026-08-04 外部安全審查的開放項需逐項重盤：本輪已確認家具檢索資料端點已加登入守衛（`rag_api.py:32`），其餘（捷徑端點後門、首帳號自動成為管理員之部署注意）未逐項複核 | 待討論 | Bella |
| Q-006 | 步驟前置依賴是否僅前端強制、伺服器端不驗順序——沿用 2026-07-26 版發現，本輪未複核 | 待討論 | Bella |
| D-001 | Docker 容器化整套移除，回歸本機啟動；達標後才重新容器化（2026-08-06 裁定，commit `09891216`） | 已決定 | Ben |
| D-002 | 跨模組幾何一律公分制；辨識輸出與方案輸出分屬兩種資料（邊界契約見 `docs/contracts/LAYOUT_SCENE_BOUNDARY_CONTRACT.md`） | 已決定 | 全隊 |
| D-003 | 風格定案 6 風格 × 3 色卡＝18 張（`taiwan_style_cards.json` 實測） | 已決定 | 全隊 |
| D-004 | 家電保留為問卷與生圖上下文，不進 2D/3D 自動配置（BR-003） | 已決定 | 全隊 |
| D-005 | 第 6 步家具以 PostgreSQL 正式資料庫優先；回退已驗證 JSON 為明確人工切換離線模式，非系統自動（BR-011；系統行為見 US-CATALOG-01 允收） | 已決定 | Kai、Bella |
| D-006 | 正式模型來源唯一為 CloudFront；IKEA 地端 GLB 備援完成前不啟用本機模式（`README.md` 頂部） | 已決定 | Kai、Django |

---

## 6. 追溯

| 項目 | ID |
| :--- | :--- |
| 上游 | `requirements_tracker.xlsx` ①需求決策（本輪 Pilot 導入不實例化，DEC-* 待 owner 拍板）；[brd.md](./brd.md) 的 BR-001～BR-012 |
| 本文件產出 | US-`<AREA>`-NN（使用者故事）、SCN-`<AREA>`-NN（允收情境）；AREA ∈ {AUTH, PROJ, FP, SCENE, AGENT, CATALOG, RAG, ENGINE, RENDER, REPORT} |
| 下游 | [srs.md](./srs.md)（FR/NFR 正式枚舉，回引本文件 US/SCN）、03_architecture/sad、02_ux_ui/ui_spec、05_qa/test_plan 以 US/SCN 引用 |

查證附註：本文件數字均於 2026-08-07 以唯讀指令實測（`pytest --collect-only` 1,053 測試／113 檔；FastAPI runtime 路由枚舉 77 條路由（8 頁面＋69 API）；PostgreSQL live 查詢 8,557/7,958/637；`taiwan_style_cards.json`、`taxonomy.json`、`category_groups.json` 讀檔核對）。標「未查證」「沿用未複核」「待補」者為 repo 內查無依據或本輪未重驗的項目；追溯 ID 主鏈規範見 `docs/document-system/architecture.md` §7.1，此處不重述。
