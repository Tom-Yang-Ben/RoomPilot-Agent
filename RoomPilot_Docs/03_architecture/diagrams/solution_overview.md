# 解決方案架構總覽圖 (Solution Architecture Overview) - RoomPilot

> **版本:** 0.1 | **更新:** 2026-08-11 | **狀態:** 草稿
> **Owner:** Bella（`backend/server/` 與跨模組整合，依 `AGENTS.md` 目錄責任；各 Zone 內元件 owner 見 §2.1）
> **語域:** L3（工程）
> **實例:** 單例（每專案一張；多環境／future state 以分頁承載，不另開檔）
> **生成:** AI 由程式碼與文件衍生｜來源版本 git yen@8863a36c
>
> **定位**：架構首頁「那一張圖」的生成規格——RoomPilot 端到端責任分區與資料路徑語意。C4 各層圖歸 [c4_context](./c4_context.md)／[c4_container](./c4_container.md)／[sad](../sad.md) §1；視覺規範歸 [README](./README.md)。

## 目錄

- [1. 圖面資訊](#1-圖面資訊)
- [2. 生成 prompt](#2-生成-prompt)
- [3. 約束與檢查](#3-約束與檢查)
- [4. 待確認](#4-待確認)
- [5. 追溯](#5-追溯)

## 1. 圖面資訊

| 欄位 | 值 |
|---|---|
| 受眾 | AIPE03 評審、組員 onboarding、跨 owner 協作對齊 |
| 回答的問題 | 八步工作流端到端由哪幾個責任區組成？`layout_json`／`scene_json`／catalog／渲染資料以哪幾種語意流動？ |
| 正典來源 | [sad](../sad.md)、[../../01_requirements/brd.md](../../01_requirements/brd.md)、`docs/TEAM_AI_OWNERSHIP.md`、`AGENTS.md` |
| 最後校驗 | 2026-08-11（依 yen@8863a36c 程式碼盤點） |
| 階段 | Pilot——依模板政策「Pilot 前不畫」，本檔先固定生成規格；實際出圖時機見 §4 |

## 2. 生成 prompt

畫一張由左至右的端到端參考架構，抽象層級 L1 Zone＋L2 主要元件（**只畫 L2**，不畫 class、function、endpoint、table 或 UI 頁面）。

### 2.1 L1 Zones（依「訊號流入 → 處理 → 領域真相 → 應用與外部」命名）

1. **Actors & Inbound Signals**：使用者／設計師與原始訊號——平面圖 PNG/JPG/DXF 上傳、兩點標定、問卷答案、2D/3D 拖曳操作。不承擔業務狀態。
2. **Channel & Runtime**：瀏覽器八步精靈（`backend/server/static/` 單頁 HTML/Three.js，ADR-006）＋單一 FastAPI app（`backend/server/main.py:195`，port 8002，所有 API 直掛，僅另 include `rag_router`，`main.py:197`）。
3. **Recognition & Placement Pipeline**：平面圖辨識（Cody `backend/floorplan/`，止於 `layout_json`，ADR-001）→ 空間評估（Django `backend/spatial_data/`）→ 需求結構化與選件（Yen `backend/agent/`，不輸出合法座標）→ **幾何引擎（Ancai `backend/engine/`，家具座標／碰撞／淨空唯一裁決者，ADR-002）** → `scene_json`。
4. **Domain Services & Data**：家具 catalog（Kai：PostgreSQL view `roompilot.furniture_catalog_current` 優先，`postgres_repository.py:20`；已驗證 JSON 8,675 件為顯式後援，ADR-003；quarantine 執行期不得載入）＋ ProjectStore（SQLite `.runtime/projects.sqlite3`，workflow JSON 單一快照＋revision 樂觀鎖，ADR-007）＋ pgvector RAG（僅 `/rag` 驗證頁，不接第 6 步）。
5. **Applications & External Systems**：第 8 步 AI 生圖（OpenRouter，`/api/projects/{id}/ai-renders`，`main.py:2070`）、交付 PDF（Playwright Chromium，缺件回 503，`main.py:2384`）、CloudFront GLB／三視角圖資產（`https://ddgsm1yg3xikc.cloudfront.net/...`，manifest 為準）。

底部一條 **Cross-Cutting Management Zone**：契約與 owner 分責（`docs/contracts/`、`AGENTS.md`）／公分制 `_cm`＋`coordinate_unit:"cm"`（NFR-001）／`ROOMPILOT_*` feature flags（`ROOMPILOT_CATALOG_PROVIDER`、`ROOMPILOT_AGENT_PIPELINE`、`ROOMPILOT_RAG_*`）／測試門檻（NFR-006）——橫切能力不混入業務主鏈。

### 2.2 四條語意資料路徑（線型固定，不得合併）

| 線型 | 語意 | 線上標註（RoomPilot 實例） |
|---|---|---|
| 藍色實線 | 即時互動／同步交易 | REST/JSON、multipart 上傳（瀏覽器 ↔ FastAPI；`/api/scene/validate` 拖曳落點裁決） |
| 綠色虛線 | 領域產物／內部 JSON | `layout_json` → `scene_json`（唯一模組邊界產物，ADR-001）→ 第 8 步 render payload |
| 紫色虛線 | 控制、設定、身分 | `.env` DB 連線（`DB_HOST` 等）、`ROOMPILOT_CATALOG_PROVIDER`、`ROOMPILOT_AGENT_PIPELINE`、`ROOMPILOT_RAG_ENABLED` |
| 橘色虛線 | 持久化、重播與證據 | SQLite `workflow_json`＋`render_outputs`、`.runtime/uploads|renders/`、PostgreSQL catalog、pgvector embeddings、CloudFront manifest |

### 2.3 視覺

白底、扁平化、低裝飾、無 3D icon。Zone 用淡色表頭與灰色邊界；Component 白底加語意色框。連線正交路由、保留獨立 lane。圖例同時說明四種線型、同步／非同步與 `🔜`。

## 3. 約束與檢查

- [ ] 所有外部整合通過明確 adapter／gateway：OpenRouter 生圖、Playwright PDF、CloudFront 資產、PostgreSQL repository（`backend/catalog/postgres_repository.py`），不直連內部資料
- [ ] 邊界鐵律逐條標上：辨識止於 `layout_json`（ADR-001）；幾何合法性只在 `backend/engine/`，RAG/LLM/前端不決定幾何（ADR-002）；catalog DB 失敗必須可見、不悄悄回退 JSON（ADR-003，`main.py:909-926`）；家電只進 `render_context`，不進 2D/3D 擺設（ADR-004）；`frontend3d/` 為次要原型不入圖主鏈（ADR-006）
- [ ] 未落地能力標 `🔜`：ProjectStore 之 PostgreSQL Phase 3（yen 分支實際為 SQLite，見 §4）
- [ ] 未虛構本產品不存在的能力（無 WebSocket、無訊息佇列、無多服務拆分——單一 FastAPI app，`main.py:195`）
- [ ] Zone 責任表與 L2 元件目錄表放 [sad](../sad.md)（表格、不畫成圖），圖面引用之

## 4. 待確認

1. 模板政策「企業級才畫、Pilot 前不畫」與本專案 Pilot 階段衝突：本檔僅固定生成規格，是否於 Pilot 即出圖由文件 owner 決定。
2. 登錄簿 [../../00-registry.md](../../00-registry.md) §6 輸出檔案計畫未列 `03_architecture/diagrams/` 任何檔案；本檔路徑待補登。
3. `README.md:312` 稱 project/workflow JSONB 已搬 PostgreSQL，但 yen 分支程式實際使用 SQLite ProjectStore（`main.py:147`）；圖上此元件標 `🔜` 或 SQLite，以程式碼為準前者僅列 future state 分頁。
4. 正典來源 [sad](../sad.md) 與 brd 於本批文件同輪生成，交叉引用以登錄簿 §6 檔案計畫為準，實檔落地後需回校連結。

## 5. 追溯

- 上游：[sad](../sad.md) §1–§2（系統與邊界）、ADR-001／ADR-002／ADR-003／ADR-004／ADR-006／ADR-007（[../../00-registry.md](../../00-registry.md) §3）、NFR-001／NFR-003／NFR-004／NFR-006
- 下游：簡報／架構首頁、onboarding 材料、[c4_container](./c4_container.md) 細化
- Worked example（虛構專案，few-shot 錨點）：模板庫 `VibeCoding_Workflow_Templates/03_architecture/diagrams/_examples/prompt_filled.md` → spec → `.drawio`（score=0）
