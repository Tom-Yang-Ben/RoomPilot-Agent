# 容器化執行指南

正式 web app（`backend/server/` + `frontend/` 八步流程）的容器化。辨識、選件、
幾何合法性都在同一個行程內，所以只有一個 app 服務，不拆微服務。

## 快速開始

```powershell
# 前置：.env 已存在且 DB_PASSWORD 已填（複製自 .env.example）
docker compose up --build
```

開 <http://127.0.0.1:8002>。首次建置約 10–15 分鐘（torch CPU wheel 與 DINOv2
骨幹要下載），之後有 layer 快取。

停止與清除：

```powershell
docker compose down            # 保留 roompilot-runtime volume
docker compose down -v         # ⚠ 連 volume 一起刪，等於清空所有專案與帳號
```

## 四個決策（2026-08-05 Ben 拍板）

| 決策 | 選擇 | 代價 |
|---|---|---|
| torch | 裝 CPU 版 | 映像多約 800MB，換回房型辨識 90.3% 準確度 |
| `frontend/` 422M 圖片資產 | 唯讀 volume | 映像小 422MB；部署時素材必須另外送達 |
| PostgreSQL | `host.docker.internal` 連本機 | 零資料搬遷；環境不可攜，換機要重建 DB |
| Node | 裝（只搬 binary） | 多約 50MB；但見下方「XLSX 匯出仍未通」 |

## 映像組成

多階段建置。builder 裝套件與預抓權重，runtime 只收 `/opt/venv`、`/opt/torch`
與程式碼。

| 層 | 約略體積 |
|---|---|
| `python:3.12-slim` 基底 | 150MB |
| `requirements-container.txt`（含 onnxruntime） | 700MB |
| torch 2.13.0 CPU | 800MB |
| DINOv2 骨幹快取 | 88MB |
| Node 20 binary | 50MB |
| `backend/` + `frontend/` 程式碼 | 30MB |

合計約 1.8GB。build context 因 `.dockerignore` 從約 900MB 降到約 130MB。

## 為什麼另開 `requirements-container.txt`

`requirements.txt` 是團隊 Windows 開發機的 baseline，由多位 owner 共用，**不應
為了容器改動它**。容器版的兩個差異：

1. **拿掉 `opencv-python`，只留 `opencv-python-headless`。** baseline 同時鎖兩
   者；`opencv-python` 在 slim 容器缺 `libGL.so.1`，`import cv2` 會直接崩。
   headless 提供同一個 `cv2` 模組，baseline 註解裡「torch 生態會拉 headless
   進來蓋掉 cv2」的顧慮在映像裡不存在——沒有第二份 opencv 可蓋。`<5` 這個
   為了 `HoughLinesP` 回傳 shape 的鎖照樣生效。
2. **拿掉 `selenium` / `webdriver-manager` / `tqdm` / `beautifulsoup4` /
   `requests`。** 這些是 Kai 的型錄爬蟲與 AWS metadata 工具，`backend/` 與
   `scripts/` 都沒有 import（2026-08-05 全域 grep 確認），且 selenium 在執行期
   會去找 chrome。

改任一份的版本 pin 時，兩份都要改。

## 容器與本機的行為差異

### 必須掛 volume 的執行資料

`ROOMPILOT_RUNTIME_DIR=/data/runtime` 取代本機的 `.runtime/`，繞過
`backend/server/runtime_paths.py` 依賴 `.git` 的 `_repository_root()`。裡面有：

- `auth_secret.key` — 重生等於所有已簽發的 access/refresh token 立即失效
- `projects.sqlite3` — `ROOMPILOT_PROJECT_STORE_PROVIDER=sqlite` 時的專案資料
- `uploads/`、`renders/`、`indexes/`、`doc-report/`、`engineering/`

### XLSX 匯出仍未通

`backend/server/engineering/workbook_builder.mjs` 會動態 `import`
`@oai/artifact-tool`。該模組不在 repo、不在公開 registry，`.env` 的
`ROOMPILOT_ARTIFACT_TOOL_MODULES` 也是空的——**本機現況與容器一樣，第 8 步
XLSX 匯出都是回 `WorkbookGenerationUnavailable`**。容器裝 node 只是把路徑備妥。

模組到位後：掛進容器並設 `ROOMPILOT_ARTIFACT_TOOL_MODULES` 指向該目錄即可，
不需改程式。

### 沒掛 `testdata/` 時

`main.py` 的 `PLAN_DIR`、`SAMPLE_GLB_DIR` 都有 `is_dir()` 守衛，缺目錄時
sample 清單回空陣列，正式八步流程不受影響。需要範例平面圖時打開
`docker-compose.yml` 裡註解掉的那行掛載。

### DINOv2 骨幹抓不到時

建置期的預抓失敗不擋建置（`|| echo`）。執行期
`backend/floorplan/room_classifier.py` 會印警告並把房型判斷退回面積規則，
`own_eval` 72 房準確度從 90.3% 掉回幾何猜測水準，服務不中斷。

要重抓：`docker compose build --no-cache app`，或掛一份既有的
`~/.cache/torch/hub` 到 `/opt/torch/hub`。

## 改用 compose 內建 PostgreSQL

目前接本機 DB。要讓環境自足可攜，在 `docker-compose.yml` 加：

```yaml
  db:
    image: pgvector/pgvector:pg17
    environment:
      POSTGRES_DB: roompilot_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - roompilot-db:/var/lib/postgresql/data
```

並把 app 的 `DB_HOST` 改成 `db`、移除 `extra_hosts`。代價是要重跑
`scripts/sql/` 全套匯入（家具 8,557、資產 34,228、BGE-M3 向量 7,958、
Phase 4 runtime catalog），向量重建耗時。

## 未在容器化範圍內的既有問題

- **連線池**：`.env.example` 的 `DB_POOL_MAX=24`。容器化不會改變池行為，但
  多副本部署時每個副本各開一池，總連線數是副本數乘以上限，會撞到
  PostgreSQL 的 `max_connections`。單副本本機開發不受影響。
- **RAG**：`ROOMPILOT_RAG_ENABLED` 預設 false，`sentence-transformers` 與模型
  權重都不在映像內。要在容器開 RAG 需另建一層並掛
  `ROOMPILOT_RAG_MODEL_CACHE`（權重不得進版控，也不該進映像）。
- **PaddleOCR**：`requirements-ocr.txt` 未納入。缺它時印刷房名/尺寸 OCR 安靜
  停用、比例尺回到手拉。
