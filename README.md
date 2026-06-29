# RoomPilot Agent

這個專題用來從 IKEA 網站收集家具商品資訊，並下載可用的 3D GLB 模型檔，方便組員用於 RoomPilot 相關的空間、家具或室內配置實作。

## 來源 GitHub

目前專案來源 GitHub：

https://github.com/Tom-Yang-Ben/RoomPilot-Agent

## 專案內容

- `download_ikea_bookcases_10.py`：下載 IKEA 書櫃類商品的前 10 個 GLB 模型，並輸出 metadata。
- `download_ikea_sofas_10.py`：使用 Selenium 下載 IKEA 沙發類商品的前 10 個 GLB 模型，並輸出 metadata。
- `find_one_sofa_glb.py`：測試下載單一沙發 GLB 模型。
- `ikea-glb-downloader.py`：較早期的通用 IKEA GLB 下載腳本。
- `downloaded-files/`：已下載的 GLB 模型與 CSV/JSON metadata，可提供組員直接查看與使用。
- `sample.jpg`：專案範例圖片。
- `requirements.txt`：Python 套件需求。

## 安裝環境

建議使用 Python 虛擬環境：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 使用方式

下載書櫃模型：

```bash
python download_ikea_bookcases_10.py
```

下載沙發模型：

```bash
python download_ikea_sofas_10.py
```

下載完成後，檔案會放在：

```text
downloaded-files/
```

## 版本控管說明

會上傳：

- Python 腳本
- `requirements.txt`
- README
- 已下載的 GLB 模型與 metadata
- 範例圖片

不會上傳：

- `.venv/`、`venv/`、`env/`
- `__pycache__/`
- `.pyc` 快取檔
- `.env` 環境設定檔
- `ikea_products.db` 本機資料庫狀態檔

