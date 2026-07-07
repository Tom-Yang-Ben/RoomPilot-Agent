# PROJECT_CONTEXT

最後更新：2026-07-07

## 專題目標

本專題主線是：

`平面圖 + 使用者需求 + 風格條件 + 既有 GLB 家具資料庫 -> 自動配置 -> 網頁展示 3D 室內場景`

這不是「直接生成全新 3D 家具模型」的專題。  
目前方向是用既有家具資料庫做風格化挑選、配置與展示。

## 先讀這份時要知道的事

1. 使用者目前負責的是「風格系統 + 家具資料庫 + LLM 溝通 + 網頁展示」。
2. 風格工作不是只寫 prompt，而是把風格規則整理成 LLM 能理解、能對應家具與空間的結構化資料。
3. UI 以中文為主，3D 檢視要清楚標示 XYZ 正負方向。
4. 如果修改了專題方向、重要功能、環境或資料結構，要同步更新本檔或對應 `docs/` 子文件。
5. TripoSR 不是目前主線，只能視為嘗試過但品質不足的方案，不要當成既定解法。

## 使用者教學規則

當使用者是在問「怎麼做」或要你帶著操作時，先說明：

1. 接下來要做什麼
2. 為什麼要這樣做
3. 做完會得到什麼

等使用者回「好」之後，再給指令、程式碼或步驟。

如果使用者是直接要求你修改專案、整理文件、改資料、改頁面，則直接動手做，不需要停下來上課。

## 文件入口

請先依主題查看對應文件，不要再把所有細節重新塞回同一份交接檔：

1. [專題總覽](D:/產業新兵計畫/期末專題/test_furniture/docs/PROJECT_OVERVIEW.md)
2. [Web UI 狀態](D:/產業新兵計畫/期末專題/test_furniture/docs/WEB_UI_STATUS.md)
3. [風格資料狀態](D:/產業新兵計畫/期末專題/test_furniture/docs/STYLE_DATA_STATUS.md)
4. [Scene 生成系統狀態](D:/產業新兵計畫/期末專題/test_furniture/docs/SCENE_SYSTEM_STATUS.md)
5. [3D / GLB 管線狀態](D:/產業新兵計畫/期末專題/test_furniture/docs/MODEL_PIPELINE_STATUS.md)
6. [AI Agent JSON Schema v1](D:/產業新兵計畫/期末專題/test_furniture/docs/AI_AGENT_JSON_SCHEMA_V1.md)

補充參考：

1. [網站規格草稿](D:/產業新兵計畫/期末專題/test_furniture/docs/website_spec_12style_2026-07-03.md)
2. [專題範圍釐清](D:/產業新兵計畫/期末專題/test_furniture/docs/project_scope_clarification_2026-07-03.md)
3. [風格進度交接](D:/產業新兵計畫/期末專題/test_furniture/docs/style_progress_handoff_2026-07-03.md)
4. [網站 README](D:/產業新兵計畫/期末專題/test_furniture/README.md)

## 目前快照

1. 家具主資料：`sf3d/metadata/ikea_furniture_style_database.json`
2. 目前網站主程式：`web_fastapi/main.py`
3. 前端頁面：
   - `/` 首頁
   - `/styles` 12 種風格展示
   - `/library` 家具資料庫與 3D 檢視
   - `/scene` 固定風格生成家具與 3D 場景展示
4. 目前資料庫已補齊可用 GLB，`missing_model_count = 0`
5. `/scene` 已正式接入 `furniture_engine/`，支援後端擺位、替換、移除、新增與重排
6. `/scene` 的改版前版本 A 已備份於 `version_snapshots/scene_version_A_20260706/`

## 最近重要決策

1. 風格分類已從寬鬆關鍵字匹配，收斂成規則化判斷，避免高彩度、童趣圖案、造型配件被誤分到極簡風系。
2. `/styles` 頁面聚焦在風格本身，不再混入右側家具分組清單。
3. `/styles` 主視覺改成橫向圖像優先，並用圖內標註替代大段覆蓋文字。
4. `/library` 已改成全中文資料卡，支援風格、類型篩選與即時 3D 檢視。
5. `/scene` 目前走「固定房間 + 固定風格 + 家具挑選 + 直接生成 3D」流程，使用者不直接接觸 JSON。
6. `/scene` 已改成後端主導的家具配置，不再只靠前端簡化座標重排。
7. DXF 目前已能解析牆線、門線、窗線並建立 3D 牆體，但不規則房間的精準避障仍未完成。
8. 首頁、風格頁、資料庫頁、場景頁已統一成 RoomPilot 導覽與黑底發光背景語言。
9. 文件已持續拆到 `docs/`；今後若只是子系統更新，請直接更新子文件。
10. 已新增 `docs/AI_AGENT_JSON_SCHEMA_V1.md`，用來定義多人協作時給 AI agent 的標準 JSON 格式，避免把外部交換格式和目前 `/scene` 內部資料流混在一起。

## 2026-07-05 至 2026-07-06 重點整理

1. 首頁已移除舊版小型結果卡，改成 RoomPilot 風格 hero、功能列與流程卡互動。
2. `/styles` 已補齊 12 種風格的牆面推薦、地板推薦、推薦搭配組合，並持續校正各風格圖與標註位置。
3. `/library` 每頁改為 21 筆，分頁改為前 5 頁與最後 3 頁，家具卡縮圖改為優先使用 GLB 即時預覽。
4. `/scene` 已收斂成上半部條件設定、下半部 3D 結果的操作流程，次要條件收進 accordion。
5. `/scene` 已加入隨機換風格、隨機換家具、替換、移除、新增家具、整組重排、視角切換與牆面自動淡出。
6. 木地板、磁磚、大理石、微水泥等牆地預覽已改為程式生成紋理，先提供可辨識材質感。
7. `furniture_engine/` 已正式接進 `/api/scene/generate` 與 `/api/scene/mutate`，開始承擔擺位與碰撞邏輯。
8. `/scene` 已取消固定 1/2 內部捲動版面，改成上方下拉式條件設定、下方直接 3D 顯示；改版前版本已另存為 version A。

## 接手原則

1. 先看本檔，再依需求打開對應 `docs/` 文件。
2. 如果只是某個子系統有更新，優先更新對應子文件，不要把所有細節重新堆回本檔。
3. 若 `docs/` 某份文件又開始失控變長，就繼續拆分，不要回退成單一巨型交接檔。
## 2026-07-07 Current UI Baseline

非 3D 網站呈現以目前 `web_fastapi/static/` 版本為主；後續 merge 新流程時，優先保留目前首頁、風格頁、家具資料庫頁的 UI 呈現，只接入 `/scene`、DXF、LLM JSON、家具配置與材質流程。

詳細交接請看：`docs/CURRENT_UI_BASELINE_2026-07-07.md`
