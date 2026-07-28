# 需求解析器（query_parser）設計規格

> 對應實作：`rag_pipeline/query_parser.py`
> 版本：v1（2026-07-27）

## 1. 定位

把使用者的自然語言家具需求，轉成**受控詞彙的結構化檢索條件**，同時產出給 bge-m3 用的
HyDE 式查詢文本。一次 LLM 呼叫同時完成兩件事，比「先結構化、再另外做 HyDE」省一半延遲。

```
「想要日式侘寂感、預算兩萬內的客廳沙發」
        │
        ├─ 硬過濾條件 → Chroma where（房型 / 類別 / 價格 / 尺寸）
        ├─ 軟性條件   → 排序加權（風格 / 氛圍）
        └─ semantic_query → bge-m3 向量檢索 + reranker 輸入
```

**模型**：`claude-haiku-4-5` + structured outputs（`output_config.format`，JSON schema 強制約束）。

> **為什麼這裡刻意留在雲端 API**（而風格判定改用本機 Qwen3）：
> 本檔輸出約 600 token，本機 Qwen3 8B 在 M1 上要 20 秒以上，Haiku 只要 1–2 秒；
> 且本檔的硬規則（不得推測尺寸、items 不可為空、HyDE 需仿 embedded_text 句式）
> 對指令遵守度要求高，小模型破壞規則的後果是**默默回傳錯結果**而非報錯。
> 成本面每次僅約 US$0.005，1,000 次查詢 ≈ US$5。詳見 `docs/RAG檢索系統說明.md` 3.5 節。
**風格詞表**：`vlm_annotation/taxonomy_v2.json`（六風格 × 3 色卡，源自 `taiwan_style_cards.json`）。

## 2. 輸出結構

外層是全域條件，`items[]` 是品項清單。**單物件 = `items` 長度 1**，多物件走完全相同的程式路徑。

| 全域欄位 | 型別 | 用途 |
| :-- | :-- | :-- |
| `room_type` | enum(9) / null | **硬過濾** `room_<type> = true` |
| `styles` | enum(6)，最多 2 | **軟加權**（style_compat 6×6 矩陣） |
| `moods` | enum(24)，最多 3 | **軟加權**（moods_flat 交集） |
| `pattern` | enum(4) / null | 進 semantic_query |
| `color_hint` / `material_hint` | string / null | 進 semantic_query（詞彙 317/700+ 種，字串比對必敗） |
| `price_level` | budget/mid/premium / null | 相對價位，由程式換算成該類別群組的分位數 |
| `budget_total` | int / null | 整組總預算，依中位價比例分配到各品項 |
| `is_set` | bool | true = 成套搭配，需維持風格一致 |
| `confidence` | 0-1 | 解析把握度 |
| `needs_clarification` / `clarify_question` / `clarify_options` | — | 追問；UI 仍先顯示結果 |

| 品項欄位 | 用途 |
| :-- | :-- |
| `item_id` / `label_zh` | 識別與顯示 |
| `category_group` | 19 群組之一 / **null**（只給風格不給類別時，不做類別過濾） |
| `quantity` / `priority` | 件數、must_have / nice_to_have |
| `is_inferred` | ★ true = 使用者沒明講、系統推論的品項，UI 標「建議加入」並可移除 |
| `semantic_query` | 此品項專屬的 HyDE 描述 |
| `styles` | 覆寫全域風格（少用） |
| `price_max` / `max_width_cm` / `max_height_cm` / `role` / `size_hint` | 硬過濾條件 |

## 3. 三個關鍵設計決定

**① `category_group` 用 19 群組，不用 64 細類。**
`category_final` 有 64 個值，其中沙發散在 5 類、地毯散在 8 類。讓 LLM 從 64 個挑會挑錯粒度
（說「沙發」挑到「布沙發」，另外 804 筆被濾掉）。改成 19 群組、程式展開成 `$in`。
對照表在 `rag_pipeline/category_groups.json`，改分類不用改 prompt。

> 群組數以 `category_groups.json` 為準，勿在文件裡記死：
> `.venv-rag/bin/python -c "import json; print(len(json.load(open('rag_pipeline/category_groups.json'))['groups']))"`

**② 風格必須是軟加權，不能硬過濾。**
單一風格硬過濾後，疊上房型與類別可能只剩個位數。`taxonomy_v2.json` 內建 6×6 的
`style_compat`（japanese↔scandinavian 0.9、cream↔american 0.7）——加權排序讓相容風格也撈得進來。

**③ `semantic_query` 要寫成與 `embedded_text` 相同的句式。**
使用者輸入通常 10 餘字，而索引文本是 VLM 寫的 300 字描述，兩者向量分布差很遠。
讓 LLM 順手擴寫成同格式的假想描述（HyDE），命中率明顯提升。

## 4. schema 的兩個實作坑（實測）

- **可為 null 的 enum 不能寫 `{"type": ["string","null"], "enum": [...]}`** →
  API 回 400「Enum value does not match declared type」。必須用
  `{"anyOf": [{"type":"string","enum":[...]}, {"type":"null"}]}`。
- **不支援 `maxItems` / `minItems`** → 上限在 prompt 說明，並在程式端裁切
  （styles 2 / moods 3 / items 6 / clarify_options 4）。

## 5. Prompt 硬規則（實測調整過）

1. 只能使用受控詞彙（六風格）；口語對映：侘寂／無印風→japanese、北歐→scandinavian、
   性冷淡風／極簡→modern_minimal、loft→industrial、奶油風／奶茶色→cream、美式／鄉村／中古世紀→american。
   使用者提到色卡名（「自然木質」「侘寂自然」「黑白俐落」…）也對映到所屬風格。
2. 沒提到的欄位一律 null / 空陣列，不要臆造。
3. 具體金額填 `price_max`／`budget_total`；相對詞只填 `price_level`，兩者互斥。
4. **`max_width_cm` / `max_height_cm` 只在使用者明講尺寸時才填。**
   ★ 初版實測時模型會用常識推測「沙發應該 220 公分寬」——這是硬過濾條件，猜錯直接砍掉正確結果。
5. `items` 不可為空陣列；只給風格時放 1 個 `category_group = null` 的品項。

## 6. 多物件與預算分配

`budget_total` **依各類別群組的實際中位價按比例分配**，不能平均分：

| 群組 | 中位價 | 佔比 | 6 萬預算 |
| :-- | --: | --: | --: |
| sofa | 18,000 | 47.9% | 28,723 |
| armchair | 8,800 | 23.4% | 14,043 |
| coffee_table | 4,500 | 12.0% | 7,181 |
| rug | 4,400 | 11.7% | 7,021 |
| lighting | 1,900 | 5.1% | 3,032 |

平均分配（每件 12,000）會讓沙發（P25 = 15,300）一件都撈不到。
檢索階段再乘 **1.3 寬容係數**避免硬邊界誤殺，總預算約束留到組合階段。

## 7. 追問行為

`needs_clarification = true` 時**照樣執行檢索並顯示結果**，絕不給空畫面；
追問以提示條顯示，`clarify_options` 直接渲染成按鈕，點下去把選項併入原查詢重跑。

## 8. 實測案例

| 輸入 | 解析結果 |
| :-- | :-- |
| 想要日式侘寂感、預算兩萬內的客廳沙發 | room=living_room, styles=[japanese], moods=[寧靜,自然], items=[sofa, price_max=20000] |
| 想找便宜一點的椅子 | price_level=budget, items=[armchair], **needs_clarification=true**, options=[餐椅/辦公椅/客廳扶手椅] |
| 臥室想弄成 loft 那種調調，牆面深色水泥 | room=bedroom, styles=[industrial], moods=[粗獷,率性], items=[**category_group=null**], 追問想先買哪件 |
