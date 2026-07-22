# RoomPilot-Agent

RoomPilot 是 AIPE03 第四組的室內設計即時提案溝通 Agent。專案把平面圖、住宅風格、家具資料與 Three.js 3D 場景串成一套可操作的網頁流程,協助設計師快速和使用者確認空間方向。

> 詳細規劃、分工與時程以團隊 SSOT《[RoomPilot_現行版本總覽](docs/01_專題進度/RoomPilot_現行版本總覽.md)》為準。

## 安裝流程

### 需求

- Python 3.12+ 與 [uv](https://docs.astral.sh/uv/)
- Node.js 20+(只有修改 React 前端原始碼時需要;repo 已含建置產物)

### 步驟

```bash
# 1. 取得原始碼
git clone <repo-url> && cd RoomPilot-Agent

# 2. 安裝 Python 依賴(第一次或依賴變動後)
uv sync --extra server --extra vision

# 3. 建立本機環境設定(選配;不設定也能跑,只是所有 OpenRouter 輔助功能停用)
cp .env.example .env
# 編輯 .env 填入 OPENROUTER_API_KEY;模型池等其餘欄位有預設值

# 4.(只有修改前端時)安裝並重建由 FastAPI 交付的 React 產品頁
cd frontend && npm ci && npm run build && cd ..
# 建置產物進 backend/server/static/frontend3d/,改完前端不重建的話 8002 看不到變更

# 5. 驗證安裝
uv run pytest tests/ -q                                   # 後端引擎與資料契約測試
uv run python backend/upgrade3d/eval_window_merge.py      # 窗辨識 eval
cd frontend && npm test                                   # 前端純邏輯測試(有裝 Node 時)
```

### 啟動

```bash
# 必須在 repo 根目錄執行(相對 import 與資料路徑)
uv run --extra vision uvicorn backend.server.main:app --port 8002
# 開 http://127.0.0.1:8002 → 首頁 /styles /library /scene /panorama
```

- `/scene` 已是完整 React/R3F 流程,不必另開 5173;`npm run dev` 只供前端開發熱更新(`/api` 代理到 8002)。
- `--extra vision` 供 PNG 平面圖辨識;省略也能跑,但 `/api/floorplan/recognize` 會回 503。
- 連接埠被占用時換 `--port 8010` 即可。
- 專案資料存在 `.runtime/`(SQLite + 上傳原檔,不進 Git);可用 `ROOMPILOT_RUNTIME_DIR=/absolute/path` 改放他處。

## 現行流程

```text
建立或續作專案
→ 上傳平面圖(DXF/PNG),在辨識後 2D 牆線沿牆拉出已知牆寬並輸入公分校尺
→ 離線分房 + OpenRouter 空間屬性建議(需使用者同意)
→ 使用者在 2D 畫面確認房型並補正門窗
→ 基礎需求問卷;需要時展開逐房客製與特殊需求(LLM→JSON,需同意)
→ Agent/本機規則逐房選件,家具引擎以公分計算 2D 配置
→ 使用者在 2D 拖曳/旋轉並經引擎驗證,確認後進入 3D 白模
→ 3D 檢視、鎖定視角 → 套用 18 色卡 → 儲存最終提案 PNG
```

## 專案 API 一覽

所有階段都遵守同一套原則:**分析類端點只產生建議、不改 revision;確認類端點才寫入正式資料**,workflow 更新需帶 `expected_revision`(過期回 409)。影像與自由文字只有在請求明確帶 `allow_openrouter=true` 且伺服器設有 `OPENROUTER_API_KEY` 時才外送;DXF 一律不外送。家具座標始終由 `backend.engine` 計算,OpenRouter 只能從候選 ID 選件。

| 階段      | 端點(`/api/projects/{id}/…`)                                                                                             |
| --------- | --------------------------------------------------------------------------------------------------------------------------- |
| 平面圖    | `floorplan`(存原檔)、`floorplan/analyze`、`floorplan/calibrate`(公分校尺)、`floorplan/confirm`                      |
| 需求      | `requirements/analyze`、`requirements/confirm`(確認後使下游 2D/3D 失效)                                                 |
| 2D 配置   | `layout-2d/analyze`、`layout-2d/validate`(拖曳/旋轉驗證)、`layout-2d/confirm`                                         |
| 3D 與輸出 | `viewpoint/confirm`(公分保存攝影機)、`style-card/apply`(18 色卡,使用者指定家具受保護)、`renders`(最終 PNG 與歷史版本) |

頁面資料 API 依頁面分拆(`/api/home-data`、`/api/styles`、`/api/furniture`、`/api/scene/bootstrap`),家具 catalog 在伺服器端記憶體快取後搜尋分頁,前端不下載完整 catalog。

## 專案結構

| 路徑                   | 用途                                                                                  |
| ---------------------- | ------------------------------------------------------------------------------------- |
| `backend/engine/`    | 家具擺放、碰撞與淨空檢查(唯一能算家具座標的模組)                                      |
| `backend/upgrade3d/` | DXF 轉 3D 樓面資料                                                                    |
| `backend/floorplan/` | PNG 平面圖轉 DXF(牆正交化+門窗偵測)                                                   |
| `backend/catalog/`   | 家具 catalog、風格與資料轉接                                                          |
| `backend/agent/`     | Agent 選件與擺位紀律(knowledge/select/place;LLM 只選件不出座標)                       |
| `backend/server/`    | FastAPI、專案 API、嚴格選件與 2D 配置協調                                             |
| `frontend/`          | `/scene` 的 React 全流程與 R3F 3D 編輯器;建置產物由 FastAPI 交付                    |
| `data/dataset/`      | 素材原料:IKEA GLB、`catalog_json/`、`style_rag/`、材質包                          |
| `data/testdata/`     | 測試圖資:dxf / dxf_scale / json / png / pngans 等,floor21 為 Demo 基準                |
| `tests/`             | 後端自動化測試                                                                        |
| `docs/`              | 資料夾總覽、`01_專題進度/`(SSOT)、`04_契約與規格/`、`ai-harness/`、`archive/` |

## 測試

```bash
uv run pytest tests/ -v          # 後端
cd frontend && npm test          # 前端純邏輯(node --test src/lib/*.test.js)
```

## 模型與私密檔案

- 既有 `data/dataset/` GLB 是專案資料資產;新增大型模型前先由組長確認,不要直接整批加入。
- `.env` 不得提交;請由 `.env.example` 建立本機設定。
- runtime 專案、個人筆記與暫存輸出不進版控;`CLAUDE.md` 是正式協作規則。
- 前端透過 `/api/furniture/{id}/model` 取得後端解析的家具模型。

## 進一步閱讀

- [資料夾功能總覽](docs/資料夾功能總覽.md)
- [現行版本 SSOT](docs/01_專題進度/RoomPilot_現行版本總覽.md)
- [ben-dev 功能整合來源報告](docs/01_專題進度/RoomPilot_ben-dev_功能整合來源報告_2026-07-19.md)
