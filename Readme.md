2026/7/22 v.2.14 變更（目錄重整：Identify_ans/ 人工答案集中、training/ 本機自管不 push；own_wip 撈回 5 題；own 量尺房型 10 類定案）

一、Identify_ans/——人工答案總目錄（進版控）：

- 集中四區：`pngans/`（牆窗像素答案 gray 21＋color 28）、`own_dataset/`（26 題微調訓練＋門位 GT）、`own_eval/`（12 題房型保留評分集，永不進訓練）、`own_wip/`（未完成標注）
- own_wip 撈回：40ec85e「43→26 精選」剔除的並非淘汰而是未改完——其中 12 題（floor55~79）已於 v2.13 轉生 own_eval 不回收，真正懸置的 **floor17/24/30/34/46 共 5 題**自 git 歷史還原。工序：Inkscape 改完 → 搬入 own_dataset/ → 補 own_train/val 清單（26→31 題）
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
