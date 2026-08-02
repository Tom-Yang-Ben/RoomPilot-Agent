# 14 部署與運維 Runbook：［環境／版本］

## 現況與責任

| 項目 | 內容 |
|---|---|
| 部署 owner／協作 owner | Bella／［Kai、其他 owner］ |
| 輸入 artifact | ［commit、Python deps、static assets、schema 前置］ |
| 輸出服務 | ［FastAPI URL、health、資料庫連線］ |
| 保存系統 | ［PostgreSQL project/catalog/runtime tables］ |
| 外部依賴 | ［CloudFront、AI provider、remote render］ |

不得把範例 K8s、Redis、HA 或微服務拓撲寫成現況；只記錄已存在且可驗證的環境。

## Runtime 拓撲

| Node／服務 | 技術／版本 | Port／protocol | Owner | Health 證據 |
|---|---|---|---|---|
| Browser | HTML/CSS/JS/Three.js | HTTPS | Bella | ［smoke］ |
| App | Python 3.12 + FastAPI | ［port］/HTTP(S) | Bella | `GET /api/health` |
| Database | PostgreSQL 17 | SQL/TLS | Bella/Kai | ［readiness］ |
| Asset/CDN | CloudFront | HTTPS | Kai | ［URL check］ |

## 設定與前置條件

- Python／Node／PostgreSQL 版本：［README 現行版本］
- 必填環境變數名稱：［只列名稱，不填 secret］
- Catalog／runtime provider：［現行正式值］
- Schema readiness：［已存在 tables/views］
- 已知重建限制：目前 repo 若缺 Phase 3/4 schema/importer，必須明示「不可從零重建」。

## 契約與保存 Gate

- [ ] 部署 artifact 使用正式 `layout_json`／`scene_json` schema 與 cm／`_cm`／`_m2` 規則。
- [ ] RAG 與 Engine 的責任邊界沒有因環境設定或 fallback 改變。
- [ ] PostgreSQL views 只公開 active 正式資料；inactive、quarantine 與家電不進正式家具 API。
- [ ] Project/workflow/render 保存、revision 409 與正式 PostgreSQL 503 行為符合現行契約。
- [ ] `backend/server/static/` 仍是 production frontend，且可由同一 FastAPI deployment 提供。

## 部署前 Gate

- [ ] Owner、API、保存、production frontend tests 通過。
- [ ] Catalog/embedding importer 若受影響，已先通過 `--help` 與 dry-run。
- [ ] DB migration／rollback 已由對應 owner 審核；沒有破壞性預設。
- [ ] `.env`、cert、runtime、cache、模型或大資產不在交付 diff。
- [ ] 備份／恢復方法與觀察窗口已確認。

## 部署與驗證步驟

| 步驟 | 動作 | 成功證據 | 失敗時停止條件 |
|---|---|---|---|
| 1 | ［建置／安裝已鎖定依賴］ | ［log］ | ［條件］ |
| 2 | ［啟動現行 FastAPI entrypoint］ | ［health］ | ［條件］ |
| 3 | ［DB／catalog readiness］ | ［view/count］ | ［條件］ |
| 4 | ［八步 smoke test］ | ［結果］ | ［條件］ |

## 回滾與事故處理

- 回滾目標版本／artifact：［版本］
- App 回滾方式：［經審核的既有程序；不放破壞性命令］
- DB 相容／回復方式：［transaction、備份、人工 Gate］
- 503／409／asset/provider failure 處理：［runbook］
- 升級 owner 與聯絡方式：［角色／管道］

## 監控與驗收

| 指標／事件 | 來源 | 基準／門檻 | Owner | 處置 |
|---|---|---|---|---|
| ［health/error/latency］ | ［log/metric］ | ［實測值］ | ［owner］ | ［處置］ |

- 自動測試：［命令與結果］
- Browser smoke：［步驟與結果］
- 部署結論／未驗證項：［內容］
