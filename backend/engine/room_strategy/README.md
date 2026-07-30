# 房型策略表（正式規格）

> **狀態**：v0 暫定拍板（2026-07-30）＋第 4 步全空間最少預設已寫定  
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

對應「4 空間與結構」會標的空間。類型鍵＝家具庫 `normalized_type`。

| 空間 | 正規碼 | 最少自動配置 | 可選 | 不自動配置 | 為何 |
|---|---|---|---|---|---|
| 主臥／次臥 | `bedroom`（UI 可細分 primary／secondary） | `bed`、`wardrobe`／`pax-wardrobe`、`bedside-table`×1 | 第二床頭、`chests-of-drawer`、`desk`、書櫃 | 軟裝、家電 | 能睡＋能收衣服＋床邊置物；主次同骨架 |
| 客廳 | `living_room` | `sofa`、`tv-bench`（同槽可 `tv-media-furniture`） | `coffee-table`、`armchair`、`bookcase` | 獨立電視、家電、地毯 | 能坐＋電視牆；茶几可選以提高小房成功率 |
| 餐廳 | `dining_room` | `dining-table`、`dining-chair`×N | `sideboard`、`display-cabinet` | 軟裝 | 先能吃飯 |
| 書房／工作區 | `workspace`（`study`→此） | `desk`、`office-chair` | `bookcase`、`wall-shelf` | 家電 | 一桌一椅 |
| 玄關 | `entry`（`entryway`→此） | `shoe-cabinet` | 衣帽架、鏡 | 家電、門墊軟裝 | 台灣玄關核心是鞋 |
| 儲藏室 | `storage` | `shelving-unit` 或 `storage-furniture`（同族） | 收納系統、櫃體 | 家電 | 功能即收納 |
| 多功能室 | `multifunction` | 無硬性最少；依用途再選骨架 | 沙發床／桌椅／收納 | 家電 | 避免未定用途就亂塞 |
| 廚房 | `kitchen` | **空白** | 非家電收納（少用） | **全部家電** | 家電禁自動摆 |
| 浴室 | `bathroom` | **空白** | 鏡櫃慎用 | 固定設備／家電 | 管線房為主 |
| 陽台 | `balcony` | **空白** | 植栽／戶外椅 | **洗衣機**等 | 採光與動線優先 |
| 走道／動線 | `hallway`（`circulation`→此） | **空白** | 無 | 軟裝 | 留空才是功能 |

### 設計原則

1. 先讓房間「看得出用途」，不先塞滿  
2. 只用庫內明確類型  
3. 家電／軟裝分開（問卷＋生圖）  
4. 動線與廚浴寧空勿塞  
5. 主臥／次臥規則共用，差在量與可選  

---

## 客廳／臥室／餐廳細節

### 客廳砍序

`armchair` → `bookcase` → `coffee-table` → 換小沙發／電視櫃 → 報錯  

### 臥室砍序

`bookcase` → `chests-of-drawer` → 第二床頭 → 換小床／衣櫃 → 報錯（**至少留床**）  

與舊 `SPACE_DEFAULTS` 差異：舊常無衣櫃、有小地毯；本表**有衣櫃、無地毯自動配、床頭預設 1**。

### 餐廳椅數

1. 跟人（2／4／6），上限 6  
2. 放不下：6→4→2  
3. 人數缺失：先 4 再減到 2  

砍序：`display-cabinet` → `sideboard` → 減椅 → 換小桌 → 報錯  

---

## 與程式對齊狀態

| 項目 | 狀態 |
|---|---|
| 本檔規格 | 已寫定 |
| `backend/agent/knowledge.py` `ROOM_MINIMUM_FAMILIES` | **已對齊**（2026-07-30） |
| `select.py` 必要族系驗證 | **已對齊** |
| `scene_service.SPACE_DEFAULTS` | 未接 |
| 前端 `ROOM_QUESTION_TEMPLATES` | 未接 |
| RAG `offers` 契約 | 未接 |
| Engine companion／hints 完整灌入第 6 步 | 未接 |

改策略時：**先改本檔 → 再改 `knowledge.py` → 補測試**。

---

## 刻意不做

| 項目 | 用意 | 缺點 |
|---|---|---|
| 走道連通、美學評分 | 先定清單 | 暂时可能擠或不美 |
| 本檔直接改 production UI | 先 Agent 規則再跨 Bella | 畫面可能仍顯示舊預設字樣 |
| 廚房自動塞冰箱 | 產品邊界 | 預覽靠生圖補 |

---

## 接線檢查清單

1. [x] 策略表寫定（本檔）  
2. [x] Agent `knowledge.py`／`select.py` 對齊＋測試  
3. [ ] Bella：`SPACE_DEFAULTS`／問卷模板  
4. [ ] Agent：hints 排序、companion 傳 Engine、失敗原因回餵  
5. [ ] RAG：依最少槽位產 `offers`  
6. [ ] 回歸：floor04＋正常／偏小尺寸  

### 驗證

```bash
.venv/bin/python -m pytest -q tests/test_agent_select.py tests/test_agent_place.py
.venv/bin/python -m pytest -q tests/test_clearance.py tests/test_placement.py
```
