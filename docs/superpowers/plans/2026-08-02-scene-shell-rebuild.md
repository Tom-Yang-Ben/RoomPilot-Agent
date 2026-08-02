# 房屋 3D 場景外殼建置重構 — 實作計畫

> **For agentic workers:** 依 spec `docs/superpowers/specs/2026-08-02-scene-shell-rebuild-design.md` 執行；本 session 以 inline 模式逐任務執行（自主模式，無 subagent 檢查點）。

**Goal:** 以 `docs/3D房屋場景建置流程.md` 的邏輯取代第 6 步 3D 房屋外殼建置：純函式幾何層 + 集中 config + Union-Find 群聚 + 開口雙路徑 + bbox 地板/相機。

**Architecture:** 新增純函式 ES module `scene_shell_geometry.js` 產出 SceneModel 描述；`scene_viewer.js` 縮為描述→mesh 薄層並保留產品附加層（PBR 材質、門葉/窗框、踢腳板、天花、逐房材質）。

**Tech Stack:** 原生 ES module、three.js（僅 viewer）、pytest + `node --input-type=module --eval` 單元測試。

---

### Task 1: tests/test_scene_shell_geometry.py（RED）

**Files:** Create `tests/test_scene_shell_geometry.py`

沿用 `test_scene_workflow.py` 的 `run_workflow_script` helper 模式。測試案例（全部 import `scene_shell_geometry.js`）：

- [ ] `test_window_symbol_lines_cluster_into_single_windows`：同窗 3 平行線（中點距 ≤30、夾角 0°）→ 1 群取最長；兩窗相距 >30 → 2 群；代表段 <30cm 且無 confirmed 身份 → 丟棄；穩定索引依中點 `(round(x*10), round(z*10))` 排序；兩個不同非空 `id` 永不合併；`confirmed: true` 短窗不被丟棄。
- [ ] `test_window_pieces_split_glass_and_infill`：`sill 90 / head 210 / 牆高 280` → glass 盒 `y∈[90,210]` 厚 `glassThicknessCm`；窗台補實 `y∈[0,90]`；窗頂補實 `y∈[210,280]`，厚 `12-2·0.2`；門（`withGlass=false`）只出門楣 `y∈[210,280]`、無 glass。
- [ ] `test_estimate_profile_reads_wall_cross_section`：開口線兩端附近放厚 24cm 的多邊形牆頂點 → `thicknessCm≈24`、`offsetCm` 為中點、`startU<0`、`endU>len`（搭接）；頂點 spread <3cm → fallback `wallThicknessCm`、`fallback: true`。
- [ ] `test_opening_infill_window_full_wall_door_lintel`：窗 → 連續牆 `y∈[0,280]` 厚 = profile、玻璃 `y∈[90,210]` 厚 = profile + 2ε；門 → 只補 `y∈[210,280]`、無玻璃。
- [ ] `test_floor_box_expands_structure_bbox`：bbox `[-200,-150,200,150]`、margin 50 → center `[0,-2.5,0]`、size `[500,5,400]`。
- [ ] `test_fit_camera_pose_follows_bbox`：span=max(w,d,100)、d=span·1.2、position `[cx+0.7d, 0.9d, cz+0.7d]`、target `[cx,0,cz]`。
- [ ] `test_empty_plan_builds_empty_model`：空輸入 → `boxes=[]`、`polygonWalls=[]`、`floor=null`、`cameraPose` 仍可用（fallback bbox），不丟例外。
- [ ] `test_build_scene_model_uses_infill_switch`：有 `wallPolygons` → 開口走 infill（模型含 `role:"opening-infill-wall"`）；只有 `walls` → 牆段在 hosted 窗區間被切分（該段 boxes 數 >1）且含 `role:"window-sill-infill"`。

Run: `.\.venv\Scripts\python.exe -m pytest -q tests/test_scene_shell_geometry.py` → 預期 RED（模組不存在）。

### Task 2: backend/server/static/scene_shell_geometry.js（GREEN）

**Files:** Create `backend/server/static/scene_shell_geometry.js`（純函式、不 import three；僅 import `scene_architecture.js`、`scene_window_types.js` 帶 `?v=sha256-` key）

匯出（對映流程文件章節）：

| 匯出 | 文件 | 內容 |
|---|---|---|
| `DEFAULT_SCENE_CONFIG` | §5.1 | wallHeightCm 280、wallThicknessCm 12、window {sillCm 90, headCm 210}、door {sillCm 0, headCm 210}、glassThicknessCm 2、epsilonCm 0.2、frameAllowanceCm 0.6、minWindowWidthCm 30、minOpeningIntervalWidthCm {door 68, window 50}、clusterDistanceCm 30、clusterAngleDeg 10、profile {normalSpreadMaxCm 40, endDistanceMaxCm 50, minThicknessCm 3}、floorMarginCm 50、floorThicknessCm 5、minCameraSpanCm 100、cameraDistFactor 1.2、axesSizeCm 200 |
| `shellConfig(overrides)` | §5.1 | 合併覆寫；`wallHeightCm` 數值下限 210 |
| `worldFromPlan(x, z)` | §1 | `[x, 0, z]`（z 已於後端邊界翻轉；註解對映文件 `(x,y)→[x,0,-y]`） |
| `segmentRotationY(dx, dz)` | §1 | `atan2(-dz, dx)` |
| `clusterOpeningSegments(openings, cfg, kind)` | §5.3 | Union-Find；合併條件中點距 ≤clusterDistanceCm 且方向夾角 ≤clusterAngleDeg（mod 180°）；**兩 ID 非空且不同永不合併**；代表段 = 先 manual/confirmed 鎖定者、再最長；`kind==="window"` 時代表段 <minWindowWidthCm 且未鎖定 → 丟群；依代表中點 rounding 排序回傳 |
| `estimateProfile(opening, polygons, cfg)` | §5.4B | u/n 投影；`|dn|≤40` 且距任一端 ≤50 的頂點；spread<3 → fallback `{thicknessCm: cfg.wallThicknessCm, offsetCm 0, startU 0, endU len, fallback true}`；否則 `{thicknessCm: spread, offsetCm: 中點, startU: min(0,minDu), endU: max(len,maxDu)}` |
| `windowPieces(opening, metrics, cfg, opts)` | §5.4A | 於開口自身線段出 BoxDesc：glass（sill..head、厚 glass）、sill 補實（0..sill−frameAllowance）、head 補實（head+frameAllowance..牆高）、厚 `wallThicknessCm−2ε`；`opts.withGlass=false`（門）→ 僅門楣 head..牆高 |
| `openingInfill(opening, metrics, profile, cfg, opts)` | §5.4B | 連續牆沿 startU..endU、法向偏 offset、厚 profile；窗 bottom 0、門 bottom head；窗玻璃 sill..head 厚 profile+2ε |
| `structureBbox(plan)` | §3.4 | 只由 walls/wallPolygons/windows/doors 座標決定；無結構 → null |
| `floorBox(bbox, cfg)` | §5.6 | center `[(minX+maxX)/2, −t/2, (minZ+maxZ)/2]`、size `[w+2·margin, t, d+2·margin]` |
| `fitCameraPose(bbox, cfg)` | §5.7 | span=max(w,d,minSpan)、dist=span·factor、pos `[cx+0.7d, 0.9d, cz+0.7d]`、target `[cx,0,cz]` |
| `buildSceneModel(plan, cfg)` | §5 | 見下 |

`buildSceneModel(plan, cfg)`：

1. 門先過 `doorOpeningForWallTopology(walls, door, thickness)`（沿用 scene_architecture），再 `clusterOpeningSegments`；窗直接群聚。`step4_skip_wall_cut` 的開口不出 pieces、不切牆。
2. `infill = wallPolygons.length > 0`（文件 §5.4 切換）。
   - **路徑 B**：`polygonWalls` 描述 `{region, heightCm}`；每開口 `estimateProfile` → `openingInfill`。
   - **路徑 A**：每牆段（長 ≥4）以 `openingWallInterval` 求 hosted 區間（門排除 `topology_gap`），區間之間出 `role:"wall-section"` BoxDesc（`wallSectionSpan` 消縫；含 `meta.segmentIndex`、`meta.from/to`）＋每段一個 `role:"top-cap"`（高 2.5、y=牆高+1.25）；每開口出 `windowPieces` / 門楣；牆端點橋接 `role:"junction-fill"`（距離 0.8..max(36,2·厚)、中點避開開口 ≥ max(0.6·厚,7)，同現行 `buildConfirmedWallJunctionFills` 邏輯）。
3. `floor = floorBox(structureBbox(plan) || fallbackBbox(plan), cfg)`；fallback 由 `plan.widthCm/depthCm` 置中推得；兩者皆無 → `floor: null`。
4. `cameraPose = fitCameraPose(bbox 或 fallback)`。
5. 回傳 `{ boxes, polygonWalls, floor, cameraPose, bbox, openings: { windows, doors } }`（openings 為群聚後代表，含 metrics 與 anchor，供 viewer 佈置窗框/門葉）。不可變：不修改輸入物件。

Run: 新測試轉 GREEN；`node --check` 通過。

### Task 3: scene_viewer.js 改薄層

**Files:** Modify `backend/server/static/scene_viewer.js`

- [ ] import 新模組（帶 `?v=sha256-`）。
- [ ] `createRoom`：組 `plan`（walls/wall_polys/window_segments/door_segments、widthCm/depthCm）與 `cfg = shellConfig({ wallHeightCm: room_height_cm })` → `const shellModel = buildSceneModel(plan, cfg)`；存 `roomGroup.userData.shellModel`。
- [ ] 刪除 createRoom 內散落 `wallThickness = 12`、`dedupeArchitecturalOpeningsFor3d` 呼叫（3D 路徑）改用 `shellModel.openings`。
- [ ] `buildSegmentWalls` 重寫為薄層：吃 `shellModel.boxes`（A 路徑 role）→ mesh；面材質仍以 `meta.segmentIndex` 找回 segment 走 `isExteriorWallSegment`/`faceMaterials`；`role:"wall-section"` 附踢腳板（同現行尺寸 7.5×厚+2.2、y 3.8）。
- [ ] `buildWallMass` 保留（吃 `shellModel.polygonWalls` 擠出）；`buildWallMassTopCaps` 不變。
- [ ] `buildStandaloneOpeningAssemblies` 薄層化：牆補實/玻璃改由 model boxes 供給；保留窗框/門葉組件；`buildOpeningAssembly` 移除自帶玻璃 Plane（glass 由 model 供給，`frameDepth` 取 model profile 厚度）。
- [ ] 地板：`createFloorGeometry` 改為由 `shellModel.floor` 出 BoxGeometry mesh；`presentationGround.position.y` 降至 floor 盒下方（−6.2）；刪 `FLOOR_SLAB_BLEED_CM` 與 `expandedFloorSlabRing` 用法（`synchronizedFloorRegions` 若仍被逐房材質/walk 用則保留該 import）。
- [ ] 相機：`setCameraPreset("corner")` 改用 `roomGroup.userData.shellModel?.cameraPose`（無則 fallback 現公式）；確認 far 平面 ≥ 100000。
- [ ] glass BoxDesc → `MeshPhysicalMaterial` + `architecturalPbrProfile("glass")`、`userData.roompilotArchitecturalDetail = "window-glass"`。

### Task 4: cache keys 與釘住測試

**Files:** Modify `backend/server/static/scene_v2.js`（viewer hash）、`backend/server/static/scene.js`（viewer 版號）、`tests/test_scene_v2_contract.py`、`tests/test_scene_pbr_realism.py`

- [ ] `dependency_edges` 增 `"scene_viewer.js": [..., "scene_shell_geometry.js"]` 與 `"scene_shell_geometry.js": ["scene_architecture.js", "scene_window_types.js"]`。
- [ ] 重算全部受影響 `?v=sha256-<12>`。
- [ ] `test_dxf_wall_mass_is_extruded_before_segment_fallback`、`test_floor_is_clipped_to_cody_floorplan_exterior`（更名為 floorBox 行為）、`buildSegmentWalls` 區段字串斷言改對新架構（斷言改為：viewer 只組 mesh、幾何在 `scene_shell_geometry.js`）。

### Task 5: 驗證與提交

```powershell
node --check backend/server/static/scene_shell_geometry.js
node --check backend/server/static/scene_viewer.js
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
```

- [ ] 逐項排除失敗（先讀 root cause 再修；不得為過測而弱化斷言語意）。
- [ ] Commit（WHY/WHAT/IMPACT）：`feat(scene): 依 3D 房屋場景建置流程文件重構外殼幾何為純函式層`。
- [ ] 報告：視覺變更三項（地板 bbox+50、相機 bbox 推算、路徑 B 斷面推定）與瀏覽器 QA 清單。
