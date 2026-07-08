## 2026-07-07 Codex 準則檔

- 根目錄新增 `CODEX_PROJECT_RULES.md`，提供 Codex 使用前置規則與分支準則。
- 使用 Codex 前，先讀 `PROJECT_CONTEXT.md`，再讀 `CODEX_PROJECT_RULES.md`。
- 歷史基準檔：`D:/產業新兵計畫/期末專題/test_furniture/PROJECT_CONTEXT.md`。
- 分支原則：只動 `bella`，其他分支僅限唯讀檢查，除非使用者另有明確要求。

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
## 2026-07-07 External Furniture Zip Import

- 本次在 `bella` 分支新增外部家具/家電 zip 索引流程，來源為使用者指定的 Downloads zip 檔。
- 大型 zip 不整包解壓進 repo；改以 `scripts/index_external_zip_catalog.py` 讀取 zip 目錄並輸出 `roompilot/catalog/data/external_furniture_import_index.json`。
- 目前索引結果：38 個來源 zip、5,469 筆 GLB，依專案正式 12 風格分配，並補上繁體中文分類、尺寸預估、顏色/材質、來源 zip 與 zip 內路徑。
- `roompilot/server/main.py` 會把外部索引併入 `/api/site-data`，並提供 `/api/external-furniture/{furniture_id}/model` 依需求從 zip 串流單一 GLB。
- `/library` 已能看到外部匯入筆數、繁體中文類型篩選、繁中卡片欄位與外部 GLB 模型預覽。
- 這次沒有修改 3D 生成流程與拖曳邏輯；外部 GLB 僅作為資料庫與前端檢視來源。
- 後續如果要讓外部 zip 資料進一步參與自動配置，需要再做「尺寸可信度校正、家具角色規則細化、放置限制與 clearance 規則補齊」。
## 2026-07-08 Unified Furniture Catalog

- 家具資料最終不再分「內建 IKEA」與「外部 zip」兩個前端資料庫；`/api/site-data` 先在 server 合併，再提供單一 `furniture` 清單給 `/library`、`/styles`、`/scene`。
- 合併規則在 `roompilot/server/main.py`：同款同色以標準化名稱、尺寸、顏色變體 key 合併；同款不同色仍保留為不同家具，避免使用者少掉顏色選項。
- `style_candidates` 會合併同款所有來源的候選風格，分數取較高者並保留理由；`primary_style` 以合併後最高分為準。
- 新增規則補分：白色/低彩度/簡單線條/收納長凳類型補回北歐、無印簡約、北歐現代、現代候選，避免兒童家具或 novelty 舊標籤壓掉主要風格。
- 前端公開資料不暴露 internal/external alias；模型 URL 統一使用 `/api/furniture/{furniture_id}/model`，server 內部自行從合併 alias 找可用 GLB。
- 同款家具模型載入優先使用可正常讀取的 zip 匯入 GLB，再回退到內建 dataset GLB；內建 GLB 若 parse 失敗會被跳過，避免壞檔造成 3D 預覽失敗。
## 2026-07-08 Floor Surface Catalog Expansion

- 使用 `C:/Users/user/Downloads/drive-download-20260706T123534Z-3-001.zip` 匯入地板素材到 `roompilot/server/static/surface_assets/_import_all/`。
- 重新產生 `roompilot/catalog/data/surface_catalog.json`，牆面維持程式生成，不再把地板材質混入牆面。
- 地板素材總數 299 筆：木地板/木質素材 60、木紋磚 146、磁磚/石紋地坪 93。
- 每筆 surface 都有 `category`、`usage: ["floor"]`、`suitable_styles`、`texture_url`、`preview_url`、`style_notes_zh`，並合併第二包 JSON 的 `source_material_id`、`source_material_family`、`source_license_status`、`source_product_url`、`source_size`。
- 12 種風格都已建立 `style_surface_profiles[style_id].floor_surface_ids`，讓 `/styles` 與 `/scene` 可依風格優先顯示符合的地板 pool。
- 新增 `scripts/generate_surface_catalog_from_import.py`，之後若更新地板 zip，可重跑此腳本重建 catalog。

## 2026-07-08 Scene Surface Sync And Continuous Tiling

- `/scene` 的牆面選項維持程式生成牆面，不再從地板 catalog 套用圖片材質，避免牆面與地板材質混用。
- `/scene` 的地板選項使用 `surface_catalog.json` 的真材質，viewer 會依房間尺寸與材質類型計算 repeat，讓木紋、木紋磚、磁磚連續鋪滿地面，而不是單張圖被拉伸。
- 使用者在 3D 場景生成後切換牆面或地板 radio，會同步更新 `currentSceneData.design_choices` 並立即 reload viewer。
- 相關檔案：`roompilot/server/static/scene.js`、`roompilot/server/static/scene_viewer.js`、`roompilot/server/static/scene.html`。

## 2026-07-08 Furniture Color Missing Audit

- 新增 `docs/MISSING_COLOR_AUDIT_2026-07-08.md`，整理合併後家具資料中 `color` 缺漏或仍為 `尚未整理` 的狀況。
- 目前 `/api/site-data` 合併後 6978 筆家具中，2686 筆缺 color；其中 970 筆可先由名稱或材質字串推測顏色，1716 筆不建議硬猜。
- 後續建議新增資料清洗腳本產生 `color_fix_candidates.json`，先回填高信心顏色，再處理需要圖片或人工判斷的低信心資料。
- 新增 `docs/FURNITURE_MISSING_COLOR_MATERIAL_ROLE_2026-07-08.md`，整理 `color`、`material`、`role` 三欄缺漏：color 2686、material 5456、role 3952，三者同時缺漏 1326。

## 2026-07-08 Styles Database Summary Simplification

- `/styles` 的「資料庫對應」區塊改為只保留 `全資料庫家具`、`已具風格標籤` 兩個總覽數字。
- 原本的目前風格命中、目前風格類型、12 種風格分布、全資料庫細分類清單已從畫面移除。
- 目前風格的家具類型改以大類歸納顯示，例如桌子、椅子/座椅、墊子/地毯、櫃子/收納、床/臥室、燈具、家電、裝飾/植栽、戶外家具、其他家具。

## 2026-07-08 Styles Surface Carousel

- `/styles` 的牆面生成方案與地板資料庫推薦改成兩條獨立橫向 carousel。
- 牆面 carousel 只顯示程式生成牆面方案；地板 carousel 顯示符合目前風格的資料庫地板 pool。
- carousel 會自動滑到下一個材質；滑鼠 hover 或鍵盤 focus 時暫停；使用者可用左右按鈕或橫向拖拉自行切換。

## 2026-07-08 Scene UI Density And Floor Search

- `/scene` 的狀態訊息移到「生成 3D 場景」按鈕上方，避免操作訊息出現在 viewer 底部而看不到。
- `/scene` 已選家具清單改為重點顯示：名稱縮短，完整名稱放在 title tooltip，類型與尺寸保留小字。
- `/scene` 地板材質選擇改為可檢索：支援搜尋、材質分類、只看目前風格、顯示更多；預設不再一次鋪滿全部地板卡片。

## 2026-07-08 Scene Viewer Drag / Snap / Camera Pass

- `/scene` 3D viewer 初始與重設角落視角已拉近，俯視、入口、室內視角也調整為更容易看清家具的距離。
- 家具拖曳時的地板 footprint guide 加強為半透明占地框、外框與中心十字，方便判斷家具實際落點。
- 拖曳靠近牆面時改用新版吸附邏輯：水平牆自動對齊 0 度，垂直牆自動對齊 90 度；放開滑鼠後會用 `/api/scene/validate` 驗證新位置與旋轉。
- 若貼牆或旋轉後驗證失敗，viewer 仍保留使用者手動位置與旋轉，只顯示警告；避免旋轉按鈕或貼牆操作看起來沒有反應。
- 追加修正：手動微調以 viewer 操作優先。旋轉按鈕與鍵盤 `R` 會立即旋轉選取家具並更新資料；後端驗證只做警告，不再讓旋轉按鈕看起來沒有反應。
- 追加 `snapDragPositionV3`：拖曳貼牆會對任意牆段找最近投影點，依牆面法線推出家具並對齊牆段角度，改善靠牆時吸附不穩或貼不上牆的問題。
- `inside` 室內視角改為受限室內旋轉模式：鏡頭放在房間內、關閉 pan/zoom、固定短距離 Orbit 半徑，只允許在室內旋轉看周圍；切回俯視/入口/角落或 focus 物件時恢復一般 OrbitControls。

## 2026-07-08 Mirror Size Sanitizer Fix

## 2026-07-08 Appliance Size And Light Preview Contrast

- `/library` appliance sizing and preview contrast were fixed on `bella`.
- `roompilot/catalog/style_db.py` now has explicit size rules for kitchen appliances and home appliances; small kitchen appliances infer rice cooker, kettle, induction hob, toaster, coffee maker, blender, air fryer from names instead of falling back to cabinet-sized defaults.
- `roompilot/server/static/common.js`, `library.js`, and `library_thumbnails.js` now route light/white/unknown-color appliances and light furniture to the dark preview stage, while keeping dark furniture on light stage for contrast.

## 2026-07-08 Scene Viewer Bounds And Per-Object Controls

- `/scene` viewer now blocks selected furniture from being dragged outside the rectangular room bounds and checks the selected footprint against wall segments before accepting movement.
- The previous drag release bypass (`if (true)`) was removed so `/api/scene/validate` results are respected again; invalid moves are reverted.
- A per-selected-furniture control pad was added inside the 3D viewer for forward/back/left/right 10 cm nudges and left/right 90 degree rotation. Each nudge and rotation runs the same frontend bounds/wall check plus backend validation before applying.

## 2026-07-08 Wall Surface Catalog Import

- Imported `C:/Users/user/Downloads/drive-download-20260708T063327Z-3-001.zip` as the first wall-material database batch.
- Added four wall-only surfaces under `roompilot/server/static/surface_assets/wall_materials_20260708/` and merged them into `roompilot/catalog/data/surface_catalog.json` with `usage: ["wall"]`.
- Each of the 12 style profiles now has `wall_surface_ids` and `default_wall_surface_id`; wall filtering is separate from floor filtering.
- `/styles` now renders a wall material carousel from the wall database, with current-style recommendations first and other wall surfaces as manual alternatives.
- `/scene` now lists catalog wall materials in the wall selector, and `scene_viewer.js` applies selected wall textures through the wall-only catalog path so floor textures do not leak onto walls.

## 2026-07-08 OpenRouter Env Loading

- User added `OPENROUTER_API_KEY` to repo `.env`; local server status showed `has_api_key=true`.
- `.env` also contains `OPENROUTER_MODELS`, but the running server can still report `has_model=false` if it was started with an empty environment value.
- `roompilot/server/scene_service.py` now lets `.env` fill variables when the existing process environment value is missing or empty, not only when the key is absent. Restart the FastAPI server after changing `.env`.

## 2026-07-08 Scene Object Control Buttons

- Fixed the in-viewer single-object control pad so button clicks no longer bleed through to the WebGL canvas.
- Added a clean control path for the pad buttons: forward/back/left/right now move the selected furniture by 25 cm relative to the furniture's current rotation, not the global room axes.
- Left/right rotation now validates and applies the safe constrained position together with the new rotation, which prevents near-wall objects from appearing unresponsive.
- Keyboard `R` and external rotate controls now use the same clean rotation path as the in-viewer buttons.

## 2026-07-08 Wall JSON Catalog Expansion

- Imported `C:/Users/user/Downloads/牆壁 JSON-20260708T082918Z-3-001.zip` as the second wall-material batch.
- Added 106 remote-preview wall surfaces into `roompilot/catalog/data/surface_catalog.json`; total wall surfaces are now 110.
- New wall categories are `paint`, `wood_wall`, `wall_tile`, and `wallpaper`, with style pools merged into all 12 style profiles.
- `/scene` wall choices now merge style-recommended catalog walls, all other catalog walls, and the original procedural/generated wall options under a `程式生成` category.
- `scene_viewer.js` now sets TextureLoader CORS to anonymous so remote wall preview/texture URLs have a better chance of loading in WebGL.

- 修正 `roompilot/catalog/style_db.py` 的尺寸清洗規則：`mirror`、`large-mirror`、`standing-mirror`、`wall-mirror` 不再套用一般家具的「寬 x 深」判斷。
- 鏡子名稱若是兩段尺寸，例如 `30x30 cm`、`78x196 cm`，會解讀為「寬 x 高」，深度補薄鏡厚度；三段尺寸才維持「寬 x 深 x 高」。
- 已確認 `BLODLÖNN Mirror 30x30 cm` 清洗後為 `30 x 3 x 30 cm`，`HOVET Mirror 78x196 cm` 清洗後為 `78 x 3 x 196 cm`，避免前端顯示 `30 x 30 x 80 cm` 或 `78 x 196 x 196 cm`。
- 前端 `formatSize(size, item)` 追加鏡子顯示順序：內部資料仍為 `width/depth/height` 給 3D 使用，但 UI 對鏡子顯示為「寬 x 高 x 厚」，例如 `BLODLÖNN` 顯示 `30 x 30 x 3 cm`、`HOVET` 顯示 `78 x 196 x 3 cm`。
- 2026-07-08 追加：鏡子尺寸顯示加上前端保護。`common.js` 的 `formatSize(size, item)` 會優先從鏡子名稱中的 `30x30`、`78x196` 解析 UI 顯示尺寸，避免伺服器尚未重啟或 API 暫時回舊尺寸時，頁面仍顯示 `30 x 80 x 30 cm`、`78 x 196 x 196 cm`。
- 2026-07-08 追加：`/styles` 風格圖標註改用 `STYLE_ANNOTATIONS_ROOM_FOCUS`，12 種風格指引只描述室內家具、材質、線條、色彩、收納、牆地板等特徵，不再用採光、窗外風景、窗景或光影作為風格說明。
- 2026-07-08 追加：美拉德風示意圖已替換為暖棕/焦糖/深胡桃木/奶茶牆調性的室內圖，避免原本偏白美式壁爐感；同步調整 `STYLE_ANNOTATIONS_ROOM_FOCUS.melad` 指向奶茶礦物牆、焦糖皮革沙發、深胡桃木層架、深木茶几、銅色桌燈。
- 2026-07-08 追加：美式風示意圖已替換為都會 American transitional / classic 方向，使用深木對稱壁櫃、壁爐主牆、皮革鉚釘單椅、厚重木茶几、黃銅黑色燈具，避免與美式鄉村風的白櫃、藤籃、格窗、花布語彙過度相似。
- 2026-07-08 追加：美式鄉村風標註改用 `STYLE_ANNOTATION_OVERRIDES.american_country`，實際渲染指向白色壁爐櫃體、藤編置物籃、花卉棉麻抱枕、仿舊木茶几、條紋休閒椅；不再以採光、窗外、窗景或光影作為風格理由。
- 2026-07-08 追加：混搭風標註改用 `STYLE_ANNOTATION_OVERRIDES.eclectic`，實際渲染指向植栽與藝術牆、開放書牆、異材質茶几組、復古圖紋地毯、跳色單椅，避免標籤落到圖片外側或指錯家具。
- 2026-07-08 追加：`/styles` 牆面與地板材質 carousel 改為使用者手動控制自動動畫。預設不自動輪播；牆面與地板各自有「自動播放 / 停止動畫」按鈕，按下後才以 1.5 秒節奏前進。
