# RoomPilot SQL／RAG 契約索引

更新日期：2026-07-31

本頁只負責導覽與標示可操作狀態；各欄位、API、錯誤與資料生命週期仍以連結的正式契約為準。歷史整合紀錄可能保留舊批次數字，不得用來取代本頁、正式資料檔或 importer dry-run。

## 現行家具資料基準

| 項目 | 正式筆數 |
|---|---:|
| catalog／GLB | 8,675 |
| active／API／RAG-indexable | 8,076 |
| inactive 複核 | 599 |
| 三視角圖片 | 26,025 |
| SQL `furniture_assets` | 34,700 |
| BGE-M3 vectors | 8,076 |
| `floor-lamp` | 118 |

正式輸入是 `JSON/furniture/furniture_official_catagory.json`、`JSON/manifests/` 四份 CSV 與 `JSON/RAG/furniture_embeddings_bge_m3.jsonl`。數量變更必須同時通過兩支 importer dry-run、live PostgreSQL view/table 檢查與 producer／consumer 測試。

## 契約與目前狀態

| 契約 | 用途 | 2026-07-31 狀態 |
|---|---|---|
| [家具模型交付](CATALOG_MODEL_DELIVERY_CONTRACT.md) | JSON、GLB、圖片、CloudFront、quarantine | 現行；8,675／26,025 與 118 筆落地燈已驗證 |
| [Catalog Read Phase 1](POSTGRESQL_CATALOG_READ_PHASE1.md) | PostgreSQL read model、provider、503 | 現行；8,076 筆 active view 已驗證 |
| [Catalog CRUD Phase 2](POSTGRESQL_CATALOG_CRUD_PHASE2.md) | 管理 API、transaction、軟刪除、audit | 現行；不可用批次 importer 取代管理權限邊界 |
| [Project Store Phase 3](POSTGRESQL_PROJECT_STORE_PHASE3.md) | project／render PostgreSQL persistence | 部分可操作；runtime adapter 與主要 tables 存在，但 repository 缺少 migration/schema 工具，engineering PostgreSQL tables 也尚未就緒 |
| [Runtime Catalog Phase 4](POSTGRESQL_RUNTIME_CATALOG_PHASE4.md) | style／surface／cost／quarantine | Live DB 與 read repository 可用；repository 缺少可從零重建的 schema/importer |
| [Single Source Phase 5](POSTGRESQL_SINGLE_SOURCE_PHASE5.md) | strict PostgreSQL、503、hot refresh | Runtime read 契約現行；Phase 3／4 重建缺口仍須遵守上列限制 |
| [家具向量](POSTGRESQL_FURNITURE_EMBEDDINGS.md) | pgvector table、hash、UPSERT | 現行；8,076 筆 BGE-M3，orphan／stale 均為 0 |
| [家具 RAG Runtime](POSTGRESQL_FURNITURE_RAG_RUNTIME.md) | Django query／retrieval／reranking | 現行；只檢索與排序，不決定幾何 |

## 可執行的 SQL 入口

目前 `scripts/` 工具樹只保留正式家具與家具向量流程：

```powershell
.\.venv\Scripts\python.exe scripts\sql\import_official_catalog_to_postgres.py --dry-run
.\.venv\Scripts\python.exe scripts\sql\import_furniture_embeddings_to_postgres.py --require-all --dry-run
```

完整重建家具資料時使用 `--replace-existing`，完成後必須重新匯入向量。此選項不影響 project、render 或 runtime catalog。

下列舊路徑目前不存在，不得把歷史文件中的命令當成可執行 runbook：

```text
scripts/project_store/
scripts/runtime_catalog/
scripts/catalog/
```

在對應 schema、importer、dry-run 與測試一起恢復之前，不得宣稱新環境可從 repository 完整重建 Phase 3／4。

## 文件回收原則

本索引中的契約仍被 README、owner、程式或測試引用，不應刪除。只有同時符合下列條件才可送入資源回收桶：

1. 沒有現行 producer／consumer 或本索引引用。
2. 內容已由另一份正式契約完整取代。
3. 移除後 Markdown link、測試與操作入口仍可通過。
4. Git 歷史足以追溯，且受影響 owner 已確認不再是公開契約。
