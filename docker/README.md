# RoomPilot 容器拆解

一鍵啟動、熱重載、以及**為什麼是這樣拆**。指令在最後一節。

## 拆解依據

拆容器的標準只有一條：**那裡本來就有一道行程或網路邊界**。沒有邊界卻硬拆，
得到的是「每個容器都跑同一支 `main.py`」的假微服務——維護成本全付、好處一個沒有。

盤點整個 repo 後，真實邊界只有三道，加上兩個獨立的執行環境，共五個容器：

| 容器 | 負責的功能 | 這道邊界為什麼是真的 |
|---|---|---|
| `db` | 家具型錄、專案保存、runtime catalog、pgvector 向量 | TCP。本來就是外部服務。 |
| `web` | 八步流程 FastAPI + `static/` 前端 + 幾何／選件／辨識 | HTTP。產品本體。 |
| `chromium` | 第 8 步交付提案 PDF 的排版瀏覽器 | `backend/agent/skills/delivery/__init__.py:301` 本來就是 subprocess 呼叫；改連遠端瀏覽器只多兩行。 |
| `rag` | BGE-M3 embed / rerank | 依賴重量。torch + sentence-transformers 約 2.5 GB，模型權重另外 4.6 GB，只有 `/rag` 用得到。 |
| `frontend` | React/R3F 次要原型的 Vite dev server | 不同語言、不同執行環境（Node），本來就是獨立 app。 |

## 為什麼不繼續往下拆

`backend/` 底下的 `engine`、`agent`、`catalog`、`floorplan`、`spatial_data`、
`upgrade3d` **全部是行程內 import**：

```
server ──imports──> agent, catalog, floorplan, upgrade3d      (main.py:26-41, 110)
agent  ──imports──> engine                                     (6 處 callsite)
```

`backend/server/main.py:200` 是全 repo **唯一**的 FastAPI app，沒有第二個 ASGI 入口。
把這些模組拆成獨立容器，等於把每一個函式呼叫改寫成 HTTP——那是重寫，不是容器化，
而且 `AGENTS.md` 明文禁止建立第二套 FastAPI。所以它們留在 `web` 裡。

需要真的拆成服務時，先在程式碼裡把邊界做出來（介面、序列化、失敗語意），
容器化才有意義。順序反過來只會得到一個更難除錯的單體。

## 修改程式碼 → 自動生效

**整個 repo 以 bind mount 掛進容器，映像裡不放程式碼。** 所以改檔不必 rebuild：

| 改什麼 | 怎麼生效 | 要多久 |
|---|---|---|
| `backend/**/*.py` | `uvicorn --reload` 偵測到就重啟 | 1–3 秒 |
| `backend/server/static/**`（JS/CSS/HTML） | FastAPI 直接從掛載點讀，重新整理瀏覽器 | 立即 |
| `backend/spatial_data/rag/**` | `rag` 容器自己的 `--reload` | 1–3 秒 |
| `frontend/src/**` | Vite HMR（改到入口模組時是整頁重載） | 立即 |
| `requirements*.txt` | **這時才要** `docker compose build` | 幾分鐘 |

> **Windows / WSL2 的關鍵一步**：主機檔案系統的 inotify 事件不會傳進 Linux 容器，
> 靠事件的偵測器在 bind mount 上一輩子不會觸發，必須改成輪詢比對 mtime。
>
> Python 端目前是自動達成的：`requirements.txt` 釘的是純 `uvicorn`（非
> `uvicorn[standard]`），沒有 `watchfiles`，`--reload` 因此退回 **StatReload**，
> 而 StatReload 本來就是輪詢 mtime——正好是這裡唯一可靠的做法。
> compose 與 Dockerfile 仍設 `WATCHFILES_FORCE_POLLING=true` 當保險：哪天有人
> 裝了 `uvicorn[standard]`，watchfiles 會被優先選用，屆時少了這個變數熱重載就死了。
>
> Vite 端沒有這種預設保護，一定要 `VITE_IN_DOCKER=1`
> （在 `frontend/vite.config.js` 打開 `usePolling`），拿掉就死。
>
> 實測（2026-08-22，兩端都在主機存檔、容器內觀察）：
>
> | 容器 | 主機動作 | 容器端證據 |
> |---|---|---|
> | `web` | 存檔 `backend/server/main.py` | `StatReload detected changes in 'backend/server/main.py'. Reloading...`；伺服器行程 8 → 82；`/scene` 回 200 |
> | `frontend` | 存檔 `frontend/src/main.jsx` | `[vite] (client) page reload src/main.jsx`；瀏覽器上預先設的 `window` 變數消失＝真的重載 |

## 動到的程式碼

拆容器本身只動兩處，兩處都**由環境變數開關，不設就是原本行為**，本機非 Docker
開發完全不受影響：

| 檔案 | 改動 | 開關 |
|---|---|---|
| `backend/agent/skills/roompilot-delivery-pdf/scripts/build_pdf.py` | `chromium.connect(ws)` 或原本的 `chromium.launch()` | `PLAYWRIGHT_WS_ENDPOINT` |
| `backend/spatial_data/rag/model_runtime.py` | embed／rerank／status 改打 sidecar HTTP，或原本的行程內載入 | `ROOMPILOT_RAG_REMOTE_URL` |

另外兩處是**實跑時發現的既有缺陷**，與 Docker 無關（本機開發同樣受影響），
修了熱重載才成立：

| 檔案 | 既有問題 | 修法 |
|---|---|---|
| `frontend/vite.config.js` | `base` 是 `/static/frontend3d/`，但 proxy 把整段 `/static` 轉給 FastAPI，**等於把 dev server 自己的位址（含 `/@vite/client`）也轉走**。`5173` 上永遠是 FastAPI 那份已建置的舊產物，HMR 不可能觸發 | proxy key 改成 RegExp `^/static/(?!frontend3d(/\|$))`，排除 base，其餘 `/static/**` 照舊轉出去 |
| `backend/spatial_data/rag/model_runtime.py` | `embed()` 沒有空輸入防護（同類的 `rerank`／`rerank_pairs` 都有），空清單會為了算零個向量去載 4.6GB 模型 | 補 `if not texts: return []` |

四處都有測試：`tests/test_docker_split_contract.py`（11 項）。

## 指令

前置：Docker Desktop 已啟動；專案根目錄有 `.env`（至少要有 `DB_PASSWORD`）。

```powershell
# 日常開發：db + web + chromium
docker compose up -d --build
# 開 http://127.0.0.1:8002/scene

docker compose logs -f web        # 看 reload 有沒有觸發
docker compose down               # 停止（保留資料）
```

選配功能各自一個 profile：

```powershell
docker compose --profile frontend up -d   # 再加 Vite dev server → http://127.0.0.1:5173
docker compose --profile rag up -d        # 再加 BGE-M3 sidecar
docker compose --profile all up -d        # 全開
```

首次啟動 `db` 會自動還原 `docker_postgresql/roompilot_db_dump.sql.gz`
（8,675 筆家具 + 8,076 筆向量），約數十秒。**只有空 volume 才會還原**；
要重灌先 `docker compose down -v`（`-v` 會清掉資料）。

驗證：

```powershell
# db 的容器名沿用被合併掉的 docker_postgresql/ 那份（roompilot-postgres），docker exec 也通
docker compose exec -T db psql -U postgres -d roompilot_db -tAc "SELECT count(*) FROM roompilot.furniture_catalog_api_current;"   # 8076
docker compose exec web python -m pytest -q tests/test_docker_split_contract.py
# web 真的連到 db（而不是回退 JSON 型錄）：provider 要是 kai_postgresql
curl -s http://127.0.0.1:8002/api/catalog/status
```

## 已知陷阱

- **`.env` 與容器環境的優先序不一致，而且兩種方向都存在。**
  `DB_*`、`ROOMPILOT_*` 模型設定是**行程環境優先**（`postgres_catalog.py:87`、
  `model_config.py:134`），所以 compose 蓋得掉 `.env` 的 `localhost`。
  但 `backend/spatial_data/rag/settings.py:30` 是**`.env` 檔優先**——`ROOMPILOT_RAG_*`
  那一組要改就得改 `.env`，在 compose 設沒有用。
  （`ROOMPILOT_RAG_REMOTE_URL` 刻意繞開那支、只讀行程環境，就是為了不踩這個坑。）

- **`5432` 埠可能被主機原生 PostgreSQL 佔住。** 在 `.env` 加 `DB_HOST_PORT=5433` 改主機側對應；
  容器之間走 `db:5432`，不受影響。

- **舊的 `docker_postgresql/docker-compose.yml` 已於 2026-08-22 合併進本份並刪除。**
  容器名 `roompilot-postgres` 沿用下來，既有 runbook 的 `docker exec roompilot-postgres …`
  不必改寫。合併前逐張比對過兩邊資料：25 張表的列數與內容 md5（含全部 8,076 條向量）
  完全相同，schema 差異只有 `pg_dump` 的隨機 `\restrict` nonce 與等價的 ARRAY 渲染，
  所以沒有資料需要搬。`docker_postgresql/` 保留 `roompilot_db_dump.sql.gz`（仍是初始化
  來源）與 `DOCKER_ONECLICK.md`。先前用過舊那份的人，舊資料留在具名 volume
  `roompilot-agent_roompilot_pgdata`——本份既不讀也不動它，確認不需要後可自行
  `docker volume rm` 回收空間。

- **`docker compose down -v` 會清掉所有具名 volume，不只資料庫。** 包含 `rag` 的 4.6 GB
  模型快取 `hfcache`。只想重灌資料庫用 `docker compose rm -sfv db` 再
  `docker volume rm roompilot_pgdata`。

- **第 8 步 PDF 的中文字型。** 官方 playwright 映像沒有 CJK 字型，而
  `assets/tokens.css` 指名 `Noto Serif CJK TC`。`chromium` 這一層裝了 `fonts-noto-cjk`，
  拿掉的話版面正常但中文全變豆腐方塊。

- **`chromium` 必須把 repo 掛在跟 `web` 相同的絕對路徑（`/app`）。**
  `build_pdf.py:377` 用 `file://` 開 HTML，遠端瀏覽器讀的是自己那一側的檔案系統。

- **Vite 只認得 `localhost`／IP 的 Host 標頭。** 從**別的容器**用 `http://frontend:5173`
  連會拿到 403（Vite 內建的 DNS rebinding 防護）。使用者的正常路徑
  `http://127.0.0.1:5173` 不受影響；真要跨容器連再加 `server.allowedHosts`。

- **`rag` 的模型權重約 4.6 GB**，放在具名 volume `hfcache`。`docker compose down -v`
  會一起清掉，下次啟動要重抓。若 `.env` 裡設了 Windows 路徑的
  `ROOMPILOT_RAG_MODEL_CACHE`，容器會照那個路徑找而找不到模型——清空它。

- **`docker/rag_sidecar.py` 讓 `/app/docker/` 成為一個叫 `docker` 的命名空間套件。**
  目前沒有任何依賴 `import docker`（Docker SDK），所以不衝突；未來要裝 `docker` 這個
  pip 套件時要先處理這件事。

- **映像裡沒有程式碼。** 這是 dev stack，刻意的取捨（見 `Dockerfile` 開頭的 `ponytail:` 註記）。
  要做可獨立部署的不可變映像，在 `web` target 末端加一層 `COPY backend/ ./backend/` 即可，
  但 `.dockerignore` 也要跟著放行。
