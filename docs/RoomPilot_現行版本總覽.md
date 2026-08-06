# RoomPilot 現行版本總覽

文件版本：2026-08-06。

本文件描述目前可由程式、測試與實際瀏覽器核對的架構。README 負責安裝與啟動；本文件負責跨模組協作與資料邊界。若文件和程式衝突，依序以自動化測試、可執行程式、正式契約、本文件為準。

## 正式八步流程

正式入口是 `/scene`：

| 步驟 | 名稱 | 使用者確認結果 |
|---|---|---|
| 1 | 建立專案 | 產生可保存與恢復的 `project_id` |
| 2 | 上傳平面圖 | 上傳 PNG/JPG/DXF 原始檔 |
| 3 | 確定尺寸 | 用已知線段校正比例，統一為公分 |
| 4 | 空間與結構 | 校正房間、牆、門、窗、樑、柱，輸出 `layout_json` |
| 5 | 需求問卷 | 全屋與逐房需求、家具偏好、家電需求與三張風格色卡 |
| 6 | 配置與預覽 | 由 Kai 家具 + Ancai 幾何規則生成 2D/3D `scene_json`；牆面與地面材質以 `room_id` 逐房保存 |
| 7 | 方案鎖定與視角 | 每房從三個候選視角選一個；每個候選都綁定正確 `room_id` 並呈現全室，再確認代表房全屋色卡 |
| 8 | AI 渲染與成果包 | 確認問卷／RAG 大致詞彙，完成全屋初稿後每張房間圖最多一次修圖，最後建立簡報、明細、工程與預算報告 |

第 4 步結構改動會使後續配置失效；系統必須重新驗證家具。未處理的碰撞、淨空、超界或 GLB 載入問題會顯示原因並阻擋進入下一步。

## 已實作、待整合與驗收

| 能力 | 狀態 | 驗收方式 |
|---|---|---|
| Step 6 逐房牆面／地面材質 | 已實作 | 修改一個 `room_id` 後重載專案；其他房間 surface override 不得改變，3D 共享牆兩側依各房資料顯示 |
| Step 6 房間座標 | 已修正 | 主場景與家具更換預覽都保留確認版平面圖座標；預覽只移動相機，並依 `room_id` 篩選該房地面、牆與家具 |
| Step 6 家具替換照片 | 已實作 | 搜尋結果優先顯示 catalog `image_url`／`thumbnail_url` 或三視圖；載入失敗顯示「暫無圖片」，卡片尺寸不得位移 |
| Step 6 家具替換照片 | 已實作 | 搜尋結果優先顯示 catalog `image_url`／`thumbnail_url` 或三視圖；載入失敗顯示「暫無圖片」，卡片尺寸不得位移 |
| Step 7 每房全室視角 | 已實作 | 候選相機含對應 `room_id`，相機在房間 polygon 內，畫面可辨識全室主要家具、門窗與動線；陽台不得復用臥室相機 |
| Step 8 首次生圖與一次修圖 | 已實作 | 全屋初稿完成後逐房檢查；同一房間第二次成功 edit 回 409，失敗請求不得消耗額度 |
| Step 8 Web／JSON 成果包 | 已實作 | `/design-delivery` 回傳逐房簡報、工程報告、家具／裝潢明細、預算與資安基線結果 |
| Yen `RequirementSkill` 專業化問卷 | 待整合 | 正式 Step 5 API 必須實際呼叫 skill、保存來源與輸出版本；目前只有模組／測試，不能標示 runtime 完成 |
| Yen `ReportAgent` | 待整合 | `/design-delivery` 必須消費 Report Agent 的版本化輸出；目前端點是 Bella deterministic builder |
| 最終資安工程審核 | 部分實作 | 現行只驗證敏感欄位名稱 denylist 移除；完整 schema allowlist、內容掃描、權限與稽核仍待整合 |

## 資料流與權責

```text
平面圖 -> Cody 辨識 + 使用者校正 -> layout_json
        -> 第 5 步家具 RAG jobs（已接線）
        -> Yen RequirementSkill 專業化（模組已存在，正式 Step 5 adapter 待整合）
        -> Kai PostgreSQL / CloudFront catalog、三視角圖、RAG metadata
        -> Ancai 配置、碰撞與淨空驗證
        -> scene_json -> Bella 正式 2D/3D UI 與 SQLite 專案保存
        -> 鎖定單一配置 -> Yen 逐房視角 -> AI 初稿／一次修圖
        -> Bella deterministic 成果包：逐房簡報、工程、denylist 資安基線與預算
        -> Yen ReportAgent：模組已存在，正式成果包 adapter 待整合
```

現行 `backend/server/main.py` 直接使用 `ProjectStore`，實作是 SQLite `projects.sqlite3`，保存 project、workflow、upload 與 render metadata。`.env.example` 雖保留 PostgreSQL project store 目標設定，但目前 `main.py` 尚未依該變數切換 provider；不得把 PostgreSQL project JSONB 寫成現行已上線功能。家具與 runtime catalog 仍可使用 Kai PostgreSQL provider，兩者不可混為同一資料庫邊界。

| Owner | 主要目錄 | 作用 |
|---|---|---|
| Bella | `backend/server/`、`backend/server/static/` | FastAPI、保存、八步流程與正式 UI 整合 |
| Cody | `backend/floorplan/`、`backend/upgrade3d/` | 平面圖辨識、開口/房間與 3D 結構 adapter |
| Django | `backend/spatial_data/` | 尺寸、房間關係、layout evaluation、RAG 查詢／排序證據與工程空間摘要 |
| Kai | `backend/catalog/`、`JSON/`、`scripts/sql/` | 正式家具、資產 manifest、PostgreSQL 與 RAG metadata |
| Yen | `backend/agent/` | 問卷專業化、選件、修復意圖、生圖／修圖 prompt 與報告語意 |
| Ancai | `backend/engine/` | 配置、旋轉、碰撞、淨空、移動與合法性 |
| Ben | `testdata/` 與辨識 QA | 測資、模型評估與發布證據 |

詳細分支與協作規則請看 [團隊 AI 責任與整合架構](TEAM_AI_OWNERSHIP.md)。

## 重要資料邊界

1. 跨模組長度與平面座標都使用公分；新欄位加 `_cm`，面積加 `_m2`。
2. 辨識輸出是 `layout_json`；設計、配置、編輯輸出是 `scene_json`。
3. Graph RAG 只負責關係檢索與證據，不負責幾何、碰撞、淨空或結構決策。
4. 家具合法性只能由 `backend/engine/` 判定；前端只呈現與送出操作。
5. 正式 production frontend 只有 `backend/server/static/`；`frontend3d/` 是次要原型。
6. 第 6 步沒有公開 A/B；舊 A/B 欄位只能作歷史資料相容。逐房 surface override 必須以 `room_id` 為主鍵，不能用陣列索引或房名猜測。
7. 房間、地面、牆與家具沿用確認版 `layout_json`／`scene_json` 的全域公分座標；切換房間只改相機，不得重置幾何中心。
8. 第 7 步視角只改相機；每個 camera manifest 必須保存 `room_id`。第 8 步 prompt 不得改空間、結構、固定家具與視角。
9. 每房初稿圖片的一次修圖由後端保存狀態強制；前端停用按鈕不是唯一防線。
10. 成果包目前以固定輸出形狀組稿，再依敏感欄位名稱 denylist 移除資料；這不是完整欄位 whitelist。價格若缺來源應待報價，但現行 builder 尚未強制 `price_source` 與金額同時存在，此項列為待補強。

## 家具、家電與資料庫

2026-08-06 live PostgreSQL 由 `roompilot.furniture_catalog_current` 提供 7,958 筆家具；`/api/catalog/status` 驗證 7,958 個 GLB 及 23,874 張正面／側面／45 度圖，`/api/rag/status` 驗證 7,958 筆 current BGE-M3 向量。`backend/server/postgres_catalog.py` 與 `backend/catalog/postgres_repository.py` 都讀這個 view；`furniture_catalog_api_current` 可能存在於舊 schema，但不是目前 runtime 來源。舊文件中的 8,675／8,076 是歷史匯入批次，不得用來宣稱現行服務 ready。正式 `postgres` 模式不可連線時 API 回傳 503；只有明確設定 `ROOMPILOT_CATALOG_PROVIDER=json` 才使用離線資料。

Phase 4、5 的 live PostgreSQL 目前有 6 個 design style profiles、18 張風格卡、571 筆牆面／地板材質、6 筆裝修單價、10,518 筆外部匯入隔離資料與 595 筆 RAG documents。正式 FastAPI 只做 SQL read-through，不掃描 JSON／CSV，也不保存會讓資料過期的 process cache。現行 repository 缺少 Phase 4 schema／importer，因此這些既有資料可讀，但新環境尚不能從本 repo 從零重建。

冰箱、洗衣機等家電不是第 6 步可自動擺放家具：問卷仍會保存它們，並寫入 `questionnaire.appliance_requirements` 與 `scene_json.render_context`，讓第 8 步生圖能反映使用者需求。

正式 GLB 與 PNG 由 CloudFront 交付。未匹配或隔離資料不得出現在 API、Agent 候選或 3D 場景。

## 主要 API

| API | 用途 |
|---|---|
| `/api/projects`、`/api/projects/{project_id}` | 建立與讀取專案 |
| `/api/projects/{project_id}/workflow` | 保存八步工作流 |
| `/api/projects/{project_id}/floorplan/analyze` | 分析專案平面圖 |
| `/api/floorplan/confirm` | 確認並取得 `layout_json` |
| `/api/scene/generate` | 依需求與 `layout_json` 生成 `scene_json` |
| `/api/scene/layout`、`/api/scene/validate` | Ancai 配置與單件合法性驗證 |
| `/api/furniture` | 由 Kai PostgreSQL 執行搜尋、篩選、facet 與分頁 |
| `/api/catalog/status` | 查看目前使用的 catalog provider |
| `GET /api/render-provider/status` | 查看 legacy `/render-jobs` provider 是否有設定 URL |
| `GET /api/ai-render/status` | 回報 OpenRouter provider、主模型與 fallback，不回傳金鑰 |
| `POST /api/projects/{project_id}/ai-renders` | 依鎖定快照與 Yen prompt 逐房首次生圖 |
| `POST /api/projects/{project_id}/ai-renders/{room_id}/edit` | 每房唯一一次修圖，超額回 409 |
| `POST /api/projects/{project_id}/design-delivery` | 建立逐房 Web 簡報、工程報告、資安審核與預算明細 |
| `/api/projects/{project_id}/render-jobs` | 舊遠端渲染 provider 相容接口；非現行第 8 步主路徑 |

現行主程式沒有 `/api/health` 路由，不得在部署文件或監控中宣稱可呼叫。需要診斷時分別使用 `/api/catalog/status`、`/api/rag/status`、`/api/scene/provider-status`、`/api/ai-render/status` 與 legacy `/api/render-provider/status`；若要新增整體 readiness，必須先實作 route 與契約測試。

### 生圖 provider 邊界

| 路徑 | 啟用條件 | 說明 |
|---|---|---|
| 現行 Step 8 `/ai-renders`／`/edit` | `OPENROUTER_API_KEY` 非空 | `ai_render_service.py` 直接使用 Yen `GenPicAgent`；未設定時回 503，不產生假圖 |
| Legacy `/render-jobs` | `ROOMPILOT_RENDER_PROVIDER_URL` 非空 | 透過 `render_service.py` 呼叫外部 adapter；token 依 provider 選填 |

兩條 provider 狀態互不代表彼此已啟用。

## 協作與驗證

跨資料夾修改前請閱讀根目錄 `AGENTS.md`，並同時更新 producer/consumer 的測試。不要直接整包合併遠端分支，也不要帶入第二套後端、重複前端、未驗證大檔或私密 `.env`。

驗收不得引用會過期的固定測試總數。每次整合需記錄實際執行的測試檔、結果、瀏覽器桌面／手機截圖與 provider 回應。OpenRouter `configured=true` 只表示有金鑰與模型設定；若供應商回 402，必須如實顯示額度問題，不能視為生圖成功。

```powershell
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
git status --short
```
