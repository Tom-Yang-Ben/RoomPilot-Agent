# RoomPilot 現行版本總覽

本文件描述目前可由程式、測試與正式資料庫核對的架構。README 負責安裝與啟動；本文件負責跨模組協作與資料邊界。若文件和程式衝突，依序以自動化測試、可執行程式、正式契約、本文件為準。

## 正式八步流程

正式入口是 `/scene`：

| 步驟 | 名稱 | 使用者確認結果 |
|---|---|---|
| 1 | 建立專案 | 產生可保存與恢復的 `project_id` |
| 2 | 上傳平面圖 | 上傳 PNG/JPG/DXF 原始檔 |
| 3 | 確定尺寸 | 用已知線段校正比例，統一為公分 |
| 4 | 空間與結構 | 校正房間、牆、門、窗、樑、柱，輸出 `layout_json` |
| 5 | 需求問卷 | 全屋與逐房需求、家具偏好、家電需求與三張風格色卡 |
| 6 | 配置與預覽 | 由 Kai 家具 + Ancai 幾何規則生成並同步編輯 2D/3D `scene_json` |
| 7 | 方案鎖定與視角 | 每個空間選擇、微調並鎖定生圖視角 |
| 8 | AI 渲染與成果 | 依問卷、色卡、材質、家具與鎖定視角逐房生圖 |

第 4 步結構改動會使後續配置失效；系統必須重新驗證家具。未處理的碰撞、淨空、超界或 GLB 載入問題會顯示原因並阻擋進入下一步。

## 資料流與權責

```text
平面圖 -> Cody 辨識 + 使用者校正 -> layout_json
        -> Yen 需求與選件意圖
        -> Kai PostgreSQL / CloudFront catalog、三視角圖、RAG metadata
        -> Ancai 配置、碰撞與淨空驗證
        -> scene_json -> Bella 正式 2D/3D UI 與專案保存
        -> 鎖定逐房相機 -> AI 渲染
```

正式專案保存的 runtime adapter 使用 PostgreSQL `roompilot.projects.workflow_json` JSONB 與 `roompilot.render_outputs`；SQLite 僅供明確離線模式。現行 repository 缺少 Phase 3 schema／migration 工具與 engineering PostgreSQL tables，不能把歷史 migration 指令視為目前可重建流程。

| Owner | 主要目錄 | 作用 |
|---|---|---|
| Bella | `backend/server/`、`backend/server/static/` | FastAPI、保存、八步流程與正式 UI 整合 |
| Cody | `backend/floorplan/`、`backend/upgrade3d/` | 平面圖辨識、開口/房間與 3D 結構 adapter |
| Django | `backend/spatial_data/` | 尺寸、房間關係、layout evaluation 與 RAG 證據 |
| Kai | `backend/catalog/`、`JSON/`、`scripts/sql/` | 正式家具、資產 manifest、PostgreSQL 與 RAG metadata |
| Yen | `backend/agent/` | 需求理解、選件、修復意圖與說明 |
| Ancai | `backend/engine/` | 配置、旋轉、碰撞、淨空、移動與合法性 |
| Ben | `testdata/` 與辨識 QA | 測資、模型評估與發布證據 |

詳細分支與協作規則請看 [團隊 AI 責任與整合架構](TEAM_AI_OWNERSHIP.md)。

## 重要資料邊界

1. 跨模組長度與平面座標都使用公分；新欄位加 `_cm`，面積加 `_m2`。
2. 辨識輸出是 `layout_json`；設計、配置、編輯輸出是 `scene_json`。
3. Graph RAG 只負責關係檢索與證據，不負責幾何、碰撞、淨空或結構決策。
4. 家具合法性只能由 `backend/engine/` 判定；前端只呈現與送出操作。
5. 正式 production frontend 只有 `backend/server/static/`；`frontend3d/` 是次要原型。

## 家具、家電與資料庫

Kai 正式 catalog 共 8,675 筆家具，其中 8,076 筆為 active／RAG-indexable，透過 PostgreSQL view `roompilot.furniture_catalog_api_current` 提供給第 6 步與家具 RAG；另有 599 筆 inactive 家具保留複核且不得進正式 API／RAG。5 份匯入來源的 ID 已完整一致：8,675 筆 JSON items、8,675 筆 GLB，以及 26,025 筆正面／側面／45 度三視圖。每筆 catalog 家具都包含 GLB、三視角 PNG、房間類型、風格、材質、尺寸與 VLM/RAG metadata。正式 `postgres` 模式不可連線時 API 回傳 503；只有明確設定 `ROOMPILOT_CATALOG_PROVIDER=json` 才使用同一份 8,675 筆 JSON 離線資料，且公開家具仍只限 8,076 筆 active 資料。

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
| `/api/health` | 檢查正式家具、runtime catalog 與 project store 的 PostgreSQL readiness |
| `/api/projects/{project_id}/render-jobs` | 送出鎖定視角的 AI 渲染任務 |

## 協作與驗證

跨資料夾修改前請閱讀根目錄 `AGENTS.md`，並同時更新 producer/consumer 的測試。不要直接整包合併遠端分支，也不要帶入第二套後端、重複前端、未驗證大檔或私密 `.env`。

```powershell
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
git status --short
```
