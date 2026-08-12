# ADR-012: Pilot 階段只綁 127.0.0.1，不做認證與 CORS (Pilot Loopback Deployment) - RoomPilot

> **狀態:** 已接受（現況追認，待 owner 核准） ｜ **日期:** 2026-08-12 ｜ **決策者:** MOD-OPS owner（Bella 整合）；服務邊界屬業務決策，待產品 owner 於 [`requirements_tracker.xlsx`](../../01_requirements/requirements_tracker.xlsx) ①需求決策拍板、③Gate 簽核 DEC-014
> **語域:** L2（橋接）——業務承諾與強制點並列，跨層一律用穩定 ID
> **實例:** 每決策一份（`ADR-012-pilot-loopback-deployment.md`）
>
> **本文件回答**：Pilot 為什麼把唯一的安全邊界放在 uvicorn 的 `--host 127.0.0.1`，而不是認證、CORS 或 rate limit；這個邊界成立的前提是什麼；要往內網開放前必須先補齊哪些東西。
> **本文件不含**：安裝與啟動逐步指令（去 `README.md` 與 [`deployment_and_operations.md`](../../06_ops/deployment_and_operations.md)）、資料備份與保留政策（DEC-015，去 [`deployment_and_operations.md`](../../06_ops/deployment_and_operations.md)、[`runbook-runtime-storage-growth.md`](../../06_ops/runbook-runtime-storage-growth.md)）、金鑰為何不下放瀏覽器（去 [`ADR-009`](./ADR-009-server-governed-ai-generation.md)）、模組與部署全貌（去 [`sad.md`](../sad.md)、[`deployment_topology.md`](../diagrams/deployment_topology.md)）。
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、2026-08-12 工作樹。行號隨程式碼演進，衝突時以原始碼為準。

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 執行計畫](#5-執行計畫)
- [6. 追溯](#6-追溯)

## 1. 背景與問題

- **上下文**：整個服務是單一 FastAPI 行程 ＋ 同源靜態單頁，執行資料落在本機 `.runtime/`。存取治理面的現況盤點如下。

| 治理面 | 現況（2026-08-12 實測） | 佐證 |
| :--- | :--- | :--- |
| 應用層中介層 | 全 app 只掛 `GZipMiddleware` 與 `rag_router`，無任何認證 dependency | `main.py:195-197` |
| CORS | 未安裝 `CORSMiddleware`；`backend/` 全樹搜尋 `CORSMiddleware`／`allow_origins`／`OAuth2`／`APIKeyHeader`／`HTTPBearer`／`slowapi` 命中 0（唯一 `security =` 是前端變數 `scene_v2.js:17222`） | 2026-08-12 全樹搜尋 |
| Rate limit | 唯一節流是檢索非同步佇列上限 24 ＋ 保留 3600 秒（429），與 HTTP 層無關 | `rag_api.py:30-32` |
| 傳輸與繫結 | 純 HTTP、無 TLS 設定；三處啟動指令一致 `--host 127.0.0.1 --port 8002`，全 repo 無 `0.0.0.0` | `README.md:49,63,79`；`install.ps1:79`；`install.sh:65` |
| 身分與識別 | 無帳號、無 session、無 cookie；專案唯一識別為 `uuid4().hex`，且無 `GET /api/projects` 清單端點可列舉 | `project_store.py:166` |
| 互動式 API 文件 | `FastAPI(title=…)` 未關 `docs_url`，`/docs`、`/redoc`、`/openapi.json` 隨服務一併公開；靜態掛載只含 `static/` 與 `static/moodboard_assets/`，未掛 repo 根或 `.runtime/` | `main.py:195,126,216-217` |

- **問題**：全部路由匿名可呼叫，其中包含會消耗 OpenRouter 金鑰額度的生圖端點（金鑰由行程 env 讀入，`agent/llm.py:133`）與會寫入客戶案件資料的 workflow 端點。把啟動旗標從 `127.0.0.1` 改成 `0.0.0.0` 不需要改任何一行程式，改完整個內網即取得完整讀寫權，且無存取紀錄可回溯。[`brd.md`](../../01_requirements/brd.md) 已把「不做公開上網服務」（OUT-1）與「不做帳號系統」（OUT-2）列為範圍外（`brd.md:120-121`），但這是**待核准的提案，不是既成宣告**——OPEN-02 明記須由 owner 核准 DEC-014 才成立（`brd.md:195`）。
- **驅動因素／約束**：
  - Pilot 是單一客戶驗證，操作者與伺服器同機，README 直接要求開 `http://127.0.0.1:8002`（`README.md:66`）。
  - 正式前端由同一行程掛載（`main.py:216`），與 API 同源，現況沒有跨源請求，CORS 無實際需求。
  - 帳號系統屬 OUT-2，必須由 owner 明文追認，工程端不得默認為已完成（`brd.md:121`）。
  - 已有的保護只在**輸出面**：遠端渲染請求剝除 PII（`render_service.py:52-61`）、成果包依 `DELIVERY_SENSITIVE_KEYS` 脫敏（`main.py:2475-2491`）——這是資料外流控制，不是存取控制（NFR-020）。

## 2. 考量的選項

### 選項一：只綁 loopback，不做應用層存取控制（採用）
- **描述**：uvicorn 綁 `127.0.0.1:8002`，安全邊界完全交給作業系統網路層；應用層零認證、零 CORS、零 HTTP rate limit。
- **優點**：零實作成本；不引入登入畫面打斷八步導覽；秘密只存在行程 env，無需 session 或 token 儲存。
- **缺點**：邊界是「部署姿勢」而非程式性質，一個旗標即可失效；無稽核；成本無歸屬。
- **成本/複雜度**：低（現況，無新增程式碼）。

### 選項二：綁 0.0.0.0 ＋ 共享密鑰標頭或 HTTP Basic
- **描述**：允許同網段其他機器連入，加一層最小身分（單一共享密鑰標頭，或反向代理層的 Basic Auth）。
- **優點**：Pilot 客戶可用自己的筆電操作，示範不必借用開發機；有最低限度的「誰進來過」。
- **缺點**：共享密鑰無法區分操作者，稽核價值有限；純 HTTP 下密鑰在內網明文傳輸，需一併補 TLS；前端 65 條 fetch 全部要帶標頭，靜態單頁無建置流程（見 [`ADR-010`](./ADR-010-static-frontend-and-eight-step-collapse.md)），改動散落全檔。
- **為何不選**：它同時開放了風險（LAN 可達）又沒補上真正需要的東西（TLS、稽核、個別身分），是三者中最容易誤以為「已經安全了」的一種。DEC-014 尚未核准內網展示，先開放再補洞等同未經核准的範圍變更。
- **成本/複雜度**：中。

### 選項三：反向代理前置（TLS ＋ 認證 ＋ rate limit）
- **描述**：nginx/Caddy 終結 TLS 並負責認證與限流，FastAPI 仍只聽 loopback，僅接受代理來的流量。
- **優點**：安全機制與應用解耦，應用碼零改動；rate limit 可保護生圖端點的金鑰消耗與上傳端點的磁碟消耗。
- **缺點**：多一個必須被安裝、設定與維護的元件；憑證、帳密與代理設定都需要責任人，而 DEC-015 連「誰負責這台機器」都還沒定義（`brd.md:197`，OPEN-13）；`install.ps1`／`install.sh` 的一鍵安裝範圍需擴張（FR-065）。
- **為何不選**：正確方向，但前提（服務邊界、責任人、備份政策）全部卡在待核准的 DEC-014／DEC-015。在 owner 拍板前建置它，等於工程端替業務決策定案。保留為 §5 的開放前置清單。
- **成本/複雜度**：中高。

## 3. 決策

**選擇**：選項一——Pilot 維持 loopback-only，唯一安全邊界是作業系統網路層；應用層不做認證、不開 CORS、不加 HTTP rate limit。**本 ADR 是對既有事實的追認，不是核准後的規格**；DEC-014 未核准前，任何下游文件都不得把「僅本機」寫成已定案的服務邊界（OPEN-02）。

**理由**：在單機單使用者的驗證階段，OS 網路層是唯一不需要新增程式碼、也不可能被前端繞過的邊界；選項二付出改動卻只換到虛假的安全感，選項三的前置條件全部卡在未核准的業務決策。把邊界留在最外層、把「開放前必須做什麼」寫成可檢查清單（§5），比現在先蓋一半的安全機制更誠實。

| 決策要點 | 強制點 | 佐證 |
| :--- | :--- | :--- |
| 唯一邊界＝OS 網路層 | 三處啟動指令一致綁 `127.0.0.1:8002`，程式內無 host 設定可覆寫 | `README.md:49`；`install.ps1:79`；`install.sh:65` |
| 應用層不做身分 | 無認證 dependency、無 session；能連上該埠的行程即擁有完整權限 | `main.py:195-197` |
| 不加 CORS | 前端與 API 同源，不掛 `CORSMiddleware` 等同讓瀏覽器預設同源政策生效 | `main.py:216-217` |
| 秘密不進回應 | 金鑰只從行程 env 讀取；成果包脫敏、遠端渲染剝除 PII；狀態端點只回布林 | `agent/llm.py:133`；`main.py:2475-2491`；`render_service.py:52-61` |
| 資料庫供應獨立於 app 邊界 | PostgreSQL 由 `docker compose` 起，密碼強制由 `.env` 提供（缺值即拒啟動），`pg_isready` 健康檢查未過不服務 | `docker_postgresql/docker-compose.yml:12,20-24` |

## 4. 後果

### 4.1 得到什麼
- 零攻擊面暴露於網路：外部無法連入，不必為 Pilot 維護憑證、帳號或代理設定。
- 八步流程不被登入打斷，一鍵安裝腳本可停在「印出啟動指令」（FR-065，`install.ps1:41-79`；`install.sh:33-65`）；安全承諾與現實一致，QA 不需驗證不存在的認證行為。
- 專案識別不可猜：`uuid4().hex` ＋ 無清單端點，即使邊界被誤開，也不能靠遍歷取得他人專案（`project_store.py:166`）。

### 4.2 付出什麼
- **邊界是部署姿勢，不是程式性質**：`--host 0.0.0.0` 一個旗標即全開，repo 內無任何機制阻止，也無啟動時告警。
- **DB 埠與 app 邊界不對稱**：compose 的 `"${DB_PORT:-5432}:5432"` 未指定繫結 IP，Docker 預設發佈於所有介面——即使 app 只在 loopback，資料庫埠仍對 LAN 可達（`docker_postgresql/docker-compose.yml:14-15`）。
- **無稽核**：沒有存取紀錄與操作者身分，DEC-015 要問的「誰動過客戶資料」目前無法回答；執行資料同時無配額、無輪替、無備份（NFR-022）。
- **成本無歸屬**：任何能連到 8002 埠的行程都能呼叫生圖端點消耗金鑰額度（ADR-009 §4.2 的「無配額」前提正是由本決策承擔）。
- **環境版本落差未收斂**：`requires-python >= 3.12`（`pyproject.toml:5`）、安裝腳本釘 3.12（`install.ps1:44,47`；`install.sh:35`），但實測 `.venv` 為 CPython 3.13.5（`.venv/pyvenv.cfg`）。「照 README 裝出來的環境」與「實際跑測試的環境」不是同一個直譯器（NFR-023）。
- **互動式 API 文件公開**：`/docs` 與 `/openapi.json` 一併暴露完整路由表（`main.py:195`）；loopback 下無害，一旦改綁即成為現成的攻擊面地圖。

### 4.3 重評觸發（可觀測）
- 啟動指令出現 `--host 0.0.0.0`，或前面加了反向代理、port forwarding、內網穿透工具 → 本決策前提立即失效，須先完成 §5 清單。
- 出現第二位並行使用者，或 Pilot 客戶要求以自己的裝置連線操作 → 需要個別身分與稽核，選項二／三重新上桌。
- 出現非同源前端呼叫（例如 `frontend3d/` 以獨立開發伺服器直連 API）→ CORS 從「無需求」變成必須明文決定的白名單。
- DEC-014 核准為「內網展示」→ 至少須完成 §5 第 1–4 項才可開放。
- `.runtime/` 出現真實客戶個資（非測試資料）→ 與 DEC-015／OPEN-13 一併重評保留與刪除政策。

### 4.4 待確認（不得寫成既成事實）
| 編號 | 內容 | 目前可驗證的事實 |
| :--- | :--- | :--- |
| OPEN-02 | 服務邊界是「僅本機」還是「內網展示」、是否需要帳號——DEC-014 未核准前，NFR-019 只能記為現況 | `brd.md:120-121` 提案 OUT-1／OUT-2；`brd.md:195` 記為阻擋項待核准；`srs.md` NFR-019 已標「待 DEC-014 核准」 |
| 待確認（承接 DEC-014） | 資料庫埠對 LAN 發佈是刻意（供他機執行匯入腳本）還是疏漏 | `docker_postgresql/docker-compose.yml:14-15` 未限定繫結 IP；repo 內找不到需要他機連線的證據 |
| 待確認（承接 NFR-023） | 執行環境該釘 3.12 還是 3.13 | `pyproject.toml:5` 與安裝腳本釘 3.12；`.venv/pyvenv.cfg` 實測 3.13.5，兩者未對齊 |
| 待確認（承接 DEC-015／OPEN-13） | 這台機器的責任人、備份頻率、保留天數與結案刪除程序 | repo 內無備份腳本、無專案刪除 API（NFR-022）；`brd.md:197` 記為承諾缺口 |

## 5. 執行計畫

**開放前置清單**——DEC-014 若核准為內網或更廣的邊界，下列各項在開放**之前**完成；未完成即開放，視為未經核准的範圍變更。

1. 加最小身分機制（共享密鑰標頭或代理層 Basic Auth），並補一條「無憑證回 401」的負向測試（TC 待建）。
2. 關閉互動式 API 文件（`FastAPI(docs_url=None, redoc_url=None, openapi_url=None)`，`main.py:195`）或置於認證之後。
3. 資料庫埠改綁 `127.0.0.1:5432:5432`，或直接移除 host 發佈只走 compose 內部網路（`docker_postgresql/docker-compose.yml:14-15`）。
4. 在 HTTP 層加 rate limit（現況只有檢索佇列，`rag_api.py:30-32`），至少涵蓋生圖與上傳端點以限制金鑰額度與磁碟消耗。
5. 補 TLS 終結與存取紀錄，並把責任人、備份頻率與保留天數寫入 [`deployment_and_operations.md`](../../06_ops/deployment_and_operations.md)（DEC-015）。
6. 收斂 Python 版本落差（NFR-023）後回寫 §4.2 與 [`srs.md`](../../01_requirements/srs.md) §3。

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-08-12 | 待簽核 | 現況追認；本 ADR 只記錄程式碼已成立的事實與其代價，服務邊界的正式宣告仍待 DEC-014 |

## 6. 追溯

| 項目 | ID／文件 |
| :--- | :--- |
| 觸發來源 | DEC-014、DEC-015（[`brd.md`](../../01_requirements/brd.md) §7、§9）；FR-065、FR-066、FR-067、NFR-019、NFR-020、NFR-022、NFR-023（[`srs.md`](../../01_requirements/srs.md) §2.9、§3） |
| 驗收對應 | ACPT-056（一鍵安裝與啟動、狀態端點不外洩設定）、ACPT-057（Docker PostgreSQL 供應）、ACPT-058（維運政策，受阻於 DEC-015／DEC-019）；[`srs.md`](../../01_requirements/srs.md) §7 的 SX 跨步列 |
| 影響範圍 | MOD-OPS、MOD-SRV-API、MOD-SQL（[`sad.md`](../sad.md)）；`README.md` 啟動段、`install.ps1`／`install.sh`、`docker_postgresql/docker-compose.yml`；[`deployment_topology.md`](../diagrams/deployment_topology.md) |
| 維運承接 | RB-001（[`runbook-catalog-db-unavailable.md`](../../06_ops/runbook-catalog-db-unavailable.md)）、RB-009（[`runbook-runtime-storage-growth.md`](../../06_ops/runbook-runtime-storage-growth.md)）；[`deployment_and_operations.md`](../../06_ops/deployment_and_operations.md) |
| 相關決策 | [`ADR-009`](./ADR-009-server-governed-ai-generation.md)（金鑰只在伺服器；其「無配額」前提由本決策承擔）、[`ADR-010`](./ADR-010-static-frontend-and-eight-step-collapse.md)（同源靜態單頁，故無 CORS 需求）、[`ADR-005`](./ADR-005-postgres-catalog-source-of-truth.md)（型錄 DB 由 compose 供應）、[`ADR-004`](./ADR-004-single-workflow-snapshot-sqlite.md)（客戶案件資料落在本機 `.runtime/`） |
| 取代關係 | 無（Supersedes：無；Superseded-by：無） |
