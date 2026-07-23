# RoomPilot-Agent

## 團隊目錄與合併規則

RoomPilot 直接使用 `backend/` 作為 Python 套件，與 Yen 分支及團隊
既有的 `backend/frontend/data` 結構一致；不再建立
不再保留舊版巢狀後端命名。

| 負責人 | 唯一主要目錄 | 功能 |
|---|---|---|
| Cody | `backend/floorplan/`、`backend/upgrade3d/` | PNG、DXF、牆與門窗辨識 |
| Kai | `backend/catalog/` | 家具型錄、AWS Manifest、CloudFront 與隔離資料 |
| Django | `backend/spatial_data/` | 房間長寬、面積、比例及尺寸標註 |
| Yen | `backend/agent/` | 家具選件與擺放失敗修復策略 |
| AN | `backend/engine/` | 家具座標、碰撞與淨空檢查 |
| Bella | `backend/server/`、`frontend3d/` | FastAPI、1–10 流程、2D／3D UI |

Agent、家具引擎與前後端的欄位及 fallback 規則，請見
[Agent 前後端契約](docs/contracts/AGENT_FRONTEND_BACKEND_CONTRACT.md)。

### 路徑規則

| 來源 | 合併落點 |
|---|---|
| `backend/floorplan/` | `backend/floorplan/` |
| `backend/upgrade3d/` | `backend/upgrade3d/` |
| `backend/catalog/` | `backend/catalog/` |
| `backend/agent/` | `backend/agent/` |
| `backend/engine/` | `backend/engine/` |
| `backend/server/` | `backend/server/` |
| `frontend/` | 第一階段不覆蓋正式網頁；靜態網站維持 `backend/server/static/` |
| `data/dataset/` | 不搬大型 GLB；型錄 metadata 放 `backend/catalog/data/` |
| `data/testdata/` | `testdata/` |
| `Final-Project_Version3/` | 只移植空間邏輯到 `backend/spatial_data/` |

### 合併方式

團隊分支雖然使用相同 `backend/` 結構，仍不得把舊分支整支 merge
到 Bella。必須先從 Bella 建立整合分支，確認差異與組員責任範圍：

```powershell
git fetch origin
git switch bella
git switch -c integration/<name>-into-bella
git diff --name-status bella...origin/<member-branch>
git log --oneline bella..origin/<member-branch>
```

整合者只挑選組員責任範圍內的 commit 或變更，再依正式契約修正
import、路徑與欄位。發生衝突時不能以整份 ours／theirs 覆蓋另一方，
也不要帶入第二套 FastAPI、重複前端或整包大型模型。

合併前必須執行：

```powershell
uv run pytest tests/ -q
git diff --check
git status --short
```

共同規則：

1. 每位成員只修改自己的主要目錄與對應測試。
2. Bella 可以在 `backend/server/` 串接模組，但不複製其他人的演算法。
3. 家具座標只能由 AN 的 `backend/engine/` 計算。
4. 跨模組幾何資料一律使用公分，新欄位的長度與座標以 `_cm` 命名。AN／Yen 既有契約的 `width`、`depth`、`pos_x`、`pos_y` 為避免破壞相容性暫不改名，但 payload 必須帶 `coordinate_unit: "cm"` 與 `schema_version`。DXF、GLB 與影像辨識 adapter 可在內部讀取檔案原生單位、glTF 公尺或像素，但輸出給其他模組前必須轉成公分；面積維持 `_m2`。
5. Kai 尚未安全對應的家具放在
   `backend/catalog/data/quarantine/unmatched_cloud_furniture/`，目前網頁、
   Agent 與 3D 場景都不得使用。

RoomPilot 是 AIPE03 第四組的室內設計即時提案溝通 Agent。專案把平面圖、住宅風格、家具資料與 Three.js 3D 場景串成一套可操作的網頁流程，協助設計師快速和使用者確認空間方向。

目前版本整合 Cody 平面圖辨識、十步驟提案流程、2D 家具配置、3D
白模、即時 PBR StylePack、方案鎖定、遠端 AI 渲染、專案持久化與室內漫遊。跨模組責任與接入
狀態請見 [RoomPilot 現行版本總覽](docs/RoomPilot_現行版本總覽.md)。

## 現行流程

```text
1 建立專案
→ 2 上傳 PNG／JPG／DXF 平面圖
→ 3 拉取兩點並確認公分尺度
→ 4 確認房間尺寸、面積、牆、門、窗、樑與柱
→ 5 填寫全屋基本問卷與逐房需求
→ 6 產生並修正 2D 家具配置
→ 7 升維為可編輯的 3D 白模
→ 8 套用六種風格、18 張色卡與即時 PBR 材質
→ 9 核對完整方案，最後鎖定一個色卡比較視角
→ 10 固定場景比較色卡，再逐房保存視角並送往遠端渲染
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
- 家具座標仍由 `backend.engine` 驗證碰撞、淨空、貼牆與房間邊界。
- 3D 白模沿用已確認的牆體與家具配置，並可載入真實 GLB。
- 即時寫實提供娃娃屋、正俯視與室內第一人稱漫遊；室內模式支援點地移動、拖曳轉頭、滾輪縮放、WASD／方向鍵與牆體碰撞。
- 牆段端點重疊並補頂面，避免牆中縫隙；室內視角固定眼睛高度並限制垂直俯仰，避免越出牆外。
- 3D 地板會從玄關開始顯示避牆的室內動線，並連接主要門洞。
- 系統可依房間與風格自動配置窗簾、地毯、植栽與燈具，並避免相同家具重複選配。
- 牆面與地板使用獨立材質目錄，可呈現木材、磁磚與塗料貼圖。

### 相對 `main` 新增的主要功能

1. **平面圖辨識與確認**：新增 Cody adapter、PNG/JPG 分析、DXF 轉接、OCR 房名、門窗候選、房間幾何、兩點公分尺度校正與人工確認 API。
2. **完整使用者流程**：把單頁展示改為建立專案、上傳、尺度、空間結構、需求問卷、2D 配置、3D 白模、即時寫實、方案鎖定與 AI 渲染十步驟流程，加入逐步阻擋原因與恢復進度。
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
| `backend/engine/` | 家具擺放、碰撞與淨空檢查 |
| `backend/upgrade3d/` | DXF 轉 3D 樓面資料 |
| `backend/floorplan/` | PNG 平面圖轉 DXF |
| `backend/catalog/` | 家具 catalog、風格與資料轉接 |
| `backend/server/` | FastAPI、頁面 API 與靜態前端 |
| `frontend3d/` | React Three Fiber 3D 編輯器 |
| `tests/` | 自動化測試 |
| `docs/` | 現行文件、摘要與資料契約 |

StylePack 的欄位、鎖定與套用規則請見
[StylePack 渲染契約](docs/contracts/STYLEPACK_RENDERING_CONTRACT.md)。

## 啟動方式

請在 repo 根目錄執行。

### 使用 uv

```powershell
uv sync --extra server
uv run uvicorn backend.server.main:app --port 8002
```

### Windows 已有虛擬環境

```powershell
.venv\Scripts\python.exe -m uvicorn backend.server.main:app --port 8002
```

啟動後開啟：<http://127.0.0.1:8002>

如果 `8002` 已被占用，可改用其他連接埠，例如 `--port 8010`。

## 家具模型來源與離線備援

正式環境使用 Kai 維護的 CloudFront Manifest。伺服器預設採用嚴格雲端模式，不會在連線失敗時悄悄改讀本機檔案，避免資料版本不一致。

完整的雲端對應、隔離與 fallback 規則請見
[家具模型交付契約](docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md)。

離線備援使用下列 IKEA 中文命名家具包。這份固定資產經驗證含有
1,517 個 GLB，可唯一提供 1,508 件家具模型；8 個未入型錄變體不
顯示，另有 1 個重複模型只對應同一件家具。雲端未對應隔離清單與
離線備援是不同集合，不可互相代替：

```text
檔名：ikea抓取家具glb_中文命名版-20260703T022419Z-3-001.zip
GLB：1,517 個，其中 1,508 件可供目前網站型錄使用
SHA-256：5AFB7B192BDCFE3BB4B303FA554AAB30DB01023318CB24661C22A78505E377A8
```

大型備援包不納入 Git。使用前先驗證，不需解壓：

```powershell
uv run python scripts/verify_ikea_offline_backup.py "D:\RoomPilot-assets\ikea抓取家具glb_中文命名版-20260703T022419Z-3-001.zip"
```

只有驗證顯示 `可用型錄家具：1,508`、SHA-256 正確且無歧義時，才在 `.env` 切換：

```dotenv
ROOMPILOT_MODEL_DELIVERY_MODE=local
ROOMPILOT_EXTERNAL_GLB_ZIP_DIRS=D:\RoomPilot-assets\ikea抓取家具glb_中文命名版-20260703T022419Z-3-001.zip
```

重新啟動 FastAPI 後，檢查家具資料庫可取得模型，並在 3D 場景實際載入至少一件家具。雲端恢復後把模式改回 `cloudfront` 並重新啟動；不要使用未定義的 `auto` 模式。

## 測試

```powershell
uv run pytest tests/ -v
```

## 版本控制規則

- `.env` 不得提交；請由 `.env.example` 建立本機設定。
- 大型 `.glb` 不直接加入新提交；正式家具模型由已驗證的 CloudFront Manifest 提供。
- IKEA 1,508 件離線備援包只存放於受控的外部資產目錄，不解壓或提交至 repo。
