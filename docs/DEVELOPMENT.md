# 開發與測試

## 環境

```powershell
uv sync --extra portable --group dev
Copy-Item .env.example .env
uv run uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload
```

不要改成 `0.0.0.0` 後直接暴露到網際網路。本機 LAN 測試也應先理解 [SECURITY.md](../SECURITY.md) 的未完成項目。

## 驗證層級

```powershell
uv run python scripts/public_repo_check.py
uv run pytest -q
node --check backend/server/static/scene_v2.js
node --check backend/server/static/scene_viewer.js
git diff --check
```

PostgreSQL、OCR、RAG 與 delivery 是明確 opt-in extras。預設 CI 不下載模型、不呼叫外部 AI、不連正式資料庫。需要瀏覽器測試時另執行 `uv sync --extra portable --extra delivery --group dev` 與 `uv run playwright install chromium`。

## Cache 與 runtime

SQLite、上傳檔、產出圖、PDF、模型 cache 與測試輸出只能放在 `.runtime/`、`.tmp/` 或其他 ignored 目錄。若測試需要檔案，使用 `tmp_path` 或 `examples/fixtures/` 中可重建的匿名資料。
