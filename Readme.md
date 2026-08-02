# 現行管線架構（常駐說明，隨程式碼更新；以下 changelog 為歷史紀錄不回改）

## 執行順序（`floorplan2room.process()`）

```
1. probe_color()          判黑白/彩色，決定走哪條偵測管線
2. detect_bw / detect_color   牆、窗、門（純幾何）
3. refine_scale()         門寬鐵律反推 cm/px（單門 85 / 雙門 175 / 牆厚 17.5cm）
4. detect_room_text()     ← 全圖 OCR：房型文字證據
   detect_text_boxes()    ← 全圖文字框：供符號比對抑制假陽性
5. detect_symbols()       ← 全圖掃家具符號（含模板比對、樓梯踏板）
6. build_rooms()  ─┬─ segment_rooms()        切割
                   └─ classify_rooms_*()     命名
```

**第 4 步必須在第 5 步之前**：模板比對用 `text_boxes` 抑制圖面文字被誤判成
家具（floor06 的「LNDRY」「BALCONY」曾被判成 ksink/sofa）。順序反了不會報錯，
只會拿到空的抑制清單而靜默失效——`test_symbol_gate.py` 有原始碼順序斷言釘住。

## 切割（`build_rooms()`）

主體純幾何：牆端點沿軸向連到對面牆封住 40~260cm 開口 → 大核閉運算
**只當灌水屏障**判內外（v2.23 起與牆扣除解耦——室內面積用原始牆遮罩
＋0.5T 髮絲縫小核扣，門寬尺度的窄走道不再被封口核填掉）→ 室內連通塊
＝房間。碰影像邊界/室外的連通塊會被室外接觸過濾修剪（邊條不成房）。

封口提案有來源長度守門（v2.24）：牆柱不得投出 >2× 自身長度的封口
（floor35 實案：陽台短柱把 216cm 封口射進廚房切成三條），門尺寸
60~200cm 豁免、救援輪不設限。keep_small 樓地板以 0.8m² 實體面積
封頂（(2T)² 隨牆厚平方暴漲，厚牆圖的小浴格曾死在門檻下）。

三級救援階梯（只在前一級整圖失敗時啟用，通過的圖零觸碰）：
常規四輪封口核 → 細線圍欄併入屏障（露臺線擋灌水）→ 寬封口 360cm 重試。

切割後、命名前的整形（皆軸對齊，房間只有直角矩形系——使用者域約束）：
1. `_merge_nondoor_bridges()`：走道橫斷橋合併（門弧＋門墨水雙重否決）
2. `_merge_bath_nooks()`：浴室隔屏碎格合併——相鄰 <8m² 含浴具符號
   碎格併一間，含廚房系符號者不候選；無浴具的 <4m² 小格鄰接 ≥2 種子
   的群則吸收（單種子不吸，防吞儲藏室）
3. `_carve_stairs()`：開放區嵌樓梯以踏板串外框切出成房（宿主須 ≥4×
   足跡；同座梯段含隔平台 <140cm 先併）
4. `_split_by_text_anchors()`：一房含 2+ 房名文字錨點＝作者標了多個
   功能區，沿輪廓階梯下刀、取兩側方正度最高的位置（純矩形退中點）。
   10 類別以外的子區印字（DINING/FOYER）不採用——使用者裁決，
   子區歸屬由方正度決定
5. `_symbol_anchors()`：無文字圖的錨點補位——大房裡緊湊偏心的強廚房
   符號群單側觸發廚客分家（對側錨點＝遠半質量質心；兩半 ≥1.8 倍
   才成立，擋廚餐一體房）

面積終篩在橋合併之後（走道碎片先併回再篩）。切割失敗會讓命名層
無事可做——這也是 `--gt-seg` 評測模式存在的理由：用 GT 多邊形當
房間、只評命名層，把兩層的分數拆開量。

## 符號模板庫（v2.24 起量測驅動啟用）

`symbol_lib.npz` 943 條 Asset 模板。啟用清單由
`training/scripts/probe_symbol_quality.py` 決定——own_dataset 全類別
掃描、每個命中以 GT 房型多邊形當弱標籤自動歸 TP/FP：
kstove/ksink/tub/wc/bed/chair 啟用（逐類 chamfer 門檻
`CH_THR_BY_KIND`）、basin 以 7 條模板白名單外科啟用、tub 黑名單
2 條；sofa/wardrobe/dtable P≤0.5 續停。比對為「各自門檻內最佳者
勝出」。專案核心 5 類（Kitchen/LivingRoom/Bedroom/Storage/Bath＝
實際進 RAG→AI 設計流程的空間）現況見 `SEG_FAILURE_ANALYSIS.md`。

## 房型詞彙（10 類，2026-08-01 定案）

`Kitchen`／`LivingRoom`／`Bedroom`／`Bath`／`Entry`／`Storage`／`Garage`／
`Balcony`／`Stair`／`Hallway`。

單一真相來源是 `eval_rooms_cc.CLASSES`，答案集 `model.svg` 的 Space token、
產品輸出的 `rooms[].label`、`room_head.npz` 的 classes 三者**同名同序**——
中間不再有任何翻譯層。以前有，而那層翻譯（CubiCasa 的 `rooms_selected`）
按它自己的慣例把 `HallWay` 併進 `Entry`、把 `Office`／`StairWell` 塌成
`Undefined`，是本專案三次房型錯誤的共同來源。

總分低於 0.15 門檻時給哨兵值 `room`（顯示「空間」），它不是類別；量尺以
`norm_label()` 把它歸入 `Hallway`。

### 答案集標準色（2026-08-01 定案，單一真相源 `make_annotation_drafts.SPACE_FILL`）

| 類別 | 色碼 | | 類別 | 色碼 |
| :--- | :--- | :--- | :--- | :--- |
| Kitchen | `#e8843c` 橙 | | Storage | `#b8a06a` 棕褐 |
| LivingRoom | `#7dc37d` 綠 | | **Garage** | **`#909090` 水泥灰** |
| Bedroom | `#4a90d9` 藍 | | Balcony | `#b5368f` 洋紅 |
| Bath | `#3dbdbd` 青 | | Stair | `#a89cc8` 灰紫 |
| Entry | `#8f5fc6` 紫 | | Hallway | `#c9a0dc` 淡紫 |

`Undefined`（人工補標暫置）＝`#d9d9d9` 淺灰。Garage 選水泥灰的
理由：與九類皆異、與 Undefined 中灰 vs 淺灰可辨，且不撞疊圖結構色
（牆紅 `#cc2222`／門琥珀 `#ddaa00`／窗綠 `#22aa22`——磚紅、黃、深綠
因此不可用）。答案集 SVG 的多邊形 fill、文字標籤、Space class 三層
須一致（2026-08-01 已全數歸一並以本表為準）。

## 命名（優先序三選一）

| 順位 | 路徑 | own_eval 72 房 | 授權 |
| :--- | :--- | ---: | :--- |
| 1 | `classify_rooms_dino()` — DINOv2 裁切分類 | **87.5%** | Apache 2.0 可商用 |
| 2 | `fp_c.classify_rooms()` — 面積規則 | （明顯更差） | — |

**分數與 v2.21 的 90.3% 不可直接比較**：GT 慣例改嚴了。舊慣例下走道叫成
玄關算對，新慣例下算錯。同一份答案集的 A/B 已隔離確認這個落差。

缺件（torch / DINOv2 骨幹 / `room_head.npz`）才會降級，且**一定印警告**。
CubiCasa 語意投票已於 2026-07-30 整批移除——**產品推論路徑不再有任何
CC BY-NC 成分**。

逐間房把第 4、5 步的全圖證據「歸屬」進來後加權投票：

| 層 | 證據 | 歸屬方式 | DINOv2 路徑 |
| :--- | :--- | :--- | :--- |
| 1 | 房型機率 | 房間裁切圖過 DINOv2＋線性頭 | ✅ |
| 2 | 相對多數票 | （CubiCasa 專屬）| 隨其移除 |
| 3 | 圖示絕對面積 cm² | （CubiCasa 專屬）| 隨其移除 |
| 4 | 符號幾何＋模板＋樓梯 | 符號中心點落在哪間房 | ✅ |
| 5 | OCR 文字 | 字框中心點落在哪間房 | ✅ |

總分最高者勝，`<0.15` 標中性「空間」。OCR 權重 1.3 刻意高於模型滿票 1.0
——圖面文字是作者親口說的答案，可壓過「自信地錯」的模型。

`Stair` 與 `Hallway` 不在 `CC_ROOM_LABEL` 裡（模型無此輸出通道的歷史包袱），
必須由 `EXTRA_LABELS` 另行播種進 score，否則 OCR 層的 `if lab_t in score`
防呆會把證據靜默丟掉——`Hallway` 未播種時實測 P=R=0。

## 命名時的一道幾何判別

`_entry_or_hallway()`：判成 `Entry` 的房間若**沒有門直通屋外**，改判
`Hallway`。

Entry 與 Hallway 都是「沒有東西的空房間」，裁切圖上長得一模一樣，DINOv2
結構上分不開（實測 GT 4 間走道被判成 Entry 3、Bedroom 1，Hallway 掛零）。
再多訓練資料也學不到——外觀證據裡根本沒有區分資訊。分水嶺在通行關係：
玄關走得出去，走道不行。

判準用「有無對外門」而非「有無貼外牆」：貼牆版只救回 4 間中的 1 間，
floor74/76 的走道沿著外牆走卻沒有對外的門。門位取樣沿用
`fp_c.room_graph` 的語義；屋外遮罩在產品路徑取自 `segment_rooms()`，
在 `--gt-seg` 量尺路徑取自 `exterior_mask()`。

規則刻意單向且保守——只降級不升級（客廳也可能直接對外），且缺門位或
屋外資訊時不表態。「偵測不到門」與「沒有對外門」是兩件事。

## 命名後的兩道跨房後處理

- `_enforce_singletons()`：客廳/廚房全戶各限一間，同類多間**留面積最大**者，
  其餘降級為次高分；接著「有廚無廳」時把該廚房改叫客廳（客餐廚一體），
  但圖上明寫 KITCHEN 則豁免。此規則的兩種「改良」皆實測為淨負面，
  對照表見該函式 docstring。
- `_merge_nondoor_bridges()`：走道被 85cm 封口橋攔腰切成兩間時合併回去
  （85cm 恰為單門尺寸，光看尺寸分不出真門與走道橫斷）。**在命名之前**。

## 版本報表標準口徑（2026-08-02 使用者定案）

每個版本的變更一律以下列兩個指標、四條量尺（灰/彩 × dev/holdout）列表呈現：

- **空間切割正確性** ＝ 切對的房間 / 全部 GT 房間（IoU≥0.5 配對率，不論命名）
- **核心5項判讀率** ＝ **切對且叫對**的核心五類（Kitchen/LivingRoom/Bedroom/Storage/Bath）/ 核心五類 GT 總數——端到端口徑

歷史條目中「核心 5 類」若未註明，多為舊口徑（配對房內命名率），與端到端口徑不可直接比較；v2.27 起一律用端到端。

## 已知待辦

- floor69/70 的真廚房仍被限額規則犧牲（見 `_enforce_singletons` docstring
  的對照表——三種替代方案實測皆更差，是取捨不是疏漏）
- 切割：own_dataset 開發集 **82.2%（129/157）**、own_eval 保留集
  **80.6%（58/72）**、保留集核心 5 類 **86.7%**——v2.23+v2.24 全日
  自 70.2%/76.4% 起，開發保留同步爬升差距 1.4pp 無過擬合。殘餘：
  floor02 圍欄線在細線層缺失、floor13/09 整圖零符號（Hough/細線
  品質）、floor64 中距開口、無證據玄關。
  詳見 `SEG_FAILURE_ANALYSIS.md` 與 `docs/superpowers/plans/2026-08-01-seg-attribution.md`
- `Garage` 在答案集中 0 樣本，該類無法量測、線性頭該通道未經訓練
- ~~color 集 104 個 `Undefined` 待人工逐一標注~~ **2026-08-02 已全數
  人工審定完成**（28 張 214 間 0 Undefined；重複的 color_floor_11 與
  洩漏的灰階 floor19 已移除）
- floor61 的走道被 DINOv2 判成 `Bedroom` 0.70，不經 `Entry` 就進不了幾何
  規則，需另循他途
- `MAIN_SYNC_TODO.md` 已整份移除，待重新分析 ben 分支後重建

---

2026/8/2 v.2.29 變更（Balcony 殘餘輪——口袋貼殼環帶化、提案器陽台對；彩 dev 71.0%）

### 一、變更
- **口袋貼殼判定環帶化**：由「邊緣鄰近」改「與外圈環帶相交」——floor_17 頂部露台橫跨外圈上緣收不到的死角補掉；完全在圈內深處或懸空遠處仍拒。floor_17 10/10 收官、floor_06 +1。
- **DINO 提案器陽台對**：接受 {Balcony}×{Kitchen/LivingRoom/Bedroom}（信心從嚴 0.65）；fence 刀候選（窗帶在細線層是長直線）＋孤立線化（同軸線列 >3＝磁磚紋理整軸作廢）；小房（≥8m²）須有 fence 刀證據；Balcony 半必須貼建物外圈。floor_19 +1、棄守的 floor_09 意外 +1；floor_05 磁磚客廳誤切在三道守門下歸零。

### 二、量測（標準口徑）

| 量尺 | 空間切割正確性 | 核心5項判讀率 |
| :--- | :--- | :--- |
| 灰階 dev（153 房） | 85.0%（130/153）持平 | 88.5%（108/122）持平 |
| 灰階 holdout（72 房） | 81.9%（59/72）持平 | 73.3%（44/60）持平 |
| 彩色 dev（152 房） | **71.0%（108/152）**（前 68.4%） | 66.4%（73/110） |
| 彩色 holdout（62 房） | 69.3%（43/62）持平 | 66.7%（34/51）持平 |

明細：彩 dev +4（floor_17 +1、06 +1、19 +1、09 +1），Balcony 配對 22 間全對；holdout 持平——本輪增益屬 dev 特有露台版式。195 測試綠。

---

2026/8/2 v.2.28 變更（DINO 提案式切分——無錨點開放 LDK 最後手段；棄守裁定與符號召回收案）

### 一、變更
- **`_dino_propose_splits`**：對 ≥25m² 且房內無作者房名文字的大房，沿主軸輪廓階梯出候選刀＋中點，每刀切兩半交 DINO 驗證——兩半 top-1 恰為 {Kitchen, LivingRoom} 對且雙方信心 ≥0.55 才收，取信心和最高的一刀；驗證不過整房不動（寧漏勿誤）。攻開放 LDK 誤併：彩圖無 OCR 無符號、灰階符號召回被模板庫卡死，這些房沒有任何錨點可用。
- **棄守裁定**（使用者）：color_floor_07/08/09（近白暗示牆/空心雙線/木紋牆，dev 殘餘 18 間）不再投工程，留在分母如實計分。
- **符號召回收案（零出貨）**：floor13/09 零符號的三條工程路實測皆死路（門檻放寬＝床→chair 假陽性；thin 上採樣零效；源頭 2x 重萃取＝馬桶/盆栽→ksink 錯種毒害）。瓶頸＝模板庫缺美式極簡畫風符號，屬素材任務另立一輪。

### 二、量測（標準口徑）

| 量尺 | 空間切割正確性 | 核心5項判讀率 |
| :--- | :--- | :--- |
| 灰階 dev（153 房） | **85.0%（130/153）**（前 81.7%） | **88.5%（108/122）**（前 84.4%） |
| 灰階 holdout（72 房） | **81.9%（59/72）**（前 80.6%） | **73.3%（44/60）**（前 71.7%） |
| 彩色 dev（152 房） | **68.4%（104/152）**（前 67.8%） | **67.3%（74/110）**（前 66.4%） |
| 彩色 holdout（62 房） | 69.3%（43/62）持平 | 66.7%（34/51）持平 |

明細：灰 dev floor09 7/7 全中、floor31 6/6、floor47 4→6；彩 dev floor_10 +1；四量尺零退化，193 測試綠。

---

2026/8/2 v.2.27 變更（畫風分流——color 機制以 domain 閘門退出灰階路；版本報表標準口徑定案）

### 一、畫風分流（使用者裁定）
灰階路凍結維護，color 循環的新機制不再進灰階——「為了彩色動刀卻波及灰階」的模式終止。det 增加顯式 `domain` 欄位（detect_bw=gray / detect_color=color），以下機制改為彩圖限定：陽台口袋收割、外圈封口、fence 輪紮實度驗收（`segment_rooms(fence_guard=)`）、切分守門 DINO 讓行、符號子群離群剔除；DINO 頭選擇同步改用 domain。灰階自有機制（墨水細線救援輪等）不受影響。代價：口袋收割在灰階的增益隨分流退場（裁定接受）；未來若要取回，該函式已獨立、可開灰階自屬開關以灰階量尺單獨驗證。

### 二、量測（標準口徑：切割正確性／核心5項判讀率〔端到端〕）

**現在（v2.27）**：

| 量尺 | 空間切割正確性 | 核心5項判讀率 |
| :--- | :--- | :--- |
| 灰階 dev（153 房） | 81.7%（125/153） | 84.4%（103/122） |
| 灰階 holdout（72 房） | 80.6%（58/72） | 71.7%（43/60） |
| 彩色 dev（152 房） | 67.8%（103/152） | 66.4%（73/110） |
| 彩色 holdout（62 房） | 69.4%（43/62） | 66.7%（34/51） |

**彩色歷次**：

| 期別 | 切割正確性 | 核心5項判讀率 |
| :--- | :--- | :--- |
| baseline（答案集定稿後首測） | dev 59.2%／hold 67.7% | dev 34.5%／hold 51.0% |
| v2.25 | dev 60.5%／hold 66.1% | dev 40.0%／hold 64.7% |
| v2.26＝v2.27（彩色路無變動） | dev 67.8%／hold 69.4% | dev 66.4%／hold 66.7% |

**灰階分流前後**：

| 期別 | 切割正確性 | 核心5項判讀率 |
| :--- | :--- | :--- |
| color 機制波及期 | dev 83.7%／hold 81.9% | dev 86.1%／hold 75.0% |
| v2.27（分流後） | dev 81.7%／hold 80.6% | dev 84.4%／hold 71.7% |

189 測試綠；彩色路逐張持平零影響。

---

2026/8/2 v.2.26 變更（color 循環二/三——外圈封口、陽台口袋鬆綁；dev 63.8%→67.8%、holdout 66.1%→69.3% 轉正、端到端全對 39 間 vs baseline 26）

### 一、外圈封口與長牆豁免（floor_09 型漏水）
- `envelope_gap_seals`：建物外圈（bbox 周邊 3T）的 260~600cm 牆縫另開一輪封口——外牆寬窗帶超過常規 260cm 上限、窗偵測 R 僅 38% 擋不住的最後防線。室內大開口不受影響；過切 1.29→1.26
- 長牆豁免 `WALL_RESCUE_LONG`（預設關）：木紋真牆與家具的可分維度是長度（家具 <5T、真牆 ≥8T），但衣櫃長邊同為長細深木紋被誤救、dev 淨 ±0——開關保留、行為以測試釘死，待「兩端接牆網」等判別成熟再啟用（實測該判別失效：牆網本身太稀疏）

### 二、陽台口袋條件鬆綁（Balcony 漏切 13 間攻堅）
- 「未分配」取代「室外」：主分割大核閉運算會把殼外露台整片吞成牆（inside 但 labels=0，floor_17 頂部露台），原 outside 條件收不到
- 排除遮罩只用牆/封口：露台內部的植栽/磁磚紋理也在 fence 層，含 fence 的排除遮罩會把口袋自己蓋掉——fence 只負責擋灌水；圍欄環併入口袋、amax 0.30→0.35
- dev Balcony 配對 19 間命名全對（循環前端到端 0/28）；floor_12 兩座陽台全中

### 三、量測
| 指標 | 循環一末 | v2.26 |
| :--- | :--- | :--- |
| dev 命中 | 63.8%（97/152） | **67.8%（103/152）** |
| holdout 命中 | 66.1%（41/62） | **69.3%（43/62，超過 baseline 67.7%）** |
| holdout 配對房命名 | 90% | 91%（核心 5 類 94%） |
| holdout 端到端全對 | 37 | **39（baseline 26，+50%）** |

殘留：floor_07/08/09 畫風硬骨頭（空心/近白牆、木紋牆誤刪）~15 間、floor_10 貪婪配對邊際 -1、Hallway/Entry 散件。

---

2026/8/2 v.2.25 變更（color 管線首循環——答案集定稿、窗封口/空心牆/雙頭命名；dev 59.2%→63.8%、配對房命名 62%→90%、端到端全對 +42%）

### 一、color 答案集定稿與衛生
- own_dataset_color 19 張（152 間）與 own_eval_color 9 張（62 間）全數與使用者逐間審定，0 Undefined、parse_gt 全過；`COLOR_PIPELINE_PLAN.md` 記錄三階段計劃與逐輪結果
- 重複清理：color_floor_11 與 floor_04 同圖（連源頭 color_png 刪除）；灰階 floor19 與保留集 floor60 同圖（開發/保留洩漏，刪開發集側三處，own_dataset 25→24 張、own_train.txt 同步，**灰階開發集舊報表 157 房分母不可比**）

### 二、分割層（第一輪，dev 84→92）
- `hollow_wall_rects`：空心雙線牆（細深描邊夾白色中性填充，floor_07/08 畫法）補抓——單向閉運算搭縫、厚度/長度/深色佔比驗收；floor_07 由 seg_fail 救回
- `color_window_layers` 抽共用＋`detect_color` 接回窗與細線層：外牆窗帶不再是灌水的洞（floor_09 型「半戶被判室外」）；thin 只以 `det["fence"]` 供救援輪，不當墨水證據（彩圖細線滿是磁磚/家具線，會壓制走道橫斷合併）
- `window_side_gate`：假窗物理判別——牆＋封口＋全候選畫屏障、1.5T 閉運算補殼縫後灌水，真窗恰一側通室外；距離外圈/兩端錨定實測都分不開真假（floor_04/05/10 三案）
- fence 救援輪加紮實度驗收（<0.60 讓路）：深磁磚圖的紋理噪點屏障不再拼碎房（floor_30 5→1→5 復原）

### 三、命名層（第二輪，配對房命名 62%→90%）
- DINOv2 分域雙頭：color 答案集餵進訓練；混訓實測傷灰階（86.1%→80.6%）改 `--domain` 分域——灰階頭原封不動、color 頭 83.9% 出貨 `room_head_color.npz`，`build_rooms` 依 `det["fence"]` 選頭。灰階基準自 90.3% 移至 86.1% 係答案卷標籤修正所致（新舊頭同分、非退化）
- `_harvest_balcony_pockets`：圍欄補屏障重灌水收殼外封閉口袋（純加法），閉運算防圍欄線切碎；Balcony 配對 5→16、配對到的命名全對（先前 11 間全錯、6 個誤判 Stair）

### 四、量測（`--own-dir` color 集，IoU≥0.5）
| 指標 | baseline | v2.25 |
| :--- | :--- | :--- |
| dev 命中 | 59.2%（84/142，1 seg_fail） | **63.8%（97/152，0 seg_fail）** |
| dev 配對房命名 | — | 95.9%（核心 5 類 96.0%） |
| holdout 命中 | 67.7%（42/62） | 66.1%（41/62，floor_27 -1） |
| holdout 配對房命名 | 62%（26/42） | **90%（37/41）**、核心 5 類 72%→**94%** |
| holdout 端到端全對 | 26 間 | **37 間（+42%）** |

殘留（下循環）：Balcony 漏切 13 間（圍欄未進細線層）、floor_08 近白暗示牆（描邊 gray 189~200 灰度不可偵測，需語意/色塊分割路線）、floor_09 窗外漏點、floor_27 -1。診斷教訓：eval 暫存檔名含 color 強制彩圖路（2x），手動診斷須用 staged 檔重現。

---

2026/8/1 v.2.24 變更（核心 5 類聚焦——符號錨點切分、偵測層量測驅動啟用、墨水層兩刀；開發集 77.1%→82.2%、保留集 76.4%→80.6% 首次淨超基線、核心 5 類 86.7%）

### 一、量尺聚焦核心 5 類（使用者定義專案核心）

專案流程「辨識→RAG→AI 安排設計空間」，實際進設計的只有 Kitchen/
LivingRoom/Bedroom/Storage/Bath——根目錄新增 `SEG_FAILURE_ANALYSIS.md`
以此 5 類為核心指標並記錄殘餘失誤比重。命名誤植後端有工具可修，
**切割命中為首要**（使用者裁決）。

### 二、符號錨點切分（無文字開放區誤併，殘餘最大類 39%）

雙系錨點實測不成立（沙發模板在本畫風全滅）→ 改單側廚房符號群
觸發：緊湊（≤350cm）偏心（≥200cm）強符號群在 ≥15m² 大房＝開放
廚客，對側錨點取遠半質量質心；min_part_ratio=1.8 擋廚餐一體房
（floor07/38 誤傷實測歸零）。floor19/20/54 +4。
兩個失敗假設如實記錄：floor31 的「廚房符號」全是假證據（長櫃刻線
誤認 ksink、真爐台未偵測）、大房豁免偏心守門零收益已還原。

### 三、偵測層量測驅動啟用（使用者授權「一張張測試哪些模板有效」）

新工具 `probe_symbol_quality.py`：全類別掃描、GT 房型多邊形當弱標籤
自動歸 TP/FP，產出逐 kind 與逐模板品質報表。據此外科手術：
tub(P0.85@0.8)/wc(P0.86@1.2)/bed/chair 啟用、basin 白名單 7 條
（全類 P=0.33 不可整類開）、tub 黑名單 2 條、逐類門檻＋「各自門檻
內最佳者勝出」（修掉嚴門檻類拖死整個候選的互動缺陷）。
浴室碎格合併二落（首落零觸發因證據未啟用；wc 假陽性曾把 floor39
廚房吸進浴室，加廚房反證守門歸零）。

### 四、墨水層兩刀

- keep_small 樓地板 0.8m² 實體面積封頂（floor38 的 T=31 使門檻
  等效 1.0m²，0.94m² 浴缸格差 6% 死在門檻下）＋碎格合併吸收制
  （≥2 種子的群吸收無浴具小格）→ floor44 浴室收復
- **封口來源長度守門**：floor35 單圖最大失誤源的真兇不是家具誤判
  成牆，是陽台 56px 短柱把 216cm 封口射進廚房切成三條。牆柱不得
  投出 >2× 自身長度的封口；門尺寸 60~200cm 豁免（floor08 的 75cm
  真門縫曾被首版誤殺）；救援輪不設限（floor02 保住）→ floor35 +3、
  floor06/47/48 過切齊降

### 五、量尺對照（兩次保留集遷移驗證）

| 量尺 | v2.23 | v2.24 |
| :--- | ---: | ---: |
| own_dataset 切割 | 77.1% | **82.2%（129/157）** |
| own_eval 切割 | 76.4% | **80.6%（58/72，淨超基線 +3）** |
| own_eval 核心 5 類 | — | **86.7%（52/60）** |
| 開發/保留差距 | — | 1.4pp（無過擬合） |
| 測試 | 149 | **170** |

彩色管線牆體回歸全程持平 87.7/95.0/83.9。

---

2026/8/1 v.2.23 變更（切割層調優——牆扣除與灌水屏障解耦、樓梯足跡切分、OCR 錨點功能區切分、三級救援階梯；開發集 70.2%→77.1%、保留集持平 76.4%）

### 一、歸因先行（45 個漏切逐案看疊圖）

own_dataset 24 題基線 70.2%（106/151）。失誤三大類：開放式功能區
誤併 21（GT 沿無牆邊界分區，封口參數修不了）、閉運算填實 11（**不是
灌水漏水**——走道高僅門寬尺度，最小封口核 65px 把走道填成牆）、
小空間/樓梯/陽台 12。純封口調優天花板估 84%，觸發 spec 安全閥，
使用者裁決擴大授權加「功能區切分」（仍無 ML 分割模型）。

### 二、六輪修復（每輪 A/B 淨正向才收，各 commit 附數字）

1. **牆扣除與灌水屏障解耦**：大核只判內外，室內用原始牆遮罩＋0.5T
   髮絲核扣——窄走道存活（106→110）
2. **室外接觸過濾**：邊條/室外凹口假房間清除（pred 155→136）
3. **面積終篩延後到橋合併後＋門墨水否決**（110→111；墨水否決堵住
   「門偵測整圖 0 時弧檢查形同虛設」的盲區）
4. **樓梯足跡切分**：踏板串外框切房，四道防呆（111→114）
5. **OCR 錨點功能區切分**（114→116，floor01 10/10 全對）
6. **細線圍欄救援輪**（整圖失敗保險）

### 三、保留集第一次驗證揭露過擬合面（如實記錄）

own_eval 76.4%→75.0% 淨退 1：floor64 中距開口失去大核順封而誤併、
floor76 樓梯間誤切、floor74 命名層對切割邊界敏感（IoU 反升但
Storage 翻 Bath）；floor69 走道 +1 是正遷移。開發集 +10 部分來自
其房名文字密度高的特性。

### 四、答案卷慣例裁決與硬化循環

使用者裁決：**10 類別以外的子區印字（DINING/FOYER）不做辨識證據**；
分區歸屬由「切給誰較方正」決定。GT 實測佐證（floor01 餐區歸客廳、
floor08 餐區歸廚房、floor05 FOYER 歸客廳——標注者慣例本就是子區
不成房）。落實：詞彙表收斂＋切線改方正度制（候選＝輪廓階梯，
117/151）；樓梯宿主比收緊 ≤25%（開發集零成本）；寬封口 360cm
全域實測淨負向（−2/−10）退回、改作救援階梯第三級——floor02 整圖
復活 4/6（121/157，開發集 seg_fail 歸零）。

### 五、量尺對照

| 量尺 | v2.22 | v2.23 |
| :--- | ---: | ---: |
| own_dataset 切割命中 | 70.2%（106/151，1 圖全損） | **77.1%（121/157，0 圖全損）** |
| own_eval 切割命中 | 76.4%（55/72） | 76.4%（55/72，floor69+1/floor64−1） |
| own_eval 端到端全對 | 49/72 | 47/72（floor74 命名 −1、floor64 −2） |
| 測試 | 133 | **149**（+16 釘住案） |

保留集 95% 目標未達；歸因、殘餘失誤與失敗嘗試（全域寬封口）全記錄
於 `docs/superpowers/plans/2026-08-01-seg-attribution.md`。彩色管線
牆體回歸全程持平 87.7/95.0/83.9。

---

2026/8/1 v.2.22 變更（房型詞彙統一為 10 類 CamelCase，答案集與量尺不再需要翻譯層；Entry 靠「有無對外門」與 Hallway 分家；線性頭以新詞彙重訓）

### 一、詞彙統一（破壞性變更）

房型名字長期有三套：管線 `bed`/`living`、答案集 `Bedroom`/`LivingRoom`、
量尺再用 CubiCasa 的 `rooms_selected` 把後者翻回前者。那層翻譯不是中立的，
它按 CubiCasa 的慣例做了三個與本專案需求相反的決定：

- `HallWay` 與 `Entry` 同碼 7 → 走道一律被評成玄關。答案集 13 檔共 14 個
  `HallWay`，其中 floor07/35/54 三檔與 `Entry` 併存，證明標注者視為兩種
  空間。v2.14 早記載「走道不算玄關」的慣例，但 `sync_room_labels` 仍把
  走道寫成 `HallWay`，慣例與實作長期背離
- `Office`／`StairWell` 同塌成 `Undefined`（v2.19 已個別攔截）
- `outdoor` 與管線既有的 `balcony` 是同一種空間的兩個名字

只要翻譯層還在這類錯誤就會再犯，故取消：類別名直接採用答案集 token 寫法。
`space`→`Hallway`（桶裡本來就是走道，叫「空間」讀報表時分不出「模型放棄
了」還是「這裡真的是走道」）、`outdoor`→`Balcony`（消掉重複命名）。

- `gt_label_of()` 改自持對照表，不再 import `rooms_selected`；未知 token
  歸 `Hallway` 但**出聲一次**，答案集的錯字不再是看不見的失分
- 灰階答案集 25 檔 43 個多邊形歸一（`HallWay`×14、`StairWell`×11、
  `Office`×9、`Outdoor`×5、`WashRoom`×4），只改 token 不動座標
- `testdata/Asset/bathroom/` → `bath/`，與類別名對齊
- **破壞性**：`rooms[].label` 值域改為 CamelCase 10 類，下游須同步

### 二、Entry / Hallway 幾何分家（86.1%→88.9%）

詞彙改對之後量尺立刻誠實了：走道不再算玄關，分數從 90.3%(舊 GT) 掉到
86.1%(新 GT)，而 `Hallway` 的 P/R 是 **0**——管線結構上答不出這一類。
兩個原因：`Hallway` 沒播種進 score；DINOv2 看空房間的裁切圖分不出玄關
與走道（外觀證據裡沒有區分資訊，這不是資料量問題）。

補播種＋改用「有無門直通屋外」判別後 86.1%→88.9%，`Hallway` recall
0→0.75、`Entry` precision 0.6→1.0。**有一項退步須留意**：GT `Entry`
3 間裡有 1 間因該圖未偵測到對外門而被誤降級（recall 1.0→0.667），淨 +2。

初版按「貼外牆」判定只救回 4 間中的 1 間，已被「對外門」取代。

### 三、線性頭重訓（88.9%→87.5%，淨負面但採用）

舊頭是在「走道＝Entry」的舊慣例下訓練的，與統一後的答案集矛盾；且其第
10 通道（原 `space`）在灰階訓練集裡樣本數為 0，結構上永遠不會預測
`Hallway`。重訓後 `Hallway` 首次取得 10 個訓練樣本。

**如實記錄這是淨負面量測**：88.9%→87.5%，唯一差異是一間 `LivingRoom`
被判成 `Kitchen`；`Hallway` 新舊頭同為 3/4，走道辨識的功勞全在對外門規則。
仍採用，理由是留著矛盾標籤訓出的權重是會在日後反咬的隱形陷阱，而 1/72
在此樣本量下難與雜訊區分。若後續證明是穩定退步，`git revert` 即可。

### 四、量尺數字對照（own_eval 72 房，同一份答案集）

| 版本 | 命中 | 分數 |
| :--- | ---: | ---: |
| v2.21（舊 GT，走道算玄關） | 65/72 | 90.3% |
| 新 GT，無幾何規則 | 62/72 | 86.1% |
| ＋貼外牆規則 | 63/72 | 87.5% |
| ＋對外門規則 | 64/72 | 88.9% |
| ＋線性頭重訓（**現行**） | 63/72 | **87.5%** |

跨 GT 慣例的數字不可直接比較。A/B 隔離證據原存
`training/json/eval_rooms/report_own_gtseg_ab_{A_before,B_after}.json`，量測報表已改為
產出到 `temp/json/eval_rooms/`（不進版控），舊檔留在 commit `1df9107` 的歷史裡。

### 五、其他

- `MAIN_SYNC_TODO.md` 整份移除（內容留在 git 歷史），待重新分析 ben 後重建
- 新增 `test_room_entry_hallway.py`（12 項），測試總數 109→121

---

2026/7/30 v.2.21 變更（CubiCasa 血統整批移除——房型命名層換 DINOv2 凍結骨幹＋線性頭，own_eval 保留集 79.2%→90.3%，且產品推論路徑不再有任何 CC BY-NC 成分；命名層後處理修好兩處誤傷真廚房）

一、授權：這是整件事的前提，先驗證才動工

- DINOv2 的 GitHub repo 放了多種模型、授權不同。我們用的基礎骨幹
  `dinov2_vits14` 是 **Apache 2.0**（上游 README 明載 "DINOv2 code and model
  weights are released under the Apache License 2.0"），**可商用**
- repo 內的 FAIR Noncommercial / X-Ray Research 授權是給 CELL_DINO、
  XRAY_DINO 等醫療變體的，與我們無關；實際下載的檔案只有
  `dinov2_vits14_pretrain.pth`（88MB）一個
- 對照：CubiCasa5k 權重 CC BY-NC 禁商用，v5 微調為其衍生物一併受限。
  這條路確實解掉了 v2.15 就記載的授權硬閘

二、命名層換人（`classify_rooms_dino` 取代 `classify_rooms_cc`）

| | own_eval 72 房保留集 |
| :--- | ---: |
| CubiCasa 語意投票（舊） | 57/72 = 79.2% |
| **DINOv2 裁切分類（新）** | **65/72 = 90.3%** |

- 新增 `backend/floorplan/room_classifier.py`（推論）＋ `room_head.npz`
  （15KB 線性頭，只用 own_dataset 157 房訓練，own_eval 保持乾淨）
- 層 1 換成 DINOv2 機率；層 2（相對多數票）與層 3（圖示絕對面積 cm²）
  隨 CubiCasa 一併消失——兩者的資料來源都是 CubiCasa 模型的輸出通道；
  層 4/5（符號幾何、OCR）原封不動，本就無 CubiCasa 血統
- 缺件（torch／骨幹／線性頭）退回面積規則，且**一定印警告**不靜默降級

三、命名層後處理修好兩處誤傷真廚房（kitchen recall 0.600→0.800）

DINOv2 接手後 9 個錯誤裡有 4 個是**純分類器判對、被後處理弄壞**的真廚房，
分屬三種根因：

- `open_living` 的 `2.0×` 係數過嚴。floor64 客廳 living 0.56 / kitchen 0.41
  過不了 `0.56 > 0.82`，防呆不觸發，廚房符號繼續加分把它推成 kitchen。
  CubiCasa 的分數分布平緩故 2× 可行，DINOv2 的機率是尖銳分布 → 改為比大小
- 「有廚無廳→改叫客廳」無條件觸發。floor73 真廚房 kitchen 1.00 / living 0.00
  被改名 → 加門檻：該房自身 living 分數 ≥0.05 才升級
- floor69/70 是限額「按面積挑」的犧牲品，**維持不改**——第三次實測確認改成
  「按分數挑」整體更差（64→62），是取捨不是疏漏。對照表見 docstring

四、移除清單與驗證

| 移除 | 說明 |
| :--- | :--- |
| `backend/floorplan/ccmodel/` | CubiCasa 模型定義副本（v2.19 才建，任務完成） |
| `backend/floorplan/infer_cubicasa.py` | 語意遮罩推論腳本 |
| `backend/floorplan/model_finetuned_v5.pkl` | v5 微調權重 200MB（未進版控） |
| `cubicasa/` | 語意快取 207 檔 30MB |
| `floorplan2room` 內 16 個定義 | 快取路徑/驗證、權重下載鏈（含 GitHub token 換 S3 簽名）、`ensure_cc_masks`、`classify_rooms_cc`、`CC_ICON` |
| `test_cc_weights_download.py` | 測的是已刪除的權重下載機制 |

**保留** `CC_ROOM_LABEL`：它是房型詞彙表，GT 標注仍是 CubiCasa 格式的 SVG，
`eval_rooms_cc.gt_label_of` 需要這層映射；產品路徑只用 `.values()`。
標注解析（`lmdb`／`scikit-image`／`floortrans.loaders`）屬 `training/` 研發
工具，不隨產品出貨，授權風險不適用。

驗證：移除前後 **混淆矩陣逐格完全相同**（65/72 = 90.3%）；端到端實跑 floor13
從「空間8.76m²、空間8.12m²」變成「臥室、廚房」；`pytest training/tests/` 107 綠
（原 116 扣掉 7 支權重下載測試與 2 支 CubiCasa 專屬的弱票放大測試）。

五、部署變更：`torch` 由 semantic extra 升為必要依賴（CPU 版即可）。DINOv2
骨幹 88MB 經 torch.hub 首次下載後快取於 `~/.cache/torch/hub/`，**實測封鎖
網路仍可載入**——非執行期連網需求，同 v5 權重的既有模式。相對地，部署端
不再需要 200MB 權重、30MB 快取，也不必再跑 `apply_cubicasa_patches`。

2026/7/29 v.2.20 變更（模板比對從死碼救活：移除 Hu 粗篩＋逐類啟用＋文字抑制，kitchen recall 0.773→0.818 且 bath precision 零損；CubiCasa 向量模板 3516 條經 A/B 實測零貢獻已剪除，庫 4459→943）

一、根因量化——Hu 粗篩從未放行過任何候選（v2.18 只查到「Asset 進不了關」，本輪量到全貌）：

- 12 張灰階圖：輪廓候選 2016 → 過尺寸閘門 509 → **過 Hu 粗篩 0**。不是 Asset 專屬，是整條路線 B 從未運作
- 候選對全庫的最佳 Hu 距離（門檻 0.15）：CubiCasa 系中位 8.67／P5 2.179／最小 0.484；**Asset 系中位 3.98／P5 0.522／最小 0.178**
- **v2.18 的印象要反轉**：Asset 點陣模板系統性地比 CubiCasa 向量模板更接近查詢圖。合理——查詢側本來就是掃描圖的點陣細線層，點陣模板同源。「素材白做了」不成立，真正沒作用的是那 3516 條向量模板
- Hu 的 0.15 應是拿模板對模板校出來的；真實查詢輪廓帶斷線、鄰接墨水、雜訊，Hu 矩對此極敏感，差 1~2 個數量級

二、閘門重構（尺寸 → chamfer，Hu 整個移除）：

- `chamfer_dt()` ＋ `load_lib()` 預算模板距離場：把重複的 distanceTransform 提出迴圈——粗篩移除後每個候選要對整個 kind 的模板算 chamfer，這是可行性關鍵
- `CH_THR` 2.0 → **1.2**（v2.18 §4 天花板量測值；2.0 是搭配 Hu 粗篩的寬鬆值，粗篩移除後由它獨自把關故收緊）
- **`ENABLED_KINDS = ("kstove", "ksink")`**：在 `load_lib()` 就濾掉，未啟用者連 chamfer 都不算、尺寸閘門也隨之收窄。這是與 v2.18「調高全域門檻」的關鍵差別——那是全域旋鈕，真假證據一起放行故 bath precision 崩壞；逐類啟用是外科手術
- 文字抑制接線：`detect_text_boxes()` 早就存在但只用在門扇迴轉區，本輪接進 `match_symbols`。**配套改了管線順序**——`process()` 與 `run_pipeline()` 原本先算 symbols 再算 text_boxes，抑制會拿到空清單；順序反了不報錯只靜默失效，已加原始碼順序斷言釘住
- `SYMBOL_KINDS` 環境變數可覆寫啟用清單供 A/B（同 `CC_WEIGHTS`／`CC_CACHE_DIR` 慣例）

三、驗收（24 圖/157 房，gt-seg 同尺）：

| | 具名 | kitchen R | **bath P** |
| :--- | ---: | ---: | ---: |
| 本輪起點（v2.19） | 117/157 = 74.5% | 0.773 | 0.920 |
| 新閘門 | **118/157 = 75.2%** | **0.818** | **0.920** |

其餘七類 recall/precision 逐項完全相同。**kitchen recall +0.045 正是 v2.18 預測「唯一穩定的真實增益」，而 bath precision 一分未損**——證實崩壞源於全域放寬而非模板本身。

四、CubiCasa 向量模板 3516 條剪除（使用者授權：驗證無用即移除）：

- A/B：新閘門下把五類（oval/tubrect/stove/sinkicon/shower）全部加回，**混淆矩陣逐格完全相同**、具名 118/157 一分未動。12 張圖它們只命中 4 次（stove 2／oval 1／tubrect 1），且全是手寫幾何規則已覆蓋的 kind
- 組成揭露：3516 條裡 `sinkicon` 2110 ＋ `stove` 1402 就佔 3512，**`oval`／`shower` 各僅 1 條、`tubrect` 2 條**——v2.8 記載的「上千變體」全集中在兩類
- `symbol_lib.npz` 4459 → **943**（478KB → 143KB），保留全部 Asset 十類（其中八類入庫但停用，日後改善閘門可重啟）
- **手寫幾何規則不受影響**：`detect_symbols` 仍獨立產出 oval/tubrect/bedrect/stove，那是另一條路
- `extract_symbol_lib.py` 標為已退役（重跑會把向量模板灌回，且需 5.6G CubiCasa5k 資料集）
- `load_lib()` 新增缺 kind 警告——靜默停用是本模組既有陷阱，不再無聲

五、下一步（未動工）：文字抑制目前在兩類配置下量不到效果（floor06 抑制 0 個，因 v2.18 記載的 LNDRY/BALCONY 假陽性是 ksink/sofa，而 sofa 已停用），它是重啟更多類別時的保險；`bed`（283 條，準但量少）是下一個評估對象。`pytest training/tests/` **96 綠**。

2026/7/29 v.2.19 變更（房型新增 office/stair 兩類拆解 space 混合桶，具名 72.6%→74.5% 且舊八類零倒退；推論鏈與 training/ 完全脫鉤——模型定義入 backend/floorplan/ccmodel/、symbol_lib 入 backend/floorplan/；Windows 原生 cp950 編碼陷阱修復）

一、房型 office/stair 補完整條鏈路（v2.14 裁決的 10 類，本輪履行）：

- 根因複述：`Office` 與 `StairWell` 在 CubiCasa `rooms_selected` 同為 11(Undefined)，
  評分的 `space` 實為「書房＋樓梯間＋真未定義」混合桶（recall 0.286）
- GT 側 `eval_rooms_cc.gt_label_of()`：在 `rooms_selected` 塌陷**之前**攔截兩個具名 token；
  `CLASSES` 9→11 類。實測 own_dataset token 分布 157 間，僅 Office 7／StairWell 7 兩者改判，其餘九類逐一驗證未動
- 管線側 `EXTRA_LABELS`：**CC_ROOM_LABEL 不新增 11 的映射**——模型沒有這兩類的輸出通道，
  硬映射 11 會把所有 Undefined 像素倒進來。改以 0 分播種進 score，讓證據層加分
  （不播種的話 OCR 層 `if lab_t in score` 防呆會靜默丟掉證據）
- 層 4 新增 `detect_stairs()`：踏板＝平行等長等距線。踏面深度 21~35cm／梯段淨寬 70~160cm
  ／**≥4 條**／間距一致性 ≤1.35 倍。條數下限是關鍵——v2.18 已記「衣櫃內部分隔線與樓梯踏步
  幾何同構、本質不可分辨」，衣櫃分隔通常 1~3 條、牆剖面線間距遠密於踏面，條數＋間距是僅有的鑑別軸
- 層 5 `OCR_WORD2LABEL` 補 OFFICE/STUDY/WORKROOM/DEN/LIBRARY→office、STAIR(S)/STAIRWELL/STAIRCASE→stair
- **驗收（24 圖/157 房，同 v2.18 尺）：具名 114/157=72.6% → 117/157=74.5%，舊八類 recall 逐類完全未動**；
  stair recall 0.429／precision 0.75；`space` 混合桶解散
- **`office` recall 0.0 已查明非 bug**：那 7 張圖 OCR 只讀到 0~3 行雜訊（「这」「中」「区」），
  圖面根本沒有房名文字。office 沒有幾何證據可用（`ASSET_KINDS` 無書桌／書櫃素材），
  OCR 是唯一來源——在美式文字標示線稿（floor04 那類）才會生效。不誤標，但也叫不出來

二、推論鏈與 `training/` 完全脫鉤（使用者裁定的目錄職責）：

- 職責界線：`backend/floorplan/`＝辨識程式與其執行期所需一切；`temp/`＝生成檔；
  `training/`＝**只放訓練材料與研發工具**，交付 main 的東西不得依賴此目錄
- **`backend/floorplan/ccmodel/`（新增）**：CubiCasa 模型定義的推論期副本（2 支 .py，約 29KB）。
  以往 `infer_cubicasa.py` 要 `sys.path` 掛 `training/CubiCasa5k` 再 `os.chdir` 進去
  （上游 `init_weights()` 寫死相對路徑 `floortrans/models/model_1427.pth`），
  等於把 6.6G 訓練目錄變成部署必要條件。現已全部移除
- **`model_1427.pth`（70MB）不再需要**：它是 MPII 姿態估計預訓練權重，推論建完架構後
  `load_state_dict(v5, strict=True)` 會覆蓋全部參數。**實測驗證：跳過 init_weights 與載入後再
  覆蓋，740 個參數張量逐張量完全相同（0 個相異）**，故 `get_model(pretrained=False)` 為推論預設
- 不取名 `floortrans`：研發工具 `eval_rooms_cc.py` 仍需原版 `floortrans.loaders` 解析 GT，同名會在
  `sys.path` 上互相遮蔽
- `symbol_lib.npz` **repo 根 → `backend/floorplan/`**（v2.18 當日移到根，本輪二次修正到位）。
  舊 `LIB_PATH` 往上三層推導，只搬 `backend/floorplan/` 就會解析到錯路徑，而**找不到檔不報錯**
  （靜默停用）；改與消費模組同目錄後 `backend/floorplan/` 自成可獨立搬運的單位。已加測試釘住。
  兩支 extract 腳本的 `--out` 預設改為引用 `symbol_match.LIB_PATH`，不再各自寫死
- `apply_cubicasa_patches.py` 移回 `training/scripts/`——推論已不碰 CubiCasa5k 程式庫，
  main 部署不必再跑這一步。`door_lib.npz` 維持 `training/`（只被 door_match.py 消費，位置本就正確）
- 例外一項，經裁定維持不動：`cubicasa/room/*_mask.npz` 雖是生成物，但屬**預算好的交付資產**
  （main 的 `DEFAULT_CACHE_DIR` 寫死此路徑、進版控讓部署端免 torch 免權重即可出結果）

三、Windows 原生 cp950 編碼陷阱（換機後才現形，v2.18 未觸及）：

- **報表全失**：`json.dump(ensure_ascii=False)` 寫進未指定 encoding 的檔，遇 `⚠`(U+26A0)
  在 24 張跑完後才 UnicodeEncodeError，整份報表報銷
- **整張圖靜默記成 error**：管線警告字串含 `⚠`，stdout 重導到檔案時 Windows 預設 cp950 編不出來
  → floor13 被記為 error、**10 間 GT 蒸發**（GT 157→147，一度誤以為是新類別改壞了映射）。
  只在輸出導向檔案時發作，互動執行看不到
- 修法：報表 `open(..., encoding="utf-8")`；`eval_rooms_cc` 與 `floorplan2room` 的 `__main__`
  重設 stdout/stderr 為 utf-8（只動 `__main__`，被 import 時不改宿主行程）
- 註：cp950 編得出中文，卡的是 `⚠` 這個符號，故只有含它的路徑會爆

四、環境：本機 `.venv` 為空（僅 pip）已依 requirements 重建，版本與 v2.18 記載一致
（numpy 2.5.1／opencv 4.14／rapidocr 1.4.4／torch 2.13.0+cpu）；`pytest training/tests/` **83 綠**
（原 66 ＋ office/stair 16 ＋ 模板庫路徑防靜默失效 1）。

2026/7/29 v.2.18 變更（換機 WSL→Windows 原生，基準零差異複驗；Asset 家具模板 943 條入庫完成——但實測**功能未生效**，根因是 Hu 預篩門檻讓整套模板比對機制早已失效；symbol_lib.npz 移至 repo 根）

一、換機與環境重建（舊機 0x154 藍屏連環當機，改走 Windows 原生繞開 WSL 記憶體回收）：

- `.venv` Python 3.12.10 與舊機同版；套件逐項對齊 WSL freeze（numpy 2.5.1／torch 2.13.0+cpu／opencv 4.14 鎖 <5／rapidocr 1.4.4），差異僅建置工具與 Windows 專屬 colorama
- CubiCasa5k 那份 2019 全鎖定 requirements（`numpy==1.15.4`／`torch==1.0.0`）在 py3.12 無 wheel 且與根 `numpy>=2.0` 互斥，實際只需其功能子集（torch CPU／shapely／svgwrite／tqdm）——舊機亦是如此
- **基準複驗與舊機零差異**：gt-seg 具名 114/157＝72.6%、端對端命中 107（70.9%）IoU 0.8975、門過濾 84/86＝98%、`pytest training/tests/` 66 綠
- git 衛生：`core.autocrlf` 本地設 false（覆蓋 Git 安裝時寫在系統層的 true）；清除 10 個中斷 fetch 殘留的孤兒 pack idx（`garbage: 0`）

二、Asset 模板工程結案——階段 A 完成、驗收零倒退，但**功能實際未生效**：

- 合併完成：CubiCasa 3516 條保留＋Asset 新增 **943** 條＝4459（來源 1490 張 PNG，chamfer<0.6 去重 547）；`extract_asset_lib.py` 新增分批續跑（`--ckpt-dir`／`--batch`／`--redo`），即舊機當機後的斷點保護
- **合併前後評測報表逐字節相同**。根因：`symbol_match.HU_THR = 0.15` 是 chamfer 前的 Hu 粗篩，Asset 模板最佳 Hu 距離落在 0.56~837（差 1~3 個數量級），943 條無一進得了驗證關
- **不是 Asset 專屬問題**：106 張圖全庫掃描，現行門檻下含原有 CubiCasa 系在內總共只命中 **2 次**（sinkicon/stove 皆 0）——路線 B 模板比對早已是死碼，房型計分實際全靠 `detect_symbols` 手寫幾何規則在撐。成因是渲染路徑不同（向量 `render_polylines` vs 點陣 `png_to_template`），Hu 對此極敏感
- **放寬門檻已實測為淨負面，勿再嘗試**：`HU_THR` 掃 0.15/0.5/1.0/2.0/5.0/∞，具名在 113~116 間震盪像雜訊，拆逐類才見真相——`kitchen` recall 0.773→0.818 是唯一穩定真實增益（kstove/ksink 圖案獨特），代價是 `bath` precision **單調崩壞** 0.920→0.767→0.676（recall 完全沒動＝非漏抓，是誤標），與 basin/wc 假陽性數 0→60→366→463 同步
- 模板品質分級（chamfer≤1.2 天花板量測，36 張考卷）：`wardrobe` 55 個為假陽性大戶——平面圖衣櫃＝長方形＋內部分隔線，與牆體剖面線／樓梯踏步幾何同構，本質不可分辨（對照 `bed` 僅 3 個，床遠比衣櫃常見，數字反轉即誤判證據）；另有圖面文字假陽性（floor06「LNDRY」「BALCONY」chamfer 1.58/1.68 被判成 ksink/sofa）
- 下一步（未動工）：接上已存在的 `detect_text_boxes()` 做文字抑制（目前只用在門扇迴轉區，沒接到符號比對）→ 只啟用 kstove/ksink → Hu 粗篩換成對渲染路徑不敏感的指標

三、`symbol_lib.npz` 移至 repo 根（main 需同步）：

- 它是**推論期資產**非訓練產物（`process()`→`detect_symbols()`→`match_symbols()`→`load_lib()`），放 `training/` 易讓部署誤判為可略過
- 同步修正 `symbol_match.LIB_PATH`、`extract_asset_lib.py`／`extract_symbol_lib.py` 的 `--out` 預設；`door_lib.npz` 維持 `training/` 不動
- 部署提醒：`LIB_PATH` 由模組位置往上三層推導，只搬 `backend/floorplan/` 而不保持 repo 結構會解析到錯路徑，且**找不到檔不報錯**（靜默停用）

四、其他發現與文件收斂：

- **「書房」結構上答不出來**：own_dataset 答案含 `Office` 7 間，但 `rooms_selected["Office"]=11` → `CC_ROOM_LABEL` 只映射 1/3/4/5/6/7/9/10 → 落入 `space`。`StairWell` 同為 11，故評分的 `space` 類實為「書房＋樓梯間」混合桶（GT 14＝7＋7，recall 僅 0.286）。`ASSET_KINDS` 亦無書桌／書櫃素材。要支援需整條鏈路新增類別
- **main 第 7 點仍未履行**：查證 `origin/ben:backend/floorplan/vision/analysis.py:431` 仍是 `recognize_cody_rooms(image_bytes)` 缺 `cache_key`，語意快取在產品路徑命中率為零，137 份 `cubicasa/room/*_mask.npz` 形同虛設
- `TODO_ASSET_SYMBOLS.md`／`TODO_ROOM_OCR.md` 已刪除，結論全數併入 `MAIN_SYNC_TODO.md` 的 2026-07-29 收斂章節（含上述量測數據與待辦定序）
- 換機提醒：`training/asset_ckpt/` 十類檢查點不在版控（`training/*` 涵蓋、無負向規則救回），換機需重跑 1490 張 PNG 模板化＋O(n²) 去重；素材 `testdata/Asset/` 1576 張本身有版控

2026/7/27 v.2.17 變更（目錄結構全面對齊 main 分支——管線入 backend/、評測資料入 testdata/、自研產物入 training/；門過濾集兩代合併 86 張＋detect_windows 開口下限修正，窗精準率 96→98%）

一、目錄重整（與 main/bella 同構，交付面直接 diff 可同步；舊→新對照）：

| 舊位置 | 新位置 |
|---|---|
| `scripts/floorplan2dxf*.py`、根目錄 `floorplan2room.py`、`config*.ini`、`scripts/eval_windows.py`、`scripts/eval_doors.py` | `backend/floorplan/` |
| 根目錄 `cabinet_designer.py` | `backend/cabinetdesign/` |
| `png/`、`color_png/`、`Identify_ans/`、`Asset/` | `testdata/` 下同名目錄 |
| `dxf_scale/gray/`＋`dxf_scale/color/` | `testdata/dxf/`（扁平合併，與 main 一致） |
| `json/`（gray/arch/room/color/eval_rooms） | `training/json/`（退出版控；main 走 cody_adapter 記憶體交接不需檔案） |
| `tests/` | `training/tests/`（退出版控；`pytest training/tests/` 28 綠） |
| 根目錄 `model_finetuned_v5.pkl` | `backend/floorplan/`（CC_WEIGHTS 預設同步，與 main 統一） |
| 根目錄 `recognition_report.html` | `docs/` |

- 路徑配套：`load_config` 支援相對路徑落模組旁、`_SCRIPTS_DIR` 修復（ensure_cc_masks subprocess 鏈）、scripts/tests 全數改掛 `backend/floorplan/`；`docs/vibecoding/` 19 份自 cody 移除（main 為正式家）
- 新增 `MAIN_SYNC_TODO.md`（根目錄）：main 需配合的 6 項修改（cody_semantic 權重路徑、入口換 floorplan2room、v5 自動下載、測試更新、依賴清單、door 評測集新位置）

二、門過濾評測集兩代合併＋detect_windows 修正（凍結檔經授權的演算法變更）：

- 舊 19 張（door_type，100% 世代）自 git 歷史復原與新 67 張合併，統一命名 `door_001–086`；素材庫全目錄改「目錄名_三位數序號」（Tub 67／WC 104／Washbasin 128／dinner_table 73）
- 根因：主迴圈開口下限 0.4T 與 sub_window 的 1.5T 不對稱，比牆厚窄的「窗」可過關；修正為 `gmin_win = max(gmin, 1.5·min(T, max(1.6·wall_t, 0.6·T)))`（沿用 _has_door_swing 的可靠尺寸基準——直接用 1.5T 會誤殺 floor35 貼邊小窗，實測後撤回）
- 結果：門過濾 80/86→**84/86=98%**（達標 ≥95%）；灰窗全批次 **P96→98%／R96% 持平**（真實誤報 5→3、零真窗損失）；殘留 door_001/door_007 為多線門扇板＝窗符號幾何同構的困難樣本，實測（側翼長度比、帶內墨密度）與真窗分布重疊，判定不可局部硬擋
- 勘誤：記憶中 99%/95% 為 2026-07-23 chk 快照分數；現行程式可重現基準即 v2.16 記載的 96%/96%，本輪後為 98%/96%

三、其他：requirements 補 pytest；scripts/ 解散——main 需要的 infer_cubicasa／symbol_match（floorplan2room 硬依賴）／apply_cubicasa_patches 三支移入 backend/floorplan/，其餘 18 支研發工具移入 training/scripts/ 退出版控；Washbasin 素材自 pieces 策展（sink 42＋fittings 23 併入，pieces 原始庫移除）；json 產物與 door 工具鏈（door_match/door_propose/score_compare 等 6 支）路徑同步 training/json/。

2026/7/25 v.2.16 變更（微調 v5 首勝基線並接管預設權重——own 尺具名命中 0.273→0.788；權重掛 GitHub Release＋缺檔自動下載，前端 clone 即可用；快取/報表/HTML 全量重算）


一、微調 v5（標注痊癒後首訓，own 25 題×3＋HQA 300、v4 同配方）：

- own 尺（主尺）**史上首勝基線**：新 GT（標注修復後 72 房）同尺重評，具名 macro-F1 基線 0.215 → **0.473**、具名命中 0.273→**0.788**（52/66），八類 recall 無一倒退（kitchen 0.4→0.9、living 0.083→1.0、bed 0.35→0.8、bath 0.43→0.86、entry 0→0.43）——證實 v1~v4 全敗於「牆窗門 id 失配使九成手畫標注隱形」，資料修復後同配方立即反轉
- CubiCasa 尺 0.797 未過 0.838 門檻（storage/garage recall 有退）；**使用者裁決：目標域＝own 風格，v5 接管預設**（floorplan2room.py CC_WEIGHTS）。CubiCasa5k 資料集已自 Zenodo 重下，該尺恢復可評
- 訓練指令勘誤（HANDOVER_finetune_v5.md 已修）：官方 44 類權重須 `--weights ＋ --new-hyperparams`；`--furukawa-weights` 是 51 類原始權重入口，誤用即 size mismatch
- cubicasa/room/ 語意快取 136 檔全量 v5 重算＋9 個來源已刪死快取移除；四報表＋recognition_report.html 同步（own 端對端切割 76.4%、IoU 0.875）

二、權重發佈與部署（前端整合：丟任意新 PNG 判斷房型需要權重推論）：

- 200M 權重不進版控（GitHub 100MB 硬限），掛 Release [`weights-v5`](https://github.com/Tom-Yang-Ben/RoomPilot-Agent/releases/tag/weights-v5)（SHA-256 `b7a280d2…f4cf`）；floorplan2room.py 缺檔自動下載＋校驗（`_ensure_cc_weights`，7 例單元測試＋私有鏈全程實測）
- **部署重點：部署機把 clone 私有 repo 用的那顆 token 設成環境變數 `GITHUB_TOKEN`，其他的程式全自動**（token＝PAT，密碼等級秘密，勿進版控；repo 轉 public 後連 token 都不需要）
- 既有考卷走版控快取不觸發下載；`CC_WEIGHTS` 指定自訂權重時缺檔不代抓

三、待辦定序衝擊：v2.15 待辦首位「DINOv2 接融合層」前提已變——v5 預設 0.788 已超 DINOv2 0.730（舊 GT 63 房快照），該項降級為「新 GT 重評後再議」；彩色窗召回 38% 升為最大真實破口；彩色 30 題標注草稿人工修正（次輪訓練素材）為 own 域繼續放大的直接槓桿。

2026/7/23 v.2.15 變更（own 量尺接線＋雙重校準，切割真實命中 72.6%；微調 v4 四輪最佳仍維持基線；去 CubiCasa 路線確立——授權禁商用實錘、DINOv2 裁切分類 0.730；四層級成功率盤點＋HTML 報表；本機大清理 17GB）

一、微調第四輪（own_eval 撤出訓練集後以乾淨 26 題重訓）：

- v3 同配方（lr 5e-5/20 epochs/batch 8）RTX 3060 重訓 → model_finetuned_v4.pkl。CubiCasa 尺具名 macro-F1 0.814/macro-R 0.900 皆四輪最佳（kitchen P 0.537→0.684 且 R 持平、space→kitchen 誤名 51→25），但六類具名 recall 仍倒退——**未過門檻，預設權重維持基線**
- 量尺校準後翻案：own 尺具名 63 房 v4 0.619 vs 基線 0.270——先前「增益未遷移到 own 風格」判定下修為「**有遷移但精度不足**」（v4 被 CubiCasa 尺＋髒 GT 雙重低估）

二、own 量尺接線與雙重校準（自此為現行主尺；CubiCasa 量尺隨資料集刪除退役）：

- `eval_rooms_cc --own-eval [--gt-seg]`：own_eval 12 題當 GT，報表 report_own[_gtseg].json，CC_WEIGHTS/CC_CACHE_DIR 照舊正交
- 標注修復鏈三波：(1) fix_annotation_paths 增 `--dir`＋**transform 烘焙**（Inkscape 縮放/移動存成 matrix，House 全忽略→座標錯位；含 path 自帶 transform 兩層合成、text 前綴保渲染）；(2) **47 筆 VLM 盲標分歧人工覆核**（review.html 看圖點選→批次改 class 純文字改名，36 補名/10 錯名修正/1 降回；floor55 五房全 Kitchen 確為複製未改名）；(3) **rebuild_room_gt.py 幾何重建**——楔形 GT 只蓋部分房間，以同檔審定牆/窗/門 flood fill 重建 68/73 房輪廓（楔形當標籤指針、開放空間距離分水嶺切分）
- **get_polygon 尾空格陷阱**（重大潛伏 bug）：House 解析 points 固定 split(' ')[:-1]，自產 polygon 無尾空格被砍最後一頂點、遮罩剩半——v2.11 起所有轉換標注中招（own_dataset 訓練資料在內）。emitter 修正＋110 處補救＋防回歸測試；**own_dataset 標注自此痊癒，下輪微調品質高於 v1~v4 當時**
- 校準後真實數字：**切割命中 38.4%（假）→72.6%（53/73）、配對 IoU 0.829**；剩餘漏接集中 floor60（GT 牆未封閉）與 floor55 類開放式黏房。門位封口查明非缺口：segment_rooms 已內建弧門＋牆縫 40~260cm 雙層封口，zone 提名即源自同一推理

三、去 CubiCasa 路線（房型命名層重構為「房間裁切分類」問題）：

- **授權實錘：repo CC BY-NC 4.0、Zenodo 資料集 CC BY-NC-SA 4.0，官方權重與微調 v1~v4 全繼承禁商用**（同 MitUNet 移除原因），商用部署前必須替換
- extract_room_crops.py（own_dataset 131 房訓／own_eval 73 房測）＋ probe_room_classifier.py（凍結 DINOv2 ViT-S/14＋線性頭，8 向擴增/TTA，--backbone 可換）：具名 63 房正確率 **0.730**，勝 CC 基線 0.270 與 v4 0.619；VLM 盲測 0.984 僅當上限參考（循環性——GT 覆核多採其建議）。131 張樣本即勝語意投票，資料效率高微調一個量級
- **VLM 盲標＋人工把關**工作流實證：47 筆補名約 20 分鐘，之後擴充 own_dataset 沿用
- 本機大清理 **17GB**（使用者確認）：CubiCasa5k 資料集 5.6G（Zenodo 2613548 可重下）、training.zip 7.7G、runs_cubi/微調 v1~v3/finetune_data/ft 快取。保留：CubiCasa5k 程式庫（floortrans 解析仍被依賴）、官方權重（管線新圖推論仍需）、v4 權重。**換機備份需重新打包**

四、四層級辨識成功率盤點（recognition_report.html，根目錄，支援深色模式）：

- 全批次重跑後評分：灰牆 F1 0.99（勝 CC mask 0.89）/灰窗 96%/96%；彩牆 87.7/94.9/IoU 83.8；**彩窗 P62/R38 為全系統最低真實值**；門過濾 100%、門位 fused P 0.576/R 0.868（zone 提名回填 json/gray）；切割 72.6%；命名四方如上
- GT 缺口：彩色管線僅牆窗有答案，門位/切割/命名三層無 GT

五、待辦（優先序）：

1. **DINOv2 裁切分類器接進 floorplan2room 融合層**（命名 0.270→0.730，最高回報）；同步處理 v2.14 定案的 10 類對齊——量尺與分類器目前 9 類，office/stair 尚未進評分與訓練
2. 彩色窗召回 38%（調參方向 v2.13 已記：牆段配對 gap 與 covered 門檻的線寬適配）
3. 切割收尾：floor60 GT 牆補封（其 1/6 命中主因）、開放空間語意分界（家具聚落切縫，最難放最後）
4. own_dataset 擴充 50~100 題（VLM 盲標＋人工把關；DINOv2 頭直接受益）
5. 彩色管線門位/切割/命名 GT 建集（同流程低成本）
6. 門位精準率 0.576（118 候選 50 誤報）
7. 長期：floortrans 解析自寫替換（CubiCasa 程式碼授權亦 CC BY-NC）；training/ 備份重打包（現僅 782MB）
8. 可選：微調 v5（own_dataset 缺角痊癒＋題數擴充後再評估，單純重訓不值得）

2026/7/22 v.2.14 變更（目錄重整：Identify_ans/ 人工答案集中、training/ 本機自管不 push；own_wip 5 題定案淘汰；own_eval 12 題審定完成維持保留集；own 量尺房型 10 類定案）

一、Identify_ans/——人工答案總目錄（進版控）：

- 集中三區：`pngans/`（牆窗像素答案 gray 38＋color 28）、`own_dataset/`（26 題微調訓練＋門位 GT）、`own_eval/`（12 題房型保留評分集，永不進訓練）
- own_wip 定案淘汰：40ec85e「43→26 精選」剔除中真正懸置的 **floor17/24/30/34/46 共 5 題**曾自 git 歷史還原（原計畫 Inkscape 改完搬入 own_dataset），本輪定案整批淘汰刪除，對應 `pngans/gray/` 答案圖（floor30/34/46 共 3 張，gray 41→38）一併移除
- own_eval 審定完成：v2.13 的 12 題草稿（floor55~79）人工 Inkscape 修正完畢，**維持保留評分集身分、永不進訓練**；期間曾誤併入 own_dataset 與 own_train.txt（26→38 題），已回退至 26 題
- 命名釐清（本輪困惑點）：own_dataset 從未改名，own_eval 是 v2.13 新建的另一批題目；「答案」的分野在用途——教材（own_dataset）vs 考卷標準答案（own_eval），考卷本體＝原始 png
- **own 量尺房型類別定案 10 類**：既有 8 類＋office（書房；CubiCasa 原歸 Undefined）＋stair（樓梯；**硬需求——樓梯區不可擺設，管線輸出必須辨識**），走道標 Undefined 併 space（注意與 CubiCasa 慣例不同，其 HallWay→entry）。標注詞彙：`StairWell`/`Office`/走道留 `Undefined`

二、training/——本機自管總目錄（gitignore 不 push，換機整包 training.zip 搬運）：

- 收：CubiCasa5k/（6.6G 程式庫＋資料集）、chk/（管線預覽輸出，148M 解除追蹤）、eval_rooms/（房型評分工作區）、finetune_data(+zip)、cubicasa_room_ft2/3、model_finetuned_v1~3.pkl、官方權重 model_best_val_loss_var.pkl、door_lib/symbol_lib.npz（後兩者解除追蹤，可由 extract 腳本重生）
- 確認留原地進版控：tests/（單元測試是程式碼）、cubicasa/（語意快取 npz，雙機 git 同步的依據）
- 路徑更新 16 檔（floorplan2room CC_WEIGHTS 預設、symbol_match LIB_PATH、eval/extract/打包各腳本、tests、.gitignore、scripts/README.md）；sed 曾產生 `Identify_ans/Identify_ans/` 重複前綴 bug 已修
- 遷移驗證全綠且數字與搬移前一致：pytest 13/13、窗評分 P 99%/R 95%、門評分 fused P 0.588/R 0.858
- 雜項：png/floor10.png 補納版控；**training/ 從此只存本機，須自行排備份**

2026/7/21 v.2.13 變更（彩色管線接回窗偵測 P 63%/R 38%；own 風格保留評分集 12 題草稿；MitUNet 移除）

一、彩色管線窗偵測（v2.9 施工缺口補完）：

- 答案集擴充 19→28 張（color_floor_21~29 新增、11 重繪中移除；牆 RGB(136,0,21)＋窗綠框）。牆體回歸：P 88.3%/R 95.1%/IoU 84.5%，新舊題品質一致
- 接回 detect_windows：程式 v2.9 早移植好，但 `run()` 寫死 `wins=[]`＋config `windows=false`（「牆抓穩後再接回」的停用旗標）——牆已穩（IoU 84.5%），本輪接上
- **彩色渲染圖的窗是「淺灰描邊白條」，牆二值化(留最深2層)會整條濾掉**——窗偵測改用獨立二值層：灰<215(orig)/<235(soft)＋色度<40 排除彩色家具；thin=窗層減膨脹牆供門弧抑制
- eval_windows.py 補尺寸對齊：彩色管線對小圖 2 倍處理，chk 與答案圖尺寸不同會把同窗判成一誤一漏（灰階同尺寸縮放係數=1 零影響，回歸 P 99%/R 95% 不變）
- 窗首輪 **P 63%/R 38%**（55/144；漏抓水平 58/垂直 31 無方向偏差）。下輪調參方向：牆段配對 gap 條件與 covered 門檻的彩色線寬適配

二、own 風格保留評分集（量尺遷移第一步）：

- png/ 未進訓練的 12 題（floor55~79，上輪人工審定剔除批次、品質自行取捨）產草稿到 `own_eval/`，House 回讀 12/12 過；清單 eval_list.txt，**此集永不進訓練**
- 待人工 Inkscape 修正（工序：修正 → fix_annotation_paths --check → sync_room_labels）後接評分器，取代 CubiCasa 風格量尺

三、MitUNet 移除（授權禁商用＋增益邊際）：

- 刪 infer_mitunet.py 與 mitunet/ 遮罩快取。**拔除前實測代價：28 張牆體 88.3/95.1/84.5 → 87.7/94.9/83.8（各掉 0.2~0.7pp）**——CC-BY-NC 權重本就進不了產品，融合增益不值維護成本
- cc_mask_dir 融合機制保留（config 留空=純古典管線），供未來可商用高精準遮罩接入。**往後牆體回歸基準以無融合的 87.7/94.9/83.8 為準**

2026/7/21 v.2.12 變更（標注修正 105 處＋微調二、三輪仍未達標維持基線；門偵測 zone 提名 recall 0.132→0.858；GTX 1650 4GB 機訓練鏈重建）

一、標注修正（v1 未達標的真根因）：

- Inkscape 一般介面只能改 `<text>`，看不到解析器實際讀的 `<g>` class——人工其實已標 86 處文字但 class 全是 Undefined；另 15 處 class 已標而文字被人工改掉（class=Kitchen 文字=Bedroom），會直接教壞模型
- **scripts/sync_room_labels.py**：文字→class 同步（寫法正規化進 CubiCasa 詞彙；逐 g-id 定點替換；House 回讀驗證）。與 fix_annotation_paths.py 同屬「Inkscape 手修後必跑」。同步 101＋人工補判 4，Undefined 歸零

二、微調二、三輪（v2＝修正標注同 v1 超參；v3＝lr 減半 5e-5）：

- v2 全面優於 v1（整體 0.749→0.757、kitchen P 0.640→0.729、garage R 0.364→0.545）——證實錯標即 v1 主因；v3 部分 recall 回拉但整體 0.753 不如 v2
- **判定：均未過「具名 recall 不得倒退」門檻（基線具名 macro-F1 0.838 vs v2 0.794），預設權重維持基線**。26 題資料量的取捨曲線已現形：能買到的是「kitchen 精準率（F1 0.695→0.821）＋space 辨識」換「具名 recall 若干」，調 lr 只是沿線滑動。下一槓桿＝擴充 own_dataset（50-100 題）或融合側只採信微調模型的 kitchen 判斷
- apply_cubicasa_patches.py 擴成 9 項冪等補丁；新增 B 機（4GB 卡）專屬陷阱：**WSL 鎖頁記憶體與 GPU 位址空間共用，VRAM 吃滿後 dataloader pin 執行緒 CUDA OOM**——兩 loader 關 pin_memory 解，訓練兩次中途陣亡的根因

三、門偵測（Asset/door/ 剪裁圖引發的調查）：

- 診斷：detect_doors 弧偵測天花板 recall 僅 0.189（26 題 GT 106 門有 86 門無候選）；build_rooms 門位 zones（標注草稿 Door quad 的來源）實測 R 0.877/P 0.798 卻從未接進 doors
- 四支後處理腳本（凍結檔零接觸）：extract_door_lib.py（19 剪裁圖→door_lib.npz 152 模板）、door_match.py（弧候選 chamfer 重評分，真門中位 1.02 vs 非門 2.16）、door_propose.py（zone 提名 score_fused=0.88）、eval_door_match.py（A/B）
- 結果（門檻 0.85）：P=0.361/R=0.132 → **P=0.588/R=0.858**（不採模板救回 P=0.619/R=0.811）；原 score 不動，下游自選讀 score 或 score_fused。其餘 54 題與白模端採用待決

四、seg_fail 歸因與評分集退役決策：

- 端到端評分 59/70 題 seg_fail 儀器化分桶：42 全漏＋16 半漏＋1 局部、「切太碎被過濾」0 題——根因是 **CubiCasa 圖的牆畫成雙線空心/剖面線，實心牆偵測器看不見**（多題只偵測到 1~14 面牆、T 亂估 40~82px），封口邏輯無辜；zones R 0.877 是 own 實心牆風格上量的，兩者不矛盾
- **決策：CubiCasa 端到端分割評分退役，不為考卷風格補空心牆偵測**（產品資料是實心牆掃描圖，此失分不代表產品品質）。gt-seg 命名層評分暫留（微調 A/B 仍需大樣本量尺），長期方向是把量尺遷移到 own 風格：png/ 尚有約 12 張未進訓練的掃描圖可建保留評分集

2026/7/21 v.2.11 變更（路線圖 C 首輪微調：26 題本機 RTX 3060 訓練完成；驗收未達標——廚房精準率+10pp 但具名房型 recall 倒退，預設權重維持基線）

一、資料審定與訓練：

- 人工審定 43→26 題（17 題品質不足整組移除，含對應 png/ 掃描圖）；own_train.txt 重建 26 題、own_val.txt 3 題（floor01/20/40）
- **scripts/fix_annotation_paths.py**：Inkscape 手修把 37 個房間 `<polygon>` 存成 `<path>`（矩形工具/路徑編輯的預設輸出），House 解析直接 StopIteration，26 題中 17 題進不了訓練——僅直線段（M/L/H/V/Z）的閉合 path 無損轉回絕對座標 polygon；`--check` 供每輪人工修正後預檢
- 本機訓練取代 Colab（RTX 3060 6GB）：378 樣本/epoch（own 26×3＋hq_arch 300）、20 epochs 約 33 分（≈100s/epoch）、VRAM 峰值 5.9GB（驗證期整圖推論）。環境補齊：matplotlib/shapely/tensorboard(X)；pandas 2.x 相容兩處——train.py `DataFrame.append`→`pd.concat`、uncertainty_loss 統計轉 float（0 維 tensor 進 DataFrame 後 `mean()` 會 TypeError，epoch 結尾才爆）

二、驗收（eval_rooms_cc --gt-seg，70 題 786 房，vs v2.7 基線）：

- 改善面：kitchen P 0.537→0.640、space→kitchen 誤名 51→27（v2.7 最大破口砍半）、space R 0.230→0.273、living P 0.817→0.873
- 倒退面：整體正確率 0.776→0.749；具名房型 recall 多數下滑（storage 0.838→0.706、garage 0.818→0.364、living 0.957→0.886、outdoor 0.958→0.896）——26 題答案仍有 94 處 Undefined，疑似教模型把具名房讓給未定義類
- **判定：未達「具名 recall 不得倒退」門檻，預設權重維持基線**。微調權重 model_finetuned_v1.pkl（gitignore）、報告快照 eval_rooms/report_gtseg_ft_v1.json 留檔
- 基礎設施沉澱：infer_cubicasa.py GPU 化（CUDA 9.4s/張 vs CPU ~60s；大圖 OOM 單張退回 CPU；safe_globals 白名單載入含 numpy 標量的微調 checkpoint）；CC_WEIGHTS/CC_CACHE_DIR 改可環境變數覆寫——A/B 驗收不動基線快取（`CC_WEIGHTS=... CC_CACHE_DIR=cubicasa_room_ft python scripts/eval_rooms_cc.py --gt-seg`）

下一輪方向：Undefined 補名（23 題 94 處）優先；再訓時考慮 lr 降半或 epoch 減半、own 過採樣配比下修，盯 storage/garage recall。

2026/7/16 v.2.10 變更（目錄重整：入口 floorplan2room.py 留根目錄，其餘 16 支 .py 統一移入 scripts/）

- 所有非入口腳本改為 `python scripts/<名>.py` 執行（工作目錄仍是專案根）；入口 `python floorplan2room.py` 用法不變
- 路徑接線：floorplan2room 把 scripts/ 加進 sys.path 並以絕對路徑呼叫 scripts/infer_cubicasa.py；scripts 內 `__file__` 相對路徑（CubiCasa5k/、symbol_lib.npz、os.chdir）全部上調一層；tests/conftest.py 統一補 root＋scripts 兩個 sys.path
- 驗證：pytest 13 綠；floor05 重跑 json/room_chk 與版控逐位元一致；16 支 CLI import 煙霧測試全過。歷史 changelog 中的舊路徑不回改

2026/7/15 v.2.9 變更（路線圖 C 準備完成：43 題標注初稿＋Colab 微調環境——只差人工修正與按下訓練）

一、標注初稿（make_annotation_drafts.py → own_dataset/，43/43 成功）：

- **格式＝CubiCasa model.svg**：FloorplanSVG loader 支援 format='txt' 現場解析，訓練端只需 sed 一行（lmdb→txt）；junction heatmap 由 House 從 SVG 自動推導不必手標；人工修正用 Inkscape
- 草稿內容全來自管線輸出：牆矩形/窗/門位（高品質）→ id=Wall/Window/Door；房間方塊+房型 → Space 多邊形（38% 有名，餘 Undefined 待人工）；符號命中 → FixedFurniture 提示。floor01 疊圖目測：三臥/浴/開放客餐廚/儲藏全對——訓練可用等級
- 兩個上游陷阱已埋補丁：PolygonWall 的 points 屬性必須尾隨空格（split(' ')[:-1] 會吃掉最後一頂點）；**svg_utils 的 np.matrix 在 numpy 2.x 直接 ValueError（任何含圖示樣本都掛）→ apply_cubicasa_patches.py**（可重複執行，re-clone 後必跑，Colab cell 已含）
- 43 張全數 House round-trip 驗證通過；CubiCasa 圖示分類法沒有床（bedrect 不輸出，床訊息在房間類別）

二、Colab 微調環境：

- colab/finetune_cubicasa.ipynb（nbformat 驗證）：T4 檢查→clone+補丁→Drive 解壓→sed txt 格式→微調（lr 1e-4/20 epoch/batch 8 起步值）→checkpoint 回 Drive→sanity 推論疊圖；尾註本機驗收流程（換權重重算快取→eval_rooms_cc --gt-seg 對比 v2.7 基線）
- pack_finetune_data.py：own 43×3 過採樣＋hq_arch train 前 300（防災難性遺忘）→ finetune_data.zip 418MB；own_val 4 張僅訓練監控，**正式驗收永遠走 val/test 評分集**
- 剩餘人工步驟：修正 own_dataset/*/model.svg（重點：Undefined 房補名、漏牆補畫）→ 重跑 pack → 上傳 Drive → 執行 notebook

2026/7/15 v.2.8 變更（路線圖 B：符號模板庫建成＋比對機制接入；命中歸零的誠實記錄——表示法落差是下一關）

一、交付（基礎設施完成，管線零回歸）：

- extract_symbol_lib.py：train 4200 樣本萃取 FixedFurniture 六類向量線稿（local 座標即標準方向、排除 display:none 與隱形外框；細節不只在 InnerPolygon——爐台燃燒圈在 OuterCircle 的 circle 元素）→ symbol_lib.npz（328K 已提交）。**變體統計本身是發現**：馬桶/淋浴全資料集各只有 1 個標準圖塊（CubiCasa 用固定符號庫繪製），變體豐富的是水槽 2110、爐台 1402——「上千變體」的價值集中在可拉伸的檯面類
- symbol_match.py：整圖 log-Hu 距離＋對稱 chamfer 兩階段比對；候選=bbox 內細線層裁切（單輪廓比不上多部件複合符號，已修）。floorplan2room 掛載為並行互補（同 kind 20cm 去重聯集；shower/sinkicon 新證據 0.3/0.15）；庫檔缺失＝行為逐位元不變。pytest ×10 全綠
- **43 題回歸關通過（零 diff）**——但這是「無害也無效」：模板一個新命中都沒有

二、為什麼沒命中（三個實測根因，留給下一輪）：

- **表示法落差（主因）**：掃描/線稿圖的粗筆畫＋雜訊 vs 向量渲染 1px 模板——芬蘭圖上的真馬桶對自家模板 chamfer 2.73、Hu 1.66（門檻 2.0/0.15）；假候選與真候選分數區間重疊，放寬門檻只進假貨。修法方向：模板按查詢圖筆寬重渲染、或改學習式描述子（併入路線 C）
- **美式符號域差距**：模板庫是芬蘭慣例，floor44 的 X 圈爐台、美式床頭板本來就不在庫內——「寬鬆 Hough param2=12＋chamfer 驗證」實驗：floor01（無爐台）假圈群 chamfer 1.84 比 floor44 疑似真爐台 3.15 更低，驗證器在此表示法下無鑑別力
- **嵌入式符號**：爐台嵌在流理台檯面線內，輪廓 bbox 框不出獨立候選（floor44 的爐台根本進不了候選清單）

三、路線修正建議：B 的形狀比對路線暫停（等表示法突破），符號救援併入 C（微調自帶風格適應）；symbol_lib.npz 的真實變體即 C 的訓練素材。gt-seg 評分（路線 A 量尺）重跑確認零變化——量測系統本輪的功勞：三個根因全部是「量出來的」而非猜的。

2026/7/15 v.2.7 變更（路線圖 A 完成：房型答案集評分工具 eval_rooms_cc.py——房型權重從拍腦袋變可量測）

一、新增 eval_rooms_cc.py（model.svg Space 多邊形當 ground truth，房間貪婪 IoU 配對 ≥0.5＋9 類房型混淆矩陣）：

- 樣本：val/test 的 high_quality_architectural 單層樓各 30/40 張（train 永不沾——路線 C 微調後評分不被污染）；圖先複製 eval_rooms/input/<id>.png 避開語意快取以檔名為 key 的撞名（樣本全叫 F1_scaled.png）
- **對位陷阱（實證）**：SVG 的 width/height 宣告與圖面尺寸全資料集普遍不符（比例還非均勻），不可拿來驗對位；多邊形座標實為 F1_scaled.png 像素（疊圖驗證嚴絲合縫）——守門改用「多邊形範圍不得超出圖面 2%」
- 兩種模式：端對端（量整條管線）＋ --gt-seg 解耦（GT 多邊形直當房間方塊，只跑房型辨識層——牆偵測失敗不遮蔽房型評分）；報表 eval_rooms/report[_gtseg].json 供調參前後 diff；配對/正規化/混淆純函式附 pytest（tests/）
- 依賴：torch CPU＋lmdb/scikit-image/svgpathtools（見〇交接）；語意快取新增 73 張 npz 已提交（cc 預覽 png 改不進版控，同 eval_rooms/chk/ 疊圖——分鐘級可重生）

二、首輪基線成績（調參靶子就位）：

- **端對端**：70 張僅 10 張可評（59 張分割失敗）——真實掃描圖的牆多為斜線填充/細線輪廓，detect_solid 幾乎全漏（實心牆假設不成立）、比例尺被圖框/標註線帶偏（T=72px、0.24cm/px 之類怪值）。可評張內配對 IoU 0.769、GT 房間命中率 19.4%。**牆偵測是最大瓶頸，量化證據直接支持路線 B/C 的優先序**
- **GT 解耦（786 間房全進混淆矩陣）**：具名房型 recall 0.82~0.99（kitchen .985 / living .957 / bed .947 / bath .960 / entry .950 / outdoor .958 / storage .838 / garage .818）——辨識系統對「有名字的房間」很強。**最大破口：GT「空間」（未定義，183 間）僅 23% 守住，51 間被誤名廚房**（kitchen precision 掉到 0.537）→ 爐具/水槽圖示加分＋0.15 門檻對未定義空間過於激進，第一個調參靶子
- 注意：解耦模式的 cm 比例尺仍取自管線（常偏差），圖示 cm² 證據層受其影響、語意投票層不受——調參時先修比例尺來源或加大語意層權重皆可實驗

2026/7/15 v.2.6 變更（房間方塊管線 floorplan2room.py：判色調度＋牆端封口切房間＋辨識式房型；輸出目錄重整；換機交接）

〇、換機交接（重要）——不在版控、新機器要手動搬運/重建的東西：

- **cubicasa5k.zip**（5.5GB 官方資料集）：解壓到 `CubiCasa5k/data/`，得 `CubiCasa5k/data/cubicasa5k/{colorful, high_quality, high_quality_architectural}` 5000 樣本＋train/val/test.txt。每樣本含原圖與 model.svg 向量標註——`Space <房型>` 房間多邊形與 `FixedFurniture <設備>`（Toilet/IntegratedStove/Bathtub…）多邊形，是下方路線圖 A/B/C 的原料
- CubiCasa5k/ 程式庫、model_best_val_loss_var.pkl 權重：重建方式見 .gitignore 註記
- **.venv 重建**：`pip install -r requirements.txt`。opencv 已釘 `<5`——OpenCV 5.0 把 HoughLinesP 回傳 shape 從 (N,1,4) 改 (N,4)，兩支管線的門偵測會當場掛掉；torch 生態會拉進 opencv-python-headless（後裝者蓋掉 cv2），**兩顆都必須 <5**（本次事故：headless 5.0.0 蓋掉 4.13）
- **推論/評分另需**（主管線不用，requirements.txt 不收）：torch（兩台機器皆有 GPU，裝 cu126 版即可，見下方 GPU 現況）＋ `pip install lmdb scikit-image svgpathtools pytest`——infer_cubicasa.py 重算語意快取、eval_rooms_cc.py 解析 model.svg（floortrans.loaders 連帶依賴）時才需要
- **CubiCasa5k/ re-clone 後必跑 `python scripts/apply_cubicasa_patches.py`**：上游 svg_utils 的 np.matrix 在 numpy 2.x 會 ValueError，任何含圖示的樣本都無法解析（訓練/round-trip 都會中招）
- GPU 現況（2026/7/21 更新，工作在兩台機器間切換，**兩台皆可本機訓練**，Colab notebook 保留作備援）。基準測試同設定：CubiCasa 模型 batch 8 @256px、torch 2.13+cu126：
  - **機器 A：RTX 3060 Laptop 6GB**——0.37s/step、VRAM 峰值 2.3GB。WSL 記憶體僅分到 7GB（dataloader worker 數別開太大，必要時調 .wslconfig）、/tmp 是 3.7G tmpfs
  - **機器 B：GTX 1650 4GB**（compute 7.5）——0.46s/step、VRAM 峰值 2.17GB（含快取保留 2.62GB；桌面另佔約 500MB，仍有餘裕）。WSL 記憶體 19GB、/tmp 是 9.8G tmpfs
  - 兩台 pip 裝大套件都走 `TMPDIR=~/piptmp` 保險；換機後 `.venv` 重建順序：requirements.txt → torch cu126（`--index-url https://download.pytorch.org/whl/cu126`）→ lmdb/scikit-image/svgpathtools/pytest → clone CubiCasa5k/ 並跑補丁 → `pytest tests/` 應 13 全綠

一、新增 floorplan2room.py（房間方塊管線，不出 DXF；批次 `python3 floorplan2room.py` = png/ → room_chk/ + json/）：

- 自動判黑白/彩色（與 color_to_bw 同準則：HSV 彩色比例 ≥8% 或檔名含 color）→ 各自調用 floorplan2dxf / floorplan2dxf_color 的偵測函式（只 import 不修改）
- 牆端連線封口：_wall_gaps 找 40~260cm 牆縫開口全封 → segment_rooms 灌水切出房間方塊
- **比例尺改門寬鐵律校正 refine_scale()**：單門候選群（60~130cm）中位數錨定 85cm；無單門用雙門群錨 175cm；再無退外牆厚 17.5cm；外牆換算掉出 10~25cm 也回退。動機：上游 wall_min 比例系統性偏大 5~8%，真門被量成 100~108cm
- 門位規則（user spec）：牆端連線長 80~95cm（單門）/ 160~190cm（雙開門）才算門；json 記 length_cm/type/bbox
- **房型改辨識決定（放棄 v1.9 面積規則）**，四層證據計分（classify_rooms_cc + detect_symbols）：
  1. CubiCasa 房間語意像素投票（乾淨渲染圖 share 0.9+，直接命中）
  2. 已分類像素內相對多數票（美式極簡線稿 75~93% 像素被標「未定義」，殘存訊號仍可用）
  3. 圖示絕對面積 cm²（馬桶≥150/浴缸≥500=浴室鐵證、爐具+水槽=廚房、衣櫃密度≥8%且無臥室票=儲藏；設備尺寸是物理常數，不被大房間稀釋；桑拿=芬蘭訓練集誤報不採證；開放式客廳不被角落爐台搶名）
  4. 古典符號偵測（模型盲區補洞）：衛浴橢圓用「輪廓對擬合橢圓徑向偏差 ≤4%」鑑別（實測馬桶 1.6% vs 圓角矩形家具 7%+，鑑別度極高）；雙人床矩形 120~230×180~235cm（下限 120 排除沙發縱深）；浴缸矩形 70~100×150~190 須同室有橢圓；爐台=≥2 個燃燒圈（r5~14cm）聚 80cm 內
  - 證據總分 <0.15 誠實標「空間」；每間房 json 記 cc_share / icons_cm2 / symbols 可追溯
- 輸出：room_chk/<名>_room.png（房型色塊+房名+橘色牆端連線）、room_chk/<名>_door.png（門位黃框+門寬 cm 標註，獨立圖避免太亂）、json/<名>_room.json
- infer_cubicasa.py 擴充：npz 新增 room（12 類語意）/ icon（11 類圖示）argmax 通道（wall/window/door 欄位不動，讀取端向下相容）；修好只能從 CubiCasa5k/ 目錄執行的相對路徑問題；語意快取 cubicasa_room/ 43 張已提交（重算 CPU 約 1 分/張）
- 43 張批次成績：42 張成功切出房間（floor17 單一大空間開口 >260cm 封不住殼）；219 個房間 38% 有辨識命名（臥室 27/浴廁 22/廚房 22/客廳 5/儲藏 4/陽台戶外 2/玄關 1），全部無命名的圖只剩 5 張（floor13/15/34/35/46，家具符號模型不認得）

二、輸出目錄重整（巢狀化；png/、color_png/ 題目目錄不動）：

- `chk/gray|color/`、`dxf_scale/gray|color/`、`pngans/gray|color/`（原 chk、color_chk、dxf_scale、color_dxf_scale、pngans、color_pngans 六個目錄 git mv 保留歷史）
- 兩支管線與 eval_windows / eval_color_walls / eval_cc_masks / score_compare 的預設路徑同步更新（floorplan2dxf.py 僅動路徑字串，偵測邏輯零改動）；搬移後 eval_windows 重驗 **99%/94% 無回歸**

三、CubiCasa5k 資料庫套用路線圖（交接 TODO，按投報率排序）：

- **A. 房型答案集評分（CPU，~半天，先做）✅ v2.7 已完成**：eval_rooms_cc.py，基線見 v2.7 章節。後續調參迭代：改權重 → 重跑 --gt-seg（快取全熱，分鐘級）→ diff report_gtseg.json
- **B. 符號模板庫（CPU）⚠️ v2.8 基礎設施完成、比對暫停**：庫與比對機制已建（symbol_lib.npz＋symbol_match.py，零回歸），但三個實測根因（表示法落差/美式域差距/嵌入式符號）令命中歸零——見 v2.8 章節。形狀比對等表示法突破，符號救援併入路線 C
- **C. 微調模型（本機 RTX 3060）⚠️ v2.11 首輪已訓、驗收未達標**：26 題（43 題人工審定後）混 hq_arch 300 訓 20 epochs——kitchen P +10pp、space→kitchen 誤名砍半，但具名 recall 倒退（storage/garage/living），預設權重維持基線。下一輪：Undefined 補名（94 處）→ `--check` 預檢 → 再訓（lr/epoch/配比調降）。注意：單純用原資料重訓無效，必須混自家標注（own×3 已配比）
- **D. 房型相鄰統計先驗（小補）**：5000 張統計浴室貼臥室/廚房貼客廳等關係，當同分 tie-breaker

已知剩餘問題：floor17 分割失敗（單一大空間）；X 圈爐台不採證（放寬 HoughCircles param2 會在植栽/臥室爆出 14 組假爐台，實測不可行）；無馬桶同室的浴缸間、單人床（90~100cm 與沙發縱深重疊）精準優先設計放掉——以上皆由路線 A/B 接手。

2026/7/15 v.2.5 變更（語意遮罩換 MitUNet：救回路線復活，IoU 83.5% → 83.8%）

一、MitUNet（github.com/aliasstudio/mitunet，2025/12 發表）取代 CubiCasa 為預設語意遮罩來源：

- infer_mitunet.py：照官方組法（smp.Unet mit_b4 + scSE、Segformer 編碼器移植、512×512 推論），weights_only=True 安全載入；輸出與 infer_cubicasa.py 同格式 npz 到 mitunet_color/（已提交 20 張快取）。權重與 mitunet/ 程式庫不進版控（.gitignore 註記重建方式）
- 遮罩單獨評分（eval_cc_masks.py --dir）：MitUNet 90.3%/83.9%/77.0 vs CubiCasa 65.1%/75.4%/53.7——精準率高 25pp，逐圖無一輸
- **授權注意**：MitUNet 程式碼 MIT，但權重 CC-BY-NC 4.0 禁商用。評估/研發可用；正式商用部署要嘛聯繫作者授權，要嘛用其 MIT 訓練碼+CubiCasa5k 資料自行重訓

二、融合升級（config_color.ini 新參數 cc_veto_cov / cc_rescue，依遮罩品質調）：

- 否決票門檻放大到 cc_veto_cov=0.3（MitUNet 覆蓋率分辨力更乾淨：存活假牆 P90=0.00；假刪 94%/真誤刪 0.02%）；用 CubiCasa 遮罩時應改 0.15
- 「漏牆救回」用 MitUNet 復活：v2.4 用 CubiCasa 救回純度僅 1.7% 而棄用，換 MitUNet 後加四重門檻（貼牆網+牆厚條≤2.5T+深色 gray<100+中性色 chroma<15）純度達 96%；CubiCasa 同條件僅 37%，故 cc_rescue 僅高精準遮罩可開
- 20 張全量：精準率 87.6%→87.7%、召回率 94.7%→94.9%、IoU 83.5%→83.8%；受益最大 floor_20（IoU 83.5%→85.9%）、floor_18（76.9%→78.6%）
- 今日累計（v2.2→v2.5）：精準率 79.1%→87.7%、IoU 76.0%→83.8%，召回率 95.2%→94.9% 幾乎持平

2026/7/15 v.2.4 變更（CubiCasa 語意否決融合：IoU 82.9% → 83.5%）

一、重建 CubiCasa5K 推論環境並對彩圖評分（環境與權重不進版控，見 .gitignore 註記）：

- infer_cubicasa.py 改 weights_only=True 安全載入（杜絕 pickle 挾帶程式碼）；cubicasa_color/ 存 20 張彩圖牆遮罩快取（npz），eval_cc_masks.py 對遮罩評分
- CC 遮罩單獨成績 65.1%/75.4%/53.7——全面弱於古典管線（20 張無一勝），「取代」路線排除；但錯誤高度互補：我們的假牆像素 81.5% 被 CC 判非牆

二、CC 語意否決票接進 drop_light_rects()（config_color.ini 新參數 cc_mask_dir，留空或無快取檔＝純古典管線，行為不變）：

- 第四規則：cc_cov<0.15 且有任一弱訊號（灰度偏淺/微色度/微紋理）才刪。弱訊號守門是關鍵——CC 召回僅 75%，它漏抓的真牆不能單票處死（floor_01 中灰基柱 cc=0.19 就是活例）。20 張逐矩形統計：存活假牆 cc_cov 中位數 0.00、真牆 0.90，此規則假牆再刪 79%、真牆誤刪 0.11%
- 「CC 救回漏牆」實驗過並棄用：CC 有、我們沒有的區域抽成矩形後純度僅 1.7%（真 1 萬 px vs 假 144 萬 px）——理想分析裡「可救回的 40% 漏抓」實為已偵測牆的邊緣暈帶，不是獨立牆段；CC 額外標的多是淺色假牆。全量實測救回會把精準率從 87.6% 打到 68.6%
- 20 張全量：精準率 87.0%→87.6%、召回率 94.7% 持平、IoU 82.9%→83.5%；受益最大 floor_09（IoU 80.1%→82.8%）
- 後續若要更強的遮罩來源可換 MitUNet（2025/12，github.com/aliasstudio/mitunet，宣稱細牆邊界更準）——融合介面已就位，換遮罩檔即可

三、v2.4 牆體成績單（eval_color_walls.py，20 張像素級；今日累計 IoU 76.0%→83.5%）：

| 圖 | 精準率 | 召回率 | IoU | | 圖 | 精準率 | 召回率 | IoU |
| :--- | ---: | ---: | ---: | :---: | :--- | ---: | ---: | ---: |
| color_floor_01 | 89.7% | 96.5% | 86.9% | | color_floor_11 | 89.9% | 96.9% | 87.4% |
| color_floor_02 | 85.0% | 90.2% | 77.9% | | color_floor_12 | 88.4% | 91.6% | 81.7% |
| color_floor_03 | 86.6% | 93.8% | 81.9% | | color_floor_13 | 86.5% | 93.0% | 81.2% |
| color_floor_04 | 91.1% | 97.0% | 88.6% | | color_floor_14 | 82.7% | 92.5% | 77.5% |
| color_floor_05 | 73.0% | 95.3% | 70.5% | | color_floor_15 | 88.1% | 96.4% | 85.3% |
| color_floor_06 | 82.3% | 92.9% | 77.4% | | color_floor_16 | 86.1% | 95.8% | 83.0% |
| color_floor_07 | 86.7% | 93.4% | 81.7% | | color_floor_17 | 89.6% | 92.8% | 83.8% |
| color_floor_08 | 87.5% | 97.6% | 85.7% | | color_floor_18 | 83.9% | 90.3% | 76.9% |
| color_floor_09 | 87.1% | 94.4% | 82.8% | | color_floor_19 | 92.5% | 88.7% | 82.7% |
| color_floor_10 | 87.5% | 87.6% | 77.8% | | color_floor_20 | 92.8% | 89.3% | 83.5% |
| **整體(20張,像素加權)** | **87.6%** | **94.7%** | **83.5%** | | | | | |

2026/7/15 v.2.3 變更（彩色管線假牆過濾：答案集擴到 20 張，IoU 76.0% → 82.9%）

一、答案集 color_pngans/ 從 3 張擴充到 20 張，全量基準（改動前）：精準率 79.1%、召回率 95.2%、IoU 76.0%——召回夠高，失分幾乎都在「多抓假牆」，用 20 張答案的逐矩形特徵統計找出三類成因並逐一處理：

二、新增 drop_light_rects() 兩段式自適應假牆過濾（config_color.ini 新參數 gray_delta=25，0=停用）：

- 灰度規則：深灰家具（沙發/植栽陰影）能通過淡化層次+色度過濾，但整體灰度仍比真牆淺。以本圖「牆基準灰度」ref＝全候選矩形 mean_gray 的面積加權 P30 為準，牆矩形 mean>ref+25 且 P25>ref+12.5 才刪（P25 守門保住混入淺像素的真牆）；基柱 mean>ref+50 才刪。絕對門檻不可行——floor_01 外牆本身就是中灰（mean≈100），所以必須每圖自適應
- 色度+紋理規則：深棕木家具（床架/書桌）灰度跟牆一樣深，但真牆是中性灰（矩形平均色度≈3）且均勻（灰度 P75−P25≈10）——平均色度>18、或（色度>12 且離散>30）、或（厚度>2.5×T 且離散>30，牆/柱不會又超厚又有紋理）即刪。20 張逐矩形統計：假牆刪 ~87%、真牆誤刪 0.09%（面積加權）
- 混合塊回收：被「色度」規則刪的候選常是「牆+相鄰木地板」黏成一個 bbox（floor_05），整塊刪會虧牆——把其中牆樣像素（灰度≤ref+25 且像素色度≤12）重新抽成矩形救回，只收牆厚條（≤2.5T）；灰度/超厚規則刪的不回收（中性灰紋理塊的暗像素會原樣通過像素條件，回收＝白刪）

三、split_pillars() 基柱改貼形切割（新 _split_blob()）：L 形/凹形黑塊用單一 bbox 輸出會把空隙全變假牆（floor_18 底部塊 fill=0.46，整圖精準率卡在 66.7%）。KD 式遞迴：先縮緊 bbox，fill≥0.8 就收，否則沿長邊在像素數最少處切開兩半各自遞迴。floor_18 精準率 66.7%→83.8%、floor_09 →84.1%、floor_15 →87.6%

四、20 張全量成績：精準率 79.1%→87.0%、召回率 95.2%→94.7%、IoU 76.0%→82.9%。另實驗過「矩形四邊內縮」換精準率（+2.8pp/內縮1px）但召回掉更多（−4.1pp）、IoU 淨虧，不採用；剩餘失分主因是預測牆比標註厚一圈的邊緣暈帶，屬標註容差範圍

2026/7/14 v.2.2 變更（彩色管線改走「先抓牆」策略 + 牆體評分基準 + 兩管線徹底分離）

一、兩管線輸出與設定徹底分離，取消 px 單位 DXF：

- floorplan2dxf.py 取消 dxf/ 目錄：px 單位 DXF 與 cm 單位的 dxf_scale/ 幾何相同只差比例，留一份就夠。唯一 DXF 輸出＝dxf_scale/（門寬推比例、公分、$INSUNITS=5），批次預設 png/ → dxf_scale/ + chk/；json/ 的 "dxf" 欄位移除（前端請改讀 "dxf_scale"）
- floorplan2dxf_color.py 同樣取消 color_dxf/，輸出只剩 color_dxf_scale/ + color_chk/
- 設定檔分離：彩色管線預設讀 config_color.ini（新增），黑白管線維持 config.ini——兩邊調參互不影響（本次分離的主要動機：接下來要單獨調彩色的辨識度）

二、彩色管線（floorplan2dxf_color.py）改走「先把牆抓穩」策略：

- 門/窗/空間標籤（客廳/陽台/房間）/門位框判斷全部停用（函式保留，牆穩了再逐步接回）；color_json/ color_arch/ 暫停輸出。現階段輸出＝牆矩形（含建築基柱）的 DXF + 疊圖
- 前處理 color_to_bw() 重寫「淡化 5 層次」：彩色 → 灰階 → P1~P99 百分位拉伸（min-max 會被單一噪點毀掉；褪色掃描圖牆灰值 87~131 也能拉回深層）→ 亮度等分 5 層(0=最深) → 保留最深 2 層「且」絕對色度 <40 的像素當牆。色度＝max(B,G,R)−min(B,G,R)：黑/灰牆三通道相近(色度 6~9)，深紫棉被/綠草皮等深色彩色家具色度高；HSV 飽和度在近黑像素會被 JPEG 噪點撐爆(實測黑牆 S=86~150)不可用。灰色沙發等灰家具比牆淺 1~2 層，由層次門檻擋掉（floor_05 實測沙發正規化後在第 3 層）。參數 fade_levels/fade_keep/chroma_max 皆在 config_color.ini
- 建築基柱（>2×牆厚的黑色實心方塊）改為 100% 保留當牆輸出——後端要拿去生成 3D 空間。split_pillars() 取代舊 remove_pillars()：厚實心塊一樣用「距離變換粗核心＋測地膨脹」找，但找到後不再丟棄，先從 bw 切出（避免柱貼牆時把 detect_solid 的 bbox 撐爆成大面積假牆）再以自身 bbox 回填進牆矩形清單；remove_solid_blobs 的大實心塊移除也一併取消（黑色實心務必全留）
- 偵測流程抽成 detect_walls() 供 run() 與評分腳本共用，調參時評分與正式輸出零漂移

三、新增牆體評分 eval_color_walls.py + 答案集 color_pngans/（起步 3 張，持續擴充）：

- 答案格式：在原圖（或管線的 2 倍放大圖）上用純色 RGB(136,0,21) 實心塗出牆＋基柱；腳本以 ±40 容差抽取遮罩，ans 與處理尺寸不同時自動縮放
- 指標＝像素級精準率/召回率/IoU；`--vis` 輸出差異圖到 color_chk/eval_*.png（白=抓對、紅=多抓、綠=漏抓）
- 首次基準（3 張）：精準率 84.3%、召回率 96.1%、IoU 81.5%——牆幾乎不漏，主要失分是家具邊緣/盆栽等小塊假牆，為後續調參方向

2026/7/13 v.2.1 變更（主程式窗偵測調校 + 彩色實驗版改名隔離）

一、floorplan2dxf_test.py 改名 floorplan2dxf_color.py，輸出完全隔離：

- 預設批次 `python3 floorplan2dxf_color.py`＝color_png/ → color_dxf/ + color_chk/ + color_dxf_scale/ + color_json/ + color_arch/，與主程式的 dxf/ chk/ dxf_scale/ json/ arch/ 徹底分開，不再互相覆蓋（v2.0 時兩管線共用輸出目錄，color_floor 系列會蓋掉主管線結果）
- 共用目錄裡殘留的 color_floor_* 舊輸出已清除；color_floor 題目圖已移到 color_png/
- 邏輯與 v2.0 相同，僅路徑改變；批次實測 20/20 成功

二、主程式 floorplan2dxf.py 窗偵測調校（pngans 人工答案評分，eval_windows.py；
調校用 46 張，後刪除 2 張錯誤答案＝44 張）：

| 指標 | 調校前（46張） | 調校後（44張） |
| ---- | ------ | ------ |
| 精準率 | 92%（誤抓 14） | **99%（誤抓 1）** |
| 召回率 | 91%（漏抓 16） | **94%（漏抓 9）** |
| 門樣式過濾（eval_doors.py） | 19/19 | 19/19（無回歸） |

失敗案例逐一調試後的修正（全部先在沙盒對 46 張迭代驗證再合入）：

- 門備援檢查 _has_door_swing 的門尺寸基準改用「可靠牆厚 wall_t」推導——原本用全圖最厚線 T，被樓梯/實心塊撐大 2~3 倍時正常寬度的門洞被排除在檢查外（floor13/34/35 的閉合門扇 8 例全因此被當成窗）；鉸鏈位置加試牆面偏移（門軸釘在牆面不在牆中線）與 ±0.25s 細格點；半徑加試 1.2 倍（蝕刻讓開口比門寬窄）
- 新增 _arc_crisp 弧「孤立性」檢查：真門弧是細曲線（半徑上有墨、內外圈留白），牆緣蝕刻殘影/家具墨團拼出的假弧內外圈都有墨——配合上述放寬不誤殺窗（floor74 左緣窗曾被牆緣假弧殺掉，此檢查救回）
- 寬開口（≥4 倍牆厚）加試「一端鉸鏈＋半寬弧」＝門+固定扇共用開口（floor20/30 的 1.9m 開口）；開口帶有 ≥2 條貫穿玻璃線時不啟用此殺法，保護寬窗
- 新增 wall_through：開口中段被垂直向牆穿過/抵住（T 字口）＝門洞/通道，整段否決（窗玻璃不可能有牆插在中間；floor13 雙開門 T 字口）
- _near_door 放寬：門分數 0.85→0.8、門寬下限 0.65→0.55×開口，錨點加開口帶側面中點（緊容差 0.5×牆厚，只殺門軸貼著帶緣的橫閂門，floor35）
- strict/scan_extra 補找路徑：貼緣檢查加「pad 加寬帶」變體（窗符號常比蝕刻後的牆帶寬，floor02 陽台窗）；帶被影像邊界裁到時貼緣門檻放寬（floor74 右緣窗）；新增子段搜尋（大開口裡只有一段有窗符號，要求 ≥3 條貫穿線＋至少一端貼牆垛；兩端都貼牆垛時子段可近滿版）；「每行 ≥2 條線」輪廓切分 runs（閉合門扇單線會把子段橋接成整段，floor03 門廊窗）
- 推斷牆線的 dedup 容差改用 max(牆厚, 0.45T)——T 被撐大時貼邊的細線窗牆會被既有線吃掉（floor35）

已知剩餘問題（9 漏抓 / 1 誤抓）：

- 題目有 7 組像素級相同的重複圖（floor10=38、12=49、14=61、16=46、18=54、19=60、20=30）。其中 floor10、floor14 的答案與其重複對答案矛盾，確認標錯後已刪除（2026/7/13）——floor10/floor14 題目仍在但不計分，以 floor38/floor61 的答案為準
- floor24 斜角窗 ×2：正交管線（只輸出水平/垂直）先天不支援
- floor08 ×2：細線畫風整圖牆偵測失敗（v1.7 已知，建議走 CubiCasa fallback）
- floor03 浴室窗：緊鄰淋浴間曲線恰好構成 0.93 分完整弧被殺；floor07 高窗：緊鄰的真門弧半徑恰等於窗高（floor38 同款開口答案就標門）——兩例屬圖面歧義
- floor13 T 字口雙開門誤抓 1 例：門弧掃遍參數格點皆 <0.8，暫無安全判據

2026/7/12 v.2.0 變更（實驗版：floorplan2dxf_test.py → v2.1 起改名 floorplan2dxf_color.py，主程式 floorplan2dxf.py 完全不動）

彩色渲染圖（color_floor_* 系列）支援：先二值化變黑白再辨識＋柱過濾＋門位框上限：

- 彩色圖判定：檔名含 color（此系列命名慣例）或彩色比例 >8% 觸發，淡彩圖不會漏
- 二值化預處理 color_to_bw()：「暗(V<140)＋低飽和(S<110)＝牆」的 HSV 萃取，彩色家具/地板/磁磚全部變白——直接灰階+Otsu 會把整片色塊當牆（v1.9 前彩色圖成功率幾乎為 0 的主因）。門檻經 10 張×3 組參數掃描選定；小於 1200px 的圖再放大 2 倍（牆線僅 4~6px，去雜訊開運算會吃掉）
- 柱過濾 remove_pillars()：彩色圖含房屋柱（黑色實心正方/長方塊），要先過濾掉再找牆——柱貼著牆時原本 remove_solid_blobs 的緊湊度判斷會失效（柱+牆連成一個細長大元件），改用「局部厚度遠大於牆厚(>1.6T)的粗核心＋測地膨脹還原柱身」偵測後移除
- 牆厚 T 估計改用距離變換「脊線」P90×2：原本的 dt.max() 會被黑色角柱撐爆（彩色圖 T 估到 56~102px 直接全毀），脊線高百分位對柱穩健；黑白圖的 T 也變準（floor03 舊 20→新 12，實際牆厚就是 12px，臥室誤標廚房與無門警告一併消除）
- 門位黃框品質排序＋上限：房間↔房間 > 房間↔室外(大門) > 房間↔走道，同級比門偵測分數；同一門洞的重疊框去重只留最好的；彩色圖經驗上限 6 扇（黑白圖不設限）——修正 v1.9 在彩色圖上黃框大量誤標的問題

批次實測 20 張 color_floor：從全滅（牆 0 塊、分割 0 張）進步到 20 張全部抓到牆、8 張完成空間分割、黃框全部 ≤6 個（color_floor_08 可分出客廳/臥室/浴廁＋6 門位）。黑白 floor 系列無回歸。已知限制：手繪牆線不完全水平垂直＋部分內牆藏在家具陰影裡，長核形態學偵測本質吃虧，分割/標籤仍不精準——要再上一個檔次建議走 v1.7 的 CubiCasa5k fallback 抓牆，再接 v1.9 的空間分割流程。

2026/7/12 v.1.9 變更（實驗版：floorplan2dxf_test.py，主程式 floorplan2dxf.py 完全不動）

辨識時同步輸出空間使用標籤（客廳/廚房/臥室/浴廁/陽台）＋門位黃框＋連通檢查（dxf/ 不動；chk/、json/、arch/、dxf_scale/ 新增欄位/圖層）。因整體成功率仍不足（詳下方已知限制），先以 floorplan2dxf_test.py 獨立存放測試，用法相同：`python3 floorplan2dxf_test.py png dxf`：

- 空間分割 segment_rooms()：把每道牆當實心方塊畫遮罩 → 牆縫開口「精準封口」（_wall_gaps 牆端沿軸射線找對面牆，40~260cm 空縫含落地窗滑門；不靠大核閉運算——大核會把窄房間/走道整個填掉）→ 貼牆的門弧也沿牆封回 → 影像邊界灌水分內外 → 室內扣牆的連通塊＝一間間空間。封口核 1.5/2.5/3.5/4.5×T 全跑完取「覆蓋率最高、覆蓋相近時分割較細且核較小」的輪次；覆蓋 <30% 或涵蓋不足牆 bbox 55% 視為殼漏水，全失敗則誠實不輸出
- 空間分類 classify_rooms()（依規則）：最大＝客廳；<1.8m²＝走道/玄關（中性「空間」）；貼外圍＋細長(長寬比≥2.3)＋設備線稀疏＝陽台；≤5.5m²＝浴廁；≤8m² 且設備線密度（細線圖，爐台/水槽線多）高於中位數＝廚房，沒有候選＝開放式廚房併入客廳；其餘居中尺寸（多近正方）＝臥室
- 門位黃框：沿牆長＝門寬(1)、垂直牆前後各一個門寬＝1:2 框。候選＝門弧（分數≥0.55、寬40~150cm、中心不在牆體內）＋牆縫開口（40~150cm），再用房間圖幾何驗證：門兩側「逐步走、撞牆就停」取樣，要能不穿牆走到兩個不同空間（或空間↔室外/走道）才是真門——爐台/水槽假弧（v1.6 已知問題）、天花圓形符號全數剔除
- 連通檢查（規則：以客廳為中心到每間都該有門）：真門建房間相鄰圖 → 客廳 BFS；沒有任何門的空間＝有問題 → chk/ 紅框＋「！無門」、json/ has_door=false 供人工檢視
- 輸出：chk/ 房間依標籤上色（客廳綠/臥室藍/浴廁青/廚房橘/陽台紫）＋中文房名與 m²（PIL＋微軟正黑，無字型退英文）＋門位黃框；json/ 新增 rooms[]（label/面積/長寬比/px+cm bbox/has_door/reachable_from_living）與 door_zones[]（px+cm 四角）；arch/ 新增 rooms[]（含 polygon，選填欄位、schema 相容）；dxf_scale/ 新增 DOORZONE 圖層（黃色 1:2 框）
- 依賴新增 Pillow（僅預覽圖畫中文用）

批次實測 66 張全過無例外：floor 系列 43/46 成功分割（floor02/08/17 殼封不住留空，floor08 為 v1.5 已知牆偵測失敗案例），共 156 處門位框。floor01 對照：7 間空間、6 扇門位全真、開放式廚房正確併入客廳、無門警告 0（v1.6 詬病的爐台/水槽假門全被幾何驗證擋掉）。已知限制：CLOSET/樓梯間會被當浴廁/臥室（無語意辨識）、>5.5m² 的大浴室會被當臥室、密集家具線的臥室偶被當廚房（floor03，v2.0 已修）；門位品質仍受弧偵測影響，但幾何驗證已擋掉絕大多數假門；彩色渲染圖此版尚不支援（v2.0 補上）。

2026/7/9 v.1.7 變更

CubiCasa5k 比對實驗 + 失敗案例 fallback 目錄（業界基準，主管線完全不動）：

- 新增樣本 60 張（floor22~81，批次全跑成功
- 用 pngans/ 21 張人工答案比分（score_compare.py，牆=像素級 F1 ±3px 容差、窗=綠框配對同 eval_windows 規則）：
- | 指標                                  | 我們的 CV 管線 | CubiCasa5k     |
  | ------------------------------------- | -------------- | -------------- |
  | 牆 F1（像素級，±3px 容差）           | **0.94** | 0.87           |
  | 窗 F1（框配對，同 eval_windows 規則） | **0.84** | 0.81           |
  | floor08（失敗案例）                   | 0.00           | **0.87** |

在乾淨 CAD 風格的圖上，原程式調的管線整體還是比較準（牆矩形貼合緊、窗規則精細）， **但兩者剛好互補** ——floor08 偵測不足的圖，CubiCasa 牆體幾乎完整抓出；新樣本裡們只偵測到 5 塊牆的 floor50、floor75，它也都完整辨識。目前策略： **不取代，當 fallback** 。

已知限制：CubiCasa 輸出是 mask 不是向量，要接進 dxf/arch 管線還需要 mask→矩形/線段的後處理（未做）；它的比例尺資訊也要另外推

2026/7/9 v.1.6 變更

新增 arch/ 白模交接輸出（architecture.json schema，dxf/、dxf_scale/、json/ 完全不動）：

- 每張圖多輸出 arch/同檔名.json，格式照 3D 白模端定義的 architecture.json schema：units 一律 cm、座標原點左下 y 向上（同 dxf_scale/）。walls＝中心點 position + rotation(0/90) + width(長)/thickness(厚)/height；windows 多 sill_height 與 host_wall；doors 多 rotation(門面法線，指向開門側)、hinge(站在開門側面對門，鉸鏈在左/右)、swing_in、host_wall
- detect_doors 回傳多帶 L 形兩自由端方向 (ux, vy)——判門面法線與鉸鏈左右要用，之前算完就丟。json/ 的輸出格式不變
- host_wall 純幾何比對：窗找同方向、跨牆重疊、沿軸最貼近的牆；門找鉸鏈最近的牆（距離 ≤3T 才掛）
- arch/ 的門只收弧吻合 ≥0.85 且換算門寬 50~250cm 的（json/ 仍保留全部門帶 score 供除錯）——高分小弧多是櫃門/雙開門半扇，876cm 的假門也被擋掉
- room_polygon（房間可用區域外框，白模端做 within-room 驗證用）：牆+窗+已偵測門洞畫成遮罩 → 膨脹封住沒偵測到的門洞 → 從影像邊界灌水找封閉區 → 同核侵蝕還原邊界 → 內縮外圍牆厚＝內緣。驗收檢查做在內縮後的最大連通塊（面積 ≥25% 牆bbox、寬高涵蓋 ≥55%），漏水就放大封口核（1.5T→2.5T→3.5T）重試，仍封不住就整個欄位不輸出（schema 裡是選填），不給錯的
- 立面資訊平面圖上沒有：牆高/窗高/窗台高用 config 新增的 [arch] 預設值（280/120/90cm）

批次實測 21 張：schema 驗證全過；room_polygon 17 張成功（floor05/08/15/17 外殼有大開口——露臺落地窗、牆偵測失敗——封不住，誠實留空）；高信心門 21 扇（host_wall 20、swing_in 16）。已知問題：detect_doors 仍會把爐台/水槽的弧線當門（floor01 的 2 扇都是假門），門的品質受限於原本的弧偵測，待改進。

2026/7/8 v.1.5 變更

比例尺改用外圍牆厚錨定（外牆必定 ≥15cm），門寬不再決定比例：

- 門寬推比例有系統性偏差——拿有印刷尺寸的圖驗證，floor01（標 30'）、floor03（房間標 3.0M×3.0M）、floor05 的門推比例都偏大 1.3~2 倍（弧偵測抓到家具/小弧拼成的假門，門寬 px 中位數偏小）。門寬改為只做交叉檢核，不再回推比例
- 新增 outer_wall_thickness()：只取「貼著平面圖外框、且沿外框方向延伸」的牆矩形，短邊中位數 = 外圍牆厚（px）。排除室內牆（端點碰到外框不算）與厚度 <0.35×T 的細長條（標註/尺寸線），量不到就退回 T
- derive_door_scale() 改版：比例以 config 的 mm_per_px 為基準，若外圍牆厚換算 <15cm 就把比例撐到剛好 15cm（method: wall_min）；≥15cm 則維持 config 比例（method: config）
- confidence 改為門寬交叉檢核結果：偵測門寬換算落在 70~110cm → high，偏離 → low（比例或門偵測至少一個有問題，值得人工看），沒偵測到門 → medium
- json/ scale 區塊欄位更新：outer_wall_px、outer_wall_cm、wall_min_cm、median_door_cm（取代原本的 median_door_px / wall_thickness_cm）

批次實測 21 張（對照圖面印刷尺寸）：floor01 高 30'=9.1m，舊輸出 13.2m → 新 10.0m；floor03 約 6.5×9m，舊 13.7×15.3m → 新 7.3×9.4m；floor05 約 9m 寬，舊 12.1m → 新 9.4m。已知問題：floor08 牆偵測本身幾乎失敗（只偵測到 2 個牆矩形），比例仍偏大（圖標 20'×30'=6.1×9.1m，輸出 12.2×17.4m），已標 low，需另調牆偵測參數。注意 wall_min 是下限錨點——實際外牆比 15cm 厚的圖，輸出尺寸會略小於真實（有印刷尺寸可對照的圖誤差皆在 10% 內）。

2026/7/7 v.1.4 變更

門寬推比例尺 + 前端交接 JSON（原本的 dxf/ 輸出完全不動）：

- derive_door_scale()：取弧吻合度 ≥0.85 的高信心門，門寬 px 中位數 = door_width_cm（config 可調，預設 90cm）反推每張圖的比例；推出的比例要通過牆厚合理性檢查（最厚外牆 8~40cm）才採用，否則退回 config 的 mm_per_px 並標 confidence: low/none
- dxf_scale/：每張圖另存一份門寬比例的 DXF，單位公分（$INSUNITS=5），幾何與 dxf/ 相同只有比例不同
- json/：每張圖一份前端交接 JSON——scale 區塊（cm_per_px、method、confidence、doors_used、推算牆厚），walls/windows/doors 同時給 px（影像座標）與 cm（同 dxf_scale，原點左下 y 向上）兩套座標

批次實測 21 張：10 張門推比例（全標 high），2 張假門被牆厚檢查正確擋掉，9 張沒抓到高信心門走 fallback。後續改進方向：把閉合門扇（_has_door_swing 抓到的）也納入比例計算，提高門推比例的覆蓋率。

2026/7/6 v.1.3 變更

- floorplan2dxf.py:925 新增 IMG_EXTS = (".png", ".jpg", ".jpeg", ".bmp")，run_batch 改成列出目錄後用副檔名（不分大小寫）過濾，所以 .JPG、.PNG 這種大寫也抓得到

提醒：批次輸出是以檔名（去掉副檔名）命名，如果目錄裡同時有 floor01.png 和 floor01.jpg，兩者的 DXF 會互相覆蓋，只留最後處理的那張。

2026/7/3 v.1.2 變更

新增/door 目錄置門的種類放篩選圖型，雙開門、上下左右往兩邊打開圖型type分類

門過濾率從 95% 提升到 100%（19/19 全過），同時窗戶精準率再往上推。

成果
門過濾率（door/ 19 張樣式）	94.7%（18/19）	100%（19/19）
窗戶精準率	89%	93%
窗戶召回率	91%	90%
牆偵測	—	完全沒動，不受影響

2026/7/2 v.1.0 變更

成果
抓對 誤抓 漏抓 精準率 召回率
修改前 68 23 18 75%	79%
修改後 78 10 8 89% 91%

長窗上限從 15 倍牆厚放寬到 25 倍（floor05、floor12 的長窗）
玻璃線畫成淺灰色時 Otsu 二值化會把它消掉——加了寬鬆門檻的備援檢測，但要求「至少兩群分開的貫穿線＋墨跡比例低」才算窗，擋掉檯面邊線和樓梯
「開口附近有門就不算窗」改嚴：門的鉸鏈必須貼在開口端點、門寬要吻合、且門本身的弧線吻合度要夠高——之前淋浴間的曲線拼出假門，把好幾個真窗誤殺了
新增「開闔弧線」備援門檢查：閉合畫法的門扇（雙細線躺在牆上）以前全被當成窗，現在拿開口兩端當鉸鏈掃弧線，含雙開門（兩端各半弧）；門檻鎖 0.9，實測真門≈1.0、真窗≤0.6
推拉門的兩片線各只蓋半長——加「至少一條線貫穿開口全長」的結構檢查
整條被細線畫的牆（floor16 下牆那種）以前連牆帶窗整段消失——現在用對齊的牆角推斷缺失牆線、垂直牆當虛擬夾邊，配最嚴格的結構檢查找回來

Todos：

寫 eval_windows.py 比對腳本（抽取綠框、配對、算 TP/FP/FN）
用現行代碼建立基準分數（20 張全跑）
分析誤判/漏抓案例，修正 detect_windows
迭代到 20 張整體精準率/召回率都改善
重新產生 chk/ 與 dxf/ 並回報結果

格式：檔案總管圖片上的紅色＝牆、綠色框＝窗戶正確位置。
