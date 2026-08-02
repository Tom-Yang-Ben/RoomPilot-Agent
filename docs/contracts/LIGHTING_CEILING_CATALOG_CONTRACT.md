# 燈具、天花板與冷氣資料契約

**狀態：草案，需由 Kai、Django、Bella、Ancai 共同遵守。**

## 目的

讓問卷、第 6 步 2D+3D 配置與第 8 步渲染使用同一份資料語意：家具燈具、天花板結構、表面材質與冷氣定位各有明確所有者，避免把模型、材質、結構與問卷偏好混在一起。

## 所有權

| 資料 | 正式 owner | 消費者 |
|---|---|---|
| 家具／燈具 GLB、PNG、尺寸、授權、模型 URL | Kai | Bella、Yen、Ancai |
| 房間 polygon、房高、樑柱、門窗與淨空區 | Django + Cody | Bella、Ancai |
| 方案中的天花板、牆地材質、燈具實例、HVAC 定位 | Bella | Ancai、Yen |
| 碰撞、朝向、動線與合法性決策 | Ancai | Bella、Yen |

## 格局與空間資料持久化

- `layout_json` 是唯一的原始格局資料，保留辨識輸出與第 4 步人工校正結果。
- 每次確認均建立 `layout_versions` 版本；不可覆寫舊版本。
- Django 將空間關係衍生寫入 `spatial_rooms`、`spatial_openings`、`spatial_clearance_zones`、`layout_evaluations` 等 versioned tables。
- 第 6 步、RAG 與後續 Graph RAG 都查詢同一份衍生關係；Graph RAG 不得另建另一套格局資料來源。
- 如衍生資料與 `layout_json` 不一致，以對應 `layout_version` 的原始 `layout_json` 為準並重新生成衍生資料。
- 第 4 步產生新版本時，舊版第 6 步的 `scene_json` 與家具配置必須保留為可回復方案。新版只重新驗證家具，不可無提示地刪除使用者既有配置。

## 資料結構

### 1. Kai catalog：燈具模型

```json
{
  "item_id": "stable-id",
  "asset_kind": "lighting_fixture",
  "lighting_type": "pendant|track|downlight|wall|table|floor",
  "glb_url": "https://...",
  "thumbnail_url": "https://...",
  "dimensions_cm": {"width": 0, "depth": 0, "height": 0},
  "style_tags": ["modern_minimal"],
  "license": "CC0|catalog-origin",
  "verification_status": "verified"
}
```

`verification_status != verified` 的資料不能被 RAG 或第 6 步自動配置。

### 2. `scene_json.surface_overrides`：每房天花板

```json
{
  "room_id": "room-1",
  "ceiling_style_id": "flat|cove|floating|linear|wood-grid|no-main-light|exposed",
  "ceiling_material_id": "surface-id",
  "ceiling_color_hex": "#f4f1eb",
  "lighting_ids": ["catalog-lighting-item-id"],
  "hvac": {
    "system": "wall-split|ceiling-cassette|ducted|none",
    "placement": "wall|ceiling_void|linear_supply",
    "status": "placeholder|catalog_model"
  }
}
```

### 3. Django 空間限制

```json
{
  "room_id": "room-1",
  "room_height_cm": 270,
  "ceiling_usable_polygon_cm": [],
  "beam_obstacles": [],
  "opening_clearance_zones": [],
  "window_clearance_zones": []
}
```

## 實作規則

- 問卷先建立全屋天花板、照明與冷氣預設；使用者只在需要時對個別房間建立 override。一般房間應沿用全屋預設，以維持整體一致性。
- 問卷選燈與選天花板時，立即顯示固定的參考圖，並搭配目前色卡與材質小樣；不需要先生成整個個人化 3D 場景。
- 真正套用房間尺寸、家具、牆地材質與燈具模型的效果，統一在第 6 步 3D 呈現。
- 系統依房間用途先自動配置燈具，並避開樑柱、門窗與家具；第 6 步可拖拉、旋轉或更換單一燈具，修改後必須重新驗證衝突。
- 第 6 步自由旋轉／正俯視預設隱藏天花板，但燈具必須顯示；室內透視與走動預設顯示天花板、燈具與冷氣定位，並提供隱藏天花板控制。
- 天花板材質來自 `surface_catalog`；家具燈具來自 Kai catalog；不得用家具 PNG 冒充表面 PBR 材質。
- 冷氣在尚無正式模型前，只能以正確尺寸與位置的 placeholder／洞口表示，不能假裝是可配置家具。
- 外部新增燈具只接受 CC0 或有明確商業授權、來源 URL、checksum 與授權紀錄的檔案。
- 大型 GLB、原始下載與批次預覽不提交 Git；提交 manifest、資料 migration、程式與小型測試 fixture。已清洗、網站執行期需要的 PBR 紋理例外，必須提交至 `frontend/pbr_assets/`。

## UIUX 驗收原則

- 問卷每個天花板、燈具與冷氣選項都要有固定參考圖、短名稱與必要的安裝／空間提醒；使用者不需閱讀技術術語才能選擇。
- 先顯示全屋預設與推薦理由，再提供「此房間調整」；個別 override 必須清楚標示，不可讓使用者誤以為改了全屋。
- 第 6 步預設使用自由旋轉視角；視角、走動、編輯家具、天花板顯示與磁吸屬於分組控制，不堆成一排文字按鈕。
- 編輯燈具時，保留目前房間與攝影機視角；右側顯示同房家具與衝突原因，避免跳離上下文。
- 每個已配置家具、燈具與冷氣定位都需有方案內穩定編號；2D、3D、右側清單與待處理原因使用同一編號。一般瀏覽也顯示編號；拖拉、旋轉、替換或鎖定後編號不得改變，刪除後才釋放。
- 為避免地面家具與天花燈具標示重疊，編輯模式提供「全部／家具／燈具與冷氣」的顯示篩選。選定類別後只高亮該類，其他類別淡化但不改變編號。
- 拖拉或旋轉後，以即時輔助線、磁吸提示與紅色衝突區說明結果；不能只顯示「無法放置」。
- 走動模式不能選取家具；門片隱藏以利穿梭，天花板可切換顯示，但燈具與冷氣定位需維持可見。

## 清洗與資料庫變更流程

1. Kai 將候選 GLB 寫入 staging，不寫正式表。
2. 驗證載入、尺寸、縮圖、類型與授權。
3. 失敗或不確定者移入 quarantine，保留 reason code。
4. 通過者 UPSERT 到正式 catalog，並建立三視角／縮圖 manifest。
5. Bella 以 API 讀取 verified item；Yen RAG 只檢索 verified item；Ancai 只擺放可合法配置的 verified item。

### 資產儲存、交付與使用

- 外部 CC0 燈具 GLB 與其純物件 PNG 上傳到 Kai 既有 S3 bucket，並透過 CloudFront URL 交付；大型 GLB 不提交 Git。
- `backend/catalog/data/manifests/lighting_assets_manifest.csv` 是 Git 內的可審核交付清單，至少包含 `item_id`、`glb_url`、`thumbnail_url`、`checksum`、`license`、`lighting_type`、`verification_status`。
- PostgreSQL catalog 儲存可查詢欄位與 URL；只公開 `verified` 資產給 API。

> **實作現況（2026-08-02，待 Kai／Django／Bella／Ancai 確認）**
>
> 燈具落在獨立的 `roompilot.lighting_assets` 表與 `lighting_assets_current` view，
> 而不是本文件原先寫的 `roompilot.furniture_catalog_current`。分表的理由是燈具透過
> `surface_overrides.lighting_ids` 引用、不參與第 6 步家具自動選件與碰撞計算；併入
> 家具表的話，任何一條沒加 `kind` 條件的家具查詢都會讓燈具漏進配置。
>
> `checksum` 目前填 S3 ETag（欄位 `checksum_algo=s3-etag`），因為交付 manifest 的
> `sha256` 欄整批是空的。若要改成真 SHA-256，需重新讀取 CloudFront 上的 GLB 計算。
- Bella 前端以 API 回傳的 `thumbnail_url` 顯示純物件圖片，以 `glb_url` 載入模型；不可從前端直接猜測或組合 S3 路徑。
- PBR 紋理是網站執行期資產，放在 `frontend/pbr_assets/` 並提交 Git；它們不取代 GLB，也不進燈具 manifest。
- 原始下載、Blender 暫存、批次預覽與失敗模型留在 staging/quarantine，不提交 Git、不由前端使用。

詳細新增作業請依角色閱讀：

- Kai：`docs/owners/KAI.md` 的「新增資料到資料庫：Kai 作業手冊」。
- Django：`docs/owners/DJANGO.md` 的「新增空間資料到資料庫：Django 作業手冊」。

## 必要測試

- Kai：catalog SQL、manifest、縮圖、quarantine 測試。
- Django/Cody：房間高度、樑柱、窗門淨空輸出測試。
- Bella：問卷 preview、Step 6 天花板顯示切換、燈具 catalog 圖片與 API 相容測試。
- Ancai：燈具／HVAC 不與樑、門窗、家具或可用高度衝突的規則測試。
