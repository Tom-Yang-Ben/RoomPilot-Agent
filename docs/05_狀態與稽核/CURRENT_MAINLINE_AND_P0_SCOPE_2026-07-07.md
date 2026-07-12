# RoomPilot Current Mainline And P0 Scope 2026-07-07

本文件用來解決新專案接手時最容易混亂的問題：哪些是現行主線、哪些只是歷史參考、前端到底改哪一套、P0 先做什麼，以及資料契約要以哪裡為準。

若本文件和舊文件衝突，先以本文件為準，再回頭修正舊文件。

## 一、現行主線

目前現行主線是：

```text
RoomPilot-Agent/
  roompilot/
    server/
    engine/
    upgrade3d/
    catalog/
    floorplan/
  roompilot/server/static/
  dataset/
  testdata/
  pyproject.toml
```

現行產品目標維持：

```text
DXF 平面圖 + 使用者需求 + 風格條件 + 既有 GLB 家具資料庫
-> 後端配置與碰撞檢查
-> 網頁展示可操作的 3D 室內場景
```

不是直接生成全新 3D 家具模型。家具來源仍是既有 GLB 家具資料庫。

## 二、前端唯一主線

前端主線指定為：

```text
roompilot/server/static/
```

優先修改：

```text
roompilot/server/static/index.html
roompilot/server/static/styles.html
roompilot/server/static/library.html
roompilot/server/static/scene.html
roompilot/server/static/home.js
roompilot/server/static/styles.js
roompilot/server/static/library.js
roompilot/server/static/scene.js
roompilot/server/static/scene_viewer.js
roompilot/server/static/site.css
roompilot/server/static/common.js
```

`frontend3d/` 的定位：

```text
只作為 R3F 3D 編輯器支線與 F6 拖曳互動參考。
不要把 frontend3d 當成現行產品前端主線。
```

`web_fastapi/` 的定位：

```text
只作為歷史 UI 對照來源。
若要搬舊 UI，請只搬設計決策、中文化、互動概念，不要把 web_fastapi 當現行主程式。
```

## 三、歷史與忽略清單

### 現行主線

```text
roompilot/server
roompilot/server/static
roompilot/engine
roompilot/upgrade3d
roompilot/catalog
roompilot/floorplan
frontend3d（只限互動參考）
dataset
testdata
docs/RoomPilot_現行版本總覽.md
docs/CURRENT_UI_BASELINE_2026-07-07.md
docs/WEB_UI_STATUS.md
docs/SCENE_SYSTEM_STATUS.md
docs/MODEL_PIPELINE_STATUS.md
pyproject.toml
```

### 歷史參考

```text
docs/archive/
examples/
外部舊專案 D:/產業新兵計畫/期末專題/test_furniture/
web_fastapi/（若新專案內存在，只作歷史 UI 對照）
```

### 不要當現況

```text
TripoSR/
test_3Dfurniture/
舊版單檔 2Dto3D.html
version_snapshots/
tmp_*.py
tmp_*.png
.pytest_cache/
```

TripoSR 不是主線，只能視為已嘗試過但品質不足的歷史方案。

## 四、P0 / P1 / Reference 優先級

### P0：目前最先完成

1. 固定 `roompilot/server/static/` 為唯一前端主線。
2. `/scene` 以「上方條件設定、下方 3D 場景」為 UI 主結構。
3. `/scene` 保留並修穩：生成、替換、移除、新增、重排、拖曳、防碰撞、牆面淡出。
4. 家具資料與篩選全部繁體中文。
5. 家具尺寸不得明明標題有尺寸卻顯示 `-`，需從標題或檔名補 `size_cm`。
6. 地板與牆面 surface catalog 正式進 JSON，且 `/styles` 與 `/scene` 都能使用。
7. 地板材質要能呈現木紋、磁磚縫、大理石紋、微水泥質感。
8. 首頁 hover 功能列時，下方對應流程卡浮起。
9. `/library` 每頁 21 筆，分頁只顯示前 5 頁與最後 3 頁，按頁碼後回到上方。
10. 風格圖與圖內標註必須圖文相符，標註位置使用百分比，不用固定 pixel。

### P1：P0 穩定後再做

1. OpenRouter / LLM 產生更完整 client brief。
2. 更擬真的無縫地材貼圖。
3. 匯出 GLB / PDF / DXF 提案檔案。
4. 更完整的不規則房間避障與內牆吸附。
5. 多房間、多方案比較。

### Reference：只看概念，不直接搬

1. `frontend3d/` 的拖曳、吸附、視角互動。
2. `docs/archive/` 的早期 UX。
3. `examples/` 的 stub 與 demo flow。
4. 舊 `test_furniture/` 的 UI baseline 與 migration guide。

## 五、資料契約

### Scene API

保留並優先修穩：

```text
POST /api/scene/generate
POST /api/scene/mutate
GET  /api/scene/provider-status
```

`/api/scene/mutate` 必須支援：

```text
replace
remove
add
reshuffle
```

前端按下同風格替換、移除、新增、重排後，後端應回傳完整 scene，前端要立即更新 3D viewer 與家具列表。

### Surface Catalog

正式資料來源建議放在：

```text
roompilot/catalog/data/ikea_furniture_style_database.json
```

或拆成：

```text
roompilot/catalog/data/surface_catalog.json
roompilot/catalog/data/style_moodboard.json
```

但前端只應透過後端 API 或統一的 site data 取得，不要多處硬寫不同版本。

建議欄位：

```json
{
  "surface_id": "white_oak_plank",
  "name_zh": "白橡木長板地板",
  "material_group": "wood_floor",
  "pattern_zh": "長板拼接",
  "finish_zh": "自然木紋、霧面",
  "color_family": ["淺木色", "米色"],
  "texture_url": "/surface-assets/wood/white_oak_plank.jpg",
  "preview_url": "/surface-assets/wood/white_oak_plank.jpg",
  "repeat": { "x": 5, "y": 5 },
  "suitable_styles": ["scandinavian", "minimalist_muji", "japanese"]
}
```

每個風格要有：

```json
{
  "default_wall_surface_id": "warm_white",
  "default_floor_surface_id": "light_oak",
  "wall_surface_ids": ["warm_white", "milk_tea", "greige_panel"],
  "floor_surface_ids": ["light_oak", "white_oak_plank", "white_oak_tile"],
  "surface_pairings": [
    {
      "label_zh": "暖白牆面 + 淺橡木地板",
      "wall_surface_id": "warm_white",
      "floor_surface_id": "light_oak"
    }
  ]
}
```

## 六、地板與牆面分類

### 地板 material_group

```text
light_wood_floor：淺橡木、白橡木、自然木地板
medium_wood_floor：中淺橡木、人字拼、溫潤木地板
dark_wood_floor：胡桃木、深胡桃、深色實木
wood_look_tile：木紋磚，適合台灣住宅與好清潔需求
matte_tile：霧面石紋磚、清水模磚、灰磚
marble_tile：白紋大理石、灰紋大理石、亮面大理石
microcement：微水泥、礦物地坪、低接縫霧面地坪
pattern_tile：花磚、復古磚、幾何拼接磚
```

### 12 風格地板推薦

```text
北歐風：淺橡木地板、白橡木長板、白橡木紋磚
現代簡約風：霧面石紋灰磚、微水泥、灰紋大理石地磚
日系簡約 / 無印風：自然木地板、白橡木長板、杏白木紋磚
北歐現代風：白橡木紋磚、淺橡木地板、霧面石紋灰磚
工業風：深灰清水模磚、微水泥、深色木地板
日式侘寂風：微水泥、礦物地坪、自然木地板
美拉德風：胡桃木地板、焦糖木地板、深橡木地板
美式風：中深木地板、人字拼木地板、暖色木紋磚
美式鄉村風：刷白木地板、自然橡木地板、復古花磚局部
輕奢風：亮面大理石地磚、灰紋大理石、深淺對比石紋磚
古典風：深胡桃木地板、人字拼木地板、大理石拼花
混搭風：復古花磚、深淺拼接木地板、局部圖案磚
```

### 牆面分類

```text
warm_white：暖白牆面
milk_tea：奶茶色牆面
light_gray：冷灰牆面
blue_gray：灰藍牆面
greige_panel：米灰線板牆
mineral_beige：礦物米灰牆
limewash：灰泥 / 石灰刷紋牆
concrete_gray：水泥灰牆
brick_rust：紅磚牆
charcoal：炭灰牆
marble_wall：大理石牆面
wood_panel：木飾面牆
accent_color：局部跳色牆
```

## 七、修改前核准邊界

### 必須先告知使用者再改

1. 改分支、merge、rebase、reset、刪分支。
2. 大量搬移或刪除資料夾。
3. 改 `roompilot/server/main.py`、`scene_service.py`、`engine/`、`upgrade3d/` 的主流程。
4. 改 JSON schema 或 API payload 欄位。
5. 改首頁、風格頁、資料庫頁、場景頁的主視覺方向。
6. 新增大型依賴或改啟動方式。
7. 修改 `.gitignore`、`pyproject.toml`、部署或環境檔。

### 可以一次打包處理的小修

1. 中文文案修正。
2. CSS 間距、hover、按鈕顏色、卡片排版小調整。
3. 圖內標註位置微調。
4. 類型翻譯補字典。
5. 文件補充或整理。
6. 不改 API 的前端 render bug。

即使是小修，完成後也要簡短列出改了什麼與是否測試。

## 八、接手時最短閱讀順序

1. `CODEX_PROJECT_RULES.md`
2. `PROJECT_CONTEXT.md`
3. `docs/RoomPilot_現行版本總覽.md`
4. `docs/CURRENT_MAINLINE_AND_P0_SCOPE_2026-07-07.md`
5. `docs/WEB_UI_STATUS.md`
6. `docs/SCENE_SYSTEM_STATUS.md`
7. 依任務進入 `roompilot/server/static/` 或 `roompilot/server/`

## 九、驗收方式

啟動現行 FastAPI：

```bash
python -m uvicorn roompilot.server.main:app --host 127.0.0.1 --port 8002 --reload
```

驗收頁面：

```text
http://127.0.0.1:8002/
http://127.0.0.1:8002/styles
http://127.0.0.1:8002/library
http://127.0.0.1:8002/scene
```

基本驗收：

```text
首頁 hover 連動流程卡。
風格頁 12 種風格、圖文標註、牆地推薦都正常。
資料庫頁篩選全中文、每頁 21 筆、分頁回頂部。
場景頁生成、替換、移除、新增、重排後 3D 立即更新。
地板與牆面材質在 3D 中能辨識差異。
```
