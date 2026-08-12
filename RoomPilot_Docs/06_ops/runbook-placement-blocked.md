# Runbook：第 6 步待處理家具清不掉 (Runbook - Placement Blocked) - RoomPilot

> **版本：** v1.0 ｜ **更新：** 2026-08-12 ｜ **狀態：** 草稿（待 owner 核准）
> **Owner:** MOD-ENG owner（Ancai，幾何判定）＋ MOD-AGT owner（Yen，修復迴圈）＋ MOD-SRV-SCENE／MOD-WEB owner（Bella，端點與前端硬閘）
> **語域:** L3（工程）——直接寫端點、欄位、常數與錯誤字串
> **實例:** 每故障症狀一份（`runbook-placement-blocked.md`，編號 RB-007）
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、工作樹日期 2026-08-12；行號對應該版

本文件回答：第 6 步「待處理」清單清不掉、`placement.failed[]`／`unavailable_types[]` 有殘留、無法進第 7 步時，怎麼在最短時間內判斷是七段檢查的哪一段擋住、用哪顆按鈕或哪支端點解掉。
本文件**不含**：擺位演算法與雙路徑設計理由（見 [ADR-003](../03_architecture/adr/ADR-003-dual-path-shapely-raster-engine.md)、[lld](../04_design/lld.md)）、型錄 DB 不可用（見 [RB-001](runbook-catalog-db-unavailable.md)）、GLB 資產缺失（見 [RB-008](runbook-glb-asset-missing.md)）、門窗辨識錯誤（見 [RB-006](runbook-recognition-failed-or-review-blocked.md)）、存檔衝突（見 [RB-003](runbook-workflow-save-conflict-or-oversize.md)）。

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

| 現象 | 使用者看到的字串 | 佐證 |
| :--- | :--- | :--- |
| 側欄待處理計數 > 0、家具列標「待處理」而非「合法」 | 「N 件因碰撞、淨空或房間尺寸無法放入」 | `scene_v2.js:11444-11470` |
| 「確認家具配置」鈕反灰 | title「尚有 N 件家具位置不合法，請先修正。」 | `scene_v2.js:3830-3839` |
| 硬按確認鈕被擋 | 「目前還有 N 件家具位置不合法，請先從 2D 待處理清單定位修正。」；生成當下另有「系統仍有 N 件家具無法合法放置…」＋狀態列「配置尚未通過門窗淨空、房間邊界與家具碰撞檢查。」 | `scene_v2.js:13932-13939`、`:12741-12750` |
| 後端載荷 | `scene_json.placement.failed[]` 非空；`placement.unavailable_types[]` 列出完全找不到型號的類型 | `scene_service.py:3074-3087` |

> **無告警來源。** 本 repo 無監控、無告警規則、無 dashboard、無 on-call 輪值；本症狀只能靠使用者回報或上述畫面錯誤文案發現，不要去找不存在的 alert 名稱。

## 2. Impact（影響）

| 項目 | 內容 |
| :--- | :--- |
| **受影響功能** | 第 6 步無法完成 → 第 7 步方案鎖定與第 8 步生圖全部進不去（硬閘在 `confirmWhiteModel()`，`scene_v2.js:13924-13954`） |
| **資料風險／範圍** | 無資料遺失：失敗件被標記而非丟棄，`user_specified`／`user_required`／`position_locked` 受保護不被換小或移除（`scene_service.py:2953-2962`；`agent/place.py:222-233`）。影響限單一專案、單一使用者（單機 loopback 部署，見 [ADR-012](../03_architecture/adr/ADR-012-pilot-loopback-deployment.md)） |
| **嚴重程度判定** | 待確認：本專案無 incident 分級與 SLA 定義，程式碼看不出目標值 |

## 3. Possible Causes（可能原因）

按發生機率排序：

1. **房間真的塞不下**——引擎七段檢查任一段命中；最常見是門前 75 cm 通行淨空與有櫃家具正面 50 cm 開合空間互吃（`engine/constraints.py:21`；`engine/clearance.py:24,33-43`）。
2. **成組副件失去主件**——茶几／床頭櫃／餐椅／辦公椅只准貼各自主件的成組候選，主件不在或旁邊沒位就直接標失敗（`scene_service.py:2496-2517,2606-2613`）。
3. **床／沙發／餐桌或使用者鎖定件放不下**——這兩類絕不靜默移除，只 `escalate` 等使用者處理；整輪無動作修復迴圈即停（`agent/place.py:222-233,247-259,304-305`；`agent/knowledge.py:70-74`）。
4. **型錄沒有這個類型的可用型號**——進 `unavailable_types[]`，不是幾何問題（`scene_service.py:495-509,620,634,2917-2933`）；型錄整體不可用先走 [RB-001](runbook-catalog-db-unavailable.md)。
5. **非幾何來源**——GLB 載不出來（同一份清單也收模型失敗件，`scene_viewer.js:4281-4320`，見 [RB-008](runbook-glb-asset-missing.md)）；門窗辨識錯誤讓淨空帶吃光整面牆（見 [RB-006](runbook-recognition-failed-or-review-blocked.md)）。

## 4. Diagnosis（診斷步驟）

**先問一句：是幾何失敗還是模型失敗？** 待處理清單同時收兩類，修法完全不同。畫面入口 <http://127.0.0.1:8002/scene>。

```bash
# 0. 服務活著嗎；順手確認型錄來源（available=false → 轉 RB-001）
curl -s http://127.0.0.1:8002/api/catalog/status
# 1. 取專案快照（PROJECT_ID 從網址列或使用者回報取得）
curl -s http://127.0.0.1:8002/api/projects/$PROJECT_ID > /tmp/rp.json
# 2. 幾何失敗清單（reason 決定下一步）
python -c "import json;s=json.load(open('/tmp/rp.json'))['project']['workflow']['white_model_3d']['sceneData'];[print(f['name'],'|',f['type'],'|',f['reason']) for f in s['placement']['failed']];print('unavailable:',s['placement']['unavailable_types'])"
# 3. 模型失敗清單（有輸出＝GLB 問題，轉 RB-008，別在幾何裡繼續找）
python -c "import json;print(json.load(open('/tmp/rp.json'))['project']['workflow']['white_model_3d']['diagnostics']['failedFurniture'])"
# 4. 修復迴圈做過什麼（換小／移除／升級的中文逐筆紀錄）
python -c "import json;print(json.dumps(json.load(open('/tmp/rp.json'))['project']['workflow']['white_model_3d']['sceneData'].get('placement_resolution_report',[]),ensure_ascii=False,indent=1))"
# 5. 單件複驗：某件擺在指定座標是否合法（回 {ok, reason}）
curl -s -X POST http://127.0.0.1:8002/api/scene/validate -H 'Content-Type: application/json' \
  -d '{"floorplan_editor":{...},"item":{...},"others":[...]}'
# 6. 整屋只驗不排（絕不改座標）——重現第 6→7 步的最終閘
curl -s -X POST http://127.0.0.1:8002/api/scene/layout -H 'Content-Type: application/json' \
  -d '{"validate_only":true,"floorplan_editor":{...},"scene_objects":[...]}'
```

端點定義：`main.py:3144-3146`（型錄狀態）、`main.py:1800-1803`（專案快照）、`main.py:3998-4009`（單件驗證）、`main.py:3647-3672`（重排／只驗）；快照鍵位 `scene_v2.js:1258-1264`。
**第 2 步拿到的 `reason` 對照下表判斷是哪一段擋住**（七段固定順序，只回最先命中者；`engine/clearance.py:118-143`）：

| 段 | 檢查 | 中文理由（原文） | 佐證 |
| :--- | :--- | :--- | :--- |
| 1 | 出界 | 物件超出空間範圍 | `engine/geometry.py:69-70` |
| 2 | 穿牆 | 與牆體穿透 | `engine/geometry.py:71-72` |
| 3 | 本體重疊 | 與「X」重疊 | `engine/geometry.py:73-75` |
| 4 | 淨空撞牆 | 「X」的開合空間被牆體阻擋 | `engine/clearance.py:99-102` |
| 5 | 淨空撞他人本體 | 「X」的開合空間與「Y」衝突 | `engine/clearance.py:107-109` |
| 6 | 淨空互撞 | 「X」與「Y」的開合空間互相衝突 | `engine/clearance.py:110-113` |
| 7 | 反向（我壓到別人淨空） | 擋住了「Y」的開合空間 | `engine/clearance.py:134-141` |

**不是七段、而是擺位前置或整屋覆核擋住的理由**（看到這些不要去追引擎）：

| 理由（原文） | 意義 | 佐證 |
| :--- | :--- | :--- |
| 休閒椅僅能擺在沙發左前或右前，目前沒有合法位置。 | 成組嚴格模式，沙發旁無位 | `scene_service.py:2606-2608` |
| 需與…成組擺放，主件不在或旁邊沒有合法位置。 | 副件失去主件 | `scene_service.py:2609-2613` |
| 找不到落在房間形狀內的合法位置 | 候選點掃完＋引擎後援皆失敗 | `scene_service.py:2630-2653` |
| 位置超出房間範圍,請移回房內再確認。／壓到門前動線、陽台出入口或窗前淨空,請讓開後再確認。 | `validate_only` 整屋覆核（邊界含 12 cm 容差、柵格覆核） | `scene_service.py:2340-2365` |
| 落地窗是陽台出入動線，家具不可擋在前方。／家具不可遮擋窗戶前方採光淨空。 | 拖曳落點驗證（shapely 路徑） | `scene_service.py:2132-2147` |
| GLB 載入失敗…／資料庫尚未提供 GLB | 模型問題，非幾何 | `scene_viewer.js:4308-4314` |

**淨空常數速查**（改不了，只能讓開）：門前 75 cm、窗前帶 40 cm、窗台門檻 90 cm（家具高 ≥ 才受窗帶限制）（`engine/constraints.py:21-23,35-37`）；有櫃家具正面 50 cm（`engine/clearance.py:24,33-43`）；背牆 5 cm（`engine/rules.py:15`）；柵格解析度 5 cm、單軸上限 1200 格、牆線描粗 12 cm（`engine/raster.py:17-19`）。

> **待確認：** 窗前淨空在兩條路徑數字不同——柵格路徑 40 cm（`engine/constraints.py:22`），拖曳／落地窗驗證走 shapely 路徑用 70 cm 預設與 75 cm 出入口帶（`scene_service.py:1318-1322,2132-2147`）。診斷時可能出現「2D 拖曳說不合法、自動擺位卻放得下」的矛盾。歸屬雙路徑分歧 OPEN-21／OPEN-22（見 [srs](../01_requirements/srs.md) §8）。

## 5. Mitigation（短期緩解）

依序嘗試，每一步都在第 6 步待處理清單上直接操作（`scene_v2.js:11472-11502`）：

1. **「只重排此家具」**（只重算該件座標，不動其他家具；失敗把原因寫回同一列，`scene_v2.js:11530-11558`）→ **「更換較小款」**（同型換更小 footprint，鏈嚴格遞減必收斂，`agent/place.py:240-272`）。
2. **「保留全部並重新擺位」**——整房 `POST /api/scene/layout` 帶 `placement_room_id` 重排，不影響其他房（`scene_v2.js:11632-11660`；`main.py:3673-3679`）。
3. **「定位」＋手動拖曳**——落點即時打 `/api/scene/validate`，合法即 `position_locked=true` 不再被重排沖掉（`scene_v2.js:5430,5497`）。GLB 失敗列只會出現「更換家具」，轉 [RB-008](runbook-glb-asset-missing.md)（`scene_v2.js:11481-11485`）。
4. **回上游改條件**——回第 5 步移除該需求品項，或回第 4 步修正門窗位置（門前 75 cm 帶是最常吃掉整面牆的來源）。

> **沒有旁路。** 本 repo 無 feature flag、無 `force` 參數、無管理者略過硬閘的機制；`deferred`（暫緩）只認舊版流程留下的紀錄，新版 UI 不再產生（`scene_v2.js:11084-11090,11508-11512`）。唯一例外是逐房 A/B 合成的 `strictSelectedFurniture` 路徑，它不硬擋但仍把失敗件留在待處理清單（`scene_v2.js:12752-12757`）。

## 6. Recovery（恢復確認）

1. 待處理計數歸 0、`#confirm-white-model` 解除反灰（`scene_v2.js:3830-3839`）。
2. 按「確認家具配置」須連過三道閘：blocking 為 0、`visibleFurnitureCount > 0`、`failedFurniture` 為空（`scene_v2.js:13932-13954`）。
3. 最終 `validate_only:true` 整屋覆核回來後，所有 `scene_objects` 無 `placement_failed`（`scene_v2.js:13957-13966`）。此旗標必須存在——少了它伺服器會對整屋聯集邊界重排，把電視櫃推到陽台（`scene_v2.js:13961-13965`）。
4. 重跑 §4 第 2 步確認 `placement.failed[]` 為空；核對受保護件仍在清單且座標未被動（`scene_service.py:2953-2962`）。
5. 若靠移除品項收場，把 `placement_resolution_report[]` 的中文逐筆訊息唸給使用者聽，不要靜默（`agent/place.py:174-178`）。

## 7. Escalation（升級路徑）

無 on-call 系統與輪值；以團隊既有溝通管道聯絡，責任分工見 [`docs/TEAM_AI_OWNERSHIP.md`](../../docs/TEAM_AI_OWNERSHIP.md)。

| 情況 | 找誰（MOD／owner） | 交付什麼 |
| :--- | :--- | :--- |
| 七段理由與畫面不符、明顯放得下卻判失敗 | MOD-ENG（Ancai）／`backend/engine/` | `placement.failed[]` 原文 ＋ `floorplan_editor` ＋ 該件 `size_cm`／`rotation_y_deg` |
| 換小／移除／升級行為不對，或保護欄位失效 | MOD-AGT（Yen）／`backend/agent/place.py` | `placement_resolution_report[]` 全文 |
| 硬閘、待處理清單、重排按鈕行為異常 | MOD-WEB／MOD-SRV-SCENE（Bella） | 瀏覽器 console ＋ 失敗的 `/api/scene/layout` 請求載荷 |
| `unavailable_types[]` 集中在同一類型，或型錄查無型號／無 GLB | MOD-CAT／MOD-SQL（Kai） | 先跑 [RB-001](runbook-catalog-db-unavailable.md)／[RB-008](runbook-glb-asset-missing.md) 的結果 |
| 門窗位置錯誤導致整房無合法位置 | MOD-FP（Cody） | 第 3–4 步 `layout_json` 與截圖，轉 [RB-006](runbook-recognition-failed-or-review-blocked.md) |

事故覆盤：待確認——本 repo 無 postmortem 模板與時限政策，程式碼看不出答案。

## 8. 追溯

| 項目 | ID／連結 |
| :--- | :--- |
| Runbook 編號 | RB-007 |
| 對應告警 | 無告警來源（本 repo 無監控／告警／on-call 輪值）；靠使用者回報與畫面錯誤文案 |
| 上游需求 | FR-034、FR-035、FR-037（另涉 FR-024、FR-030、FR-032、FR-033）；NFR-015、NFR-016 |
| 驗收條件 | ACPT-031、ACPT-032、ACPT-034；使用者場景 SCN-022（見 [prd](../01_requirements/prd.md)） |
| 決策 | DEC-008；[ADR-002](../03_architecture/adr/ADR-002-engine-sole-geometry-authority.md)、[ADR-003](../03_architecture/adr/ADR-003-dual-path-shapely-raster-engine.md) |
| 模組 | MOD-ENG、MOD-AGT、MOD-SRV-SCENE、MOD-WEB（見 [srs](../01_requirements/srs.md) §2.4、§2.7、§9.2 S6 列） |
| 相鄰 runbook | RB-001、RB-006、RB-008；存檔受阻另見 RB-003 |
| 待確認 | OPEN-21、OPEN-22（雙路徑窗前淨空 40／70／75 cm 不一致）；嚴重程度分級、SLA 與覆盤政策未定 |
| 上下游文件 | [deployment_and_operations](deployment_and_operations.md)、[srs](../01_requirements/srs.md)、[ui_spec-step6](../02_ux_ui/ui_spec-step6-layout-2d.md)、[test_plan](../05_qa/test_plan.md) |
