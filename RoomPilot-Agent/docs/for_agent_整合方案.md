# for_agent 整合方案 —— 採用/丟棄清單、座標轉接、鐵律說明

> 對象:`for_agent/`(多代理室內設計 pipeline skill 包)如何併入 `roompilot/` 產品。
> 定位:整合前的**決策文件與對照表**,不是最終實作。動手前需先拍板 §6 兩件事。
> 撰寫日期:2026-07-08 ・ 依據:`for_agent/SKILL.md`、`for_agent/SCHEMA_審查_V1.md`、`roompilot/engine/*`、`roompilot/server/scene_service.py`
> 相關:團隊 SSOT `docs/RoomPilot_現行版本總覽.md`(F3 Agent、F9 匯出)。

---

## 0. 一句話結論

`for_agent/` 正好補上專案兩個 P0 空缺(**F3 LLM Agent**、**F9 匯出**),但它自帶**一套不同的座標/單位約定**、**重複的確定性腳本**,以及一個**與專案鐵律相反的擺放哲學**。因此**不是 drop-in**:只採用「補空缺」的部分(agent 提示、GLB 匯出、俯視渲染),丟棄與引擎重工的部分(parse_dxf、geometry、validate),中間用一層**座標轉接器**黏合,並維持「家具座標只有引擎能算」的鐵律。

---

## 1. for_agent 對應到專案哪個缺口

| for_agent 提供 | 對應 SSOT 待辦 | 專案現況 |
|---|---|---|
| `agents/agent1~4.md`(需求解析／選家具／排版／驗證修復) | **F3 LLM Agent**(P0,林柏彥主責) | 只有 `engine/schema.py` 的 tool schema 骨架 |
| `scripts/build_glb_scene.py`(牆+家具 → `scene.glb`) | **F9 匯出**(P0) | 完全沒有;server 只發單件 GLB |
| `scripts/render_plan.py`(俯視 PNG 給 agent 看) | 無(F3 多模態自檢可用) | 專案沒有等價物 |
| `scripts/validate_layout.py` + `validation_report.json` | — | 引擎在**擺放當下**驗證,無獨立報告/修復迴圈 |
| `schemas/*.json` + `examples/*.json` | Agent↔引擎 JSON 契約 | `engine/schema.py` 已有部分,可對齊 |

---

## 2. 「家具座標只有引擎能算」鐵律 —— 是什麼、為什麼

### 2.1 鐵律出處與內容

CLAUDE.md「Architecture invariants」第一條:

> **家具座標只有 `roompilot.engine` 能算。** `scene_service.generate_layout` 的類型錨點只是候選順序,合法性由 `check_placement_with_clearance` 把關;放不下回報 `placement.failed`,不硬塞。

拆成三句白話:

1. **LLM / 前端 / 任何非引擎程式,都不得決定家具最終座標。**
2. 允許的只有「**候選建議**」——`generate_layout` 的 `_placement_candidates`(`scene_service.py:404`)給每種家具一組「視覺上合理」的擺放順序(沙發靠下牆、電視櫃靠上牆…),但這只是**試放順序**。
3. 每一個候選都要通過 `check_placement_with_clearance`(`engine/clearance.py:89`)才算數;全數不合法 → 退回引擎網格搜尋 `place_furniture`(`engine/placement.py:9`)→ 再不行才標 `placement_failed`,**絕不硬塞**。

### 2.2 引擎把關實際檢查了什麼(這是鐵律的價值所在)

`check_placement_with_clearance` 是用 **Shapely 多邊形交集**做的、可重現的幾何判斷,不是估算:

| 檢查 | 位置 | 內容 |
|---|---|---|
| 出界 | `geometry.py:62` `out_of_bounds` | 家具旋轉後多邊形必須完整 `within` 房間 |
| 穿牆 | `geometry.py:44` `hits_wall` | 家具多邊形不得與**有厚度的牆多邊形**相交 |
| 家具重疊 | `geometry.py:52` `hits_furniture` | 兩兩本體多邊形不得相交 |
| 開合淨空撞牆/撞家具/互撞 | `clearance.py:56` `clearance_conflict` | 抽屜/門的開合矩形(跟著 rotation 轉)不得撞牆、撞別人本體、撞別人的淨空 |
| 反向淨空 | `clearance.py:105` | 我的本體不得壓到**別人**的開合淨空 |

`scene_service` 還在此之上加了非矩形房間的多邊形包含檢查(`_inside_boundary`、`_grid_place_in_boundary`,`scene_service.py:486/492`),擋掉「落在 bbox 內但實際在牆體裡」的假合法點。

### 2.3 for_agent 的相反哲學

for_agent 的 pipeline(`SKILL.md` §管線總覽)是:

```
Agent 3(LLM 決定每件家具 position/rotation) → 腳本事後 validate → Agent 4 轉修復指令 → 回 Agent 3 重排(最多 5 次)
```

也就是 **LLM 先擺、腳本後驗、驗不過就迴圈重排**。這與鐵律「引擎擺、當場驗、放不下就回報」是**方向相反**的兩種架構。

### 2.4 為什麼推薦保留鐵律(引擎擺放),而非改採 for_agent 迴圈

1. **已經做完、且穩。** 引擎擺放 + 碰撞/淨空是專案**已完成並上線**的部分(F6 拖曳驗證、`/api/scene/layout` 重排都靠它)。SSOT §0.2 明講「配置/微調引擎反而已做、穩」,風險應該壓在 F4 風格生成,不是回頭重寫已穩的擺放。
2. **確定性 = 可重現、可測。** 引擎走 `uv run pytest tests/` 就能驗;LLM 擺放每次結果不同,難測、難重現,Demo 前一晚最不想要的就是「這次剛好擺歪」。
3. **迴圈有成本與震盪風險。** for_agent 自己在 `references/pipeline.md` 花大篇幅處理「防止震盪/死迴圈、卡住偵測、最多 N 次」——這些成本,引擎「一次擺到合法或明確回報失敗」的模型天生沒有。距 Demo(2026-08-20)時間有限,不值得引進。
4. **座標宇宙不同(見 §4)。** 讓 LLM 在 for_agent 的 cm/左下原點/CCW 座標系裡算座標,結果還要轉回專案的 m/中心原點/three 旋轉才能渲染——多一層每次都可能出錯的轉換,而引擎本來就直接產出前端契約座標。
5. **鐵律不擋 LLM 的強項。** LLM 真正擅長的是「理解模糊需求、選風格、決定要哪些家具、成組關係」(這正是 for_agent agent1/2 的價值);「算座標」本就是 LLM 不該做的(for_agent 的 `SKILL.md` §為什麼這樣切分 自己也這麼說)。保留鐵律 = 讓 LLM 做它強的,把幾何交給引擎。

**結論:F3 採「LLM 決定要什麼家具 + 語意約束 → 引擎算座標」,而不是「LLM 算座標 → 腳本驗證迴圈」。** for_agent 的 agent3 職責因此要**改寫**(見 §5)。

---

## 3. 採用 / 丟棄清單

### 🟢 採用(補專案空缺,不與引擎衝突)

| 項目 | 用途 | 落點 |
|---|---|---|
| `agents/agent1_requirement_parser.md` | F3 需求解析 system prompt | 併/取代 `scene_service.build_questionnaire_prompt` |
| `agents/agent2_furniture_selector.md` | F3 選家具 system prompt | 新 `roompilot/agent/` 模組;查型錄走 `catalog/style_db.py` |
| `agents/agent3_layout_designer.md` | **改寫**:只輸出「要哪些家具+語意約束」,不輸出座標 | 新 `roompilot/agent/`,座標交 `generate_layout` |
| `agents/agent4_validator.md` | **改寫**:把引擎的 `placement.failed`/淨空違規轉成自然語言或「換更小家具」指令 | 新 `roompilot/agent/` |
| `scripts/build_glb_scene.py` | **F9 匯出**(淨新增,零衝突) | 包成 `POST /api/scene/export` |
| `scripts/render_plan.py` | (可選)agent 多模態自檢的俯視 PNG | F3 走多模態才需要,可延後 |
| `schemas/*.json`(修正後) | Agent↔引擎 JSON 契約 | 對齊 `engine/schema.py`;套用 §3.1 修正 |

### 🔴 丟棄(與引擎重工,用專案既有的)

| for_agent 檔 | 用專案的什麼取代 |
|---|---|
| `scripts/parse_dxf.py` | `upgrade3d/dxf_parser.py` + `engine/dxf_room.py`(已聯集牆體、取最大房間) |
| `scripts/geometry.py` | `engine/geometry.py` + `engine/clearance.py`(已是驗證真值,支援旋轉/淨空) |
| `scripts/validate_layout.py` | `check_placement_with_clearance`(擺放當下已驗)。若真要獨立報告,讓它**包引擎**,不要自帶第二套幾何 |
| for_agent 的座標約定(cm/左下/CCW) | 專案約定(m/角落/中心原點/three 旋轉);只在轉接器邊界短暫用 for_agent 座標 |

### 3.1 採用 schema 前必先修正(來自 `SCHEMA_審查_V1.md`)

- `requirement`(單數鍵,非 `requirements`);`prefer_color` 用**陣列**。
- `architecture.room_polygon` 維持**頂層**,不要塞進 `room{}`(否則 within-room 抓不到)。
- `rule.json` 補回 `footprint_cap`(程式有 `check_footprint_ratio` 卻漏這條)。
- **不要**合併成 `layout_result.json`——維持 `furniture.json` + `validation_report.json` 拆分,保留 `metrics` / `suggested_fix`。
- 刪/延後:`coordinate_system`、`ceiling_height`、`wall.normal`、`door.open_angle_deg`、`window.access_clearance_cm`(目前無程式消費)。

---

## 4. 座標轉接公式(黏合層核心)

**這是整合最容易出錯的地方,獨立成 `roompilot/agent/adapters.py`,寫測試。**

### 4.1 三套座標系對照

| | for_agent | 專案 payload(`scene_objects`) | 專案引擎(`PlacedFurniture`) |
|---|---|---|---|
| 單位 | 公分 | 公分(`position_cm`/`size_cm`) | **公尺** |
| 原點 | 平面**左下角** | 房間**中心** | **角落**(0,0) |
| 平面第二軸 | Y 朝上(北,數學慣例) | z(three,+z 朝南/觀察者) | pos_y(第二軸,非高度) |
| 旋轉 | 逆時針度,0°朝 +Y | `rotation_y_deg`(three) | 與 three **相反**(取負) |

已知的專案內換算(payload ⇄ 引擎)在 `scene_service._scene_object_to_placed`(`scene_service.py:569`):

```
引擎 pos_x = (position_cm.x + half_w_cm) / 100
引擎 pos_y = (position_cm.z + half_d_cm) / 100
引擎 rotation = (-rotation_y_deg) % 360
```

其中 `half_w_cm = room.width * 50`、`half_d_cm = room.depth * 50`。

### 4.2 payload `scene_objects` → for_agent `furniture.json`

for_agent 是**左下原點**、Y **朝北**(數學),而 payload z **朝南**(three,見 `scene_service._flip_parsed_z` 的 z 翻轉註解 `scene_service.py:806`)。因此第二軸要**翻向 + 平移**:

```
# 位移部分(可直接推導、寫死)
furniture.position.x = position_cm.x + half_w_cm          # 中心 → 左下
furniture.position.y = half_d_cm - position_cm.z          # 中心+朝南 → 左下+朝北(翻向)
furniture.dimensions.width  = size_cm.width               # 皆 cm,不縮放
furniture.dimensions.depth  = size_cm.depth
furniture.dimensions.height = size_cm.height

# 旋轉部分(結構已知,常數需校準,見下)
furniture.rotation = (rotation_y_deg + ROT_OFFSET) * ROT_SIGN  (mod 360)
```

> ⚠️ **旋轉的 `ROT_OFFSET` / `ROT_SIGN` 必須用 `render_plan.py` 做一次視覺校準,不要憑空寫常數。**
> 原因:三套系統的「0°朝哪」與旋轉正負向都不同(for_agent 0°朝+Y/CCW;three 另一套;引擎又取負)。位移部分可純推導,但旋轉零點是實測題:擺一件明確有正面的家具(如沙發),用 `render_plan` 渲出來看箭頭朝向對不對,校出 `ROT_OFFSET`(多半是 0/90/180/270 之一)與 `ROT_SIGN`(±1),寫進測試鎖住。

反向(for_agent → payload,匯入外部 furniture.json 時)為上式代數反解。

### 4.3 payload `floorplan` → for_agent `architecture.json`(給 build_glb / render_plan)

- **牆**:payload `wall_segments` 是 `{start,end}`(中心原點、公尺)。for_agent 牆要 `position`(中心線中點)+`rotation`+`width`(長度)+`thickness`+`height`。轉換 = `engine/geometry.py:26 wall_polygon` 的**逆運算**:
  ```
  position = 線段中點,各軸 ×100 + half(→ 左下 cm);第二軸同樣 half_d - z 翻向
  width(長度) = hypot(end-start) × 100
  rotation = atan2(dz, dx) 換算(同樣需與 §4.2 一致的校準)
  thickness = 6cm(專案 payload 牆厚 0.06m),height 用預設牆高
  ```
- **門/窗**:`door_segments` / `window_segments` 同樣的 ×100 + 翻向 + 平移。
- **`room_polygon`(頂層)**:由 `floorplan.room_regions`(最大一塊 exterior 環)每點 ×100 + 翻向 + 平移得到。

> 全部共用同一組軸規則:`×100`(m→cm)、`half_d - z`(第二軸翻向並移到左下)、`x + half_w`(第一軸移到左下)。把它寫成一個 `_to_foragent_xy(x_m, z_m, half_w_cm, half_d_cm)` 小函式,牆/門/窗/家具/多邊形全部呼叫它,避免各自解讀(這正是 for_agent `geometry.py` 共用旋轉/平移函式的用意)。

---

## 5. 串接步驟(推薦路徑:拆進 FastAPI)

1. **新增 `roompilot/agent/` 模組**,放 agent1~4 的封裝(system prompt = 對應 `.md`,輸出用 §3.1 修正後的 schema 綁定 structured output)。走現有 OpenRouter 管道(`scene_service._openrouter_request`)。
2. **agent3 改寫**:輸出「家具類型清單 + 語意約束(靠窗/成組/朝向偏好)」,**不含座標**;把清單餵給既有 `generate_layout`(`scene_service.py:666`)由引擎算座標。約束若引擎無法直接吃,先當 `_placement_candidates` 的排序提示。
3. **agent4 改寫**:讀引擎回傳的 `placement.failed` / 淨空違規訊息,轉成「換更小候選 / 移除 / 提示使用者」,而非叫原地微移。
4. **新增 `roompilot/agent/adapters.py`**:實作 §4 全部轉換 + 單元測試(至少涵蓋:一件靠下牆沙發往返轉換座標不漂、旋轉校準值鎖定)。
5. **F9 匯出**:`POST /api/scene/export`,輸入現有 `scene_objects`+`floorplan` → 經 adapters 轉 for_agent `furniture.json`/`architecture.json` → 呼叫 `build_glb_scene.py` → 回 `scene.glb`。GLB 缺檔時它以佔位方塊替代並警告,不中斷(見 `pipeline.md` §錯誤處理),安全。
6. **依賴**:`build_glb_scene.py` 需 `trimesh` + `pygltflib`;`render_plan.py` 需 `matplotlib` + CJK 字型。透過 `pyproject.toml` 的 extras 加(對齊 `server`/`vision`/`catalog` 慣例),不要復活 `requirements.txt`。

---

## 6. 動手前需拍板的兩件事

1. **F3 擺放哲學**:維持鐵律「引擎算座標 + agent3 改寫成只選家具」(**本文件推薦**,理由見 §2.4),還是改採 for_agent「LLM 擺放 + 驗證迴圈」?這決定 `roompilot/agent/` 怎麼寫。
2. **首波範圍**:先只做風險最低的 **F9 GLB 匯出**(淨新增、不動 F3),還是連 **F3 agent 鏈**一起上?

> 建議:先 F9(§5 步驟 4~6),把 adapters + 匯出跑通;F3 agent 鏈另開一輪。理由:F9 淨新增、可獨立驗證,先把最容易出錯的座標轉接器在低風險場景鍛出來,再拿去支撐 F3。

---

## 附:一眼帶走

- for_agent = F3 agent 提示 + F9 匯出 + 俯視渲染的來源;**不是**可以整包 drop-in 的東西。
- 鐵律「引擎算座標」要保留:已做、穩、可測、不震盪;LLM 只做選家具與語意約束。
- 座標三宇宙,轉接器獨立成檔寫測試;**旋轉零點靠 `render_plan` 校準,不憑空寫常數**。
- 丟棄 for_agent 的 parse_dxf/geometry/validate(與引擎重工);採用 agent 提示/build_glb/render_plan。
</content>
</invoke>
