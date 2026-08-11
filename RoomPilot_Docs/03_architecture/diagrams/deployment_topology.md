# 部署拓撲圖 (Deployment Topology) - RoomPilot

> **版本:** 0.1 | **更新:** 2026-08-11 | **狀態:** 草稿
> **Owner:** Bella（跨模組整合，依 `AGENTS.md` 目錄責任；本檔為 AI 衍生草稿，人工核准前為 TO-BE）
> **語域:** L3（工程；本檔為 drawio 生成規格）
> **實例:** 單例（每專案一張；多環境／future state 以分頁承載，不另開檔）
> **生成:** AI 由程式碼與文件衍生｜來源版本 git yen@8863a36c
>
> **定位**：部署與邊界溝通圖的生成規格——把 [c4_container](./c4_container.md) 的邏輯容器落到具體 Node（本機單機部署）。部署程序與環境設定歸 [../../06_ops/deployment_and_operations.md](../../06_ops/deployment_and_operations.md)；邏輯容器分工歸 c4_container。ID 沿用 [../../00-registry.md](../../00-registry.md)。

## 目錄

- [1. 圖面資訊](#1-圖面資訊)
- [2. 生成 prompt](#2-生成-prompt)
- [3. 約束與檢查](#3-約束與檢查)
- [4. 待確認](#4-待確認)
- [5. 追溯](#5-追溯)

## 1. 圖面資訊

| 欄位 | 值 |
|---|---|
| 受眾 | 團隊組員（自行架環境）、維運/展示窗口 |
| 回答的問題 | 什麼跑在同一台機器上？哪些是外部雲服務？資料落在哪裡？ |
| 正典來源 | [sad](../sad.md) §7（待產出）、[../../06_ops/deployment_and_operations.md](../../06_ops/deployment_and_operations.md) |
| 最後校驗 | 2026-08-11（對照 git yen@8863a36c） |
| 階段 | Pilot |

## 2. 生成 prompt

畫部署拓撲：**本機單機部署**，單租戶、單使用者工作站——不是雲端架構，不畫 LB／K8s／多 AZ。模板的「per-tenant／集中平台／加購模組」三分模式不適用（無多租戶證據），改為三分組：① 本機工作站、② 外部雲服務、③ 使用者瀏覽器。

### 2.1 Node 與部署單元

| 分組 | Node / 部署單元 | 屬性與數量 | 證據 |
|---|---|---|---|
| ① 本機工作站（藍） | uvicorn `backend.server.main:app` | 127.0.0.1:8002 ×1（占用時改 8023）；Python 3.12 `.venv`；`--reload` 開發模式 | `README.md:47-50,68`、事實檔 06-ops §1 |
| ① 本機工作站 | 靜態前端（同 process） | FastAPI 直接服務 `backend/server/static/`，無獨立 web server | ADR-006、`backend/server/main.py:195` |
| ① 本機工作站 | SQLite ProjectStore | 檔案型 DB（`DB_PATH` 可覆寫）；workflow JSON 單一快照 ≤2MB | `backend/server/main.py:127,460-469`、NFR-002 |
| ① 本機工作站 | runtime 目錄 | 上傳圖／渲染圖等落地檔；`ROOMPILOT_RUNTIME_DIR` 可覆寫；不進 git | `backend/server/runtime_paths.py:22`、`AGENTS.md:59` |
| ① 本機工作站 | PostgreSQL 17.10 ＋ pgvector v0.8.2 | localhost:5432、`roompilot_db` ×1；原生 Windows 安裝或 Docker（`pgvector/pgvector`）二擇一 | `scripts/sql/PostgreSQL 17.10 安裝與資料匯入指南.md:3`、`docker_postgresql/docker-compose.yml:7`、事實檔 06-ops §2 |
| ① 本機工作站 | Playwright Chromium | 第 8 步 PDF print 引擎；缺席時交付提案回 503（設計行為） | `requirements-delivery.txt:2`、事實檔 06-ops §6 |
| ① 本機工作站 | RAG 模型快取（可選） | 約 9GB，repo 外；伺服器只 lazy-load 已快取模型，BGE-M3+reranker 約 4.6GB 常駐記憶體 | `README.md:98-107`、事實檔 06-ops §7 |
| ② 外部雲服務（灰） | OpenRouter | HTTPS；LLM/VLM/生圖唯一閘道（單一 `OPENROUTER_API_KEY`） | `backend/agent/llm.py:133`、事實檔 06-ops §2 |
| ② 外部雲服務 | AWS S3/CloudFront | 家具 GLB 與三視角圖；API 以 307 redirect，瀏覽器直載 | `backend/server/main.py:4012`、`cloud_models.py:47-72` |
| ② 外部雲服務 | 遠端算圖 provider（可選） | `ROOMPILOT_RENDER_PROVIDER_URL/_TOKEN`，timeout 預設 60s；未設定時不啟用 | `backend/server/render_service.py:34-44` |
| ③ 使用者瀏覽器（青） | Three.js 八步精靈 | 與 server 同機（127.0.0.1 bind，僅本機可達）×1 | `README.md:47-50`、ADR-006 |

### 2.2 連線（只畫跨組線）

| 從 → 到 | 語意與協定 | 證據 |
|---|---|---|
| 瀏覽器 → uvicorn | HTTP 127.0.0.1:8002（頁面、REST API、上傳） | `README.md:47-50` |
| 瀏覽器 → CloudFront | HTTPS 直載 GLB／圖（經 API 307 redirect） | `main.py:4012` |
| uvicorn → PostgreSQL | TCP 5432，查 view `roompilot.furniture_catalog_current`；失敗必須可見，僅顯式設定才回退已驗證 JSON | ADR-003、NFR-003、`main.py:909-926` |
| uvicorn → OpenRouter | HTTPS，統一閘道一條線（問卷解析／場景規劃／生圖） | 事實檔 06-ops §2 |
| uvicorn → SQLite／runtime | 本機檔案 I/O（同 Node 內部線，虛線淡化） | `main.py:460-469`、`runtime_paths.py:22` |

### 2.3 註記帶（畫進圖）

- 資料隔離：單機單租戶，無 tenant 概念；秘密只在本機 `.env`（不提交，`AGENTS.md:59`），且 `.env` 檔優先於 process env（`backend/spatial_data/rag/settings.py:23-28`）。
- 幾何合法性只在 uvicorn 內的 `backend/engine/` 計算（ADR-002）——外部服務線不得標「決定擺位」。
- 無 CI/CD、無反向代理、無 TLS 終結：目前拓撲即開發機即產品展示機。

## 3. 約束與檢查

- [ ] 每個 Node 標屬性（port／數量 ×1／可選與否）；可選元件（RAG 快取、遠端算圖、OCR）以虛框標示
- [ ] 只畫 §2.2 跨組連線；同 Node 內部檔案 I/O 淡化，不畫滿
- [ ] 資料隔離註記為「單機單租戶」，不虛構 schema／tenant_id 隔離
- [ ] 不畫目標雲端拓撲；未來狀態（如 ProjectStore 遷 PostgreSQL）僅得以 `🔜` 註記，見 §4
- [ ] 圖例＋metadata banner 已附（版本 0.1、git yen@8863a36c）

## 4. 待確認

1. 正典來源 [sad](../sad.md) §7 與 [deployment_and_operations](../../06_ops/deployment_and_operations.md) 尚未產出（登錄簿 §6 已列計畫）；產出後本檔須與其對齊。
2. PostgreSQL 正式部署方式（原生 Windows 或 Docker）團隊未拍板——兩份指南並存（`scripts/sql/` 與 `docker_postgresql/`），圖上以二擇一註記。
3. 遠端算圖 provider 是否實際啟用無 `.env` 證據（預設未設定），圖上標可選虛框。
4. ProjectStore 遷移 PostgreSQL 的 Phase 3 說法僅見契約文件（登錄簿 §7 待確認項），是否入圖為 `🔜` 待 owner 決定。
5. 工作站硬體規格（RAM 需求：RAG 常駐約 4.6GB）未有正式最低配備文件。

## 5. 追溯

- 上游：[../../00-registry.md](../../00-registry.md)（ADR-002/003/006、NFR-002/003）、[c4_container](./c4_container.md)、[../sad.md](../sad.md) §7（待產出）；事實檔 06-ops（git yen@8863a36c）。
- 下游：[../../06_ops/deployment_and_operations.md](../../06_ops/deployment_and_operations.md)、[../../06_ops/runbook-catalog-db-unavailable.md](../../06_ops/runbook-catalog-db-unavailable.md)、[../../06_ops/runbook-delivery-proposal-503.md](../../06_ops/runbook-delivery-proposal-503.md)、對外展示簡報。
- 產圖：以本 §2 規格走 `VibeCoding_Workflow_Templates/03_architecture/diagrams/_tools/drawio_kit.py` 生成 `.drawio`，再以 `_tools/analyze_layout.py` 驗 cross=0, pierce=0。
