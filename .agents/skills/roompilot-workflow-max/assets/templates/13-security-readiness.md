# 13 安全與生產準備：［變更／版本］

## 責任與資料流

| 項目 | 內容 |
|---|---|
| 主要 owner／協作 owner | ［Bella／Kai／domain owner］ |
| 輸入 | ［HTTP、上傳檔、DB、外部 provider］ |
| 輸出 | ［API、保存資料、log、asset URL］ |
| 契約／保存位置 | ［文件］／［PostgreSQL/project state/無］ |

## 資料分類

| 資料 | 分類 | 收集理由 | 保存／保留 | Log／回應遮罩 |
|---|---|---|---|---|
| ［資料］ | ［公開／內部／機密／PII］ | ［理由］ | ［位置／期限］ | ［策略］ |

## 安全 Gate

### Secret 與設定

- [ ] `.env`、密碼、API key、certificate 私鑰未提交或輸出。
- [ ] `.env.example` 只含非敏感範例，且測試不記錄真值。
- [ ] 模型權重、runtime、cache 與大型資產留在 Git 之外。

### API 與授權

- [ ] 輸入採 schema／白名單驗證；檔案上傳限制類型與大小。
- [ ] 管理 API 沿用現有 Bearer 權限、audit 與最小回應；不虛構 OAuth。
- [ ] 對 project/resource 做物件層級存取檢查。
- [ ] 錯誤不回傳 credential、SQL、`raw_data` 或敏感內部資訊。

### Catalog、RAG 與資料庫

- [ ] API/RAG 只查 active 正式資料；inactive、quarantine、未匹配資料不公開。
- [ ] SQL 參數化，寫入維持 transaction、revision/audit 與軟刪除。
- [ ] 正式 PostgreSQL 失敗回明確 503，不靜默改讀本機 JSON。
- [ ] RAG 證據可追溯，且不被宣稱為幾何或結構合法性。

### 前端與外部資產

- [ ] Production frontend 未將敏感資料存入 URL/localStorage。
- [ ] CloudFront/外部 URL 使用 HTTPS 且只輸出必要欄位。
- [ ] 使用者輸入與 AI/provider 輸出在 DOM 呈現前安全編碼。

## Readiness

| 項目 | 證據／位置 | Owner | 結果／待辦 |
|---|---|---|---|
| Health/readiness | ［route/log］ | Bella/Kai | ［結果］ |
| Backup/recovery | ［runbook］ | ［owner］ | ［結果］ |
| Timeout/error | ［test］ | ［owner］ | ［結果］ |
| Audit/monitoring | ［table/log］ | ［owner］ | ［結果］ |

## 驗證

- 安全／env tests：［命令］
- API auth／error tests：［命令］
- PostgreSQL view／quarantine tests：［命令］
- Browser security check：［步驟］
- 結論：［可交付／修正後可交付／阻擋］

