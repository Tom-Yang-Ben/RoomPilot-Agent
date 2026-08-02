# 15 文件與維護紀錄：［變更名稱］

## 基本資料

| 項目 | 內容 |
|---|---|
| 文件 owner／協作 owner | ［owner］／Bella |
| 輸入 | ［實作 diff、測試、契約、runbook］ |
| 輸出 | ［更新文件、連結、命令與狀態說明］ |
| 影響保存／資料流 | ［內容／無］ |

## 文件更新清單

| 文件 | 更新原因 | Producer／Consumer | Owner | 驗證方式 |
|---|---|---|---|---|
| ［路徑］ | ［行為／schema／命令］ | ［兩端］ | ［owner］ | ［link/command/test］ |

## 一致性 Gate

- [ ] README 的八步流程、啟動與驗證命令符合現行程式。
- [ ] `docs/TEAM_AI_OWNERSHIP.md`、owner profile、最近 `AGENTS.md` 未互相矛盾。
- [ ] `layout_json`／`scene_json`、cm／`_cm`／`_m2` 與 schema version 用語一致。
- [ ] RAG／Engine、catalog／quarantine／家電、production frontend 邊界一致。
- [ ] 受影響 `docs/contracts/` 同時描述 producer、consumer、保存與錯誤。

## `scripts/` 文件 Gate

- [ ] 只記錄目前工作樹實際存在的 script、`--help` 與 dry-run。
- [ ] 沒有從遠端、Git 歷史、備份或帶版本尾碼檔案回填舊命令。
- [ ] 不宣稱缺少 schema/importer 的 Phase 3/4 可從 repo 完整重建。
- [ ] 正式匯入與任何 replace 行為只描述人工 Gate，不提供破壞性預設。

## 保存與相容性說明

- 原始 truth：［資料／owner］
- 衍生／保存位置：［table/project JSONB/file］
- revision／migration／reload：［行為］
- fallback／不可用行為：［503、409、其他］

## 驗證與維護

- Markdown 相對連結：［結果］
- 文件中的檔案／命令存在性：［結果］
- Owner／contract tests：［命令與結果］
- `git diff --check`：［結果］
- 下次複核日期／觸發：［日期或 schema/release 事件］

