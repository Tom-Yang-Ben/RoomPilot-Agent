# 近景穿牆（X-ray Walls）修改歷程

> 對象：`app/`（FastAPI + React Three Fiber 版本）的前端。
> 影響檔案：`app/frontend/src/Scene.jsx`、`app/frontend/src/App.jsx`、`CLAUDE.md`。
> 日期：2026-06-30。

---

## 需求

> 「視野拉近時遮住視野的牆會變透明。」

把相機與焦點（OrbitControls target）之間、擋住視線的牆面，在**鏡頭拉近**時漸漸變透明，讓使用者看進房間內部；拉遠則回復完全不透明。並提供開關。

實作落在較新的 R3F app（`app/`，依 `CLAUDE.md` 為現行開發主線），而非舊的單檔 `2Dto3D.html`。

---

## 設計決策：為何用「逐片元 shader」而非「整面牆調透明度」

後端 `dxf_parser.py` 會把**所有牆**用 `unary_union` 合併成單一（或少數幾個）相連多邊形，房間是這個多邊形的「洞」。因此前端的 `wall_polys` 常常**只有一個 mesh**，涵蓋整張平面圖——近側牆與遠側牆屬於**同一個 mesh**。

→ 結論：用「整個 mesh 調 opacity」無法只挑出近側牆。必須在**逐片元（per-fragment）** 層級判斷，故採用 `material.onBeforeCompile` 注入著色器邏輯。

事前已比對實際安裝的 `three@0.160.1` 原始碼，確認注入點正確：
- 頂點：`#include <begin_vertex>`（提供 `transformed`），`modelMatrix` 為內建 uniform。
- 片元：`#include <dithering_fragment>`，最終輸出仍為 `gl_FragColor`。
- three 內建的世界座標 varying 名為 `vWorldPosition`，與自訂的 `vWorldPos` 不衝突。

---

## 第一版實作

### `Scene.jsx`
- `makeWallMaterial(color)`：建立 `MeshStandardMaterial`，以 `onBeforeCompile`：
  - 頂點階段注入 `varying vec3 vWorldPos`，由 `modelMatrix * transformed` 算出世界座標。
  - 片元階段以 `proj = dot(vWorldPos - uCamPos, uViewDir)`（沿視線方向的距離）判斷片元是否在焦點前方，前方者淡出至 `uMinAlpha`。
  - uniforms：`uCamPos / uViewDir / uCamDist / uFade / uMargin / uBand / uMinAlpha`。
- `Walls` 以 `useFrame` 每幀更新 uniforms：依相機到焦點的距離 `dist` 與平面圖對角線 `span` 推出 `uFade`（拉近→1、拉遠→0），並用 `THREE.MathUtils.damp` 平滑過渡。

### `App.jsx`
- `show` 狀態新增 `xray: true`，於核取方塊列加入 `近景穿牆` 標籤。

### `CLAUDE.md`
- 於前端架構段落補充此 shader 機制的說明。

---

## 對抗式審查（多代理）與修正

對改動跑了 5 面向的對抗式審查（shader/GLSL、R3F 生命週期、遮擋數學、透明排序、整合），每筆發現再獨立驗證。**確認 6 項真實問題、駁回 2 項誤報**（其一誤稱 `onBeforeCompile` 會與其他材質發生 program-cache 衝突——r160 實際會把注入原始碼納入快取鍵；其二為無害的「相機與焦點重合」退化）。

第一批修正（6 項）：

| # | 嚴重度 | 問題 | 修正 |
|---|--------|------|------|
| 1 | 中 | 清理用的 `useEffect([mat, geos])` 把**共用材質**與幾何綁在一起，導致每次拉桿都 dispose 仍在用的材質 → shader 重編譯、x-ray 閃一下 | 拆成兩個 effect：材質僅於顏色變更／卸載時 dispose，幾何於重建時 dispose |
| 2 | 中 | `depthWrite` 在牆仍約 98% 不透明時就關掉 → 遮擋突跳 | （當時）改在較透明時才關 |
| 3 | 低 | 方正平面圖經 `<Bounds fit>` 後起始就微透 | 加入 `want < 0.12` 死區，整圖視角保持完全不透明 |
| 4 | 低 | 接近俯視時遮擋判斷退化為「高度判斷」 | 視角越垂直，效果越淡出 `want *= min(1, hypot(viewDir.x,z)/0.35)` |
| 5 | 低 | 透明的牆仍投出實心陰影（幽靈陰影） | （當時）淡出後關閉 `castShadow` |
| 6 | 低 | `transparent=true` 使遠側窗戶排序錯誤 | 牆加 `renderOrder={-1}`，先於窗／門繪製 |

驗證：`npm run build` 通過（39 modules、exit 0）。

---

## 使用者回饋與第二版修正

> 「近景穿牆的效果過於強烈，且畫面渲染變得不穩定。」

### 診斷
1. **過於強烈**：`uMinAlpha = 0.12`（牆幾乎消失）＋觸發過早（`far = span*1.3`，約在預設取景距離就開始）。
2. **渲染不穩定（閃爍）**根因有二，都來自第一版做法：
   - 每幀在硬門檻（`uFade < 0.5`）切換 `depthWrite` / `castShadow` 布林值 → 相機停在門檻附近時逐幀翻動，連陰影都會閃。
   - 在「關閉 depthWrite」下把**單一、會自我重疊的整面牆 mesh** 做透明 → 該 mesh 自己的面依**索引順序**（非深度）混色，相機一動就閃爍。

### 修正
- **保持 `depthWrite` 開啟**（移除每幀切換）：淡化的近牆改為把 `uMinAlpha` 疊在**先畫的不透明室內**（地板／日後家具）上——穩定，且仍看得進房間。代價是看不到「透過近牆看到的遠牆」，但本來就不需要。
- 移除 `castShadow` 的每幀切換與相關 `groupRef` / `useRef`。
- 調弱效果：`uMinAlpha` 0.12 → **0.4**（清楚的半透明殘影，而非近乎隱形）。
- 收緊觸發範圍：`near` `span*0.55 → *0.45`、`far` `span*1.3 → *1.05`（須實際拉近、超過預設取景距離才開始）；`uBand` `span*0.22 → *0.16`。
- 保留：`want < 0.12` 死區、俯視淡出、`renderOrder={-1}`。

### 驗證
- `npm run build` 通過（39 modules、exit 0）。
- 對抗式複查（比對實際 `three@0.160.1` 原始碼）確認：
  - 不透明 pass 先於透明 pass（`renderScene`），故淡化近牆能正確以 0.4 疊在地板／家具上 → 「看進房間」成立。
  - 渲染清單以**物件**為單位排序，永不重排單一 mesh 自身的三角形；保持 `depthWrite` 開啟後，深度測試會把累積收斂為**時間上穩定**的合成 → 閃爍消除。
  - 移除布林切換消除了門檻翻動（含陰影閃爍）；`damp()` 單調不過衝，不會重新觸發門檻穿越。
  - 無 HIGH 級殘留問題。

---

## 目前狀態與可調旋鈕

最終參數（`Scene.jsx`）：

| 項目 | 值 | 說明 |
|------|----|------|
| `uMinAlpha` | `0.4` | 淡化後牆面殘影濃度（越高越不透明） |
| `near` | `max(2, span*0.45)` | 拉近到此距離達到完全淡化 |
| `far` | `max(near+1, span*1.05)` | 超過此距離不淡化（整圖視角） |
| `uBand` | `max(0.5, span*0.16)` | 淡化邊界的柔和度 |
| `uMargin` | `max(0.15, span*0.04)` | 焦點面附近的牆保持不透明 |
| 死區 | `want < 0.12 → 0` | 整圖視角完全不透明 |
| 俯視淡出 | `*= min(1, hypot(viewDir.x,z)/0.35)` | 視角越垂直效果越弱 |
| `depthWrite` | 維持預設 `true` | 穩定關鍵，不再每幀切換 |
| `renderOrder` | `-1` | 牆先於透明窗／門繪製 |

其中 `span` 為平面圖長寬的對角線（公尺），由 `Scene` 依 `data.bbox` 算出，使門檻隨模型大小自動縮放。**想再調整觀感**：改 `uMinAlpha`（殘影濃度）與 `near`／`far`（觸發範圍）即可。

### 已知的小取捨（穩定、純外觀，可日後再處理）
- 近牆淡化後，**遠側窗戶面板**會被它遮住（不影響看到室內地板）。
- 淡化的牆仍投出**實心陰影**（shadow map 無法依逐片元 alpha 變淡）。
