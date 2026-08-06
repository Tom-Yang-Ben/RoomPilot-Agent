# RoomPilot 團隊 AI 責任與整合架構

文件版本：2026-08-06。

本文件把遠端分支、目前 repository 目錄與模組責任對應起來。判斷依據依序是通過的測試、現行程式、`docs/contracts/`、本文件與歷史分支；Git author 不能單獨視為 owner，因為 Bella 已整合多位組員的相容 patch。

AI 開始工作前先讀本文件，再讀對應 `docs/owners/<OWNER>.md`。遇到 A/B、九步／十步、Yen 尚未接入或第 8 步仍只用 `/render-jobs` 的描述時，視為歷史資料，不得覆蓋現行八步架構。

## 遠端分支對照

| 組員 | 遠端分支 | 工作責任 | 整合原則 |
|---|---|---|---|
| Bella | `origin/bella` | 整合、FastAPI、SQLite 專案保存、正式 UI、八步工作流、資安與成果包 | 以 Bella test 分支完成可驗證整合後再推送 |
| Cody | `origin/cody` | 辨識模型、測資評估、牆門窗房間 | 大型訓練資產不直接放入正式 runtime tree |
| Django | `origin/django` | 房間推論、家具符號證據、空間資料、layout evaluation、家具 RAG 證據 | 只移植相容演算法與 schema，不整包搬 Version4；報告與資安由跨 owner pipeline 完成 |
| Kai | `origin/kai`、`origin/kai-with-bellatest1` | catalog、AWS/CloudFront manifest、PostgreSQL 與資料交付 | Kai 資料庫為第 6 步家具主來源 |
| Yen | `origin/yen` | 問卷專業化、RAG 選件、修復意圖、生圖／修圖與報告語意 | 正式 UI、保存、一次修圖 API 與成果包由 Bella 接入 |
| Ancai | `origin/ancai`、`origin/ancai-dev` | 配置引擎與 2D+3D 互動原型 | scene-lab 類實驗必須經 Bella 驗證後進正式 UI |
| Ben | `origin/ben` 與 Cody 歷史 commit | 辨識 QA、模型/evaluation 資產、文件 | 與 Cody 共同維護辨識品質，與 Bella 做發布驗證 |

## 目錄責任與資料流

| 目錄 | Owner | 協作方 | 輸入 | 輸出／功能 |
|---|---|---|---|---|
| `backend/server/` | Bella | 各 owner 的 adapter | HTTP、專案狀態、`layout_json`、需求 | FastAPI、保存、八步 UI、`scene_json` 調度 |
| `backend/server/static/` | Bella | Yen、Ancai、Cody、Django | API payload | 正式 HTML/CSS/JS/Three.js 編輯介面 |
| `backend/floorplan/` | Cody | Django、Ben | PNG/JPG/DXF、尺度校正 | 牆、門、窗、房間、信心度與 `layout_json` |
| `backend/spatial_data/` | Django | Cody、Kai、Ancai、Bella | 已確認幾何或家具自然語言需求 | 空間 evaluation；家具 RAG 解析、檢索協調與排序，不負責渲染或幾何合法性 |
| `backend/catalog/` | Kai | Django、Bella | 官方 catalog、資產 manifest | 已驗證家具/材質、三視角圖、RAG metadata |
| `JSON/` | Kai | Bella | 匯入/匯出中介資料 | 家具 JSON 與 GLB/圖片 manifest |
| `scripts/sql/` | Kai | Bella | 已驗證 JSON/CSV | PostgreSQL schema、dry-run、transactional import |
| `backend/agent/` | Yen | Django、Kai、Ancai、Bella | 問卷、空間證據、候選家具、鎖定快照與視角 | 專業化需求、選件、說明、修復意圖、生圖／修圖與報告語意；不輸出合法座標 |
| `backend/engine/` | Ancai | Yen、Bella | 房間、牆、候選家具 | 擺放、碰撞、淨空、移動與合法性 |
| `backend/upgrade3d/` | Cody | Ancai、Bella | 已確認 DXF/layout | 3D 可用的牆、地板、門窗幾何 |
| `frontend3d/` | Bella | Ancai review | DXF/scene API | 次要 React/R3F 原型，不取代正式流程 |
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
  -> Yen 將問卷整理成專業室內設計語言與 RAG 查詢意圖
  -> Kai PostgreSQL / CloudFront 家具、三視角圖與 RAG metadata
  -> Ancai 幾何配置、碰撞與淨空驗證
  -> scene_json
  -> Bella FastAPI、SQLite 專案保存、正式 2D/3D UI
  -> 第 6 步鎖定單一 configuration_snapshot + 逐房牆地 surface override
  -> 第 7 步每房三個候選視角（各自綁定 room_id 並呈現全室）+ 代表房全屋色卡
  -> 第 8 步全屋初稿 + 每張房間圖最多一次修圖
  -> Bella deterministic design-delivery：逐房簡報 + 工程報告 + denylist 資安基線 + 預算
```

Graph RAG 只補強 Kai/Django 的房間、風格、家具、材質、限制關係與可追溯證據；Ancai 仍是幾何與規則的唯一裁決者。

家具向量 RAG 由 Django 維護查詢 schema、BGE-M3 與 reranker 品質，Kai 維護正式家具、metadata 與 pgvector 查詢，Bella 提供已接線的 HTTP/UI jobs adapter。Yen `RequirementSkill` 將問卷專業化為可追溯查詢意圖的模組與測試已存在，但正式 Step 5 尚未呼叫；在 adapter 完成前不得寫成已上線。RAG 不接管 Ancai 的第 6 步合法座標。

### Yen／Django-Skill 接線狀態

| 能力 | Owner 與狀態 | 正式邊界 |
|---|---|---|
| 問卷專業室內設計語言 | Yen `RequirementSkill`，待整合 | Django 提供空間證據；Bella 尚需建立 Step 5 adapter、保存輸入／輸出版本 |
| 家具 RAG jobs | Django/Kai/Bella，已實作 | 檢索、rerank 與候選證據；不產生合法座標 |
| Step 8 生圖／修圖 | Yen `GenPicAgent` + Bella adapter，已實作 | 使用 `OPENROUTER_API_KEY`，失敗不得假成功 |
| 工程與預算報告語意 | Yen `ReportAgent`，待整合 | 現行 `/design-delivery` 是 Bella deterministic builder，尚未呼叫 Report Agent |
| 最終資安工程審核 | Bella，部分實作 | 目前只有敏感欄位名稱 denylist 移除；完整 schema allowlist、權限與稽核待補 |

### 第 7、8 步現行接口

- 第 7 步視角由正式 Three.js 場景擷取，不消耗 OpenRouter 圖像額度；每個 camera manifest 綁定 `room_id` 且呈現全室。Yen 擁有視角與 prompt 語意契約，Bella 擁有 UI 與保存。
- `GET /api/ai-render/status`：只回 provider 與模型狀態，不回 token。
- `POST /api/projects/{project_id}/ai-renders`：逐房首次生圖。
- `POST /api/projects/{project_id}/ai-renders/{room_id}/edit`：後端強制每房最多一次修圖。
- `POST /api/projects/{project_id}/design-delivery`：建立 Web 簡報、工程、資安與預算成果包。
- `/render-jobs` 是舊 provider 相容接口，不是現行第 8 步主路徑。
- 現行 `/ai-renders` 以 `OPENROUTER_API_KEY` 啟用；legacy `/render-jobs` 以 `ROOMPILOT_RENDER_PROVIDER_URL` 啟用，兩條狀態不可混用。
- 現行沒有 `/api/health`；不得把 Phase 5 readiness 目標端點寫成已實作。

### Kai catalog 與家電邊界

- 2026-08-06 live runtime 讀 `roompilot.furniture_catalog_current`，提供 7,958 筆家具、7,958 個 GLB、23,874 張三視圖與 7,958 筆 current BGE-M3 向量。`furniture_catalog_api_current` 不是目前 repository 的 runtime 讀取來源；舊 8,675／8,076 批次不得當成現行 readiness。
- 每筆正式家具有 GLB 與 `front`、`side`、`angle-45` 三視角 CloudFront PNG。
- 正式 `postgres` 模式不可用時 API 回傳 503；只有明確設定 `ROOMPILOT_CATALOG_PROVIDER=json` 才使用已驗證的離線資料，離線筆數不得冒充 live PostgreSQL readiness。
- Phase 2 家具管理 API 由 Kai 擁有 SQL transaction、啟用門檻與 audit，Bella 只接入受 Bearer token 保護的 FastAPI adapter；刪除一律為 `is_active=false`。
- 現行 `backend/server/project_store.py` 實際使用 SQLite 保存 project、workflow 與 render metadata；`.env.example` 的 PostgreSQL project store 是目標設定，尚未在目前 `main.py` 接成可切換 provider。文件與 AI 不得把目標架構寫成已上線事實。
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
