# 安全與生產準備檢查清單 - RoomPilot-Agent

> 本文件由 VibeCoding v5.0 模板 05_qa/security_and_readiness.md 導入 RoomPilot-Agent | 基準：分支 django-skill、commit a2179f7e、日期 2026-08-04

> **版本:** v1.0 | **更新:** 2026-08-04 | **審查人員:** 待補（本檔為程式碼實查產出，尚未經人工安全審查）

**系統定位（影響判讀基準）:** RoomPilot-Agent 是本機啟動的 FastAPI 單體（`uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload`，README.md:30、README.md:46；8002 被占用改 8023，README.md:35），無使用者帳號系統、未對外部署。全站 HTTP 路由 **63 條**（main.py 46 ＋ rag_api.py 5 ＋ catalog_admin.py 4 ＋ engineering/api.py 8；數法見 scratchpad vibemap/server-api.md，逐條 grep 核對）。以下每項按現狀程式碼實查打勾/打叉；❌ 不代表現階段展示不能用，代表**對外部署前必須處理**。

**標記說明:** `[x]` 通過（附證據）／ `[ ]` ❌ 不通過（附風險與建議）／ `[ ]` ⚠️ 部分成立或條件性通過。

**與 2026-07-26 舊導入版（docs/vibecoding/13_security_and_readiness_checklists.md）的重大差異（本次逐項重查確認）:**

| 舊版事實 | 現行事實（2026-08-04 實查） |
| :--- | :--- |
| 44 條路由、全部無認證 | 63 條路由；catalog admin 4 條已有 Bearer token 驗證（catalog_admin.py:170-195），其餘 59 條仍無認證 |
| 三個上傳端點無大小上限 | 已全數補上 20MB 上限（`_read_upload`，main.py:1025；呼叫點 main.py:2115、3579、3615） |
| DXF 只驗副檔名即放行 | 已補內容驗證：二進位 DXF 拒收＋前 64KB 找 SECTION 結構（main.py:1952-1981） |
| three.js 從 unpkg CDN 載入、無 SRI | 已 vendored 進 `/static/vendor/three/`（grep unpkg/cdn 於 static/*.html 零命中） |
| 無 `/health` 端點 | 已有 `GET /api/health`（main.py:2533）與 `GET /api/v1/engineering/health`（engineering/api.py:77） |
| 無任何 middleware | 已有 GZipMiddleware（main.py:215）；仍無 CORS／安全標頭／限流 middleware |
| `ROOMPILOT_CATALOG_ADMIN_TOKEN` 宣告未強制（R7） | 已強制：`Depends(_admin_principal)` 以 `secrets.compare_digest` 常數時間比對（catalog_admin.py:186-195） |

---

## 資安基線 R1–R8（來源：`.claude/skills/roompilot-security/SKILL.md` 已知風險基線，逐項對現行工作樹重查）

| # | 風險 | 基線位置（skill 記載） | 現行實查（2026-08-04） | 現況判定 |
| :-- | :--- | :--- | :--- | :--- |
| R1 | 全端點無認證/授權，任何人可讀寫任一 `project_id`（IDOR）；OWASP A01/A07、CRITICAL | main.py 所有 `/api/projects/*` | 59/63 條路由仍無認證（含全部 `/api/projects/*`、`/api/v1/*` 工程文件、`/api/rag/*`）；僅 catalog admin 4 條有 Bearer token | **未處理（範圍縮小）** |
| R2 | SSRF/LFI：`_remote_glb_response` 用 `urllib.urlopen(model_url)` 無 scheme allowlist；HIGH | main.py:1019-1036（已漂移） | 現位於 main.py:1276-1293；URL 來源 `_remote_glb_url`（main.py:303-308）經 `_is_remote_glb_url`（main.py:293-300）過濾——只接受 `https://`/`http://` 開頭且帶 glb 路徑樣式，`file://` 已被擋；但 `http://` 明文與內網主機仍可通過，且 URL 取自型錄資料欄位（admin API 可寫入） | **部分緩解**（LFI 已擋；http 明文與內網目標未擋） |
| R3 | DB 明文連線：`DB_SSLMODE` 預設 `"disable"`；HIGH | postgres_catalog.py:96（已漂移） | 預設 `"disable"` 現存在三處：backend/catalog/postgres_repository.py:217、backend/server/postgres_project_store.py:64、scripts/runtime_catalog/import_runtime_catalogs_to_postgres.py:234；`.env.example` 亦以 `DB_SSLMODE=disable` 為範本（tests/test_env_example_contract.py:33 斷言） | **未處理**；且 audit.sh 的 A05 檢查回 PASS 與實況不符（腳本掃描目標未跟上檔案搬移，見下方 audit 實跑） |
| R4 | 無 rate limiting / CORS 政策；MEDIUM | main.py:168 | 全 backend 無 CORS／限流 middleware（`add_middleware` 僅 GZip 一處命中，main.py:215）；唯一局部防護是 RAG 非同步 job 併發上限 `RAG_JOB_MAX_ACTIVE = 1`，超過回 429（rag_api.py:30、163-165） | **未處理（局部改善）** |
| R5 | 例外文字回傳 client：`detail=f"...{exc}"`；MEDIUM | main.py:1031 等 | 仍存在：main.py:1288 `detail=f"遠端 GLB 讀取失敗：{exc}"`、main.py:3569／3583 `HTTPException(422, f"parse failed: {e}")`、main.py:3632／3655／3667 `HTTPException(422, str(exc))` | **未處理** |
| R6 | `/docs`、`/openapi.json` 預設公開；MEDIUM | main.py:168 | `FastAPI(title=...)` 未設 `docs_url=None`/`openapi_url=None`（main.py:214），預設仍公開 | **未處理** |
| R7 | `ROOMPILOT_CATALOG_ADMIN_TOKEN` 宣告於 .env.example 但未強制；MEDIUM | .env.example | 已強制：token 由 postgres_admin_repository.py:67-69 讀取，`_admin_principal`（catalog_admin.py:170-195）未設 token 回 503 `catalog_admin_not_configured`、非 strict postgres 模式回 503、比對用 `secrets.compare_digest` | **已處理** |
| R8 | f-string SQL 型態（hardcoded view，安全但易被複製）；LOW | postgres_catalog.py:215 | audit.sh A03 掃描 PASS（無新增動態 f-string SQL）；backend/server/postgres_catalog.py 現僅 33 行轉接層 | **維持安全，續監控** |

> 基線表自身的行號已多處漂移（R2/R3/R6 位置、「49 條路由」對現行 63 條）；SKILL.md 明言「行號可能位移，以實際程式碼為準並更新本表」——建議把本次實查結果回寫 skill 基線（見 F 行動項 7）。

### audit.sh 實跑證據（2026-08-04，`bash .claude/skills/roompilot-security/audit.sh`）

- 結果：**FAIL=1、WARN=2**，其餘 PASS。
- FAIL（A08 危險呼叫零基線）：`subprocess.run` 出現於 backend/server/engineering/documents.py:156-166——工程文件 XLSX 由 Node adapter 產生，執行檔取自 `ROOMPILOT_ARTIFACT_NODE` 或 `shutil.which("node")`（documents.py:142-144），固定引數清單、非 shell、有 timeout（`ROOMPILOT_XLSX_TIMEOUT_SECONDS` 預設 90，documents.py:164）。屬「可人工核可」的合理用法，但基線要求任何命中須核可並記錄——目前未見核可紀錄（未查證：是否曾在 PR 說明中核可）。
- WARN 1（A10 外部抓取）：intake_service.py:143、render_service.py:141、render_providers.py:279、main.py:1285 四處，對照 R2。
- WARN 2（A09 錯誤洩漏）：main.py:1288，對照 R5。
- **腳本本身的缺口**：A05 回「PASS：DB_SSLMODE 未預設為 disable」與實查不符——`sslmode` 預設 `"disable"` 已搬到 backend/catalog/postgres_repository.py:217 等三處（見 R3），audit.sh 掃描目標未跟上搬移，需更新腳本。

---

## A. 核心安全原則

- [ ] ❌ **最小權限**: 63 條路由中 59 條無任何認證授權；僅 `/api/admin/furniture` 4 條（POST/GET/PATCH/DELETE，catalog_admin.py:234-299）經 `Depends(_admin_principal)` Bearer token 驗證。風險：任何能連上該 port 的人可建立/讀取/覆寫所有專案資料、觸發工程文件產生與 LLM 呼叫。建議：對外部署前比照 `_admin_principal` 模式加最小認證層；本機展示確保 uvicorn 綁 127.0.0.1（README 啟動指令已明寫 `--host 127.0.0.1`）。
- [ ] ⚠️ **縱深防禦**: middleware 僅 GZipMiddleware（main.py:215），無限流、無安全標頭、無 WAF；主要防線是各端點的參數驗證（普遍紮實，見 C 節）＋兩個 503 例外處理器（`ProjectStoreUnavailable` 附 Retry-After、`RuntimeCatalogUnavailable`，main.py:226-266）。單一驗證疏漏仍直達資料層。
- [ ] ⚠️ **預設安全**: 部分成立——家具交付預設 `cloudfront` 模式（`ROOMPILOT_MODEL_DELIVERY_MODE` 預設 `"cloudfront"`，services/cloud_models.py:47）且 delivery URL 經 `_https_url()` 強制 https（cloud_models.py:55-60）；遠端渲染未設定回 503 不產生假結果（render_service.py:126-128）；工程文件 `ROOMPILOT_DEMO_MODE` 預設 False（engineering/api.py:58）；LLM 兩開關預設關閉（`OPENROUTER_INTAKE_ENABLED`、`OPENROUTER_SCENE_PLANNING_ENABLED`，intake_service.py:157、scene_service.py:82）。但伺服器本身「預設無認證」。
- [ ] ⚠️ **攻擊面最小化**: `/docs`、`/openapi.json` 預設公開（R6）；舊版 R3F 路由仍存活（`GET /api/plans` main.py:3551、`GET /api/plan` main.py:3556、`POST /api/upload` main.py:3572），但 `/api/upload` 已補 20MB 上限，殘餘風險降低；`/api/plan` 有 `Path(name).name` basename 防跳脫與 Query `gt/le` 邊界（main.py:3556 起）。建議：frontend3d 去留裁決後淘汰舊路由。

## B. 資料安全與隱私

### 資料分類與收集
- [ ] ❌ 資料未依敏感性分類——repo 內無資料分類文件。上傳平面圖與問卷內容（居住格局、家庭成員）實質是個資，未被當 PII 對待。
- [x] 只收集業務必要資料：API payload 均為流程必要欄位；靜態頁無第三方 analytics，three.js 已 vendored、無外部 CDN 請求（grep unpkg/cdn 於 backend/server/static/*.html 零命中）。
- [ ] ⚠️ PII 同意機制：頁面無同意文案；但送外部渲染前有實質防護——`PRIVATE_KEYS`（render_service.py:12）定義 name/phone/email 等私人鍵，`_strip_private_fields`（render_service.py:52-60）遞迴剝除後才送供應商（render_service.py:120 套用於 requirements）。

### 傳輸安全
- [ ] ❌ 本機服務為純 HTTP：uvicorn 啟動無 TLS（README.md:30、46；repo 無 ssl_certfile/ssl_keyfile 設定，grep 零命中）。內網展示可接受；對外部署走反向代理終結 TLS。
- [x] 對外 LLM 呼叫皆 HTTPS 硬編碼：OpenRouter `https://openrouter.ai/api/v1/chat/completions`（intake_service.py:141）；CloudFront base `https://ddgsm1yg3xikc.cloudfront.net`（cloud_models.py:32）且 `_https_url()` 只採 https。
- [ ] ⚠️ 兩個例外：(1) 遠端渲染供應商 URL 直接取自 `ROOMPILOT_RENDER_PROVIDER_URL`，無 https scheme 強制（render_service.py:126）——誤填 http 時 Bearer token 明文外送；(2) 遠端 GLB 抓取允許 `http://`（main.py:294-295，R2）。建議：兩處都加 https-only 檢查。
- [ ] ❌ DB 連線預設不加密：`DB_SSLMODE` 預設 `"disable"`（R3，三處位置見基線表）。本機 localhost PostgreSQL 可接受；跨主機連線前必須改 `require` 以上。

### 儲存安全
- [ ] ❌ 敏感資料未加密儲存：專案資料存 SQLite `.runtime/`（或 PostgreSQL 專案保存 Phase 3，postgres_project_store.py），上傳平面圖/渲染 PNG 明文存檔。展示階段可接受。
- [ ] ⚠️ 金鑰管理：secrets 全在本機 `.env`，無 KMS/Vault；`.env` 在 .gitignore:2。團隊 `.env` 分發與輪替方式未定義。
- [ ] ❌ 備份保護：`.runtime/` 無備份機制（不進版控也無其他備份）。

### 資料生命週期
- [x] 日誌不記錄敏感資訊：backend/server 完全未使用 logging 模組（`grep "^import logging"` 零命中）；金鑰只進 Authorization header（intake_service.py:141、render_service.py:136-138、scene_service.py:122、render_providers.py:327），無列印金鑰之處。
- [ ] ❌ 無資料保留期限定義、無過期銷毀機制。工程文件產物存 `.runtime/engineering`（engineering/api.py 之 DocumentService generated_dir），同樣無限期留存。

## C. 應用程式安全

### 認證
- [ ] ⚠️ **系統性認證仍缺，但已有第一個受保護面**：catalog admin 寫入 API 的 `_admin_principal`（catalog_admin.py:170-195）是全 repo 唯一認證實作——Bearer token、`secrets.compare_digest` 常數時間比對、未配置回 503、認證失敗回 401（含 WWW-Authenticate）。其餘 59 條路由無帳號/密碼/session，密碼 hash/Session token/暴力破解防護不適用。唯一存取控制是 `project_id = uuid4().hex`（project_store.py:187）：不可列舉，但知道 ID 即可完全讀寫。
- 建議：對外部署時以 `_admin_principal` 為範式推廣到專案端點（skill `references/remediation.md` 有 `require_project_access` 範式）。

### 授權
- [ ] ❌ 物件級授權不存在：任何請求者持 project_id 即可讀寫該專案（IDOR，R1）——「無認證」的直接推論。
- [ ] ⚠️ 功能級授權：僅 catalog admin 寫入有 token 門檻＋strict postgres 模式閘（`catalog_admin_writes_enabled`，postgres_admin_repository.py:72）；其餘路由權限一律相同。

### 輸入驗證與輸出編碼
- [x] 防注入：SQLite 全參數化——project_store.py 28 處 `execute()` 皆佔位參數（grep 實測）；PostgreSQL 端 audit.sh A03 PASS（無動態 f-string SQL，hardcoded view）；catalog admin 輸入用 Pydantic `extra="forbid"` 嚴格模型＋regex pattern（catalog_admin.py:34-76，item_id/style_code 皆有字元白名單）。
- [ ] ❌ 防 XSS：無 CSP——middleware 無 CSP header、6 個靜態 HTML 無 CSP meta（grep `Content-Security-Policy` 全零命中）；`innerHTML` 實測 scene_v2.js 80 處、library.js 19 處、engineering.js 3 處、rag.js 0 處（`grep -c` 2026-08-04），使用者輸入是否流入這些寫入點未逐一稽核（未查證）。建議：抽查 scene_v2.js 對專案名/問卷字串的渲染路徑，補 CSP meta。
- [ ] ⚠️ 防 CSRF：無 CSRF token；但系統無 cookie session，不存在借用登入態的古典 CSRF——問題被「無認證」吸收。加認證時必須同時補 CSRF 防護。

### 上傳檔案驗證（逐端點實查，2026-08-04）

| 端點 | 副檔名白名單 | 內容驗證 | 大小上限 | 判定 |
| :--- | :---: | :--- | :---: | :---: |
| `POST /api/projects/{id}/floorplan`（main.py:2097） | ✅ FLOORPLAN_EXTENSIONS | ✅ `_validate_floorplan_bytes`（main.py:1952）：空檔拒收；DXF 拒二進位 sentinel＋前 64KB 驗 SECTION 結構；影像 PIL `Image.verify` | ✅ 20MB（main.py:180、2115） | ✅ |
| `POST /api/projects/{id}/renders`（main.py:2164） | （只收 PNG） | ✅ PNG magic bytes＋PIL verify | ✅ 20MB `read(MAX+1)`（main.py:2185-2186） | ✅ |
| `POST /api/upload`（舊版 R3F，main.py:3572） | ❌ 無 | ⚠️ ezdxf 解析失敗回 422（且 detail 帶原始例外文字，R5） | ✅ 20MB（main.py:3579） | ⚠️ |
| `POST /api/floorplan/analyze`（main.py:3602） | ✅ `.png/.jpg/.jpeg`（main.py:3612） | ⚠️ 交下游分析管線，無前置 PIL 驗證 | ✅ 20MB（main.py:3615） | ⚠️ |
| `PUT /api/projects/{id}/workflow`（main.py:2046） | （JSON） | ✅ 步驟名/型別白名單驗證 | ✅ 2MB（project_store.py:13、245） | ✅ |
| `GET /api/v1/documents/{id}/download`（engineering/api.py:294） | （讀伺服器產物） | ✅ 僅允許 `.runtime/engineering` 之下實檔：`path.is_relative_to(root)`（api.py:296-303） | — | ✅ |

- [x] 舊版三個無上限端點已全數補 20MB 上限（`_read_upload` 用 `read(limit+1)` 模式避免整檔先進記憶體，main.py:1025-1036）——舊導入版行動項 1 已完成。
- [ ] ⚠️ 檔名安全：floorplan 以 `Path(file.filename).name` 取 basename（main.py:2104），實際存檔名由伺服器決定。

### API 安全
- [ ] ❌ 端點認證授權：59/63 無認證（R1）。
- [ ] ❌ 速率限制：無全域限流；唯一防護是 RAG job 併發上限 1、超過回 429 `rag_job_capacity_reached`（rag_api.py:30、163-165）。LLM 端點（`/api/agent/intake/*`、`/api/scene/generate`）與工程文件產生（`POST /api/v1/projects/{id}/engineering-packages`，202 背景 job）可被刷量。
- [x] 參數白名單驗證普遍紮實：副檔名白名單、workflow 步驟集合驗證、render mode 白名單、catalog admin Pydantic strict 模型、engineering 端 snapshot path/payload 一致性驗證（422 PATH_PAYLOAD_MISMATCH）與鎖定狀態閘（409 REVISION_NOT_LOCKED、`approval_status == "designer_confirmed"` 才可產包，engineering/api.py:180-198）。
- [ ] ⚠️ 回應最小化：大致可以；`GET /api/v1/engineering/health` 回報 provider/demo_mode/knowledge counts/xlsx adapter 等內部組態（engineering/api.py:77-104），無認證下屬資訊揭露，加認證後重新評估。

### 依賴安全
- [ ] ❌ 無常態漏洞掃描：repo 無 `.github/`（ls 實測不存在）、無 CI、無 Dependabot/Snyk。本次未重跑 pip-audit/npm audit（未查證：現行依賴的已知漏洞狀態；舊版 2026-07-26 快照——pip-audit 0 漏洞、npm 1 high postcss——已過期不可沿用）。
- [x] 版本鎖定：requirements.txt 為 team baseline，5 組 owner 分組共 21 個 `==` pin（fastapi==0.140.0、uvicorn==0.51.0、pillow==12.3.0、psycopg2-binary==2.9.12 等；scratchpad vibemap/team-git-skills.md 逐行實數）。
- [x] 前端供應鏈：three.js 已 vendored 進 `/static/vendor/three/`（含 GLTFLoader/DRACOLoader；draco decoder wasm 另置於同層的 `/static/vendor/draco/`，共 24 個檔案），靜態頁無外部 CDN 依賴——舊導入版行動項 2 已完成。

### LLM 與 Prompt 邊界（RoomPilot 特有，對應 skill 信任邊界⑤）
- [x] LLM 選件結果經伺服器端白名單重驗：`/api/agent/furniture/select` 的 furniture_id 必在候選集（main.py:2948 起；backend/agent/select.py 明言 LLM 不得捏造家具或輸出座標）。
- [x] 幾何合法性只由 `backend/engine/` 判定（AGENTS.md 鐵律），LLM 輸出不直接成為座標。
- [ ] ⚠️ RAG 檢索句、問卷自由文字送 LLM parser（openai_parser/anthropic_parser）之前無注入清理；LLM 回應以 Pydantic Structured Outputs 約束（backend/spatial_data/rag/models.py），結構面有防護、語意面未稽核（未查證）。

## D. 基礎設施安全

- [ ] ⚠️ 防火牆/安全組：不適用（未部署雲端）；本機控制是 `--host 127.0.0.1`（README.md:30、46 已明寫，較舊版改善——舊版未指定 host）。
- [ ] ❌ DDoS 防護：無，同速率限制項。
- [x] **Secrets 不硬編碼**（逐條實查）:
  - `.env` 在 .gitignore:2；audit.sh「秘密外洩防線」PASS（.env 未被追蹤/暫存）、「A02 硬編碼秘密」PASS。
  - `.env.example` 金鑰欄位空值：`OPENROUTER_API_KEY=""`、`DB_PASSWORD=""`（tests/test_env_example_contract.py:23、32 斷言；.env.example 本體因本機權限設定無法直接讀取，以契約測試為證據）。
  - catalog admin token 由環境變數 `ROOMPILOT_CATALOG_ADMIN_TOKEN` 讀取（postgres_admin_repository.py:67-69），無預設值。
  - PostgreSQL 憑證全走 `DB_*` 環境變數（.env.example 範本經 test_env_example_contract.py 斷言；匯入器同）。
- [ ] ⚠️ 資訊揭露（低風險）：manifest CSV 揭露 S3 bucket 名（內含 AWS 帳號 ID）——沿自舊版的已知項，本次未重查 bucket 端設定（未查證：S3 僅允許 CloudFront OAC 讀取是否已實測，需向 Kai 確認）。
- [ ] ⚠️ 非 root/容器：不適用（無容器化）。
- [ ] ❌ 安全事件日誌與告警：無——backend/server 未使用 logging 模組，僅 uvicorn 預設 access log。
- [ ] ⚠️ 工程文件 XLSX 走 `subprocess.run` 呼叫 Node（documents.py:156-166）：固定引數、非 shell、有 timeout，但打破 repo「零 subprocess」基線（audit.sh FAIL 項），且 `ROOMPILOT_ARTIFACT_NODE` 可指向任意執行檔——該環境變數本身成為敏感設定。建議：於 skill 基線正式核可此例外並記錄約束（僅信任本機 env）。

## E. 合規性

- [ ] ❌ 未識別適用法規：repo 內無合規文件；台灣情境下平面圖＋問卷屬個資法適用資料。展示會蒐集他人資料前口頭告知用途即可，商用化才需正式處理。
- [ ] ⚠️ 已落實的合規相關設計：對外送渲染前剝除私人欄位（render_service.py PRIVATE_KEYS，本次實查仍在）；機電需求免責輸出（backend/floorplan/vision/requirements.py，未查證：本次未重讀該檔內容，沿自舊版事實）。

## F. 審查結論

| # | 行動項 | 對應風險 | 負責 owner（依 docs/TEAM_AI_OWNERSHIP.md） | 狀態 |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `_remote_glb_response` 與 render provider URL 補 https-only＋內網位址阻擋 | R2 | Bella（backend/server/） | 待辦 |
| 2 | `DB_SSLMODE` 跨主機連線改 `require` 以上；與 Kai 確認三處預設 | R3 | Kai＋Bella | 待辦 |
| 3 | 更新 audit.sh 的 A05 掃描目標（postgres_catalog.py → postgres_repository.py/postgres_project_store.py），消除誤判 PASS | R3 稽核缺口 | skill 維護者（django-skill 分支） | 待辦 |
| 4 | 清理 R5 例外文字回傳（main.py:1288、3569／3583、3632／3655／3667），client 給 generic 訊息 | R5 | Bella | 待辦 |
| 5 | 對外部署前置項：認證層（以 `_admin_principal` 為範式）、TLS（反向代理）、全域限流、關閉 /docs | R1/R4/R6 | Bella；僅商用化需要 | 待辦 |
| 6 | 重跑 pip-audit＋npm audit（舊快照已過期），並評估納入一支 CI workflow | 依賴安全 | 待指派 | 待辦 |
| 7 | 把本次實查結果回寫 `.claude/skills/roompilot-security/SKILL.md` 基線（R7 已處理、R2 部分緩解、行號與 63 條路由數更新）、核可 documents.py subprocess 例外 | 基線漂移 | skill 維護者 | 待辦 |
| 8 | 抽查 scene_v2.js（innerHTML 80 處）使用者字串渲染路徑，補 CSP meta | XSS | Bella | 待辦（沿自舊版未完成項） |
| 9 | 向 Kai 確認 S3 bucket 僅允許 CloudFront OAC 讀取 | 資訊揭露 | 跨組協調 | 待辦（沿自舊版未完成項） |

**整體評估:** 以「本機/內網展示」用途，現狀可執行——secrets 管理與注入防護紮實，上傳驗證與供應鏈較 7/26 舊版明顯改善（大小上限、DXF 內容驗證、three vendored、admin token、健康端點皆已補上）。**不可以現狀直接對外公開部署**：行動項 5 全數為前置條件；R1（59 條無認證）與 R3（DB 明文預設）是最高優先缺口。

---

## G. 生產準備就緒

### 可觀測性
- [ ] ❌ 監控儀表板／SLI 定義／結構化日誌／全鏈路追蹤／告警：五項皆無（backend/server 無 logging 模組、pyproject 無追蹤依賴）。對課堂發表非必要；列出供商用化評估。

### 可靠性
- [x] 健康檢查端點已補：`GET /api/health`（main.py:2533-2545，回報 catalog provider、project store provider 與 formal/ready 判定）＋`GET /api/v1/engineering/health`（engineering/api.py:77，回報 snapshot provider、demo_mode、knowledge counts、xlsx adapter）＋`GET /api/rag/status`（rag_api.py:141）＋`GET /api/catalog/status`（main.py:2528）——舊導入版「無 /health」已解。
- [ ] ⚠️ 優雅停機：SIGTERM 交由 uvicorn 框架預設處理；應用層已有自訂 `@app.on_event("shutdown")`（`close_catalog_connections`，main.py:2831-2834：關閉型錄連線池與 `PROJECT_STORE`）與 `@app.on_event("startup")`（`warm_catalog_cache`，main.py:2821-2828：JSON 型錄模式下預熱快取）。缺口是無進行中請求的排空（drain）與背景 job（RAG／工程文件）的收尾機制。
- [x] 外部呼叫有超時：OpenRouter intake 8 秒（intake_service.py:143）、scene 8 秒（scene_service.py:319）、遠端 GLB 20 秒（main.py:1285）、遠端渲染 httpx 由 `_render_timeout_seconds()` 決定（render_service.py:140）、XLSX subprocess 預設 90 秒（documents.py:164）。失敗降級：OpenRouter 失敗走本地規則、渲染失敗回 502/503 不假成功、`ProjectStoreUnavailable` 503 附 Retry-After:2（main.py:226-243）。
- [ ] ❌ 故障轉移：單機單進程，無。
- [ ] ❌ 備份恢復演練：`.runtime/` 無備份機制。

### 效能與擴展
- [ ] ❌ 負載測試／容量規劃：未做（repo 無負載測試腳本）。
- [ ] ⚠️ 無狀態化：否——SQLite＋本機檔案系統綁定單機；但 PostgreSQL 五階段（Phase 3 專案保存 postgres_project_store.py、Phase 4 runtime catalog、Phase 1/2/5 型錄，docs/contracts/POSTGRESQL_*.md ＋ scripts/sql/、scripts/project_store/、scripts/runtime_catalog/）已把資料層外移到 PostgreSQL 的路徑鋪好，為未來水平擴展的前置工程。

### 可維護性
- [ ] ⚠️ Runbook：README 有安裝/啟動/驗收步驟；無故障排除 runbook。
- [ ] ❌ CI/CD：無——`.github/` 不存在；tests/ 有 99 支 test_*.py＋3 支前端 .test.mjs（scratchpad vibemap/data-contracts-tests.md 實數），全靠本機手動執行。2026-08-04 實跑 `pytest -q tests` = 811 passed / 1 failed / 9 skipped（共 821；紅燈為 cache-busting 雜湊守約），repo 根 `pytest -q` = 916 passed / 3 failed / 9 skipped。另有 audit.sh 可作 commit 前靜態關卡（本次實跑 FAIL=1/WARN=2，見基線節）。
- [x] 配置集中管理：環境變數統一 `ROOMPILOT_` 前綴（LLM 為 `OPENROUTER_`、DB 為 `DB_`），`.env.example` 為範本並由 tests/test_env_example_contract.py 契約測試守護預設值。
- [x] Feature Flag（env 開關）：`OPENROUTER_INTAKE_ENABLED`（intake_service.py:157）、`OPENROUTER_SCENE_PLANNING_ENABLED`（scene_service.py:82、336）、`ROOMPILOT_MODEL_DELIVERY_MODE` 預設 cloudfront（cloud_models.py:47）、`ROOMPILOT_DEMO_MODE` 預設關（engineering/api.py:58）、`ROOMPILOT_ARTIFACT_NODE`／`ROOMPILOT_XLSX_TIMEOUT_SECONDS`（documents.py:142、164）。

---

## 新增子系統安全狀態摘要（舊導入版未涵蓋）

| 子系統 | 進入點 | 已有防護 | 缺口 |
| :--- | :--- | :--- | :--- |
| 工程文件 MVP（backend/server/engineering/，契約 docs/contracts/ENGINEERING_DOCUMENT_MVP.md） | `/api/v1/*` 8 條（snapshot→lock→packages→jobs→documents） | 下載限 `.runtime/engineering` 目錄內（is_relative_to）、path/payload 一致性 422、鎖定閘 409、subprocess 固定引數＋timeout | 無認證；health 揭露內部組態；subprocess 例外未正式核可 |
| 家具 RAG runtime（backend/spatial_data/rag/ 經 rag_api.py） | `/rag`、`/api/rag/*` 5 條 | job 併發上限 1（429）、Pydantic Structured Outputs 約束 LLM 回應、typed errors 不洩堆疊 | 無認證；檢索句送 LLM 前無注入清理 |
| PostgreSQL 五階段（backend/catalog/、scripts/sql/ 等） | catalog admin 4 條＋各 repository | admin Bearer token（constant-time）、strict postgres 閘、Pydantic strict 輸入、參數化 SQL、樂觀併發＋audit record（postgres_admin_repository.py） | `DB_SSLMODE` 預設 disable（R3） |
| 新 server 檔（cost_estimation.py、render_providers.py、questionnaire_visuals.py、style_cards.py） | `/api/cost/estimate`、渲染 provider、`/api/questionnaire/*` | questionnaire 圖片以 image_id 查 SQLite（非路徑拼接）；render_providers 走 https OpenRouter | 無認證（同全站） |
| 專案 skills（.claude/skills/roompilot-*） | 非 runtime 攻擊面 | roompilot-security 提供 R1–R8 基線＋audit.sh；proposal/budget 以 verify 腳本擋編造數字 | 基線行號/路由數已漂移，需回寫（行動項 7） |

## 交叉引用

- API 路由全表與行號：scratchpad vibemap/server-api.md（63 條數法）
- 遠端渲染隱私剝除契約：`docs/contracts/REMOTE_RENDER_CONTRACT.md`
- CloudFront 信任邊界：`docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md`
- 工程文件 MVP 契約：`docs/contracts/ENGINEERING_DOCUMENT_MVP.md`
- PostgreSQL 五階段契約：`docs/contracts/POSTGRESQL_*.md`
- 風險基線與修補範式：`.claude/skills/roompilot-security/SKILL.md`、`references/remediation.md`
- 舊導入版（事實已過期，僅供結構參考）：`docs/vibecoding/13_security_and_readiness_checklists.md`
- 模板指向的 `software_development_documentation_guide_zh_tw.docx` 與 `docs/document-system/`：本次實查兩者皆不存在於 repo（`find` 與 `ls` 零命中），無法引用。
