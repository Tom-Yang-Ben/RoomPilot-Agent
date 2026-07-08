# AI Agent JSON Schema 審查報告

> **審查對象**:`for_agent/examples/AI_AGENT_JSON_SCHEMA_V1.md`(提案)
> **對照基準**:`for_agent/examples/*.json`(範例)、`for_agent/schemas/*.json`(JSON Schema)、`for_agent/scripts/*.py`(實際消費程式)
> **審查日期**:2026-07-08
> **方法**:逐欄位比對「MD 提案 ↔ 範例資料 ↔ 正式 schema ↔ 程式實際讀取」,以程式消費為「必要性」的最終判準。
> **行號**:引用 `檔案:行號` 為審查當下狀態(`for_agent/` 為靜態未進版控資料夾)。

---

## 0. 結論先講(TL;DR)

`for_agent/examples/` 裡混了**兩個不同層級**的東西:

| | 內容 | 定位 |
|---|---|---|
| `AI_AGENT_JSON_SCHEMA_V1.md` | 一份**願景提案**,自稱「多人協作資料交換格式 v1」,並明講「不是 `furniture_engine` v0.1 的最小輸入格式」 | 紙上規格 |
| 其餘 5 個 `*.json` | 實際可跑的**範例資料**,對齊 `schemas/*.json`,且被 `scripts/*.py` 真的讀入 | 程式契約 |

**差異的本質**:MD 是一個比現行契約更大的超集,而且在三個地方跟會跑的程式對不上。

一句話總覽:

```
rule.json 幾乎一致
  → requirement / candidates 差在一堆「Agent 提示」欄位
    → architecture 有「會弄壞程式」的結構差異
      → 最嚴重:MD 把 furniture.json + validation_report.json 併成 layout_result.json,
         反而弄丟了修復迴圈依賴的 metrics / suggested_fix
```

差異分四類,全文沿用此圖例:

- 🟢 **必要** — 已被程式消費,必須與 schema 一致
- 🟡 **Agent 提示** — 有價值,但只餵 LLM(Agent 2/3),確定性腳本不吃 → 保留但不進驗證契約
- 🔴 **目前多餘** — 沒有任何程式產出或消費(常常 MD 自己也標「暫不考慮」)→ 可刪或延後
- 🟠 **衝突** — 照 MD 寫會直接弄壞現有腳本或 schema 驗證

---

## 1. 三層真值關係

在判斷「某欄位是否必要」時,真值優先序為:

```
scripts/*.py(程式實際讀取)   ← 最終真值:決定「必要 vs 裝飾」
      ▲
schemas/*.json(jsonschema 契約) ← 決定「格式驗證會不會過」
      ▲
examples/*.json(範例資料)       ← 應驗證通過(但目前有一處沒有,見 §3)
      ▲
AI_AGENT_JSON_SCHEMA_V1.md(提案)← 超集,與上面三層有落差
```

MD 提案是獨立於 `SKILL.md` 管線寫的:它列 5 個檔,並未把 `furniture.json`(擺放輸出)與 `validation_report.json`(驗證報告)當成獨立檔,而是折進一個 `layout_result.json`;也沒提 `architecture.json` 由 `parse_dxf.py` 產生。

---

## 2. 逐檔比對

### 2.1 architecture.json

範例是**扁平**結構、`room_polygon` 在**頂層**;MD 把它塞進 `room{}` 物件並多加一堆欄位。

| MD 欄位 | 範例/schema 有嗎 | 程式讀嗎 | 判定 |
|---|---|---|---|
| `room.room_polygon`(巢狀) | 範例在**頂層** | `geometry.py:96` 讀**頂層** `architecture.get("room_polygon")` | 🟠 照 MD 巢狀 → within-room 驗證抓不到多邊形而崩 |
| `coordinate_system` | ✗ | ✗(約定寫死在 `geometry.py` + `pipeline.md`) | 🔴 全域約定,不該每檔重寫 |
| `schema_version` | ✗ | ✗ | 🔴 目前無值;要加就 5 檔統一加 |
| `room.usable_floor_polygon` | ✗ | ✗ | 🔴 MD 自己寫「暫不考慮」 |
| `room.ceiling_height` | ✗ | ✗(build_glb 用牆高) | 🔴 MD 自己寫「暫不考慮」 |
| `wall.normal` | ✗ | ✗ | 🔴 MD 自承「沒有也能貼牆」 |
| `window.access_clearance_cm` | ✗ | ✗ — 窗前淨空讀 `rule.json` 的 `clearance_cm`(`validate_layout.py:180`) | 🟠 與 rule 重複、且放錯檔 |
| `door.open_angle_deg` | ✗ | ✗ — `door_swing_polygon` 寫死 90°(`geometry.py:89` `math.pi/2`) | 🔴 加了也不會被算 |
| `units` / `walls` / `windows` / `doors` / `hinge` / `swing_in` | ✓ | ✓ | 🟢 必要 |

**重點**:`room_polygon` 巢狀化與 `window.access_clearance_cm` 是這檔的兩個真問題——前者破壞程式,後者跟 `rule.json` 重工。其餘 MD 新欄位連它自己都說先擱著。

### 2.2 requirement.json

| 差異 | 範例 | schema | MD | 判定 |
|---|---|---|---|---|
| 陣列鍵名 | `requirement`(單數) | `requirement`(**required**) | `requirements`(複數) | 🟠 照 MD 寫會過不了 `jsonschema.validate` |
| `prefer_color` 型別 | `"米白色"`(字串) | `array \| null` | `["米白","淺木"]`(陣列) | ⚠️ 範例違反自己的 schema;MD 反而修對了 |
| `constraints.priority_order` | ✗ | ✗ | ✓ | 🟡 只給 Agent 取捨;`check_requirements` 不讀 |
| `constraints.preferred_layout_pattern` | ✗ | ✗ | ✓ | 🟡 純 LLM 提示 |
| `constraints.style_strictness` | ✗ | ✗ | ✓ | 🟡 純 LLM 提示 |
| `constraints.exclude_categories` / `include_categories` | ✓ | ✓ required | ✓ | 🟢 唯一真被消費的約束(`validate_layout.py:221` 起) |
| `constraints.must_keep` / `notes` | ✓(空) | ✓ | ✓ | 🟡 供人/Agent 看,不被驗證消費 |

**重點**:`check_requirements` 只讀 `constraints.exclude/include_categories`;其他(`requirement` 陣列本身、`must_keep`、`notes`、MD 三個新約束)全是給人/Agent 看的。MD 的 `requirements` 拼字差異、以及範例 `prefer_color` 是字串,是兩個要修的不一致點。

### 2.3 furniture_candidates.json

範例每件只有 9 個欄位;MD 幾乎翻倍。

| MD 新增 | 程式讀嗎 | 判定 |
|---|---|---|
| `quantity{min,max,recommended}` | ✗ | 🟡 給 Agent 3 決定放幾件,合理但非必要 |
| `placement_hints{…}`(8 子欄位) | ✗ | 🟡 給 Agent 3 的擺放直覺;**放在候選檔位置正確**,但不該進驗證 |
| `layout_relations[]`(surround / co_locate…) | ✗ | 🟡 成組關係提示,同上 |
| `clearance_zones`(放在**候選**上) | 消費點在 `furniture.json` **輸出**(`validate_layout.py:132`) | 🟠 權威來源應是輸出檔,不是候選 |
| `catalog_id` / `name` / `category` / `dimensions` / `glb_path` | ✓ | 🟢 schema required |
| `role` / `match_reason` / `style` / `color` | ✗(僅供審查) | 🟡 已在範例,無害 |

**重點**:MD 對這檔的加值(`quantity` / `placement_hints` / `layout_relations`)**真的能提升排版品質**,而且放在「Agent 3 的輸入檔」位置正確——但它們是**建議、非驗證**,不能洩漏進 `furniture.json` 或 validator。`clearance_zones` 例外:它的真正歸宿是輸出的 `furniture.json`。

### 2.4 rule.json ↔ MD 的 rules.json

**這檔最一致。** 欄位結構 `id / type / description / severity / params / applies_to` 完全對得上。差異只有:

| 差異 | 判定 |
|---|---|
| 檔名 `rule.json`(單數,schema/程式)vs MD `rules.json`(複數) | 🟠 小命名不一致 |
| 範例多一條 `footprint_cap`(`max_footprint_ratio`,程式有 `check_footprint_ratio`);MD 少這條 | 🔴 MD 漏了一條真規則 |
| MD 討論的未來欄位 `allow_overlap_with` / `support_surface` / `overlap_mode` | 🟡 把 `validate_layout.py:33` 寫死的 `FLAT_CATEGORIES`(地毯/掛畫可重疊)資料化,方向對,但更該放「家具屬性」而非全域 rule |

補充:`applies_to` 目前**連範例/程式都沒真的用**——`_rule_map`(`validate_layout.py:40`)沒依它過濾,check 函式一律套全部家具。這不是 MD 的問題,但值得知道。

### 2.5 🚩 最大分歧:layout_result.json vs (furniture.json + validation_report.json)

MD 提議一個 `layout_result.json`,把現行**兩個檔**併成一個。注意:這個 `layout_result` 在 `schemas/` 和 `examples/` 裡**既無 schema 也無範例**——它只活在 MD 裡。而現行拆法兩邊都有實體檔且被程式讀。

| 現行(可跑) | MD 合併版 | 問題 |
|---|---|---|
| `furniture.json` — Agent 3 的機器真值,`build_glb_scene.py:79` 只吃幾何 | `placed_furniture` | 併檔後把 LLM 敘事混進機器真值檔,易漂移 |
| `validation_report.json.violations{object_id, type, metrics, suggested_fix}` | `violations{objects, value, expected}` | 🟠 **MD 版更弱**:掉了 `type`(rule/requirement)、`metrics`、`suggested_fix`——而 `pipeline.md` 的修復迴圈正是靠 `metrics` + `suggested_fix.min_delta_cm` 讓 Agent 4 算出精確位移。照 MD 走會弄壞迴圈 |
| (無) | `score{style/functionality/…}` | 🔴 沒有任何程式產出或消費 |
| (無) | `reasoning` / `summary` / `status` | 🔴 LLM 敘事,`build_glb` 不看 |
| `validation_report.summary{total,errors,warnings}` | `validation_summary{passed/warning/failed_rules}` | 🔴 與 `violations` 重複 |

**重點**:現行「機器真值 `furniture.json` / 確定性報告 `validation_report.json`」的拆分是**刻意的**;MD 的合併是這份提案裡風險最高的一步——它換來一堆沒人消費的敘事欄位,卻犧牲了迴圈實際依賴的可執行修復資訊。

---

## 3. 附帶發現:範例自身的不一致

不是 MD 造成,但審查中一併發現,建議順手修:

1. **`examples/requirement.json` 的 `prefer_color` 是字串 `"米白色"`,但 `schemas/requirement.schema.json` 定義為 `array | null`** → 範例過不了自己的 schema。MD 用陣列反而是對的。
2. **`applies_to` 在 schema/範例都存在,但 `validate_layout.py` 沒有依它做任何過濾** → 目前是「宣告了但不生效」的欄位。

---

## 4. 「哪些欄位放到別處更好」— 具體建議

1. **`window.access_clearance_cm` → 刪掉,留在 `rule.json`。** 程式讀的是 rule 的 `clearance_cm`(全域一份),per-window 重複又不被消費。除非真要「逐窗覆寫」,否則放 architecture 是錯位。
2. **`coordinate_system` / 座標約定 → 留在 `SKILL.md` / `references`,別進每個 architecture.json。** 全站一次性約定,已寫死在 `geometry.py`。
3. **`room_polygon` → 維持頂層,別塞進 `room{}`。** 否則 `geometry.py:96` 抓不到。要放 `room_type` / `ceiling_height` 可另加頂層欄位,但 `room_type` 已在 requirement / candidates,architecture 再放屬冗餘。
4. **`quantity` / `placement_hints` / `layout_relations` → 留在 `furniture_candidates.json`(位置對),但標記為「Agent 提示、不驗證」。** 別讓它們流進 `furniture.json` 或 validator schema。
5. **`clearance_zones` → 權威版放輸出 `furniture.json`(已在 schema),候選上的只當來源。**
6. **`support_surface` / `allow_overlap_with` → 若要資料化,放「家具/類別屬性」比放全域 rule 好**——「地毯可承載」本質是物件性質,目前寫死在 `FLAT_CATEGORIES`。
7. **`layout_result.json` → 不要合併。** 幾何留 `furniture.json`,驗證留 `validation_report.json`(保留 `metrics` + `suggested_fix`)。若真想要 `score` / `reasoning` / `summary` 這種展示層,另開一個**輕量 presentation 物件**,不要污染機器真值檔。

---

## 5. 行動清單(三桶)

### 🟢 現在就該對齊 schema(真必要)

- architecture:扁平 `room_polygon`、`units / walls / windows / doors`
- requirement:`exclude / include_categories` + 鍵名統一成 `requirement`;把範例 `prefer_color` 改成陣列
- candidates:`catalog_id / name / category / dimensions / glb_path`
- rule:全欄位 + 補回 `footprint_cap`
- 輸出:維持 `furniture.json` + `validation_report.json`(含 `metrics` / `suggested_fix`)

### 🟡 保留為「Agent 提示、不進驗證契約」(能提品質)

- `placement_hints`、`layout_relations`、`quantity`
- `constraints.priority_order` / `preferred_layout_pattern` / `style_strictness`

> 這些是 MD 真正的貢獻,放對檔(候選 / 需求),但別讓確定性腳本依賴它們。

### 🔴 可刪或延後(目前無人消費)

- `coordinate_system`、`usable_floor_polygon`、`ceiling_height`、`wall.normal`、`door.open_angle_deg`、`window.access_clearance_cm`
- `layout_result` 的 `score` / `reasoning` / `validation_summary`
- 會弄壞東西的:`room{}` 巢狀化、`requirements` 複數鍵、`layout_result` 併檔

---

## 附錄:程式消費點對照(必要性依據)

| 欄位 | 消費位置 | 用途 |
|---|---|---|
| `architecture.room_polygon`(頂層) | `geometry.py:96` `room_polygon()` | within-room 邊界 |
| `architecture.walls[].{position,rotation,width,thickness,height}` | `geometry.py:34` / `build_glb_scene.py:47` | 牆 footprint、3D 牆體 |
| `architecture.doors[].{position,rotation,width,hinge,swing_in}` | `geometry.py:79` `door_swing_polygon()` | 門開合掃掠(角度寫死 90°) |
| `architecture.windows[].{position,rotation,width}` | `validate_layout.py:179` `check_window_access()` | 窗前淨空 |
| `rule.params.clearance_cm` | `validate_layout.py:180` | 窗前淨空深度(**非** architecture) |
| `rule.type`(enum) | `validate_layout.py:40` `_rule_map()` | 決定套哪個檢查器 |
| `rule.params.{min_distance_cm,tolerance_cm,max_ratio}` | 各 `check_*` 函式 | 規則門檻 |
| `furniture[].{id,category,position,rotation,dimensions}` | `geometry.py:28` / 全 `check_*` | footprint / 幾何驗證 |
| `furniture[].clearance_zones` | `validate_layout.py:132` `check_clearance_zone()` | 抽拉/開門淨空 |
| `furniture[].{glb_path,position,rotation,dimensions}` | `build_glb_scene.py:79` | 載入模型、擺入場景 |
| `requirement.constraints.{exclude,include}_categories` | `validate_layout.py:221` `check_requirements()` | 需求層違規 |
| `validation_report.violations.{metrics,suggested_fix}` | `pipeline.md` 修復迴圈 → Agent 4 | 算出精確修改量 |

> 未列於此表的 MD 欄位(`score` / `reasoning` / `coordinate_system` / `placement_hints` / `layout_relations` / `quantity` / `wall.normal` / `open_angle_deg` / `access_clearance_cm` / `usable_floor_polygon` / `ceiling_height` …)**目前沒有任何程式讀取**,故列為 🟡(僅 Agent 用)或 🔴(可刪/延後)。
