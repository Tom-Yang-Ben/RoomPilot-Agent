# 工程估價與初步排程契約

Last updated: 2026-08-14

第 8 步「產出設計提案 PDF 與工程估價」按鈕的**第二份輸出**：一份
`estimate_and_schedule.xlsx`，兩張工作表（工程估價、初步排程）。與交付提案 PDF 由
同一次 POST 產出，不是另一顆按鈕。

公開實作只保留計算與文件產出，不包含獨立 `/api/v1` router、SQLite 版本鎖定或
第二套 `/engineering` 前端頁。

## 路徑

| 環節 | 位置 |
|---|---|
| 接縫 | `backend/server/engineering_report.py` `build_engineering_estimate()` |
| 觸發 | `POST /api/projects/{id}/delivery-proposal`（PDF 產出成功之後） |
| 下載 | `GET /api/projects/{id}/delivery-proposal/xlsx` |
| 紀錄 | `workflow.delivery_proposal.engineering`（只存檔名與統計，不存內容） |
| 檔案 | `<runtime>/manuals/<project_id>/<revision>/<package_id>/`，與 PDF 同一棵目錄 |
| 計算 | `backend/engineering/services/`（quantity → RAG → rules → cost → schedule → narrative） |
| 資料 | `knowledge/*.json`（工項、材料對照、單價、產能） |

整條管線 deterministic：沒有 LLM、沒有向量資料庫、沒有網路。`NoopSemanticRetriever`
永遠回空陣列，`advanced_rag.py` 實際上是查 `knowledge/` 的結構化對照表。

## 輸入對應（workflow → ProjectSnapshot）

轉換在 `backend/engineering/adapters/workflow_snapshot.py`。UI 欄位改名時只改這個檔，
`contracts.py` 的工程契約不跟著變。

| ProjectSnapshot | 來源 |
|---|---|
| `rooms[]` | `workflow.space_confirmation.rooms[]`（需有 `polygon_cm`，優先取 `confirmed`） |
| `geometry.length_m` / `width_m` | `polygon_cm` 的外接矩形 ÷100 |
| `geometry.height_m` | `confirmed_floorplan.floorplan.room_height_cm`，缺則 270 cm |
| `geometry.opening_area_m2` | `space_confirmation.structures.doors/windows` 段長×高（缺高度用 210/120 cm） |
| `materials[]` | `requirements.roomRequirementModel.roomRequirements[room_id].surfaces` 的 floor/wallDefault/ceiling；沒有逐房選擇才退回 `requirements.finishes` 的全屋選項（會記進 assumptions） |
| `furniture[]` | `layout_2d.furniture[]`，依 `roomId` 分組並轉成房間座標 |
| `renders[]` | `proposal_review.jobs[]`（只影響 HTML 報告插圖，XLSX 不用） |

**沒有的資料**：水電點位（`mep_points` 恆為 `[]`，本產品沒有點位編輯器），因此
「已有既有點位可用」的判斷一律成立不了，水電只會列出需求數量。

**刻意造的資料**：本分支沒有版本鎖定流程，`build_engineering_estimate()` 直接把
snapshot 標成 `designer_confirmed`／`confirmed_by="step8_delivery_proposal"`——按下按鈕
即視為設計師確認當下配置。

## 材料關鍵字對照是校準點，不是死參數

`knowledge/material_work_mappings.json` 用**子字串比對**把材料對到工項：
`keyword.lower() in f"{material.name} {description}".lower()`。

**比對的不是 surface_id，是型錄的受控詞彙。** 問卷存的是型錄 ID
（`wall_json_ambientcg_wall_paint_concrete036`），adapter 會先用
`backend/catalog/data/surface_catalog.json` 換成 `category` + `material_group`
（`paint 塗料牆`、`wood_wall 木質牆板`、`wood_tile 木紋磚`…）再交給比對。

直接拿 ID 比對會出事：`wall_json_ambientcg_wall_wood_wall_paintedwood007c` 是木質牆板，
但 ID 裡有 `paint`，會被算成油漆——實測 NT$134,946 的木作被報成 NT$21,036 的油漆，
低估 3 倍以上，而且外觀完全正常（有列、有價、狀態 priced）。

改對照表前先確認**同一個材料不會命中多個 mapping**：那會讓同一面牆被計價兩次。
新增型錄類別時，這裡要跟著校準。

## 對不到工項的材料會列出來，不會消失

材料查無對照時，`advanced_rag.py` 會補一列 `UNMAPPED-<PART>` 工項（無單價，
`status=pending_quote`）。因此 `pending_quote_count` 會增加、`estimated_total` 依
`cost.py` 的規則變成 `None`、XLSX 明細看得到「查無對應工項，未計價」那一行。

沒有這一段的話，整個工種會靜靜從估價單消失，而封面照樣印「待詢價工項 0」與一個
看起來完整的總價——那比報錯危險得多。

**目前已知對不到的**：天花的 `wood-veneer`、`exposed-concrete`、`micro-cement`
（面材型錄沒有 ceiling 用途的項目），以及 `ceilingStyle`（flat／cove）完全沒進比對，
所以 `CEILING-GYPSUM`（平釘天花，示範單價 2,030/m²，天花最大宗）與
`CEILING-LIGHT-TROUGH`（燈槽）目前不可能被命中。要補這些工項是**工程判斷**，
請由懂施工的人決定對照關係再寫進 `material_work_mappings.json`。

## 金額的性質

`ROOMPILOT_DEMO_MODE` 預設 `true`，`knowledge/price_records.json` 的單價全部是
`region=DEMO_ONLY` 的合成示範值。XLSX 表頭第 5 列與前端狀態文字都會標示。

要換成真實單價：照 `knowledge/PRICE_AND_PRODUCTIVITY_POLICY.md` 填
`knowledge/production_templates/` 三個範本，並設 `ROOMPILOT_DEMO_MODE=false`。
切過去之後缺同地區有效單價的工項會變 `pending_quote`、小計為 `null`——那是設計行為，
不是壞掉；系統不補猜價格。

環境變數：`ROOMPILOT_DEMO_MODE`（預設 true）、`ROOMPILOT_DEFAULT_REGION`（預設「新北市」）、
`ROOMPILOT_KNOWLEDGE_DIR`（預設 `knowledge/`）。demo 模式下下載檔名會帶 `DEMO-`。

XLSX 的字串儲存格會擋掉 `=` 開頭被存成公式（`documents.py` 把 data_type 拉回 `s`）：
房間 id 與材料名稱是前端寫的，這份檔要寄給屋主與工班，不能在對方的 Excel 裡執行。

## 與家具報價的分工

這份 XLSX 算的是**施工工項**（地坪、油漆、天花、水電點位）。家具本身的錢在成果包
JSON 的 `budget_report`，來自型錄單價（見 `main.py` 的 `_delivery_furniture_lines`）。
兩者不重疊，也不互相取代。

## 失敗行為

估價是 PDF 的附掛品：`build_engineering_estimate()` 吞掉所有例外並回
`{"status": "skipped", "reason": ...}`，PDF 照常輸出，前端 XLSX 連結維持隱藏，
狀態文字會說明原因。常見的 skipped 原因是 `WORKFLOW_HAS_NO_ROOMS`（專案還沒走完
第 4 步）與 openpyxl 未安裝（`requirements-delivery.txt`）。
