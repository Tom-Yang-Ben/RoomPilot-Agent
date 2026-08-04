# RoomPilot AI 協作守則

本文件適用於整個 repository。修改任何檔案前都必須先閱讀。

## 動手前必做

1. 閱讀 `README.md`，確認目前八步產品流程與啟動指令。
2. 閱讀 `docs/TEAM_AI_OWNERSHIP.md` 與目標 owner 的 `docs/owners/` 說明。
3. 閱讀最近的 `AGENTS.md` 與相關 `docs/contracts/`。
4. 執行 `git status --short`，保留他人尚未提交的變更。
5. 追查本次行為的輸入、輸出、座標單位、保存邊界與測試。
6. 修改前說明預計修改的檔案與驗證指令。

不得整包複製或合併遠端成員分支；只能檢視後移植最小且相容的功能。

## 跨資料夾修改

只有確實需要整合時才能改動其他 owner 的目錄。修改前須記錄：

```text
跨資料夾修改
- 主要 owner：
- 協作 owner：
- 修改檔案：
- 改變的資料契約或流程：
- 為何不能只在單一目錄完成：
- 兩端驗證測試：
```

共享契約必須同時驗證生產端與消費端。前端 fallback 不得悄悄取代後端演算法；整合端也不得重做其他 owner 的核心領域邏輯。

## 目錄責任與資料邊界

| 路徑 | 主要 owner | 主要責任 |
|---|---|---|
| `backend/server/` | Bella | FastAPI、專案保存、八步 UI、2D/3D 調度 |
| `backend/floorplan/` | Cody | 影像/DXF 辨識、牆門窗房間、`layout_json` |
| `backend/spatial_data/` | Django | 空間尺寸、房間關係、layout evaluation schema、家具 RAG 檢索與排序 |
| `backend/catalog/`、`JSON/`、`scripts/sql/` | Kai | 正式家具、CloudFront 資產、PostgreSQL 匯入與 RAG metadata |
| `backend/agent/` | Yen | 需求結構化、選件、修復意圖與說明 |
| `backend/engine/` | Ancai | 配置、碰撞、淨空、移動與幾何合法性 |
| `backend/upgrade3d/` | Cody | 已確認 layout 轉為 3D 可用結構 |
| `frontend3d/` | Bella | 次要 React/R3F 原型，不是正式流程 |
| `testdata/` | Cody | 辨識測資；Django 協助空間標註檢視 |
| `tests/` | 對應模組 owner | 契約與回歸；Bella 維護端到端整合門檻 |
| `docs/contracts/` | Bella 整合 | 跨目錄公開契約，受影響 owner 必須共同確認 |

## 不可違反的契約

- 跨模組幾何使用公分；新長度與座標欄位使用 `_cm`，面積使用 `_m2`。
- 舊欄位 `width`、`depth`、`pos_x`、`pos_y` 必須同時帶 `coordinate_unit: "cm"` 與 schema version。
- 平面圖辨識輸出是 `layout_json`；方案生成與編輯輸出是 `scene_json`。
- Graph RAG 只檢索房間、家具、風格、材質與限制的關係與證據，不決定幾何、碰撞、淨空或結構合法性。
- 家具向量 RAG 只解析需求、檢索與排序 Kai PostgreSQL 家具；不得取代 Yen 選件決策或 Ancai 幾何判定。
- 家具合法位置只由 `backend/engine/` 判定。
- 第 6 步正式家具以 Kai PostgreSQL `roompilot.furniture_catalog_current` 優先；資料庫不可用時才回退已驗證 JSON。
- 冰箱、洗衣機等家電保留為問卷與 AI 生圖上下文，不能進入 2D/3D 自動配置或正式家具 API。
- 隔離區或未匹配資料不得進 API 或場景。
- 正式網頁在 `backend/server/static/`；不得以 `frontend3d/` 取代，除非已明確核准遷移。
- 不得提交 `.env`、本機 runtime、快取、模型權重或大型 GLB 壓縮檔。

## 驗證矩陣

| 變更類型 | 最低驗證 |
|---|---|
| Python 領域模組 | 對應測試加 `pytest -q` |
| FastAPI 或保存 | API 測試加 `pytest -q` |
| 靜態前端／Three.js | JS 語法、契約測試、實際瀏覽器 QA |
| 平面圖辨識 | 使用 `testdata/` 的 vision/evaluation 測試 |
| Catalog／SQL | dry-run、資料契約測試、PostgreSQL view 檢查 |
| React 原型 | `npm ci`、`npm run build` |
| 文件／責任 | 連結與指令可用性檢查 |

最終整合指令：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
git status --short
```
