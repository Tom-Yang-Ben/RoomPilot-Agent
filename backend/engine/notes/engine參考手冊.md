> **非正式參考手冊**。正式規格見 `../README.md` 與 `../room_strategy/README.md`。
> 本檔用白話寫，術語一律附解釋。

# Engine 參考手冊（查數字用）

> **這本放「不太會變的東西」**：淨空數字、資料庫事實、環境怎麼建、踩過哪些坑。
> 想知道「現在做到哪、還沒做什麼」請看 [`engine工作總帳.md`](engine工作總帳.md)。
>
> 由 2026-07-29 ～ 08-01 的五份每日筆記彙整而成（2026-08-01），原始日記已刪除，
> 內容全數併入本檔與工作總帳；需要原始脈絡時查 git 歷史。

## 目錄

1. [淨空欄位定義](#1-淨空欄位定義v12)
2. [全類型淨空對照表](#2-全類型淨空對照表)
3. [八項拍板與理由](#3-八項拍板2026-07-29與理由)
4. [資料庫事實](#4-資料庫事實)
5. [環境重建](#5-環境重建每台機器都要做一次)
6. [驗證指令](#6-驗證指令)
7. [踩過的坑](#7-踩過的坑)
8. [已解除的疑慮](#8-已解除的疑慮別再當成問題)
9. **[2D／3D 擺放程式碼地圖（改引擎前必查）](#9-2d3d-擺放程式碼地圖改引擎前必查)**

---

## 1. 淨空欄位定義（v1.2）

每件家具（或每個類型預設）可宣告 0 到多個淨空區：

```jsonc
"clearance_zones": [
  {
    "side": "front",      // front | back | left | right
                           // 以家具「未旋轉時」自身方向為準，front = +Y
    "kind": "operation",  // operation = 硬性（門／抽屜打不開 = 違規擋下）
                           // access    = 軟性（使用舒適；違反時警告／扣分，不擋）
    "ideal_cm": 90,       // 理想保留深度：優先嘗試
    "floor_cm": 50,       // 底線保留深度：理想放不下時退到這裡，結果標
                           // "clearance_compressed"；低於底線 = 違規（僅 operation）
    "reason": "門扇開啟"   // 給 agent／使用者轉述的中文原因
  }
]
```

### 名詞白話翻譯

| 詞 | 白話 |
|---|---|
| `type`／`normalized_type` | 家具在系統內的種類名稱。例如 `chests-of-drawer` 就是「抽屜櫃」 |
| `FAMILY_OF` | 把很多詳細種類合併成大類的對照表（布沙發、皮沙發都併成「沙發類」）。適合安排擺放順序，**不適合直接決定開門或抽屜要多少空間** |
| `operation` | 家具真的要操作的空間。例如開衣櫃門、拉抽屜；不夠就不能擺 |
| `access` | 人使用家具時比較舒服的空間。例如站著拿書、把椅子拉開；不夠時先警告，不直接禁止 |
| `zone` | 家具周圍需要保留的範圍 |
| `companion` | 配套家具。例如書桌與辦公椅、餐桌與餐椅、沙發與茶几 |

### 六個設計要點

1. **理想／最低兩個數字**——先保留理想空間；房間太小時可以縮到最低值並標記「空間較擠」。真正開門、拉抽屜的空間低於最低值才算不能擺。
2. **必要空間／舒適空間分開**——門片或抽屜打不開就擋下；只是拿東西、入座不方便則提醒或扣分。
3. **空陣列／無欄位 = 無淨空需求。**
4. **優先順序**：RAG 對某一件家具指定數字 → 用該數字；否則用類型預設；兩者都沒有就不設淨空。
5. **怎麼判斷家具種類**：直接看家具原本的詳細種類。抽屜櫃就查抽屜櫃的規則，不要先併成餐邊櫃，否則會套到錯誤的數字。
6. **配套家具**：書桌前方需要使用空間，但辦公椅本來就該放在這裡，所以配套椅可以進入桌子的「舒適使用空間」；但仍然**不能**擋住衣櫃門、抽屜等必須能開啟的地方。實作順序是先讓引擎知道「哪兩件是一組」，再啟用舒適空間檢查。

> ⚠️ 2026-08-01 補充：這個 `companion_pairs` 機制早就寫好，但直到擺放策略層才第一次被啟用。
> 沒有它，床頭櫃會被判成「侵入床側的舒適空間」而擺不下。

---

## 2. 全類型淨空對照表

「面」欄以家具自身方向為準。程式實作在 [`../clearance_defaults.py`](../clearance_defaults.py)。

### A. 必須保留的開啟空間（不合格會被擋下）

| # | 族群 | normalized_type | 中文分類（筆數） | 面 | 理想 | 底線 | 說明 |
|---|---|---|---|---|---|---|---|
| 1 | 衣櫃族 | `wardrobe`, `pax-wardrobe`, `cabinet-cupboard`, `storage-solution-system` | 衣櫃(75)、PAX 衣櫃(75)、櫃體(149)、收納系統(69) | front | 90 | **50** | 門扇全開＋站立取物。底線維持 50（草案曾寫 60，為小房可行性改回），避免 240×240 級小臥室床＋衣櫃無解。資料無法分開門／推拉，一律當開門保守 |
| 2 | 抽屜櫃 | `chests-of-drawer` | 抽屜櫃(130) | front | 90 | 60 | 抽屜全拉出＋彎身 |
| 3 | 餐邊櫃 | `sideboard` | 餐邊櫃(46) | front | 90 | 60 | 門＋抽屜 |
| 4 | 電視櫃 | `tv-bench`, `tv-media-furniture` | 電視櫃(49)、電視與影音家具(10) | front | 60 | 45 | 只算門片／抽屜；觀看距離歸電視牆規則，不用淨空 |
| 5 | 展示櫃 | `display-cabinet` | 展示櫃(37) | front | 60 | 45 | 玻璃門 |
| 6 | 鞋櫃 | `shoe-cabinet` | 鞋櫃(9) | front | 75 | 50 | 翻斗門斜開 |
| 7 | 鏡櫃 | `mirror-cabinet` | 鏡櫃(24) | front | 60 | 45 | 鏡門 |
| 8 | 泛用收納 | `storage-furniture` | 收納家具(20) | front | 60 | 45 | 籠統分類，保守當有門 |

### B. 使用起來較舒服的空間（記錄／警告，不禁止擺放）

| # | 族群 | normalized_type | 中文分類（筆數） | 面 | 理想 | 底線 | 說明 |
|---|---|---|---|---|---|---|---|
| 9 | 開放書櫃／層架 | `bookcase`, `shelving-unit` | 書櫃(231)、層架(79) | front | 75 | 40 | 取物舒適非機構 |
| 10 | 書桌 | `desk` | 書桌(662) | front | 105 | 75 | 椅子拉出＋入座。必須先讓引擎知道辦公椅是書桌的配套家具 |
| 11 | 餐桌族 | `dining-table`, `table`, `bar-table` | 餐桌(137)、桌子(23)、吧檯桌(17) | 四面 | 75／面 | 60／面 | 呼叫端宣告哪幾面有椅；餐椅可進入餐桌的舒適使用空間 |
| 12 | 床族 | `bed`, `bed-frame`, `mattress`（**不含 `sofa-bed`**） | 床(81)、床墊(17) | 兩長側 | 75／側 | 單側 60 | 「左右至少留一側」。床尾不算側。沙發床當沙發處理 |
| 13 | 衣帽架 | `clothes-rack` | 衣帽架(26) | front | 45 | 30 | 取掛衣物 |
| 14 | 沙發族 | `fabric-sofa`, `leather-sofa`, `modular-sofa`, `sofa`, `armchair`, `sofa-bed` | 布沙發、皮沙發、沙發、模組沙發、扶手椅、沙發床 | — | — | — | **刻意不設淨空**。前方是茶几的**關係**，不是淨空 |

### C. 無淨空需求（刻意，不是漏掉）

| 族群 | normalized_type | 理由 |
|---|---|---|
| 椅凳全系 | `dining-chair`, `office-chair`, `gaming-chair`, `stool-bench`… | 是桌子的配套家具；所需空間由桌子的舒適使用空間與走道規則處理 |
| 小桌附件 | `coffee-table`, `bedside-table` | 距離由關係約束管 |
| 地毯全系 | `large-medium-rug`, `runner-small-rug`, `rug`… | floor_overlay，允許被壓 |
| 壁掛層架 | `wall-shelf` | wall 層；歸堆疊層 |
| 燈具／裝飾／隔間／兒童其他 | — | 無機構或屬動線／堆疊 |

> ⚠️ **不要因為件數多就去補沙發／椅凳／地毯的淨空**，那會推翻 2026-07-29 的設計決定。
> 覆蓋率低是刻意的：無規則的 6,138 件裡約 5,100 件屬於本表 C 與 B-14。

### D. 真正漏掉的（約 300 件，可考慮補）

| 類型 | 件數 | 為何當初沒收 |
|---|---|---|
| **`bedside-table`** | **54** | 規格表把它歸「距離由關係約束管」，但關係約束一直沒做，等於完全沒規則 |
| `room-divider` 屏風 | 17 | 會擋動線，規格表當初沒收 |
| `mirror` + `large-mirror` | 92 | 浴室唯一能放的東西；`mirror-cabinet` 有規則但 `mirror` 沒有 |
| `childrens-*` 四類 | 87 | 2026-07-31 才決定次臥開 `kids_room` 池，寫規格時還沒這決定 |

### E. 死鍵（引擎有規則，資料庫沒這分類）

```
❌ bed-frame          資料庫裡床只叫 bed（110 件）
❌ cabinets-cupboard  資料庫裡叫 cabinet-cupboard（少一個 s，146 件）
```

**這兩條規則永遠不會被命中。** 更麻煩的是 `backend/server/scene_service.py` 的別名表**正在使用這兩個死名字**：

```
:124  "床架"   → "bed-frame"          → 撈到 0 件
:132  "收納櫃" → "cabinets-cupboard"  → 撈到 0 件
```

使用者在問卷打「床架」或「收納櫃」，系統**安靜回 0 件不報錯**。
👉 清死鍵**不能只動 engine**，別名表在 Bella 那邊。

---

## 3. 八項拍板（2026-07-29）與理由

全部已勾選確認，引擎已實作：

- [x] **衣櫃前方最低留 50 公分**：空間夠時盡量留 90，小房間最少 50，不採用原草案的 60。
- [x] **書櫃、書桌空間不足先提醒，不直接禁止**：影響舒適度，但不等於家具不能用。
- [x] **沙發與沙發床前方不強制留空**：前方通常要放茶几，距離改由關係規則處理。
- [x] **每種家具使用自己的詳細規則**：抽屜櫃就查抽屜櫃，不先併成餐邊櫃；沙發床明確當沙發處理。
- [x] **配套家具可以放進舒適使用空間，但不能擋門或抽屜**。
- [x] **無法分辨普通門與推拉門時，先按需要較多空間的普通門計算**。
- [x] **鏡櫃、屏風、兒童家具的系統內部代碼已確認**（見下）。
- [x] **餐桌四周與床兩側的進階規則**：後續已於 v1.3 完成。

### 為什麼這樣定（給審查用）

1. **衣櫃 50 不是退縮**：理想仍 90；底線跟現行對齊，避免規格一啟用小房全滅。
2. **軟硬分開**：門打不開是安全／功能問題；取書／入座是舒適問題——不該同一把刀砍。
3. **沙發不設淨空**：茶几本來就該在沙發前；用關係約束比用淨空正確。
4. **每種家具查自己的規則**：合併大類只適合安排擺放順序，不代表抽屜或門片需要相同空間。
5. **先讓引擎認得配套家具**：否則啟用書桌的舒適空間後，會得到「椅子不能放在桌前」的荒謬結果。

### 已確認的系統代碼

正式代碼在 `scripts/sql/roompilot_type_category_mapping.csv`（**不是** `家具大分類_小分類統計.csv`，那份只有中英文分類名）：

| 中文 | 代碼 |
|---|---|
| 鏡櫃 | `mirror-cabinet` |
| 屏風與隔間 | `room-divider` |
| 兒童椅與凳子 | `kids-chairs-stools`（別名 `kids-chairs-stool`） |
| 兒童桌 | `childrens-table` |
| 兒童家具 | `childrens-furniture` |
| 兒童凳子與長凳 | `childrens-stools-bench` |

---

## 4. 資料庫事實

以 2026-07-31 建置的定版資料庫實測。**Ancai 已確認資料庫定版不再增加。**

### 4.1 規模

| 項目 | 數量 |
|---|---|
| 家具 | 8,557 筆（8,557 個 GLB、25,671 張三視角圖） |
| 向量 | 7,958 筆 BGE-M3，1024 維 / cosine / normalized |
| 分類 | 55 個 `category_code` |
| 資產缺口 | **零**。7,958 件全部有 GLB ＋ front/side/angle-45 三視角圖 |

### 4.2 各槽位候選數

```
desk 527 | sofa 490 | dining-chair 411 | office-chair 175 | dining-table 133
bed 110 | shelving-unit 80 | wardrobe 72 | pax-wardrobe 72 | tv-bench 56
bedside-table 54 | storage-furniture 20 | shoe-cabinet 5  ← 唯一警訊
```

### 4.3 房間碼只有 9 個，跟 12 房型策略對不上

```
living_room 6108 | bedroom 4380 | dining_room 3057 | entryway 2077
study 1787 | kids_room 779 | outdoor 236 | bathroom 79 | kitchen 70
```

- **沒有** `storage`、`multifunction`、`hallway`
- `outdoor`(236) = 植栽 235 + 戶外地毯 1，**戶外桌椅一件都沒有**
- `shoe-cabinet` 全庫只有 5 件，且**一件都沒掛 `entryway` 標籤**
- 廚房 70 = `wall-shelf` 53 + `bar-table` 17；浴室 79 = `mirror` 61 + `mirror-cabinet` 17 + 1 件錯分的沙發

👉 這就是 v1 規格「**房間標籤只當加分，不當硬過濾**」那條的由來。硬過濾會讓儲藏室、玄關、多功能室直接回傳零件。

### 4.4 catalog 資料品質問題（Kai 的範圍，只追蹤）

| 問題 | 數量 | 說明 |
|---|---|---|
| `category_code='bed'` 但實際是櫃類 | 10 筆 | 抽屜櫃、餐邊櫃、床下收納；含尺寸異常者（例如標成 468×225×186 的六抽屜櫃） |
| `item_id` 含 `-beds-` 但不是床 | 238／326 | 只有 88 件真的是床；其餘 sofa 113、sofa-bed 77、chests-of-drawer 28、wardrobe 16… |

👉 **從 `item_id` 或來源群組推型別，錯誤率高達 73%。** 這就是 2026-07-30 QA「床的槽位跑出衣櫃」的根因——那件 `Vida Designs Corona Wardrobe` 的 `category_code` 是對的（`wardrobe`），錯在 `item_id` 是 `abo-beds-01-...`。
👉 **詞彙只准一套 `category_code`**，應加測試禁止從 `item_id` 推型別。

---

## 5. 環境重建（每台機器都要做一次）

**git 只帶程式碼，不帶資料庫。** 公司、家裡、新環境是各自獨立的 PostgreSQL。

### 5.1 重建流程（可重複執行）

```bash
# 1. 裝與起服務
sudo apt-get install -y postgresql postgresql-contrib postgresql-18-pgvector
sudo service postgresql start

# 2. 設密碼（讀 .env，不外顯）＋建庫＋開 extension
PW=$(grep -E '^DB_PASSWORD=' .env | cut -d= -f2-)
sudo -u postgres psql -c "ALTER USER postgres PASSWORD '$PW';"
sudo -u postgres createdb -O postgres roompilot_db
sudo -u postgres psql -d roompilot_db -c \
  "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_trgm;"

# 3. 匯家具（importer 自帶 schema；先 --dry-run 驗）
.venv/bin/python scripts/sql/import_official_catalog_to_postgres.py --dry-run
.venv/bin/python scripts/sql/import_official_catalog_to_postgres.py

# 4. 匯向量
PGPASSWORD=$PW psql -h localhost -U postgres -d roompilot_db -v ON_ERROR_STOP=1 \
  -f scripts/sql/roompilot_furniture_embeddings_schema.sql
.venv/bin/python scripts/sql/import_furniture_embeddings_to_postgres.py \
  --embeddings JSON/RAG/furniture_embeddings_bge_m3.jsonl --require-all
```

`.env` 一個字都不用改；`JSON/` 七個檔已在 repo 內，與 `Kai-Django-RAG-report` 分支 byte-for-byte 一致，不必另外抓。

### 5.2 驗收查詢

```sql
SELECT extname FROM pg_extension WHERE extname='vector';
SELECT count(*) FROM roompilot.furniture_catalog_current WHERE kind='furniture';  -- 7958
SELECT count(*) FROM roompilot.furniture_embeddings e
  JOIN roompilot.furniture_embedding_source_current s
    ON s.item_id=e.item_id AND s.text_hash=e.text_hash
 WHERE e.embedding_model='BAAI/bge-m3';                                          -- 7958
SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
 WHERE n.nspname='roompilot' AND p.proname='search_furniture_embeddings_filtered';
```

### 5.3 合併 ben 之後必補的兩行

```bash
ROOMPILOT_RUNTIME_CATALOG_PROVIDER=json
ROOMPILOT_PROJECT_STORE_PROVIDER=sqlite
```

ben 帶進來的 runtime catalog **預設是 postgres 嚴格模式**：讀不到 `roompilot.runtime_catalog_imports` 就回 503，不會靜默退回 JSON。本機沒有 Kai 的 Phase 4 表，所以第 6 步會全數 503。

### 5.4 環境現況

| 項目 | 值 |
|---|---|
| OS | Ubuntu 26.04 LTS, WSL2, 12 核 / 15 GB |
| PostgreSQL | 18.4 + pgvector 0.8.1 + pg_trgm |
| GPU | NVIDIA RTX 2060 6GB，`torch.cuda.is_available() = True` |
| RAG device | `.env` 仍寫死 `cpu` ← **未做的 P0** |

⚠️ 開 `cuda` 的風險：BGE-M3 ＋ reranker 兩個模型同時上 6GB VRAM 可能 OOM，必要時只把 reranker 上 GPU，或改 fp16。

---

## 6. 驗證指令

```bash
# 環境（WSL 無 systemd，每次重開機都要手動起資料庫）
sudo service postgresql start && pg_isready -h localhost -p 5432

# 起 server
.venv/bin/python -m uvicorn backend.server.main:app --host 127.0.0.1 --port 8002

# 六支端點 smoke（任一支非 200 就是又被擋住了）
for p in "/api/furniture?type=sofa" /api/styles /api/home-data /api/site-data \
         /api/scene/bootstrap /api/rag/status; do
  printf "%-32s %s\n" "$p" "$(curl -s -m 60 -o /dev/null -w '%{http_code}' "http://127.0.0.1:8002$p")"
done

# 引擎回歸（不需資料庫）— 基準 131 passed
.venv/bin/python -m pytest -q tests/test_layout_strategy.py tests/test_clearance.py \
  tests/test_placement.py tests/test_agent_place.py tests/test_agent_select.py \
  tests/test_scene_layout_regions.py

# floor04 擺放預覽（跑真實辨識管線，約 21 秒，不使用快照）
.venv/bin/python scripts/floor04_layout_preview.py

# 頁面路由（注意是 /scene 不是 /scene.html）
#   /         主畫面
#   /scene    第 6/7 步 2D/3D
#   /rag      RAG 搜尋
#   /library  家具庫

# 確認 server 在哪個埠
ss -ltnp | grep python
```

---

## 7. 踩過的坑

| # | 坑 | 怎麼避開 |
|---|---|---|
| 1 | **`!` 開頭的指令貼進終端機會失效** | `!` 是 Claude Code 輸入框語法；在 bash 裡是「反轉結果」運算子，會讓 `!cmd && next` 的 next 永遠不執行。長指令一律寫成腳本再 `sudo bash` |
| 2 | **改 DB 或 `.env` 後第 6 步家具沒變** | `main.py` 的 `_furniture_payload_cache()` 有 `@lru_cache`，要重啟 server。RAG 走連線池，不用重啟 |
| 3 | **斷言硬編資料量** | `cloud_catalog.py` 曾以舊資料量 9,350 硬斷言，資料換版後把**六支不相干的端點一起打死**（500）。症狀是步驟 1～5 全正常，按下「產生場景」才炸 |
| 4 | **「重啟就會走另一條路」是推測** | 該次判斷錯誤，重啟後照樣 500。**推測必須實測才能寫進筆記** |
| 5 | **WSL 無 systemd** | 每次重開機都要手動 `sudo service postgresql start` |
| 6 | **遮罩指令寫錯會把 API key 印在終端機** | 2026-07-31 曾完整輸出 `OPENROUTER_API_KEY`。`.env` 未進版控，但 key 已出現在 session 紀錄 → **建議輪換**（仍未做） |
| 7 | **`.env` 備份沒被 gitignore 擋住** | `.gitignore` 只寫 `.env`，`.env.bak-*` 完全沒擋。2026-08-01 已改為排除 `.env.*` 並保留 `!.env.example` |
| 8 | **`notes/` 會比正式 README 舊** | 判斷進度一律以 `../README.md`、`../room_strategy/README.md` 為準 |

---

## 8. 已解除的疑慮（別再當成問題）

| 曾以為 | 實際 | 怎麼查證的 |
|---|---|---|
| engine clearance 只覆蓋 22.9%，是大缺口 | **與 v1.2 規格 100% 對齊，一個沒漏**。無規則的 65% 是刻意設計（本檔 §2-C） | 用規格表 A+B 的 22 個類型比對 `clearance_defaults.py` 的 23 個鍵 |
| 本機 SQL schema 是舊版，要跟 Kai 要 | **已是新版**，含 `furniture_catalog_api_current` 與 `furniture_admin_audit` | grep schema 內的 CREATE 陳述 |
| 房型策略表待勾選，是 P0 阻塞 | **早已拍板**，v1 定版於 `../room_strategy/README.md` | 讀正式 README |
| `chests-of-drawer` 對碼有缺口 | **DB 實際就是 `chests-of-drawer`(129 筆)**，與引擎完全一致，不需改碼 | 查 DB 分類 |
| 靠牆衣櫃的 front 會不會朝室內？ | **會**。正面朝牆時淨空跑到牆外，引擎自己就擋掉了 | 2026-08-01 實測 rotation 0 legal / 180 illegal |

---

## 9. 2D／3D 擺放程式碼地圖（**改引擎前必查**）

> 2026-08-01 全庫掃描結果。擺放這件事散在 **6 層、13 個檔案**。
> 只改引擎而沒改對應的上層，常見結果是「改了但畫面沒變」或「規則被別的地方蓋掉」。

### 9.1 資料流：誰決定什麼

```
第 4 步 房型與門窗
   ↓
[1] 房型清單「放什麼」      ← 4 套並存，第 6 步實際只吃前端那套
   ↓
[2] 選件「選哪一件」        ← scene_service 評分＋亂數（不是 RAG）
   ↓
[3] 尺寸與淨空「要留多少」   ← 3 套並存，引擎那套勝出
   ↓
[4] 擺放策略「放哪裡、朝哪」 ← 引擎策略層優先，舊候選表 fallback
   ↓
[5] 合法性「能不能放」       ← 引擎＋scene_service 各有一半
   ↓
[6] 呈現 2D SVG／3D three.js
```

### 9.2 逐層檔案清單

#### [1] 房型清單「放什麼」——**4 套並存**

| # | 位置 | 內容 | 第 6 步吃嗎 |
|---|---|---|---|
| 1 | `backend/engine/room_strategy/README.md` | v1 正式規格（人讀） | ❌ |
| 2 | `backend/agent/knowledge.py:97` `ROOM_MINIMUM_FAMILIES` | Agent 機器可讀 | ❌ |
| 3 | `backend/server/scene_service.py:108` `SPACE_DEFAULTS` | 後端預設 | 只有直接打 API 時 |
| 4 | `backend/server/static/scene_layout2d.js:234` `recommendedFurnitureForRoom` | 前端 | ✅ **走瀏覽器時實際用這張** |

#### [2] 選件「選哪一件」

| 位置 | 內容 |
|---|---|
| `scene_service.py:409` `choose_furniture_items` | 風格／顏色／尺度四項評分 ＋ **亂數 0~8 分**，取第一名 |
| `scene_service.py:125` `FURNITURE_ALIASES` | 中文→型別；**仍含 2 個死鍵**（`bed-frame`／`cabinets-cupboard`） |
| `scene_service.py:534` `_BED_CONFLICT_TOKENS` | 防「床的槽位跑出衣櫃」的字串防呆 |
| `backend/spatial_data/rag/` | 真 RAG，**沒接主流程**，只掛 `/api/rag/*` |
| `backend/agent/select.py` | LLM 選件，**結構上不可能被呼叫** |

#### [3] 尺寸與淨空「要留多少」——**3 套並存**

| # | 位置 | 涵蓋 | 實際生效？ |
|---|---|---|---|
| 1 | `backend/engine/clearance_defaults.py` | 17 單面＋6 多面 | ✅ **勝出** |
| 2 | `backend/catalog/style_db.py:185` `CLEARANCE_BY_TYPE` | 只有 4 個類型 | ❌ **死碼**——`scene_service.py:1313` 會 `replace(catalog, clearance=None)` 明確清掉再補引擎的 |
| 3 | `backend/server/engineering/rules.py:208` | 走道 80cm advisory | ⚠️ 只進工程報告警告，不擋擺放 |

⚠️ **`style_db.CLEARANCE_BY_TYPE` 是陷阱**：數字與引擎不同（sideboard 40 vs 60、desk 硬 50 vs 軟 75），看起來像規則但**永遠不會生效**。改它沒用，別被誤導。

#### [4] 擺放策略「放哪裡、朝哪」

| 位置 | 內容 | 順序 |
|---|---|---|
| `backend/engine/layout_strategy.py` | 選牆／貼牆／正面朝內／貼床頭端／正前方／擺放順序 | **1️⃣ 優先** |
| `scene_service.py:726` `_placement_candidates` | 80 行寫死的位置＋角度表，17 種家具 | 2️⃣ fallback |
| `scene_service.py:706` `_WALL_ANCHORED_TYPES` | 貼牆清單（供上表用） | — |
| `scene_service.py:806` `_hinted_wall_candidate` | 使用者拖曳留下的牆面提示 | 插在候選最前 |
| `scene_service.py:848` `curtain_window_hint` | 窗簾對齊窗戶 | 插在候選最前 |
| `backend/engine/placement.py` | 中心→四面牆→15cm 網格，first-fit | 3️⃣ 最後備援 |
| `backend/agent/place.py` | 順序／換小／降級，**不算座標** | 包在最外層 |
| `backend/server/main.py:3072` | 貼 `placement_relation` 標籤 | **只給地毯／植栽／燈** |

#### [5] 合法性「能不能放」

| 位置 | 內容 |
|---|---|
| `backend/engine/clearance.py` | 淨空七道檢查（順序見 `../README.md`） |
| `backend/engine/geometry.py` | 出界／穿牆／重疊 |
| `scene_service.py:1002` `window_clearance_zones` | **窗前 70cm 禁放帶**，平頭硬擋，不分窗型不看高度 |
| `scene_service.py:844` `_OVERLAY_TYPES` | 地毯可壓在別人身上 |
| `scene_service.py:845` `_IGNORE_COLLISION_TYPES` | 壁架**完全跳過碰撞** |
| `scene_service.py:1442` `_shrunk_boundary` | 全房內縮 **8cm** |
| `scene_service.py:1450`～`:1534` | 非矩形房間／多區域邊界 |

#### [6] 呈現

| 位置 | 行數 | 內容 |
|---|---|---|
| `static/scene_layout2d.js` | 368 | 2D SVG；`toSceneFurniture` **預設 `position_locked=true`** |
| `static/scene_viewer.js` | 5,235 | 3D three.js；**8 處**會把 `position_locked` 設 true |
| `static/scene_v2.js` | 13,224 | 第 6 步主控；`autoLayoutFurniture`:8052、`relayoutFurnitureForScheme`:8236 |
| `static/scene.js` | 3,128 | 舊版場景頁 |
| `frontend3d/src/snap.js` | 137 | **完全獨立的貼牆吸附**，**公尺制**，次要原型，與正式產品無關 |

### 9.3 改引擎時的連動檢查表

| 你要改引擎的 | 一定要一起改 | 否則 |
|---|---|---|
| **堆疊層（地毯）** | `scene_service.py:844` `_OVERLAY_TYPES` 分支 | 地毯走 overlay 分支，策略層碰不到，**完全吃不到** |
| **落地窗留距** | `scene_service.py:1002` `window_clearance_zones` | 70cm 平頭帶取嚴，**細緻規則被蓋掉** |
| **清死鍵** | `scene_service.py:125` `FURNITURE_ALIASES` | 問卷打「床架」「收納櫃」**照樣回 0 件** |
| **房型白名單** | 上面 [1] 的 4 套清單 | 變成第 5 套，第 6 步仍走前端那張 |
| **壁架碰撞** | `scene_service.py:845` `_IGNORE_COLLISION_TYPES` | 壁架跳過碰撞，引擎規則無效 |
| **貼牆邊距** | `scene_service.py:1442` `_shrunk_boundary`（8cm） | 兩套邊距疊加，家具離牆變 16cm |
| 淨空數字 | 無（`style_db` 那套是死碼） | ✅ 安全 |
| 成組擺放、選牆、朝向 | 無（已接線） | ✅ 安全 |

### 9.4 五個容易踩的陷阱

1. **`position_locked`**：2D／3D 拖過的家具會被鎖住，之後重排**不會動它**。測引擎改動時若用舊專案，可能整批家具都是鎖定的，看起來像「改了沒效」。
2. **`@lru_cache`**：`main.py` 的 `_furniture_payload_cache()` 有快取，改 DB 或 `.env` 後**要重啟 server** 才生效（RAG 走連線池，不用重啟）。
3. **`style_db.CLEARANCE_BY_TYPE`**：看起來是規則，實際是死碼（見 [3]）。
4. **方案 A／B**：方案 B **刻意不走策略層**（策略層是確定性的，否則兩案會一模一樣）。測策略層時要確認在方案 A。
5. **`frontend3d/` 是公尺制**，正式產品是公分制。那份 `snap.js` 與生產流程無關，別拿去對照。

### 9.5 開關

```bash
ROOMPILOT_LAYOUT_STRATEGY=0   # 關掉擺放策略層，100% 退回接線前行為
```
