# RoomPilot

RoomPilot 是 AIPE03 第四組開發的本機優先室內規劃系統。它把平面圖辨識、人工校正、逐房需求、確定性家具配置、2D/3D 編輯、視角鎖定與可選的 AI 成果生成整合成八步流程。

本 repository 的公開預設是 `portable`：不需要 PostgreSQL、第三方家具資料、模型權重或 API 金鑰，家具會用有明確尺寸的程序化方塊呈現。`full` profile 僅供開發者接入自行準備且具有再散布／使用權的資料。

> 安全邊界：目前是 local-development preview，只應綁定 `127.0.0.1`。專案 API 尚未完成公開網際網路部署所需的驗證、授權、速率限制與營運強化。

## 快速開始

需求：Python 3.12、[uv](https://docs.astral.sh/uv/)；瀏覽器需支援 WebGL 2。Node.js 24 只用於 JavaScript 檢查與測試。

Windows：

```powershell
.\install.ps1
uv run uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload
```

Ubuntu／其他 Linux：

```bash
bash install.sh
uv run uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload
```

開啟 <http://127.0.0.1:8002>。portable profile 會使用本機 SQLite 專案儲存、匿名家具 fixture 與程序化 3D 家具。

## Quick start (English)

RoomPilot defaults to a self-contained `portable` development profile:

```bash
uv sync --extra portable --group dev
uv run uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload
```

Open <http://127.0.0.1:8002>. This preview is intended for loopback-only local development, not public-internet deployment. See [Development](docs/DEVELOPMENT.md) and [Full profile](docs/FULL_PROFILE.md).

## 八步流程

```text
1 建立專案
→ 2 上傳 PNG/JPG/DXF 平面圖
→ 3 標定並確認公分尺度
→ 4 校正空間、牆、門、窗、樑與柱
→ 5 填寫全屋與逐房需求
→ 6 產生並編輯 2D/3D 家具配置
→ 7 鎖定方案與逐房視角
→ 8 連接外部供應商後產生 AI 渲染與成果包
```

第 8 步未設定金鑰或排版引擎時會明確回傳 `503`／「尚未連接」，不會產生假圖或假成功。可先查看匿名範例 [public_sample_scene.json](examples/fixtures/public_sample_scene.json)。

## Runtime profiles

| Profile | 預設 | Catalog | 專案儲存 | 用途 |
|---|---:|---|---|---|
| `portable` | 是 | 專案自製小型 fixture | SQLite | 離線開發、測試、貢獻 |
| `full` | 否 | 開發者提供的 PostgreSQL/pgvector 與授權資產 | 目前仍為 SQLite | 資料庫整合開發 |

設定 `ROOMPILOT_PROFILE=full` 前請閱讀 [Full profile](docs/FULL_PROFILE.md)。無效的 profile 或 catalog provider 會在啟動／呼叫時立即失敗，不會靜默降級。

## 驗證

```powershell
uv run python scripts/public_repo_check.py
uv run pytest -q
node --check backend/server/static/scene_v2.js
node --check backend/server/static/scene_viewer.js
git diff --check
```

外部 AI、OCR 權重、Playwright 瀏覽器與 PostgreSQL 測試一律明確 opt-in；CI 的 portable 測試不存取網路。

## 架構與契約

- [系統架構](docs/ARCHITECTURE.md)
- [文件索引](docs/README.md)
- [開發與測試](docs/DEVELOPMENT.md)
- [發布檢查清單](docs/RELEASE_CHECKLIST.md)
- [資產與資料政策](docs/ASSET_POLICY.md)
- [已知限制](docs/KNOWN_LIMITATIONS.md)
- [layout_json／scene_json 邊界](docs/contracts/LAYOUT_SCENE_BOUNDARY_CONTRACT.md)

幾何跨模組一律使用公分；平面辨識輸出 `layout_json`，方案生成／編輯輸出 `scene_json`。Graph/vector RAG 只提供檢索證據，家具合法位置、碰撞與淨空只由 `backend/engine/` 判定。

## 參與貢獻與授權

請先閱讀 [CONTRIBUTING.md](CONTRIBUTING.md)、[SECURITY.md](SECURITY.md) 與 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。程式碼以 [GPL-3.0-or-later](LICENSE) 授權，著作權標示為「AIPE03 第四組」。第三方元件與資產見 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
