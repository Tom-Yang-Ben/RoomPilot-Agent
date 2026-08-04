# 3D 場景常駐與增量更新（2026-08-04）

使用者回報：流程每進下一步 3D 場景都重新建立，新增/刪除家具也讓整個場景重跑。
調查結論：六個 viewer（renderer/THREE.Scene）本來就常駐，問題在內容管線——
`loadScene()` 是唯一內容 API，每次清空全部家具＋重建房殼＋重抓所有 GLB；
家具增刪/替換全部收斂到整包重載（只保相機）；GLB 無任何快取；
第 6 步 A/B 預覽還借用前景 whiteViewer 連刷三次。

## 跨資料夾修改

- 主要 owner：Bella（`backend/server/static/`）
- 協作 owner：Yen（發起與實作；本次未動 `backend/agent/`）
- 修改檔案：
  - `backend/server/static/scene_viewer.js`（核心）
  - `backend/server/static/scene_v2.js`（呼叫端接線）
  - `backend/server/static/scene.js`（僅 cache-key 級聯）
  - `backend/server/static/scene.html`（僅 entrypoint cache-key）
  - `tests/test_scene_3d_lifecycle_contract.py`（新增契約測試）
- 改變的資料契約或流程：viewer 公開 API 新增 `addObject(item)`、
  `removeObject(furnitureId)`、`updateObject(item)`；`loadScene(sceneData)`
  介面不變，但內容未變時直接沿用既有場景（見下）。無後端/payload 變更，
  公分制與座標來源（engine）不受影響。
- 為何不能只在單一目錄完成：3D 生命週期由 Bella 的 static viewer 實作，
  Yen 目錄內沒有對應程式；本次為前端效能/正確性修復，未涉及 agent 邏輯。
- 兩端驗證測試：`tests/test_scene_3d_lifecycle_contract.py`（新）＋
  `tests/test_scene_v2_contract.py`（既有 cache-key 鏈與 ES module 語法）。

## 變更內容

### 1. GLB 頁面級快取（scene_viewer.js）

- 模組層 `gltfPromiseCache: Map<model_url, Promise<gltf>>`；同一網址只下載
  ＋解析一次，失敗不留快取（可重試）。六個 viewer 共用。
- 使用端一律 `cloneCachedGltfScene()`：clone 場景樹、幾何/貼圖沿用快取
  共用資源；clone 樹全部打上 `userData.roompilotCachedAsset` 旗標。
- `clearGroup` 抽出 `disposeObjectTree`，對 `roompilotCachedAsset` 物件
  跳過 dispose（快取資產跨場景共用，dispose 會弄壞其他 clone 與快取本體）。
  房殼、代理框、標記、接觸陰影照常釋放。
- 已知取捨：`applyStyleSkin` 產生的每實例材質不再顯式 dispose，交給 GC；
  GPU program 變體數量有限，屬有界洩漏。skinned mesh 用普通 clone（型錄
  家具皆靜態網格；若未來出現骨架模型需換 SkeletonUtils.clone）。

### 2. 增量家具操作（scene_viewer.js＋scene_v2.js）

- 抽出 `buildFurnitureWrapper(item, index, sceneData, failures)`（原
  loadScene 內逐件建構邏輯，行為不變），新增：
  - `addObject(item)`：只建這一件並加入場景。
  - `removeObject(furnitureId)`：只拆這一件（含選取狀態清理），其餘家具
    重編號（`renumberFurnitureWrappers` 只換編號標記 sprite）。
  - `updateObject(item)`：拆舊建新（替換模型/單件重擺用）。
  - 增量操作後同步 `lastSceneKey` 與診斷（`refreshFurnitureDiagnostics`，
    原 loadScene 尾段診斷邏輯抽出，行為不變）。
- 呼叫端改線（scene_v2.js）：
  - 刪除 `deleteSelectedSceneFurniture` → `removeObject`（viewer 未載入
    場景時 fallback 整包重載）。
  - 新增 `addSceneFurniture` → `addObject`。
  - 替換 `replaceSceneFurniture` → `updateObject`。
  - 單件重擺 `reflowSingleConfigurationFurniture` → `updateObject`。
  - 多件重擺（`prioritizeUnassignedConfigurationFurniture` 等）維持整包
    reload——多數家具都動了，增量無益；成本已因 1、3 大幅下降。

### 3. loadScene 跳過鍵（scene_viewer.js）

- `lastSceneKey`＝整包場景 JSON：內容未變且上次載入沒有模型 fallback 時
  直接沿用既有場景（步驟往返、還原重載、同方案重進全部命中；等於把第 7 步
  `ensureProposalSceneLoaded` 的版本快取泛化到所有 viewer）。有 fallback
  時仍重載，讓暫時性模型錯誤可重試。
- `lastShellKey`＝去除 `scene_objects` 後的世界座標場景 JSON：未變時跳過
  `createRoom`（牆體/天花/吊燈不重建），材質/風格切換只重灌家具皮。

### 4. A/B 方案預覽離屏化（scene_v2.js）

- `ensureRoomScheme3dPreviews` 改用離屏 `glbThumbnailViewer`，掛進既有
  `glbThumbnailSequence` 序列佇列（避免與 GLB 縮圖並發 loadScene 互清）；
  前景 whiteViewer 的場景與相機完全不動。
- 清除時機（「進入下一流程清除不要的場景」）：
  - `syncFurnitureInventoryAcrossSchemes`（家具清單變更、方案標記 stale）
    → `roomSchemePreviewCache.clear()`。
  - `completeRoomSchemeSelection`（完成選擇進入微調）→ 同上。

### 5. Cache-key 雜湊鏈級聯（CRLF 位元組）

- `scene_viewer.js` → `sha256-1187c05f6401`（`scene_v2.js`、`scene.js`
  的 import 已更新）。
- `scene_v2.js` → `sha256-c36a8b3f94ed`（`scene.html` entrypoint 已更新）。

補充：`test_viewer_keeps_missing_glbs_editable...` 以「`async function
loadScene` 到 `let lastSceneData`」切片驗 fallback 行為；因此
`buildFurnitureWrapper`/`refreshFurnitureDiagnostics` 必須放在 loadScene
**之後**（函式宣告 hoisting，語意不變）。未改動任何既有測試。

## 驗證（2026-08-04 已執行）

- `pytest tests/test_scene_3d_lifecycle_contract.py -q` → 6 passed（新增）。
- `pytest tests/test_scene_v2_contract.py -q` → 11 failed / 162 passed；
  失敗清單與同日同環境量測的 HEAD 基準**逐名相同**（本次修改前先還原
  HEAD 版靜態檔實測），零新增失敗。cache-key 鏈與 ES module 語法測試通過。
- 全套 `python -m pytest -q` → 21 failed / 780 passed；21 個全屬 yen 既有
  失敗群組（cody_room_recognition 4、questionnaire_visual_catalog 1、
  scene_6_8_wizard 4、scene_room_requirements 1、scene_v2 契約 11）。
- `git diff --check` 乾淨；編輯後全檔維持 CRLF（lone-LF=0）。
- 待辦：實際瀏覽器 QA（增刪家具不閃場、步驟往返即時、A/B 預覽不動前景）
  ——本機無瀏覽器環境，留給下次啟動 server 驗證。

## 追加修復（同日）：第 6 步起網頁當機／Shader Error 1282

使用者回報：第 6 步起 3D 場景容易讓網頁當機；console 洗版
`THREE.WebGLProgram: Shader Error 1282 - VALIDATE_STATUS false`（
MeshBasicMaterial、Program Info Log 全空）；截圖（feedback.png）第 7 步
proposalViewer 白畫面但狀態列顯示「場景已生成」。

診斷：info log 全空＋所有 program 驗證失敗＝**WebGL context 遺失**（GPU
記憶體耗盡）。三個成因，前兩個是本次生命週期改動引入的回歸：

1. GLB 快取「永不 dispose」→ 每個 WebGL context 的貼圖/幾何只增不減
   （離屏縮圖 viewer 一個 session 會滾過數百個模型，全部滯留）。
2. A/B 預覽改灌**整棟房子場景**進離屏縮圖 viewer 後未卸載，第 7 個
   context 常駐一份完整場景。
3. （既有）七個 renderer 的 setAnimationLoop 不論面板是否可見都全速渲染。

對策（同檔案，cache-key 已再級聯）：

- **LRU 上限**：`GLTF_CACHE_LIMIT = 48`，超限淘汰最舊條目並
  `disposeGltfResources()` 真正釋放幾何/貼圖——dispose 對仍在畫面上的
  clone 是安全的，three 下一幀惰性重新上傳，只有一次重傳成本。
  「快取資產不 dispose」語意改為「只由 LRU 淘汰統一釋放」。
- **`unloadScene()` viewer API**：整包卸載（家具＋房殼＋天花＋吊燈＋
  快取鍵歸零）；`ensureRoomScheme3dPreviews` 拍完 A/B 預覽即在縮圖佇列
  上卸載，離屏 context 不再滯留整棟場景。
- **隱藏 viewer 跳過渲染**：`setAnimationLoop` 開頭
  `if (container.offsetParent === null) return;`——隱藏面板（display:none）
  與離屏縮圖臺（position:fixed 移出畫面）都命中；`capturePng` 走顯式
  渲染不受影響，面板重新可見時自動恢復。

- 新雜湊：`scene_viewer.js` → `sha256-c4f9b4ad04df`、
  `scene_v2.js` → `sha256-e461fdef70ba`（scene.js／scene.html 已同步）。
- 驗證：`tests/test_scene_3d_lifecycle_contract.py` 新增
  `test_gpu_memory_stays_bounded_against_context_loss`（7 項全過）；
  `test_scene_v2_contract.py` 失敗清單仍與 HEAD 基準逐名相同（11 個既有、
  零新增）。
