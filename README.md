# RoomPilot-Agent

## IKEA 地端 GLB 備援（尚未完成）

Kai 的 CloudFront catalog 目前仍是唯一正式模型來源。Django 與 Kai 後續會共同完成本機 IKEA GLB 備援的 JSON 對照、固定備份路徑與 API 模式；完成前請勿在 `.env` 啟用本機模式，也不要將大型 GLB 提交到 Git。已清洗的網站 PBR 紋理可提交至 `frontend/pbr_assets/`。

RoomPilot 是 AIPE03 第四組的 AI 室內設計系統。它把平面圖辨識、人工
校正、逐房需求、家具資料庫、幾何配置、2D/3D 編輯、方案視角與 AI
渲染整合成一個可恢復的網頁流程。

## 快速啟動

需求：

- Windows 10/11 64-bit
- Python 3.12
- Git
- PostgreSQL 17：第 6 步正式家具 catalog 的優先資料來源

### 方式一：Python venv 與 requirements.txt

在 repo 根目錄開啟 PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe -m uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload
```

開啟 <http://127.0.0.1:8002>。

如果 `8002` 已占用，把指令改成 `--port 8023` 或其他未使用連接埠。
若既有 `.venv\Scripts\python.exe` 指向已移除的舊 Python 路徑，先把
舊 `.venv` 重新命名備份，再執行上面的建立指令。

### 方式二：uv

日常開發不含大型 OCR：

```powershell
uv sync --extra server --extra vision --extra catalog --group dev
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uv run uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload
```

需要 PaddleOCR 時，使用完整環境：

```powershell
uv sync --extra server --extra vision --extra catalog --extra ocr --group dev
```

使用 pip 的 OCR 鎖定版本：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ocr.txt
```

OCR 套件較大，且不是啟動網站或執行目前標準測試的必要條件。

需要 CubiCasa 語意房型辨識時（`backend/floorplan/infer_cubicasa.py` 需要
torch），再加 `semantic`：

```powershell
uv sync --extra server --extra vision --extra catalog --extra semantic --group dev
```

不裝也不會壞：房型會退回面積規則，分析照常完成，`cody_room_semantics.room_label_source`
會標示 `area_rules` 而非 `cubicasa_semantic`。torch 會連帶拉進 CUDA 相依套件，
因此與 OCR 同樣不放進預設環境。

## 驗證指令

```powershell
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
git status --short
```

平面圖辨識：

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_floorplan_vision.py tests/test_floorplan_vision_api.py
```

網頁流程與專案恢復：

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_scene_workflow.py tests/test_project_workflow_api.py tests/test_scene_v2_contract.py
```

## 現行八步流程

```text
1 建立專案
-> 2 上傳 PNG/JPG/DXF 平面圖
-> 3 兩點標定並確認公分尺度
-> 4 校正空間、牆、門、窗、樑與柱
-> 5 先選全屋風格、材質與冷氣範圍，再逐房確認用途、家具類型、尺寸與數量
-> 6 產生配置，在同一畫面同步編輯 2D/3D 家具與走動預覽
-> 7 鎖定方案，每個空間選擇並微調生成視角
-> 8 AI 渲染與成果包：依問卷、家具、材質、色卡與視角產生逐房成果
```

未處理的家具碰撞、淨空、超界或模型載入問題會阻擋下一步。結構變更
必須回到第 4 步，系統會重新驗證目前家具。

## 系統架構

詳細圖解請見 [使用者流程與系統架構圖](docs/使用者流程與系統架構圖.md)。

```text
瀏覽器 HTML/CSS/JavaScript/Three.js
  <-> FastAPI API 與專案持久化
      -> Cody 平面圖辨識
      -> Django 空間關係與 layout evaluation
      -> layout_json
      -> Yen 需求解析與家具選擇
      -> Kai catalog / AWS / PostgreSQL / 關係檢索
      -> Ancai 幾何配置、碰撞與淨空
      -> scene_json
      -> Bella 2D/3D 編輯、方案與渲染流程
```

Graph RAG 只負責房間、家具、風格、材質與限制關係的檢索和證據，
不負責幾何、碰撞、淨空或結構合法性。

## 團隊責任

| 分支／人員 | 主要路徑 | 功能 |
|---|---|---|
| Bella | `backend/server/`, `frontend/` | FastAPI、專案、八步流程、2D/3D UI、整合 |
| Cody | `backend/floorplan/`, `backend/upgrade3d/` | PNG/DXF、牆門窗房間辨識、`layout_json` |
| Django | `backend/spatial_data/`, floorplan spatial helpers | 房間尺寸、面積、關係、layout evaluation、RAG 關係 |
| Kai | `backend/catalog/`, `JSON/`, `scripts/sql/` | 家具型錄、AWS/CloudFront、Manifest、PostgreSQL |
| Yen | `backend/agent/` | 需求結構化、選件、排序、修復意圖與說明 |
| Ancai | `backend/engine/` | 家具座標、碰撞、淨空、移動與合法性 |
| Ben | `testdata/`, evaluation/docs support | 辨識資料 QA、模型評估與版本證據 |

AI 或新成員開始修改前，必須依序閱讀：

1. [AGENTS.md](AGENTS.md)
2. [CLAUDE.md](CLAUDE.md)
3. [團隊 AI ownership 與架構](docs/TEAM_AI_OWNERSHIP.md)
4. `docs/owners/` 內對應成員檔案
5. 目標資料夾內的 `AGENTS.md`
6. 相關 `docs/contracts/`

跨資料夾修改前必須列出雙方 owner、資料契約、修改原因與兩側測試。

## 主要資料夾

| 路徑 | 用途 |
|---|---|
| `backend/agent/` | 需求與家具決策 |
| `backend/catalog/` | 家具、材質與正式雲端 catalog |
| `backend/engine/` | 幾何擺放與驗證 |
| `backend/floorplan/` | 平面圖辨識與確認 |
| `backend/spatial_data/` | 空間關係與 evaluation 的共享邊界 |
| `backend/server/` | 正式 FastAPI 與 production frontend |
| `backend/upgrade3d/` | 已確認格局轉 3D 幾何 |
| `JSON/` | Catalog/manifest 交接資料 |
| `scripts/sql/` | PostgreSQL schema 與匯入 |
| `testdata/` | 小型辨識測資與 ground truth |
| `tests/` | 單元、API、契約與視覺回歸測試 |
| `docs/contracts/` | 跨模組資料契約 |

## 關鍵資料契約

- 跨模組長度與座標使用公分，新欄位以 `_cm` 結尾。
- 面積使用 `_m2`。
- 相容欄位 `width`, `depth`, `pos_x`, `pos_y` 必須搭配
  `coordinate_unit: "cm"` 和 schema version。
- 平面圖辨識輸出是 `layout_json`。
- 方案生成與編輯輸出是 `scene_json`。
- 家具是否合法只能由 `backend/engine/` 判斷。
- Production frontend 只有 `frontend/` 一套，不另建第二套。

更多契約：

- [Layout 與 Scene 邊界](docs/contracts/LAYOUT_SCENE_BOUNDARY_CONTRACT.md)
- [Agent 前後端契約](docs/contracts/AGENT_FRONTEND_BACKEND_CONTRACT.md)
- [家具模型交付](docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md)
- [StylePack 渲染](docs/contracts/STYLEPACK_RENDERING_CONTRACT.md)

## 家具資料與 PostgreSQL

正式雲端 catalog 由 Kai 的資料流維護：

- Kai 官方 JSON catalog：8,557 筆；目前為 API 與本機開發的預設資料來源
- PostgreSQL：完成 Kai 匯入後才以 `ROOMPILOT_CATALOG_PROVIDER=postgres` 明確啟用
- 每筆具有 CloudFront GLB 與正面、側面、45 度 PNG
- 資料來源切換：預設讀取上述 Kai JSON；僅在明確設定 PostgreSQL provider 時才讀取資料庫
- 家電問卷需求會保留給 AI 生圖，不會進入第 6 步 2D/3D 擺設

先建立 `.env`：

```dotenv
DB_HOST=localhost
DB_PORT=5432
DB_NAME=roompilot_db
DB_USER=postgres
DB_PASSWORD=安裝 PostgreSQL 時自行設定的密碼
```

網站預設嘗試 PostgreSQL。若本機尚未匯入或資料庫暫時不可連線，會自動
使用已驗證 JSON 備援；如需強制使用 JSON 進行離線開發，可在 `.env` 加入：

```dotenv
ROOMPILOT_CATALOG_PROVIDER=json
```

Dry-run：

```powershell
.\.venv\Scripts\python.exe scripts/sql/import_official_catalog_to_postgres.py --dry-run
```

正式匯入：

```powershell
.\.venv\Scripts\python.exe scripts/sql/import_official_catalog_to_postgres.py
```

匯入採 transaction 與 UPSERT，預設不刪除其他資料。只有經過人工確認
才可使用 `--prune-extra`。

目前的責任、資料流與家電邊界請看
[現行版本總覽](docs/RoomPilot_現行版本總覽.md) 與
[團隊 AI 責任與整合架構](docs/TEAM_AI_OWNERSHIP.md)。

## 套件版本

Python baseline 經實際測試：

- Python `3.12.13`
- FastAPI `0.140.0`
- Uvicorn `0.51.0`
- Shapely `2.1.2`
- NumPy `2.5.1`
- OpenCV `4.13.0.92`
- ezdxf `1.4.4`
- Pillow `12.3.0`
- pytest `9.1.1`

完整 Python 直接依賴版本以 [requirements.txt](requirements.txt) 為準。
可選 OCR 版本由 `pyproject.toml` 與 `uv.lock` 管理。

前端不經打包：`frontend/` 直接以原生 ES module 載入
`vendor/three/`，沒有 Node.js 建置步驟。

## 版本控制與整合

```powershell
git fetch origin
git switch bella
git pull --ff-only origin bella
git switch -c integration/<owner>-<feature>
git diff --name-status bella...origin/<owner-branch>
git log --oneline bella..origin/<owner-branch>
```

只移植責任範圍內、符合現行契約的 commit。禁止以整份 ours/theirs
覆蓋衝突、建立第二套 FastAPI、搬入完整舊前端或提交大型模型。

不得提交：

- `.env` 或密碼
- `.runtime/` 專案資料
- `.tmp/` 與快取
- 大型 GLB、圖片包或模型權重
- 未驗證的 catalog 或自動標註結果
