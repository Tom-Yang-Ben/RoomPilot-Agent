# RoomPilot 檢索受控詞彙表

> **來源檔（唯一事實來源，本檔與其不符時以檔案為準）**
> - `backend/spatial_data/rag/data/taxonomy.json` — 風格、相容矩陣、圖樣、氛圍（`taxonomy_version: v2-six-style`，2026-07-27）
> - `backend/spatial_data/rag/data/category_groups.json` — 19 群組展開表與房型預設組合（`version: v1`）
> - `rag/vlm_annotation/taxonomy_v2.json` — 上者的完整版，另含 18 色卡與 64 類 `category_map`
> - 載入點：`backend/spatial_data/rag/vocab.py:15`；欄位契約：`backend/spatial_data/rag/models.py`
>
> 抄寫日期 2026-08-02。`lint_query.py` 讀的是上列檔案而非本檔，詞表改版時 lint 會先抓到。

---

## 1. 風格（6 個，`styles` 最多 2 個，軟加權）

| id | 中文 | 定義（taxonomy 原文） | 全庫佔比 |
| :--- | :--- | :--- | --: |
| `scandinavian` | 北歐風 | 淺色原木、白色基調、簡潔圓潤線條與明亮放鬆氛圍 | 23.3% |
| `japanese` | 日式 | 自然材質、低彩度大地色、低矮家具與寧靜留白 | 1.9% |
| `modern_minimal` | 現代簡約 | 俐落幾何、黑白灰、玻璃金屬與乾淨都會感 | 44.0% |
| `cream` | 奶油風 | 奶油白與奶茶色、柔霧質感、圓弧和柔軟布藝 | 6.0% |
| `industrial` | 工業風 | 黑鐵、深色木材、皮革、水泥灰與粗獷結構 | 4.8% |
| `american` | 美式 | 厚實木作、線板、皮革與沉穩舒適的家庭氛圍 | 20.0% |

**佔比會影響策略**：日式只有 181 筆、工業風 450 筆。這兩種風格疊上房型與價格後很容易撈空，
要先放寬其他硬過濾，而不是換風格。

### 風格相容矩陣 `style_compat`（軟加權用，`ranking.py:81`）

| ↓要求／實際→ | scandinavian | japanese | modern_minimal | cream | industrial | american |
| :--- | --: | --: | --: | --: | --: | --: |
| **scandinavian** | 1.0 | 0.9 | 0.8 | 0.7 | 0.3 | 0.4 |
| **japanese** | 0.9 | 1.0 | 0.8 | 0.5 | 0.4 | 0.2 |
| **modern_minimal** | 0.8 | 0.8 | 1.0 | 0.5 | 0.7 | 0.4 |
| **cream** | 0.7 | 0.5 | 0.5 | 1.0 | 0.2 | 0.7 |
| **industrial** | 0.3 | 0.4 | 0.7 | 0.2 | 1.0 | 0.5 |
| **american** | 0.4 | 0.2 | 0.4 | 0.7 | 0.5 | 1.0 |

物件的 `style_secondary` 命中只算 0.6 倍。要求兩個相斥風格（如 cream + industrial，0.2）
等於兩邊都拿不到分——**寧可只寫一個**。

---

## 2. 色卡（18 個，每風格 3 個）

色卡名有寫進索引文本的「色卡：」欄位，是**比風格名更精準的訊號**。屋主講得出調性時優先用。

| 風格 | 色卡 | 主色階 |
| :--- | :--- | :--- |
| scandinavian | 自然木質 | `#F3EBDD` `#D3B48A` `#8B684B` |
| scandinavian | 清新明亮 | `#F7F5ED` `#DCE7DF` `#A5C0B0` |
| scandinavian | 低彩度質感 | `#E8E6DF` `#B9B5A9` `#6E706D` |
| japanese | 侘寂自然 | `#D8D0C1` `#A89B87` `#625B50` |
| japanese | 茶室禪意 | 同上 |
| japanese | 現代和風 | 同上 |
| modern_minimal | 黑白俐落 | `#F4F3F0` `#969696` `#252525` |
| modern_minimal | 暖灰質感 | `#E4DED5` `#A69C91` `#5A534D` |
| modern_minimal | 自然留白 | `#F5F2EB` `#D3C7B5` `#77736B` |
| cream | 奶油米白 | `#F5EBDD` `#DCC4A8` `#A98568` |
| cream | 法式柔霧 | 同上 |
| cream | 奶茶木質 | 同上 |
| industrial | 黑鐵水泥 | `#3D403F` `#858078` `#A56F4E` |
| industrial | 復古工坊 | `#4A4038` `#9A6A46` `#C19B72` |
| industrial | 極簡冷調 | `#D5D6D2` `#697078` `#252A2D` |
| american | 鄉村溫馨 | `#F0E5D4` `#B58D67` `#6C513F` |
| american | 經典優雅 | 同上 |
| american | 現代輕奢 | 同上 |

> 日式、奶油風、美式三組的三張色卡共用同一組 hex（來源色票如此），
> **靠色卡名而非色階區分**——寫「茶室禪意」和寫「侘寂自然」對向量檢索是不同的字。

---

## 3. 氛圍（24 個，`moods` 最多 3 個，軟加權）

```
溫馨  放鬆  明亮  寧靜  俐落  率性  沉穩  大器
優雅  浪漫  質樸  自然  精緻  高級  復古  懷舊
活潑  繽紛  純粹  靜謐  粗獷  溫潤  療癒  都會
```

**必須逐字命中。** `mood_score = |實際 ∩ 要求| / |要求|`（`ranking.py:98`），
用 `|` 分隔的 `moods_flat` 做集合交集，沒有模糊比對、沒有同義詞。
一個都沒寫時回傳中性 0.5——**寫錯詞比不寫還糟**（0 分）。

---

## 4. 家具群組（19 個，硬過濾，展開成 64 個 `category_final`）

| group | 中文 | 展開的 category_final |
| :--- | :--- | :--- |
| `sofa` | 沙發 | 沙發、布沙發、皮沙發、模組沙發、沙發床 |
| `armchair` | 扶手椅／單椅 | 扶手椅、椅子 |
| `dining_chair` | 餐椅 | 餐椅 |
| `office_chair` | 辦公椅 | 辦公椅、電競椅 |
| `stool_bench` | 凳子與長凳 | 凳子與長凳、兒童凳子與長凳 |
| `coffee_table` | 茶几 | 茶几 |
| `side_table` | 邊桌／床邊桌 | 床邊桌 |
| `dining_table` | 餐桌 | 餐桌、吧檯桌 |
| `desk` | 書桌／工作桌 | 書桌、桌子、兒童桌 |
| `bed` | 床與床墊 | 床、床墊 |
| `storage` | 收納櫃體 | 櫃體、抽屜櫃、書櫃、電視櫃、餐邊櫃、展示櫃、鏡櫃、收納系統、收納家具、層架、壁架、收納盒與籃子 |
| `wardrobe` | 衣櫃與鞋櫃 | 衣櫃、PAX 衣櫃、鞋櫃、衣帽架 |
| `rug` | 地毯 | 地毯、大型與中型地毯、走道地毯與小地毯、手工地毯、圓形地毯、羊皮與牛皮地毯、戶外地毯、門墊 |
| `lighting` | 燈具 | 燈具、檯燈、落地燈、吊燈、壁燈、吸頂燈、工作燈、燈罩與燈座 |
| `mirror` | 鏡子 | 鏡子、大型鏡子、立鏡 |
| `decor` | 軟裝與擺飾 | 抱枕靠墊、裝飾配件、花器、盆栽植器 |
| `kids` | 兒童家具 | 兒童家具、兒童椅與凳子、兒童桌、兒童凳子與長凳 |
| `media` | 電視與影音 | 電視與影音家具、電視櫃 |
| `partition` | 屏風與隔間 | 屏風與隔間 |

**群組是刻意重疊的**（`電視櫃` 同屬 `storage` 與 `media`；`兒童桌` 同屬 `desk` 與 `kids`）。
選群組不選細類的理由：沙發散在 5 個細類、地毯散在 8 個，直接挑細類會誤砍掉 800+ 筆。

**不在型錄的品項**（提到時要明說，不要當家具找）：
冰箱、洗衣機、冷氣、烘乾機、電視機等家電 → 留在問卷與 `scene_json.render_context`；
窗簾、馬桶、浴缸、洗手台、廚具流理台 → 不在本型錄。

---

## 5. 房型（9 個，硬過濾，只能一個）

| id | 中文 | 常見口語 |
| :--- | :--- | :--- |
| `living_room` | 客廳 | 客廳、起居室、公共空間 |
| `bedroom` | 臥室 | 臥室、主臥、次臥、寢室 |
| `dining_room` | 餐廳 | 餐廳、用餐區、飯廳 |
| `kitchen` | 廚房 | 廚房、中島區 |
| `bathroom` | 浴室 | 浴室、衛浴、廁所 |
| `study` | 書房 | 書房、工作室、辦公區 |
| `kids_room` | 兒童房 | 兒童房、小孩房、嬰兒房 |
| `entryway` | 玄關 | 玄關、入口、鞋櫃區 |
| `outdoor` | 戶外 | 陽台、露台、庭院、戶外 |

### 房型預設組合（只在屋主要「一整組」時才補，補入項會標 `is_inferred=true`）

| 房型 | 預設組合 |
| :--- | :--- |
| living_room | sofa + coffee_table + rug + lighting + armchair |
| bedroom | bed + wardrobe + side_table + lighting |
| dining_room | dining_table + dining_chair + lighting + rug |
| study | desk + office_chair + storage + lighting |
| kids_room | kids + storage + lighting + rug |
| entryway | storage + mirror + stool_bench + rug |

> `kitchen`、`bathroom`、`outdoor` **沒有預設組合**——這三個房型講「配一整組」時，
> 要回頭問屋主要哪些品項，不要自行推論。

---

## 6. 其他受控欄位

| 欄位 | 值 | 性質 |
| :--- | :--- | :--- |
| `pattern` | 素色 / 木紋 / 幾何 / 花紋 | 進語意查詢 |
| `role` | `anchor`（主家具）/ `accent`（配件） | **硬過濾**，不確定就別寫 |
| `size_hint` → `size_class` | `S` / `M` / `L` | **硬過濾**，不確定就別寫 |
| `price_level` | `budget` / `mid` / `premium` | 換算成該群組的 p33／p67 分位數 |
| `quantity` | 1–8 | 每個品項 |
| `items` | 1–6 筆 | 不可為空；不知類別用 `category_group=null` |
| `query` | ≤1000 字 | API 上限（`models.py:83`） |
| `top_k` | 1–8 | API 上限 |

### 價格如何被使用（`ranking.py:38`）

1. 品項有 `price_max` → 直接用。
2. 有 `budget_total` → 依各群組**中位價比例**分配（不是平均分），再乘 `BUDGET_SLACK = 1.3`。
3. 只有 `price_level` → `budget` 取 ≤p33、`mid` 取 p33–p67、`premium` 取 ≥p67。
4. 具體金額與相對詞**互斥**，同時給會讓解析器二選一，結果不可預期。

> 為什麼不能平均分：6 萬配一組客廳，平均每件 12,000 會讓沙發（P25 = 15,300）一件都撈不到。

---

## 7. 索引文本句式（語意描述要模仿的對象）

每件家具的向量來自 `embedded_text`，格式是固定順序的中文標籤句，以「。」分隔
（`rag/json_adjustment/build_rag_v3.py:203`）：

```
名稱：…。類別：…。物件類型：…。顏色：…。材質：…。適用空間：…。
風格：日式(japanese)。色卡：侘寂自然。氛圍：寧靜、自然。表面圖樣：素色。
造型：…。描述：（VLM 寫的 80–120 字外觀描述）。特徵：…。關鍵字：…。
```

屋主的話通常十餘字，索引文本是 300 字的 VLM 描述，**兩者向量分布差很遠**。
所以檢索句裡的語意描述要往這個句式靠（HyDE）：寫 30–120 字、涵蓋
**物件 + 風格 + 色卡 + 材質 + 顏色 + 造型量體 + 氛圍**，
**不要寫價格與尺寸**（那是硬過濾的事，寫進語意只會稀釋向量）。

---

## 8. 排序公式（診斷時對照）

```
final = 0.60 × rerank        （bge-reranker-v2-m3，已內建 sigmoid，0-1）
      + 0.20 × style_compat  （要求風格 vs 物件 style_primary／secondary×0.6）
      + 0.10 × mood 命中率    （集合交集 / 要求數）
      + 0.10 × item.confidence（標註把握度）
```

權重常數在 `backend/spatial_data/rag/ranking.py:16`。
向量檢索取 top 50 → 重排 top 20（配件 12）→ 最終回 8 筆。

**rerank 佔 0.6，所以語意描述寫得好不好，比風格詞填得對不對影響更大。**

---

## 9. 已知資料限制

1. 日式 181 筆、工業風 450 筆——小樣本風格疊上硬過濾容易撈空。
2. `name_zh` 有法文／義大利文殘留（ABO 來源），影響顯示不影響檢索（檢索靠中文描述）。
3. 重複商品只靠 `duplicate_group` 去重，177 筆有標，同款不同色仍可能並列。
4. 865 筆有 `category_conflict` 標記（分類已修正）。
5. 成套推論偶爾夾帶不合房型的品項（客廳組推出床邊桌），會標 `is_inferred`，要人工剔除。
6. 檢索**不做**擺放可行性判斷——那是 `backend/engine/` 的事。
