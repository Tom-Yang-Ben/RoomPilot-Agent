---
description: 產出 RoomPilot VLM 家具標註輸出規格（受控詞彙、80–120 字繁中描述、confidence、灰模判定）
---
# VLM 標註輸出模式
當我請你設計、審查或執行 RoomPilot 的家具 VLM 標註（`vlm_annotation/`，模型 `claude-haiku-4-5`，
輸入為 `rendering/output/…/正面(abo|ikea)/` 的預渲染 PNG）時，請使用「受控詞彙優先」的輸出方式：
【標註原則】
1. 只輸出 JSON，不加 markdown 圍欄、不加任何前後說明文字
2. 所有 enum 欄位一律取自 `vlm_annotation/taxonomy_v2.json`，不得自創新值
3. 從外觀事實逐步推到風格判斷（先看到什麼，再判是什麼風格）
4. 用對比方式標註信心（有貼圖 vs 灰模、圖片事實 vs 已知欄位衝突）
5. 提供可驗證的欄位值與 confidence，讓下游能量化篩選
【輸出結構】
請按照以下結構組織標註結果：
## 一、核心輸出總覽
- 用一段話說明這件家具的外觀本質
- 用單一 JSON 物件呈現全部欄位（下方第三節列出完整欄位表）
## 二、輸入現況（如適用）
- 這件模型有沒有貼圖：有貼圖走 `desc_source="glb_render"`，灰模走 `desc_source="text_inference"`
- 已知欄位（`name_zh` / `canonical_category_zh` / `materials` / `colors`）目前的值與缺漏
## 三、欄位規格詳解
- 每個欄位的型別、受控詞彙來源、上限個數
- 欄位之間的關係（`style_secondary` 可與 `style_primary` 相同；`colors_seen` 只在原欄位為空時採用）
- 資料流走向：`annotations_full.jsonl`（可續跑進度檔）→ merge → `furniture_enriched_v2.json`
## 四、具體案例
- 用一筆真實家具展示實際輸出（含 JSON 全文）
- 標註關鍵決策點：為什麼判 `japanese` 而不是 `scandinavian`
## 五、合格 vs 不合格對比
- 用表格呈現常見不合格輸出與修正後的樣子
- 說明各自會在下游造成什麼後果
## 六、批次實施建議
- 分階段執行圖（sample 試跑 → 全量 → merge → report）
- 風險與注意事項（費用、續跑、429、灰模比例）
【受控詞彙】
一律取自 `vlm_annotation/taxonomy_v2.json`（`taxonomy_version: v2-six-style`），共 7 類：
- 風格 styles（6 個）：scandinavian 北歐風／japanese 日式／modern_minimal 現代簡約／cream 奶油風／industrial 工業風／american 美式
- 表面圖樣 pattern_enum（4 個）：素色／木紋／幾何／花紋
- 氛圍 mood_vocab（24 個）：溫馨、放鬆、明亮、寧靜、俐落、率性、沉穩、大器、優雅、浪漫、質樸、自然、精緻、高級、復古、懷舊、活潑、繽紛、純粹、靜謐、粗獷、溫潤、療癒、都會
- 房型 room_enum（9 個）：living_room／bedroom／dining_room／kitchen／bathroom／study／kids_room／entryway／outdoor
- 角色 role_enum（2 個）：anchor（主角家具）／accent（配件）
- 視覺重量 visual_weight_enum（3 個）：light／medium／heavy
- 高度分區 height_zone_enum（3 個）：low／mid／high
（另有 18 張色卡 `style_card_id`／`style_card` 與 6×6 `style_compat` 相容矩陣，
 由後段 `json_adjustment/build_rag_v3.py` 掛上，VLM 階段不需自行填。）
【描述文字風格】
`description` 欄位固定規格：
- 長度：80–120 字繁體中文，過短資訊不足、過長會稀釋 embedding
- 內容順序：線條 → 色調 → 材質 → 氛圍 → 適合情境
- 禁詞：不得出現「圖片」「照片」「模型」「這張圖」「渲染」等指涉素材本身的字眼
- 用途：`description` 會被組進 `embedded_text`，是 bge-m3 的實際輸入，寫得越具體檢索越準
- 標點：句號用「。」，列舉用「、」；不要使用條列符號或換行
【正規化與防呆】
- enum 去括號正規化：VLM 常回 `"minimalist(極簡風)"` 或 `"japanese（日式）"`，
  比對前一律取 `s.split("(")[0].split("（")[0].strip()`，半形與全形括號都要處理
- 不在清單內就降信心：`style_primary` 正規化後仍不合法 → 改判 `modern_minimal`
  且 `confidence = min(原值, 0.3)`；`style_secondary` 不合法 → 回退成 `style_primary`
- 氛圍詞過濾取前三：`mood_tags` 只保留在 `mood_vocab` 內的詞，超過 3 個截斷為 3 個
- 灰模判定：`render_meta_full.jsonl` 的 `is_gray=True` 代表模型無材質貼圖，
  此時不送圖片、只依名稱與已知欄位推斷，`confidence` **不得超過 0.5**，`desc_source="text_inference"`
記住：目標是讓每一筆標註都能直接餵進 `embedded_text` 與 Chroma metadata，而不是寫給人看的評論。
簡化版 Prompt（日常使用）
請用「VLM 標註輸出模式」回答：
- 不加說明文字，只輸出單一 JSON 物件
- 先看到什麼再判什麼，從外觀事實推到風格
- 對比已知欄位與圖片事實，衝突時以看到的為準
- 所有 enum 取自 taxonomy_v2.json，不自創新值
- description 寫 80–120 字繁中，不提及圖片或模型
- 誠實給 confidence，灰模不得超過 0.5
特定場景版本
有貼圖模型標註
請以圖片實際外觀為準：
1. 先描述看到的線條、色調、材質，再收斂到六風格擇一
2. `colors_seen` / `materials_seen` 各最多 3 個，繁體中文
3. 與已知欄位（materials/colors）衝突時以你看到的為準
4. `desc_source` 填 `glb_render`，confidence 可高於 0.5
灰模（無貼圖）標註
請主要依商品名稱與已知欄位推斷：
1. 不送圖片，只用 `name_zh`、`canonical_category_zh`、已知材質顏色
2. `confidence` 一律 ≤ 0.5，不得因為描述寫得順就給高分
3. `desc_source` 填 `text_inference`
4. `colors_seen` / `materials_seen` 寧可留空，也不要編造顏色
補標與續跑
請以可續跑方式批次執行：
1. 只把「成功列」視為已完成，錯誤列（429 等暫時性失敗）留待重跑自動重試
2. 每筆寫一行 JSONL 後立刻 flush，中斷不丟進度
3. 失敗列格式固定為 `{"id": ..., "error": "..."}`，錯誤訊息截斷至 200 字
4. merge 前先備份主檔（`furniture_enriched_v2.bak_before_full.json`）
使用範例
你可以這樣使用：
「請用 VLM 標註輸出模式，為這件『UNDERLÄTTA 木質邊桌』產出標註 JSON」
「用受控詞彙檢查這 20 筆 annotations_full.jsonl，列出不合法的 style_primary」
「不要說明，直接輸出灰模版本的標註 JSON，confidence 記得壓在 0.5 以下」
「用表格對比 taxonomy v1（12 風格）與 v2（6 風格）在這批標註上的判定差異」
為什麼這種方式有效
自由文字標註　　　　　受控詞彙標註
　　　│　　　　　　　　　　　│
　　　↓　　　　　　　　　　　↓
　風格值百花齊放　　　　六風格閉集合
　氛圍詞無法比對　　　　24 詞可統計
　信心值靠感覺　　　　　confidence 可篩選
　　　↓　　　　　　　　　　　↓
　Chroma where 對不上　　硬過濾直接可用
　排序公式無法加權　　　style_compat 查得到
（排序公式 `final = 0.60×rerank + 0.20×style_compat + 0.10×mood命中率 + 0.10×confidence`
 有三項直接吃 VLM 標註品質——標註一鬆，檢索就跟著鬆。）
Prompt 客製化建議
根據你的需求，可以調整：
【調整重點】
如果你想要：
更嚴格的風格判定
→ 加入「不確定就填 modern_minimal 並把 confidence 壓到 0.3 以下」
更豐富的檢索詞
→ 加入「額外輸出 search_keywords，最多 3 個繁中短詞」
更省成本
→ 先用 `--sample 20` 跨品牌抽樣試跑，確認格式再全量（全量批次才是燒額度的地方）
更快速
→ 使用簡化版，只要 style_primary / pattern / mood_tags / confidence 四欄
補充說明
這個 prompt 的設計理念：
┌────────────────────────────────────────┐
│ 標註品質的層次                         │
├────────────────────────────────────────┤
│                                        │
│ 第一層：合法 JSON（能被 parse）        │
│   ↓                                    │
│ 第二層：enum 合法（能進 Chroma）       │
│   ↓                                    │
│ 第三層：描述具體（embedding 有訊號）   │
│   ↓                                    │
│ 第四層：信心誠實（能被門檻篩選）       │
│   ↓                                    │
│ 第五層：判定正確（檢索結果對得上人感） │
│                                        │
└────────────────────────────────────────┘
下游可以在任何層次設門檻，已經獲得該層次的品質保證
這樣的 prompt 能確保：
1. 可機器消費：JSON 直接進 `annotations_full.jsonl`，不需人工清洗
2. 可硬過濾：enum 閉集合讓 `chroma_metadata` 的 `where` 一定命中
3. 可加權排序：`style_compat` 與 `mood命中率` 查得到、算得出
4. 可稽核：`confidence` 與 `desc_source` 讓灰模與低信心筆數一眼可統計
