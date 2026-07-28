# 安全規範

本專案為本機單機執行（macOS），無對外服務、無 CI、無 Docker。
安全重點是**金鑰不外流**與**不信任 LLM 輸出**。

## 每次交付前必檢

（專案尚未 git init，以下清單在 init 前套用於「每次交付／收尾」，init 後即為 commit 前檢查）

- [ ] 無硬編碼秘密（Anthropic API key、任何 token）——`.anthropic_key` 內容絕不出現在程式碼或輸出
- [ ] 所有使用者輸入已驗證（Gradio 查詢框與 CLI argv：非空、長度上限、去控制字元）
- [ ] Chroma `where` 注入防護——條件只由受控詞彙（taxonomy／category_groups）組出，
      不接受使用者原始字串直接拼進 filter
- [ ] Gradio 卡片 HTML 已跳脫——家具名稱／描述／VLM 標註屬外部資料，插進 HTML 前必須 escape
- [ ] 服務只綁 `127.0.0.1:7860`，`share=True` 一律不開（開了等同對外暴露，CSRF／未授權存取風險）
- [ ] 認證／授權：本機無認證機制，因此必須確認 port 未對外轉發、未掛上公網
- [ ] 速率／成本限制已設定——批次 LLM 呼叫要有 `--limit` 與續跑機制，避免失控燒額度
- [ ] 錯誤訊息不洩露敏感資料（不回顯金鑰路徑內容、不把完整 traceback 丟到 Gradio 介面）
- [ ] LLM／VLM 輸出當**不可信資料**處理：先驗 schema 與受控詞彙，再進 `where` 或 UI

## 秘密管理

- 絕不在原始碼硬編碼秘密
- 使用環境變數 `ANTHROPIC_API_KEY`，或專案根的 `.anthropic_key` 純文字檔
  （`query_parser.py:25` 讀取；已列入 `.gitignore`）
- **絕不 `cat` / `echo` / 印出 `.anthropic_key` 內容**，也不得寫進 log、報告或 context 檔
- 啟動時驗證必要秘密存在（缺金鑰要快速失敗並給清楚訊息，而非在呼叫時才 500）
- 輪換任何可能已暴露的秘密（Anthropic Console 重新簽發並更新本機檔案）

## 依賴安全

- 提交 lock file：本專案尚無 `requirements.txt`／lock 檔，建議以
  `.venv-rag/bin/python -m pip freeze > requirements.txt` 固定版本後納管
- 新增依賴前確認：活躍維護、無已知漏洞、授權相容
- 定期執行 `.venv-rag/bin/python -m pip_audit`（或 `pip-audit`）掃描已知漏洞
- 模型權重只從 HuggingFace 官方帳號取得（`BAAI/bge-m3`、`BAAI/bge-reranker-v2-m3`），
  不載入來源不明的 pickle／checkpoint
- 不安裝來源不明的套件

## 安全事件回應

1. 立即停止
2. 載入 sunnydata-security skill 進行完整安全審查
3. 修復 CRITICAL 問題後才繼續
4. 輪換已暴露的秘密（金鑰外流時同步檢查 Anthropic 用量是否異常）
5. 審查整個程式碼庫是否有類似問題
