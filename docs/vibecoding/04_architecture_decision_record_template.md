# 架構決策紀錄(ADR)— RoomPilot-Agent

> 本文件由 VibeCoding 模板 04_architecture_decision_record_template.md 導入 RoomPilot-Agent 生成 | 基準分支 bella-local-20260726 | 2026-07-26

本文件分兩部分:

1. **空白模板**:新增 ADR 時複製使用,章節結構不可刪減。
2. **真實 ADR 範例**:5 則已在本 repo 查證過依據的既成決策,每則均註明 commit 或檔案位置。範例中的「決策者」欄依 commit 作者與 README 歸屬填寫;實際口頭決策過程未必留痕,標註「(未查證)」處待團隊補認。

## ADR 索引

| 編號 | 標題 | 狀態 | 日期 | 主要依據 |
| :--- | :--- | :--- | :--- | :--- |
| ADR-001 | 統一 `backend/` 單層套件與一人一目錄 | 已接受 | 2026-07-24 | commit `b04833c`、`README.md` |
| ADR-002 | 對外資料契約全面採用公分(cm) | 已接受 | 2026-07-23~24 | commits `d97f95c`→`714722f`、`b04833c` |
| ADR-003 | GLB 模型改由 CloudFront 供應(預設 `cloudfront` 模式) | 已接受 | 2026-07-23 | commit `3260497`、`backend/server/services/cloud_models.py` |
| ADR-004 | 官方雲端家具型錄 9,350 件為唯一母集合 | 已接受 | 2026-07-26 | commit `83b3c8a`、`backend/catalog/cloud_catalog.py` |
| ADR-005 | 型錄匯入硬化:狀態白名單 + 非破壞性預設 | 已接受 | 2026-07-26 | commit `e48cd67` |

---

# 第一部分:ADR 空白模板

# ADR-XXX: [簡短的決策標題]

> **狀態:** 提議中/已接受/已取代/已棄用 | **日期:** YYYY-MM-DD | **決策者:** [人員/團隊]

---

## 1. 背景與問題

- **上下文**: [需要做出此決策的背景]
- **問題**: [具體問題,盡量量化嚴重性]
- **驅動因素/約束**:
  - [驅動 1]
  - [約束 1]

## 2. 考量的選項

### 選項一: [名稱]
- **描述**: [實現方式]
- **優點**: [列舉]
- **缺點**: [列舉]
- **成本/複雜度**: 高/中/低

### 選項二: [名稱]
- **描述**: [實現方式]
- **優點**: [列舉]
- **缺點**: [列舉]
- **成本/複雜度**: 高/中/低

## 3. 決策

**選擇**: [明確指出選項]

**理由**: [為何此選項最符合需求,與其他選項的權衡比較]

## 4. 後果

- **正面**: [預期收益,盡量可衡量]
- **負面**: [引入的風險或技術債]
- **影響範圍**: [對其他元件/團隊的影響]
- **重新評估觸發**: [何時需重新審視此決策]

## 5. 執行計畫 (選填)

1. [步驟 1]
2. [步驟 2]

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| YYYY-MM-DD | [姓名] | [意見] |

---

# 第二部分:真實 ADR 範例

以下 5 則為回溯撰寫的既成決策紀錄。「決策」與「後果」段的每一項具體聲明皆於 2026-07-26 在基準分支上以 git/grep/讀檔查證;「考量的選項」段中未被採納的選項是依 commit 前後狀態回推,未必是當時實際討論過的方案。

---

# ADR-001: 統一 `backend/` 單層套件與一人一目錄

> **狀態:** 已接受 | **日期:** 2026-07-24 | **決策者:** Bella(整合 commit 作者)+ 團隊合併規則(README);口頭決策過程(未查證)

---

## 1. 背景與問題

- **上下文**: 專案由 6 人分別開發平面圖辨識、型錄、空間資料、選件 Agent、擺放引擎、伺服器與前端,各自分支曾使用不同的套件結構。commit `3260497`(2026-07-23)時伺服器程式仍在 `roompilot/server/` 路徑下(`git show --stat 3260497` 可證);`README.md:5-7` 記載更早曾有舊版巢狀後端命名。
- **問題**: 多套件命名並存造成 import 路徑不一致、分支合併時大量路徑衝突,且無法一眼判定每個目錄的負責人。
- **驅動因素/約束**:
  - 6 人平行開發,合併頻繁,需要最小衝突面的目錄劃分。
  - 與 Yen 分支及團隊既有的 `backend/frontend/data` 結構對齊(`README.md:5-6`)。

## 2. 考量的選項

### 選項一: 保留 `roompilot/` 套件名
- **描述**: 維持 commit `3260497` 時期的 `roompilot/server/`、`roompilot/agent/` 等路徑。
- **優點**: 不需大規模 rename,既有分支免改 import。
- **缺點**: 與團隊其他分支的 `backend/` 結構不一致,合併衝突持續。
- **成本/複雜度**: 低(短期)/高(長期合併成本)

### 選項二: 統一為 `backend/` 單層套件,一人一個主要目錄
- **描述**: 全套件 rename 為 `backend/`,並在 README 明定每人唯一主要目錄。
- **優點**: import 路徑單一;責任邊界清楚,合併規則可執行。
- **缺點**: 一次性大規模 rename,所有分支需跟進。
- **成本/複雜度**: 中

## 3. 決策

**選擇**: 選項二。

**理由**: commit `b04833c`(2026-07-24「整合:完成 Bella 公分制架構與十步空間規劃流程」)以 git rename(`{roompilot => backend}`,多數檔案 R100)完成統一,commit 訊息明言「統一 backend 目錄與公分制資料契約,清除重複舊版與本機素材」。責任目錄表定於 `README.md:9-16`:

| 負責人 | 唯一主要目錄 | 功能 |
|---|---|---|
| Cody | `backend/floorplan/`、`backend/upgrade3d/` | PNG、DXF、牆與門窗辨識 |
| Kai | `backend/catalog/` | 家具型錄、AWS Manifest、CloudFront 與隔離資料 |
| Django | `backend/spatial_data/` | 房間長寬、面積、比例及尺寸標註 |
| Yen | `backend/agent/` | 家具選件與擺放失敗修復策略 |
| AN | `backend/engine/` | 家具座標、碰撞與淨空檢查 |
| Bella | `backend/server/`、`frontend3d/` | FastAPI、1–10 流程、2D/3D UI |

`pyproject.toml:50` 以 `pythonpath = ["."]` 讓 pytest 直接以 repo 根匯入 `backend.*`;啟動指令為 `uv run uvicorn backend.server.main:app --port 8002`(`README.md:185`)。

## 4. 後果

- **正面**: import 路徑與啟動指令單一化;責任目錄成為合併規則的依據(`README.md:3-16`)。
- **負面**:
  - 路由未拆分:全部 44 條路由(27 GET + 16 POST + 1 PUT,grep `@app.` 實測)集中在 `backend/server/main.py`(2,796 行),全 `backend/server/` 無 APIRouter/include_router(grep 零命中)。
  - `backend/spatial_data/` 至今僅有 `.gitkeep`,無任何程式碼(實測)。
  - `backend/floorplan/__pycache__`、`backend/upgrade3d/__pycache__` 殘留已刪模組的 .pyc(opening_classifier、wall_openings 等),原始 .py 已不存在。
  - `README.md:5-7` 有編輯殘缺句(「不再建立\n不再保留舊版巢狀後端命名」),待修。
- **影響範圍**: 全體成員的分支與 import;tests/ 47 個測試檔中 23 個 import `backend.server`(grep 實測)。
- **重新評估觸發**: `main.py` 持續成長需要拆 APIRouter 時;或柏彥 room_pilot2 平行系統(repo 外,含第二後端)整合裁決時。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-07-26 | 本顥(回溯撰寫) | 依 commit `b04833c` 與 README 現況整理,口頭決策脈絡待團隊補認 |

---

# ADR-002: 對外資料契約全面採用公分(cm)

> **狀態:** 已接受 | **日期:** 2026-07-23~24 | **決策者:** 團隊(commit 作者含 bellayang312-source;7/7 週會決議 repo 內查無記錄,決議過程未查證)

---

## 1. 背景與問題

- **上下文**: DXF 解析器內部以公尺運算(`backend/upgrade3d/dxf_parser.py`,WALL_HEIGHT=2.7、WALL_THICK=0.18 皆公尺)、平面圖視覺管線內部亦為公尺,而家具型錄尺寸為公分(width_cm/depth_cm/height_cm),前端 three.js 另有自己的座標系。
- **問題**: 各模組單位不一,跨模組傳遞時的換算錯誤難以在測試中攔截;家具擺放與碰撞檢查對單位錯誤零容忍。
- **驅動因素/約束**:
  - 家具尺寸以公分表達最貼近型錄與台灣室內設計慣例。
  - 內部演算法(shapely、OpenCV)不必改單位,只需在邊界一次轉換。

## 2. 考量的選項

### 選項一: 全面統一公尺
- **描述**: 對外契約沿用 DXF/視覺管線的內部公尺表示。
- **優點**: 解析層免轉換。
- **缺點**: 家具型錄與 UI 顯示皆需小數;與型錄欄位命名(`*_cm`)矛盾。
- **成本/複雜度**: 中

### 選項二: 對外契約統一公分,內部各自保留、邊界單點轉換
- **描述**: 引擎、API、前端契約一律 cm;DXF 與視覺管線內部維持公尺,各設唯一轉換點。
- **優點**: 型錄、擺放、UI 全程整數級公分;轉換點可測試。
- **缺點**: 內部/外部雙表示並存,新讀者需知道邊界在哪。
- **成本/複雜度**: 中

## 3. 決策

**選擇**: 選項二。以四段 commit 鏈實施(2026-07-23,`git log` 實證):

1. `d97f95c` refactor(engine): adopt centimeter contract
2. `1baf027` refactor(server): use centimeters across layout workflow
3. `b7df307` refactor(app): complete centimeter workflow
4. `714722f` fix(app): harden centimeter migration boundaries

最終由 `b04833c`(2026-07-24)完成「公分制架構與十步空間規劃流程」整合。

**座標契約**(`backend/engine/models.py` 檔頭 docstring,實讀):長度一律公分;X 向右、Y 向上,原點在平面圖左下角;position 為物件中心;rotation 為逆時針度數,0 度時家具正面朝 +Y。序列化輸出 `schema_version: "2.0"`、`coordinate_unit: "cm"`(`backend/engine/schema.py:21-22`)。

**單位邊界(唯一轉換點)**:

- DXF 路徑:`backend/engine/dxf_room.py`(`_M_TO_CM = 100.0`,第 38 行)把 dxf_parser 的公尺輸出 ×100 進引擎,並平移到角落原點。
- 影像路徑:`backend/floorplan/vision/units.py` 的 `canonicalize_analysis_cm()`(第 30 行)是辨識結果公尺→公分的唯一轉換點。

**主流程步驟(程式碼權威)**:`frontend/scene_workflow.js:4-16` 的 `WORKFLOW_STEPS` 定義 11 個有序內部步驟:project → upload → recognition → calibration → space_confirmation → requirements → layout_2d → white_model_3d → realistic_3d → proposal_review → ai_render;其中 recognition 與 calibration 共用同一 `scale` 面板(`WORKFLOW_PANEL_BY_STEP`),故 UI 呈現為十步(`README.md:79-90` 的十步流程與此一致)。

## 4. 後果

- **正面**: 引擎、伺服器 API、前端契約單位一致;單位轉換集中兩個檔案,可被 `tests/test_dxf_room_units.py` 等測試覆蓋。
- **負面**:
  - 內部公尺表示仍存在,繞過邊界模組直接取用內部值會拿到公尺。
  - `backend/floorplan/vision/analysis.py:30` 的 COORDINATE_SYSTEM 常數仍宣告 `"unit": "metre"`(實測),為中間態宣告;最終回傳前才經 `canonicalize_analysis_cm` 改為 centimeter——引用該常數的文件會與對外契約矛盾。
  - DXF 自動比例本質是推測(`dxf_parser.py` 的 scale_basis 有 manual/insunits/normalized 三級,normalized 時尺寸非真實),公分數值精度受此上限。
- **影響範圍**: `backend/engine/`、`backend/server/`、`backend/floorplan/`、前端 `scene_v2.js` 全部。
- **重新評估觸發**: 若與以 mm 為單位的外部系統(如 room_pilot2)整合,需在邊界另立轉換點,不回頭改本契約。

## 5. 執行計畫(已完成)

1. 引擎契約先行(`d97f95c`)→ 伺服器(`1baf027`)→ 應用層(`b7df307`)→ 邊界加固(`714722f`)。
2. `b04833c` 整合收尾並統一 backend 目錄。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-07-26 | 本顥(回溯撰寫) | commit 鏈與邊界程式碼皆實測;決策會議記錄待補 |

---

# ADR-003: GLB 模型改由 CloudFront 供應(預設 `cloudfront` 模式)

> **狀態:** 已接受 | **日期:** 2026-07-23 | **決策者:** Kai(型錄/AWS 歸屬)+ Bella(commit `3260497` 作者為 bellayang312-source);分工細節(未查證)

---

## 1. 背景與問題

- **上下文**: 家具 GLB 模型體積大,`.gitignore` 明確排除 `dataset/`(第 34 行)與 `*.glb`(第 72 行,實測),模型不進 git;本機 GLB 依賴各成員自行下載,跨機器不一致。
- **問題**: 網站要能穩定載入數千件家具模型,不能依賴每台開發機的本機檔案。
- **驅動因素/約束**:
  - 9,350 件 GLB 已上傳 S3 並經 CloudFront 發佈(manifest `backend/catalog/data/manifests/glb_upload_all_result.csv`,9,350 資料列全為 `upload_status=uploaded`、delivery_url 全為 `https://ddgsm1yg3xikc.cloudfront.net/` 開頭——其他 agent 以 csv.DictReader 實測)。
  - 前端 three.js 的 GLTF loader 可直接吃 HTTPS URL。

## 2. 考量的選項

### 選項一: 本機 GLB + repo 外資料目錄
- **描述**: 維持 `data/dataset/` 本機檔案,由後端以 FileResponse 供應。
- **優點**: 離線可用。
- **缺點**: 1.3GB 資料每台機器都要放對位置;git 不管理,一致性無保證。
- **成本/複雜度**: 低(程式)/高(維運)

### 選項二: CloudFront 供應 + manifest 驗證,本機模式保留為 fallback
- **描述**: 預設由 CloudFront 轉址供應;只信任 manifest 驗證過的 URL;以環境變數切換 local 模式。
- **優點**: 跨機器一致;URL 經 manifest 白名單,不猜測拼接。
- **缺點**: 執行期需要網路;離線開發需另備方案。
- **成本/複雜度**: 中

## 3. 決策

**選擇**: 選項二,由 commit `3260497`(2026-07-23 feat(catalog): adopt verified CloudFront furniture manifest)引入 `services/cloud_models.py`(216 行)實施:

- `ROOMPILOT_MODEL_DELIVERY_MODE` 預設 `"cloudfront"`(`backend/server/services/cloud_models.py:49`),僅接受 local/cloudfront 兩值。
- CloudFront base 預設 `https://ddgsm1yg3xikc.cloudfront.net`(同檔第 34 行),可用 `ROOMPILOT_CLOUDFRONT_BASE_URL` 覆寫;manifest 路徑可用 `ROOMPILOT_GLB_MANIFEST_PATH` 覆寫(第 69、74 行)。
- `GET /api/furniture/{furniture_id}/model`(路由定義於 `backend/server/main.py:2621`)在有雲端 URL 時回 **307 RedirectResponse** 到 CloudFront(307 回應位於其呼叫的 `_model_response_for_merged_furniture`,main.py:917)。
- cloudfront 模式下,本機 glTF 拆解端點一律回 **410**:`/model.gltf`(main.py:2630)、`/buffer.bin`(main.py:2639)、`/images/{i}`(main.py:2649)、範例 GLB(main.py:2792)。
- `cloud_model_url()` 只回 manifest 驗證過的 URL,manifest 缺列即回 None,不拼 URL 猜測。

**理由**: 模型交付與 repo 解耦;manifest 是唯一信任來源,契約另見 `docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md`。

## 4. 後果

- **正面**: 9,350 件模型跨機器一致;前端可直接載 CloudFront URL(`frontend3d/src/Furniture.jsx` 的 furnitureUrl 對 http(s) URL 透傳)。
- **負面**:
  - 執行期依賴外部網路與 CloudFront 存活;離線時 3D 模型全部無法載入。
  - 離線備援是一顆 zip(1,517 GLB、可供 1,508 件使用,SHA-256 見 `README.md:228-241`,以 `scripts/verify_ikea_offline_backup.py` 驗證),與雲端隔離清單是不同集合、不可互代(README 明文)。
  - `main.py:101` 的 DATASET_DIR 指向 repo 根 `dataset/`(不存在,實際 GLB 在 `data/dataset/`),local 模式的本機解析路徑落空——cloudfront 模式不受影響;local 模式已實測(2026-07-26 本機):型錄 9,350 件仍載入成功,但 `_dataset_glb_lookup()` 為空,抽測家具的模型端點回 404「找不到這件家具對應的 GLB 檔案(dataset/ 未就緒?)」。
- **影響範圍**: `backend/server/`、`frontend3d/`、部署環境變數。
- **重新評估觸發**: CloudFront 費用或供應商變更;需要完全離線 demo 的場合。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-07-26 | 本顥(回溯撰寫) | 程式行號與 commit 實測;AWS 帳務與 bucket 治理不在本 ADR 範圍 |

---

# ADR-004: 官方雲端家具型錄 9,350 件為唯一母集合

> **狀態:** 已接受 | **日期:** 2026-07-26 | **決策者:** Bella(commit `83b3c8a` 作者 bellayang312-source)+ Kai(型錄歸屬);決策討論過程(未查證)

---

## 1. 背景與問題

- **上下文**: repo 同時存在舊六風格中文型錄 `furniture_catalog_6styles_zh.json`(10,550 件,其他 agent 實測)與已上雲的 9,350 件 GLB(manifest 驗證);兩者數量與 ID 集合不一致。
- **問題**: 若以舊型錄為準,會有超過一千件家具沒有可用的 3D 模型;網站、Agent 選件與 3D 擺放需要單一且模型保證存在的家具集合。
- **驅動因素/約束**:
  - 每件對外家具必須有經驗證的 CloudFront GLB。
  - 舊型錄的風格標籤、分類與擺放提示仍有價值,不應直接丟棄。

## 2. 考量的選項

### 選項一: 沿用舊 10,550 件型錄,缺模型者標記不可 3D
- **描述**: 型錄照舊,前端依 has_model 過濾。
- **優點**: 不需資料工程。
- **缺點**: 母集合含千餘件無模型項目;「有沒有模型」變成執行期判斷,測試難以立契約。
- **成本/複雜度**: 低

### 選項二: 雲端 9,350 件為母集合,舊型錄降級為 enrichment,無法映射者隔離
- **描述**: 以 cloud catalog JSON + manifest CSV 一對一決定母集合;舊型錄只能補風格/分類資訊,不能新增家具;映射不到的舊列進隔離區。
- **優點**: 母集合每件保證有已驗證的 GLB;數量成為可斷言的契約。
- **缺點**: 1,514 筆舊資料退出對外集合;329 件雲端家具暫無風格標籤。
- **成本/複雜度**: 中

## 3. 決策

**選擇**: 選項二,由 commit `83b3c8a`(2026-07-26 feat(catalog): integrate official cloud furniture catalog,+195,917 行)實施,核心為 `backend/catalog/cloud_catalog.py`(新增 339 行):

- `OFFICIAL_CATALOG_COUNT = 9_350`(cloud_catalog.py:18);`build_official_catalog()` 強制驗證:件數必須恰為 9,350(第 143-145 行)、ID 必須存在且唯一(第 150-151 行)、每件必須有驗證過的 HTTPS GLB URL(第 206 行),否則 raise ValueError。
- 舊資料映射僅允許兩種方式(`backend/catalog/data/README.md` 明文):家具 ID 完全相同,或標準化後唯一相同的英文名稱;歧義者不得進入家具 API、Agent 或 3D。
- 現行整合結果(`backend/catalog/data/README.md` 記載,與 `scripts/sql/README.md:25-29` 的 dry-run 期望值一致):正式 9,350 件、可補六風格 enrichment 9,021 件、無舊風格標籤 329 件、排除舊列 1,514 筆。
- 隔離區 `backend/catalog/data/quarantine/unmatched_cloud_furniture/unmatched_catalog_items.json` 實測 count=1514、items=1514;`tests/test_cloud_quarantine.py` 斷言隔離 ID 不得出現在 web model 集合。
- 伺服器啟動即載入合併型錄:`backend/server/main.py:403-409` 的 `load_style_database()` 呼叫 `load_official_catalog(...)`。
- 同 commit 一併交付 PostgreSQL 匯入工具 `scripts/sql/`(schema 3 張表 + view `official_furniture_with_glb`);執行期仍從 JSON+CSV 載入記憶體,伺服器不連 Postgres(grep 實測 main.py 無 psycopg2)。

**理由**: 「每件對外家具必有模型」從執行期判斷升級為載入期硬驗證,壞資料直接讓啟動失敗而不是靜默缺圖。

## 4. 後果

- **正面**: 型錄數量成為測試可斷言的契約(`tests/test_official_cloud_catalog.py`、`tests/test_catalog_six_style_contract.py`);ID 映射規則杜絕同名猜測。
- **負面**:
  - 329 件雲端家具暫無六風格標籤,風格篩選看不到它們。
  - 1,514 筆舊型錄資料退出對外集合,只存於隔離區供核對。
  - 8.0MB JSON + 9,351 行 CSV 進 git,repo 體積增加。
  - `backend/catalog/data/` 下「舊有:12種風格與JSON」(untracked)與「舊友:12種風格與JSON」(已追蹤)為近重複目錄(其他 agent diff 實測僅 README.md 不同),去留待裁決。
- **影響範圍**: `GET /api/furniture` 全部查詢、Agent 選件候選、3D 模型載入、PostgreSQL 匯入。
- **重新評估觸發**: 雲端集合增補(件數變動時 `OFFICIAL_CATALOG_COUNT` 與測試需同步改);329 件未分類項目補標籤時。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-07-26 | 本顥(回溯撰寫) | 常數行號、隔離區數量、README 數字皆實測;9,350/9,021/329/1,514 三處文件一致 |

---

# ADR-005: 型錄匯入硬化:狀態白名單 + 非破壞性預設

> **狀態:** 已接受 | **日期:** 2026-07-26 | **決策者:** Bella(commit `e48cd67` 作者 bellayang312-source)

---

## 1. 背景與問題

- **上下文**: ADR-004 的首版實作(`83b3c8a`)有三個弱點:(1) manifest 只驗 URL 是 HTTPS,不驗 `upload_status` 是否為可發布狀態;(2) PostgreSQL 匯入器預設**清除**官方集合以外的資料列,須加 `--keep-extra` 才保留——破壞性行為是預設值;(3) repo 內同時存在兩份 manifest(`glb_upload_all_result.csv` 與重複的 `glb_upload_manifest.csv`,後者 9,351 行),來源二義。
- **問題**: 上傳失敗的列可能混入正式型錄;誤跑匯入指令會刪掉資料庫既有資料。
- **驅動因素/約束**:
  - 匯入工具會被不同成員在不同機器執行,預設值必須安全。
  - manifest 是模型存在性的唯一信任來源,狀態欄位必須參與驗證。

## 2. 考量的選項

### 選項一: 維持首版(不驗狀態、預設清除、雙 manifest 並存)
- **描述**: 不動。
- **優點**: 無工作量。
- **缺點**: 三個弱點持續存在;誤操作即資料損失。
- **成本/複雜度**: 低

### 選項二: 白名單驗證 + 反轉預設為非破壞 + 刪除重複 manifest
- **描述**: 見決策段。
- **優點**: 壞列在載入期就 fail;預設安全;manifest 單一來源。
- **缺點**: 需要清除多餘列時要記得加旗標。
- **成本/複雜度**: 低

## 3. 決策

**選擇**: 選項二,由 commit `e48cd67`(2026-07-26 fix(catalog): harden cloud database import,+120/−9,371)實施(以下均出自該 commit diff,實測):

1. **狀態白名單**:新增 `READY_UPLOAD_STATUSES = {uploaded, already_exists, complete, completed, success, skipped_existing}`(`backend/catalog/cloud_catalog.py:19-26`);manifest 列的 `upload_status` 不在白名單即 raise ValueError(第 198-201 行)。
2. **非破壞性預設**:匯入器旗標由 `--keep-extra`(預設清除)反轉為 `--prune-extra`(預設保留,明確要求才清除)(`scripts/sql/import_official_catalog_to_postgres.py` diff 實證;用法見 `scripts/sql/README.md:56`)。
3. **單一 manifest**:刪除重複的 `backend/catalog/data/manifests/glb_upload_manifest.csv`(9,351 行,commit stat 實證)。
4. **路徑可覆寫**:`CLOUD_MANIFEST_PATH` 改由 `_project_path_from_env("ROOMPILOT_GLB_MANIFEST_PATH", ...)` 取得(`backend/server/main.py` diff 實證),測試與部署可注入替代 manifest。
5. **匯入器支援 .env**:python-dotenv 載入專案根 `.env`(override=False),資料庫連線參數不必寫死在 shell。

**理由**: 資料工程工具的預設值應該是「不動既有資料」;破壞性操作必須是明確選擇。狀態白名單把「上傳成功與否」納入契約驗證,與 ADR-004 的載入期硬驗證一致。

## 4. 後果

- **正面**: 全 manifest 9,350 列現況皆 `uploaded`(csv 實測;2026-07-26 收尾時以 csv.DictReader 複核仍為 9,350 列全 `uploaded`),白名單當下零誤殺;誤跑匯入不再刪資料;`tests/test_official_catalog_sql.py`(+31 行)與 `tests/test_official_cloud_catalog.py`(+24/−1 行)同 commit 補測試。
- **負面**: 需要清理資料庫多餘列時,忘了 `--prune-extra` 會殘留舊資料(view `official_furniture_with_glb` 的 9,350 驗證仍會把關,匯入後計數不符即 RuntimeError,`scripts/sql/import_official_catalog_to_postgres.py:341-345` 實測)。
- **影響範圍**: `backend/catalog/cloud_catalog.py` 的所有載入方(伺服器啟動、測試)、PostgreSQL 匯入流程。
- **重新評估觸發**: manifest 出現白名單以外的新狀態值時;Postgres 從匯入工具階段接上執行期 API 時(現行伺服器不讀 Postgres)。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-07-26 | 本顥(回溯撰寫) | 全部依 `git show e48cd67` diff 與現行檔案實測 |

---

## 待補事項

- 各 ADR 的「決策者」僅依 commit 作者與 README 責任歸屬回推,實際討論與拍板過程待團隊補認(標註「(未查證)」處)。
- ADR-003 local 模式已於 2026-07-26 實測補記(DATASET_DIR 缺失使 GLB 查找表為空、模型端點回 404),詳見 ADR-003 後果段;跨機器行為(如 `~/Downloads` zip 備援命中時)仍依各機器素材而異。
- 「舊有:/舊友:12種風格與JSON」重複目錄的去留為裁決事項,裁決後可新增 ADR。
