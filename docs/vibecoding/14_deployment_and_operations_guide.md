# 部署與運維指南 - RoomPilot-Agent

> 本文件由 VibeCoding 模板 14_deployment_and_operations_guide.md 導入 RoomPilot-Agent 生成 | 基準分支 bella-local-20260726 | 2026-07-26(HEAD e48cd67)

> **版本:** v1.0 | **更新:** 2026-07-26

**現況一句話:本專案目前沒有正式部署環境。** 後端以本機 uvicorn 單進程啟動,唯一常態雲端元件是 CloudFront GLB 模型交付;OpenRouter LLM 與遠端渲染供應商為選用外部服務,未設定時系統以確定性 fallback 或 503 回應,不假成功。本文件保留模板章節骨架,凡機制不存在一律照實標「現況:無」,並把可查證的本機運維事實(啟動、資料、日誌、備份)寫齊。

---

## 1. 部署架構

```
現況:Development(本機)only — 無 Staging、無 Production
```

實際執行拓撲(依 `backend/server/main.py` 與 `.env.example` 查證):

```
瀏覽器 ─ http://127.0.0.1:8002 ─→ uvicorn 單進程(backend.server.main:app,44 條路由全在 main.py)
                                    ├─ 靜態頁 /static(index/styles/library/scene 四頁 + JS)
                                    ├─ SQLite  .runtime/projects.sqlite3(WAL 模式)
                                    └─ 檔案     .runtime/uploads/、.runtime/renders/
瀏覽器 ─ GLB 模型 ──────────────→ CloudFront https://ddgsm1yg3xikc.cloudfront.net
                                    └─ S3 bucket: roompilot-furniture-glb-prod-825555019055-ap-east-2-an
選用外部服務(未設定即停用):OpenRouter API、遠端渲染供應商(ROOMPILOT_RENDER_PROVIDER_URL)
```

### 基礎設施元件

| 元件 | 用途 | 現況(2026-07-26 實測) |
| :--- | :--- | :--- |
| 負載均衡 | 流量分配與故障轉移 | **無**;單機 uvicorn,無反向代理 |
| 應用伺服器 | 核心應用託管 | uvicorn(本機 .venv 實測 0.50.0)+ FastAPI(實測 0.139.0);**無 Dockerfile、無容器化**(repo 根 find 實測) |
| 資料庫 | 資料持久化 | 執行期:SQLite `.runtime/projects.sqlite3`(WAL,`project_store.py:96`)。PostgreSQL 只有離線匯入器 `scripts/sql/import_official_catalog_to_postgres.py`,**伺服器執行期不連 Postgres** |
| 快取層 | 效能優化 | **無** Redis/Memcached;僅進程內記憶體快取(啟動時預熱家具 payload,`main.py:2102-2108`) |
| CDN | 靜態資源交付 | CloudFront `https://ddgsm1yg3xikc.cloudfront.net`,交付 9,350 件 GLB(manifest:`backend/catalog/data/manifests/glb_upload_all_result.csv`);網頁靜態資源不走 CDN,由 FastAPI `/static` 直出 |
| 監控 | 健康檢查與告警 | **無**;無 `/health` 端點(grep 實測),僅三個狀態端點,見第 5 節 |

### 開發環境需求

| 項目 | 需求 | 依據 |
| :--- | :--- | :--- |
| Python | `>=3.12`(本機 .venv 實測 3.12.10) | `pyproject.toml` `requires-python` |
| uv | 有 `uv.lock`,以 uv 管理(本機實測 uv 0.11.14) | repo 根 `uv.lock` |
| 後端相依(server extra) | fastapi>=0.115、uvicorn>=0.30、pillow>=10、ezdxf>=1.3、python-multipart>=0.0.9、httpx>=0.28 | `pyproject.toml` `[project.optional-dependencies].server` |
| 其他 extras(按需) | `vision`(numpy/opencv/ezdxf,PNG 辨識)、`ocr`(paddleocr/paddlepaddle,模型較大部署端按需)、`catalog`(selenium/psycopg2-binary 等,型錄管線與 SQL 匯入) | `pyproject.toml` |
| 測試 | pytest>=9.1.1(dev dependency group) | `pyproject.toml` `[dependency-groups]` |
| Node.js(僅 frontend3d) | vite 8.1.0 要求 node `^20.19.0 \|\| >=22.12.0`(本機實測 v24.15.0、npm 11.12.1) | `frontend3d/package-lock.json` engines 欄位 |

### 後端啟動指令(查證自 README.md「啟動方式」與 main.py)

在 repo 根目錄執行:

```bash
uv sync --extra server
uv run uvicorn backend.server.main:app --port 8002
```

Windows 已有虛擬環境:

```powershell
.venv\Scripts\python.exe -m uvicorn backend.server.main:app --port 8002
```

啟動後開啟 <http://127.0.0.1:8002>。

- **port 未寫死在程式碼**:README 慣例 8002,被占用改 8010,組員驗收範例用 8014;不給 `--port` 時 uvicorn 自身預設 8000。
- `main.py` **無 `__main__` 區塊**(grep 實測),不能 `python backend/server/main.py` 直跑,必須經 uvicorn。
- 啟動時 `@app.on_event("startup")` 預熱型錄快取;失敗只印 `[RoomPilot] catalog cache warmup skipped: ...` 到 stdout,不擋啟動(`main.py:2102-2108`)。註:`on_event` 是 FastAPI 已棄用 API,pytest collect 時有 deprecation warning。
- 模組載入時會把舊 worktree 的 legacy `.runtime` 合併進共用資料庫(`main.py:106-107` → `project_store.import_runtime`;`.runtime` 位置解析見 `runtime_paths.py:20-25`)。

### frontend3d(React Three Fiber DXF 檢視器)指令

```bash
cd frontend3d
npm install      # 現況 node_modules 不存在;安裝流程未實測
npm run dev      # vite dev server;/api 代理到 http://localhost:8002(vite.config.js)
npm run build    # vite build(未實測)
npm run preview
```

- scripts 只有 dev/build/preview 三個,無測試無 lint(`frontend3d/package.json`)。
- 後端**沒有任何 CORS middleware**(grep 全 backend/ 實測零命中);瀏覽器直連只能同源,開發時靠 vite proxy 把 `/api` 轉到 8002。若後端不是跑在 8002,需自行改 `vite.config.js`。
- 定位注意:正式 UI 是 `backend/server/static/` 由 FastAPI 直出;frontend3d 是輔助檢視器,`main.py:2073` 的 `_legacy_viewer_models` docstring 稱其為 retired R3F viewer,但對應路由(`/api/plans`、`/api/plan`、`/api/upload`、`/api/furniture`)仍存活。
- `frontend3d/README.md` 內容過時(寫 port 8000 與舊路徑),以 `vite.config.js` 與根 README 為準。

### 環境變數(全部 grep `backend/` 實測;範例檔=git 追蹤的 `.env.example`)

`.env` 載入方式:`services/cloud_models.py:23-25` 在 import 時以 python-dotenv 讀 repo 根 `.env`(override=False);`intake_service.py:22-40` 另讀 repo 根 `.env` 與 `backend/server/.env`(不覆蓋既有環境變數)。`.env` 已被 `.gitignore` 第 1 行排除。本機現況:repo 根 `.env` 存在,僅含 OPENROUTER_* 五個鍵;`backend/server/.env` 不存在。

| 變數 | 用途 | 預設值 | 讀取位置 |
| :--- | :--- | :--- | :--- |
| `ROOMPILOT_RUNTIME_DIR` | 覆寫 `.runtime` 位置 | repo 根 `/.runtime` | `runtime_paths.py:22` |
| `ROOMPILOT_MODEL_DELIVERY_MODE` | GLB 交付模式 `local`/`cloudfront` | `cloudfront` | `services/cloud_models.py:49` |
| `ROOMPILOT_CLOUDFRONT_BASE_URL` | 覆寫 CloudFront base URL | `https://ddgsm1yg3xikc.cloudfront.net` | `services/cloud_models.py:69` |
| `ROOMPILOT_GLB_MANIFEST_PATH` | 覆寫 manifest CSV 路徑 | `backend/catalog/data/manifests/glb_upload_all_result.csv` | `services/cloud_models.py:74` |
| `ROOMPILOT_EXTERNAL_GLB_ZIP_DIRS` | local 模式離線 GLB zip/資料夾(Windows 分號、macOS/Linux 冒號分隔) | 空 | `main.py:240` |
| `ROOMPILOT_RENDER_PROVIDER_URL` | 第 10 步遠端渲染服務端點 | 空(未設定回 503) | `render_service.py:42` |
| `ROOMPILOT_RENDER_PROVIDER_TOKEN` | 渲染服務 token | 空 | `render_service.py:43` |
| `ROOMPILOT_RENDER_PROVIDER_NAME` | 渲染供應商名稱 | `remote_renderer` | `render_service.py:44` |
| `ROOMPILOT_RENDER_PROVIDER_TIMEOUT_SECONDS` | 渲染請求逾時(夾在 5–180) | `60` | `render_service.py:34` |
| `OPENROUTER_API_KEY` | OpenRouter 金鑰 | 空 | `intake_service.py:52`、`scene_service.py:75,259` |
| `OPENROUTER_INTAKE_ENABLED` | `=1` 才啟用 LLM 引導式需求 intake | 未設=停用(deterministic fallback) | `intake_service.py:138,157` |
| `OPENROUTER_SCENE_PLANNING_ENABLED` | `=1` 才啟用 LLM 場景規劃 | 未設=停用 | `scene_service.py:80,87,264` |
| `OPENROUTER_MODELS` / `OPENROUTER_MODEL` | 模型輪詢清單/單一模型 | 預設 `qwen/qwen3-32b:free`(`intake_service.py` DEFAULT_MODELS) | `intake_service.py:44-47`、`scene_service.py:60-66` |
| `OPENROUTER_SITE_URL` / `OPENROUTER_APP_NAME` | OpenRouter 請求標頭 | `http://127.0.0.1:8000` / `test_furniture scene planner` | `scene_service.py:261-262` |
| `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` | **僅離線 SQL 匯入器用**,伺服器不讀 | DB_NAME 預設 `roompilot_db` | `scripts/sql/import_official_catalog_to_postgres.py` |

---

## 2. CI/CD 流水線

**現況:無任何 CI/CD。** repo 無 `.github/`、無 Dockerfile、無 docker-compose、無 Makefile(2026-07-26 ls/find 實測)。實際流程是手動的,README「合併方式」一節規定了合併前的必跑閘門:

| 階段 | 步驟(現況實際做法) |
| :--- | :--- |
| **建置** | 無編譯產物;`uv sync --extra server` 安裝依賴即完成 |
| **測試** | `uv run pytest tests/ -q`(47 個測試檔,collect 392 tests——本次僅收集實測,全量通過率未查證)+ `git diff --check` + `git status --short`(README 合併前必跑三指令) |
| **部署** | 無部署動作;各組員本機 `git pull` 後重啟 uvicorn(README「組員同步 Bella」流程,見第 3 節) |

待辦:
- [ ] 引入 CI(如 GitHub Actions)自動跑 pytest;團隊是否已有規劃(未查證)
- [ ] 8/20 發表的 demo 環境形態尚未定義(本機 demo 或雲端部署,待補)

---

## 3. 部署檢查清單

本專案「部署」= 組員本機更新到指定 commit 並重啟。以下清單改寫自 README「組員同步 Bella」與「合併方式」小節,全部項目在 README 有明文依據:

### 更新前
- [ ] `uv run pytest tests/ -q` 通過
- [ ] `git diff --check` 無殘留衝突標記、`git status --short` 乾淨
- [ ] 停止舊的 uvicorn 進程(README 明文要求,避免驗到舊程式)

### 更新中
- [ ] `git fetch origin` → `git switch <目標分支>` → `git pull --ff-only origin <目標分支>`
- [ ] `git rev-parse --short HEAD` 確認 commit 與整合者宣布的一致
- [ ] 重啟:`uv run uvicorn backend.server.main:app --port 8002`

### 更新後(煙霧測試)
- [ ] 開啟 `/scene`:頁面帶 `Cache-Control: no-store`、JS 以內容雜湊防快取(README 明文;`main.py:1452`),不需手動清快取
- [ ] `GET /api/catalog/status`:CloudFront manifest 健康度,正常應回報 9,350 件已驗證模型
- [ ] 上傳 `floor04.png` 的辨識基準:**19 面牆、5 扇門、5 扇窗、7 個房間**(README 驗收基準)
- [ ] 注意:`project_id` 對應各電腦本機 `.runtime/`,**不能**拿另一台電腦的專案網址驗證程式版本是否一致(README 明文)

---

## 4. 部署策略

| 模板策略 | 本專案現況 |
| :--- | :--- |
| Blue-Green | 不適用;單機單進程,無第二套環境 |
| Rolling | 不適用;無多實例 |
| Canary | 不適用;無流量分配 |

實際策略:**更新即停機重啟**(短暫斷線;SQLite 與上傳檔在 `.runtime/` 持久化,重啟不掉資料)。版本控制即發佈控制:

- 遠端分支(git branch -r 實測):`origin/main`(預設分支)、`origin/bella`(整合來源)、各組員分支 `ancai/ben/cody/django/kai/kai-dev/kai-dwv/yen`。
- 本文件基準工作區在本機分支 `bella-local-20260726`(HEAD e48cd67)。
- 團隊規則:不得把舊分支整支 merge 到 bella,必須從 bella 開整合分支、只挑組員責任範圍內的變更(README「合併方式」)。

---

## 5. 監控與告警

**現況:無監控系統、無告警、無 `/health` 端點**(grep `main.py` 無 health 字樣)。可當健康檢查用的現有狀態端點:

| 端點 | 回報內容 | 定義位置 |
| :--- | :--- | :--- |
| `GET /api/catalog/status` | CloudFront manifest 健康度(verified_model_count、cloudfront_base_url、manifest_ready)+ surfaces/doors/style_cards 供應者狀態 | `main.py:1933` |
| `GET /api/render-provider/status` | `{configured, provider, has_token}` 遠端渲染供應商設定狀態 | `main.py:1751` |
| `GET /api/scene/provider-status` | OpenRouter 場景規劃啟用狀態 | `main.py:2111` |

### 日誌現況

- **無日誌檔、無集中式日誌**;所有輸出走 uvicorn 的 stdout(access log + 應用訊息),終端關閉即消失。
- Python `logging` 在全 backend 只有 `backend/agent/select.py` 使用(選件丟棄警告,`select.py:138,152`);`backend/server/` 無任何 logging 設定,啟動預熱失敗用 `print`(`main.py:2108`)。
- 前端錯誤無回報機制(未查證前端 JS 是否有任何錯誤上報)。

### 關鍵指標與告警規則

現況皆無。模板的指標表(P95 延遲、錯誤率、CPU/記憶體閾值)與告警表在單機開發階段無對應設施,列為待辦:

- [ ] 若走向雲端部署(7/16 會議方向:雲端 API 單視角渲染),需先補 `/health` 端點與最小 uvicorn 日誌落檔(待補)

---

## 6. 回滾流程

### 自動回滾
現況:無。

### 手動回滾步驟(git 是唯一版本機制)

1. `git log --oneline` 找上一個穩定 commit(或 `git rev-parse --short HEAD` 記下目前版本再動)
2. `git switch --detach <穩定commit>`(或切回已知穩定分支)
3. 重啟 uvicorn
4. 跑第 3 節「更新後」煙霧測試

### 資料層注意事項

- `.runtime/` 不隨 git 回滾:程式回舊版後,SQLite 內可能有新版程式寫入的 workflow 資料。workflow 前端 schema 版本為 `WORKFLOW_SCHEMA_VERSION = 2`(`scene_workflow.js:1`);舊程式讀新資料的相容性未查證,回滾跨大版本時建議先備份 `.runtime/`。
- 專案 API 有樂觀鎖(`expected_revision`,衝突回 409 `project_revision_conflict`),回滾不會造成靜默覆寫,但會讓前端要求重新載入。

### 備份現況(本節為運維事實盤點,2026-07-26 本機實測)

| 項目 | 現況 |
| :--- | :--- |
| `.runtime/` 總量 | 約 12MB:`projects.sqlite3` 3.0MB + `-wal` 2.3MB + `-shm`;`uploads/` 160 個專案目錄;`renders/` 空 |
| 版控狀態 | `.runtime/` 被 `.gitignore` 第 12 行排除,**完全不在 git 保護範圍** |
| 自動備份 | **無任何備份腳本或排程** |
| 手動備份方法 | SQLite 為 WAL 模式,直接複製須同時帶 `projects.sqlite3` + `-wal` + `-shm` 三檔,或在伺服器停機時用 `sqlite3 .runtime/projects.sqlite3 ".backup <目的檔>"`(標準 SQLite 做法;repo 內無現成腳本) |
| 跨 worktree 合併 | 啟動時自動把舊 worktree 的 `.runtime` 合併進共用資料庫(`runtime_paths.legacy_runtime_dirs` + `project_store.import_runtime`);設計對象是**同機多 worktree**,不是跨機備援 |
| 跨電腦搬移 | 曾有「跨電腦匯入匯出專案」功能(commit 6cf188b,含 `tests/test_project_bundle.py`),但現行工作區已無該測試檔、`main.py` 也 grep 不到 bundle 端點——功能在後續合併中消失,**現況不可用**(何時移除未查 git 歷史) |
| 問卷視覺索引 | `.runtime/indexes/questionnaire_visuals.sqlite3` 為惰性建立的查詢索引(`main.py:147-161`),資料來源是版控內的 `backend/server/data/questionnaire_visual_catalog.json`,可隨時重建,**不需備份**;本機目前尚未生成 |
| 離線 GLB 備援 | IKEA zip(1,517 GLB、SHA-256 `5AFB7B19...E377A8`)是**型錄資產**的雲端故障備援(驗證指令 `uv run python scripts/verify_ikea_offline_backup.py <zip路徑>`,README),與 `.runtime` 使用者資料備份是兩回事 |

待辦:
- [ ] 建立 `.runtime/` 定期備份(哪怕只是 cron 複製到雲端硬碟);8/20 demo 前的專案資料目前是單點
- [ ] 決定回滾跨 schema 版本時的資料相容策略(待補)

---

## 7. Runbook:RoomPilot FastAPI 服務

```markdown
# 服務 Runbook: backend.server.main:app

## 服務概覽
- 用途:AI 室內風格與家具配置展示系統(FastAPI title,main.py:144);
  十步驟主流程(程式碼權威序在 static/scene_workflow.js WORKFLOW_STEPS,共 11 個內部步驟:
  project → upload → recognition → calibration(與 recognition 共用尺度面板,UI 顯示 10 顆按鈕)
  → space_confirmation → requirements → layout_2d → white_model_3d → realistic_3d
  → proposal_review → ai_render)
- 依賴服務:
  - CloudFront(GLB 模型,必要;斷線時 3D 家具載不出來,伺服器本身仍可啟動)
  - OpenRouter(選用;未設定走 deterministic fallback,mode=guided_fallback)
  - 遠端渲染供應商(選用;未設定時第 10 步回 503,UI 顯示尚未連接,不產生假結果)
- 架構圖:見本文件第 1 節拓撲

## 部署流程
- 建置與部署步驟:見本文件第 1 節(啟動指令)與第 3 節(更新清單)
- 配置需求:`.env` 參照 git 追蹤的 `.env.example`;金鑰不進版控
- 健康檢查端點:無 /health;以 GET /api/catalog/status 代用(見第 5 節)

## 監控
- 儀表板:無
- 告警:無
- 日誌位置:uvicorn stdout(無落檔)

## 故障排除(常見問題,均查證自程式碼)
- 啟動後 port 被占用 → 換 `--port`(8002 慣例,8010/8014 亦見於 README)
- 啟動印 `[RoomPilot] catalog cache warmup skipped: ...` → 型錄 JSON/manifest 載入失敗,
  檢查 backend/catalog/data/ 的 furniture_catalog_cloud_9350.json 與 manifests/ CSV
  (load_official_catalog 強制驗證 9,350 件,不符會 raise)
- GLB 端點回 410 → cloudfront 模式下 /api/furniture/{id}/model.gltf、buffer.bin、images
  固定回 410,屬設計行為;整體改本機供應須設 ROOMPILOT_MODEL_DELIVERY_MODE=local
  並先用 scripts/verify_ikea_offline_backup.py 驗證備援 zip(README 規定流程)
- POST /api/projects/{id}/render-jobs 回 503 → ROOMPILOT_RENDER_PROVIDER_URL 未設定
  或供應商連不上(main.py:1772-1776);回 502 = 供應商拒絕任務
- LLM 功能沒反應 → 需同時設 OPENROUTER_API_KEY 且 OPENROUTER_INTAKE_ENABLED=1
  (intake)/OPENROUTER_SCENE_PLANNING_ENABLED=1(場景規劃);未設定走本地 fallback
  是契約規定行為,不是故障(docs/contracts/AGENT_FRONTEND_BACKEND_CONTRACT.md)
- 換電腦後找不到專案 → project_id 綁本機 .runtime/,資料不跟 git 走(README 明文)
- 前端存檔回 409 project_revision_conflict → 樂觀鎖版本衝突,前端須以回應附帶的
  最新 project 重新套用;非資料損毀
- 軟裝加窗簾回 409 decor_model_missing → main.py:2446 引用的
  /static/models/roompilot-curtain.glb 實際不存在(find static/ 零 .glb,已知缺陷)
- pytest collect 出現 on_event deprecation warning → FastAPI 已棄用 API,已知現象

## 緊急聯絡人 / 升級流程
- 責任目錄表見 README「團隊目錄與合併規則」:backend/server 與 frontend3d 由 Bella 負責、
  backend/catalog(CloudFront/manifest)由 Kai 負責,其餘依表
- 正式升級流程:無 on-call 制度;口頭/群組聯絡(未查證是否有書面約定)
```

---

## 附:本文件的已知缺口(待補清單)

- 8/20 發表用環境的部署形態(本機 demo 或雲端)未定義(待補)
- pytest 全量通過率:本次只做 `--collect-only`(392 tests),未執行完整測試(未查證;記憶中 7/24 曾 330 過/4 敗,非本次實測)
- frontend3d `npm install` / `npm run build` 未實際執行,依賴可裝性未驗證(未查證)
- CI 導入與 `.runtime/` 備份機制:現況皆無,列於第 2、6 節待辦
