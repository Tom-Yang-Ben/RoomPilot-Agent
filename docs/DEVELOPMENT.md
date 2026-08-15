# 開發與測試

## 環境

```powershell
uv sync --extra portable --group dev
Copy-Item .env.example .env
uv run uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload
```

不要改成 `0.0.0.0` 後直接暴露到網際網路。本機 LAN 測試也應先理解 [SECURITY.md](../SECURITY.md) 的未完成項目。

啟動後可由 <http://127.0.0.1:8002/docs> 查看目前 FastAPI 產生的 OpenAPI 文件；repository 不保存容易和程式漂移的端點快照。

## 驗證層級

```powershell
uv run python scripts/public_repo_check.py
uv run pytest -q
node --check backend/server/static/scene_v2.js
node --check backend/server/static/scene_viewer.js
git diff --check
```

已知漏洞可用 PyPA `pip-audit` 檢查四份已鎖定的 requirements；CI 使用相同指令，且不自動修改版本：

```powershell
uvx --from pip-audit==2.10.1 pip-audit --no-deps --skip-editable --progress-spinner off -r requirements.txt -r requirements-delivery.txt -r requirements-rag.txt -r requirements-ocr.txt
```

PostgreSQL、OCR、RAG 與 delivery 是明確 opt-in extras。預設 CI 不下載模型、不呼叫外部 AI、不連正式資料庫。需要瀏覽器測試時另執行 `uv sync --extra portable --extra delivery --group dev` 與 `uv run playwright install chromium`。

完整發布前驗收與乾淨 clone 要求見 [Release checklist](RELEASE_CHECKLIST.md)。

## Cache 與 runtime

SQLite、上傳檔、產出圖、PDF、模型 cache 與測試輸出只能放在 `.runtime/`、`.tmp/` 或其他 ignored 目錄。若測試需要檔案，使用 `tmp_path` 或 `examples/fixtures/` 中可重建的匿名資料。
