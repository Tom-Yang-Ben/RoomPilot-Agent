# 安全與生產準備檢查清單 - RoomPilot-Agent

> 本文件由 VibeCoding 模板 13_security_and_readiness_checklists.md 導入 RoomPilot-Agent 生成 | 基準分支 bella-local-20260726 | 2026-07-26

> **版本:** v1.0 | **更新:** 2026-07-26(程式基準 e48cd67;現 HEAD d88b707 僅新增 docs,程式檔相同) | **審查人員:** 待補(本檔為程式碼實查產出,尚未經人工安全審查)

**系統定位(影響判讀基準):** RoomPilot-Agent 目前是本機啟動的 FastAPI 單體(`uv run uvicorn backend.server.main:app --port 8002`,README L185),無使用者帳號系統、未對外部署。以下每項按「現狀程式碼實查」打勾/打叉;❌ 不代表現階段展示不能用,代表**對外部署前必須處理**。

**標記說明:** `[x]` 通過(附證據) / `[ ]` ❌ 不通過(附風險與建議) / `[ ]` ⚠️ 部分成立或條件性通過。

---

## 重點五項現況總覽(導入指引指定項目)

| 項目 | 現況 | 一句結論 |
| :--- | :---: | :--- |
| `.env` 與 secrets 管理 | ⚠️ | `.env` 已 gitignore、`git log --all` 無提交紀錄、`.env.example` 金鑰欄位全空、程式無硬編碼金鑰;但無專用 secrets 管理系統,金鑰輪替與團隊共享方式未定義 |
| 上傳檔案驗證 | ⚠️ | 渲染 PNG 端點驗證最完整(20MB 上限+magic bytes+PIL);平面圖端點有副檔名白名單+PIL 驗證但**無大小上限**;舊版 `/api/upload` 幾乎無驗證 |
| CORS 設定 | ⚠️ | 全 backend 零 CORS/middleware 設定(grep 實測零命中)=瀏覽器同源政策預設拒絕跨域,現行同源部署可運作;但屬「未設定」而非「設定了白名單」 |
| AWS 憑證處理 | ✅ | repo 內無任何 AWS 金鑰樣式與 SDK;執行期只消費 CloudFront 公開 HTTPS URL;manifest 的 presigned URL 欄 9,350 列全空;唯一揭露是 bucket 名含 AWS 帳號 ID(低風險) |
| 依賴風險 | ❌ | 有 `uv.lock`/`package-lock.json` 鎖定;本次手動實測 pip-audit(93 個鎖定套件)0 個已知漏洞、npm audit 1 個 high(postcss);但無常態掃描機制(無 CI/Dependabot),`/scene` 與 `/library` 從 unpkg CDN 載 three.js 無 SRI |

---

## A. 核心安全原則

- [ ] ❌ **最小權限**: 全部 44 條 API 路由(`backend/server/main.py`,路由裝飾器 grep 實數;`@app.` 全部 45 處另含 1 個 startup 事件)無任何認證授權——`Depends`/`Authorization`/`api_key` 在 main.py 零命中。風險:任何能連上該 port 的人可建立/讀取/覆寫所有專案資料。建議:對外部署前加最小認證層;本機展示至少確保 uvicorn 只綁 127.0.0.1。
- [ ] ❌ **縱深防禦**: 無任何 middleware(grep `add_middleware` 全 backend 零命中)、無速率限制、無 WAF——唯一防線是各端點的參數驗證。風險:單一驗證疏漏即直達資料層。建議:對外部署時前置反向代理(限流+TLS)。
- [ ] ⚠️ **預設安全**: 部分成立——家具交付預設 `cloudfront` 模式且只回 manifest 驗證過的 HTTPS URL(`backend/server/services/cloud_models.py`,docstring 明言 manifest 是信任邊界);遠端渲染未設定時回 503 不產生假結果(`render_service.py`)。但伺服器本身「預設無認證」。
- [ ] ⚠️ **攻擊面最小化**: cloudfront 模式下舊 glTF 拆解端點(model.gltf/buffer.bin/images)已改回 410(main.py:2627 起)——有做關閉;但舊版 R3F 路由 `/api/plans`、`/api/plan`、`/api/upload` 仍存活(main.py:2661-2693),其中 `/api/upload` 驗證最弱(見 C 節)。建議:確認 frontend3d 去留後淘汰或補驗證。

## B. 資料安全與隱私

### 資料分類與收集
- [ ] ❌ 資料未依敏感性分類——repo 內無資料分類文件(未查證是否存在於 repo 外)。風險:上傳的平面圖與問卷內容(居住格局、家庭成員描述)實質上是個人資料,但未被當 PII 對待。建議:至少在 README 或契約標注「上傳平面圖視同個資」。
- [x] 只收集業務必要資料:API 請求 payload 均為流程必要欄位(專案名/平面圖/問卷/場景);無追蹤、無第三方分析腳本(static HTML 無外部 analytics,僅 unpkg CDN 載 three.js)。
- [ ] ⚠️ PII 同意機制:現行頁面無同意文案——scene.html 與 scene_v2.js 的「隱私/同意/consent」grep 零命中;僅未被任何頁面載入的舊版 scene.js 留有 privacy-consent 勾選流程,main.py:1788-1794 仍相容該舊欄位。但送外部渲染前有實質防護——`render_service.py:12-22` 定義 `PRIVATE_KEYS`(name/phone/email/address 等 9 鍵),`_strip_private_fields` 遞迴剝除後才送供應商,與 `docs/contracts/REMOTE_RENDER_CONTRACT.md` L61-62 一致。

### 傳輸安全
- [ ] ❌ 本機服務為純 HTTP:uvicorn 啟動無 TLS 設定(README L183-196、repo 內無憑證/TLS 設定)。風險:跨機器使用時(README L207 組員驗收情境)平面圖與問卷內容明文傳輸。建議:對外部署走反向代理終結 TLS;內網展示可接受。
- [x] 對外呼叫皆 HTTPS:OpenRouter 端點硬編碼 `https://openrouter.ai/api/v1/chat/completions`(intake_service.py:141、scene_service.py:240);CloudFront base `https://ddgsm1yg3xikc.cloudfront.net`(cloud_models.py:34),且 `_https_url()` 強制 delivery URL 為 https 才採用。
- [ ] ⚠️ 例外:遠端渲染供應商 URL 直接取自環境變數 `ROOMPILOT_RENDER_PROVIDER_URL`,無 https scheme 強制(render_service.py:126-140)。風險:誤填 http URL 時 Bearer token 明文外送。建議:submit 前驗證 scheme。

### 儲存安全
- [ ] ❌ 敏感資料未加密儲存:專案資料存 SQLite `.runtime/projects.sqlite3`(WAL),上傳平面圖/渲染 PNG 明文存 `.runtime/uploads/`、`.runtime/renders/`(project_store.py:275-278、runtime_paths.py:20-25)。風險:本機檔案任何本地程序可讀。建議:展示階段可接受;對外部署改伺服器級磁碟權限控管。
- [ ] ⚠️ 金鑰管理:secrets 全在本機 `.env`(見 D 節,gitignore 有效),無 KMS/Vault。單人本機情境可接受;團隊共享 `.env` 的分發與輪替方式未定義。
- [ ] ❌ 備份保護:無備份機制(`.runtime/` 在 .gitignore L12,不進版控也無其他備份)。風險:專案資料單點存放,誤刪 `.runtime/` 即全失。建議:展示前手動備份 `.runtime/`。

### 資料生命週期
- [x] 日誌不記錄敏感資訊:backend/server 完全未使用 logging 模組(grep 零命中);`OPENROUTER_API_KEY` 與 render token 只進 Authorization header(scene_service.py:268、intake_service.py:141、render_service.py:138),無列印金鑰之處(grep `api_key` + print/log 交叉實測)。
- [ ] ❌ 無資料保留期限定義、無過期銷毀機制(repo 內未查到)。風險:上傳的平面圖無限期留存。建議:發表會後清空 `.runtime/uploads/`。

## C. 應用程式安全

### 認證
- [ ] ❌ **整個系統無認證機制**——無帳號、無密碼、無 session(main.py 零命中),密碼 hash/Session token/暴力破解防護三項全部不適用。唯一存取控制是 `project_id = uuid4().hex`(project_store.py:166):不可列舉,但知道 ID 即可完全讀寫該專案。風險:URL 被分享/記錄即等於交出專案控制權。建議:展示階段明知即可;對外部署為前置條件。

### 授權
- [ ] ❌ 物件級授權不存在:任何請求者持 project_id 即可 `GET /api/projects/{id}`、`PUT .../workflow`、上傳覆寫平面圖(無擁有者概念)。風險與建議同上——這是「無認證」的直接推論,不是獨立漏洞。
- [ ] ❌ 功能級授權不存在:44 條路由權限一律相同。

### 輸入驗證與輸出編碼
- [x] 防注入:SQLite 全部參數化查詢——project_store.py 28 處 `execute()` 皆用 `?` 佔位,無 f-string 拼 SQL(grep 實測);PostgreSQL 匯入器用 psycopg2 `execute_values`(scripts/sql/import_official_catalog_to_postgres.py)。
- [ ] ❌ 防 XSS:無 CSP——無 middleware 即無 CSP header,4 個靜態 HTML 亦無 CSP meta(grep 零命中);前端 33 支自家 JS 中 `innerHTML` 實測出現於 6 支共 109 處(scene_v2.js 51 處;另 31 處在未被任何頁面載入的舊版 scene.js),是否有使用者輸入流入這些寫入點未逐一稽核(未查證)。風險:若任一 JS 把使用者輸入(專案名/問卷答案)以 innerHTML 寫入即成 stored XSS。建議:抽查 scene_v2.js 對使用者字串的渲染方式,並補 CSP meta。
- [ ] ⚠️ 防 CSRF:無 CSRF token;但系統無 cookie session,不存在「借用既有登入態」的古典 CSRF——跨站請求與直接請求權限相同,問題被「無認證」吸收。加認證時必須同時補 CSRF 防護。

### 上傳檔案驗證(逐端點實查)

| 端點 | 副檔名白名單 | 內容驗證 | 大小上限 | 路徑安全 | 判定 |
| :--- | :---: | :--- | :---: | :--- | :---: |
| `POST /api/projects/{id}/floorplan`(main.py:1593-1639) | ✅ `.dxf/.png/.jpg/.jpeg`(main.py:111) | 影像走 PIL `Image.verify`+空檔檢查(main.py:1493-1517);**DXF 只驗副檔名即放行**(1503-1504) | ❌ 無 | ✅ `Path(filename).name` 取 basename(1600),實際存為固定檔名 `floorplan{ext}`(project_store.py:277) | ⚠️ |
| `POST /api/projects/{id}/renders`(main.py:1660-1720) | (只收 PNG) | ✅ PNG magic bytes(1687)+PIL verify(1693);provider 白名單只接受 `browser_capture` | ✅ 20MB,`read(MAX+1)` 實測法(1681-1686) | ✅ 存檔名由伺服器生成 | ✅ |
| `POST /api/upload`(舊版 R3F,main.py:2682-2693) | ❌ 無 | ❌ 唯一驗證=ezdxf 解析失敗回 422 | ❌ 無,整檔讀入記憶體 | 檔名僅作顯示 | ❌ |
| `POST /api/floorplan/analyze`(main.py:2705-2718) | ✅ `.png/.jpg/.jpeg` | ⚠️ 交給下游 `decode_image`/分析管線,無前置 PIL 驗證 | ❌ 無 | — | ⚠️ |
| `GET /api/plan`(main.py:2666-2679) | (讀伺服器內建檔) | — | — | ✅ `Path(name).name` basename,註解明寫「防路徑跳脫」(2673) | ✅ |
| `PUT /api/projects/{id}/workflow`(main.py:1542-1590) | (JSON) | ✅ 步驟名對 `WORKFLOW_STEPS` 白名單、型別逐項驗證 | ✅ 2MB(project_store.py:11,超過 413) | — | ✅ |

- [ ] ❌ **三個上傳端點無大小上限**(floorplan、/api/upload、/api/floorplan/analyze 皆 `await file.read()` 全量進記憶體)。風險:單一超大檔即可耗盡記憶體(DoS),floorplan 端還會原樣寫入磁碟。建議:比照 renders 端點的 `read(MAX+1)` 模式加上限(平面圖 20-50MB 已足)。
- [ ] ⚠️ DXF 內容驗證薄弱:上傳時不驗內容,實際解析延後到 analyze 步驟由 ezdxf 承擔(經 temp file,upgrade3d/dxf_parser.py)。風險:惡意構造 DXF 的資源消耗由 ezdxf 解析行為決定(未查證 ezdxf 對此的防護)。建議:對外部署前補解析逾時或大小上限。

### API 安全
- [ ] ❌ 端點認證授權:同「認證」節,44/44 條無認證。
- [ ] ❌ 速率限制:無(grep `rate`/`limiter` 零命中)。風險:LLM 端點(`/api/agent/intake/*`、`/api/scene/generate`)可被刷量,消耗 OpenRouter 額度。建議:對外部署時於反向代理層限流。
- [x] 參數白名單驗證:普遍做得紮實——副檔名白名單、`WORKFLOW_STEPS` 集合驗證(main.py:113-125)、render mode 白名單 `palette_comparison|room_final`(render_service.py:11)、`/api/plan` Query 有 `gt/le` 邊界(main.py:2669-2671)、LLM 選件結果經伺服器端白名單重驗(`/api/agent/furniture/select`,main.py:2220-2281:furniture_id 必在候選集、count 夾 1-6)。
- [ ] ⚠️ 回應最小化:大致可以;例外是 409 revision 衝突回應附完整最新 project payload(main.py:1571-1580)——對無認證系統無額外暴露,加認證後需重新評估。

### 依賴安全
- [ ] ❌ 無常態漏洞掃描機制:repo 無 `.github/`(ls 實測不存在)、無 CI、無 audit/dependabot/snyk 工具設定。本次查證已手動實測一次(2026-07-26):`uvx pip-audit`(uv export --all-extras 匯出的 93 個鎖定套件)0 個已知漏洞;`npm audit --package-lock-only`(frontend3d,無需安裝 node_modules)1 個 high——postcss ≤8.5.17 路徑跳脫(GHSA-r28c-9q8g-f849),`npm audit fix` 可修。風險:此為單次快照,之後的新 CVE 仍無人知會。建議:修 postcss,並把兩道指令納入例行或一支 CI workflow。
- [x] 版本鎖定存在:repo 根 `uv.lock`(475KB)、`frontend3d/package-lock.json` 皆在版控;pyproject 依賴為下限約束(`>=`),paddle 系列有上限 `<4`。
- [ ] ❌ 前端 CDN 供應鏈:`/scene` 與 `/library` 兩頁 importmap 從 unpkg 載 `three@0.165.0`(scene.html:787-788、library.html:164-165),無 SRI、無 vendoring。風險:unpkg 被竄改或斷線時,3D 頁面供應鏈失守或直接失效(離線展示會場即重現)。建議:把 three 0.165.0 vendored 進 `/static`(自家 `scene_v2.js` 已用 sha256 查詢參數防快取,可比照管理)。

## D. 基礎設施安全

- [ ] ⚠️ 防火牆/安全組:不適用(未部署雲端);本機唯一等效控制是 uvicorn 綁定位址,README 啟動指令未指定 `--host`(uvicorn 預設 127.0.0.1),組員跨機驗收時如何開放未在 repo 文件中規定(grep `--host` 全 repo 文件僅本檔自身命中;實際操作方式未查證)。
- [ ] ❌ DDoS 防護:無,同速率限制項。
- [x] **Secrets 不硬編碼**(重點項,逐條實查):
  - `.env` 在 .gitignore L1(另 L2 涵蓋舊路徑 `web_fastapi/.env`);`git log --all -- .env backend/server/.env` 無任何提交紀錄——金鑰從未進過版控。
  - 版控內 `.env.example` 全部金鑰欄位為空值(OPENROUTER_API_KEY=、ROOMPILOT_RENDER_PROVIDER_TOKEN=)。
  - 本機 `.env` 現只含 OPENROUTER_* 五個鍵(只查鍵名未讀值)。
  - AWS 憑證樣式(`AKIA*`/aws_secret/aws_access_key/boto3)在 backend/ 與 scripts/ 零命中;pyproject 無任何 AWS SDK——本 repo 執行期不持有 AWS 憑證,GLB 上傳程式在別處(kai 分支,不在本分支)。
  - manifest CSV 的 `temporary_presigned_url` 欄 9,350 列全空(python csv 實測)——無簽名 URL 洩漏。
  - PostgreSQL 匯入器憑證全走環境變數 `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD`(import_official_catalog_to_postgres.py:192-196),密碼預設空字串非硬編碼值。
  - `.env` 載入點有三處且行為一致(`override=False`/不覆蓋既有環境變數):intake_service.py:22-40(手寫 parser,repo 根與 backend/server/.env)、cloud_models.py:23-25(python-dotenv)、scene_service.py `load_local_env()`。
- [ ] ⚠️ 例外(資訊揭露,低風險):manifest CSV 入版控揭露 S3 bucket 名 `roompilot-furniture-glb-prod-825555019055-ap-east-2-an`(內含 AWS 帳號 ID)與 s3_uri/s3_etag(CSV 首列實測)。風險:攻擊者得知帳號 ID 與 bucket 命名,利於針對性嘗試;bucket 的 AWS 端實際設定不可由 repo 查證,但 kai 分支 `KAI_progress.md` 明列「Block Public Access 應保持開啟」且 OAC/Bucket Policy 外部實測項標「待確認」(git show origin/kai 實查)——設計意圖已文件化,實測完成與否仍需向 Kai 確認。建議:向 Kai 確認 bucket 只允許 CloudFront OAC 讀取。
- [ ] ⚠️ 非 root/容器:不適用(無容器化);伺服器以開發者本人帳號執行。
- [ ] ❌ 安全事件日誌與告警:無——backend/server 未使用 logging 模組,存取紀錄只有 uvicorn 預設 access log,無留存與告警。

## E. 合規性

- [ ] ❌ 未識別適用法規:repo 內無合規文件;台灣情境下上傳平面圖+問卷屬個資法適用資料(未查證是否有課程層級的豁免認定)。建議:發表會蒐集他人資料前口頭告知用途即可,商用化才需正式處理。
- [ ] ⚠️ 已落實的合規相關設計:對外送資料前剝除私人欄位(render_service.py PRIVATE_KEYS)、機電需求輸出固定附 `requires_professional_review=True` 與免責聲明(backend/floorplan/vision/requirements.py)。

## F. 審查結論

| # | 行動項 | 負責人 | 預計完成 | 狀態 |
| :--- | :--- | :--- | :--- | :--- |
| 1 | 三個無上限上傳端點補大小上限(floorplan/`/api/upload`/`/api/floorplan/analyze`,比照 renders 的 `read(MAX+1)` 模式) | 待指派(backend/server 依 README 責任表屬 Bella) | 待補 | 待辦 |
| 2 | three@0.165.0 從 unpkg 改 vendored 進 `/static`(同時解決離線展示風險) | 待指派 | 8/20 發表前 | 待辦 |
| 3 | 手動跑 `pip-audit` + `npm audit`(2026-07-26 已跑:pip-audit 0 漏洞、npm audit 1 high=postcss);後續=`npm audit fix` 並納入例行 | 待指派 | 待補 | 部分完成 |
| 4 | 向 Kai 確認 S3 bucket 讀取權限僅開放 CloudFront OAC(kai 分支 KAI_progress.md 自列 OAC/Bucket Policy 實測「待確認」) | 本顥(跨組協調) | 待補 | 待辦 |
| 5 | 抽查 scene_v2.js 使用者字串渲染是否有 innerHTML 注入點 | 待指派 | 待補 | 待辦 |
| 6 | 決定舊版 R3F 路由(`/api/upload` 等)去留;保留則補驗證 | 待指派(涉 frontend3d 去留裁決) | 待補 | 待辦 |
| 7 | 對外部署前置項:認證層、TLS(反向代理)、速率限制 | 待指派 | 僅商用化需要 | 待辦 |

**整體評估:** 以「本機/內網展示」用途,現狀可執行——secrets 管理與注入防護紮實,主要缺口(無認證/無 TLS/無限流)在單機展示情境不構成實際暴露。**不可以現狀直接對外公開部署**:行動項 7 全數為前置條件,行動項 1 在展示情境也建議先做(單一誤操作大檔即可讓伺服器記憶體耗盡)。

---

## G. 生產準備就緒

### 可觀測性
- [ ] ❌ 監控儀表板:無。
- [ ] ❌ SLI 定義:無。
- [ ] ❌ 結構化日誌:無——backend/server 完全未用 logging 模組(grep 零命中),僅 uvicorn 預設輸出。
- [ ] ❌ 全鏈路追蹤:無 OpenTelemetry 或任何追蹤依賴(pyproject 實查)。
- [ ] ❌ 告警:無。
- 註:以上五項對 8/20 課堂發表非必要;列出供商用化評估。

### 可靠性
- [ ] ❌ `/health` 健康檢查端點:不存在(grep main.py 零命中)。建議:一條 `GET /health` 回 200 成本極低,對組員驗收(「伺服器起來了沒」)立即有用。
- [ ] ⚠️ 優雅停機:交由 uvicorn 框架預設 SIGTERM 處理(專案無自訂 shutdown hook;`@app.on_event("startup")` 只做型錄預熱且失敗不擋啟動,main.py:2102-2108——該 API 已被 FastAPI 標記棄用,收集測試時有 deprecation warning)。
- [x] 外部呼叫有超時:OpenRouter 8 秒(intake_service.py:143、scene_service.py:247)、遠端渲染 5-180 秒夾擠預設 60(render_service.py:33-38);OpenRouter 失敗一律降級本地規則(guided_fallback/local_rules),渲染供應商失敗回 502/503 不假成功。重試:無顯式 retry,scene 規劃以多模型輪詢(scene_service.py:274 `for model in models`)達到等效備援。
- [ ] ❌ 故障轉移:單機單進程,無。
- [ ] ❌ 備份恢復演練:`.runtime/` 無備份機制(同 B 節)。

### 效能與擴展
- [ ] ❌ 負載測試:未做(repo 無任何負載測試腳本)。
- [ ] ❌ 容量規劃:未做;已知單點是型錄 JSON(8MB+16MB)整包載入記憶體與上傳全量進記憶體。
- [ ] ❌ 無狀態化:否——SQLite(WAL)+本機檔案系統綁定單機,無法水平擴展;`ROOMPILOT_RUNTIME_DIR` 可改資料目錄位置(runtime_paths.py:22-24)但仍是單寫者。

### 可維護性
- [ ] ⚠️ Runbook:README 有安裝/啟動/驗收步驟(L183-215)與 floor04.png 驗收基準(L212);無故障排除 runbook。
- [ ] ❌ CI/CD:無——`.github/` 不存在,392 個測試全靠本機手動 `uv run pytest`。本次實跑(2026-07-26):389 通過、2 失敗(`tests/test_scene_v2_contract.py` 兩條快取鍵與 bundle 內容不符的契約測試)、1 跳過。風險:合併分支時無自動守門(7/24 合併曾出現 4 個紅燈前例)。建議:一支跑 pytest 的 GitHub Actions workflow 即可補上。
- [x] 配置集中管理:環境變數統一 `ROOMPILOT_` 前綴(LLM 為 `OPENROUTER_`),`.env.example` 為完整範本並附註解;平面辨識參數集中在 `backend/floorplan/config.ini`。
- [x] Feature Flag(env 開關)已實作:`OPENROUTER_INTAKE_ENABLED=1`(intake_service.py:138)、`OPENROUTER_SCENE_PLANNING_ENABLED=1`(scene_service.py:264)、`ROOMPILOT_MODEL_DELIVERY_MODE=cloudfront|local`(cloud_models.py:49)——前兩者預設關閉;delivery mode 預設 `cloudfront` 嚴格雲端模式(README 明言不悄悄 fallback 本機),符合「重大能力用開關」精神。

---

## 交叉引用

- API 端點全表與錯誤碼:`docs/vibecoding/04_design/api_spec.md`
- 目錄結構與 gitignore 白名單陷阱:`docs/vibecoding/04_design/lld_project_structure.md`
- 遠端渲染的隱私剝除與 503 契約:`docs/contracts/REMOTE_RENDER_CONTRACT.md`
- CloudFront 信任邊界與 410 政策:`docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md`
