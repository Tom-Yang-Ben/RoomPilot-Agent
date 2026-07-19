# PROJECT_HANDOFF — RoomPilot 交接文件

> 產生日期:2026-07-19 ・ 產生方式:全專案實測稽核(測試/eval/API curl/前端建置全數實跑)
> 讀者:接手的組員或 AI 模型。與 SSOT(`docs/01_專題進度/RoomPilot_現行版本總覽.md`)衝突時,以 SSOT 為準。

## 1. 專案目前狀態(2026-07-19 實測)

RoomPilot = 室內設計即時提案溝通 Agent(AIPE03 第四組,Demo 死線 **2026-08-20**)。
主線為五階段流程(7/16 轉向,待 Sunny 老師批准):①尺寸與空間辨識 → ②需求問卷 → ③2D 傢俱佈局 → ④3D 白模 → ⑤雲端 API 高畫質渲染。

本日實測結果(全部在 repo 根目錄、本機 macOS 執行):

| 驗證項 | 指令 | 結果 |
|---|---|---|
| 後端測試 | `uv run pytest tests/` | **102 passed, 1 skipped**(3.3s) |
| 前端測試 | `cd frontend3d && npm test` | **32 passed** |
| 前端建置 | `cd frontend3d && npm run build` | 成功(bundle 1.1MB,有 >500KB 警告) |
| 窗偵測 eval(現行管線) | 批次重跑後 `eval_windows.py` | **精準 94% / 召回 95%**(門檻 ≥90/90) |
| 門過濾 eval | `eval_doors.py` | **19/19 = 100%**(門檻 ≥95%) |
| 窗段合併 eval | `eval_window_merge.py` | **precision/recall 100%/100%** |
| 批次管線 | `floorplan2dxf.py testdata/png <out>` | 21/21 成功、無例外 |
| 伺服器 + API | `uvicorn` 啟動 + curl 約 15 支路由 | 四頁 200;專案工作流(建立→上傳 floor21→analyze)走通;409/422/404 錯誤契約正確 |

註:那 1 個 skipped 是 `test_catalog_six_style_contract.py::test_known_external_model_resolves_to_a_real_glb_response`(依賴外部 GLB zip,環境沒有就跳過,非故障)。

## 2. 架構與重要檔案

單一 Python 套件 `roompilot/` +獨立 React 前端 `frontend3d/`。三條鐵律(違反前先讀根目錄 CLAUDE.md 的 invariants 節):
1. **家具座標只有 `roompilot.engine` 能算**(前端只顯示,不做本地擺放)。
2. **全專案唯一 FastAPI = `roompilot.server`**,前端一律走 API。
3. **引擎與 Python 業務層一律公分**;`engine/dxf_room.py` 是公尺→公分唯一邊界;payload 的牆/窗/門 segments 維持公尺(three.js 契約),轉換集中在 `scene_service.py`。三套座標系並存,rotation 方向相反,詳見 CLAUDE.md。

| 路徑 | 角色 |
|---|---|
| `roompilot/server/main.py`(3,660 行) | 全部約 50 支路由:五階段專案工作流(`/api/projects/...`)+ 舊四頁展示 + GLB 串流 + frontend3d 用的 `/api/plans`/`/api/plan`/`/api/upload` |
| `roompilot/server/scene_service.py` | 擺位服務+單位/座標轉換集中地+OpenRouter LLM 呼叫 |
| `roompilot/server/project_store.py` | 專案持久化:SQLite(WAL)在 `.runtime/projects.sqlite3`,含樂觀鎖 revision |
| `roompilot/engine/` | Shapely 碰撞+淨空引擎(公分);`schema.py` = LLM tool schema 契約 |
| `roompilot/floorplan/floorplan2dxf.py` | PNG→DXF 主管線(60KB);seg 第二意見融合靠 `models/floorseg.onnx`(93MB,**不在 git**) |
| `roompilot/upgrade3d/dxf_parser.py` | DXF→3D 樓面 JSON(公尺) |
| `roompilot/catalog/data/furniture_catalog_6styles_zh.json` | 主型錄 17MB;`taiwan_style_cards.json` = 6×3=18 色卡 |
| `frontend3d/src/App.jsx`(56KB) | 五階段流程主殼;`Furniture.jsx`+`snap.js` = 3D 拖曳 |
| `tests/`(15 檔)+ `frontend3d/src/*.test.js`(6 檔) | 後端 pytest(含 TestClient API 測試)+前端 node --test |
| `docs/ai-harness/` | DoD/FAILURE_LOG/TASK_TEMPLATES(宣稱完成前必讀) |

## 3. 如何啟動、測試與部署

前置:Python 3.12+、uv、Node 20+;`cp .env.example .env` 並填 `OPENROUTER_API_KEY`(不填也能跑,LLM 路徑自動 fallback 規則引擎)。

```bash
# 後端(必須在 repo 根目錄跑)
uv run uvicorn roompilot.server.main:app --port 8002
# 前端(開發模式,proxy → :8002)
cd frontend3d && npm install && npm run dev
# 測試
uv run pytest tests/ -v
cd frontend3d && npm test
# 三個 eval(門檻見 docs/ai-harness/DEFINITION_OF_DONE.md)
uv run --extra vision python roompilot/floorplan/eval_windows.py
uv run --extra vision python roompilot/floorplan/eval_doors.py
uv run python roompilot/upgrade3d/eval_window_merge.py
```

**部署現況:沒有任何部署設定**(無 Dockerfile/compose/CI)。目前唯一運行方式是本機 uvicorn + vite dev server。Demo 前需決定:(a) 就用本機跑(最穩,建議);(b) 要對外就得補 `npm run build` 產物的靜態掛載(FastAPI 目前**沒有**掛 `frontend3d/dist/`,只掛舊四頁)。

## 4. 已知問題與技術債

### 阻斷性(Demo 會失敗)——目前無
本日實測主鏈路(上傳→辨識→analyze;樣品選單;四頁;擺位 API)全部走通。

### 重要(不修有風險)
1. **`floorseg.onnx`(93MB)不在 git**(`.gitignore` 明文「進 git 前組長決定」)。只存在本機 `roompilot/floorplan/models/`。任何人 clone 後窗偵測召回率無聲從 95% 退回 92%(管線自動 fallback、不報錯)。**Demo 機器若不是這台,必須手動複製這個檔案。**建議:放雲端硬碟連結進 SSOT,或決定進 git。
2. **`testdata/` 的 tracked 產物(chk/dxf/dxf_scale/json,共 93 檔)是 7/12 舊管線輸出**,落後於 7/15 的 seg 融合 commit——前端若拿 `testdata/json/` 交接檔開發,窗資料比現行管線少 3 扇。重跑 `uv run --extra vision python roompilot/floorplan/floorplan2dxf.py testdata/png testdata/dxf` 即可刷新(本日已在 scratch 目錄驗證 21/21 成功),但會動到 93 個 tracked 檔案,建議由組長擇時執行+提交。
3. **雲端渲染 API 選型(站⑤)無人主責**(SSOT §14)——新五階段流程的關鍵路徑,8/20 前最大時程風險。
4. **手動拉比例 UI(F2a)未做**——SSOT 列為全案最高風險;後端 `/api/projects/{id}/floorplan/calibrate` 已存在並有測試,缺的是前端拉線 UI。
5. **room_pilot2 平行系統整合待裁決**(柏彥個人 repo,mm 制+第二後端,與三鐵律衝突)——拖越久 divergence 越大。

### 可延後
- 前端 bundle 1.1MB 未 code-split(vite 建置警告,不影響功能)。
- `docs/ai-harness/DEFINITION_OF_DONE.md` 寫「28 支路由零 TestClient 測試」已過時——現在 `tests/test_project_api.py`/`test_layout_api.py`/`test_requirements_api.py`/`test_plan_api.py` 都是 TestClient API 測試,文件待更新。
- eval 輸出夾雜「找不到設定檔 config.ini」提示(用內建預設值,無害但吵)。
- `docs/05_狀態與稽核/` 多份 STATUS 文件過時(DoD §0.1 已警告勿當現況)。
- 舊四頁展示(`/`、`/scene`、`/library`、`/panorama`)與 frontend3d 並存,前端主線已定 frontend3d,舊頁面何時退役待定。

### 安全性/資料面(本日檢查結果,無急迫問題)
- `.env` 未進版控(只有 `.env.example`);程式碼無硬編碼金鑰。
- CORS 限 `localhost/127.0.0.1`;`/api/plan` 有 basename 防路徑跳脫(已加測試);上傳有 20MB 上限;渲染 PNG 路徑取自 store 而非使用者輸入。
- 專案資料在 `.runtime/projects.sqlite3`(WAL)。**沒有備份機制**——Demo 前先手動備份 `.runtime/`,重要展示專案不要只存在這裡。
- 樂觀鎖(revision)保護多分頁併發寫入,409 錯誤契約已實測。

## 5. 建議的下一步(優先序)

1. **渲染 API 選型調研**(站⑤,無主、關鍵路徑)——先做 spike:拿 floor21 白模截圖 + 一張色卡,實測 2–3 家雲端 API 的效果/價格/延遲。
2. **F2a 手動拉比例 UI**(前端,後端 calibrate 已備好)。
3. 把 `floorseg.onnx` 的取得方式寫進 SSOT(雲端連結或進 git 的裁決)。
4. room_pilot2 整合裁決會議(附 SSOT §14 的衝突清單)。
5. 擇時重跑 floorplan 批次刷新 `testdata/` tracked 產物(見上面「重要 2」)。

## 6. 可直接交給其他模型執行的具體任務

照 `docs/ai-harness/TASK_TEMPLATES.md` 格式交辦;宣稱完成前必須過 `.claude/rules/verification.md`。

**任務 A(低成本模型):刷新 testdata 產物**
> 在 repo 根目錄跑 `uv run --extra vision python roompilot/floorplan/floorplan2dxf.py testdata/png testdata/dxf`,確認輸出「成功 21 / 失敗 0」;跑 `uv run --extra vision python roompilot/floorplan/eval_windows.py` 確認 ≥94/95;`git add` 明確列出 testdata/chk、testdata/dxf、testdata/dxf_scale、testdata/json 底下變更的檔案(不用 `git add .`),commit 訊息註明「刷新為 seg 融合後管線輸出」。證據:eval 數字+`git diff --stat`。

**任務 B(低成本模型):更新 DoD 過時敘述**
> 把 `docs/ai-harness/DEFINITION_OF_DONE.md` 層 5 的「28 支路由零 TestClient 測試」改為現況(列出 tests/ 裡四個 TestClient API 測試檔與涵蓋範圍),證據:檔案回讀。

**任務 C(中階模型):FastAPI 掛載 frontend3d 建置產物**
> 在 `roompilot/server/main.py` 加一個可選靜態掛載:`frontend3d/dist/` 存在時掛到某路徑(如 `/app`),不存在時不影響現有路由。加 TestClient 測試(dist 缺席時 404、存在時回 index.html)。證據:`npm run build` 後 curl。

**任務 D(中階模型):F2a 拉比例 UI**
> 前端 `FloorplanReview.jsx` 加「兩點拉線+輸入實際公分」互動,呼叫既有 `/api/projects/{id}/floorplan/calibrate`(契約見 `tests/test_project_api.py`)。完成標準=DoD 第 6 層(瀏覽器逐狀態實測+截圖),後端測試通過不算前端證據。

**任務 E(高階模型,先 spike 再定案):站⑤渲染 API 選型**
> 輸入:floor21 白模單視角截圖+18 色卡任一張。對 2–3 家雲端圖生圖 API 各做一次實測(效果、延遲、單張成本、商用授權),產出對照表+建議,不寫整合程式。

## 7. 本次交接處理改了什麼(2026-07-19)

| 變更 | 檔案 | 驗證 |
|---|---|---|
| `.gitignore` 豁免 `docs/04_契約與規格/`,救回被無聲吞掉的《系統架構圖_三層制_v1.0.md》 | `.gitignore` | `git check-ignore` 確認不再被忽略,`git status` 看得到該檔 |
| 樣品平面圖目錄改指 `testdata/dxf`(原 `testdata/pic/temp` 只有 7 張外來圖,選單裡挑不到 Demo 基準圖 floor21) | `roompilot/server/main.py` | curl:30 plans、floor21 可解析(28 牆/2 窗);新增 `tests/test_plan_api.py` 2 測試 |
| 修正 GLB 數量 1,808 → 1,517(實數,`git ls-files "*.glb" | wc -l`) | `CLAUDE.md`、`docs/資料夾功能總覽.md` | 磁碟與 git 追蹤數一致 |
| 新增本文件 | `PROJECT_HANDOFF.md` | — |

全套回歸:`uv run pytest tests/` → **102 passed, 1 skipped**;前端 32 passed;三個 eval 全達標。
