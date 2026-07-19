# RoomPilot `ben-dev` 功能整合來源報告

> 盤點日期：2026-07-19
> 整合分支：`ben-dev`；盤點時基底 HEAD 為 `ba1674a`，本報告與本次功能修改由同一整合提交承載。
> 盤點範圍：`main`、`ben`、`ancai`、`bella`、`django`、`kai`、`yen`、`cody`，以及外部儲存庫 `hehehahiWowo/room_pilot2`。

## 1. 結論摘要

這次不是把某一條分支整體合併進 `ben-dev`，而是維持 `ben-dev` 的 FastAPI + React Three Fiber 主架構，按功能選用來源：

- 家具合法擺放的幾何權威直接沿用 `ancai` 的 `roompilot/engine/`。
- 平面圖牆、門、窗辨識沿用 `cody` 管線，再疊加 `ben` 的 VLM／分類器／分割模型改良。
- 3D 編輯器與 Agent 提示鏈沿用 `yen`，但接口已由 `ben` 收斂到 `roompilot/`。
- 六風格、18 張色卡與圖片資產直接沿用 `bella`。
- SQLite 專案儲存以 `bella` 2026-07-18 版本為骨架，再於 `ben-dev` 加上 revision、防競態、Pydantic 契約與 PNG 歷史。
- 房間語意、牆上公分校尺、專案式問卷、單一 2D 配置、真窗洞、視角鎖定、條件式換家具與 PNG 版本血統，都是本次在 `ben-dev` 新寫或大幅重寫的整合層。
- `django` 沒有採用；目前該遠端分支實際也已是 FastAPI，且相對 `ben-dev` 的共同基底沒有獨有程式碼。
- `kai` 的 PDF／完整交付包沒有進 P0；PDF 依組長決定留在 P1。
- 外部 `room_pilot2` 只作房間分割與 Canvas 輸出設計參考，沒有直接複製它的獨立 TypeScript／毫米制後端。

## 2. 來源標記方式

| 標記 | 定義 |
|---|---|
| 直接沿用 | Git 檔案血統或資料 blob 可直接追到來源分支，目前仍是執行期依賴。 |
| 骨架移植 | 保留來源的資料模型／主要方法，再為主線接口大幅加固。 |
| 參考重寫 | 借用演算法或產品閘門概念，但目前檔案是 `ben-dev` 新檔，沒有直接 Git 血統。 |
| `ben-dev` 新寫 | 各候選分支沒有同檔或同接口；為這次主流程新建。 |
| 未採用 | 有評估，但未成為目前 P0 執行路徑。 |

## 3. 各功能採用來源總表

| 使用者流程功能 | 實際採用的來源分支與檔案 | 採用方式 | 目前落地檔案 | 關鍵證據 |
|---|---|---|---|---|
| 共用 FastAPI／R3F 主殼 | `ben:roompilot/server/main.py`、`ben:roompilot/server/scene_service.py`；`yen:frontend3d/src/App.jsx`、`Scene.jsx`、`Furniture.jsx`、`snap.js` | 直接沿用後擴充 | `roompilot/server/main.py`、`scene_service.py`；`frontend3d/src/App.jsx`、`Scene.jsx`、`Furniture.jsx` | `85b4a92` 完成「B 殼 A 內臟」；前端檔案血統可追到 `yen` 的 `3434731`／`66324bc`。 |
| 建立新專案／續作 | `bella@c0c7463:roompilot/server/project_store.py`、`runtime_paths.py`、`main.py` | 骨架移植；React 客戶端與強型別 API 為新寫 | `roompilot/server/project_store.py`、`runtime_paths.py`、`project_models.py`、`main.py:create_project/get_project/save_project_workflow`；`frontend3d/src/project.js`、`App.jsx` | 來源與目前版共同保留 `_utc_now`、`_merge_dict`、`_compact_workflow_value`、SQLite `projects` 表與 upload 方法；目前版新增 `revision`、WAL、2 MB workflow 上限與 409 衝突。 |
| 上傳平面圖 | `bella@c0c7463:project_store.py:save_upload`、`main.py` 專案端點；`ben:main.py:/api/upload` 舊解析入口；`yen:frontend3d/src/App.jsx` 上傳殼 | 儲存骨架移植，專案式 endpoint 與 UI 重寫 | `main.py:save_project_floorplan/get_project_floorplan_source`、`project_store.py:save_upload`、`project_models.py`、`frontend3d/src/project.js:uploadServerFloorplan`、`App.jsx` | 原檔進 `.runtime/uploads/{project_id}`，重新上傳會清除舊辨識／問卷／配置等下游資料；`tests/test_project_api.py:test_floorplan_upload_is_stored_and_increments_revision`。 |
| AI 辨識牆壁、門窗、空間屬性 | `cody:scripts/floorplan2dxf.py`（早期為根目錄 `floorplan2dxf.py`）；`ben:roompilot/floorplan/seg_infer.py`、`opening_classifier.py`、`server/floorplan_vlm.py`、`upgrade3d/dxf_parser.py`；外部 `room_pilot2:backend/app/rooms/segment.py`、`label_text.py`、`label_rules.py` | 牆門窗直接沿用 Cody→Ben 血統；房間分割／文字優先概念參考重寫 | `roompilot/floorplan/floorplan2dxf.py`、`room_analysis.py:derive_room_regions`、`upgrade3d/dxf_parser.py:_collect_texts`、`server/main.py:_recognize_floorplan_bytes`、`frontend3d/src/FloorplanReview.jsx` | `449a7f3` 明記移植 Cody v1.3–v1.5，`280dc46` 加入 seg 第二意見；`a0e50aa` 加入 OpenRouter VLM；目前房間幾何改用 Shapely「bbox − wall mass」而非外部 repo 的 NumPy flood-fill。 |
| AI 建議＋使用者確認 | `bella@c0c7463:floorplan/vision/confirmation.py` 的 confirmation seam；`ben:floorplan_vlm.py` 的 opt-in VLM | 參考重寫 | `main.py:analyze_project_floorplan/confirm_project_floorplan`、`project_models.py:ProjectSpaceConfirmationRequest`、`FloorplanReview.jsx` | AI 回傳只停在 `recognition`；只有 `/floorplan/confirm` 能寫入 `space_confirmation`。`tests/test_project_api.py:test_space_confirmation_persists_only_user_confirmed_geometry`。 |
| 手拉線設定比例（公分、沿辨識牆） | `ben@9ec0708:roompilot/server/static/scene.js`、`scene_service.py` 的兩點標定；`bella@c0c7463:scene_calibration.js` 僅作比例計算參考 | 以 Ben 版為前身，依新規格重寫 | `frontend3d/src/FloorplanReview.jsx`、`floorplanReview.js:snapPointToWall/calibrationPayload`、`main.py:_validate_reference_follows_wall/calibrate_project_floorplan` | 舊 Ben 版接受任意兩點後換算全圖長邊；目前端點必須貼合辨識牆且同向，API 欄位為 `reference_cm`／`actual_length_cm`。全圖長邊輸入沒有進使用者上傳主流程。 |
| 針對性需求問卷 | `kai:roompilot/server/workflow_service.py:extract_special_requirements` 的確定性 JSON／確認概念；`bella:roompilot/server/intake_service.py` 的 OpenRouter + fallback 模式 | 參考重寫 | `roompilot/server/requirements_service.py`、`project_models.py` 問卷 models、`main.py:analyze_project_requirements/confirm_project_requirements`、`frontend3d/src/RequirementsQuestionnaire.jsx`、`requirements.js` | 新服務未 import Kai／Bella 模組；一般欄位走 `build_local_constraints`，只有 advanced 自由文字＋明確同意才走 `_openrouter_suggestion`，最後仍需 `/requirements/confirm`。 |
| AI 自動配置 2D 家具 | `ancai:roompilot/engine/{models,geometry,clearance,placement,adjustment,schema,dxf_room}.py`；`yen:roompilot/agent/{layout_intent,recovery,prompts}.py`；`bella:roompilot/catalog/data/furniture_catalog_6styles_zh.json` 與 `style_db.py` | 引擎、Agent、型錄直接沿用；專案協調層新寫 | `roompilot/server/layout_service.py:build_layout_proposal`、`scene_service.py:generate_layout`、`main.py:analyze_project_layout`、`frontend3d/src/Layout2DReview.jsx`、`layout2d.js` | `layout_service.py` 直接 import `design_layout_intent`、`run_recovery`，再呼叫 `generate_layout`；`generate_layout` 最後以 `check_placement_with_clearance`／`place_furniture` 決定座標。OpenRouter 只能從伺服器候選 ID 選件，不能輸出座標。 |
| 2D／3D 手動微調 | `yen:frontend3d/src/Furniture.jsx`、`snap.js`；`ben@793a74c:scene_service.py` 的引擎驗證／彈回 | 直接沿用後擴充；2D 編輯畫面新寫 | `Layout2DReview.jsx`、`layout2d.js`、`main.py:validate_project_layout`；`Furniture.jsx`、`snap.js`、`scene_service.py:validate_scene_placement` | 2D 拖曳與旋轉送 `/layout-2d/validate`；3D 舊拖曳仍由引擎檢查。問卷指定家具不可刪除。 |
| 生成 3D 白模 | `yen:frontend3d/src/Scene.jsx`、`Furniture.jsx`、`upgrade3d/dxf_parser.py` 的 R3F／DXF 升維底座 | 底座直接沿用；中性家具白模為新寫 | `Furniture.jsx:WhiteFurnitureLayer`、`whiteModel.js`、`main.py:confirm_project_white_model`、`Scene.jsx` | 白模不載入 GLB，而依 `size_cm` 生成中性 box，避免缺模型造成假完成；`tests/test_layout_api.py:test_white_model_requires_every_furniture_and_real_window_opening`。 |
| 牆體形成真窗洞 | 各分支與外部 repo 均沒有相同的 `wall_solids`／`opening_geometry` 契約；舊 Ben／Bella 只有窗玻璃盒或窗牆視覺連續化 | `ben-dev` 新寫 | `roompilot/upgrade3d/wall_openings.py:build_opening_wall_geometry`、`dxf_parser.py`、`frontend3d/src/Scene.jsx:Walls` | 依高度切牆帶，窗洞只在 sill～head 間扣除，門洞從地面扣除；離牆的誤偵測不挖洞。所有候選分支 `git grep wall_solids/opening_geometry` 均無結果。 |
| 手動調整並鎖定攝影機 | `yen:Scene.jsx` 的 `OrbitControls`／R3F camera；`bella@c0c7463:scene_viewer.js` 的 `cameraLocked` 行為與 `test_scene_delivery.py` | R3F 底座直接沿用，鎖定／保存接口參考重寫 | `frontend3d/src/Scene.jsx:CameraBridge`、`proposal.js:viewpointConfirmationPayload`、`main.py:confirm_project_viewpoint` | 目前保存 `position_cm`、`target_cm`、`fov_deg`，鎖定後才可套色卡；不是 Bella vanilla Three.js 檔案的直接合併。 |
| 選擇 18 色卡與風格參數 | `bella@bd9ae45:roompilot/catalog/data/taiwan_style_cards.json`、`server/static/style_cards/`、`server/style_cards.py` | 色卡資料與圖片直接沿用；渲染契約新寫 | 原色卡檔與圖片；`style_cards.py:style_card_render_intent`、`proposal.js:flattenStyleCards`、`Scene.jsx` | `origin/ben`、`origin/bella` 與目前 `taiwan_style_cards.json` blob 都是 `1a5a2a12…`，證明資料未另造一份。 |
| 換色卡時保護使用者指定家具 | 使用 Bella 風格型錄＋Ancai 引擎；條件規則由本次產品決策新增 | `ben-dev` 新寫 | `layout_service.py:_is_user_selected/build_style_variant`、`main.py:apply_project_style_card`、`proposal.js:isUserSelectedFurniture` | `user_required=true` 或 `selection_source=user` 會鎖定型號與位置；其餘同類換選後再由 `roompilot.engine` 重排。`tests/test_layout_api.py:test_viewpoint_style_card_and_final_png_preserve_explicit_furniture`。 |
| 儲存與匯出最終 PNG | 外部 `room_pilot2@f6a6f29:frontend/src/render/saveImage.ts` 的 Canvas→PNG；`bella@c0c7463:scene_viewer.js:capturePng` 與 `project_store.py` | Canvas 輸出是參考重寫；SQLite 專案骨架延伸 | `Scene.jsx:CameraBridge.capturePng`、`project.js:createServerRender/listServerRenders`、`project_store.py:save_render/list_renders`、`main.py:create_project_render` | 目前用 WebGL canvas `toBlob`，後端驗證 PNG 並記錄白模／視角／色卡版本；不是只在瀏覽器下載。外部 repo 沒有 RoomPilot 專案 revision／歷史表。 |
| PDF 報告 | `kai`／`bella` 有完整交付／PDF 構想 | 未採用（P1） | P0 沒有 PDF 程式碼 | 組長已決定 P0 只做最終 PNG；`kai` delivery 與 `bella:scene_delivery.js` 的 PDF output 未接入目前 endpoint。 |

## 4. 各分支實際貢獻與未採用部分

| 分支／儲存庫 | 這次真正使用的檔案或血統 | 沒有採用的主要部分 | 判定 |
|---|---|---|---|
| `main` (`8fbd372`) | 只作歷史共同基底；實際工作由較新的 `ben`／`ben-dev` 承接。 | `main` 內重複的 `RoomPilot-Agent/` repo 副本與舊狀態不帶入。 | 不從 `main` 另做整體 merge。 |
| `ben` (`280dc46`) | `roompilot/server/main.py`、`scene_service.py`、`floorplan_vlm.py`、`floorplan/` 改良、既有 FastAPI 主流程；手動比例前身 `9ec0708`。 | 舊 vanilla `server/static/scene.js` 不作新的主前端；全圖長邊輸入不進上傳主流程。 | 本次整合主骨架。 |
| `ancai` (`e0f34d9`) | `roompilot/engine/` 全套與 `tests/test_placement.py`、`tests/test_clearance.py`。 | 沒有另建第二套座標引擎。 | 家具擺放主版本；直接採用。 |
| `bella` (`c0c7463`) | 既有 `bd9ae45` 色卡／六風格資料；最新 `project_store.py`、`runtime_paths.py` 作專案儲存骨架；camera lock 與 confirmation seam 作參考。 | `web_fastapi/`、`sf3d/`、`furniture_engine/` 副本、vanilla `scene_v2.js`、成本估算、完整 delivery manifest 不整包搬入。 | 選擇性移植，不做整體 merge。 |
| `django` (`9db58a3`) | 無本次 P0 獨有來源。 | 分支名雖叫 django，目前 tree 只有 FastAPI；`git grep` 找不到 `manage.py`／`django` import，且分支相對共同基底沒有獨有 diff。 | 不採用，也不引入第二套後端。 |
| `kai` (`60dad36`) | 本次 P0 功能沒有直接 runtime 依賴；問卷完整性與交付分級只作需求分析參考。 | `frontend3d/src/project.js` 的單一 localStorage 大物件、`requirement_service.py` 的正式設計／工程交付、PDF／SQL／大型 JSON 更新未帶入。 | P0 暫不整合；PDF 留 P1。 |
| `yen` (`708a038`) | `frontend3d/{App,Scene,Furniture,snap}.jsx/js` 與 `roompilot/agent/`。 | 合併基底 `c14ff38` 之後只有 README／整合方案文件差異，沒有漏掉未整合功能。 | 已被 Ben 包含；保留程式血統。 |
| `cody` (`9cbecf7`) | `floorplan2dxf` 牆／門／窗管線及評估資料；透過 `449a7f3`、後續 Ben commit 進 `roompilot/floorplan/`。 | `floorplan2room.py` 的獨立彩圖／CubiCasa／符號模板管線與大量衍生資料未直接進主流程。 | 核心辨識沿用；房型管線只取概念，不搬資料集。 |
| 外部 `room_pilot2` (`af858b0`) | `backend/app/rooms/{segment,label_text,label_rules}.py` 的「封門縫→分房→文字優先」概念；`frontend/src/render/saveImage.ts` 的 Canvas 輸出方式。 | 它的毫米制 backend、獨立家具引擎、TypeScript 前端、path tracer、自然語言場景編輯皆未合併。 | 參考重寫；沒有直接 copied file。 |

### Bella 歷史狀態補充

目前 `ben-dev` 與 `origin/bella` 已有共同歷史，merge base 是 `6274b46`；但 `origin/bella` 最新的 `c0c7463` 仍不在 `ben-dev`。因此這次只逐檔取 `project_store.py`／`runtime_paths.py` 的骨架，沒有把最新 Bella 分支整體 merge，仍符合「不要直接整體合併 Bella」的安全原則。

### Yen 是否還有未整合功能

`git diff $(git merge-base ben-dev origin/yen)..origin/yen` 只有：

- `README.md`
- `RoomPilot-Agent/docs/for_agent_整合方案.md`

所以 `yen` 在 Ben 已納入的 `c14ff38` 之後沒有額外程式功能遺漏；遠端 `708a038` 只多文件。

## 5. 目前檔案的來源帳本

### 5.1 後端與演算法

| 目前檔案 | 來源判定 | 主要職責 |
|---|---|---|
| `roompilot/server/main.py` | Ben FastAPI 檔案直接擴充；Bella 專案 endpoint 選擇性移植 | 全部 project-scoped API 與確認閘門。 |
| `roompilot/server/scene_service.py` | Ben 整合檔；內含 Ancai engine 與 Yen Agent 的既有接線 | 單位／座標轉接、合法配置、拖曳驗證。 |
| `roompilot/server/project_store.py` | Bella `c0c7463` 骨架移植並加固 | SQLite 專案、revision、uploads、render history。 |
| `roompilot/server/runtime_paths.py` | Bella `c0c7463` 骨架移植並縮小副作用 | `.runtime`／worktree 共用路徑解析。 |
| `roompilot/server/project_models.py` | `ben-dev` 新寫 | Pydantic 請求／回應契約與公分欄位。 |
| `roompilot/server/requirements_service.py` | 參考 Kai／Bella 後新寫 | 確定性問卷規則、OpenRouter 結構化建議。 |
| `roompilot/server/layout_service.py` | `ben-dev` 新寫，直接調用 Ancai／Yen／Bella 既有模組 | 型錄白名單、單一 2D 提案、風格換件。 |
| `roompilot/server/style_cards.py` | Bella 既有 loader；本次新增 `style_card_render_intent` | 18 色卡→場景渲染契約。 |
| `roompilot/floorplan/floorplan2dxf.py` | Cody 直接血統，Ben 續改 | PNG 牆／窗／門離線辨識。 |
| `roompilot/floorplan/room_analysis.py` | 外部 repo／Bella 分房概念參考後新寫 | Shapely 自由空間、穩定 room ID、文字／AI 語意。 |
| `roompilot/upgrade3d/dxf_parser.py` | Yen 升維底座、Ben 長期修正；本次加文字與真窗洞接線 | DXF→中心原點公尺 payload。 |
| `roompilot/upgrade3d/wall_openings.py` | `ben-dev` 新寫 | 依高度切牆並扣除真實門窗開口。 |
| `roompilot/engine/*.py` | Ancai 直接沿用 | 公分制家具 placement／clearance／geometry／schema。 |
| `roompilot/agent/*.py` | Yen 直接沿用，本次只小修 recovery 欄位 | LLM layout intent 與放不下 recovery。 |

### 5.2 前端

| 目前檔案 | 來源判定 | 主要職責 |
|---|---|---|
| `frontend3d/src/App.jsx` | Yen R3F App 直接擴充，這次大幅重組流程 | 專案全流程 orchestration。 |
| `frontend3d/src/Scene.jsx` | Yen R3F Scene 直接擴充；Bella camera lock／外部 PNG 概念參考 | 真窗洞牆層、CameraBridge、色卡 surface、PNG capture。 |
| `frontend3d/src/Furniture.jsx` | Yen 3D 家具／拖曳底座直接擴充 | 中性白模、GLB 失敗 fallback、保護指定家具。 |
| `frontend3d/src/snap.js` | Yen 直接沿用 | 3D 家具吸附。 |
| `frontend3d/src/project.js` | `ben-dev` 新寫；未採 Kai 單一 localStorage 架構 | Server API client、project URL、每專案快取。 |
| `frontend3d/src/FloorplanReview.jsx`、`floorplanReview.js` | `ben-dev` 新寫 | 辨識後 2D 確認與沿牆公分校尺。 |
| `frontend3d/src/RequirementsQuestionnaire.jsx`、`requirements.js` | `ben-dev` 新寫 | 80/20 問卷、OpenRouter 同意與確認。 |
| `frontend3d/src/Layout2DReview.jsx`、`layout2d.js` | `ben-dev` 新寫 | 2D footprint 拖曳／旋轉／確認。 |
| `frontend3d/src/whiteModel.js` | `ben-dev` 新寫 | 白模可見性診斷與確認 payload。 |
| `frontend3d/src/proposal.js` | `ben-dev` 新寫 | 攝影機契約、18 色卡攤平、家具保護規則。 |
| `frontend3d/src/styles.css` | Yen 原檔上擴充 | 新流程與提案畫面樣式。 |

### 5.3 測試

本次新測試不是從其他分支直接複製，而是針對整合後契約新寫：

| 測試檔 | 驗證功能 |
|---|---|
| `tests/test_project_api.py` | 建立／續作、上傳、revision、空間確認、持久化。 |
| `tests/test_floorplan_room_analysis.py` | 分房、DXF 文字優先、OpenRouter 明確同意。 |
| `tests/test_requirements_api.py` | 問卷、特殊需求、LLM opt-in、指定 GLB 合法性。 |
| `tests/test_layout_api.py` | 2D 配置、引擎限制、白模、視角、色卡、PNG 與家具保護。 |
| `tests/test_wall_openings.py` | 窗洞高度、門洞、離牆誤偵測、座標翻轉。 |
| `frontend3d/src/*.test.js` | project client、校尺吸附、問卷、2D 編輯、白模、提案契約。 |

## 6. 沒有直接採用的競爭版本

1. **Bella 整套 `scene_v2.js`／`web_fastapi`**：功能多，但屬 vanilla Three.js 與重複 FastAPI 殼；目前主線已決定用 `frontend3d/` R3F，因此只移植專案儲存、確認／視角概念與色卡資產。
2. **Kai 專案物件／交付包**：`frontend3d/src/project.js` 以 localStorage 為唯一狀態，缺少伺服器 revision；完整工程交付、PDF、SQL 超過目前 P0。
3. **Cody `floorplan2room.py` 最新整包**：需要獨立 CubiCasa 權重、快取與大量資料；目前主流程以已有 `wall_polys` 做 Shapely 分房，整合成本較低且接口一致。
4. **外部 `room_pilot2` 家具引擎**：採毫米制並形成第二套權威；違反目前「家具座標只有 `roompilot.engine` 能算」的不變量。
5. **外部 path tracer／自然語言改場景**：不在目前 P0，PNG 採瀏覽器現有 R3F 場景擷取。
6. **PDF**：保留 P1，沒有把 Bella／Kai 的 PDF 宣告誤當成已完成輸出。

## 7. 驗證與可追溯證據

### 7.1 Git 證據

- `b75f709`／`09cb887`／`1dfa4d5`／`52bfc6f`：Ancai 建立 placement、clearance、geometry、schema 與測試。
- `e0f34d9`，再由 merge commit `b58d53e` 納入 Ben：Ancai engine 公分化。
- `2ea41aa` 起：Cody `floorplan2dxf`；`449a7f3` 移植 Cody v1.3–v1.5；`280dc46` 再加入 segmentation second opinion。
- `3434731`／`66324bc`：Yen R3F 前端；`da162f9` 納入 Ben。
- `2e152bb`：Yen Agent；`e1509b9` 納入 Ben。
- `bd9ae45`，再由 `9c6f8ef` 策略式納入：Bella 六風格／18 色卡／intake。
- `c0c7463`：Bella 最新 project store、floorplan confirmation、camera lock 與 delivery 原型；本次只逐檔移植所需骨架。
- `9ec0708`：Ben 舊 F2a 兩點比例標定；本次改成辨識後沿牆、公分 API。
- 外部 `room_pilot2`：`3a27440` 房間 flood-fill／文字標籤；`f6a6f29` Canvas PNG／path tracing。

### 7.2 目前測試狀態

本次整合在完成報告時重新執行的完整驗證結果：

```text
uv run pytest tests/ -q
100 passed, 1 skipped

cd frontend3d && npm test
32 passed

cd frontend3d && npm run build
成功；只有 bundle > 500 kB 警告
```

這些數字驗證的是目前 working tree，不代表各候選分支自己的測試狀態；來源分支的角色以 Git 血統與執行期 import 為準。

## 8. 維護責任建議

| 範圍 | 最適合的原始維護者／目前接手者 |
|---|---|
| `roompilot/engine/` 幾何、淨空、schema | Ancai 為原作者；Ben／整合者維護接口與單位邊界。 |
| `roompilot/floorplan/` 牆門窗辨識 | Cody 為原作者；Ben 維護 VLM／seg 仲裁與 server 接線。 |
| `frontend3d/` R3F、拖曳、Agent | Yen／hehehahiWowo 為底座原作者；目前整合者維護 project workflow。 |
| 六風格、18 色卡與資產 | Bella 為原作者；目前整合者維護 `style_card_render_intent` 與換件策略。 |
| 專案 SQLite、確認 API、真窗洞、PNG 歷史 | 目前 `ben-dev` 整合層；應由 Ben／主線整合者接手，因這些新檔尚無獨立分支 owner。 |

## 9. 最終一句話

目前 `ben-dev` 的組成不是「選一條最好分支」，而是：**Ben 的 FastAPI 整合殼 + Yen 的 R3F／Agent + Ancai 的家具幾何引擎 + Cody 的平面圖辨識 + Bella 的色卡與專案儲存骨架，再由本次 `ben-dev` 新整合層把每個使用者確認關卡、真窗洞、條件式換家具與最終 PNG 串成同一個可續作專案。**
