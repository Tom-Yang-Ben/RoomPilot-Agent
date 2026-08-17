# Contributing to RoomPilot

感謝你協助改善 RoomPilot。請從 issue 或可重現測試開始，讓行為、資料來源與風險邊界都能被審查。

## 開發流程

1. 從最新公開主線建立功能分支，不直接推送 `main`。
2. 執行 `uv sync --extra portable --group dev`。
3. 保持 `layout_json`、`scene_json`、公分座標與 engine-only geometry 契約。
4. 新資料或資產必須附來源、作者、授權、用途與 checksum；不確定就不要提交。
5. 執行 README 的完整驗證，再送出小而可審查的 pull request。

跨 API／前端契約的變更須同時測試生產端與消費端。外部服務在測試中必須 mock，不能讓預設測試下載模型、呼叫付費 API 或連正式資料庫。

## Commit 與 PR

- 說明使用者可觀察到的變化、相容性與驗證結果。
- 不混入生成快取、個人設定或無關格式化。
- 破壞性 schema 變更必須有 migration／rollback 說明。

提交貢獻表示你有權提供內容，並同意以本專案的 GPL-3.0-or-later 條款散布該貢獻。
