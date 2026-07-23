# RoomPilot-Agent

## 團隊目錄與合併規則

Bella 保留 `roompilot/` 作為 Python 套件，不另外建立重複的
`backend/`。組員舊分支若採用先前的 `backend/frontend/data` 結構，
請依下表移植到 Bella。

| 負責人 | Bella 唯一主要目錄 | 功能 |
|---|---|---|
| Cody | `roompilot/floorplan/`、`roompilot/upgrade3d/` | PNG、DXF、牆與門窗辨識 |
| Kai | `roompilot/catalog/` | 家具型錄、AWS Manifest、CloudFront 與隔離資料 |
| Django | `roompilot/spatial_data/` | 房間長寬、面積、比例及尺寸標註 |
| Yen | `roompilot/agent/` | 家具選件與擺放失敗修復策略 |
| AN | `roompilot/engine/` | 家具座標、碰撞與淨空檢查 |
| Bella | `roompilot/server/`、`frontend3d/` | FastAPI、1–8 流程、2D／3D UI |

### 舊分支路徑對照

| 組員舊路徑 | Bella 合併落點 |
|---|---|
| `backend/floorplan/` | `roompilot/floorplan/` |
| `backend/upgrade3d/` | `roompilot/upgrade3d/` |
| `backend/catalog/` | `roompilot/catalog/` |
| `backend/agent/` | `roompilot/agent/` |
| `backend/engine/` | `roompilot/engine/` |
| `backend/server/` | `roompilot/server/` |
| `frontend/` | 靜態網站放 `roompilot/server/static/`；R3F 放 `frontend3d/` |
| `data/dataset/` | 不搬大型 GLB；型錄 metadata 放 `roompilot/catalog/data/` |
| `data/testdata/` | `testdata/` |
| `Final-Project_Version3/` | 只移植空間邏輯到 `roompilot/spatial_data/` |

### 合併方式

不要把包含整份 `backend/`、`frontend/`、`data/` 的舊分支直接執行一般
`git merge`。先從 Bella 建立整合分支並查看差異：

```powershell
git fetch origin
git switch bella
git switch -c integration/<name>-into-bella
git diff --name-status bella...origin/<member-branch>
```

只將成員負責的實作移到上表指定目錄，並將 import 改成
`roompilot.<module>`。不要帶入第二套 FastAPI、重複前端或整包大型模型。

合併前必須執行：

```powershell
uv run pytest tests/ -q
git diff --check
git status --short
```

共同規則：

1. 每位成員只修改自己的主要目錄與對應測試。
2. Bella 可以在 `roompilot/server/` 串接模組，但不複製其他人的演算法。
3. 家具座標只能由 AN 的 `roompilot/engine/` 計算。
4. Python 內部一律使用公尺；公分只出現在既有 catalog 與前端 payload 邊界。
5. Kai 尚未安全對應的 1,514 件家具放在
   `roompilot/catalog/data/quarantine/unmatched_cloud_furniture/`，目前網頁、
   Agent 與 3D 場景都不得使用。

RoomPilot 是 AIPE03 第四組的室內設計即時提案溝通 Agent。專案把平面圖、住宅風格、家具資料與 Three.js 3D 場景串成一套可操作的網頁流程，協助設計師快速和使用者確認空間方向。

相較於 `main`，目前版本整合 Cody 平面圖辨識、九步驟提案流程、2D 家具配置、3D 白模、即時 PBR StylePack、專案持久化與室內漫遊。

## 現行流程

```text
1 建立專案
→ 2 上傳 PNG／JPG／DXF 平面圖
→ 3–4 拉取兩點並確認公分尺度、房間尺寸與面積
→ 5 確認空間、牆、門、窗、梁與柱
→ 6 填寫全屋基本問卷與逐房需求
→ 7 產生並修正 2D 家具配置
→ 8 升維為可編輯的 3D 白模
→ 9 套用六種風格、18 張色卡與即時 PBR 材質
```

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

- 平面圖辨識以 Cody 流程為主，支援兩點尺度校正、房間語意、牆門窗與結構確認。
- 2D 家具配置承接逐房需求，可選取、拖曳、旋轉、替換與刪除家具。
- 家具座標仍由 `roompilot.engine` 驗證碰撞、淨空、貼牆與房間邊界。
- 3D 白模沿用已確認的牆體與家具配置，並可載入真實 GLB。
- 即時寫實提供娃娃屋、正俯視與室內第一人稱漫遊；室內模式支援點地移動、拖曳轉頭、滾輪縮放、WASD／方向鍵與牆體碰撞。
- 牆段端點重疊並補頂面，避免牆中縫隙；室內視角固定眼睛高度並限制垂直俯仰，避免越出牆外。
- 3D 地板會從玄關開始顯示避牆的室內動線，並連接主要門洞。
- 系統可依房間與風格自動配置窗簾、地毯、植栽與燈具，並避免相同家具重複選配。
- 牆面與地板使用獨立材質目錄，可呈現木材、磁磚與塗料貼圖。

### 相對 `main` 新增的主要功能

1. **平面圖辨識與確認**：新增 Cody adapter、PNG/JPG 分析、DXF 轉接、OCR 房名、門窗候選、房間幾何、兩點公分尺度校正與人工確認 API。
2. **完整使用者流程**：把單頁展示改為建立專案、上傳、尺度、空間結構、需求問卷、2D 配置、3D 白模與即時寫實九步驟流程，加入逐步阻擋原因與恢復進度。
3. **家具與軟裝引擎**：新增逐房家具需求、2D 家具圖示與尺寸、GLB 指定、15 度旋轉、貼牆候選，以及窗簾、地毯、植栽、燈具自動配置。
4. **3D 與材質**：新增六種風格、18 張色卡、牆地 PBR 貼圖、HDR 環境光、GTAO、ACES、柔和陰影、材質覆寫與 StylePack 即時切換。
5. **3D 操作與視覺修正**：新增娃娃屋自由旋轉、正俯視、室內漫遊、碰撞限制、牆體接縫修正、玄關動線與家具編號。
6. **專案持久化**：新增 project store、workflow step 儲存、3D 場景與 StylePack 恢復，重新整理後可承接既有專案。
7. **驗證**：補齊 floorplan、workflow、project API、家具配置、StylePack、材質、軟裝與 3D 視覺回歸測試。

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
| `roompilot/server/` | FastAPI、頁面 API 與靜態前端 |
| `frontend3d/` | React Three Fiber 3D 編輯器 |
| `tests/` | 自動化測試 |
| `docs/` | 現行文件、摘要與資料契約 |

## 啟動方式

請在 repo 根目錄執行。

### 使用 uv

```powershell
uv sync --extra server
uv run uvicorn roompilot.server.main:app --port 8002
```

### Windows 已有虛擬環境

```powershell
.venv\Scripts\python.exe -m uvicorn roompilot.server.main:app --port 8002
```

啟動後開啟：<http://127.0.0.1:8002>

如果 `8002` 已被占用，可改用其他連接埠，例如 `--port 8010`。

## 測試

```powershell
uv run pytest tests/ -v
```

目前完整測試基準為 `161 passed`。

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

過往網頁版改動摘要請見 [網頁版改動摘要](docs/BELLA_CHANGE_SUMMARY_2026-07-11.md)。
