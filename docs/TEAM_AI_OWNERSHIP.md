# RoomPilot 團隊 AI 責任與整合架構

本文件把遠端分支、目前 repository 目錄與模組責任對應起來。判斷依據是分支內容、現行程式、測試與既有文件；Git author 不能單獨視為 owner，因為 Bella 已整合多位組員的相容 patch。

## 遠端分支對照

| 組員 | 遠端分支 | 工作責任 | 整合原則 |
|---|---|---|---|
| Bella | `origin/bella` | 整合、FastAPI、保存、正式 UI、八步 2D/3D 工作流 | 以 Bella test 分支完成可驗證整合後再推送 |
| Cody | `origin/cody` | 辨識模型、測資評估、牆門窗房間 | 大型訓練資產不直接放入正式 runtime tree |
| Django | `origin/django` | 房間推論、家具符號證據、空間資料與 RAG 標註 | 只移植相容演算法與 schema，不整包搬 Version4 |
| Kai | `origin/kai`、`origin/kai-with-bellatest1` | catalog、AWS/CloudFront manifest、PostgreSQL 與資料交付 | Kai 資料庫為第 6 步家具主來源 |
| Yen | `origin/yen` | 需求結構化、偏好、選件與修復決策 | 正式 UI 由 Bella 接入 |
| Ancai | `origin/ancai`、`origin/ancai-dev` | 配置引擎與 2D+3D 互動原型 | scene-lab 類實驗必須經 Bella 驗證後進正式 UI |
| Ben | `origin/ben` 與 Cody 歷史 commit | 辨識 QA、模型/evaluation 資產、文件 | 與 Cody 共同維護辨識品質，與 Bella 做發布驗證 |

## 目錄責任與資料流

| 目錄 | Owner | 協作方 | 輸入 | 輸出／功能 |
|---|---|---|---|---|
| `backend/server/` | Bella | 各 owner 的 adapter | HTTP、專案狀態、`layout_json`、需求 | FastAPI、保存、八步 UI、`scene_json` 調度 |
| `backend/server/static/` | Bella | Yen、Ancai、Cody、Django | API payload | 正式 HTML/CSS/JS/Three.js 編輯介面 |
| `backend/floorplan/` | Cody | Django、Ben | PNG/JPG/DXF、尺度校正 | 牆、門、窗、房間、信心度與 `layout_json` |
| `backend/spatial_data/` | Django | Cody、Ancai、Bella | 已確認房間與開口幾何 | 空間尺寸、相鄰與 evaluation 記錄，不負責渲染 |
| `backend/catalog/` | Kai | Django、Bella | 官方 catalog、資產 manifest | 已驗證家具/材質、三視角圖、RAG metadata |
| `JSON/` | Kai | Bella | 匯入/匯出中介資料 | 家具 JSON 與 GLB/圖片 manifest |
| `scripts/sql/` | Kai | Bella | 已驗證 JSON/CSV | PostgreSQL schema、dry-run、transactional import |
| `backend/agent/` | Yen | Kai、Ancai、Bella | 需求、房間、候選家具 | 選件、說明、修復意圖；不輸出合法座標 |
| `backend/engine/` | Ancai | Yen、Bella | 房間、牆、候選家具 | 擺放、碰撞、淨空、移動與合法性 |
| `backend/upgrade3d/` | Cody | Ancai、Bella | 已確認 DXF/layout | 3D 可用的牆、地板、門窗幾何 |
| `testdata/` | Cody | Django、Ben | 圖片/DXF/ground truth | 可重現辨識測資 |
| `tests/` | 對應 owner | Bella 整合 | 公開行為 | 單元、API、契約與視覺回歸門檻 |
| `docs/contracts/` | Bella | 受影響 owner | 已協議介面 | 跨目錄 schema 與生命週期唯一依據 |

`.runtime/`、`.tmp/`、cache、模型權重與本機資料庫沒有原始碼 owner，且不得提交。

## 目前正式架構

```text
平面圖 PNG/JPG/DXF
  -> Cody 辨識與使用者確認
  -> Django 空間關係與 evaluation 證據
  -> layout_json
  -> Yen 解析逐房需求與選件意圖
  -> Kai PostgreSQL / CloudFront 家具、三視角圖與 RAG metadata
  -> Ancai 幾何配置、碰撞與淨空驗證
  -> scene_json
  -> Bella FastAPI、專案保存、正式 2D/3D UI
  -> 第 7 步鎖定逐房視角 -> 第 8 步 AI 生圖
```

Graph RAG 只補強 Kai/Django 的房間、風格、家具、材質、限制關係與可追溯證據；Ancai 仍是幾何與規則的唯一裁決者。

### Kai catalog 與家電邊界

- Kai 官方 JSON catalog 是第 6 步家具 API 的預設來源，目前有 8,557 筆。PostgreSQL `roompilot.furniture_catalog_current` 完成同批資料匯入後，才可透過環境變數啟用。
- 每筆正式家具有 GLB 與 `front`、`side`、`angle-45` 三視角 CloudFront PNG。
- 開發與展示預設讀取同一份 Kai JSON；PostgreSQL 連線失敗時也回退到這份 JSON，確保資料版本一致。
- 冰箱、洗衣機等家電仍可由問卷收集，會寫入 `questionnaire.appliance_requirements` 與 `scene_json.render_context`，供 AI 生圖理解需求；它們不進第 6 步 2D/3D 自動配置、不出現在正式家具 API。

## 共用修改流程

1. 資料生產 owner 先修改並版本化契約。
2. 消費端 owner 更新 adapter，不重做生產端演算法。
3. Bella 驗證 API、保存與端到端 UI。
4. 生產端與消費端皆須有測試。
5. 同步更新 owner profile 與受影響的契約文件。

例子：新平面圖欄位由 Cody 負責，涉及空間資訊時與 Django 協作，再由 Bella 寫 adapter 測試；新家具 metadata 由 Kai 與 Yen 確認檢索語意，Bella 更新 API/UI；新擺放規則由 Ancai 定義、Yen 說明，Bella 完成 workflow 測試。

## Owner Profiles

- [Bella](owners/BELLA.md)
- [Cody](owners/CODY.md)
- [Django](owners/DJANGO.md)
- [Kai](owners/KAI.md)
- [Yen](owners/YEN.md)
- [Ancai](owners/ANCAI.md)
- [Ben](owners/BEN.md)
