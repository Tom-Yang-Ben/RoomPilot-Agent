# 房屋 3D 場景外殼建置重構 — 設計規格

- 日期：2026-08-02
- 依據：`docs/3D房屋場景建置流程.md`（使用者指定的取代邏輯，以下稱「流程文件」）
- 分支：`yen`
- 狀態：自主執行模式；使用者指令「以此邏輯取代當前房屋場景建置流程」即為規格核准來源

## 目標

以流程文件的邏輯取代 `backend/server/static/` 第 6 步 3D 房屋外殼建置：

1. **幾何運算全在純函式層**：新增 `scene_shell_geometry.js`（ES module、不 import three），輸出 SceneModel 描述；`scene_viewer.js` 只做「描述 → mesh」與材質。
2. **數值常數集中一處**：`DEFAULT_SCENE_CONFIG`，消除散落硬編碼（牆厚 12、窗台 90、地板外擴、相機係數…）。
3. **窗/門群聚 Union-Find**（中點 ≤30cm 且夾角 ≤10°、最長代表段、丟棄 <30cm、穩定索引），取代 3D 路徑的 `dedupeArchitecturalOpeningsFor3d`。
4. **開口雙路徑**：`infill = wallPolygons.length > 0` 切換。
   - 路徑 A（線段牆）`windowPieces`：玻璃 + 窗台下補實 + 窗頂上補實；門只留門楣。
   - 路徑 B（多邊形牆）`openingInfill` + `estimateProfile`：由鄰近牆頂點推定牆斷面（|dn|≤40cm、距端點≤50cm、spread<3cm fallback），補同厚同心連續牆 + 貼玻璃（厚 = profile + 2·epsilon）。
5. **地板 `floorBox`**：結構 bbox 外擴 `floorMarginCm`、薄盒 y∈[-FLOOR_THICKNESS, 0]，取代逐房外擴 14cm 的基底樓板。
6. **相機 `fitCameraPose`**：依結構 bbox（span×1.2、XZ 0.7 / Y 0.9、最小 span 100cm）取代手調 corner 公式。
7. **不變式鎖定**：以現有 node ES-module 測試機制（`tests/` 內 `node --input-type=module --eval`）為純函式層加單元測試。

## 座標與單位（對映流程文件 §1）

本 repo 前端已是公分制、{x, z} 世界對齊座標（後端 `_flip_parsed_z` 與前端 `floorplanForWorld` 在邊界翻轉一次）。流程文件的 `(x,y)→[x,0,-y]` 在本 repo 等價於 `(x,z)→[x,0,z]`（代換 y := -z），`rotationY = atan2(dy,dx) ≡ atan2(-dz,dx)`。純函式層以單一 `worldFromPlan` / `segmentRotationY` 集中此約定；`polygonShape` 的 `(x,-z)` + `rotateX(-π/2)` 映射維持不變並以測試鎖定。

## 與流程文件的刻意偏離（產品契約優先）

| 項目 | 文件 | 本次採用 | 原因 |
|---|---|---|---|
| 群聚身份 | 純幾何合併 | 兩開口 ID 皆非空且不同時**永不合併**；丟棄 <30cm 不適用於 confirmed/manual 開口 | 第 4 步擁有門窗身份（`dedupe` 註解明定「Step 6 must never merge distinct doors」）；文件的群聚對象是無 ID 的原始 DXF 符號線 |
| 窗 sill/head | config + windowOverrides | 逐開口 `windowOpeningMetrics`（`sill_height_cm`/`height_cm`/`head_height_cm`/`window_type`）為主，config 為預設 | 本 repo 資料契約已含逐窗欄位與落地窗型；比文件的索引 override 更精確 |
| 材質/燈光/座標軸 | MeshStandard 3 色 + Environment + axesHelper | 保留現有 PBR/GTAO 管線與 `createArchitecturalMaterial`；不加常駐 axesHelper | `test_scene_pbr_realism.py` 契約鎖定；正式產品畫面不放除錯座標軸 |
| 門楣/門葉 | 門 = 補門楣 | 補門楣（文件）+ 保留現有門葉/窗框組件 | 文件 §8 將此類列為附加層 |
| 天花/頂蓋 | 無 | 保留 `buildWallMassTopCaps` 與天花系統 | 產品功能，文件未涵蓋 |
| 牆高預設 | 280 | config 預設 280；資料 `room_height_cm`（≥210）優先 | 後端固定送 270，實務行為不變；缺值時依文件 |

## 資料流（取代後）

```
sceneData.floorplan (cm, 世界對齊)
  ▼ createRoom
plan = { walls: wall_segments, wallPolygons: wall_polys,
         windows: window_segments, doors: door_segments(經拓撲映射), … }
  ▼ scene_shell_geometry.buildSceneModel(plan, cfg)   ← 純函式
SceneModel { boxes[](wall/glass/floor, meta), polygonWalls[], floor, cameraPose }
  ▼ scene_viewer.js（薄層）
boxes → BoxGeometry mesh（材質依 kind + 現有 PBR）
polygonWalls → polygonShape + ExtrudeGeometry + rotateX(-π/2)
floor → floorBox mesh；cameraPose → corner 初始取位
附加層不變：門葉/窗框組件、踢腳板、頂蓋、天花、逐房材質、家具、燈光
```

- 路徑 A：牆段依 host 開口區間切分（junction inset/fill 一併移入純函式層），窗出 glass+sill/head 補實、門出門楣。
- 路徑 B：多邊形牆照擠出；每個開口 `estimateProfile` 推定斷面 → `openingInfill` 連續牆 + 玻璃（取代固定 12cm 的 sill/header 段）。

## 修改檔案（owner：Bella `backend/server/static/`、對應 `tests/`）

- 新增 `backend/server/static/scene_shell_geometry.js`（純函式層）
- 修改 `backend/server/static/scene_viewer.js`（createRoom 外殼路徑改為消費 SceneModel；保留函式名 `buildWallMass`/`buildSegmentWalls`/`buildStandaloneOpeningAssemblies` 作為描述→mesh 薄層）
- 修改 importer cache key：`scene_v2.js`、`scene.js`（`scene_viewer.js` 的 `?v=sha256-`）＋ `scene_viewer.js` 內新依賴的 `?v=`
- 測試：更新 `tests/test_scene_pbr_realism.py`（字串斷言）、`tests/test_scene_v2_contract.py`（dependency_edges + 行為）、新增 `tests/test_scene_shell_geometry.py`（純函式單元測試：群聚、雙路徑、estimateProfile、floorBox、fitCameraPose、空輸入）
- 後端不動：辨識止於 `layout_json`；`backend/engine/` 幾何裁決不變；`backend/upgrade3d/` 不動

## 跨資料夾修改聲明（AGENTS.md 格式）

- 主要 owner：Bella（`backend/server/static/`）
- 協作 owner：Cody（`layout_json` 消費格式不變，僅前端建 mesh 方式改變）、Ancai（不涉及家具合法性）
- 修改檔案：如上節
- 改變的資料契約或流程：無 payload 變更；純前端建置邏輯重構＋常數集中
- 為何不能只在單一目錄完成：測試在 `tests/`（對應模組 owner 規則）
- 兩端驗證測試：`pytest -q`（全套）+ 新增純函式單元測試 + `node --check`

## 已知視覺行為變更（需瀏覽器 QA 確認）

1. 基底樓板：逐房形狀+14cm → 結構 bbox+50cm 薄盒（`floorMarginCm` 一鍵可調；門檻破口覆蓋由 bbox 全覆蓋保證）。
2. corner 初始相機：手調公式 → bbox 推算（非置中平面圖也能對準）。
3. 路徑 B 開口補實厚度：固定 12cm → 依鄰牆推定（消縫、貼合真牆厚）。

## 驗證門檻

```powershell
node --check backend/server/static/scene_shell_geometry.js
node --check backend/server/static/scene_viewer.js
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
```

加上實際瀏覽器 QA（八步流程至第 6 步，DXF 與非 DXF 各一）。
