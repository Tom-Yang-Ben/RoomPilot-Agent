# 已知限制

此文件列出公開 preview 未作為本次 release blocker 的事項。

- 僅支援 loopback 本機開發；API 尚未完成帳戶驗證、專案角色授權、速率限制與公開網路強化。
- 專案保存仍為 SQLite；並行寫入採 revision conflict，尚無多人協作合併策略。
- portable 家具是尺寸正確的程序化 fixture，不是商品模型、採購建議或 photorealistic asset。
- full profile 不附 catalog 資料、embedding、模型權重或 migration service；使用者需提供具有授權的資料。
- 第 8 步外部 AI 與 PDF 排版為 opt-in；未設定時明確 unavailable，不提供假成果。
- OCR、semantic segmentation 與 furniture RAG 依賴較大，預設不安裝，也不在離線 CI 下載。
- 部分歷史幾何流程同時存在 Shapely 與 raster adapter；`backend/engine/` 仍是最終合法性權威，後續應持續收斂重複路徑。
- 尚未定義 runtime upload／render retention policy；公開 deployment 前必須補上配額、清理與稽核。
