# 16 WBS 與最大平行工作包：［任務名稱］

## 專案資料

| 項目 | 內容 |
|---|---|
| Root orchestrator | ［負責人］ |
| 主要 owner／協作 owner | ［owner］／［owners］ |
| 輸入 | ［已確認 PRD、ADR、contract、現行 code］ |
| 輸出 | ［程式、測試、文件、驗證證據］ |
| 保存／契約 | ［project/catalog/layout/scene 邊界］ |

## 最大平行規則

- 總槽位為 root + 最多 3 個 subagents；只有可獨立、檔案不重疊的工作才平行。
- Shared `AGENTS.md`、README、`docs/contracts/*` 與本 skill 由 root／單一 writer 管理。
- Producer/consumer schema 未穩定前先唯讀分析；由 contract owner 固定後再平行實作。
- 每個 owner packet 同時擁有其實作與專屬測試；shared fixture 另指定單一 writer。
- Subagent 不 commit/push，不修改 `.env`、cert、runtime、cache、模型或大型資產。

## Waves

| Wave | 目標 | Root | Agent A | Agent B | Agent C | Gate |
|---|---|---|---|---|---|---|
| 0 | Preflight | owner/contract/status/範圍 | - | - | - | 輸入輸出與 dirty files 鎖定 |
| 1 | 唯讀分析 | 統整 | domain | API/data | tests/UI/ops | 無猜測 schema |
| 2A | 契約穩定 | 單一 writer | producer review | consumer review | test review | contract 確認 |
| 2B | 實作 | shared files | owner packet | owner packet | owner packet | 檔案不重疊 |
| 3 | 驗證 | 協調修正 | domain tests | contract/API | browser/docs/security | 結果可重現 |
| 4 | 整合 | full tests/diff/status | - | - | - | 無 owner 越界 |

## Work Packet

| 欄位 | 內容 |
|---|---|
| Packet ID／owner | ［ID］／［owner］ |
| 目標 | ［單一可驗收結果］ |
| 可修改檔案 | ［完整清單／glob 邊界］ |
| 禁止修改檔案 | ［dirty/shared/其他 owner］ |
| 輸入 | ［schema、fixture、前置決策］ |
| 輸出 | ［code、test、evidence］ |
| 契約 Gate | ［cm、layout/scene、RAG/Engine、catalog、frontend］ |
| 保存 Gate | ［transaction、revision、reload］ |
| 驗證 | ［精確命令］ |
| Handoff | ［changed files、結果、風險］ |

## 依賴與跨資料夾

| Packet | 前置依賴 | Consumer | 可否平行 | 原因 |
|---|---|---|---|---|
| ［ID］ | ［contract/packet］ | ［ID/owner］ | ［是／否］ | ［理由］ |

- 主要 owner：［owner］
- 協作 owner：［owner］
- 跨資料夾原因：［理由］
- Producer／consumer tests：［命令］

## 最終驗證

- Owner tests：［命令］
- API／保存／browser／SQL：［命令］
- 全套：`.\.venv\Scripts\python.exe -m pytest -q`
- 格式：`git diff --check`
- 工作樹：`git status --short`

