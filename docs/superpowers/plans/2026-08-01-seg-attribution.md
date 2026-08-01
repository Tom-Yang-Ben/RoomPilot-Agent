# own_dataset 切割失誤歸因表（2026-08-01 基線）

基線：24 題、GT 151 間、命中 106（70.2%）、配對平均 IoU 0.894、
過切率 0.78（欠切主導）。報表 `report_own_own_dataset_segbase.json`。
另 floor02 整圖 seg_fail（GT 不計入 151，另列）。

## 失誤類別定義與統計

| 類別 | 定義 | 件數 | 純幾何可修性 |
| :--- | :--- | ---: | :--- |
| E1 開放式功能區誤併 | GT 沿「無牆邊界」分區（廚/餐/客一體、玄關-走道虛線、樓梯嵌在大空間），封口規則無牆可封 | ~21 | **不可修**——圖上沒有牆，改封口參數無濟於事；需功能區切分機制（見結論） |
| D 灌水漏水→整片漏切 | 室外灌水經未封開口漏進室內，中央走道帶連同鄰房整片判為室外（疊圖大片空白） | ~11 | **可修**——找出漏點補封口邏輯 |
| C2 樓梯間漏切 | 樓梯無四面牆、嵌在大空間角落，被併入鄰房 | 6 件中約 4 件與 E1 重疊 | **部分可修**——管線已有樓梯踏板偵測，可用其足跡切房 |
| C3 小空間漏切 | 小儲藏/洗衣間/小浴室低於面積門檻或被併入鄰房 | ~6 | 部分可修——調 `amin` 門檻與小縫封口 |
| C4 陽台漏切 | 陽台在主建物輪廓外側，灌水直接判室外 | 2 | 可修但每件影響小 |
| F 整圖 seg_fail | floor02 分割整個失敗（`segment_rooms` 回 None 或無房） | 1 圖 | 待查 |

漏切房型統計：Kitchen 9、Bath 9、LivingRoom 7、Hallway 6、Stair 6、
Storage 3、Entry 3、Balcony 2 ＝ 45。

## 逐圖歸因

| 圖 | gt/pred/match | 漏切房 | 歸因 |
| :--- | :--- | :--- | :--- |
| floor54 | 9/6/5 | Entry, Stair, LivingRoom, Kitchen | E1：廚/客/玄關/樓梯開放一體，pred 連成一大塊 |
| floor52 | 7/4/3 | Entry, Stair, LivingRoom, Kitchen | E1：同上，完全同構 |
| floor47 | 8/6/4 | Kitchen, LivingRoom, Bath, Hallway | E1（廚餐+客廳誤併）＋D（走道帶整片白）＋C3（流理台帶小間） |
| floor13 | 10/5/5 | Hallway, Stair, Storage, Bath×2 | D：中央走道帶漏水，兩浴/樓梯/儲藏連坐整片白 |
| floor35 | 8/3/3 | Hallway, Entry, Bath, Kitchen, Balcony | D：廚房+走道+玄關+浴室整片白；C4（頂部陽台） |
| floor01 | 10/7/7 | Kitchen, Storage×2 | E1（family/dining/kitchen 誤併成一塊）＋C3（closet、W/D 間） |
| floor06 | 7/5/4 | Bath×2, Balcony | C3（LNDRY/小浴）＋C4（陽台在輪廓外） |
| floor31 | 6/4/4 | Kitchen, Stair | E1：廚房與樓梯嵌在客廳開放區 |
| floor09 | 7/6/5 | LivingRoom, Kitchen | E1：廚餐與客廳無牆分界 |
| floor07 | 8/7/6 | LivingRoom, Hallway | E1：玄關-走道虛線分界、客廳開放 |
| floor05 | 8/7/6 | Hallway, Kitchen | E1：kitchen/foyer/living 一體；走道分段 |
| floor03 | 6/5/4 | LivingRoom, Bath | E1：廚餐/客廳誤併；浴室小間 |
| floor04 | 6/6/5 | Hallway | 已知案（v2.22 橋合併修過，殘 1） |
| floor08 | 6/5/5 | Stair | C2 |
| floor12 | 7/6/6 | Stair | C2 |
| floor19 | 4/3/3 | Kitchen | E1（IoU 0.669 亦偏低，形狀受誤併影響） |
| floor20 | 4/3/3 | LivingRoom | E1 |
| floor38 | 6/5/5 | Bath | C3 |
| floor44 | 5/6/4 | Bath | C3（唯一過切圖，5→6） |
| floor02 | seg_fail | 整圖 | F：待單獨除錯 |

（floor15/39/40/48 全對，不列。）

## 對照 95% 目標的可行性推估（安全閥觸發）

修復潛力疊加（開發集）：

| 累計修復 | 預估命中 | 分數 |
| :--- | ---: | ---: |
| 基線 | 106/151 | 70.2% |
| ＋D 漏水全修（~11） | ~117 | ~77% |
| ＋C3/C4 小空間陽台（~8） | ~125 | ~83% |
| ＋C2 樓梯切分（~2 不與 E1 重疊） | ~127 | ~84% |
| **純幾何封口路線天花板** | | **~84%** |
| ＋E1 功能區切分（~21） | ~148 | ~98% |

**結論：純幾何封口調優的天花板約 84%，距 95% 目標差一整個 E1 類。**
E1 的 21 件全部是「圖上沒有那道牆」——廚餐客一體、玄關走道虛線分界、
樓梯嵌在開放區。封口參數怎麼調都切不出不存在的牆。

要過 95%，需要「功能區切分」機制：把含多個房名文字/功能證據的大連通塊
再切開。管線內既有可用證據（不引入 ML 分割模型）：
- `detect_room_text()` 全圖 OCR 已有房名文字錨點（KITCHEN/DINING/FOYER…）
- 樓梯踏板偵測已存在，足跡可直接成房
- 廚房流理台/爐台符號已有偵測

此為架構層級的新增，超出本 spec「調參數與規則」的授權範圍——
依安全閥條款停下，帶本表向使用者重談路線。
