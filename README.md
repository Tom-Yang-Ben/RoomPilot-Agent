# RoomPilot AI 室內風格與家具配置展示系統

這是一個以 FastAPI + Three.js 製作的室內風格與家具配置展示網站。  
目前主線不是重新訓練模型、也不是直接生成全新 3D 家具，而是使用既有 IKEA GLB 家具資料庫，依照平面圖、使用者問卷、風格規則、牆面與地板選擇，自動挑選家具並在網頁中呈現 3D 場景。

## 目前網站功能

- `首頁 /`：展示專題定位、功能流程與入口。
- `風格類型 /styles`：整理 12 種室內風格、Moodboard 圖、關鍵字、主色、材質、造型特徵、牆面與地板推薦。
- `家具資料庫 /library`：瀏覽家具資料、依風格與類型篩選，並用 Three.js 檢視 GLB 家具。
- `3D 場景展示 /scene`：上傳平面圖、填寫問卷、選擇風格、牆面、地板、家具需求，產生單房間 3D 家具配置預覽，並支援家具替換、移除、新增、整組重抽與視角切換。
- OpenRouter LLM：可選配。沒有 API key 時，後端會使用本地 fallback 規則生成場景。

## 必須 push 的資料夾與檔案

以下是目前網站版本運作需要的核心內容：

| 路徑 | 是否必須 | 用途 |
| --- | --- | --- |
| `web_fastapi/` | 必須 | FastAPI 後端、HTML、CSS、JS、Three.js viewer、靜態圖片與 Draco 解碼器 |
| `sf3d/metadata/` | 必須 | 家具資料庫 JSON、風格 JSON、Moodboard JSON |
| `dataset/ikea_glb_db/` | 必須 | 真實 IKEA GLB 家具模型，3D 檢視與場景生成會用到 |
| `docs/moodboard_assets/` | 必須 | Moodboard、代表家具圖與文件用圖片資產 |
| `requirements.txt` | 必須 | Python 套件安裝清單 |
| `README.md` | 必須 | 本網站專用說明文件 |
| `.env.example` | 建議 | OpenRouter API key 範例設定 |
| `PROJECT_CONTEXT.md` | 建議 | 專題交接紀錄與目前決策 |
| `docs/*.md` | 建議 | 補充規格、資料整理與開發紀錄 |
| `scripts/` | 建議 | 資料修復、圖檔生成、家具 JSON 維護工具 |

如果 GitHub 上傳容量太大，`dataset/ikea_glb_db/` 建議使用 Git LFS、雲端硬碟或 release asset 管理。  
但要注意：沒有這個資料夾，網站仍可開啟，家具資料也會顯示，但 3D 模型無法完整載入。

## 不建議 push 的內容

以下內容通常是本機環境、暫存檔或舊方案，不建議放進正式網站版 repository：

- `.env`
- `web_fastapi/.env`
- `.venv/`
- `.venv_triposr/`
- `tmp/`
- `web_fastapi/uploads/`
- `web_fastapi/__pycache__/`
- `__pycache__/`
- `Miniconda3-latest-Windows-x86_64.exe`
- `TripoSR/`，除非要另外保存過去測試紀錄
- `test_3Dfurniture/`，除非要另外保存舊版 demo

## 安裝環境

建議使用 Python 3.10 以上版本。

```powershell
cd D:\產業新兵計畫\期末專題\test_furniture
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

`requirements.txt` 目前包含：

- `fastapi`：建立網站 API 與靜態頁面服務。
- `uvicorn[standard]`：啟動 FastAPI server。
- `pillow`：讀取 GLB 內嵌圖片或產生家具預覽圖時使用。

## 啟動網站

請在專案根目錄執行：

```powershell
python -m uvicorn web_fastapi.main:app --reload
```

啟動後開啟：

```text
http://127.0.0.1:8000/
```

常用頁面：

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/styles
http://127.0.0.1:8000/library
http://127.0.0.1:8000/scene
```

## OpenRouter 設定

如果要讓 `/scene` 使用 LLM 產生 JSON 規劃，請建立 `.env` 或 `web_fastapi/.env`，並參考 `.env.example` 填入：

```env
OPENROUTER_API_KEY=你的_api_key
OPENROUTER_MODEL=可用的_openrouter_model
OPENROUTER_SITE_URL=http://127.0.0.1:8000
OPENROUTER_APP_NAME=RoomPilot
```

如果沒有設定 API key，系統會使用本地 fallback 規則，仍可做基本場景生成展示。

## GLB 模型路徑注意事項

家具資料庫位於：

```text
sf3d/metadata/ikea_furniture_style_database.json
```

其中家具會記錄 GLB 模型路徑。若專案搬到其他電腦，可能需要確認下列項目：

- `dataset/ikea_glb_db/` 是否存在。
- `.glb` 檔案是否真的在資料夾內。
- JSON 中的模型路徑是否指向目前電腦的正確位置。

如果模型卡片顯示有資料但 3D 無法出現，通常是 GLB 檔案缺失、路徑失效、模型過大、材質解碼失敗或瀏覽器尚未完成載入。

## 推送前檢查清單

推送前建議確認：

- `requirements.txt` 已存在。
- `web_fastapi/static/vendor/draco/` 已存在，否則部分壓縮 GLB 可能無法載入。
- `web_fastapi/static/style_images/` 有 12 種風格圖。
- `sf3d/metadata/ikea_furniture_style_database.json` 已存在。
- `sf3d/metadata/style_moodboard.json` 已存在。
- `dataset/ikea_glb_db/` 已包含實際 `.glb` 模型。
- `.env` 沒有被加入 git。
- 網站可正常開啟 `/`、`/styles`、`/library`、`/scene`。

## 專題定位

本專題目標是：

```text
平面圖輸入 -> 使用者風格與家具需求 -> LLM/規則整理 JSON -> 從既有 GLB 家具資料庫挑選 -> 生成可瀏覽的 3D 室內場景
```

因此，目前最重要的交付不是模型訓練，而是：

- 風格規則資料化。
- 家具資料庫可被查詢與篩選。
- GLB 模型可被正確載入。
- 使用者問卷能轉成後端 JSON。
- 3D 場景能依照牆面、地板、家具與風格產生可視化結果。
