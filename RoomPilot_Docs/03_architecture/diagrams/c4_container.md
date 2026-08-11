# 容器圖 (C4 Container) - RoomPilot

> **版本:** 0.1 | **更新:** 2026-08-11 | **狀態:** 草稿
> **Owner:** Bella（`backend/server/` 主要 owner，AGENTS.md:36；跨模組連線受影響 owner 共同確認）
> **語域:** L3（工程；圖面本身供跨團隊溝通）
> **實例:** 單例（每專案一張；多環境／future state 以分頁承載，不另開檔）
> **生成:** AI 由程式碼與文件衍生｜來源版本 git yen@8863a36c
>
> **定位**：C4 L2 全景主錨圖溝通級 drawio 版的生成規格；與 [sad](../sad.md) §1.2 mermaid 二擇一，不得雙軌維護。容器內部（L3）歸 sad §1.3 mermaid；部署實體化歸 [deployment_topology](./deployment_topology.md)。

## 目錄

- [1. 圖面資訊](#1-圖面資訊)
- [2. 生成 prompt](#2-生成-prompt)
- [3. 約束與檢查](#3-約束與檢查)
- [4. 待確認](#4-待確認)
- [5. 追溯](#5-追溯)

## 1. 圖面資訊

| 欄位 | 值 |
|---|---|
| 受眾 | 跨團隊對接（Bella/Yen/Kai/AN 等 owner）、新進工程師 |
| 回答的問題 | RoomPilot 有哪些可獨立執行的 runtime？八步工作流資料怎麼在它們之間流？ |
| 正典來源 | [sad](../sad.md) §1.2 |
| 最後校驗 | 2026-08-11 |
| 階段 | Pilot（本檔為 drawio 生成規格；圖檔尚未產出） |

## 2. 生成 prompt

畫 C4 Container 全景圖：actor＋全部 runtime 單位＋主要連線。方塊**必須是 runtime**：

| 類別 | 內容 | 形狀／配色 | 證據 |
|---|---|---|---|
| Actor | 使用者（瀏覽器） | 人形 | — |
| 應用程序 | **八步 SPA**（Three.js，於瀏覽器執行；由 FastAPI 掛 `/static` 供檔） | 圓角矩形 | backend/server/main.py:216-217、scene.html |
| 應用程序 | **FastAPI 單體 :8002**（唯一 app；`main.py` 全部路由＋唯一 include 的 `rag_api` router；引擎 `backend/engine/`、catalog 讀取、RAG 服務、MasterAgent 管線皆為同進程模組，不另畫容器） | 圓角矩形 | main.py:197、README.md:49 |
| 應用程序 | **Playwright Chromium**（交付提案 PDF 渲染子進程；未安裝時 503 `delivery_engine_not_configured`） | 圓角矩形 | main.py:2384、02-api §1.6 |
| 批次工具 | **匯入腳本**（`scripts/sql/import_official_catalog_to_postgres.py`、`import_furniture_embeddings_to_postgres.py`；離線一次性） | 圓角矩形（灰） | 05-data §7 |
| 資料儲存 | **PostgreSQL**（schema `roompilot`：catalog 正表＋view `furniture_catalog_current`、pgvector `furniture_embeddings`） | 圓柱 | schema.sql:386-471、roompilot_furniture_embeddings_schema.sql:7 |
| 資料儲存 | **SQLite ProjectStore**（`runtime/projects.sqlite3`：專案、workflow 快照 ≤2MB、renders） | 圓柱 | project_store.py:78,84 |
| 資料儲存 | **本機 JSON/GLB 檔庫**（8,675 件官方 JSON＋manifest fallback、`dataset/` GLB 後援、quarantine 執行期禁載） | 圓柱 | main.py:130-140、440-453、05-data §3-4 |
| 共用服務 | **OpenRouter**（intake LLM、nano banana 生圖）、**CloudFront CDN**（GLB 307 redirect＋三視角圖） | 綠 | main.py:3331、4012、02-api §1.6 |
| 獨立子系統 | 無（`frontend3d/` 為次要原型，不入圖；AGENTS.md:58） | — | — |

主要連線（每條標協定與用途）：

| 來源 → 目的 | 協定／用途 | 線型 | 證據 |
|---|---|---|---|
| 瀏覽器 SPA → FastAPI | HTTP JSON（公分制 payload、`coordinate_unit: "cm"`）：八步主鏈 upload→analyze→confirm(layout_json)→intake/問卷→scene/generate(scene_json)→scene/layout/validate→renders→ai-renders→delivery | 主鏈粗實線 | 02-api §1.1-1.6、NFR-001 |
| FastAPI → PostgreSQL | psycopg2 pool；`/api/furniture` 讀 view（須回滿 8,675 筆才採用）；RAG pgvector 檢索 | 實線 | postgres_repository.py:20,211-245、main.py:909-926 |
| FastAPI → SQLite ProjectStore | sqlite3 檔案；revision 樂觀鎖，落後 409 | 實線 | project_store.py:28-33 |
| FastAPI → JSON/GLB 檔庫 | 檔案讀取；catalog fallback（DB 失敗必須可見）與本機 GLB 後援 | 回流虛線 | main.py:909-926 |
| FastAPI → OpenRouter | HTTPS；intake 訪談（失敗 `guided_fallback`）、第 7/8 步生圖 | 實線 | main.py:3343、2070 |
| 瀏覽器 → CloudFront | HTTPS GET；`/api/furniture/{id}/model` 307 redirect 取 GLB | 實線 | main.py:4012 |
| FastAPI → Playwright Chromium | 子進程；delivery-proposal PDF | 實線 | main.py:2384 |
| 匯入腳本 → PostgreSQL | psql/psycopg2；離線建庫與向量 UPSERT | 橫切點線 | 05-data §7 |

部署邊界分組：〔瀏覽器〕×〔單機 FastAPI＋本機儲存（SQLite、JSON/GLB）〕×〔外部共用服務（PostgreSQL、OpenRouter、CloudFront）〕。

各 Container L3 揭露狀態：FastAPI 單體 ✅（[sad](../sad.md) §1.3）；SPA、Chromium、匯入腳本＝表代圖（本檔連線表已盡述，內部無跨團隊介面）。

## 3. 約束與檢查

- [x] 無 module／package 當容器：`backend/engine/`、`backend/catalog/`、RAG、MasterAgent 均註記為 FastAPI 同進程模組（main.py 單一 app，02-api §1）
- [x] 每條跨邊界連線標協定與用途；主鏈粗實線、fallback 回流虛線、離線匯入點線
- [x] 每個 Container 標 L3 揭露狀態（見 §2 末）
- [ ] 環境間拓撲不對稱：PostgreSQL 不可用時走 JSON fallback 的本機形態已以虛線註記；雲端部署形態未定義（見 §4）
- [x] 無 future state 分頁：MasterAgent 併存管線受 `ROOMPILOT_AGENT_PIPELINE` flag 控制但已落地（main.py:3518-3531），屬當前圖，不標 `🔜`
- [ ] 圖例＋metadata banner：drawio 圖檔尚未產出，產出時依 [ai_guardrails](../../../VibeCoding_Workflow_Templates/03_architecture/diagrams/ai_guardrails.md) 附上

## 4. 待確認

1. drawio 圖檔本身尚未產出；本檔目前僅為生成規格（階段欄已註記）。
2. ProjectStore 實際為 SQLite（project_store.py:78），但契約 `docs/contracts/POSTGRESQL_PROJECT_STORE_PHASE3.md` 稱 PostgreSQL Phase 3 runtime path 存在、缺 migration 腳本——正式拓撲以何者為準待 owner 拍板（同 [../../00-registry.md](../../00-registry.md) §7 待確認）。
3. 服務埠 8002 取自 README.md:49 的開發啟動指令；正式部署埠與 host 未定義。
4. 雲端／多環境部署拓撲無 repo 證據，環境不對稱檢查項暫留空。
5. 本檔不在 [../../00-registry.md](../../00-registry.md) §6 輸出檔案計畫清單內，登錄簿是否補列待維護者確認。

## 5. 追溯

- 上游：[sad](../sad.md) §1.2（Container 清單正典）、[ADR-003](../adr/ADR-003-catalog-postgres-first-json-fallback.md)（catalog 讀取邊界）、[ADR-005](../adr/ADR-005-agent-pipeline-parallel-flag.md)（併存管線不另立容器）、[ADR-006](../adr/ADR-006-static-frontend-as-production.md)（正式前端＝static SPA）、[ADR-007](../adr/ADR-007-workflow-json-single-snapshot-store.md)（ProjectStore 邊界）
- 下游：[deployment_topology](./deployment_topology.md)、[sad](../sad.md) §1.3 各 L3 圖
- 關聯 ID：NFR-001（公分制連線標註）、NFR-003（PostgreSQL 優先／可見失敗）、NFR-004（幾何合法性僅在 FastAPI 進程內 `backend/engine/`）
