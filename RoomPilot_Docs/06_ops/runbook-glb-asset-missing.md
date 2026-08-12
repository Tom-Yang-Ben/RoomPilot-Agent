# Runbook RB-008：3D 家具 GLB 缺席或載入失敗 (GLB Asset Missing) - RoomPilot

> **版本:** v1.0 ｜ **更新:** 2026-08-12 ｜ **狀態:** 草稿（待 owner 核准）
> **Owner:** Kai（`backend/catalog/`、`JSON/` manifest、CloudFront 資產）＋ Bella（`backend/server/` 交付端點與 `static/` viewer），依 [`docs/TEAM_AI_OWNERSHIP.md`](../../docs/TEAM_AI_OWNERSHIP.md):9,12,21,22
> **語域:** L3（工程）
> **實例:** 每故障症狀一份（本檔＝症狀「3D 出現替身方塊／GLB 載不到／模型端點回 410」）
>
> **本文件回答**：第 6 步 3D 出現橘色替身方塊、或第 6→7 步被「GLB 無法載入」擋住時，怎麼在最短路徑判斷是「型錄本來就沒模型、manifest 沒對到、CloudFront 取不到、快照帶著舊 URL」哪一種，怎麼緩解，怎麼確認已恢復。
> **本文件不含**：型錄資料庫連不上（去 [`runbook-catalog-db-unavailable.md`](./runbook-catalog-db-unavailable.md)，RB-001）、家具幾何擺不下（去 [`runbook-placement-blocked.md`](./runbook-placement-blocked.md)，RB-007）、型錄權威與降級決策理由（去 [`ADR-005`](../03_architecture/adr/ADR-005-postgres-catalog-source-of-truth.md)）、端點欄位契約（去 [`api_spec.md`](../04_design/api_spec.md)）、部署與環境全貌（去 [`deployment_and_operations.md`](./deployment_and_operations.md)）。
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、2026-08-12 工作樹。行號隨程式碼演進，衝突時以原始碼為準。

## 目錄

- [1. Symptoms（症狀）](#1-symptoms症狀)
- [2. Impact（影響）](#2-impact影響)
- [3. Possible Causes（可能原因）](#3-possible-causes可能原因)
- [4. Diagnosis（診斷步驟）](#4-diagnosis診斷步驟)
- [5. Mitigation（短期緩解）](#5-mitigation短期緩解)
- [6. Recovery（恢復確認）](#6-recovery恢復確認)
- [7. Escalation（升級路徑）](#7-escalation升級路徑)
- [8. 追溯](#8-追溯)

## 1. Symptoms（症狀）

**無告警來源。** 本 repo 無監控、無 dashboard、無 alert 規則、無 on-call 輪值；本故障只靠使用者回報或下列畫面／API 回應被發現。

| 症狀 | 觀察位置 | 佐證 |
| :--- | :--- | :--- |
| 3D 出現橘色半透明方塊替身（`0xd97706`、`opacity 0.38`、深橘描邊）取代真家具 | 瀏覽器第 6 步 3D | `scene_viewer.js:4091-4140` |
| 替身原因文案「資料庫尚未提供 GLB」＝ `model_url` 為空，根本沒送出請求 | 3D 診斷／待處理清單 | `scene_viewer.js:4224-4227` |
| 替身原因文案「GLB 載入失敗，請更換家具或檢查資料庫模型權限」＝ loader 丟例外（網路、403、檔案損毀），同時 DevTools Console 有 GLTFLoader 堆疊（唯一的錯誤細節來源） | 3D 診斷／待處理清單、Console | `scene_viewer.js:4270-4278` |
| 第 6→7 步被擋：「有 N 件資料庫 GLB 無法載入，請先修正型錄權限或更換家具，才能進入下一步。」 | 瀏覽器 `#white-error` | `scene_v2.js:13940-13954` |
| 更早一關被擋：「有 N 件家具尚未找到可用的資料庫 GLB：…請更換家具或確認型錄模型後再進入配置預覽。」 | 瀏覽器 `#layout-error` | `scene_v2.js:12639-12649` |
| 2D 家具清單該列右側徽章顯示「圖示」而非「GLB」；配置清單顯示「缺少 GLB」 | 瀏覽器側欄 | `scene_v2.js:11058,12983` |
| `GET /api/furniture/{id}/model` **沒有**回 307（改回 404「找不到可載入的 GLB 模型。」或本機檔案） | API | `main.py:4012-4018,1066-1087` |
| cloudfront 模式下 `model.gltf`／`buffer.bin`／`images/{i}`、`/api/furniture/{name}.glb` 回 **410**＋中文訊息；`/api/sample-furniture` 回空陣列＋「請由家具型錄取得已驗證的 CloudFront model_url。」 | API | `main.py:4021-4047,4174-4181,4194-4195` |

**3am 陷阱三則。**（1）**410 不是故障**：cloudfront 模式下三個 glTF 拆解端點依契約就該回 410（`docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md:42`），看到 410 代表模式正確、不要往這方向修。真正的故障是 `/model` 沒回 307。
（2）**同一件事三套文案**：catch 分支寫「請更換家具或檢查資料庫模型權限」，診斷面板同情境卻寫「請檢查資料庫模型權限或網址」（`scene_viewer.js:4276,4308-4310`）；文字不同不代表原因不同。
（3）**替身會自動重試**：`loadScene` 只在上次 `fallbackFurnitureCount === 0` 時才跳過重建，有替身就整包重載（`scene_viewer.js:4142-4156`）——所以修好後重進第 6 步即可，不必清快取。

## 2. Impact（影響）

| 項目 | 內容 |
| :--- | :--- |
| **受影響功能** | 第 6 步 3D 白模不可信（替身尺寸只依 `size_cm` 畫方盒）；第 6→7 步硬閘阻斷，`failedFurniture` 非空即無法前進（`scene_v2.js:13948-13954`）；連帶第 7、8 步無法開始 |
| **連帶效應** | 第 5 步問卷候選會**變少**：載不到的 `model_url` 會被加入 `unavailableCatalogModelUrls` 並在該分頁 session 內永久排除，沒有清除入口（`scene_v2.js:632,10068-10091`）——修好後必須重新整理頁面 |
| **仍可運作** | 第 1–5 步主流程、型錄瀏覽與三視角圖片（走 `front/side/angle-45` image URL，不經 GLB）、幾何合法性計算（引擎不讀 GLB） |
| **嚴重程度判定** | 單件缺模型＝可繞過（換家具）；整批 `verified_model_count` 掉到 0＝第 6 步等同不可用，為本 Pilot 最高嚴重度。**升級門檻、回應時限與覆盤義務本 repo 無明文政策 → 待確認（OPEN-02，承接 [`deployment_and_operations.md`](./deployment_and_operations.md)）** |

## 3. Possible Causes（可能原因）

按發生機率排序：

| # | 原因 | 你會看到 | 佐證 |
| :--- | :--- | :--- | :--- |
| 1 | 該家具在型錄本來就沒模型：view 的 `glb_url` 為 NULL 或空白 → `has_model:false` | `model_url:null`＋`missing_model_reason:"缺少可載入的 GLB 模型。"` | `postgres_repository.py:130,346,409-411`；`main.py:860-869` |
| 2 | cloudfront 模式，但 manifest 找不到這件的已驗證列（ID、合併 ID、唯一英文品名三種鍵全落空） | `model_url:null`；`/model` 404，訊息「CloudFront manifest 中找不到此家具的 delivery_url。」 | `cloud_models.py:153-174,177-192`；`main.py:649-655,1066-1071` |
| 3 | manifest 檔缺席或路徑指錯（預設 `<repo>/JSON/manifests/glb_upload_all_result.csv`，可用 `ROOMPILOT_GLB_MANIFEST_PATH` 覆寫） | 整批家具同時失效；`/api/catalog/status` 的 `manifest_error` 為 `missing`／`invalid_or_unreadable`／`empty` | `cloud_models.py:26-31,71-76,136-150,195-208` |
| 4 | manifest 有列但 `upload_status` 不在白名單，或 `delivery_url` 非 https 且 `object_key` 空 → 該列不產出 URL（部分家具失效，manifest 卻「有檔案」） | `verified_model_count` 少於預期 | `cloud_models.py:35-42,79-89` |
| 5 | URL 存在但 CloudFront 端取不到（403／404／CORS／連線中斷）——伺服器不參與，瀏覽器直接吃 https URL | 替身＋Console 例外，`/model` 仍正常回 307 | `scene_viewer.js:4230,4270-4278`；`main.py:4012-4017` |
| 6 | **專案快照帶著舊 URL**：合併時 `scene_json` 的既有值優先於型錄現值 | 型錄已修好，重開舊專案仍失敗 | `scene_service.py:759,761` |
| 7 | 改了 manifest 或 `.env` 卻沒重啟：manifest 索引掛 `lru_cache`，無 TTL、無檔案監看 | 檔案已修但行為不變 | `cloud_models.py:98-104,136-138,211-214` |
| 8 | 房數多、相異 `model_url` 超過頁面級 LRU 上限 48 → 反覆淘汰重載，表現為間歇性替身與卡頓（NFR-021） | 大坪數專案才出現，小案重現不了 | `scene_viewer.js:42-50,66-85` |
| 9 | 有人試圖讓隔離區家具（`unmatched_cloud_furniture` 1,514 筆）出現在場景 | 守護測試變紅 | `tests/test_cloud_quarantine.py:21-42` |

## 4. Diagnosis（診斷步驟）

伺服器 base URL 為 `http://127.0.0.1:8002`（`README.md:49`）。逐步照跑，第一個異常的步驟就是分歧點；`<ID>` 換成畫面上那件家具的 `furniture_id`。

```powershell
# 1. 整批還是單件？（可直接在瀏覽器開）http://127.0.0.1:8002/api/catalog/status
curl.exe -s http://127.0.0.1:8002/api/catalog/status
#   furniture.verified_model_count = 0 或 manifest_ready = false → 整批問題，看 manifest_error（原因 3）
#   furniture.provider = "kai_postgresql" 且 verified_model_count 正常 → 單件問題，往下走

# 2. 這件家具的型錄現值：model_url / has_model / missing_model_reason
curl.exe -s http://127.0.0.1:8002/api/furniture/<ID>
#   model_url = null + missing_model_reason「缺少可載入的 GLB 模型。」→ 原因 1（型錄沒模型）
#   model_url = null + 訊息提到 CloudFront manifest                  → 原因 2/3/4

# 3. 交付端點該回 307；回 404 就是伺服器端也拿不到 URL
curl.exe -s -o NUL -w "%{http_code}`n" http://127.0.0.1:8002/api/furniture/<ID>/model
#   307 → 伺服器沒問題，問題在 CloudFront 或瀏覽器端（原因 5），跳步驟 5
#   404 → 原因 1/2/3/4
#   410 → 你打到的是 model.gltf / buffer.bin / images/{i}，那是契約行為不是故障

# 4. manifest 裡到底有沒有這件（預設路徑；有設 ROOMPILOT_GLB_MANIFEST_PATH 就換成該路徑）
Select-String -Path D:\RoomPilot-Agent\JSON\manifests\glb_upload_all_result.csv -Pattern "<ID>" | Select-Object -First 3
#   沒命中 → 原因 2；有命中但 upload_status 不在 success/uploaded/complete/completed/already_exists/skipped_existing → 原因 4

# 5. 直接打那個 CloudFront URL（步驟 2 或 3 的 Location 拿到的）
curl.exe -s -I -o NUL -w "%{http_code}`n" "<CloudFront URL>"
#   200 → CDN 沒問題，問題在瀏覽器端（快取、擴充套件、離線），看 Console；403/404 → 原因 5，交 Kai

# 6. 交付模式與 manifest 設定（密碼與金鑰不要貼進工單）
Get-Content D:\RoomPilot-Agent\.env | Select-String "^ROOMPILOT_MODEL_DELIVERY_MODE|^ROOMPILOT_CLOUDFRONT_BASE_URL|^ROOMPILOT_GLB_MANIFEST_PATH|^ROOMPILOT_EXTERNAL_GLB_ZIP_DIRS"

# 7. 型錄源頭：view 這一列的 glb_url 到底有沒有值（原因 1 的最終確認）
psql -h localhost -p 5432 -U postgres -d roompilot_db -c "SELECT item_id, glb_url FROM roompilot.furniture_catalog_current WHERE item_id = '<ID>';"
```

> 前端 `whiteViewer.getDiagnostics()` **無法**在 Console 直接呼叫：`scene_v2.js` 以 `type="module"` 載入（`scene.html:1217`），不掛 `window`。請改看畫面上的錯誤區文案與待處理清單，或 Console 的 loader 例外。

## 5. Mitigation（短期緩解）

1. **單件缺 GLB（原因 1／2）** → 在第 6 步換一件同類家具。前端已把它標為 `placementFailed` 並附「尚未找到可用的資料庫 GLB，請替換為可載入的家具。」（`scene_v2.js:12650-12660`），換完即可通過硬閘。
2. **manifest 路徑錯（原因 3）** → 在 repo 根 `.env` 設 `ROOMPILOT_GLB_MANIFEST_PATH` 指到正確檔案，**重啟 uvicorn**（索引掛 `lru_cache`，`cloud_models.py:136-138`）。
3. **CloudFront 全面不可用（原因 5，且短期修不好）** → 依契約做**人工災難切換**（不是自動 failover）：先完成 SHA-256 與型錄對應驗證，再設 `ROOMPILOT_MODEL_DELIVERY_MODE=local` ＋ `ROOMPILOT_EXTERNAL_GLB_ZIP_DIRS=<已驗證 zip>` 並重啟；CloudFront 恢復後**必須改回 `cloudfront` 再重啟**（`docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md:44-58`；`cloud_models.py:45-52`）。
4. **舊專案卡著舊 URL（原因 6）** → 請使用者在第 6 步重新產生配置，讓前端以型錄現值覆寫 `item.model_url`（`scene_v2.js:10652-10658`）；只重新整理頁面不會清掉快照裡的舊值。
5. **候選在問卷端被永久排除（§2）** → 修復後請使用者**重新整理 `/scene` 分頁**；`unavailableCatalogModelUrls` 是 session 級 `Set`，無 API 可清（`scene_v2.js:632`）。
6. **重啟指令**：`.\.venv\Scripts\python.exe -m uvicorn backend.server.main:app --host 127.0.0.1 --port 8002`（`README.md:49`）。
7. **禁止事項**：不得替隔離區家具猜測 `model_url`、不得把 `has_model` 硬設為 true、不得在 cloudfront 模式下改走本機 ZIP 繞過驗證（`docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md:30-31,41`；`tests/test_cloud_quarantine.py:21-42`）。

## 6. Recovery（恢復確認）

四項全過才算恢復（對應 ACPT-038、ACPT-040）：

```powershell
# 1. 交付端點回 307
curl.exe -s -o NUL -w "%{http_code}`n" http://127.0.0.1:8002/api/furniture/<ID>/model
# 2. 型錄狀態：manifest_ready = true 且 verified_model_count 回到基準
curl.exe -s http://127.0.0.1:8002/api/catalog/status
# 3. 隔離區零外洩守護測試仍綠（確認緩解沒有把隔離資料放進來）
.\.venv\Scripts\python.exe -m pytest tests/test_cloud_quarantine.py -q
```

4. 使用者側（**重新整理分頁後**再確認）：第 6 步 3D 無橘色替身方塊、家具清單徽章顯示「GLB」、按「進入下一步」不再出現「有 N 件資料庫 GLB 無法載入」。恢復判定**沒有量化基線可比對**（無載入耗時指標、無歷史 dashboard），只能以上述布林檢查為準；量化 SLA 待確認，承接 [`deployment_and_operations.md`](./deployment_and_operations.md)。

## 7. Escalation（升級路徑）

**本專案無 on-call 系統、無升級計時器、無事故追蹤工具**；下表的「管道」一律是直接聯繫該 owner。逾時門檻與覆盤義務本 repo 皆無政策 → 待確認，結論請寫回 [`requirements_tracker.xlsx`](../../VibeCoding_Workflow_Templates/01_requirements/requirements_tracker.xlsx) ②決策沿革。

| 情況 | 找誰（MOD） | 管道與依據 |
| :--- | :--- | :--- |
| manifest 缺列／狀態不對、CloudFront 物件 403/404、view 的 `glb_url` 為空、需重跑資產上傳 | Kai（MOD-CAT、MOD-SQL） | 直接聯繫；`TEAM_AI_OWNERSHIP.md:12,25,26` |
| `/api/furniture/{id}/model` 與本檔描述不符、410／307 行為異常、viewer 替身或硬閘邏輯有誤 | Bella（MOD-SRV-API、MOD-WEB） | 直接聯繫；`TEAM_AI_OWNERSHIP.md:9,21,22` |
| GLB 正常載入但家具仍進待處理清單（原因是碰撞／淨空） | Ancai（MOD-ENG）→ 改走 [RB-007](./runbook-placement-blocked.md) | `TEAM_AI_OWNERSHIP.md:29` |
| 整個型錄不可用（`available:false`），不只是模型 | Kai ＋ Bella → 改走 [RB-001](./runbook-catalog-db-unavailable.md) | 本檔 §4 步驟 1 |
| 要裁決「是否允許本機 ZIP 作為常態備援」「manifest 正規路徑是哪一個」 | 產品 owner ＋ Kai／Bella | [`ADR-005`](../03_architecture/adr/ADR-005-postgres-catalog-source-of-truth.md)；[`CATALOG_MODEL_DELIVERY_CONTRACT.md`](../../docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md) |

## 8. 追溯

| 項目 | ID／文件 |
| :--- | :--- |
| Runbook 編號 | **RB-008**（[`srs.md`](../01_requirements/srs.md) §9.2，S6 列；索引見 [`00-registry.md`](../00-registry.md)） |
| 對應告警 | 無。本專案無監控與告警來源，觸發僅靠使用者回報或 §1 的畫面／API 回應 |
| 上游需求 | DEC-007、DEC-017；FR-042、FR-045（次要：FR-024、FR-037、FR-038）；NFR-021 |
| 驗收與情境 | ACPT-038（模型與圖片交付失敗時的替代呈現）、ACPT-040（隔離資料零外洩）；無專屬 SCN，歸 [`srs.md`](../01_requirements/srs.md) §7 的 S6 區塊 SCN-017–025 |
| 測試 | TC-038、TC-040（[`test_plan.md`](../05_qa/test_plan.md)）；現有守護測試 `tests/test_cloud_quarantine.py:21-42` |
| 架構決策 | [`ADR-005`](../03_architecture/adr/ADR-005-postgres-catalog-source-of-truth.md)（型錄與資產權威）、[`ADR-010`](../03_architecture/adr/ADR-010-static-frontend-and-eight-step-collapse.md)（前端即產品，替身呈現在瀏覽器端）、[`sad.md`](../03_architecture/sad.md) |
| 影響模組 | MOD-CAT（Kai）；MOD-SRV-API、MOD-WEB（Bella）；MOD-OPS |
| 相關 runbook | [RB-001](./runbook-catalog-db-unavailable.md)（型錄 DB）、[RB-007](./runbook-placement-blocked.md)（擺不下）、[RB-009](./runbook-runtime-storage-growth.md)（執行資料成長） |
| 待確認 | **本檔新增（無既有 OPEN 編號）**：①manifest 正規路徑分歧——程式預設 `JSON/manifests/glb_upload_all_result.csv`（`cloud_models.py:26-31`），契約覆寫範例卻寫 `backend/catalog/data/manifests/…`（`docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md:66`），兩處實際都存在同名檔，哪一份是權威待 Kai 裁決；②同一故障三套中文文案（`scene_viewer.js:4226,4276,4308-4310`）是否收斂；③GLB 快取上限 48 無實測依據（原始碼註明是粗上限），NFR-021 的目標值待確認；④`unavailableCatalogModelUrls` 無清除入口，恢復後必須重新整理分頁——是否補 API 待 Bella 裁決 |
