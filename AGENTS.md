# RoomPilot contribution rules

本文件適用整個 repository。修改前先讀 `README.md`、目標目錄最近的 `AGENTS.md`、相關 `docs/contracts/`，並執行 `git status --short`。

## 不可違反的契約

- 跨模組幾何使用公分；新長度／座標欄位用 `_cm`，面積用 `_m2`。
- 平面圖辨識輸出 `layout_json`；方案生成與編輯輸出 `scene_json`。
- RAG 只檢索關係與證據；家具位置、碰撞、淨空與合法性只由 `backend/engine/` 判定。
- `backend/server/static/` 是唯一正式前端，不得建立第二套 production app。
- portable profile 必須離線、可重現；fallback 不得假裝成外部 AI／資料庫成功。
- 不得提交 `.env`、憑證、使用者資料、資料庫 dump、模型權重、大型 GLB 或來源授權不明的資產。
- 公開開發伺服器只綁定 loopback；未完成安全強化前不得宣稱可公開網際網路部署。

## 跨模組修改紀錄

修改共享契約前，在工作說明記錄生產端、消費端、資料形狀、無法局部完成的原因，以及兩端驗證。前端程序化 fixture 只能呈現資料，不能取代後端幾何裁決。

## 最低驗證

```powershell
uv run python scripts/public_repo_check.py
uv run pytest -q
node --check backend/server/static/scene_v2.js
node --check backend/server/static/scene_viewer.js
git diff --check
git status --short
```
