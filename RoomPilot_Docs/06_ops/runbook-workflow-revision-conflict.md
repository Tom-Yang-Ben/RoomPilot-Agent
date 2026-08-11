# Runbook - 保存工作流回 409 project_revision_conflict - RoomPilot

> **版本:** 0.1 | **更新:** 2026-08-11 | **狀態:** 草稿
> **Owner:** Bella（`backend/server/` 與 `backend/server/static/` owner，docs/TEAM_AI_OWNERSHIP.md:21-22；AI 衍生，人工核准前為 TO-BE）
> **語域:** L3（工程）
> **實例:** 每故障症狀一份（`runbook-<symptom>.md`）；本份對應症狀 `workflow-revision-conflict`
> **定位宣告:** 本文件回答「專案寫入回 409 `project_revision_conflict`（多分頁/多 session 互踩）時如何診斷、緩解與恢復」；不包含樂觀鎖的設計論述（見 [../03_architecture/adr/ADR-007-workflow-json-single-snapshot-store.md](../03_architecture/adr/ADR-007-workflow-json-single-snapshot-store.md)）、API 錯誤碼總表（見 [../04_design/api_spec.md](../04_design/api_spec.md) §3）與部署拓撲（見 [deployment_and_operations.md](./deployment_and_operations.md)）。
> **生成:** AI 由程式碼與文件衍生｜來源版本 git yen@8863a36c

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

本專案為本機 Pilot，**無 Grafana／告警系統**；症狀來源只有使用者回報與 API 回應。

| 來源 | 看到什麼 | 證據 |
| :--- | :--- | :--- |
| 使用者（`/scene` 頁） | 保存/上傳時彈出訊息「專案已在另一個分頁更新，請載入最新版本後再儲存。」（或「…再上傳。」「…再輸出 PNG。」），右上保存狀態顯示「保存失敗」 | main.py:1854、1904、1993；scene_v2.js:1355 |
| API 呼叫端 | HTTP 409，`detail.code = "project_revision_conflict"`，`detail.project` 附伺服器目前最新專案快照（含 `revision`、`workflow`） | main.py:1850-1857 |
| API 呼叫端（變體） | HTTP 409，`detail` 為純字串 `"project_version_conflict"` —— 未帶 `expected_revision`、只帶 `replay_pending + base_updated_at` 的重播保存撞到落後版本時 | main.py:1858、1836-1839 |

會回此 409 的端點（樂觀鎖比對都在 `ProjectStore`，`BEGIN IMMEDIATE` 內原子比對版本）：

| 端點 | `expected_revision` | 409 位置 |
|---|---|---|
| `PUT /api/projects/{id}/workflow` | payload 選填（int ≥0） | main.py:1848-1857 |
| `POST /api/projects/{id}/floorplan` | Form 選填 | main.py:1899-1907 |
| `POST /api/projects/{id}/renders` | Form **必填** | main.py:1988-1996 |

版本鎖本體：`project_store.py:28-33`（`ProjectVersionConflict`）、`project_store.py:199-218`（鎖內比對 `revision`／`updated_at`）。

## 2. Impact（影響）

| 項目 | 內容 |
| :--- | :--- |
| **受影響功能／使用者** | 八步工作流的自動保存與上傳（REQ-001）；落後的那個分頁/session 無法寫入，**已在伺服器的資料不會遺失**——這是樂觀鎖的預期防護（NFR-002、ACPT-014），落後方未保存的本機編輯若不重放才會丟失 |
| **嚴重程度判定** | 單次 409＋重載後可續作＝預期行為，非 incident。升級為缺陷處理的條件：單一分頁、無並行 session 卻反覆 409；或重載後仍立即 409（revision 比對疑似失準） |

## 3. Possible Causes（可能原因）

按發生機率排序：

1. **兩個分頁／兩個瀏覽器同時編輯同一專案**（SCN-009）——雙方各自遞增 revision，落後方寫入被 `project_store.py:209-213` 擋下。預期行為。
2. **恢復專案時重播 pending save 撞到他處更新**——前端把未完成保存暫存於 localStorage（key `roompilot.pending-save.<project_id>`，scene_v2.js:1290-1301），重開頁面時帶 `replay_pending: true` + `base_updated_at` 重播（scene_v2.js:19267-19294）；伺服器 `updated_at` 已前進則回 409（main.py:1836-1839、project_store.py:214-218），前端自動丟棄 pending save 並改抓最新版（scene_v2.js:19283-19288）。
3. **同分頁內其他寫入端點先遞增了 revision**——floorplan 上傳、renders、palette/ai-renders 寫入都會 +1 revision（project_store.py:228、292、398）；呼叫端沿用舊 `expected_revision` 再寫就 409。
4. **外部 script／測試用寫死的 `expected_revision` 呼叫 API**——`POST /renders` 的 `expected_revision` 是必填 Form（main.py:1941），任何自動化呼叫端沒先 `GET` 最新 revision 就會撞。

注意：正式 UI 的一般自動保存（scene_v2.js:1294-1326 `capturePendingSave`/`saveWorkflowRequest`）**不帶** `expected_revision`，屬 last-write-wins 深合併；因此 `project_revision_conflict` 物件主要出現在上表帶 `expected_revision` 的呼叫與重播路徑（見 §8 待確認）。

## 4. Diagnosis（診斷步驟）

前提：服務跑在 `http://127.0.0.1:8000`（uvicorn 前景執行，log 只在該終端機的 stdout，無 log 檔）。以下 `<PROJECT_ID>` 換成回報者網址 `/scene?project=<PROJECT_ID>` 中的 id。

```powershell
# 1. 取伺服器目前的 revision 與 updated_at（此端點 no-store，回的一定是最新）
(curl.exe -s http://127.0.0.1:8000/api/projects/<PROJECT_ID> | ConvertFrom-Json).project |
  Select-Object project_id, current_step, revision, updated_at

# 2. 與 409 回應比對：detail.project.revision（伺服器最新）vs 呼叫端送的 expected_revision
#    — 409 body 本身就帶最新快照，通常不需要另外查
#    人工重現落後寫入（送一個必落後的 expected_revision）：
curl.exe -s -X PUT http://127.0.0.1:8000/api/projects/<PROJECT_ID>/workflow `
  -H "Content-Type: application/json" `
  -d '{\"expected_revision\": 0, \"workflow\": {}}'
# 預期：{"detail":{"code":"project_revision_conflict", ... "project":{...最新快照...}}}
# 若這裡回 200，代表該專案 revision 恰為 0（全新專案），換一個大數字重試

# 3. 直接查 SQLite（資料庫在 repo 共用 .runtime/，除非設了 ROOMPILOT_RUNTIME_DIR；runtime_paths.py:20-25）
$db = if ($env:ROOMPILOT_RUNTIME_DIR) { Join-Path $env:ROOMPILOT_RUNTIME_DIR "projects.sqlite3" }
      else { "C:\RoomPilot-Agent\.runtime\projects.sqlite3" }
uv run python -c "import sqlite3; [print(dict(r)) for r in sqlite3.connect(r'$db').execute('SELECT project_id,current_step,revision,updated_at FROM projects ORDER BY updated_at DESC LIMIT 5').fetchall()]" 2>$null
# （在 C:\RoomPilot-Agent 下執行；.venv 是 uv 管理，直接 python 可能不在 PATH）

# 4. 確認是否真有並行編輯：問使用者是否開了多個分頁/瀏覽器；
#    伺服器端旁證＝短時間內 revision 連續跳號且 current_step 來回變動（重跑步驟 1 觀察）
```

```javascript
// 5. 在回報者的瀏覽器 DevTools Console（/scene 頁）檢查 pending save 殘留：
Object.keys(localStorage).filter(k => k.startsWith("roompilot.pending-save."))
// 有值＝上次保存沒完成，下次重開會走重播路徑（scene_v2.js:19267-19294）
```

## 5. Mitigation（短期緩解）

**正確做法：重載取最新 revision，把使用者的變更重放在最新狀態上，再重送。**

1. 請使用者**只留一個分頁**編輯該專案，關閉其餘分頁/瀏覽器。
2. 落後的分頁按瀏覽器重新整理——`restoreProject()` 會 `GET /api/projects/{id}` 取回最新 `revision`/`updated_at`，殘留的 pending save 若已落後會被自動丟棄（scene_v2.js:19283-19293），之後繼續編輯即可。
3. 程式化呼叫端（測試/script）：收到 409 後，用 `detail.project`（就是最新快照）為基底，把要改的欄位重放上去，帶最新 `revision` 當 `expected_revision` 重送。

**絕對不能做的事：**

- **不能把舊快照直接蓋寫**（拿最新 revision 但沿用舊的完整 workflow payload 重送，或乾脆拿掉 `expected_revision` 強行寫入——鎖是 opt-in，不帶就必定寫入成功）。原因：保存是深合併（`_merge_dict`，project_store.py:18-25），同 key 的葉值以後送者為準；舊快照重送會把另一個 session 剛寫入的子樹**無聲覆蓋**，資料遺失且無任何錯誤訊息。這正是 NFR-002／ACPT-014 要防的 lost update，也違反 golden-rules 第 3 條「保護使用者工作」。
- 不能為了止血在前端移除 409 處理或重試迴圈裡自動遞增 `expected_revision`——等同關掉鎖。

## 6. Recovery（恢復確認）

- 重載後再存一次：右上保存狀態回到「已自動保存 · <專案名>」（scene_v2.js:1353），不再彈 409 訊息。
- 重跑 §4 步驟 1：`revision` 隨每次保存 +1、`updated_at` 前進。
- 重跑 §4 步驟 5：`roompilot.pending-save.<project_id>` 已清空。
- 抽查雙方剛才的編輯內容（如第 6 步家具、第 5 步問卷）都還在——確認沒有一方被無聲蓋寫。
- 回歸驗證（開發機）：`uv run pytest -q tests/server/test_projects_api.py`（以 yen 分支既有失敗基準為對照，NFR-006／ACPT-016）。

## 7. Escalation（升級路徑）

無 on-call 系統，Pilot 階段以團隊直接聯繫。owner 依 docs/TEAM_AI_OWNERSHIP.md:19-34。

| 情況 | 找誰 | 管道 |
| :--- | :--- | :--- |
| 重載後仍反覆 409、或單分頁也 409（鎖比對疑似失準） | Bella（`backend/server/` FastAPI 與保存 owner） | 團隊直接聯繫 |
| 前端保存/重播行為異常（pending save 不清、保存狀態卡住） | Bella（`backend/server/static/` owner；Yen/Ancai 協作） | 團隊直接聯繫 |
| 懷疑資料已被蓋寫需比對 SQLite 內容 | Bella；`.runtime/` 無原始碼 owner（TEAM_AI_OWNERSHIP.md:36），操作前先備份 `projects.sqlite3` | 團隊直接聯繫 |

事故結束後 48 小時內完成覆盤紀錄（正式覆盤文件依需增建）。

## 8. 追溯

| 項目 | ID／來源 |
| :--- | :--- |
| 對應告警 | 無（本機 Pilot 無告警系統；症狀來源為使用者回報與 API 409） |
| 對應 NFR | NFR-002（revision 樂觀鎖，落後回 409） |
| 對應 ACPT | ACPT-014（落後 revision 收 409、不覆寫他人變更） |
| 對應 SCN | SCN-009（兩分頁同時編輯，落後方收 409 並重載） |
| 上游需求 | REQ-001、FR-001；設計決策 ADR-007（[workflow-json-single-snapshot-store](../03_architecture/adr/ADR-007-workflow-json-single-snapshot-store.md)） |
| 程式碼證據 | main.py:1806-1867（workflow 保存）、1899-1907（floorplan）、1988-1996（renders）；project_store.py:18-25、28-33、199-218；scene_v2.js:1290-1361、19267-19294；runtime_paths.py:20-25 |
| 相鄰文件 | [../04_design/api_spec.md](../04_design/api_spec.md) §2-3（錯誤碼與並發控制）、[deployment_and_operations.md](./deployment_and_operations.md)（啟動與環境變數） |
| 待確認 | ① 正式 UI 一般自動保存不帶 `expected_revision`（last-write-wins 深合併），與 ACPT-014「兩分頁同時保存收 409」的涵蓋範圍是否一致，待 owner 確認是預期設計還是缺口。② `POST /renders` 的呼叫端在目前 `scene_v2.js` 內未找到（第 8 步走 `render-jobs`/`ai-renders`），該端點的實際使用面待確認。③ Phase 3 遷移 PostgreSQL 後（TEAM_AI_OWNERSHIP.md:63）本 runbook 的 SQLite 診斷步驟需改寫。 |
