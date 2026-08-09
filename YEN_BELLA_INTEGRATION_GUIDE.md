# Yen 整合 Bella 第 4 至第 8 步指南

這份文件是提供 AI 執行整合的操作規格。目標是把 Bella 的最新第 4 至第 8 步功能正確移植到 Yen 分支，保留 Yen 的第 1 至第 3 步能力；不是把畫面或單一 JavaScript 檔複製過去。

## 0. 不可違反的規則

1. `bella-new` 是第 4 至第 8 步的功能基準。開始前先抓取最新遠端，並記錄實際比較的 commit；不可用 Yen 既有版本覆蓋 Bella 較新的行為。
2. Yen 目前 `/scene` 由 `backend/server/main.py` 回傳 `backend/server/static/scene.html`，並掛載 `backend/server/static/` 為 `/static`。這是本輪唯一的八步流程執行入口。
3. `frontend/scene.html`、`frontend/scene_v2.js`、`frontend/src/` 與 `backend/server/static/frontend3d/` 可能是平行或實驗實作。第一輪不可把功能搬到這些位置，也不可刪除；先停止把它們當成 `/scene` 的來源。
4. 不可只 cherry-pick 「第 5 至第 8 步前端排版」的提交。每項行為都要連同狀態、儲存資料、API payload、後端端點與測試一起搬入。
5. 未完成第 1 至第 8 步端對端驗收前，不可刪除、覆蓋或大幅重寫任何重複前端。重複程式碼是暫時的比對來源，不是立即清理目標。
6. 不可修改第 1 至第 3 步既有能力，除非為了維持資料契約而新增向後相容的轉換。

## 1. 整合前準備

在 Yen 的新整合分支執行，分支名稱建議為 `yen/bella-step4-8-integration`。

1. `git fetch origin bella-new yen`
2. 記錄 `origin/bella-new`、`origin/yen` 與共同祖先 commit。
3. 確認 `GET /scene` 實際回傳 `backend/server/static/scene.html`。
4. 以 `backend/server/static/scene_v2.js` 作為唯一前端修改位置，並同步它所 import 的同目錄模組、`scene.html`、`site.css`、必要後端檔案與測試。
5. 每次修改 JavaScript 或 CSS 後，更新 `scene.html` 內對應的 SHA-256 cache key，避免瀏覽器載入舊檔。

## 2. 唯一資料鏈

整合後必須只有這一條資料鏈，所有房間都以穩定的 `room.id` 對應，不得用下拉選單索引、中文名稱或陣列位置代替。

```text
第 4 步已確認房間與結構
  -> confirmedFloorplan + confirmedStructureSnapshot
  -> 第 5 步 roomRequirementModel.roomRequirements[room.id]
  -> 第 6 步 roomFinishDrafts[room.id] + surfaceCatalog + scene objects
  -> 第 7 步 proposalReview.roomViews[room.id]
  -> 第 8 步 render request + render jobs + design delivery
```

### 必須保留的狀態

| 狀態 | 用途 | 不能遺漏的原因 |
|---|---|---|
| `confirmedFloorplan` | 第 4 步完成後的房間、牆面輪廓、尺寸與比例 | 後續 2D/3D、家具落點與相機必須基於同一張確認圖 |
| `confirmedStructureSnapshot` | 已確認的牆、門、窗、樑、柱快照 | 不能被重新辨識、切換頁面或材質更新覆蓋 |
| `roomRequirementModel` | 第 5 步全屋與逐房需求 | RAG、家具選擇、材質建議與生圖提示詞都要讀它 |
| `roomFinishDrafts[room.id]` | 第 6 步逐房家具、牆地材質、天花與照明草稿及確認狀態 | 切換房間時保留草稿，確認後才鎖定 |
| `surfaceCatalog` | 真實材質目錄與預覽圖 | 材質 id、圖片、顏色與 3D 貼圖必須取同一筆資料 |
| `proposalReview.roomViews[room.id]` | 第 7 步逐房相機與鎖定狀態 | 第 8 步每房只能使用已鎖定的該房視角 |
| render jobs 與 design delivery | 第 8 步生圖、確認、報告與預算輸出 | 每房生圖結果與最終報告不可混用不同房間的資料 |

## 3. 分階段移植順序

每一階段都要先跑測試、手動建立至少三個房間，再進下一階段。不要一次搬完。

### A. 先建立第 4 步出口

從 Bella 搬入並驗證：

- 房間名稱、`room.id`、`type` 的標準化與下拉選單對應。
- 牆、門、窗、樑、柱的編輯、確認、尺寸與房間歸屬。
- `confirmedStructureSnapshot` 的建立、保存、還原與失效規則。
- 第 4 步未確認時，後面步驟不得把暫存結構當成已鎖定資料。

驗收：切換或重新整理後，陽台、臥室、浴室等每個房間仍指向正確區域；更改一房牆材質或結構不影響其他房間。

### B. 接第 5 步需求模型

從 Bella 搬入並驗證：

- 全屋問卷與逐房問卷寫入同一個 `roomRequirementModel`。
- 每個 `room.id` 都有自己的用途、使用者需求、家具需求、材質偏好與延後處理項目。
- 問卷完成後由既有 RAG/Agent 讀取此模型，不可重新依中文房名猜房間。
- 重新修改第 5 步時，必須使受影響的第 6 至第 8 步草稿或確認狀態失效，而不是留下舊資料。

驗收：至少三房有不同用途時，問卷結果不互相覆蓋，送出的 Agent payload 含正確 room id。

### C. 接第 6 步逐房配置與材質

從 Bella 搬入並驗證：

- `roomFinishDrafts[room.id]` 的草稿、切換、確認與保存。
- 家具的 `placement_room_id`、家具編號、2D/3D 同步、移動、旋轉與貼牆規則。
- 材質卡與 3D 牆地貼圖使用同一個材質 id；選取時更新草稿預覽，按「確認此房間材質」才鎖定。
- 材質目錄讀取 `surfaceCatalog`，不得用錯誤的色碼覆蓋圖片實際顏色；缺少圖片資訊時顯示待確認，不得虛構。
- 移動視角不重新產生 3D 場景；切換房間保留草稿；同一房只執行一次必要的預覽生成。

驗收：每房的牆地材質獨立、家具在正確房間、2D 與 3D 編號一致、刷新後確認狀態仍存在。

### D. 接第 7 步逐房視角鎖定

從 Bella 搬入並驗證：

- 視角候選、相機位置與 `proposalReview.roomViews[room.id]` 的保存。
- 點選房間必須顯示該房全貌，而非沿用前一房或固定主視角。
- 每一房都要完成鎖定才能進第 8 步。
- 視角鎖定後不得因第 6 步無關操作重新生成或覆蓋。

驗收：逐一點選所有房間，畫面、房名、room id、鎖定相機完全一致；少一房未鎖定時，第 8 步入口必須被阻擋且說明原因。

### E. 接第 8 步生圖、確認與成果包

從 Bella 搬入並驗證：

- 呼叫 `POST /api/projects/{project_id}/render-jobs` 時，payload 必須包含已確認的結構、逐房需求、逐房材質草稿、家具、該房視角與 room id。
- 每房可在初圖後提出一次修改；修改不可改寫房間尺寸、門窗、固定家具位置與第 7 步鎖定視角。
- 生成完成後，逐房確認，最後呼叫 `POST /api/projects/{project_id}/design-delivery`。
- 成果包需對應每個房間的設計敘述、設計師參照、工程內容與裝潢／家具明細；不可把代表房資料套到所有房間。

驗收：三房案例可完成送圖、每房僅一次修改、每張成果與報告內容對應相同 room id。

## 4. 對接 API 前的檢查表

每一個從前端送出的 payload 都必須檢查：

- 有 `project_id` 與穩定 `room_id`。
- 不以顯示名稱、中文名稱、房間排序或下拉 index 對應房間。
- 房間的結構、需求、材質、家具與視角都來自同一個 room id。
- API 回傳錯誤需完整顯示 stderr/stdout 或 HTTP detail 後再修正，不可只顯示 `Failed to fetch`。
- API 成功後才推進 workflow；運算中顯示等待狀態，不能先跳到未完成步驟或跳回前一步。

## 5. 禁止的整合方式

- 禁止只複製 HTML、CSS 或按鈕事件。
- 禁止同時維護兩份 `scene_v2.js` 的同一功能。
- 禁止將第 5 至第 8 步搬到未被 `/scene` 路由服務的 `frontend/` 副本。
- 禁止把原始 `color_hex` 當作唯一材質真實顏色。
- 禁止讓第 6 步以房名、index 或最近選取房間推斷家具／材質所屬。
- 禁止第 7 步以全屋主視角替代逐房鎖定視角。
- 禁止在未建立端對端測試前刪除任何重複前端或 3D 實作。

## 6. 必做測試

保留既有測試，並新增一條真正的跨步測試，例如 `tests/test_scene_step4_to_8_integration.py`：

1. 建立至少三房且 room id 不連續的平面圖。
2. 第 4 步確認房間與結構並重新載入。
3. 第 5 步填入不同逐房需求。
4. 第 6 步各房選擇不同家具與牆地材質，確認草稿與鎖定行為。
5. 第 7 步鎖定三個不同房間的視角。
6. 第 8 步送出 render jobs，驗證每一筆 payload 的 room id、家具、材質與視角相同。
7. 模擬一房一次修改、全房確認、產生 design delivery。

至少執行：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_scene_6_8_wizard_contract.py tests/test_scene_room_requirements.py tests/test_scene_surface_materials.py tests/test_scene_step4_to_8_integration.py -q
node --check backend/server/static/scene_v2.js
git diff --check
```

## 7. 最後才可剃除的項目

只有上述測試、手動三房流程與 `/scene` 實際服務驗收全部通過後，才可建立第二個清理 PR：

1. 列出 `frontend/`、`frontend/src/`、`backend/server/static/frontend3d/` 各自是否仍有獨立路由或用途。
2. 不再被路由、測試、import 或部署使用的副本，先移入 `deprecated/` 或在 PR 中明確刪除。
3. 每刪一個入口，重新檢查 `/scene`、第 4 至第 8 步、成果包與 3D 預覽。
4. 清理 PR 不可同時引入新功能。

## 8. AI 完成回報格式

每完成一階段，回報以下內容，不可只說「已整合」：

- 修改的實際執行檔案與原因。
- 從 Bella 搬入的資料欄位、API 與行為。
- 未搬入的部分及其原因。
- 執行的測試、結果與完整錯誤訊息。
- 手動驗證的房間、room id、材質、家具與視角對應結果。
- 是否已到可清理重複檔案的條件。預設答案必須是「否」，直到第 6 節全部通過。
