# RoomPilot 現行基準

本檔是工作流導覽，不是第二份正式契約。每次工作都要重新讀取 repository
當下的 `README.md`、`AGENTS.md`、owner profile、程式、測試與相關
`docs/contracts/`；若內容不同，以當下 repository 為準。

## 產品流程

```text
1 建立專案
→ 2 上傳 PNG/JPG/DXF 平面圖
→ 3 兩點標定並確認公分尺度
→ 4 校正空間、牆、門、窗、樑與柱
→ 5 完成逐房問卷、家具需求與風格色卡
→ 6 產生配置並同步編輯 2D/3D 家具
→ 7 鎖定方案並選擇逐房生成視角
→ 8 依需求、家具、材質、色卡與視角產生 AI 成果
```

碰撞、淨空、超界或模型載入問題未解決時不得前進。結構變更回到第 4 步，
並重新驗證既有家具。

## 正式資料流

```text
PNG/JPG/DXF
→ Cody：辨識、尺度、confidence、layout_json
→ Django：空間關係、layout evaluation、關係證據
→ Yen：requirements、選件與修復意圖
→ Kai：PostgreSQL catalog、CloudFront、metadata、pgvector
→ Ancai：placement、collision、clearance、legality
→ scene_json
→ Bella：FastAPI、保存、正式 HTML/JS/Three.js UI、八步流程
```

RoomPilot 目前是 FastAPI 模組化單體。不要把每個 owner 目錄畫成獨立微服務，
除非現行部署與程式確實已拆分。外部依賴包括 PostgreSQL、CloudFront/object
storage 與已設定的 AI provider；不得把模板中的 Redis、RabbitMQ、Kubernetes、
OAuth 或多區 HA 當成現況。

## 正式執行面

- `backend/server/`：唯一 FastAPI、專案保存與模組調度。
- `backend/server/static/`：正式 production frontend。
- `frontend3d/`：次要 React/R3F 原型；不取代正式流程。
- `layout_json`：格局與結構事實。
- `scene_json`：方案、家具、表面、燈光、渲染與規則結果。
- PostgreSQL：正式 catalog 與 project/runtime read path 的主要來源。

## 保存與相容性

- 新欄位先查現行 Pydantic/JSON/schema version 與舊資料 fallback。
- 前端狀態、API payload、project persistence 與 reload 行為必須一起追查。
- 變更第 4 步格局版本時，保留可回復的舊方案並重新驗證家具。
- 工程文件需由鎖定 revision 產生；未鎖定回傳既有契約的 409 錯誤。
- 正式報價缺資料時保留待確認，不得用示範值假裝正式價格。

## Catalog 與 SQL 現況

- 正式家具只公開 active、已驗證且具有正式資產證據的集合。
- inactive、unmatched 與 quarantine 不得進 API、RAG 或場景。
- 正式 PostgreSQL provider 失敗時依契約回 503；只有明確指定的離線模式才讀
  已驗證 JSON，不得靜默 fallback。
- 目前 `scripts/` 只以工作樹中的實際內容為準。歷史文件提到但已不存在的
  `scripts/project_store/`、`scripts/runtime_catalog/`、`scripts/catalog/` 不可當成
  可執行 runbook，也不可宣稱新環境能由 repository 完整重建 Phase 3/4。

## 啟動與基準驗證

從 repository 根目錄依當下 `README.md` 選擇 `.venv` 或 `uv` 啟動。文件、
程式或整合變更完成後，至少考慮：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
git status --short
```

若變更只涉及文件或 skill，仍需驗證連結、命令、UTF-8、來源覆蓋與差異格式。
