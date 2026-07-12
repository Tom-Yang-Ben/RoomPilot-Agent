# RoomPilot-Agent

RoomPilot 是 AIPE03 第四組的室內設計即時提案溝通 Agent。專案把平面圖、住宅風格、家具資料與 Three.js 3D 場景串成一套可操作的網頁流程，協助設計師快速和使用者確認空間方向。

## 快速上手(先看這裡)

```bash
# 0. 需求:Python 3.12+、uv、Node.js(只有 frontend3d 需要)
# 1. 安裝依賴(第一次或依賴變動後)
uv sync --extra server --extra vision

# 2. 啟動主網站 —— 必須在 repo 根目錄執行
uv run --extra vision uvicorn roompilot.server.main:app --port 8002
# 開 http://127.0.0.1:8002 → 首頁 /styles /library /scene /panorama
# (--extra vision 供 PNG/JPG 平面圖辨識;省略也能跑,但 /api/floorplan/recognize 會回 503)

# 3.(可選)R3F 3D 編輯器
cd frontend3d && npm install && npm run dev   # 會 proxy 到 :8002

# 4.(可選)驗證安裝
uv run pytest tests/ -q                                  # 引擎與資料契約測試
uv run python roompilot/upgrade3d/eval_window_merge.py   # 窗辨識 eval
```

Windows 已有虛擬環境:`.venv\Scripts\python.exe -m uvicorn roompilot.server.main:app --port 8002`。
連接埠被占用時換 `--port 8010` 即可。

## 現行流程

```text
首頁與功能介紹
→ 選擇風格與生活色調
→ 從家具資料庫建立本次方案清單
→ 在 3D 場景補充空間資料與特殊需求
→ 生成並微調室內配置
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
| `roompilot/server/` | FastAPI、頁面 API 與靜態前端 |
| `frontend3d/` | React Three Fiber 3D 編輯器 |
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

目前完整測試基準為 `49 passed`。

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
