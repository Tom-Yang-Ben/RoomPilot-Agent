# Runbook - 執行資料持續成長與磁碟壓力 (Runtime Storage Growth) - RoomPilot

> **版本:** v1.0 ｜ **更新:** 2026-08-12 ｜ **狀態:** 草稿（待 owner 核准）
> **Owner:** Bella（MOD-SRV-STORE／MOD-OPS；`docs/TEAM_AI_OWNERSHIP.md:21`）；保留與備份政策的決策權在產品 owner（DEC-015）
> **語域:** L3（工程）
> **實例:** 每故障症狀一份（`runbook-<symptom>.md`）；本份編號 **RB-009**，症狀＝`.runtime/` 只增不減、磁碟餘量下降、無專案刪除途徑
>
> **本文件回答**：`.runtime/` 撐大時，凌晨三點要量什麼、哪個子樹是肥大來源、在**沒有配額／輪替／備份／刪除 API** 的前提下能做什麼、哪些動作必須先等 owner 核准。
> **本文件不含**：執行資料佈局與各目錄用途的完整清單（去 [`deployment_and_operations.md`](./deployment_and_operations.md) §6，本文件不重複該表）、單筆快照撞 2 MB 上限的 413（去 [`runbook-workflow-save-conflict-or-oversize.md`](./runbook-workflow-save-conflict-or-oversize.md)，RB-003）、SQLite schema 與欄位設計（去 [`../04_design/db_design.md`](../04_design/db_design.md)）、PDF 產出失敗（去 [`runbook-delivery-pdf-engine-missing.md`](./runbook-delivery-pdf-engine-missing.md)，RB-005）。
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

**無告警來源**：本 repo 無監控、無容量 alert、無 on-call 輪值，也**沒有任何回報容量的狀態端點**——`main.py` 的 60 條路由與 `rag_api.py` 的狀態端點沒有一條揭露磁碟或資料庫大小。入口只有使用者回報、畫面錯誤文案，或維運者自己 `du`。

| 來源 | 看到什麼 | 佐證 |
| :--- | :--- | :--- |
| 主機 | 部署磁碟餘量持續下降；`.runtime/` 只增不減，跑再久也不會自己縮回去 | 全 `backend/server/*.py` 只有兩處刪除：`project_store.py:401`（上傳 render 失敗回滾）與 `questionnaire_visuals.py:182-183`（索引重灌）；無 `VACUUM`、無 TTL、無排程 |
| API 呼叫端 | 想刪掉舊案子卻找不到端點 | **零條 `@app.delete`**；`GET /api/projects` 列表端點也不存在，只有 `GET /api/projects/{project_id}`（`main.py:1800`） |
| 第 2 步上傳 | 磁碟寫滿時回 **500**（無具名 code）：`stored_path.write_bytes()` 拋 `OSError`，端點只接 `ProjectVersionConflict` | `project_store.py:278`；`main.py:1890-1907` |
| 第 2 步讀圖 | 有人手動刪過 `uploads/` → 410 `floorplan_source_missing`「原始平面圖已遺失，請重新上傳。」 | `main.py:1698-1706` |
| 第 8 步下載 | 有人手動刪過 `manuals/` → 410 `design_manual_file_missing`／`delivery_proposal_file_missing`「紀錄存在，但檔案已遺失，請重新產出。」 | `main.py:2345-2349,2432-2436` |

**2026-08-12 實測基準線**（本機工作樹，服務未執行故無 `-wal`／`-shm`）：

| 子樹 | bytes | 筆數／檔數 | 成長模型 |
| :--- | ---: | :--- | :--- |
| `uploads/` | 119,062,637 | 451 個專案目錄，單目錄最大 828 KB | 每專案一份，固定檔名重傳即覆蓋（`project_store.py:275-278`）→ 隨**專案數**線性 |
| `projects.sqlite3` | 69,287,936 | 741 筆專案；`workflow_json` 合計 67,465,720 bytes（＝檔案 97%），最大 1,316,192、49 筆已破 1 MB | 深合併只覆蓋不刪 key（`project_store.py:18-25`）→ 隨**編輯次數**單調成長 |
| `manuals/` | 46,588,468 | **僅 3 個專案、4 個 PDF**，最大單檔 15,061,617 bytes | 每次呼叫用 `uuid4` 新檔名、舊檔留著（`design_manual_service.py:227-228,261-262`）→ 隨**產出次數**線性，單位成本最高 |
| `renders/`、`agent_pipeline/` | 0 | `render_outputs` 表 0 筆 | 本機未觸發；兩者皆僅追加、無清理（`project_store.py:349-356`；`agent_pipeline_service.py:8-11,54-60`） |
| `indexes/`、`engineering/`、`auth_secret.key` | 237,568／196,716／約 1 KB | — | 問卷索引每次 `sync()` 先清表重灌、可重建（`questionnaire_visuals.py:180-183`） |
| 合計 | **235,373,389** | — | — |

## 2. Impact（影響）

| 項目 | 內容 |
| :--- | :--- |
| **受影響功能** | 磁碟寫滿時最先死的是寫檔路徑：第 2 步上傳（FR-005）、第 7 步 render 保存（FR-009）、第 8 步 PDF（FR-061、FR-062），接著是 SQLite 寫入（FR-003）＝整條八步工作流的自動存檔。讀路徑（`GET`）在寫入失敗後仍可運作。 |
| **資料安全性** | **無備份腳本**——磁碟或檔案一旦損毀即無恢復來源（NFR-022）。`.runtime/` 由 `.gitignore` 整目錄排除，不在版控內。 |
| **嚴重程度判定** | 「持續成長」本身**不是 incident**，是已登記的既知缺口（NFR-022、OPEN-13）。升級為 incident：(a) 部署磁碟餘量 < 10%；(b) 上傳或 PDF 產出開始回 500；(c) 有人為了挪空間刪過 `.runtime/` 底下任何檔案（此時同時觸發 §5 的資料遺失風險）。 |

## 3. Possible Causes（可能原因）

按**單位成長率**排序，不是按發生機率——這份故障沒有「原因」，只有「哪個子樹長最快」：

1. **交付提案／設計手冊 PDF 只追加不覆蓋**。每次 `POST design-manual`／`delivery-proposal` 產生 `roompilot-{manual|proposal}-<pid8>-<uuid8>.pdf`（`design_manual_service.py:227-228,261-262`），workflow 只換掉中繼資料裡的 `filename`，舊檔永遠留在 `manuals/<project_id>/`（`main.py:2290-2291`）。單檔 9.6–15.1 MB。**算術外推（非實測）**：741 筆專案若各出一份提案，`manuals/` 約需 8.6 GB。
2. **`workflow_json` 深合併單調成長**。`_merge_dict` 只覆蓋、不刪 key（`project_store.py:18-25`）；主要體積在第 6／7 步白模，抽樣最大三筆中 `white_model_3d` 佔 2,890,867 bytes ≒ 83%。SQLite 檔即使將來刪列也不會自動縮小（無 `VACUUM`）。
3. **啟動時把舊 worktree 的執行資料複製進共用目錄**。`import_runtime()` 對 `legacy_runtime_dirs()` 掃出的每個 `.runtime` 逐筆比 `updated_at`，較新者 `shutil.copy2` 上傳檔與 render 檔（`project_store.py:433-441,466-484,523-537`；`main.py:147-149`；掃描範圍 `runtime_paths.py:28-53`）。**副作用：手動刪掉的檔案可能在下次啟動被重新複製回來。**
4. **沒有任何刪除途徑**。零條 DELETE 路由、無 TTL、無配額檢查、無排程清理；唯一的 `unlink` 是 render 寫入失敗的回滾（`project_store.py:400-402`）。上傳路徑則相反——檔案先落地再更新資料庫（`project_store.py:278-297`），交易失敗會留下孤兒檔。
5. **`uploads/` 目錄數與專案數對不上**（451 vs 741）：曾被手動搬動或來自不同 worktree 的合併結果。孤兒目錄不會被任何程式回收。
6. **執行資料根目錄放在 repo 內**。未設 `ROOMPILOT_RUNTIME_DIR` 時預設 `<repo 根>/.runtime`（`runtime_paths.py:20-25`），與程式碼、模型快取共用同一顆磁碟。

## 4. Diagnosis（診斷步驟）

前提：服務跑在 `http://127.0.0.1:8002`（`README.md:49`）。以下為 PowerShell，路徑以 `D:\RoomPilot-Agent` 為例。

```powershell
# 0. 先確認服務還活著（無容量端點，只能用既有狀態端點當 liveness）
curl.exe -s http://127.0.0.1:8002/api/catalog/status | ConvertFrom-Json | Select-Object provider, available

# 1. 磁碟餘量（先判斷是不是真的緊急）
Get-PSDrive D | Select-Object Used, Free, @{n='FreePct';e={[math]::Round($_.Free/($_.Used+$_.Free)*100,1)}}

# 2. .runtime 分項大小（對照 §1 基準線看漲了多少）
$rt = if ($env:ROOMPILOT_RUNTIME_DIR) { $env:ROOMPILOT_RUNTIME_DIR } else { "D:\RoomPilot-Agent\.runtime" }
Get-ChildItem $rt | ForEach-Object {
  $n = if ($_.PSIsContainer) { (Get-ChildItem $_.FullName -Recurse -File | Measure-Object Length -Sum).Sum } else { $_.Length }
  [pscustomobject]@{ Name=$_.Name; MB=[math]::Round($n/1MB,1) } } | Sort-Object MB -Descending

# 3. SQLite：檔案大小 vs 內容大小（差額≒VACUUM 可回收量），與快照分布
python -c "import sqlite3,os;p=r'$rt\projects.sqlite3';c=sqlite3.connect(p);print('file',os.path.getsize(p));print(c.execute('select count(*),sum(length(cast(workflow_json as blob))),max(length(cast(workflow_json as blob))) from projects').fetchone());print('renders',c.execute('select count(*),coalesce(sum(byte_size),0) from render_outputs').fetchone())"

# 4. 最肥的 5 筆專案，以及肥在哪個 workflow 節點
python -c "import sqlite3,json;c=sqlite3.connect(r'$rt\projects.sqlite3');rows=c.execute('select project_id,length(cast(workflow_json as blob)) n,workflow_json from projects order by n desc limit 5').fetchall();[print(r[0],r[1],sorted(((len(json.dumps(v,ensure_ascii=False).encode()),k) for k,v in json.loads(r[2]).items()),reverse=True)[:3]) for r in rows]"

# 5. manuals：逐檔大小（單位成本最高的子樹；同一專案多個 PDF＝重複產出的歷史檔）
Get-ChildItem "$rt\manuals" -Recurse -Filter *.pdf |
  Sort-Object Length -Descending | Select-Object -First 10 Length, FullName

# 6. 孤兒偵測：uploads 目錄數 vs projects 筆數
(Get-ChildItem "$rt\uploads" -Directory).Count
python -c "import sqlite3;print(sqlite3.connect(r'$rt\projects.sqlite3').execute('select count(*) from projects').fetchone()[0])"

# 7. 確認「真的沒有自動清理」再動手（預期：只命中 §3.4 那兩處）
rg -n "rmtree|unlink|DELETE FROM|VACUUM|@app\.delete" D:\RoomPilot-Agent\backend\server
```

## 5. Mitigation（短期緩解）

**全部是人工操作，且 `.runtime/` 沒有備份**。動任何檔案前先 `Copy-Item`；不確定就先停在 §7。

1. **先備份，再談其他**：停掉 uvicorn（避免 WAL 半途），`Copy-Item $rt "D:\roompilot-runtime-backup-<日期>" -Recurse`。本 repo 無備份腳本，這一步就是全部的備份機制。
2. **搬走執行資料根目錄（唯一非破壞性手段）**：設 `ROOMPILOT_RUNTIME_DIR` 指向大容量磁碟的絕對路徑後重啟（`runtime_paths.py:20-25`）。**注意**：舊 `.runtime` 會被 `legacy_runtime_dirs()` 掃到並在啟動時 `import_runtime()` 合流回來（`main.py:147-149`），所以搬完要把舊目錄移出 repo 樹或改名，否則等於複製一份而非搬家。
3. **清 `manuals/` 舊 PDF（CP 值最高）**：只保留每個專案 workflow 中 `design_manual.filename`／`delivery_proposal.filename` 指到的那一份，其餘為歷史殘留。刪掉被指到的檔會讓下載變 410（`main.py:2345-2349,2432-2436`），使用者需重新產出。
4. **清 `uploads/`**：**只對已結案專案做**。刪掉後該專案第 2 步讀圖回 410（`main.py:1698-1706`）、無法重跑辨識（FR-010）。沒有「已結案」的定義可依——這正是 DEC-015 未核准的直接後果。
5. **縮 `projects.sqlite3`**：需停服務、`DELETE FROM projects WHERE …` 後 `VACUUM`。本 repo **無此腳本、無此 API、無保留政策**，屬破壞性且不可逆，**必須先取得 Bella 核可與 owner 的刪除授權**（§7）。不要改 `MAX_WORKFLOW_BYTES`（`project_store.py:11`）——那是 NFR-001 規格值，走 ADR-004。
6. **不要做的事**：不要把 `.runtime/` 加進版控；不要在服務執行中直接刪 `projects.sqlite3-wal`；不要靠刪 `indexes/` 省空間（僅 237 KB，且會在下次 `sync()` 重建）。

## 6. Recovery（恢復確認）

- 重跑 §4 步驟 1：磁碟 `FreePct` 回到可接受範圍（**門檻值待確認**——本 repo 未定義容量目標，見 NFR-025）。
- 重跑 §4 步驟 2：分項大小符合預期，且與備份副本的差額可解釋。
- 服務可寫：對測試專案跑一次第 2 步上傳（`POST /api/projects/{id}/floorplan`）回 201，不是 500。
- 若動過 `manuals/`／`uploads/`：對受影響專案打一次 `GET .../design-manual/pdf`、`GET .../floorplan/source`，確認回的是 200 或**預期中的 410**，而非 500。
- 若搬過根目錄：重啟後 `GET /api/projects/{已知 project_id}` 仍回得到專案，且 §4 步驟 3 的筆數與搬家前一致（確認 `import_runtime` 沒有把舊目錄又合流一次）；涉及程式修改時回歸 `pytest -q tests/test_project_store_hardening.py`。

## 7. Escalation（升級路徑）

無 on-call 輪值、無值班表；管道一律為團隊頻道或 repo issue，owner 對應見 [`docs/TEAM_AI_OWNERSHIP.md`](../../docs/TEAM_AI_OWNERSHIP.md) 與 [`../01_requirements/srs.md`](../01_requirements/srs.md) §9.2。

| 情況 | 找誰 | 依據 |
| :--- | :--- | :--- |
| 要刪任何客戶案件資料（`projects.sqlite3` 列、`uploads/`、`manuals/`） | **產品 owner** 授權；**Bella** 執行 | 無保留政策可依，**DEC-015 未核准（OPEN-13）**；不可由值班者自行判斷 |
| 上傳／PDF 產出開始回 500，或 `.runtime/` 寫入失敗 | **Bella**（MOD-SRV-STORE／MOD-OPS） | `backend/server/` owner（`docs/TEAM_AI_OWNERSHIP.md:21`） |
| `white_model_3d` 快照異常肥大（單筆逼近 2 MB） | **Bella** 主責；幾何內容找 **Ancai**（MOD-ENG）、選件內容找 **Yen**（MOD-AGT） | 快照子樹歸屬；單筆超量走 RB-003 |
| 型錄／向量資料庫（PostgreSQL）磁碟成長 | **Kai**（MOD-CAT／MOD-SQL） | 不在 `.runtime/` 範圍，本份不涵蓋 |
| 檢索模型快取約 4.6 GB 佔用 | **Django**（MOD-RAG） | 見 [`runbook-rag-model-cache-missing.md`](./runbook-rag-model-cache-missing.md)（RB-004） |
| 要求「加配額／輪替／備份／刪除 API」 | **產品 owner** 拍板範圍後 **Bella** 實作 | 目前全部不存在（NFR-022）；目標值未定義（NFR-025） |

事故結束後 48 小時內在 `requirements_tracker.xlsx` ②決策沿革留一列；正式覆盤文件依需增建（本 repo 目前無覆盤模板）。

## 8. 追溯

| 項目 | ID／連結 |
| :--- | :--- |
| Runbook 編號 | **RB-009**（[`../01_requirements/srs.md`](../01_requirements/srs.md) §9.2：S2、SX 兩列指向本份） |
| 對應告警 | **無**——本 repo 無監控、無容量告警、無容量狀態端點；入口為使用者回報、畫面錯誤文案與人工 `du` |
| 業務決策 | **DEC-015**（客戶案件資料存哪、誰備份、保留多久、結案怎麼刪）——**待 owner 核准**；相鄰 DEC-014（服務邊界，決定誰能碰到這些資料） |
| 功能需求 | FR-008（啟動時 `import_runtime` 合流舊 worktree 執行資料）；受影響的寫入路徑 FR-003、FR-005、FR-009、FR-061、FR-062 |
| 非功能需求 | **NFR-022**（無配額／無輪替／無備份／無刪除 API 的現況登記）、**NFR-025**（容量目標、備份頻率、保留天數**目標值未定義**）；相鄰 NFR-001（單筆 2 MB 上限）、NFR-019（存取邊界） |
| 驗收與情境 | ACPT-007（`import_runtime` 合流語意）、ACPT-058（維運政策，**受阻於 DEC-015**，見 srs §7「SX 受阻」列） |
| 架構決策 | [`ADR-004`](../03_architecture/adr/ADR-004-single-workflow-snapshot-sqlite.md)（單一快照＋SQLite）、[`ADR-012`](../03_architecture/adr/ADR-012-pilot-loopback-deployment.md)（Pilot 部署形態） |
| 測試案例 | TC-007、TC-058（計畫見 [`../05_qa/test_plan.md`](../05_qa/test_plan.md)；TC-058 在 DEC-015 核准前無可驗對象） |
| 待確認 | **OPEN-13**（資料保存、備份、保留與交還政策空白，承接 [`../01_requirements/brd.md`](../01_requirements/brd.md) §9）；**OPEN-02**（服務邊界未宣告，決定這些資料的可及範圍）。本文件新增待確認：**容量告警門檻與 `.runtime/` 所在磁碟的容量規劃無來源可考**，須隨 DEC-015 一併定義。 |
| 相鄰 runbook | RB-003 [`runbook-workflow-save-conflict-or-oversize.md`](./runbook-workflow-save-conflict-or-oversize.md)（單筆快照超量／存檔衝突）、RB-004 [`runbook-rag-model-cache-missing.md`](./runbook-rag-model-cache-missing.md)（模型快取佔用）、RB-005 [`runbook-delivery-pdf-engine-missing.md`](./runbook-delivery-pdf-engine-missing.md)（PDF 產出失敗） |
| 上游／下游 | 上游：[`../01_requirements/srs.md`](../01_requirements/srs.md) §3／§4、[`../04_design/db_design.md`](../04_design/db_design.md)；下游：[`deployment_and_operations.md`](./deployment_and_operations.md) §6、[`../00-registry.md`](../00-registry.md) |
