# RoomPilot 現行版本總覽

本文件是 RoomPilot 團隊的現行架構與整合導航。它只描述目前程式可
核對的責任、流程、資料邊界與接入狀態，不記錄個人進度、暫時數量、
歷史測試結果或分支開發日誌。

實際欄位與行為發生衝突時，依序以自動化測試、可執行程式、正式契約
及本總覽為準。README 負責安裝與啟動，本文件負責跨模組協作。

## 產品流程

正式網頁入口為 `/scene`，目前固定為八個步驟：

| 步驟 | 名稱 | 主要結果 |
|---|---|---|
| 1 | 建立專案 | 建立 `project_id`，後續確認結果可保存 |
| 2 | 上傳平面圖 | 上傳 PNG、JPG 或 DXF，並確認圖檔內容 |
| 3 | 確定尺寸 | 以已知線段校正比例尺，跨模組尺寸使用公分 |
| 4 | 空間與結構 | 確認房間、尺寸標註、牆、門、窗、樑與柱 |
| 5 | 需求問卷 | 蒐集全屋基本資料、逐房家具與特殊需求 |
| 6 | 2D 家具配置 | Agent 選件，AN 引擎配置並驗證家具 |
| 7 | 3D 白模 | 以已確認格局與家具建立可檢查的 3D 場景 |
| 8 | 即時寫實 | 套用 StylePack、PBR 材質、燈光與真實 GLB |
| 9 | 方案鎖定 | 核對家具、格局、材質、色卡與需求，最後鎖定色卡比較視角 |
| 10 | AI 渲染 | 先以固定場景比較色卡，再逐房保存視角並送往遠端渲染 |

前一步資料改動時，依賴它的後續步驟必須失效並重新確認，不能沿用
可能已過期的 2D 或 3D 結果。

## 團隊責任

| 負責人 | 唯一主要目錄 | 責任 | 現行接入狀態 |
|---|---|---|---|
| Cody | `backend/floorplan/`、`backend/upgrade3d/` | PNG／JPG／DXF、房間、牆與門窗辨識及升維資料 | 已由 FastAPI 分析與確認流程呼叫 |
| Kai | `backend/catalog/` | 家具 metadata、CloudFront Manifest、模型對應與隔離 | 已接家具 API、Agent 候選與 3D 模型交付 |
| Django | `backend/spatial_data/` | 房間長寬、面積、比例與尺寸標註邏輯 | 目錄目前僅保留落點；現行尺寸標註 UI 位於 `backend/server/static/` |
| Yen | `backend/agent/` | 需求理解、家具選件與擺放失敗修復策略 | `request_selections()` 與 `resolve_placements()` 已接正式流程 |
| AN | `backend/engine/` | 家具座標、旋轉、碰撞、淨空與房間邊界 | 已接場景生成、重新配置與位置驗證 |
| Bella | `backend/server/`、`frontend3d/` | FastAPI、專案保存、十步驟 UI 與 2D／3D 呈現 | `backend/server/static/` 是整合網頁；`frontend3d/` 是獨立 R3F 編輯器 |

組員只在自己的主要目錄維護演算法。Bella 可在 `backend/server/`
調度模組與轉換 payload，但不複製其他組員的核心邏輯。

## 現行資料流

```text
平面圖
  -> Cody 辨識與人工確認
  -> 公分制房間／結構資料
  -> Bella 現行尺寸與比例確認（Django 模組落點保留）
  -> Bella 問卷
  -> Yen 家具選件
  -> AN 家具擺放與驗證
  -> Yen 失敗修復策略
  -> AN 重新擺放
  -> Bella 2D／3D 顯示與專案保存
  -> Kai CloudFront GLB
  -> StylePack 即時寫實
```

Agent 可以選件、排序或提出修復策略，但不能輸出合法家具座標。每次
替換或移除家具後，都必須重新呼叫 AN 引擎。

## 資料與單位

1. 跨模組長度、平面座標、位移與淨空使用公分。
2. 新增欄位以 `_cm` 表示公分；既有未帶後綴欄位必須同時提供
   `coordinate_unit: "cm"` 與 `schema_version`。
3. 房間面積使用 `_m2`，例如 `area_m2`、`net_area_m2`。
4. 角度使用度數；前後端不得默默改變旋轉方向。
5. DXF、影像與 GLB adapter 可以讀取檔案原生單位、像素或 glTF
   檔案原生單位或 glTF 公尺，但送出跨模組 payload 前必須轉成上述契約。
6. 前端不得自行實作第二套家具碰撞、淨空或合法座標演算法。

## 專案結構

| 路徑 | 用途 |
|---|---|
| `backend/floorplan/` | 平面圖辨識、正交化、房間與門窗候選 |
| `backend/upgrade3d/` | DXF 與樓面資料轉成 3D 可用結構 |
| `backend/spatial_data/` | Django 空間尺寸邏輯的指定落點 |
| `backend/catalog/` | 家具型錄、色卡、Manifest 與模型解析 |
| `backend/agent/` | Yen 選件規則與擺放失敗修復 |
| `backend/engine/` | AN 家具擺放、碰撞與淨空核心 |
| `backend/server/` | 唯一 FastAPI、工作流、專案保存與整合前端 |
| `backend/server/static/` | 正式十步驟網頁與 Three.js Viewer |
| `frontend3d/` | 獨立 React Three Fiber 編輯器及相容 API 用戶端 |
| `scripts/` | 型錄、模型與離線備援維護工具 |
| `testdata/` | 可提交的小型辨識及整合測試資料 |
| `tests/` | 後端、契約、工作流與前端靜態回歸測試 |
| `docs/contracts/` | 團隊穩定契約，不存個人進度 |
| `docs/backlog/` | 尚未完成但已確認要追蹤的工作 |

正式 Python 套件直接使用根目錄 `backend/`，不再建立
不再保留舊版巢狀後端命名。組員分支的
`backend/<module>/` 可在相同路徑進行 three-way merge，但不得帶入
第二套 FastAPI 或重複前端。

## 正式服務入口

主要頁面：

- `/`：首頁。
- `/styles`：住宅風格與色卡。
- `/library`：家具資料庫。
- `/scene`：十步驟專案流程。

主要 API：

| API | 用途 |
|---|---|
| `/api/projects`、`/api/projects/{project_id}` | 建立與讀取專案 |
| `/api/projects/{project_id}/workflow` | 保存十步驟工作流 |
| `/api/render-provider/status` | 確認遠端渲染服務是否已設定 |
| `/api/projects/{project_id}/render-jobs` | 代理色卡比較與逐房渲染任務 |
| `/api/projects/{project_id}/floorplan/analyze` | 分析專案平面圖 |
| `/api/agent/intake/start`、`/answer` | Yen 需求訪談與 fallback |
| `/api/agent/furniture/select` | 依房間與白名單選擇家具 |
| `/api/scene/generate` | 產生場景並執行擺放失敗修復 |
| `/api/scene/layout` | 由 AN 引擎重新配置家具 |
| `/api/scene/validate` | 驗證家具位置 |
| `/api/scene/decorate` | 配置可用軟裝 |
| `/api/furniture` | 搜尋及分頁家具 |
| `/api/furniture/{id}/model` | 解析並交付家具 GLB |
| `/api/catalog/status` | 檢查家具 provider 與 Manifest |

`backend/server/main.py` 是唯一正式 FastAPI。`frontend3d/` 所需舊
相容端點仍由同一個 FastAPI 提供，不另啟第二套後端。

## 家具與模型

家具 metadata 由 `backend/catalog/` 管理，正式 GLB 由 Kai 維護的
CloudFront Manifest 交付。未能可靠對應的家具必須留在 quarantine，
不得出現在網頁、Agent 或 3D 場景。

正式家具集合固定為 cloud catalog 與 Manifest 一對一共有的 9,350
件。舊六風格型錄只能為這個集合補充風格、RAG、分類與擺放提示；
無法對應的舊資料不進入正式 API。未有舊風格標籤的正式雲端家具可
保留為未分類，但不得假裝已完成風格判定。

正式環境使用嚴格 `cloudfront` 模式；連線失敗時不會自動切成本機
資料。離線備援必須先通過 README 指定的資產驗證，再由管理者明確
切換為 `local`，雲端恢復後改回 `cloudfront`。

## 已接入與尚未接入

已接入正式流程：

- 十步驟專案建立、保存、恢復與步驟阻擋。
- 第 9 步方案版本與主比較視角鎖定；第 10 步色卡比較、逐房視角與遠端渲染任務。
- Cody 平面圖分析、尺度校正及空間結構人工確認。
- Yen `request_selections()` 家具選件與 deterministic fallback。
- AN 家具配置、碰撞、淨空與位置驗證。
- Yen `resolve_placements()` 擺放失敗修復及中文報告。
- Kai CloudFront 家具模型解析與人工離線備援。
- 六種風格、18 張色卡與即時 PBR StylePack。

尚未完整接入：

- `backend/spatial_data/` 尚未放入獨立 Python 空間計算模組；現行
  尺寸標註與確認由整合前端處理。
- `LAYOUT_EVALUATION_SCHEMA.md` 的完整 `status`、`violations`、
  `warnings`、`score` 與 `validation_summary` 尚未成為正式 API。
- OpenRouter 是可選能力；未設定或失敗時必須使用本地規則，不得讓
  核心流程中斷。

## 正式契約

- [Agent 前後端契約](contracts/AGENT_FRONTEND_BACKEND_CONTRACT.md)
- [家具模型交付契約](contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md)
- [家具工程規則](contracts/FURNITURE_ENGINEERING_RULES.md)
- [配置評估 Schema](contracts/LAYOUT_EVALUATION_SCHEMA.md)
- [StylePack 渲染契約](contracts/STYLEPACK_RENDERING_CONTRACT.md)
- [遠端室內渲染契約](contracts/REMOTE_RENDER_CONTRACT.md)

契約若描述「提案」或「尚未接入」，不得在 UI、README 或總覽中宣稱
已完成。

## 合併與驗證

不要直接把舊分支整包 `merge` 到 Bella。先比較分支，再把組員負責的
程式移到唯一落點，修正 import 與契約，最後驗證：

```powershell
git fetch origin
git diff --name-status bella...origin/<member-branch>
uv run pytest tests/ -q
git diff --check
git status --short
```

合併時不得帶入第二套 `backend/`、重複的 `frontend/`、未驗證大型
GLB、個人工具設定、個人進度文件或私密 `.env`。
