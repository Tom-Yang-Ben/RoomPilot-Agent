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

| Owner | 主要目錄 | 作用 |
|---|---|---|
| Bella | `backend/server/`、`frontend/` | FastAPI、保存、八步流程與正式 UI 整合 |
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
5. 正式 production frontend 只有 `frontend/`。

## 家具、家電與資料庫

第 6 步優先讀取 Kai PostgreSQL view `roompilot.furniture_catalog_current`。目前正式 view 有 7,958 筆啟用家具（`furniture_items` 共 8,557 筆，其中 599 筆因品質標記 `is_active = false` 而未進 view），每筆資料包含 GLB、正面/側面/45 度 PNG、房間類型、風格、材質、尺寸與 VLM/RAG 說明。燈具另走 `roompilot.lighting_assets`（793 筆，`lighting_assets_current` 637 筆可用），不在本 view 內。資料庫暫時不可連線時，才使用 repository 內已驗證的 8,557 筆 JSON catalog（`JSON/furniture/furniture_official_catagory.json`）。

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
| `/api/furniture` | 搜尋 Kai PostgreSQL 優先的家具 catalog |
| `/api/catalog/status` | 查看目前使用的 catalog provider |
| `/api/projects/{project_id}/render-jobs` | 送出鎖定視角的 AI 渲染任務 |

## 協作與驗證

跨資料夾修改前請閱讀根目錄 `AGENTS.md`，並同時更新 producer/consumer 的測試。不要直接整包合併遠端分支，也不要帶入第二套後端、重複前端、未驗證大檔或私密 `.env`。

```powershell
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
git status --short
```
