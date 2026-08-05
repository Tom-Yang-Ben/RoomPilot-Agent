# RoomPilot 換機部署清單

在一台乾淨的 Windows 10／11 64-bit 上，把 RoomPilot 佈到「三個 provider 全走
PostgreSQL、RAG 開啟」的完整開發狀態。章節順序就是相依順序，不要跳。

安裝細節（pgvector 編譯、匯入驗收 SQL）在
[PostgreSQL 17.10 安裝與資料匯入指南](../scripts/sql/PostgreSQL%2017.10%20安裝與資料匯入指南.md)；
本文件負責的是「整台機器要備齊什麼」與「哪些東西不在 Git 裡、必須手動搬」。

## 目標狀態

以下為 2026-08-05 實測的參考機器組態：

| 項目 | 版本／狀態 |
|---|---|
| Python | 3.12（實測 3.12.10） |
| 虛擬環境 | `.venv`，由 **uv** 建立（uv 0.11.14）。**venv 內沒有 pip**，一律用 `uv pip` |
| Git LFS | 3.7.1（必要，家具向量檔是 LFS） |
| Node / npm | v24.15.0 / 11.12.1 |
| PostgreSQL | 17.10 x86-64 + **pgvector 0.8.2**，資料庫 `roompilot_db` |
| `ROOMPILOT_CATALOG_PROVIDER` | `postgres` |
| `ROOMPILOT_PROJECT_STORE_PROVIDER` | `postgres` |
| `ROOMPILOT_RUNTIME_CATALOG_PROVIDER` | `postgres` |
| `ROOMPILOT_RAG_ENABLED` | `true`（torch 2.13.0+cpu、sentence-transformers 5.6.1） |
| PaddleOCR | 未安裝（選配） |
| 模型快取 | torch hub 89 MB ＋ HuggingFace 6.5 GB |

## 1. 系統工具

- [ ] **Git for Windows** 與 **Git LFS**（安裝後執行一次 `git lfs install`）
- [ ] **Python 3.12**：`py -3.12 --version`
- [ ] **uv**：`winget install astral-sh.uv`
- [ ] **Node.js 22+**：jsdom 行為測試與第 9 步 XLSX 匯出都需要
- [ ] **Visual Studio 2022 Build Tools**：**只有要自行編譯 pgvector 才需要**。
      在 Visual Studio Installer 勾選「使用 C++ 的桌面開發」，確認含 MSVC v143
      x64/x86、一個 Windows 10／11 SDK、MSBuild 與 NMAKE

## 2. 取得程式碼

```powershell
git lfs install
git clone https://github.com/Tom-Yang-Ben/RoomPilot-Agent.git
cd RoomPilot-Agent
git switch -c ben-local origin/ben
```

- [ ] 確認 LFS 檔已還原成真檔，不是指標檔：

```powershell
(Get-Item JSON\RAG\furniture_embeddings_bge_m3.jsonl).Length   # 應為 91622177
```

Clone 需下載約 2 GB（`.git` pack 2.04 GiB）。

## 3. PostgreSQL 17.10 與 pgvector 0.8.2

完整步驟見安裝指南，重點：

- [ ] 安裝 PostgreSQL 17.10 x86-64，port 5432，記住 `postgres` 密碼
- [ ] Windows service `postgresql-x64-17` 為 Running
- [ ] 編譯安裝 pgvector v0.8.2。以下是 **BAT 語法**，必須在「x64 Native Tools
      Command Prompt for VS 2022」以系統管理員身分執行，不可貼進一般 PowerShell：

```bat
set "PGROOT=C:\Program Files\PostgreSQL\17"
cd /d %TEMP%
git clone --branch v0.8.2 https://github.com/pgvector/pgvector.git
cd pgvector
nmake /F Makefile.win
nmake /F Makefile.win install
```

- [ ] 驗證 extension 可用：

```powershell
& 'C:\Program Files\PostgreSQL\17\bin\psql.exe' -U postgres -d postgres `
  -c "SELECT name, default_version FROM pg_available_extensions WHERE name = 'vector';"
```

## 4. Python 環境

```powershell
uv sync --extra server --extra vision --extra catalog --group dev
uv pip install -r requirements-rag.txt
```

`requirements-rag.txt` 帶進 torch 2.13.0＋sentence-transformers＋anthropic／openai
（約 2 GB）。它同時滿足兩件事：家具 RAG 檢索，以及 `backend/floorplan` 房型語意層
的 DINOv2 骨幹。不裝 torch 的話房型會退回面積規則——服務不中斷，但會印警告，
`own_eval` 72 房準確度由 90.3% 掉回幾何猜測水準。

選配 OCR（參考機器未安裝）：

```powershell
uv pip install -r requirements-ocr.txt
```

不裝時印刷房名／尺寸標註 OCR 安靜停用，比例尺回到手動拉線。

## 5. `.env`

`.env` 不在 Git 裡，必須從舊機複製或重填。

```powershell
Copy-Item .env.example .env
```

需要實際填值的欄位：

| 欄位 | 說明 |
|---|---|
| `DB_PASSWORD` | 新機 PostgreSQL 的 `postgres` 密碼 |
| `OPENROUTER_API_KEY` | 從舊機 `.env` 複製；留空則選件與生圖退回本地規則 |
| `ROOMPILOT_CATALOG_PROVIDER` | `postgres` |
| `ROOMPILOT_PROJECT_STORE_PROVIDER` | `postgres` |
| `ROOMPILOT_RUNTIME_CATALOG_PROVIDER` | `postgres` |
| `ROOMPILOT_RAG_ENABLED` | `true` |

參考機器上 `OPENAI_API_KEY`、`ANTHROPIC_API_KEY` 留空（RAG parser 走 openrouter），
`ROOMPILOT_CATALOG_ADMIN_TOKEN` 留空（等同停用 `/api/admin/furniture` 寫入端點）。

### 兩個容易踩的坑

**shell 環境變數會蓋過 `.env`。** 設定讀取是
`os.getenv(name, file_values.get(name, default))`
（`backend/catalog/postgres_repository.py`），作業系統環境變數優先。若 PowerShell
profile 或先前的終端機殘留 `ROOMPILOT_*_PROVIDER`，改 `.env` 不會生效。驗證前先確認：

```powershell
Get-ChildItem env:ROOMPILOT_*
```

**JWT 簽章金鑰。** `.env` 沒設 `ROOMPILOT_AUTH_SECRET` 時，系統會自動產生一把存在
`.runtime/auth_secret.key`。新機沒有這個檔＝所有既有帳號的 token 失效，必須重新登入。
兩種做法擇一：把舊機的 `.runtime/auth_secret.key` 一併複製，或（較正確）在 `.env`
明確設定一把：

```powershell
python -c "import secrets;print(secrets.token_urlsafe(48))"
```

## 6. 資料庫 schema 與匯入

三個 provider 都走 PostgreSQL 時，**四份 schema 都要套用**，不是只有家具那份。
依序執行，順序有相依性（向量的外鍵指向 `furniture_items`）：

```powershell
# 6-1 家具 catalog——先 dry-run，再實際建庫匯入
.\.venv\Scripts\python.exe scripts\sql\import_official_catalog_to_postgres.py --dry-run
.\.venv\Scripts\python.exe scripts\sql\import_official_catalog_to_postgres.py --create-database

# 6-2 BGE-M3 家具向量
.\.venv\Scripts\python.exe scripts\sql\import_furniture_embeddings_to_postgres.py `
  --catalog JSON\furniture\furniture_official_catagory.json `
  --embeddings JSON\RAG\furniture_embeddings_bge_m3.jsonl `
  --require-all

# 6-3 專案／workflow_json／render metadata（ROOMPILOT_PROJECT_STORE_PROVIDER=postgres）
psql -U postgres -d roompilot_db -f scripts\project_store\roompilot_project_store_schema.sql

# 6-4 runtime catalog：風格卡、表面材質、裝修費率、quarantine
#     （ROOMPILOT_RUNTIME_CATALOG_PROVIDER=postgres 為嚴格模式，缺資料會回 503）
psql -U postgres -d roompilot_db -f scripts\runtime_catalog\roompilot_runtime_catalog_schema.sql
.\.venv\Scripts\python.exe scripts\runtime_catalog\import_runtime_catalogs_to_postgres.py

# 6-5 燈具獨立表（scene_json.surface_overrides.lighting_ids 會引用）
.\.venv\Scripts\python.exe scripts\sql\import_lighting_assets_to_postgres.py
```

匯入後的預期筆數；不吻合就停下來查，不要繼續：

| 項目 | 筆數 |
|---|---:|
| `furniture_items` | 8,557 |
| active（進正式 API 與 RAG） | 7,958 |
| inactive | 599 |
| `furniture_assets` | 34,228 |
| `furniture_catalog_current` | 7,958 |
| `furniture_embeddings` | 7,958 |
| orphan embeddings | 0 |
| stale embeddings | 0 |

完整驗收 SQL 見安裝指南第 10 節。

## 7. 模型快取

首次執行會自動下載，但總量 6.6 GB。用外接硬碟從舊機複製這兩個目錄會快很多：

| 快取路徑 | 大小 | 用途 | 缺少時的後果 |
|---|---:|---|---|
| `~/.cache/torch/hub/` | 89 MB | DINOv2 房型語意骨幹 | 房型退回面積規則，印警告 |
| `~/.cache/huggingface/hub/models--BAAI--bge-m3` | 4.3 GB | 家具 RAG 向量檢索 | 首次啟動時下載 |
| `~/.cache/huggingface/hub/models--BAAI--bge-reranker-v2-m3` | 2.2 GB | RAG 重排序 | 首次啟動時下載 |

要放在非預設位置時，設定 `TORCH_HOME` 與 `.env` 的 `ROOMPILOT_RAG_MODEL_CACHE`。

線性頭 `backend/floorplan/room_head.npz` 僅 15 KB 且已進版控，clone 即得。

## 8. Node 測試相依

```powershell
Set-Location tests\static
npm ci
Set-Location ..\..
```

未安裝時 `tests/test_scene_pending_actions_dom.py` 會 skip（不是失敗）。

## 9. 驗收

```powershell
Get-ChildItem env:ROOMPILOT_*
.\.venv\Scripts\python.exe -m pytest -q
```

- [ ] 預期 **1018 passed, 11 skipped**（8–13 分鐘）

預設測試把三個 provider 釘成 sqlite/json（見 `tests/conftest.py`），所以全綠只證明
JSON／SQLite 備援路徑沒壞。要驗證正式資料路徑，另外執行：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_postgres_live_tests.ps1
```

該腳本會先跑預設 skip 的 PostgreSQL live 測試，再用 postgres provider 跑全套。

- [ ] 啟動網站：`.\dev.ps1`，開啟 <http://127.0.0.1:8002>
- [ ] `/login` 註冊或登入後進 `/projects`

## 10. 不在 Git 裡、需要手動搬的本機資料

| 路徑 | 大小 | 是否要搬 |
|---|---:|---|
| `.env` | — | **必搬**：API key 與資料庫密碼 |
| `.runtime/auth_secret.key` | 64 B | **建議搬**，否則既有帳號全部要重新登入（或改用 `.env` 的 `ROOMPILOT_AUTH_SECRET`） |
| `~/.cache/huggingface/hub/`、`~/.cache/torch/hub/` | 6.6 GB | **建議搬**，省一次大下載 |
| `.runtime/engineering/` | 約 29 MB | 鎖版報告產物；要保留歷史成果才搬 |
| `.runtime/projects.sqlite3` | — | 不必搬：provider 為 postgres 時是離線模式遺留 |
| `.tmp/` | 約 106 MB | 不必搬：QA 截圖與暫存輸出 |

專案資料本身在 `ROOMPILOT_PROJECT_STORE_PROVIDER=postgres` 下存於 PostgreSQL。
要把舊機的 SQLite 專案搬進新機的 PostgreSQL，使用
`scripts/project_store/migrate_sqlite_projects_to_postgres.py`。

## 常見問題

| 症狀 | 原因 | 處理 |
|---|---|---|
| 改了 `.env` 但 provider 沒變 | shell 環境變數優先 | `Get-ChildItem env:ROOMPILOT_*` 後清掉 |
| 帳號全部要重新登入 | 缺 `.runtime/auth_secret.key` | 搬舊檔或設 `ROOMPILOT_AUTH_SECRET` |
| 向量檔只有 132 bytes | 未執行 `git lfs install` 就 clone | `git lfs pull` |
| 風格卡／材質 API 回 503 | 第 6-4 步未執行 | 套用 runtime catalog schema 並匯入 |
| `extension "vector" is not available` | pgvector 未裝到 PostgreSQL 17 | 確認 `PGROOT` 後重新 build 與 install |
| `cl`／`nmake` 找不到 | 缺 C++ workload 或開錯 shell | 用 x64 Native Tools Command Prompt |
| 房型辨識印警告、準確度偏低 | 未安裝 torch | `uv pip install -r requirements-rag.txt` |
