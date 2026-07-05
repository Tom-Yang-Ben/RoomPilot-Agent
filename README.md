### 後端環境設定 (Frontend)

1. **開啟新的終端機，進入 backend 目錄**：

    ```bash
    cd d:\app\backend
    ```

2. **建立虛擬環境及安裝套件**：

    ```
    python -m venv .venv

    .venv\\Scripts\\activate

    pip install -r requirements.txt
    ```

3. **啟動後端**：

    ```
    python -m uvicorn main:app --reload --port 8000
    ```

### 前端環境設定 (Frontend)

## 安裝 Node.js

前端使用 React + Vite，需要安裝 [Node.js](https://nodejs.org/) (建議 v18 以上版本)。

1. **開啟新的終端機，進入 frontend 目錄**：

    ```bash
    cd d:\app\frontend
    ```

2. **安裝 npm 套件**：

   ```bash
   npm install
   ```

3. **啟動前端**：

    ```bash
    npm run dev
    ```

### 開啟網頁

**於網址列輸入 localhost:5173**