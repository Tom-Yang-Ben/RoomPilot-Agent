# Runbook RB-006：平面圖辨識失敗或複核卡住 (Recognition Failed or Review Blocked) - RoomPilot

> **版本:** v1.0 ｜ **更新:** 2026-08-12 ｜ **狀態:** 草稿（待 owner 核准）
> **Owner:** Cody（`backend/floorplan/`、`backend/upgrade3d/`：辨識、比例尺、牆門窗房間）＋ Bella（`backend/server/`：端點狀態碼與第 3／4 步 UI），依 [`docs/TEAM_AI_OWNERSHIP.md`](../../docs/TEAM_AI_OWNERSHIP.md):10,21,22,23,30
> **語域:** L3（工程）
> **實例:** 每故障症狀一份（本檔＝症狀「第 3 步辨識出不來／第 4 步空間確認存不進去」）
>
> **本文件回答**：使用者卡在第 2–4 步時，怎麼在最短路徑上分辨這是「前置閘門沒過、圖真的解不開、比例待人工標定、還是複核清單沒清空」，怎麼緩解，怎麼確認已恢復。
> **本文件不含**：辨識管線的內部演算法與資料流（去 [`lld.md`](../04_design/lld.md)）、`layout_json`／`scene_json` 邊界（去 [`ADR-001`](../03_architecture/adr/ADR-001-layout-json-scene-json-boundary.md)）、公分契約（去 [`ADR-007`](../03_architecture/adr/ADR-007-centimeter-unit-contract.md)）、端點欄位契約（去 [`api_spec.md`](../04_design/api_spec.md)、[`openapi-project-workflow-v1.yaml`](../04_design/openapi-project-workflow-v1.yaml)）、畫面元素與互動（去 [`ui_spec-step3-recognition.md`](../02_ux_ui/ui_spec-step3-recognition.md)、[`ui_spec-step4-space-confirmation.md`](../02_ux_ui/ui_spec-step4-space-confirmation.md)）、存檔衝突與超量（去 [`runbook-workflow-save-conflict-or-oversize.md`](./runbook-workflow-save-conflict-or-oversize.md)，RB-003）。
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

| 症狀 | HTTP／code | 觀察位置 | 佐證 |
| :--- | :--- | :--- | :--- |
| 第 2 步按下一步，紅字「請先勾選確認圖檔內容正確，才能進入下一步。」 | 前端自擋，不發請求 | 瀏覽器 `#upload-error` | `scene_v2.js:1799-1802` |
| 直接呼 API 或舊專案：辨識被擋 | 409 `floorplan_confirmation_required` | API | `main.py:2981-2993`；相容判定 `main.py:2967-2979` |
| 上傳區紅字「Cody 無法辨識這張平面圖：`<例外>`」 | 422 `cody_recognition_failed` | 瀏覽器＋API | `main.py:3018-3033`；`scene_v2.js:1866-1869` |
| 上傳區紅字「DXF 無法解析：`<例外>`」 | 422 `dxf_parse_failed` | 瀏覽器＋API | `main.py:2996-3010` |
| 第 3 步狀態列「辨識完成。現在請在圖上拉兩端，並輸入這一段的實際公分尺寸。」；`issues` 含 `scale_confirmation_required` | 200（**非故障**，是設計要求的人工標定） | 瀏覽器＋`analysis.issues` | `analysis.py:36,501-502,543-544`；`scene_v2.js:650,1860-1862` |
| 第 3 步辨識摘要尾巴多一句「；系統標記 N 間房需人工複核」 | 200 | 瀏覽器 `#recognition-summary` | `scene_v2.js:1854,2935-2943`；`spatial_report.py:170-199` |
| 存檔狀態變「保存失敗」，狀態列紅字「系統標記需人工複核的房間尚未逐一確認，無法將空間確認標為完成；請回到第 4 步處理。」 | 422 `recognition_review_unresolved` | 瀏覽器＋API | `main.py:1815-1827`；`scene_v2.js:1354-1356` |
| 原圖不見 | 409 `floorplan_missing`／410 `floorplan_source_missing` | API | `main.py:1685-1707` |

**3am 陷阱**（三條，全部會誤導判斷）：

1. `analyze` 只把 `TypeError`／`ValueError` 轉成 422（`main.py:3024`），其他例外（cv2、記憶體、ezdxf 內部錯誤）**直接 500**、前端只顯示通用「操作失敗」；而 `dxf_parse_failed` 的 `{exc}` 幾乎永遠是「DXF 中沒有可建立房間的牆體幾何」，因為 `parse_floorplan_with_engine` 的 `except Exception: return None, None`（`scene_service.py:2758,2777-2778`）已先吞掉真因，`main.py:3001-3002` 只看得到 `parsed` 是空的。兩種情況的真因都要照 §4 步驟 4／5 繞過去看。
2. 422 時 `PROJECT_STORE.update_workflow` 還沒被呼叫（`main.py:3036`），所以**辨識失敗不會弄髒下游**；反過來，辨識**成功**會把 `confirmed_floorplan`／`calibration`／`space_confirmation`／`requirements`／`layout_2d`／`white_model_3d`／`realistic_3d` 全部寫成 `null`（`main.py:3039-3063`）——重跑辨識＝下游全部重做。
3. `recognition_review_unresolved` 檢查的是**送上來的 payload**，不是資料庫既有值（`main.py:1815`）。正式前端每次存檔都送整份快照（`scene_v2.js:1213-1227`），所以一旦踩中就是**每次自動保存都失敗**，而且 `saveWorkflowRequest` 會先重試 3 次、退避 180 ms×n（`scene_v2.js:1306-1325`），使用者是延遲約半秒後才看到「保存失敗」。

## 2. Impact（影響）

| 項目 | 內容 |
| :--- | :--- |
| **受影響功能** | 辨識失敗＝第 3 步之後全部無法開始（無 `layout_json` 即無 `scene_json`）；`recognition_review_unresolved` ＝第 4 步之後的**所有**存檔被擋，進度只留在瀏覽器 `localStorage` pending（`scene_v2.js:1294-1302`） |
| **仍可運作** | 第 1、2 步（建案、上傳、換圖）與其他專案；FastAPI 不整體停擺；`scale_confirmation_required` 不阻斷，只是要求人工標定 |
| **受影響使用者** | 單機 Pilot 全部使用者（無多租戶、無分區）；辨識失敗通常只影響該張圖 |
| **嚴重程度判定** | 第 3 步阻斷＝主要交付價值中斷，等同最高嚴重度。**升級門檻、回應時限與覆盤義務本 repo 無明文政策 → 待確認（OPEN-02，承接 [`deployment_and_operations.md`](./deployment_and_operations.md)）** |

## 3. Possible Causes（可能原因）

按發生機率排序：

| # | 原因 | 對應症狀 | 佐證 |
| :--- | :--- | :--- | :--- |
| 1 | 第 2 步沒勾「圖檔內容正確」（或舊專案只有 privacy 形態的相容欄位） | 409 `floorplan_confirmation_required` | `main.py:2967-2993` |
| 2 | 圖檔本身解不開：非真圖、毀損、副檔名對但內容不是 PNG／JPG | 422 `cody_recognition_failed`（訊息 `unsupported_or_corrupt_floorplan_image`） | `vision/image.py:9-13`；`cody_adapter.py:34` |
| 3 | 圖能解、但幾何抽不出可用牆體（掃描歪斜、彩圖、家具線干擾） | 422，或 200 但 `issues` 含 `geometry_missing`／`walls` 為空 | `analysis.py:545-549,656-660` |
| 4 | DXF 沒有可封閉成房間的牆體圖層 | 422 `dxf_parse_failed` | `main.py:3001-3005`；`scene_service.py:2765-2778` |
| 5 | 自動比例信心 < 0.8（OCR 分數，或 `cody_*` 來源的 0.9／0.7 落到門檻下） | `scale_confirmation_required`（**預期行為**，要求兩點標定） | `analysis.py:36,501-502,543-544`；`cody_adapter.py:756,775-776` |
| 6 | 逐房自我評分產生 `review_items`（四種 reason：房名與圖示衝突、幾何信心不足、形狀不規則、邊界無解），而 `space_confirmation.rooms[].confirmed` 未逐一為 true | 422 `recognition_review_unresolved` | `spatial_report.py:170-199`；`main.py:1747-1781` |
| 7 | 非 `TypeError`／`ValueError` 的例外 | 500，無 code | `main.py:3024` |

**背景限制（會影響你能做什麼）**：`README.md` 記載的分割模型融合在本分支**未接線**——`backend/floorplan/models/` 目錄不存在、`floorplan2dxf.py` 全檔無 `_fuse_with_seg`、`seg_infer.py:22,34-45` 雖在但全 repo 無任何 import。辨識品質目前只由 OpenCV／cody 幾何決定，**沒有可調的模型旋鈕**；README 記載的精準 94%／召回 92% 是否仍成立屬 OPEN-25（[`srs.md`](../01_requirements/srs.md) §8）。另比例尺有兩套推導並存（OPEN-28），主線只消費 `derive_door_scale` 的 confidence（`analysis.py:493-544`）。

## 4. Diagnosis（診斷步驟）

伺服器 base URL 為 `http://127.0.0.1:8002`（`README.md:49`）。把 `<PID>` 換成專案 id，逐步照跑，第一個異常的步驟就是分歧點。

```powershell
# 1. 專案現況（辨識結果全在 workflow.recognition 底下；可直接在瀏覽器開）
#    http://127.0.0.1:8002/api/projects/<PID>
curl.exe -s http://127.0.0.1:8002/api/projects/<PID>
#   workflow.floorplan_confirmation.confirmed != true → 原因 1，跳 §5.1

# 2. 原圖還在不在（409 = 沒上傳過，410 = 檔案被刪）
curl.exe -s -o NUL -w "%{http_code}`n" http://127.0.0.1:8002/api/projects/<PID>/floorplan/source
Get-ChildItem D:\RoomPilot-Agent\.runtime\uploads\<PID>

# 3. 重跑辨識，取得真正的 code（這一步不會弄髒 workflow，失敗即中止）
curl.exe -s -X POST http://127.0.0.1:8002/api/projects/<PID>/floorplan/analyze

# 4. 影像失敗 → 離線重跑看完整堆疊與中繼結果（422 訊息只帶一行字串）
.\.venv\Scripts\python.exe -c "from pathlib import Path; from backend.floorplan.vision.analysis import analyze_floorplan_image as a; r=a(Path(r'.runtime/uploads/<PID>/floorplan.png').read_bytes(), filename='floorplan.png'); print('issues', r['issues']); print('scale', r['scale']); print('walls', len(r['walls']), 'review', len(r['spatial_report']['review_items']))"

# 5. DXF 失敗 → 繞過 scene_service 的 except Exception 才看得到真因
.\.venv\Scripts\python.exe -c "from pathlib import Path; from backend.upgrade3d.dxf_parser import parse_dxf_bytes; p=parse_dxf_bytes(Path(r'.runtime/uploads/<PID>/floorplan.dxf').read_bytes(),'upload.dxf'); print({k:(len(v) if isinstance(v,list) else v) for k,v in p.items()})"

# 6. 422 recognition_review_unresolved → 列出到底是哪幾間卡住（回應 body 的 rooms[] 也有同一份）
.\.venv\Scripts\python.exe -c "import json,urllib.request as u; w=json.load(u.urlopen('http://127.0.0.1:8002/api/projects/<PID>'))['project']['workflow']; items=w['recognition']['spatial_report']['review_items']; rooms={str(r.get('id')):r for r in (w.get('space_confirmation') or {}).get('rooms') or []}; print([(i['room_id'], i['reason'], rooms.get(str(i['room_id']),{}).get('confirmed')) for i in items])"
#   confirmed 為 None＝房間 id 已不存在（刪除／合併／切割）視為已處理；為 False 或缺欄位的那幾間就是元凶

# 7. OCR 供應者是否有裝（缺 paddle 會安靜降級成 None，不是故障）
.\.venv\Scripts\python.exe -c "from backend.floorplan.vision.ocr import default_ocr_provider as p; print(p())"
```

## 5. Mitigation（短期緩解）

1. **409 `floorplan_confirmation_required`** → 回第 2 步勾「圖檔內容正確」再按下一步（前端會一併寫入 `floorplan_confirmation.confirmed`，`scene_v2.js:1816-1827`）。舊專案的 privacy 形態欄位由 `main.py:2974-2979` 相容承接，不需手改資料。
2. **422 `cody_recognition_failed`（原因 2）** → 換一張真的 PNG／JPG 重傳；重傳直接覆蓋同名檔（`project_store.py:275-278`），不留歷史。
3. **422（原因 3、4）** → 換路徑而不是調參：有 DXF 就傳 DXF、只有 DXF 解不開就出一張 PNG 走影像路徑。**本分支沒有分割模型可以開**（見 §3 背景限制）。**落到 500（原因 7）** 時唯一線索是 uvicorn 終端機的堆疊（本專案無 log 檔）：貼給 Cody，並用 §4 步驟 4／5 離線重現。
4. **OCR 干擾**（印刷尺寸被誤讀成比例）→ 設 `ROOMPILOT_OCR_DISABLED=1` 後重啟 uvicorn（`main.py:156-160`）。OCR 只是輔助證據，關掉不影響幾何抽取；供應者是 `lru_cache` 單例，**不重啟不生效**（`vision/ocr.py:74-89`）。
5. **`scale_confirmation_required`** → 這不是故障：在第 3 步拖兩個端點、輸入該段實際公分即可（`scene_v2.js:2178-2200`）。注意套用**完全在瀏覽器端**（`scene_v2.js:2094-2172`），不回打伺服器；且只重算 `walls`／`doors`／`windows`／`rooms` 與 `scale`，**`spatial_report` 不重算**（`scene_v2.js:2126-2142,2170-2172`）——所以標定完比例，`review_items` 不會因此消失。
6. **422 `recognition_review_unresolved`** → 用 §4 步驟 6 拿到房間清單，回第 4 步逐間確認（或刪除／合併該房，id 消失即視為人工介入，`main.py:1737-1746`）。**不要**直接改資料庫繞過閘門。若使用者已離開頁面，pending 快照還在 `localStorage`（`roompilot.pending-save.<PID>`），處理完旗標房後重新整理 `/scene` 會重播（`scene_v2.js:1294-1302`）。
## 6. Recovery（恢復確認）

三項全過才算恢復（對應 ACPT-009、ACPT-011、ACPT-013）：

```powershell
# 1. 辨識端點回 200，且 layout_json 有牆
curl.exe -s -X POST http://127.0.0.1:8002/api/projects/<PID>/floorplan/analyze
# 2. 第 4 步閘門不再擋：專案可正常存檔（回 200 並帶新的 revision）
curl.exe -s -o NUL -w "%{http_code}`n" http://127.0.0.1:8002/api/projects/<PID>
# 3. 辨識與複核的守護測試仍綠
.\.venv\Scripts\python.exe -m pytest -q tests/test_floorplan_vision.py tests/test_floorplan_vision_api.py tests/test_recognition_review_wiring.py
```

4. 使用者側：`/scene` 第 3 步摘要不再帶「系統標記 N 間房需人工複核」（或第 4 步已逐間確認），存檔列顯示「已自動保存 · `<專案名>`」（`scene_v2.js:1353`），`localStorage` 的 pending key 已被清掉。**恢復判定無量化基線可比對**（無延遲／成功率指標、無歷史 dashboard），只能以上述布林檢查為準；辨識精準度基準線是否仍成立見 OPEN-25。

## 7. Escalation（升級路徑）

**本專案無 on-call 系統、無升級計時器、無事故追蹤工具**；「管道」一律是直接聯繫該 owner。逾時門檻（例如「緩解 30 分鐘無效即升級」）本 repo 無政策 → 待確認。

| 情況 | 找誰（MOD） | 管道與依據 |
| :--- | :--- | :--- |
| 影像／DXF 解不開、牆門窗抽不出、比例推導錯 | Cody（MOD-FP、MOD-U3D） | 直接聯繫；`TEAM_AI_OWNERSHIP.md:10,23,30` |
| 房型標籤錯、語意管線覆蓋順序可疑 | Django（空間語意）＋ Cody | `TEAM_AI_OWNERSHIP.md:11,24` |
| 端點狀態碼、第 3／4 步 UI、workflow 閘門行為與本檔不符 | Bella（MOD-SRV-API、MOD-WEB） | `TEAM_AI_OWNERSHIP.md:9,21,22` |
| 辨識品質基準線（94%／92% 是否仍成立、測資重跑，OPEN-25） | Ben ＋ Cody | `TEAM_AI_OWNERSHIP.md:15,32` |
| 裁決 OPEN-28（兩套比例邏輯誰是權威）、OPEN-32（一鍵確認繞過閘門是否接受） | 產品 owner ＋ Cody／Bella | [`requirements_tracker.xlsx`](../../VibeCoding_Workflow_Templates/01_requirements/requirements_tracker.xlsx) ②決策沿革 |

事故後覆盤：**本 repo 無覆盤流程與 postmortem 範本**，目前僅能把結論寫回 `requirements_tracker.xlsx` ②決策沿革與相關 ADR。是否建立正式覆盤義務 → 待確認。

## 8. 追溯

| 項目 | ID／文件 |
| :--- | :--- |
| Runbook 編號 | **RB-006**（[`srs.md`](../01_requirements/srs.md) §9.2，S3 與 S4 列；索引見 [`00-registry.md`](../00-registry.md)） |
| 對應告警 | 無。本專案無監控與告警來源，觸發僅靠使用者回報或 §1 的畫面／API 回應 |
| 上游需求 | DEC-003、DEC-004、DEC-018；FR-007、FR-010–016（次要：FR-005、FR-006、FR-021、FR-022）；NFR-017 |
| 驗收與情境 | ACPT-006、ACPT-009–014；SCN-006–011、SCN-013（[`prd.md`](../01_requirements/prd.md) §邊界場景「辨識信心不足」） |
| 使用案例 | UC-001（[`srs.md`](../01_requirements/srs.md) §6，A1–A5 例外路徑即本檔症狀） |
| 測試 | TC-006、TC-009–014（[`test_plan.md`](../05_qa/test_plan.md)）；現有守護測試 `tests/test_recognition_review_wiring.py:63-88` |
| 架構決策 | [`ADR-001`](../03_architecture/adr/ADR-001-layout-json-scene-json-boundary.md)（辨識止於 `layout_json`）、[`ADR-007`](../03_architecture/adr/ADR-007-centimeter-unit-contract.md)、[`sad.md`](../03_architecture/sad.md) |
| 影響模組 | MOD-FP、MOD-U3D（Cody）；MOD-SRV-API、MOD-WEB（Bella）；MOD-OPS |
| 相關 runbook | [RB-003](./runbook-workflow-save-conflict-or-oversize.md)（同樣表現為存檔失敗，但 code 是 409／413 不是 422）、[RB-009](./runbook-runtime-storage-growth.md)（`uploads/` 成長） |
| 待確認 | **OPEN-25**（分割模型融合未接線、94%／92% 基準線是否成立）、**OPEN-28**（兩套比例邏輯誰是權威）、**OPEN-32**（`confirmAllRooms` 不排除旗標房，使 422 在正常操作路徑不會觸發，`scene_v2.js:3037-3050` vs `scene_recognition_review.js:9-11` 註解）。**本檔新增**：①`analyze` 只轉譯 `TypeError`／`ValueError`，其餘例外落 500 且無 code，是否補齊分類待 Bella 裁決；②手動兩點標定不重算 `spatial_report`，其 `*_cm` 尺寸與 `review_items` 停留在辨識當下的值（`scene_v2.js:2126-2142`），是否為刻意取捨待 Cody／Bella 確認；③升級門檻、回應時限與覆盤義務無政策 |
