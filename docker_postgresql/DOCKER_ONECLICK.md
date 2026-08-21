# PostgreSQL 一鍵安裝（Docker）

> 本資料夾原本另有一份只起資料庫的 `docker-compose.yml`，2026-08-22 已合併進專案根目錄
> 的 `docker-compose.yml`（`db` 服務，容器名 `roompilot-postgres` 不變）。整個專案的容器
> 拆解見 [`docker/README.md`](../docker/README.md)；這份只講「在別台電腦重建資料庫」。

別台電腦重建完整 RoomPilot 資料庫（8,675 家具 + 8,076 BGE-M3 向量），不需裝 PostgreSQL、不需編 pgvector、不需跑匯入腳本。

## 需求

- 目標電腦已安裝 Docker Desktop（含 `docker compose`）。

## 步驟

```powershell
# 1. 取得 repo（含 docker_postgresql/roompilot_db_dump.sql.gz 這份 dump，走 git-lfs）
# 2. 在專案根目錄建立 .env，填 DB_PASSWORD
Copy-Item .env.example .env    # 然後編輯 .env 把 DB_PASSWORD 設好
# 3. 在專案根目錄啟動；只要資料庫就指名 db（首次會自動還原，約數十秒）
docker compose up -d db
```

首次啟動時，`pgvector/pgvector:pg17` 會自動執行本資料夾的 `roompilot_db_dump.sql.gz`
（整個資料夾掛在 `/docker-entrypoint-initdb.d/`，非 SQL 檔會被略過），建立 `roompilot_db`、啟用 `vector` extension 並灌入全部資料。

## 驗證

```powershell
docker exec roompilot-postgres psql -U postgres -d roompilot_db -c "SELECT count(*) FROM roompilot.furniture_catalog_api_current;"  # 8076
```

## 常見操作

| 需求 | 指令 |
|---|---|
| 停止（保留資料） | `docker compose stop db` |
| 砍掉並重灌 dump | `docker compose rm -sfv db` → `docker volume rm roompilot_pgdata` → `docker compose up -d db`。**別用 `docker compose down -v`**，那會把 RAG 的 4.6 GB 模型快取一起清掉 |
| 更新 dump（在有資料的機器上重出一份） | `docker exec roompilot-postgres sh -c "pg_dump -U postgres --create --clean --if-exists -d roompilot_db \| gzip -9" > docker_postgresql/roompilot_db_dump.sql.gz` |

## 注意

- **只有空 volume（首次）才會自動還原**。volume 已存在時放新 dump 不會重跑，要先照上表清掉 volume。
- dump 檔約 55MB，不適合塞進一般 git；本 repo 已用 git-lfs 追蹤 `*.sql.gz`（見 `.gitattributes`）。
- `.env` 是本機秘密，不可提交。原生 Windows（非 Docker）安裝仍看
  `PostgreSQL 17.10 安裝與資料匯入指南.md`。
