# RoomPilot 第 5、6 步整合規格（提供 Ben／AI 實作）

## 目的

本文件定義需求問卷、RAG 家具搜尋、2D／3D 配置與最終生圖之間唯一可依循的資料契約。所有欄位名稱維持機器可讀的英文，所有介面與說明使用繁體中文。

核心原則：

1. 第 4 步確認的牆、門、窗、樑、柱是不可變結構。第 5、6、7、8 步不得移動、刪除或以生圖掩蓋它們。
2. 方案 A／B 只代表家具選擇、尺寸、位置與方向不同；不得代表不同牆體或不同房間格局。
3. 每間房確認後立即送出 RAG 工作，但使用者不會因為缺 GLB、找不到候選或 RAG 失敗而卡在第 5 步。
4. 第 6 步才顯示「不合法、尺寸不合、缺 GLB」的原因、替代家具與可採取的動作。
5. 廚房、浴室、陽台的大型設備可在最終生圖產生；第 6 步不應假裝已有可拖拉的 GLB 設備。

## 第 5 步：逐房需求問卷

### 每間房必收集的資料

```json
{
  "room_id": "room-uuid",
  "room_type": "Bedroom",
  "room_label": "主臥",
  "room_polygon_cm": [{"x": 0, "y": 0}],
  "room_size_cm": {"width": 360, "depth": 420},
  "room_uses": ["sleep", "reading_work"],
  "selected_furniture": [
    {
      "furniture_id": "catalog-id",
      "category": "bed",
      "label_zh": "標準雙人床",
      "quantity": 1,
      "size_cm": {"width": 150, "depth": 188, "height": 95},
      "source": "user_selected"
    }
  ],
  "furniture_description": "淺木色、圓角、靠窗閱讀椅，保留採光與走道",
  "furniture_tags": ["淺木色", "圓角", "可收納"],
  "special_requirements": "不遮擋落地窗",
  "generation_requirements": [],
  "questionnaire_version": 3
}
```

### 用途與家具的互動規則

1. 先顯示本房用途大類，再展開細項家具；例如臥室為「睡眠、收納、更衣、閱讀工作、梳妝」。
2. 每個房型都必須能「新增家具」，可先瀏覽目前房間分類，也可切換「全部空間」再搜尋。搜尋「椅子」必須涵蓋工作椅、閱讀椅、梳妝椅與椅凳，不可只回傳單一扶手椅。
3. 使用者自由輸入的家具外觀、材質與空間描述，要同時作為 RAG 搜尋條件與最終生圖文字，不得只顯示於前端。
4. 問卷可帶入依全屋風格與色卡產生的推薦，但使用者可逐房覆寫。走道預設繼承客廳風格；改動時必須提示使用者。
5. 廚房必問爐灶、冰箱、洗滌區的位置與型式；可用平面圖框選或文字補充。浴室、陽台同樣要問功能、設備形式、必要淨空與生圖偏好。

### 廚房、浴室、陽台的特殊說明

這三種房間的設備通常沒有可配置 GLB，仍必須完成問卷。介面須清楚說明：設備形式、位置、材質與補充描述會交給最終生圖；第 6 步只呈現已有 GLB 的小型物件與空間限制。不得因為沒有設備模型而省略問題或阻擋送出。

### 結構風險提示

若使用者補充文字含有「拆牆、移門、加大空間、延伸陽台、移窗、打通」等意圖，送出前顯示確認提示：這些描述不會改變已確認結構，後續生圖仍依目前房間尺寸、門窗與走道淨空執行。使用者可返回修改文字或確認保留為風格參考。

## RAG 工作契約

### 請求

每次房間確認時，依 `room_id + questionnaire_version + 問卷內容雜湊` 建立或更新工作。內容變更後不得沿用舊的 completed 結果。

```json
{
  "room_id": "room-uuid",
  "room_type": "Bedroom",
  "room_uses": ["sleep", "reading_work"],
  "selected_furniture_ids": ["catalog-id"],
  "furniture_description": "淺木色、圓角、靠窗閱讀椅",
  "furniture_tags": ["淺木色", "圓角"],
  "style_id": "japanese",
  "materials": {"wall": "warm_white", "floor": "light_oak"},
  "room_constraints": {"width_cm": 360, "depth_cm": 420}
}
```

### 回應與狀態

RAG 回傳的每個 hit 只可用 `furniture_id` 當識別。前端或後端必須以精確 ID 回查型錄取得完整資料、GLB URL、尺寸與類別；不得以名稱搜尋第一筆替代。

可接受終態為 `completed`、`failed`、`cancelled`、`expired`、`unavailable`。所有非等待狀態都要結束輪詢並保存原因；不得讓頁面永遠顯示處理中。RAG 無結果時須撤回上一輪自動套用的 RAG 家具，保留使用者手選的家具。

### 第 6 步前的可行性資料

RAG 命中家具初始為 `room_fit_checked: false`。必須先以房間尺寸、門窗淨空、走道與實際 GLB 尺寸檢查，再標示為可配置。任何不合格家具不可被自動選入，但使用者可以在第 6 步看到原因與替代選擇。

## 第 6 步：2D／3D 配置與家具鎖定

### 進入順序

1. 先顯示每個房間的方案 A／B 比較。每張方案卡必須有本房 2D 家具配置與可旋轉的 3D 室內預覽。
2. 方案 A／B 都必須維持第 4 步的同一牆、門、窗、樑、柱與房間邊界。若方案 B 無可比較內容，明確顯示原因，並預設選用 A。
3. 使用者完成每房方案選擇後，才進入配置編輯工作區。
4. 工作區提供「同步平面／待處理／選取家具」三個主分頁；選取家具頁可以搜尋、替換、調整位置、旋轉與鎖定家具。

### 家具替換與鎖定

替換對話框只顯示家具中文名稱與尺寸，例如「雙人衣櫃，98 × 61 cm」。不得顯示原始型錄長名稱、英文材質碼或無關欄位。若使用者選擇「更小款」，系統必須先取得可替換候選；沒有候選時不應提供該選項，或須直接解釋沒有符合尺寸的 GLB。

鎖定分兩類：

```json
{
  "position_locked": true,
  "appearance_locked": false
}
```

位置鎖定表示後續配置不移動該家具；外觀鎖定表示後續不替換模型、顏色與材質。鎖定不得阻擋使用者在明確解除後再修改。

### 3D 預覽資料要求

方案預覽的 `scene_objects` 必須包含：

```json
{
  "furniture_id": "layout-item-id",
  "catalog_furniture_id": "catalog-id",
  "name_zh_raw": "雙人床",
  "model_url": "https://.../model.glb",
  "size_cm": {"width": 150, "depth": 188, "height": 95},
  "position_cm": {"x": 120, "z": 180},
  "rotation_y_deg": 90,
  "placement_room_id": "room-uuid"
}
```

房間 3D 預覽必須從室內視角開始，可旋轉、縮放；平面縮圖上的家具編號僅用於第 6 步選取，不得進入第 7 步的最終視角。若畫面為單房比較，必須同時裁切並平移本房的結構幾何、房間區域與家具座標；陣列座標 `[x, y]` 與物件座標 `{x, y}` 都要正確處理。

## 提供給最終生圖 Agent 的交付檔

第 6 步確認後，輸出每房一份資料並彙整成專案檔。檔名建議：`project_<project_id>_agent_render_input.json`。

```json
{
  "project_id": "project-uuid",
  "immutable_structure": {
    "walls": [],
    "doors": [],
    "windows": [],
    "beams": [],
    "columns": []
  },
  "rooms": [
    {
      "room_id": "room-uuid",
      "room_label": "主臥",
      "room_type": "Bedroom",
      "space_constraints": {
        "polygon_cm": [],
        "clearance_requirements": ["保留門片開啟範圍", "保留採光"]
      },
      "uses": ["sleep", "reading_work"],
      "selected_scheme": "A",
      "selected_furniture": [],
      "rag_candidates": [],
      "style": {"style_id": "japanese", "palette": []},
      "materials": {"wall": "warm_white", "floor": "light_oak"},
      "ceiling_lighting": {},
      "user_description": "淺木色、圓角、靠窗閱讀椅",
      "generation_requirements": []
    }
  ]
}
```

Agent 必須遵守 `immutable_structure` 與 `space_constraints`；不能因為文字出現「打通、延伸、加大」而擴張房間。廚房、浴室、陽台的設備描述放在 `generation_requirements`，由生圖生成，但仍受房間邊界限制。

## 驗收清單

1. 改變一間房的文字、標籤、用途或家具後，RAG 必重新執行且舊 RAG 預設不會殘留。
2. RAG 精確命中的家具可回查完整型錄資料，通過可行性檢查後進入第 6 步。
3. RAG 失敗、取消或沒有 GLB 時，使用者仍能離開第 5 步；第 6 步顯示可理解的原因與替代。
4. 每間房的方案比較都有正確的 2D 與 3D，3D 內看得到該方案的家具且可旋轉。
5. 方案 A／B 的牆、門、窗、樑、柱完全相同；差異只在家具。
6. 第 7 步最終視角沒有家具編號；第 6 步仍可用編號選取家具。
7. 所有面向使用者的文案、家具名稱、顏色、材質與狀態均為繁體中文。
