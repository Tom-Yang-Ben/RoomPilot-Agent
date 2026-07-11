---
name: interior-design-pipeline
description: >
  室內軟裝自動化多代理流程。當使用者上傳 2D 平面圖(DXF)並描述房間風格與家具需求,
  想要自動「解析需求 → 選家具 → 排版布置 → 驗證 → 產生 3D 場景 / GLB」時使用此技能。
  觸發詞包括:室內設計、軟裝、平面圖、DXF、家具擺放、家具布置、擺設、3D 場景、GLB、
  requirement.json、architecture.json、furniture.json、rule.json,或任何提到「幫我把這間
  客廳/臥室/書房布置成某風格」的請求。即使使用者只提到其中一個階段(例如「幫我驗證家具有沒有
  重疊」或「把家具放進平面圖」),也應使用本技能,以確保各階段輸出格式一致、能串接成完整管線。
---
# 室內軟裝自動化多代理流程 (Interior Design Pipeline)

把「一張 2D 平面圖 + 一段自然語言需求」轉成「一個布置好家具、可驗證、可輸出 GLB 的 3D 場景」。
整條管線由 4 個 LLM 代理 (agent) 與 3 個確定性腳本 (script) 組成。

## 為什麼這樣切分

**LLM 擅長的**:理解模糊需求、把自然語言正規化、依風格/情境做設計判斷(哪張椅子配哪張桌、
朝向是否合理)。這些交給 agent。

**LLM 不該做的**:讀二進位 DXF、算幾何重疊、算走道寬度、組 GLB。這些是確定性計算,交給腳本,
既精準又可重現。特別是「驗證」——是否重疊、走道是否 ≥ 60cm、是否超出牆界——**必須用幾何計算**,
不能靠 LLM 目測。因此 agent 4 的核心是 `scripts/validate_layout.py`,LLM 只負責把違規報告
轉成給 agent 3 的可執行修改指令。

## 管線總覽

```
使用者輸入 (2D 平面圖 DXF + 需求文字)
        │
        ▼
[Agent 1  需求解析] ──────────────────────────► requirement.json
        │
        ▼
[Script  parse_dxf.py] ───────────────────────► architecture.json
        │
        ▼
[Agent 2  家具挑選]  ← rule.json + requirement.json + 家具資料庫查詢
        │                                        └► furniture_candidates.json
        ▼
[Agent 3  版面布置]  ← architecture.json + furniture_candidates.json
        │                              (+ 上一輪 plan.png 做視覺定位)
        │                                        └► furniture.json
        ▼
┌────────────────────────────────────────────────┐
│ [Script render_plan.py]  渲俯視平面圖            │
│  ← architecture.json + furniture.json           │
│  └► plan.png(給 agent 看)+ plan.svg(給人看)   │
│                                                 │
│ [Script validate_layout.py]  幾何 + 規則驗證     │
│  ← rule.json + requirement.json                 │
│    + furniture.json + architecture.json         │
│  └► validation_report.json                      │
│                                                 │
│  passed? ── 否 ──► [Agent 4:看 plan.png(套疊    │
│    │                違規)+ 讀 report → 轉修改指令]│
│    │                    └─► 回到 Agent 3 重排     │
│    │              (最多 N 次;超過則升級給使用者)  │
│    └── 是 ──► 繼續                                │
└────────────────────────────────────────────────┘
        │
        ▼
[Script  build_glb_scene.py] ← architecture.json + furniture.json
        └► scene.glb (含牆體 + 依 glb_path 放入的家具)
```

## 執行步驟

依序執行。每一步的完整規格見括號內指定的檔案。

1. **Agent 1 — 需求解析**
   讀取 `agents/agent1_requirement_parser.md` 作為系統提示,輸入使用者需求文字,輸出
   `requirement.json`(schema 見 `schemas/requirement.schema.json`)。
2. **DXF → architecture.json**(確定性)

   ```bash
   python scripts/parse_dxf.py --dxf 平面圖.dxf --out architecture.json
   ```

   輸出 wall / window / door 的 `id`、`position`、`rotation`、`width`,以及推導出的房間
   多邊形 `room_polygon`(供後續 within-room 驗證使用)。
3. **Agent 2 — 家具挑選**
   讀取 `agents/agent2_furniture_selector.md`。輸入 `rule.json` + `requirement.json`,
   依 `style`/`room_type`/`prefer_color` 與 include/exclude 條件呼叫家具資料庫查詢工具,
   整理出候選清單 `furniture_candidates.json`。**此步需要一個資料庫查詢工具**;若管線中沒有,
   見下方「資料庫查詢工具」一節。
4. **Agent 3 — 版面布置**
   讀取 `agents/agent3_layout_designer.md`。以資深軟裝設計師身分,輸入 `architecture.json`

   + `furniture_candidates.json`(第一次)或 + 上一輪的修改指令(重排時),為每件家具決定
     `position`、`rotation`,輸出 `furniture.json`。
5. **渲俯視平面圖**(確定性,給 agent 一雙眼睛)

   ```bash
   python scripts/render_plan.py \
     --architecture architecture.json --furniture furniture.json \
     --out plan            # 產生 plan.svg(母檔)+ plan.png(給 agent)
   ```

   純 JSON 讓 agent「算得對」卻「看不到」——朝向錯置、對齊歪掉、燈卡在動線這類
   錯誤,座標上不違規但一眼可辨。這步把當前布置渲成俯視正投影 PNG,標好每件家具的
   `id` 與朝向箭頭,交給 Agent 3(自檢)與 Agent 4(判讀)。**PNG 是視覺輔助,不是真值;
   真值永遠是 `furniture.json`。** 影像模型讀不了 GLB/DXF,平面問題也只需俯視 2D,不需 3D。
6. **驗證迴圈**(確定性驗證 + Agent 4 轉譯)

   ```bash
   python scripts/validate_layout.py \
     --furniture furniture.json --architecture architecture.json \
     --rules rule.json --requirement requirement.json \
     --out validation_report.json
   # 未通過時,渲一張套疊違規的圖給 Agent 4 判讀:
   python scripts/render_plan.py --architecture architecture.json \
     --furniture furniture.json --report validation_report.json --out plan_flagged
   ```

   - `passed == true` → 進入第 7 步。
   - `passed == false` → 把 `validation_report.json` 與 `plan_flagged.png`(違規物件已紅框標示)
     一起交給 Agent 4(`agents/agent4_validator.md`),它把每筆違規轉成給 Agent 3 的具體
     修改指令(哪個 `id`、違反哪條、往哪個方向移多少),回到第 4 步重排。
   - 迴圈上限預設 **N = 5**。超過仍未通過就停止並把剩餘違規回報使用者,不要無限迴圈。
     詳細迴圈控制見 `references/pipeline.md`。
7. **產生 3D 場景 / GLB**(確定性)

   ```bash
   python scripts/build_glb_scene.py \
     --architecture architecture.json --furniture furniture.json \
     --out scene.glb
   ```

   依 `architecture.json` 建牆體/開口,依 `furniture.json` 每件家具的 `glb_path`、
   `position`、`rotation` 載入並擺放對應 GLB,合併輸出 `scene.glb`。

## 各檔案的角色

| 檔案                          | 產生者             | 內容                                                  |
| ----------------------------- | ------------------ | ----------------------------------------------------- |
| `requirement.json`          | Agent 1            | 正規化後的需求:風格、房型、色調、include/exclude 家具 |
| `architecture.json`         | parse_dxf.py       | 牆/窗/門的幾何 + 房間多邊形                           |
| `rule.json`                 | 人工預先定義       | 硬性規則(走道 ≥60cm、不可重疊、門開合淨空…)         |
| `furniture_candidates.json` | Agent 2            | 符合條件的候選家具(含尺寸、glb_path)                  |
| `furniture.json`            | Agent 3            | 最終布置:每件家具的位置與朝向                         |
| `validation_report.json`    | validate_layout.py | 是否通過 + 違規清單(object_id + 違反項)               |
| `plan.svg` / `plan.png`   | render_plan.py     | 俯視平面圖:svg 給人看、png 給 agent 做視覺定位        |
| `scene.glb`                 | build_glb_scene.py | 最終 3D 場景                                          |

所有 schema 的欄位說明集中在 `references/schemas.md`,對應的 JSON Schema 檔在 `schemas/`,
可直接餵給 agent 當輸出格式約束,或用 `jsonschema` 驗證。`examples/` 內有每種檔案的範例。

## 座標與單位約定(全管線一致,務必遵守)

- 單位一律 **公分 (cm)**;`architecture.json` 的 `units` 欄位標明,不要混用。
- 平面座標系 **X 向右、Y 向上**(數學慣例),原點在平面圖左下角。
- `position` 一律指物件的**中心點**(牆例外:牆的 position 指其中心線中點)。
- `rotation` 為**逆時針角度(度)**,0 度時家具正面朝 +Y。
- 家具 `dimensions`:`width` 沿物件本地 X、`depth` 沿本地 Y、`height` 沿 Z。
- 三維座標軸（3D Coordinate Axes）**X 軸** ：紅色, **Y 軸** ：綠色, **Z 軸** ：藍色。
- 這套約定同時被 `validate_layout.py`(算 footprint)與 `build_glb_scene.py`(擺 GLB)使用,
  三支腳本共用 `scripts/geometry.py` 的旋轉/平移函式以保證一致,agent 也要照此輸出。

## 資料庫查詢工具(Agent 2 需要)

Agent 2 需要一個能依條件查家具的工具。這是使用者環境相依的,本技能不預設實作。請提供一個介面像:

```
search_furniture(style, room_type, color=None, category=None, exclude_categories=None, limit=20)
  → [{catalog_id, name, category, style, color, dimensions{width,depth,height}, glb_path}, ...]
```

若你的環境用向量檢索、SQL 或 REST API 都可以,只要回傳欄位對得上
`furniture_candidates.schema.json`。若管線中還沒有這個工具,先用 `examples/furniture_candidates.json`
的格式手動提供候選,Agent 3 之後的流程即可照跑。

## 依賴

確定性腳本需要以下 Python 套件(見 `scripts/requirements.txt`):
`ezdxf`(DXF 解析)、`shapely`(幾何驗證)、`numpy`、`trimesh` 與 `pygltflib`(GLB 組裝)、
`matplotlib`(渲俯視平面圖;需要 CJK 字型如 Noto Sans CJK 才能正確標中文家具名)。

## 常見裁切

- 只想跑驗證:直接執行 `scripts/validate_layout.py`,不需要前面的 agent。
- 沒有 DXF、只有座標:自己手寫 `architecture.json`(照 schema),跳過 parse_dxf.py。
- 不需要 3D:跑到第 5 步通過即可,`furniture.json` 就是最終布置結果。
