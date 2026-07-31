# 房型策略表（正式規格）

> **狀態**：**v1 定版（2026-07-31，Ancai 確認）**——下表 12 個房型**寫死不再變動**  
> **人讀 SSOT**：本檔  
> **機器執行 SSOT**：[`backend/agent/knowledge.py`](../../agent/knowledge.py)（`ROOM_MINIMUM_FAMILIES` 等）  
> **几何合法性**：[`../README.md`](../README.md)（Engine）  
> **尚未全接**：`scene_service.SPACE_DEFAULTS`／前端問卷模板仍可能是舊清單

## 目錄

1. [一句話](#一句話)
2. [誰負責什麼](#誰負責什麼)
3. [通用砍件規則](#通用砍件規則g1g5)
4. [第 4 步全空間最少預設](#第-4-步全空間最少預設)
5. [客廳／臥室／餐廳細節](#客廳臥室餐廳細節)
6. [與程式對齊狀態](#與程式對齊狀態)
7. [刻意不做](#刻意不做)
8. [接線檢查清單](#接線檢查清單)

---

## 一句話

先定「這間房要放什麼」，再讓 RAG／Agent 選型號，最後才叫 Engine 找合法座標。

---

## 誰負責什麼

| 誰 | 做什麼 | 不做什麼 |
|---|---|---|
| **本表** | 必備／可選、順序、關係意圖、砍件 | 不算 x／y |
| **Agent（`knowledge.py`）** | 把本表變成可執行規則與 prompt | 不定几何 |
| **RAG** | 依槽位檢索候選白名單 | 不定合法性 |
| **Engine** | 座標、碰撞、淨空 | 不定房型清單 |
| **Bella** | 問卷／八步 UI／呈現失敗 | 不重做引擎规则 |

---

## 通用砍件規則（G1–G5）

| 代號 | 決定 | 用意 | 可能缺點 |
|---|---|---|---|
| G1 | 放不下先換小款，再砍可選 | 保住核心體驗 | 換小可能掉風格 |
| G2 | 由清單尾端往前砍 | 可預期 | 順序寫錯就整桌錯 |
| G3 | 必備仍失敗 → 誠實失敗；剩餘可當生圖素材 | 不硬塞 | 畫面可能空 |
| G4 | 軟裝不進自動配置 | 硬家具先合法 | 預覽較光禿 |
| G5 | 家電永不進 2D／3D 自動配置 | 產品邊界 | 廚浴真實感靠生圖 |

---

## 第 4 步全空間最少預設

對應「4 空間與結構」會標的空間。類型鍵＝家具庫 `normalized_type`（＝ catalog `category_code`）。
**這 12 個房型即全集，不再新增。**

| # | 空間 | 正規碼 | 最少自動配置 | 可選 | 不自動配置 | 為何 |
|---|---|---|---|---|---|---|
| 1 | 玄關 | `entry`（`entryway`→此） | `shoe-cabinet` **優先**；不足退 `storage-furniture`／`cabinet-cupboard` | `stool-bench`、`clothes-rack`、`mirror` | 家電、門墊軟裝 | 台灣玄關核心是鞋，但全庫僅 5 件鞋櫃，必須留備援 |
| 2 | 客廳 | `living_room` | `sofa`、`tv-bench`（同槽可 `tv-media-furniture`） | `coffee-table`、`armchair`、`bookcase` | 獨立電視、家電、地毯 | 能坐＋電視牆；茶几可選以提高小房成功率 |
| 3 | 餐廳 | `dining_room` | `dining-table`、`dining-chair`×N | `sideboard`、`display-cabinet` | 軟裝 | 先能吃飯 |
| 4 | 廚房 | `kitchen` | **空白** | 無 | **全部家電** | 庫內無可自動擺的廚房主家具（僅壁架 53／吧台桌 17） |
| 5 | 主臥 | `bedroom` | `bed`、`wardrobe`／`pax-wardrobe`、`bedside-table`**×2** | `chests-of-drawer`、`bookcase` | 軟裝、家電 | 雙人床兩側對稱各一床頭櫃 |
| 6 | 次臥 | `bedroom` | `bed`、`wardrobe`、`bedside-table`**×1** | `desk`＋`office-chair`（成組）、`chests-of-drawer`、`bookcase` | 軟裝、家電 | 給 2 個床頭櫃會先擠爆小房；書桌組是台灣次臥最常見第二用途 |
| 7 | 浴室 | `bathroom` | **空白** | `mirror-cabinet`（慎用） | 固定設備／家電 | 庫內只有鏡 61／鏡櫃 17 |
| 8 | 書房／工作區 | `workspace`（`study`→此） | `desk`、`office-chair`（companion 成組） | `bookcase`、`shelving-unit`、`wall-shelf` | 家電 | 一桌一椅 |
| 9 | 陽台 | `balcony`（`outdoor`→此） | **空白** | 無 | **洗衣機**等 | 庫內 `outdoor` 236 件＝植栽 235＋戶外地毯 1，**戶外桌椅一件都沒有** |
| 10 | 儲藏室 | `storage` | `shelving-unit` 或 `storage-furniture`（同族） | `storage-solution-system`、`cabinet-cupboard` | 家電 | 功能即收納 |
| 11 | 走道／動線 | `hallway`（`circulation`→此） | **空白** | 無 | 軟裝 | 留空才是功能 |
| 12 | 多功能室 | `multifunction` | **依問卷用途路由到既有骨架**（見下） | 隨骨架 | 家電 | 本質是「還沒決定用途的房間」，不另立第四套骨架 |

### 房間標籤只當加分，不當硬過濾（最重要的一條）

決定候選的是**類型白名單**，房間碼只用來排序加分。理由：catalog 的 `room_codes` 覆蓋不全——
儲藏室 0 件、玄關 5 件鞋櫃**無一掛 `entryway`**、`multifunction` 根本無此碼。
硬過濾會直接回傳零件。此原則一次解掉儲藏室、玄關、多功能室三個死局。

### 多功能室路由

| 問卷用途 | 套用骨架 |
|---|---|
| 客房 | 次臥（#6） |
| 工作 | 書房／工作區（#8） |
| 起居延伸 | 客廳（#2） |
| 未填 | 只放收納，或留空 |

### 兒童房

**不另立房型。**次臥（#6）若問卷標為兒童房，額外開放 `kids_room`(779 件) 候選池，骨架完全相同。

### 設計原則

1. 先讓房間「看得出用途」，不先塞滿  
2. 只用庫內明確類型——**規格必須以資料庫實際有什麼為準**  
3. 家電／軟裝分開（問卷＋生圖）  
4. 動線與廚浴陽台寧空勿塞：留白使用者知道待補，塞錯會讓人不信任整套自動配置  
5. 主臥／次臥共用骨架，只差量與可選  

---

## 客廳／臥室／餐廳細節

### 客廳砍序

`armchair` → `bookcase` → `coffee-table` → 換小沙發／電視櫃 → 報錯  

### 臥室砍序

主臥：`bookcase` → `chests-of-drawer` → 第二床頭 → 換小床／衣櫃 → 報錯（**至少留床**）  
次臥：`bookcase` → `chests-of-drawer` → 書桌椅組 → 換小床／衣櫃 → 報錯（**至少留床**）  

與舊 `SPACE_DEFAULTS` 差異：舊常無衣櫃、有小地毯；本表**有衣櫃、無地毯自動配、主臥床頭 2 次臥床頭 1**。

### 其餘砍序

| 房型 | 砍序 |
|---|---|
| 玄關 | 鏡 → 衣帽架 → 穿鞋凳 → 換小櫃 → 報錯 |
| 書房 | `wall-shelf` → `shelving-unit` → `bookcase` → 換小桌 → 報錯（**至少留桌椅**） |
| 儲藏室 | 尾端往前 → 報錯 |
| 多功能室 | 隨路由到的骨架 |

### 餐廳椅數

1. 跟人（2／4／6），上限 6  
2. 放不下：6→4→2  
3. 人數缺失：先 4 再減到 2  

砍序：`display-cabinet` → `sideboard` → 減椅 → 換小桌 → 報錯  

---

## 與程式對齊狀態

| 項目 | 狀態 |
|---|---|
| 本檔規格 | **v1 定版**（2026-07-31） |
| `backend/agent/knowledge.py` `ROOM_MINIMUM_FAMILIES` | 對齊到 v0；**v1 尚未對齊**（見下） |
| `select.py` 必要族系驗證 | 對齊到 v0 |
| `scene_service.SPACE_DEFAULTS` | 未接 |
| 前端 `ROOM_QUESTION_TEMPLATES` | 未接 |
| RAG `offers` 契約 | 未接 |
| Engine companion／hints 完整灌入第 6 步 | 未接 |

改策略時：**先改本檔 → 再改 `knowledge.py` → 補測試**。

### v0 → v1 差異（`knowledge.py` 待補的六項）

| # | v0 現況 | v1 定版 | 原因 |
|---|---|---|---|
| 1 | 房間碼別名缺 `outdoor` | 補 `outdoor` → `balcony` | catalog 用 `outdoor`(236)，接不上就永遠零候選 |
| 2 | 玄關 `shoe-cabinet` 硬必備 | 優先＋櫃類備援 | 全庫 5 件且無 `entryway` 標籤 |
| 3 | 床頭櫃「×1」未分主次 | 主臥 ×2、次臥 ×1 | 主臥雙人對稱 |
| 4 | 陽台可選「植栽／戶外椅」 | 刪除，維持空白 | 庫裡沒有戶外桌椅 |
| 5 | 儲藏室未註明過濾方式 | 明註不做房間過濾 | 否則回傳 0 件 |
| 6 | 多功能室「無硬性最少」 | 四條路由規則＋兒童房開 `kids_room` 池 | 從原則變可執行 |

⚠️ `backend/agent/knowledge.py` 屬 `backend/agent/`，**跨資料夾，動工前先知會**。

---

## 刻意不做

| 項目 | 用意 | 缺點 |
|---|---|---|
| 走道連通、美學評分 | 先定清單 | 暂时可能擠或不美 |
| 本檔直接改 production UI | 先 Agent 規則再跨 Bella | 畫面可能仍顯示舊預設字樣 |
| 廚房自動塞冰箱 | 產品邊界 | 預覽靠生圖補 |

---

## 接線檢查清單

1. [x] 策略表寫定（本檔，v1 定版 2026-07-31）  
2. [ ] Agent `knowledge.py`／`select.py` 對齊 **v1 六項差異**＋測試  
3. [ ] Bella：`SPACE_DEFAULTS`／問卷模板  
4. [ ] Agent：hints 排序、companion 傳 Engine、失敗原因回餵  
5. [ ] RAG：依最少槽位產 `offers`  
6. [ ] 回歸：floor04＋正常／偏小尺寸  

### 驗證

```bash
.venv/bin/python -m pytest -q tests/test_agent_select.py tests/test_agent_place.py
.venv/bin/python -m pytest -q tests/test_clearance.py tests/test_placement.py
```
