# 證據文件：第 5 步「問卷 → RAG → JSON → 第 8 步生圖」鏈路在兩分支的實際狀態

收件人：全體組員。
目的：為「第 5～7 步採 `bella-test1`」的整合規格補一條**邊界條文**提供依據。
本文件**不推翻**整合方向本身；只主張其中一條資料鏈必須保留 `ben-local` 實作。

立場先講清楚：這不是評比誰的程式碼寫得好。`bella-test1` 的問卷**資料模型**
（尤其逐房生圖設備六題）設計得比 `ben-local` 完整，值得搬。本文件量測的是另一
件事——**「今天」哪一邊的鏈路是端到端通的**。所有主張附一行可複驗指令，任何人
在 repo 根目錄執行即可自行驗證，不需要相信本文件的轉述。

---

## 0. 結論摘要

| 鏈路環節 | ben-local | bella-test1 |
|---|---|---|
| 全屋問卷題可作答 | 8/8 題 | 1/5 題（其餘容器 hidden，證據 E1） |
| 問卷 → 家具檢索 | pgvector 語意檢索（證據 B1） | 型錄過濾＋前端關鍵詞加權；RAG 僅重排且預設停用（證據 E4、E5） |
| 問卷 → 結構化 JSON | 通（digest） | 通（`buildRoomRequirementsPayload`，此段兩邊都好） |
| JSON → 第 8 步生圖請求 | 通，按鈕直綁（證據 B2） | **斷**：送出 dialog 的 DOM 不存在，payload 組裝函式為不可達死碼（證據 E2） |
| 生圖 prompt 組裝 | 有（`build_render_prompt`，證據 B3） | **無**：後端 0 處 prompt 組裝，外包給未設定的外部 provider（證據 E3） |
| 第 8 步完成標記 | 通 | **斷**：`workflow.complete("ai_render")` 位於死碼內，八步流程無法收尾（E2 連鎖） |

---

## 1. bella-test1 側證據（E1–E5）

以下指令都在 repo 根目錄執行，直接讀 `bella-test1` 分支的檔案內容，
不需要 checkout。

### E1．全屋問卷 5 題中 4 題永遠無法作答

容器在 HTML 出生就是 `hidden`，且全前端沒有任何一行解除：

```
git show bella-test1:backend/server/static/scene.html | findstr "whole-house-fields"
```
預期輸出（注意行尾的 `hidden`）：
`<div id="whole-house-fields" class="rp-test2-profile-grid" hidden></div>`

```
git show bella-test1:backend/server/static/scene_v2.js | findstr "wholeHouseFields"
```
預期輸出只有兩行：一行取元素、一行寫 `innerHTML`——**沒有任何一行
`hidden = false` 或 `removeAttribute`**。家庭成員／工程狀態／成員寵物／預算
時程四題渲染進一個永遠不可見的容器，收值時全部是空字串。

### E2．第 8 步生圖送出是不可達死碼

送出前必經的 `render-brief-dialog` 在 HTML 完全不存在：

```
git show bella-test1:backend/server/static/scene.html | findstr "render-brief"
```
預期輸出：**空**（0 行）。

而 JS 端開啟函式第一行就因元素為 null 而 return：

```
git show bella-test1:backend/server/static/scene_v2.js | findstr /c:"if (!element.renderBriefDialog) return"
```
預期輸出：`  if (!element.renderBriefDialog) return;`

連鎖後果（順著程式碼即可確認）：兩顆送出按鈕點擊後無任何反應與錯誤；
`renderRequestPayload()`（含問卷 digest、家具、色卡的完整 payload 組裝）
不可達；`POST /api/projects/{id}/render-jobs` 前端零呼叫點；
`workflow.complete("ai_render")` 只存在於這條死路徑內。

### E3．即使修好 E2，後端也沒有 prompt——生圖被外包給不存在的服務

```
git show bella-test1:backend/server/render_service.py | findstr /i "prompt"
```
預期輸出：**空**（整檔 0 處 prompt 組裝）。

```
git show bella-test1:backend/server/render_service.py | findstr "PROVIDER_URL"
```
預期輸出：兩行 `ROOMPILOT_RENDER_PROVIDER_URL`——未設定此環境變數即回 503，
而 repo 內沒有任何 provider 實作。

### E4．RAG 只做「重排」，不做檢索——兩句原文註解自己承認

```
git show bella-test1:backend/server/static/scene_v2.js | findstr /c:"RAG changes ranking"
git show bella-test1:backend/server/static/scene_v2.js | findstr /c:"enhancement to ranking"
```
預期輸出（原文）：
`// This is intentionally non-blocking: RAG changes ranking, never room completion.`
`// RAG is an enhancement to ranking; questionnaire completion never blocks on it.`

家具實際來源是 `GET /api/furniture` 型錄過濾＋前端關鍵詞加權；RAG 命中結果
只拿 `item_id` 對既有推薦清單做穩定重排，不新增任何一件家具、不進生圖。

### E5．RAG 預設停用；query 的生圖語意欄位因 UI 死鏈恆空

```
git show bella-test1:backend/spatial_data/rag/settings.py | findstr "ROOMPILOT_RAG_ENABLED"
```
預期輸出含：`"ROOMPILOT_RAG_ENABLED", "false"`（預設關閉，未配置即 503 全走
fallback）。

組 RAG query 的「生圖設備方向／不需要設備／生圖補充」欄位，其唯一輸入 UI
（六個 `questionnaire-generative-*` id）在 HTML 不存在：

```
git show bella-test1:backend/server/static/scene.html | findstr "questionnaire-generative questionnaire-generation"
```
預期輸出：**空**。JS 端 `renderGenerativeEquipment()` 因取不到元素而永遠
提前 return——資料模型設計完整，但沒有一題填得到。

---

## 2. ben-local 側證據（B1–B3）

### B1．問卷送出即做真檢索：結構化過濾 → pgvector 語意排序

```
git show HEAD:backend/spatial_data/rag/shortlist.py | findstr /n "pgvector 語意排序 正規化欄位"
```
模組 docstring 原文：「把需求問卷轉成語意查詢，先用正規化欄位做結構化過濾
（房型、尺寸、風格、價格），再用 pgvector 對過濾後的子集做語意排序，逐房
逐類取 top-N」。輸入組裝在 `backend/server/shortlist_api.py`
`build_needs_from_workflow()`：第 4 步房間幾何＋第 5 步問卷（用途、特殊需求、
家具偏好文字、標籤）。附需求指紋快取與 `semantic=false` 降級標記。

### B2．第 8 步送出按鈕直綁，不經任何 dialog

```
git grep -n "request-palette-renders" HEAD -- frontend/
```
預期輸出含 `frontend/scene_v2.js` 的
`$("#request-palette-renders").addEventListener("click", requestPaletteRenders);`
與 `frontend/scene.html` 的按鈕本體。payload（`renderRequestPayload`）帶
`requirements: { basic, visual_preferences, finishes, room_requirements,
ready_for_rag, digest }` 全量問卷。

### B3．後端有 prompt 組裝器，逐行消費問卷 digest

```
git grep -n "build_render_prompt\|requirements.digest\|不可變更的條件" HEAD -- backend/server/render_providers.py
```
`build_render_prompt()` 把全屋與逐房的牆/地/天花/燈光/空調寫進 prompt，
自由文字「特殊或不可變條件」原文成為一行「不可變更的條件：…」；家具身分
刻意只取 `scene_json`（防止問卷敘述與實際擺放矛盾造成失真）。

---

## 3. 提議的整合邊界條文（供整合規格增補）

1. **第 5 步的 UI 與題目資料模型**：依原裁定採 `bella-test1`，**並補齊其缺失的
   DOM**（全屋四題解除 hidden、生圖設備六題補 UI）——這是把對方設計完整但
   死掉的部分救活，不是丟棄。
2. **問卷之後的資料鏈四件套保留 `ben-local`，不得替換**：
   - `backend/server/shortlist_api.py` ＋ `backend/spatial_data/rag/shortlist.py`
     （問卷 → pgvector 檢索）
   - `requirements.digest`（`renderRequirementsDigest()`）
   - 第 8 步送出路徑（`requestPaletteRenders` / `submitRoomRenders` 直綁按鈕）
   - `backend/server/render_providers.py` 的 prompt 組裝
3. **驗收判準**：整合完成後，從新專案跑完八步，必須能 (a) 問卷送出後取得
   逐房 shortlist（`workflow.furniture_shortlist` 非空且 `semantic=true`）、
   (b) 第 8 步實際送出 render job 並拿到圖。bella-test1 現狀做不到 (b)，
   這是可當場演示的。

---

## 附註

- 本文件的行號與內容以 `bella-test1` @ `c043ca7a`、`ben-local` @ `09891216`
  為準；指令本身不依賴行號，分支前進後仍可複驗。
- 「視覺 55 題（極與極）」兩邊皆已下架，非本文件爭點。
- bella-test1 值得搬的清單（公平起見一併列出）：逐房生圖設備六題資料模型、
  `buildRoomRequirementsPayload` 的 `planGeometry` 欄位設計、逐房五段式導覽的
  UI 意圖（DOM 需重建）。
