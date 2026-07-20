# RoomPilot-Agent

RoomPilot 是 AIPE03 第四組的室內設計即時提案溝通 Agent。專案把平面圖、住宅風格、家具資料與 Three.js 3D 場景串成一套可操作的網頁流程，協助設計師快速和使用者確認空間方向。

## 快速上手(先看這裡)

```bash
# 0. 需求:Python 3.12+、uv；只有修改 React 原始碼時需要 Node.js
# 1. 安裝依賴(第一次或依賴變動後)
uv sync --extra server --extra vision

# 2. 啟動主網站 —— 必須在 repo 根目錄執行
uv run --extra vision uvicorn roompilot.server.main:app --port 8002
# 開 http://127.0.0.1:8002 → 首頁 /styles /library /scene /panorama
# /scene 已是完整 React/R3F 流程，不必另開 5173
# (--extra vision 供 PNG/JPG 平面圖辨識;省略也能跑,但 /api/floorplan/recognize 會回 503)

# 3.(只有修改前端時)重建由 FastAPI 交付的 R3F 產品頁
cd frontend3d && npm ci && npm run build

# 4.(可選)驗證安裝
uv run pytest tests/ -q                                  # 引擎與資料契約測試
uv run python roompilot/upgrade3d/eval_window_merge.py   # 窗辨識 eval
```

Windows 已有虛擬環境:`.venv\Scripts\python.exe -m uvicorn roompilot.server.main:app --port 8002`。
連接埠被占用時換 `--port 8010` 即可。

## 現行流程

```text
建立或續作專案
→ 上傳平面圖，在辨識後 2D 牆線沿牆拉出已知牆寬並輸入公分
→ 離線分房 + OpenRouter 空間屬性建議
→ 使用者在 2D 畫面確認房型並補正門窗
→ 基礎需求問卷；需要時展開逐房客製與特殊需求
→ 本機規則／OpenRouter 整理 JSON，再由使用者明確確認
→ Agent／本機規則逐房選件，家具引擎以公分計算單一 2D 配置
→ 使用者在 2D 拖曳／旋轉並經引擎驗證，確認後進入 3D 白模
→ 在 3D 場景檢視並微調室內配置、鎖定視角
→ 選擇色卡並儲存最終 PNG
```

> 詳細規劃、分工與時程以團隊 SSOT《[RoomPilot_現行版本總覽](docs/01_專題進度/RoomPilot_現行版本總覽.md)》為準。

## 主要功能

### 六種住宅風格

目前網站提供北歐、日式、現代簡約、奶油、工業與美式六種風格，每種風格包含三組生活情境色調。使用者選定色調後，可把風格、主色與材質方向帶入 3D 場景。

### 家具資料庫

- 左側依空間、類型、風格、尺寸、顏色、材質與關鍵字篩選家具。
- 家具資料由後端搜尋及分頁，每次只回傳目前頁面需要的資料。
- 右側顯示單件家具資訊與 Three.js 模型預覽。
- 家具可加入本次方案清單，再一起帶入 3D 場景。
- 家具中文名稱、尺寸、顏色、材質、風格候選與模型來源由統一 catalog 管理。

### 3D 場景與需求問答

- 支援上傳平面圖、填寫空間類型與房間尺寸。
- 固定選項與聊天補充欄位會隨問題一起顯示。
- 可承接風格頁選定的色調，以及家具資料庫建立的方案清單。
- 生成前會檢查空間資料與家具需求，避免只顯示空白場景。
- 支援家具選取、前後左右微調、旋轉、貼牆與房間邊界限制。
- 牆面與地板使用不同資料來源，可套用連續木紋或磁磚材質。

### 專案建立與續作

- 8002 的 `/scene` 第一次開啟會先要求建立專案，成功後進入上傳平面圖；不需要另開 Vite 網頁。
- 專案以 SQLite 儲存在 `.runtime/projects.sqlite3`；原始平面圖放在 `.runtime/uploads/`，兩者皆不進 Git。
- 瀏覽器網址使用 `?project_id=...` 載入同一專案，`localStorage` 只作離線快取，伺服器資料才是正式版本。
- 可用 `ROOMPILOT_RUNTIME_DIR=/absolute/path` 指定執行資料目錄；啟動不會自動掃描或匯入其他 worktree。
- workflow 更新需帶 `expected_revision`，過期版本回傳 HTTP 409，避免多分頁無聲覆寫。
- `POST /api/projects/{id}/floorplan` 保存 DXF／PNG 原檔；`POST /api/projects/{id}/floorplan/analyze` 以同一原檔產生並保存 canonical 幾何，重新整理不需靠瀏覽器記住辨識結果。
- `POST /api/projects/{id}/floorplan/calibrate` 接收辨識後牆線上的 `reference_cm` 與實際公分數，並以公分重新換算全圖比例；校正時只重跑離線幾何，沿用既有 OpenRouter 建議，不再次外送影像。
- PNG 辨識只有在請求明確帶 `allow_openrouter=true` 且伺服器設有 `OPENROUTER_API_KEY` 時才會把影像送到 OpenRouter；DXF 不外送，改讀取 TEXT／MTEXT 房名。
- 房型、門窗與空間屬性在分析後都屬於建議；`POST /api/projects/{id}/floorplan/confirm` 經使用者逐房確認後，才把定稿版保存到 `workflow.data.space_confirmation` 供後續流程使用。
- `POST /api/projects/{id}/requirements/analyze` 只整理候選需求，不改變專案 revision；一般勾選不呼叫 LLM，只有進階自由文字、`allow_openrouter=true` 且伺服器允許時才外送。
- `POST /api/projects/{id}/requirements/confirm` 會重新驗證房間／房型、六風格 ID 與指定家具 GLB，經使用者勾選確認後才保存到 `workflow.data.requirements`，並使舊的 2D／3D 下游結果失效。
- `POST /api/projects/{id}/layout-2d/analyze` 產生一版逐房家具配置但不修改 revision；OpenRouter 僅在使用者另行同意時收到需求限制與候選家具 ID，回應會再經型錄白名單驗證，座標始終由 `roompilot.engine` 計算。
- `POST /api/projects/{id}/layout-2d/validate` 驗證拖曳／旋轉後的房間邊界、碰撞、家具開合與門口淨空；`POST /api/projects/{id}/layout-2d/confirm` 會再次驗證完整配置、確保問卷指定型號仍存在，經使用者確認才保存到 `workflow.data.layout_2d`。
- `POST /api/projects/{id}/viewpoint/confirm` 以公分保存攝影機位置／目標與 FOV；重新鎖定會使舊色卡設定失效。
- `POST /api/projects/{id}/style-card/apply` 套用 18 色卡之一；`selection_source=user`／`user_required=true` 的家具型號受保護，其餘家具同類換選後重新交由引擎擺放。
- `POST /api/projects/{id}/renders` 只接受 P0 最終 PNG，另以 `render_outputs` 保存白模／取景／色卡版本血統；`GET /api/projects/{id}/renders` 與下載端點提供歷史版本。PDF 報告列 P1。

## 載入效能

前端不再讓所有頁面共同下載完整家具 catalog，而是依頁面取得必要資料：

| 頁面 | API | 回傳內容 |
|---|---|---|
| 首頁 | `/api/home-data` | 專案摘要與首頁資訊 |
| 風格頁 | `/api/styles` | 風格、色卡、示意圖與說明 |
| 家具庫 | `/api/furniture` | 篩選後的分頁家具 |
| 家具詳情 | `/api/furniture/{id}` | 單件家具完整資料 |
| 3D 場景 | `/api/scene/bootstrap` | 問卷、風格與材質必要資料 |

家具 catalog 會在伺服器端建立記憶體快取，API 再從快取結果進行搜尋、篩選與分頁，避免每次換頁重新合併全部家具。

## 專案結構

| 路徑 | 用途 |
|---|---|
| `roompilot/engine/` | 家具擺放、碰撞與淨空檢查 |
| `roompilot/upgrade3d/` | DXF 轉 3D 樓面資料 |
| `roompilot/floorplan/` | PNG 平面圖轉 DXF |
| `roompilot/catalog/` | 家具 catalog、風格與資料轉接 |
| `roompilot/agent/` | Agent 擺放語意提示與失敗修復 |
| `roompilot/server/` | FastAPI、專案 API、嚴格選件與 2D 配置協調 |
| `frontend3d/` | `/scene` 的 React 全流程與 React Three Fiber 3D 編輯器；建置產物由 FastAPI 交付 |
| `scripts/` | IKEA 型錄管線(下載/清洗/匯入) |
| `dataset/` | 素材與資料原料:IKEA GLB、`catalog_json/`、`style_rag/`、材質包 |
| `testdata/` | 測試圖資:dxf / dxf_scale / json / png / pngans 等,floor21 為 Demo 基準 |
| `tests/` | 自動化測試 |
| `docs/` | `01_專題進度/`(SSOT)、`04_契約與規格/`、`05_狀態與稽核/`、`archive/` |

> 啟動方式見最上方「快速上手」。詳細規劃與分工以 `docs/01_專題進度/RoomPilot_現行版本總覽.md` 為準。

## 測試

```powershell
uv run pytest tests/ -v
```

`frontend3d` 另以 `npm test` 驗證專案快取、上傳／同牆校尺／確認 revision、房型修正、門窗草稿、需求問卷與 2D 配置契約。

## 模型與私密檔案

- `.glb` 模型屬於本機或外部資料資產，不納入 `bella` 分支版本控制。
- `.env` 不得提交；請由 `.env.example` 建立本機設定。
- `PROJECT_CONTEXT.md` 與 `CODEX_PROJECT_RULES.md` 屬於本機工作規則，不上傳 GitHub；`AGENTS.md` 不由 `bella` 修改。
- 前端透過 `/api/furniture/{id}/model` 取得後端解析的家具模型。

## 目前待辦

- 家具類型名稱與圖示要依使用者選擇的空間動態更換。
- 裝飾品排除燈具，燈具維持獨立分類。
- 家電不顯示於家具資料庫，只在 3D 場景依空間與需求配置。
- 3D 場景 Step 2 提供更換已選風格，並保留已填空間資料與特殊需求。
- 持續依模型與資料欄位稽核結果補齊 catalog。

## 詳細改動

本次 `bella` 分支的完整改動內容請見 [Bella 分支目前改動摘要](docs/BELLA_CHANGE_SUMMARY_2026-07-11.md)。
