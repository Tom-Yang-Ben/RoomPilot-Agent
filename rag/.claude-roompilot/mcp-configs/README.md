# MCP Server 現況與推薦清單

> 建議同時啟用 < 10 個，避免佔用過多 context window。
>
> **本專案現況（2026-07-28 實測）**：專案根目錄**沒有 `.mcp.json`**，
> `.claude-roompilot/settings.json` 也**沒有 `enabledMcpjsonServers`** 設定 —— 即
> **本專案目前沒有任何專案層級的 MCP server**。所有工作都以內建工具
> （Read / Edit / Write / Grep / Glob / Bash）與 `.venv-rag/bin/python` 完成。
> 以下清單是「若要加裝，什麼對本專案有用」的評估，**不代表已安裝**。

## 目前可用（實際狀態）

| 來源 | 狀態 | 說明 |
| :--- | :--- | :--- |
| 專案 `.mcp.json` | **不存在** | 無任何專案層級 MCP server |
| `settings.json` 的 `enabledMcpjsonServers` | **未設定** | 沒有啟用清單 |
| 使用者層級（`~/.claude.json`）連接器 | 依個人環境而定 | 屬個人設定，非本專案配置，勿當成專案依賴 |
| 內建工具 | 可用 | Read / Write / Edit / Grep / Glob / Bash（macOS zsh） |

## 若要加裝：對本專案有實際幫助的

| Server | 用途（對應本專案的實際場景） | 需要 API Key |
| :--- | :--- | :--- |
| **context7** | 即時文檔查詢（Gradio 6、ChromaDB 1.5.9、sentence-transformers、Anthropic SDK 版本差異大） | CONTEXT7_API_KEY |
| ~~playwright~~ | **不建議**：本專案 E2E 一律走 CLI 端到端 + Gradio 人工冒煙（見 `commands/e2e.md`、`agents/e2e-validation-specialist.md`）。導入瀏覽器自動化屬策略變更，須先寫 ADR | 否 |
| **sequential-thinking** | 鏈式推理（檢索品質除錯：解析→硬過濾→向量→rerank 逐階段分析） | 否 |
| **memory** | 跨 session 記憶（記住六個坑，如 `rag_indexable` 不可進 `where`、rerank 不可再套 sigmoid） | 否 |
| **brave-search** | 網路搜尋（查 bge-m3／bge-reranker-v2-m3 模型卡與已知問題） | BRAVE_API_KEY |

### 視情況才有意義

| Server | 用途 | 安裝前提 |
| :--- | :--- | :--- |
| **github** | GitHub PR/Issue/Repo 操作 | **專案尚未 git init**，建立 repo 後才有意義；需 GITHUB_PERSONAL_ACCESS_TOKEN |
| **firecrawl** | 網頁爬取（研究家具風格資料來源） | 需 API Key |
| **exa-web-search** | 進階網路搜尋（找論文／模型評測） | 需 API Key |
| **fetch** | 單頁抓取（讀模型卡、官方文件頁） | 否 |

### 不適用於本專案（列出理由，避免日後誤裝）

| Server | 不適用理由 |
| :--- | :--- |
| **vercel / railway / cloudflare** | 本專案**無雲端部署**，只在本機 macOS 執行 `rag_pipeline/app.py` |
| **supabase / 各式雲端 DB** | 向量庫是本機 `chroma_db/`（collection `furniture_v3`），SQL 端交付走 `rag_export/` 檔案 |
| **前端元件庫類（Magic UI 等）** | UI 是 Gradio 6（Python），不是前端框架生態 |
| **AI 圖片生成類（fal-ai 等）** | 卡片圖來自本機預渲染 `rendering/output/…/正面(abo\|ikea)/`，無生成需求 |
| **容器／叢集管理類** | **本專案無 CI、無 Docker** |

## 如何新增（本專案目前尚未建立 `.mcp.json`）

### 步驟

1. 在**專案根目錄**建立 `.mcp.json`，內容為 `{"mcpServers": { ... }}`
2. 在 `mcpServers` 中加入 server 設定（見下方兩種型態）
3. 在 `.claude-roompilot/settings.local.json` 的 `enabledMcpjsonServers` 加入 server 名稱
4. 重開 session，用 `/mcp` 確認連線狀態

### 型態 A：HTTP server（**本專案優先採用**，不需額外執行環境）

```json
{
  "mcpServers": {
    "server-name": {
      "type": "http",
      "url": "https://example.com/mcp"
    }
  }
}
```

### 型態 B：本機 stdio server（以本專案既有的 Python 環境啟動）

```json
{
  "mcpServers": {
    "server-name": {
      "command": ".venv-rag/bin/python",
      "args": ["-m", "your_mcp_server_module"],
      "env": {
        "API_KEY": "${YOUR_API_KEY}"
      }
    }
  }
}
```

> 本專案唯一的執行環境是 `.venv-rag/`（Python 3.11.15）；`.venv/`（Python 3.9）**已不存在**，
> 任何設定都不得寫成 `.venv/bin/python`。

### 金鑰規範（必守）

- **絕不**把金鑰明碼寫進 `.mcp.json` —— 一律以環境變數注入（`"${VAR_NAME}"`）
- 本專案 Anthropic 金鑰慣例：`.anthropic_key` 純文字檔（已列入 `.gitignore`）或 `ANTHROPIC_API_KEY`
- 新增 `.mcp.json` 後，若內含任何憑證路徑，先確認 `.gitignore` 已涵蓋（**專案尚未 git init**，
  未來 init 時務必先補上再首次提交）

### 加裝前的自問

- [ ] 這個 server 解決的是本專案真實遇到的問題（檢索品質／文檔查詢／UI 驗證），而非「看起來很酷」
- [ ] 同時啟用數量仍 < 10，未明顯吃掉 context window
- [ ] 不屬於上表「不適用於本專案」的類別（雲端部署／前端元件／容器管理）
