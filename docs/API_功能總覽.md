# RoomPilot API 功能總覽

> 整理日期：2026-08-06（分支 `feat/step1-4-ben-port`；行號對 `backend/server/main.py` 重新校準）
> 所有端點皆定義於 `backend/server/main.py`，無外部 APIRouter。
> 共 52 個端點：4 個頁面路由 + 48 個 API。無 WebSocket 端點。

## 基本資訊

- **框架**：FastAPI（進入點 `backend/server/main.py`）
- **啟動事件**：`startup` 時執行 `warm_catalog_cache()` 預熱型錄快取
- **CORS / Middleware**：未自訂（FastAPI 預設）
- **靜態掛載**：
  | 路由 | 目錄 | 內容 |
  |---|---|---|
  | `/static` | `backend/server/static` | CSS、JS、HTML、GLB 樣本 |
  | `/docs-assets` | `backend/server/static/moodboard_assets` | 風格 moodboard 與色卡圖片 |
- **大小限制**：渲染 PNG 上限 20 MB；workflow payload 上限 2 MB
- **平面圖支援格式**：`.dxf`、`.png`、`.jpg`、`.jpeg`

## 工作流程步驟（WORKFLOW_STEPS，main.py:113）

`project` → `upload` → `recognition` → `calibration` → `space_confirmation` → `requirements` → `layout_2d` → `white_model_3d` → `realistic_3d` → `proposal_review` → `ai_render`

---

## 1. 頁面路由

| 方法 | 路由 | 位置 | 功能 |
|---|---|---|---|
| GET | `/` | main.py:1637 | 首頁（index.html） |
| GET | `/styles` | main.py:1642 | 風格頁 |
| GET | `/library` | main.py:1647 | 家具型錄頁 |
| GET | `/scene` | main.py:1652 | 3D 場景編輯頁（no-cache） |

## 2. 專案管理

| 方法 | 路由 | 位置 | 功能 |
|---|---|---|---|
| POST | `/api/projects`（201） | main.py:1772 | 建立新專案。Body：`{name, notes}` → `{project}` |
| GET | `/api/projects/{project_id}` | main.py:1788 | 取得專案資料 |
| PUT | `/api/projects/{project_id}/workflow` | main.py:1794 | 保存工作流程狀態；以 `expected_revision`、`base_updated_at` 做樂觀鎖防衝突。宣告 `space_confirmation` 完成、但 `recognition.spatial_report.review_items` 指到的房間仍未確認時，回 422 `recognition_review_unresolved`（`detail.rooms` 列出待處理房間）|

## 3. 平面圖（專案綁定）

| 方法 | 路由 | 位置 | 功能 |
|---|---|---|---|
| POST | `/api/projects/{project_id}/floorplan`（201） | main.py:1858 | 上傳平面圖（multipart，DXF/PNG/JPG）+ `expected_revision` |
| GET | `/api/projects/{project_id}/floorplan/source` | main.py:1907 | 下載已上傳的平面圖原始檔 |
| POST | `/api/projects/{project_id}/floorplan/analyze` | main.py:2342 | 執行平面圖辨識（Cody 影像引擎或 DXF 引擎）→ `{analysis, geometry_engine}` |

## 4. 渲染輸出、AI 生圖與報告產出

| 方法 | 路由 | 位置 | 功能 |
|---|---|---|---|
| POST | `/api/projects/{project_id}/renders`（201） | main.py:1925 | 上傳最終 PNG 渲染（瀏覽器截圖），附版本欄位 `white_model_version`、`viewpoint_version`、`style_version`、`style_card_id`、`provider` |
| GET | `/api/projects/{project_id}/renders` | main.py:1988 | 列出專案的所有 PNG 輸出 |
| GET | `/api/projects/{project_id}/renders/{render_id}/png` | main.py:1999 | 下載指定 PNG 渲染 |
| GET | `/api/render-provider/status` | main.py:2016 | 查詢遠端渲染服務狀態 |
| POST | `/api/projects/{project_id}/render-jobs`（202） | main.py:2021 | 提交遠端 AI 渲染任務（色卡對比／正式渲染）→ `{jobs}`。契約：`docs/contracts/REMOTE_RENDER_CONTRACT.md` |
| GET | `/api/ai-render/status` | main.py:2052 | 查詢第 8 步 AI 生圖服務（OpenRouter nano banana）是否可用；不外洩 token |
| POST | `/api/projects/{project_id}/ai-renders`（201） | main.py:2058 | 逐房視角經 nano banana 生成寫實室內圖（不移動擺設）。前端送 `scene` ＋逐房第 7 步鎖定視角截圖；伺服器補需求／材質／家電／色卡後逐房呼叫 Gen_Pic Agent。未設金鑰回 503 |
| POST | `/api/projects/{project_id}/ai-renders/{room_id}/edit`（201） | main.py:2117 | 整批一次改圖：只改指定內容、其餘鎖定不動。額度用完回 409 `ai_edit_budget_exhausted` |
| POST | `/api/projects/{project_id}/design-manual`（201） | main.py:2188 | 九章設計手冊 PDF（比較後未採用為正式版；端點保留供獨立呼叫，第 8 步 UI 不再觸發）。未設 `OPENROUTER_API_KEY` 時走 deterministic 底稿照樣輸出 |
| GET | `/api/projects/{project_id}/design-manual/pdf` | main.py:2222 | 下載已產出的設計手冊 PDF；未產出回 404、檔案遺失回 410 |
| GET | `/api/delivery-proposal/status` | main.py:2266 | 設計提案排版引擎（playwright Chromium）是否可用；未安裝時回報安裝指引 |
| POST | `/api/projects/{project_id}/delivery-proposal`（201） | main.py:2412 | 正式成果報告：roompilot-delivery-pdf skill 排版的設計提案 PDF，同一次請求再產一份工程估價與排程 XLSX（`proposal.engineering`）。第 8 步「產出設計提案 PDF 與工程估價」按鈕唯一觸發的報告 |
| GET | `/api/projects/{project_id}/delivery-proposal/pdf` | main.py:2460 | 下載已產出的設計提案 PDF；未產出回 404、檔案遺失回 410 |
| GET | `/api/projects/{project_id}/delivery-proposal/xlsx` | main.py:2479 | 下載與 PDF 同一次產出的工程估價與初步排程 XLSX；未產出或檔案遺失回 404。契約：`docs/contracts/ENGINEERING_ESTIMATE_CONTRACT.md` |

## 5. Agent 需求訪談與家具選件

契約：`docs/contracts/AGENT_FRONTEND_BACKEND_CONTRACT.md`

| 方法 | 路由 | 位置 | 功能 |
|---|---|---|---|
| POST | `/api/agent/intake/start` | main.py:2697 | 啟動需求訪談。回傳 `{session_id, mode, step, question, client_brief, ready_for_confirmation}` |
| POST | `/api/agent/intake/answer` | main.py:2704 | 進行一輪訪談（可選 LLM，`llm_selection`）。回傳新的 `step`、`question`、`reply`、`client_brief` |
| POST | `/api/agent/furniture/select` | main.py:2801 | 家具選件與規則驗證（LLM 或本地 fallback）。Body：`{rooms, offers, style_id, context, llm_selection}` → `{source, model, warnings, rooms[{room_id, items}]}` |

## 6. 場景生成與配置

| 方法 | 路由 | 位置 | 功能 |
|---|---|---|---|
| POST | `/api/scene/generate` | main.py:2865 | 生成 3D 場景：家具選件 + AN 擺放引擎。回傳 `{selected_furniture, scene_objects, placement_resolution_report, placement}` |
| POST | `/api/scene/layout` | main.py:2916 | 使用者編輯後重算場景配置 → `{scene_objects}` |
| POST | `/api/scene/decorate` | main.py:3068 | 依風格自動加入軟裝（地毯／植栽／燈具／布簾）→ `{scene_objects, decor_summary}`。可帶 `dismissed_roles: [role]` 跳過使用者刪除過的軟裝角色，不再自動補回 |
| POST | `/api/scene/validate` | main.py:3267 | 驗證單件家具拖曳位置（碰撞／淨空）→ `{valid, message, conflicts}` |
| GET | `/api/scene/provider-status` | main.py:2692 | 查詢 OpenRouter／LLM 服務狀態 |
| GET | `/api/scene/bootstrap` | main.py:2546 | 場景編輯初始化資料 → `{styles, taiwan_style_cards, surface_catalog, catalog_status}` |

## 7. 家具型錄

契約：`docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md`

| 方法 | 路由 | 位置 | 功能 |
|---|---|---|---|
| GET | `/api/furniture` | main.py:2590 | 型錄搜尋（分頁／篩選）。Query：`style`、`group`、`type`、`q`、`page`、`page_size`、`has_model`、`detail`、`color`、`material`、`size` |
| GET | `/api/furniture/{furniture_id}/model` | main.py:3281 | 下載家具 GLB（本機直傳或 CloudFront 重定向） |
| GET | `/api/furniture/{furniture_id}/model.gltf` | main.py:3290 | 將 GLB 拆為 glTF JSON + 分離 buffer（本機 GLB 用） |
| GET | `/api/furniture/{furniture_id}/buffer.bin` | main.py:3299 | 下載 GLB binary buffer |
| GET | `/api/furniture/{furniture_id}/images/{image_index}` | main.py:3309 | 下載 GLB 內嵌貼圖（WebP 自動轉 PNG） |
| GET | `/api/sample-furniture` | main.py:3443 | 列出範例 GLB 檔名 |
| GET | `/api/furniture/{name}` | main.py:3459 | 下載範例 GLB（`.glb` 結尾）或家具詳情頁 payload。**注意**：與上方 `{furniture_id}` 系列路由共用前綴，靠註冊順序與路徑後綴區分 |
| GET | `/api/catalog/status` | main.py:2505 | 型錄提供者狀態（本機／CloudFront／AWS）→ `{furniture, surfaces, doors, style_cards}` |

## 8. 風格與站點資料

| 方法 | 路由 | 位置 | 功能 |
|---|---|---|---|
| GET | `/api/home-data` | main.py:2510 | 首頁資料（統計／前 6 風格／色卡） |
| GET | `/api/styles` | main.py:2528 | 全風格與統計（含表面型錄、各風格家具數） |
| GET | `/api/site-data` | main.py:2444 | 完整站點資料（不含家具清單） |

## 9. 問卷圖像系統

| 方法 | 路由 | 位置 | 功能 |
|---|---|---|---|
| GET | `/api/questionnaire/visual-catalog` | main.py:2556 | 問卷視覺型錄（含圖像索引）。Query：`space_type`、`ready_only` |
| GET | `/api/questionnaire/visual-images/{image_id}` | main.py:2579 | 下載單張問卷圖像 |

## 10. 平面圖分析（3D 編輯器用，非專案綁定）

| 方法 | 路由 | 位置 | 功能 |
|---|---|---|---|
| GET | `/api/plans` | main.py:3324 | 列出可用平面圖 |
| GET | `/api/plan` | main.py:3329 | 解析指定 DXF。Query：`name`、`scale_m`、`thickness`、`height` |
| POST | `/api/upload` | main.py:3345 | 直接上傳並解析 DXF |
| POST | `/api/floorplan/analyze` | main.py:3375 | 新版平面圖分析（Cody + 手動修正）。multipart：檔案 + `calibration_json`、`ocr_json`、`geometry_json`、`observed_utilities_json`、`brief_json` |
| POST | `/api/floorplan/confirm` | main.py:3418 | 確認分析結果並套用使用者修正 → `{confirmed_floorplan}` |

## 11. 其他

| 方法 | 路由 | 位置 | 功能 |
|---|---|---|---|
| POST | `/api/cost/estimate` | main.py:3431 | 概念工程概算（台灣公開行情）。Body：`{items}` → `{estimate, summary}` |
| GET | `/api/floorplan/sample/630` | main.py:2433 | 下載示範平面圖 PNG |

---

## 相關契約文件對照

| 契約文件 | 涵蓋範圍 |
|---|---|
| `docs/contracts/AGENT_FRONTEND_BACKEND_CONTRACT.md` | `/api/agent/*`、`/api/scene/generate` 欄位與 fallback 規則 |
| `docs/contracts/REMOTE_RENDER_CONTRACT.md` | `/api/projects/{id}/render-jobs` 遠端渲染 |
| `docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md` | 家具型錄與模型交付 |
| `docs/contracts/LAYOUT_EVALUATION_SCHEMA.md` | 擺放與驗證規則（`/api/scene/layout`、`/api/scene/validate`） |
| `docs/contracts/FURNITURE_ENGINEERING_RULES.md` | 家具工程規則 |
| `docs/contracts/STYLEPACK_RENDERING_CONTRACT.md` | StylePack 即時渲染 |

> 補充：跨模組幾何資料一律使用公分（`_cm` 欄位），payload 需帶 `coordinate_unit: "cm"` 與 `schema_version`；面積使用 `_m2`。詳見根目錄 `README.md` 共同規則。
