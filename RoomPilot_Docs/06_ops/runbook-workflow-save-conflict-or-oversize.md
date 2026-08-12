# Runbook - 專案存檔衝突或快照超量 (Workflow Save Conflict or Oversize) - RoomPilot

> **版本:** v1.0 ｜ **更新:** 2026-08-12 ｜ **狀態:** 草稿（待 owner 核准）
> **Owner:** Bella（MOD-SRV-STORE／MOD-WEB；`docs/TEAM_AI_OWNERSHIP.md:21-22`）
> **語域:** L3（工程）
> **實例:** 每故障症狀一份（`runbook-<symptom>.md`）；本份編號 **RB-003**，症狀＝存檔失敗／版本衝突／快照超量
>
> **本文件回答**：使用者說「存不進去」「一直跳保存失敗」「關頁面被瀏覽器攔下來」時，凌晨三點該敲哪幾行指令、怎麼分辨 409／413／500、怎麼救回來。
> **本文件不含**：單一快照＋樂觀鎖的設計取捨（去 [`../03_architecture/adr/ADR-004-single-workflow-snapshot-sqlite.md`](../03_architecture/adr/ADR-004-single-workflow-snapshot-sqlite.md)）、錯誤碼欄位級契約（去 [`../04_design/api_spec.md`](../04_design/api_spec.md)）、`.runtime/` 容量成長本身（去 [`runbook-runtime-storage-growth.md`](./runbook-runtime-storage-growth.md)，RB-009）、第 4 步複核未解造成的 422（去 [`runbook-recognition-failed-or-review-blocked.md`](./runbook-recognition-failed-or-review-blocked.md)，RB-006）。
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、2026-08-12 工作樹。行號隨程式碼演進，衝突時以原始碼為準。

---

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

**無告警來源**：本 repo 無監控、無 alert、無 on-call 輪值；唯一入口是使用者回報或畫面錯誤文案。uvicorn 前景執行，log 只在該終端機 stdout，無 log 檔。

| 來源 | 看到什麼 | 佐證 |
| :--- | :--- | :--- |
| `/scene` 頁右上狀態列 | 卡在「正在保存…」後變成「保存失敗」（正常應為「已自動保存 · <專案名>」） | `scene_v2.js:1332,1353,1355` |
| 頁面錯誤橫幅 | 「專案已在另一個分頁更新，請載入最新版本後再儲存。」 | `main.py:1854`；文案由 `errorMessage()` 取 `detail.message`，`scene_v2.js:642-653` |
| 頁面錯誤橫幅 | 「專案草稿內容超過 2 MB，請移除大型暫存資料後再儲存。」 | `main.py:1864` |
| 離開專案時 | 瀏覽器原生「離開此頁？」提示；或按返回首頁後出現「專案尚未完成保存，請稍後再試。」 | `scene_v2.js:19167-19172,1372-1375` |
| API 呼叫端 | HTTP 409，`detail` 是**物件**：`{"code":"project_revision_conflict", "message":…, "project":<伺服器最新快照>}` | `main.py:1848-1857` |
| API 呼叫端 | HTTP 409，`detail` 是**裸字串** `"project_version_conflict"`——只走 `replay_pending`+`base_updated_at`、沒帶 `expected_revision` 的重播路徑 | `main.py:1836-1839,1858` |
| API 呼叫端 | HTTP 413，`detail.code = "workflow_too_large"` | `main.py:1859-1866`；上限 `MAX_WORKFLOW_BYTES = 2 * 1024 * 1024`，`project_store.py:11` |

## 2. Impact（影響）

| 項目 | 內容 |
| :--- | :--- |
| **受影響功能** | 八步工作流的自動存檔與續作（FR-003、FR-004、FR-022）。每次步驟切換與編輯都走 `PUT /api/projects/{id}/workflow`，存不進去等同該分頁之後的操作全部只活在瀏覽器記憶體。 |
| **資料安全性** | 409／413 都在 `BEGIN IMMEDIATE` 交易內先拋出，**伺服器上一版完好、整筆不落地**（`project_store.py:199-225`，NFR-004）。遺失的只有失敗那一方尚未上傳的本機編輯。 |
| **嚴重程度判定** | 單次 409＋重新整理後可續作＝樂觀鎖預期行為，不是 incident。升級為缺陷：(a) 只有一個分頁、無並行 session 卻反覆 409；(b) 重新整理後仍立即 409；(c) 413（使用者無自助解法，見 §5.3）；(d) 回 500 而非 409/413。 |

## 3. Possible Causes（可能原因）

按發生機率排序：

1. **同一專案開了兩個分頁／兩個瀏覽器**（SCN-002）。落後方帶 `expected_revision` 或 `base_updated_at` 寫入，被 `project_store.py:209-218` 擋下。**注意**：正式前端的一般自動存檔**不帶** `expected_revision`（全 `backend/server/static/` 無此欄位；`scene_v2.js:1305-1326`），因此純自動存檔是 last-write-wins、後手靜靜蓋掉前手——這是 **OPEN-14**，是取捨還是遺漏未定。
2. **重開頁面重播 pending save 撞到他處更新**。前端把未完成存檔雙寫到 `localStorage["roompilot.pending-save.<project_id>"]`（`scene_v2.js:1290-1303`），`restoreProject()` 只在 `base_updated_at === server.updated_at` 時重播（`scene_workflow.js:32-41`、`scene_v2.js:19267-19281`）；不符就直接丟棄該 pending。
3. **快照撐破 2 MB**（SCN-003）。`workflow` 是**深合併**累積（`_merge_dict`，`project_store.py:18-25`）——只覆蓋、不刪除舊 key，所以體積單調成長。現場最大宗是第 7 步白模的 `white_model_3d.sceneData`。
4. **同分頁其他寫入端點先遞增了 revision**。上傳平面圖、存 render 也走同一個 store 並 `revision + 1`（`main.py:1870-1918,1937-1999`；`project_store.py:228`），沿用舊 `expected_revision` 的呼叫端就會撞；`POST /renders` 的 `expected_revision` 是**必填** Form（`main.py:1941`）。
5. **SQLite 寫鎖等待逾時**。`sqlite3.connect(..., timeout=10)`（`project_store.py:90`）；併發寫超過 10 秒會拋 `OperationalError: database is locked`，**沒有對應的 except**（`main.py:1846-1866` 只接兩種例外）→ 回 **500**，不是 409/413。
6. **前端無條件重試放大現象**。`saveWorkflowRequest` 對任何失敗都重試 3 次、退避 180 ms×n（`scene_v2.js:1308-1325`），且丟出的 Error 只帶文字不帶 status（`scene_v2.js:1317`）——所以一次 413 在 log 裡是三筆請求，前端也無法分辨 409 與 413。

## 4. Diagnosis（診斷步驟）

前提：服務跑在 `http://127.0.0.1:8002`（`README.md:49,66`）。`<PROJECT_ID>` 取自回報者網址 `/scene?project=<PROJECT_ID>`。以下為 PowerShell。

```powershell
# 1. 伺服器目前版本與步驟（此端點 no-store，回的一定是最新）— main.py:1800-1804
(curl.exe -s http://127.0.0.1:8002/api/projects/<PROJECT_ID> | ConvertFrom-Json).project |
  Select-Object project_id, current_step, revision, updated_at

# 2. 這個專案離 2 MB 上限多遠（伺服器量的是 UTF-8 bytes，不是字元數）— project_store.py:223-225
$db = if ($env:ROOMPILOT_RUNTIME_DIR) { Join-Path $env:ROOMPILOT_RUNTIME_DIR "projects.sqlite3" } else { "D:\RoomPilot-Agent\.runtime\projects.sqlite3" }
python -c "import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);print(c.execute('select revision,length(cast(workflow_json as blob)) from projects where project_id=?',(sys.argv[2],)).fetchone())" $db <PROJECT_ID>

# 3. 全庫排行：誰快撞上限（2026-08-12 實測：741 筆、最大 1,316,192 bytes＝上限 62.8%、49 筆已破 1 MB）
python -c "import sqlite3;c=sqlite3.connect(r'.runtime\projects.sqlite3');print(c.execute('select count(*),max(length(cast(workflow_json as blob))) from projects').fetchone());print(c.execute('select project_id,length(cast(workflow_json as blob)) from projects order by 2 desc limit 5').fetchall())"

# 4. 誰把它撐大（最大那筆：white_model_3d.sceneData 佔 1,095,210 bytes ≒ 全快照 83%）
python -c "import sqlite3,json,sys;c=sqlite3.connect(r'.runtime\projects.sqlite3');w=json.loads(c.execute('select workflow_json from projects where project_id=?',(sys.argv[1],)).fetchone()[0]);print(sorted(((len(json.dumps(v,ensure_ascii=False).encode()),k) for k,v in w.items()),reverse=True)[:5])" <PROJECT_ID>

# 5. 人工重現 409（送一個必落後的 expected_revision；若該專案 revision 恰為 0 就換大數字）
curl.exe -s -X PUT http://127.0.0.1:8002/api/projects/<PROJECT_ID>/workflow `
  -H "Content-Type: application/json" -d "{\"expected_revision\":0,\"workflow\":{}}"
# 預期 detail 是物件（project_revision_conflict）；若回的是裸字串，代表你走到了重播分支
```

瀏覽器端（回報者的分頁按 F12 → Console）：

```javascript
Object.keys(localStorage).filter((k) => k.startsWith("roompilot.pending-save."))   // 有殘留＝存檔沒完成
const p = localStorage.getItem("roompilot.pending-save.<PROJECT_ID>");
[JSON.parse(p).base_updated_at, new Blob([p]).size]   // 與步驟 1 的 updated_at 比對；size 對照 2 MB
```

回 500 而非 409/413 時：看 uvicorn 終端機 traceback。出現 `database is locked` → 成因 3.5；其他 traceback 直接進 §7 升級。

## 5. Mitigation（短期緩解）

1. **409 物件型**：請使用者重新整理（F5）。`restoreProject()` 會抓最新 project，`base_updated_at` 不符的 pending 會被自動丟棄後續作（`scene_v2.js:19255-19292`）。請他關掉多餘分頁再繼續。
2. **409 裸字串型**：前端已自動處理（catch `error.status === 409` → 丟棄 pending → 重抓最新，`scene_v2.js:19283-19293`）。若仍卡住，Console 執行 `localStorage.removeItem("roompilot.pending-save.<PROJECT_ID>")`——**這會丟掉該分頁未上傳的編輯**，先確認使用者接受。
3. **413**：使用者端無自助解法（深合併刪不掉舊 key）。先 `Copy-Item .runtime\projects.sqlite3 .runtime\projects.sqlite3.bak-<日期>`，再以步驟 4 找出肥大子樹（通常是 `white_model_3d.sceneData` 或其他步驟殘留的舊 `sceneData`），由 Bella 決定刪哪個 key 後離線裁剪。**不要**直接調大 `MAX_WORKFLOW_BYTES`——那是 NFR-001 的規格值，改它要走 ADR-004。
4. **離開時被攔**：`beforeunload` 只在 `pendingSaveCount > 0` 或 localStorage 有殘留時觸發（`scene_v2.js:19167-19172`）。請使用者等狀態列回到「已自動保存 · <專案名>」再離開；急著離開就先照 §5.2 清 pending（同樣會丟編輯）。
5. **500 `database is locked`**：確認是否有另一個 uvicorn／pytest／DB 瀏覽器同時開著同一個 `.runtime/projects.sqlite3`，關掉後重試。本 repo 無自動重試機制。

## 6. Recovery（恢復確認）

- 重跑 §4 步驟 1：`revision` 已 +1、`updated_at` 前進到當下時間。
- 使用者畫面狀態列顯示「已自動保存 · <專案名>」（`scene_v2.js:1353`）。
- Console `Object.keys(localStorage).filter(k => k.startsWith("roompilot.pending-save."))` 回空陣列。
- 重新整理後停在同一步、內容完整（ACPT-001／SCN-001）。
- 涉及程式修改時，回歸至少跑：`pytest -q tests/test_project_store_hardening.py tests/test_project_workflow_api.py`（衝突與超量的既有守護：`test_expected_revision_rejects_stale_update_without_overwriting`、`test_workflow_payload_over_two_megabytes_is_rejected_atomically`、`test_workflow_api_supports_revision_and_size_guard`、`test_pending_save_replay_rejects_a_stale_server_version_atomically`）。

## 7. Escalation（升級路徑）

無 on-call 輪值、無值班表；管道一律為團隊頻道或 repo issue，owner 對應見 [`docs/TEAM_AI_OWNERSHIP.md`](../../docs/TEAM_AI_OWNERSHIP.md) 與 [`../01_requirements/srs.md`](../01_requirements/srs.md) §9.2。

| 情況 | 找誰 | 依據 |
| :--- | :--- | :--- |
| 單分頁、無並行卻反覆 409；或重整後仍 409 | **Bella**（MOD-SRV-STORE、MOD-WEB） | `backend/server/`＋`backend/server/static/` owner |
| 413，需要決定刪哪個 key／是否改 schema | **Bella** 主責；肥大來源在第 6 步幾何找 **Ancai**（MOD-ENG）、在第 8 步生圖產物找 **Bella**（MOD-SRV-RENDER） | 快照子樹歸屬 |
| 500 `database is locked` 或其他 traceback | **Bella** | 存檔層唯一 owner |
| `.runtime/projects.sqlite3` 檔案持續膨脹（2026-08-12 為 69,287,936 bytes） | 依 [`runbook-runtime-storage-growth.md`](./runbook-runtime-storage-growth.md)（RB-009） | 與單筆超量是不同故障 |
| 「一般存檔要不要帶 `expected_revision`」的決策 | **Bella** 提案、產品 owner 拍板 | **OPEN-14**，承接 ADR-004 |
| 保留期、備份、結案刪除等政策 | 產品 owner | **待確認**：DEC-015 未核准前無政策可依（NFR-022、NFR-025） |

事故結束後 48 小時內在 `requirements_tracker.xlsx` ②決策沿革留一列；正式覆盤文件依需增建（本 repo 目前無覆盤模板）。

## 8. 追溯

| 項目 | ID／連結 |
| :--- | :--- |
| Runbook 編號 | **RB-003**（[`../01_requirements/srs.md`](../01_requirements/srs.md) §9.2：S1、SX 兩列指向本份） |
| 對應告警 | **無**——本 repo 無監控與告警，入口為使用者回報與畫面錯誤文案 |
| 業務決策 | DEC-002（進度不遺失）；政策面 DEC-015 待核准 |
| 功能需求 | FR-003（深合併寫入＋白名單＋413）、FR-004（雙軌樂觀鎖）、FR-022（localStorage 雙寫與重播） |
| 非功能需求 | NFR-001（≤ 2 MB）、NFR-003（樂觀鎖一致性）、NFR-004（交易原子性） |
| 驗收與情境 | ACPT-001、ACPT-002、ACPT-003、ACPT-020；SCN-001、SCN-002、SCN-003 |
| 架構決策 | [`ADR-004`](../03_architecture/adr/ADR-004-single-workflow-snapshot-sqlite.md)（單一快照＋SQLite） |
| 測試案例 | TC-001–003、TC-020（計畫見 [`../05_qa/test_plan.md`](../05_qa/test_plan.md)） |
| 待確認 | **OPEN-14**（一般存檔不帶 `expected_revision`＝last-write-wins，取捨或遺漏未定）；另：`docs/contracts/POSTGRESQL_PROJECT_STORE_PHASE3.md:9` 宣稱 `backend/server/postgres_project_store.py` 仍存在，但該檔在本分支不存在，live store 為 SQLite（`main.py:147`）——契約敘述過期，待 Bella 更新 |
| 相鄰 runbook | RB-009 [`runbook-runtime-storage-growth.md`](./runbook-runtime-storage-growth.md)、RB-006 [`runbook-recognition-failed-or-review-blocked.md`](./runbook-recognition-failed-or-review-blocked.md)（422 `recognition_review_unresolved` 走該份，`main.py:1817-1827`） |
| 上游／下游 | 上游：[`../01_requirements/srs.md`](../01_requirements/srs.md)、[`../04_design/api_spec.md`](../04_design/api_spec.md)；下游：[`deployment_and_operations.md`](./deployment_and_operations.md)、[`../00-registry.md`](../00-registry.md) |
