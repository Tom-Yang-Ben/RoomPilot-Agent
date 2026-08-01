# 材質、天花與燈光參考體驗契約

## 目的

第 5、6 步的材質、天花與燈光介面，是讓使用者理解、選擇並確認未來畫面要遵循的視覺與施工語言。它不是商品採購頁，不是施工報價或保證，也不應用看似真實但沒有依據的空房生成圖誤導使用者。

本文件記錄已確認的產品決策。修改相關前端、RAG、Agent payload 或資料來源前，必須遵守本契約。

## 已確認的核心原則

1. 以接近台灣住宅尺度與常見工法的真實完工案例，作為天花、燈光、牆面與地板的主要視覺參考。
2. 真實案例是風格與施工參考，不是商品目錄、特定施工商推薦、工程報價或可保證複製的施工圖。
3. 高品質渲染圖只能作為補充效果示意，必須明確標示「效果示意」；不可偽裝成真實完工案例。
4. 使用者選定案例後，系統傳給 Agent 的是可泛化的視覺效果與工法語言，不是圖片中的精確尺寸、門片、植栽、家具或其他不相關元素。
5. 牆、地板、燈具與可選材質優先從 KAI PostgreSQL 取得；無可用資料時才顯示離線備援，且必須標示為「示意備援」。
6. 示意備援不是可驗證商品、採購品或 GLB；不得宣稱已由資料庫驗證，也不得在 Agent payload 中偽裝成 catalog item。
7. 沒有可用資料庫結果時，介面必須說明缺少的資料與影響，不能只留下空白或把固定樣本寫成推薦。

## 參考卡的內容模型

每張主參考卡必須有：

| 欄位 | 用途 |
| --- | --- |
| `reference_kind` | `real_case` 或 `effect_mockup`。主卡只用 `real_case`。 |
| `reference_image` | 可辨識的真實住宅完工案例圖片。 |
| `visual_language` | Agent 可用的可泛化視覺描述。 |
| `construction_language` | 可理解的施工形式，例如燈槽、單向木格柵、平釘天花。 |
| `visible_features` | 僅描述圖片確實看得到的特徵。 |
| `suitable_spaces` | 適合的空間種類與使用情境。 |
| `constraints` | 需依現場確認的樓高、空調、消防、管線、採光或維護條件。 |
| `selection_status` | `recommended`、`available`、`fallback` 或 `unavailable`。 |

卡片不可顯示與圖片無關的抽象風格句子。文字必須可從 `visible_features`、`construction_language` 或選擇理由追溯。

## 天花案例規則

### 線性燈天花

- 是平釘天花中的線性燈槽或嵌燈語言。
- Agent payload 描述應著重平整頂面、線性光帶、光線方向與空間氛圍。
- 吊頂深度不得以固定 15 cm 宣稱為施工結論；僅能寫成預估範圍與現場確認條件。

### 木格柵天花

- 目前定義為「單向木格柵／木條天花搭配暖色背光或間接光」，不是交叉方格、商業棚架或空白 3D 空房。
- 參考方向應接近台灣住宅入口、走道或局部端景的木條節奏、透光感與引導感。
- Agent payload 可帶入：`single_direction_wood_slats`、`visible_spacing`、`warm_backlighting`、`entry_or_hallway_guidance`。
- 不帶入圖片中的木門、植栽、地板或精確格柵間距，除非使用者另行選擇或明確鎖定。

## 資料庫與備援行為

1. 先以選定色卡、房間類型、用途、色彩與材質偏好查詢 KAI PostgreSQL。
2. 資料庫卡須顯示名稱、資料庫 ID、來源、用途、縮圖與推薦原因；可搜尋、篩選與替換。
3. 「推薦」必須是實際排序/選取結果，不可只以綠色文字附加在固定樣本後。
4. 無資料庫結果時，顯示原因和後果，例如「目前資料庫沒有可用的木格柵參考材質；可選示意備援，但不會作為可採購或 GLB 資料送出」。
5. 使用者可選示意備援繼續流程；Agent payload 必須寫入 `source: fallback_reference` 與 `catalog_verified: false`。

## Agent 資料契約

送往 Agent 的每個已選參考項目至少包含：

```json
{
  "reference_kind": "real_case",
  "visual_language": ["single-direction wood slats", "warm indirect backlighting"],
  "construction_language": ["wood slat ceiling", "concealed linear lighting"],
  "constraints": ["confirm ceiling height", "coordinate HVAC and fire systems"],
  "source": "kai_postgres|fallback_reference",
  "catalog_verified": true
}
```

Agent 必須將這些欄位轉成生圖提示的視覺限制；不得把參考圖中未選定的家具、植物、門片或精確尺寸當成強制需求。

## UI 驗收標準

1. 主要天花參考圖為真實住宅案例，畫面可辨識且不使用裁切過度的空房生成圖。
2. 所有參考圖保持完整內容：依原始圖片比例使用 `object-fit: contain`，不可裁掉關鍵文字或施工特徵。
3. 卡片文字與圖像一一對應，使用者能說出照片中哪個特徵是被選擇的原因。
4. 資料庫結果、推薦結果與示意備援具有明確不同的來源標示。
5. 沒有資料庫結果或資料不相容時，顯示原因、可採取的下一步，以及對家具配置和生圖的影響。
6. 選擇參考圖後，使用者可在送往 Agent 前檢查並修改其摘要。

## 實作狀態

| 項目 | 狀態 |
| --- | --- |
| 色卡圖不裁切關鍵邊緣 | 已完成：3:2 `contain` 顯示。 |
| 固定樣本改為真實案例主卡 | 待實作。 |
| KAI PostgreSQL 材質/燈具查詢與結果卡 | 待實作。 |
| 資料庫優先、示意備援與來源標示 | 待實作。 |
| 天花案例轉成 Agent 視覺/工法語言 | 待實作。 |
| Agent payload 的 `catalog_verified` 與 `fallback_reference` | 待實作。 |
| 生圖前可編輯的參考摘要 | 待實作。 |

## 禁止事項

- 不得把固定 demo 樣本稱為資料庫推薦。
- 不得把效果示意稱為真實案例或可採購產品。
- 不得把單向木格柵與交叉方格天花混為同一選項。
- 不得以固定吊頂深度取代現場條件確認。
- 不得讓 Agent 將未選定的參考圖片元素當成必要生圖內容。

## 2026-07-31 Confirmed Room-First Decisions

This section is normative. It records the confirmed product decisions so a
future implementation must not silently return to a whole-home-only finish
flow.

### Per-room ownership and migration

1. Wall, floor, ceiling, lighting, and their related reference choices belong
   to one `room_id`, never only to a whole-home default.
2. When opening a legacy project, copy its existing whole-home finish values
   into every detected room as that room's initial draft. After migration,
   changing one room must not mutate another room.
3. A room is eligible for step 6 only after the user explicitly confirms that
   room's finish draft. The UI must identify every incomplete room and explain
   what remains to be selected; it must not send an ambiguous whole-home value.
4. A clearly named "apply to selected rooms" action is allowed as a shortcut,
   but it must show target rooms and require confirmation. It is not the
   default editing behavior.

### Material truthfulness and reference presentation

1. A selectable database material needs a stable material ID, exact swatch
   asset, material category, source/provenance, and the room selections that
   use it. Label, image, color, and recommendation must refer to the same
   record.
2. Do not reuse one texture thumbnail for several differently named materials.
   A fallback may be shown only when labelled as a fallback reference, never as
   catalog-verified stock.
3. Each material choice is shown in two linked layers:
   - **Material sample:** a close, uncropped, repeatable swatch which allows
     the user to inspect grain, joints, surface texture, and reflectance.
   - **Style / construction reference:** a realistic Taiwan-residential image
     showing the same visual effect installed at room scale. It is educational
     reference, not a product claim, quotation, or construction guarantee.
4. A color field may tune the selected material only where the material is
   tintable. It must never replace wood, stone, tile, or textured coating with
   a flat color block.
5. Recommendations must be traceable: show why the material suits the chosen
   room and style, and distinguish a live KAI PostgreSQL result from a local
   fallback reference.
6. The room-first questionnaire initially shows the three most suitable wall
   choices and the three most suitable floor choices. A separate "browse
   database materials" dialog exposes further eligible records; the compact
   room page must never imply that the three recommendations are the only
   possible selections.
7. The material-selection section includes a deterministic **front-cut,
   half-cube material preview**: the viewer looks into an open-front room box
   with a ceiling plane, left wall, back wall, right wall, and a trapezoidal
   floor converging to a vanishing point. Every visible plane uses the exact
   selected texture at a believable repeat scale. It appears before the
   selectable material lists. It is explicitly a neutral selection aid, not a
   simulation of the user's room. It updates while the draft changes and is
   persisted only after "confirm this room".
8. The user's own room remains the authoritative preview. After confirmation,
   the exact selected materials must be applied to its 2D+3D model so the user
   can verify furniture, daylight, windows, and spatial scale.
9. The legacy flat material-atmosphere preview is not displayed. Wall and
   floor comparison happens only through the interactive paired mini-room
   previews; ceiling construction and lighting remain separate selectors.
10. Recommendation eligibility requires a readable exact swatch and texture.
    Records without usable assets are not eligible for recommendation. The
    user interface supplies a domain-level retry path without exposing source
    or infrastructure diagnostics.

### Ceiling-reference set

The initial Taiwan residential reference library contains exactly these seven
construction languages: exposed structural ceiling; flat suspended gypsum-board
ceiling; flat ceiling with recessed downlights; indirect cove-lighting ceiling;
recessed linear-light channel; localized shaped ceiling / beam wrap; and
single-direction wood-slat ceiling. Each must use a separate, realistic image,
not a collage or a generic empty showroom.

The current six selectable ceiling-construction cards use the existing
real-residential atlas at
`backend/server/static/questionnaire_images/ceiling-reference-real-homes-v1.png`.
It is a six-panel reference atlas for bare ceiling, flat ceiling, indirect cove,
floating ceiling, linear-light ceiling, and wood slat ceiling. It must remain
the questionnaire asset until a complete licensed seven-card replacement is
available; do not replace it with a generic empty-room montage.

### Questionnaire hierarchy and UX

1. The first questionnaire page collects only whole-home context: household,
   budget, living pattern, project status, and non-negotiable constraints. It
   must explicitly state that these are recommendation inputs and do not
   overwrite room-level finishes or configurations.
2. The user selects exactly one whole-home style family at this stage from six
   realistic Taiwan-residential reference images: Scandinavian, Japanese,
   modern minimal, cream, industrial, or contemporary American. This choice
   fixes the recommendation language for every room; room-level edits may
   choose materials, ceiling construction, and lighting only within that
   style family and must not silently change the whole-home family.
3. Step 7 presents exactly three palette directions for the already selected
   style family. Each palette is a distinct, realistic room-scale image and a
   coherent set of wall, floor, furniture, lighting, and accent colors. It is
   not another whole-home style chooser. Once the user confirms one palette,
   it is the single palette sent with the selected configuration to the render
   agent.
4. Labels, supporting text, and primary-action text must name the data actually
   shown on the page. Do not claim that the page edits equipment or shared
   finishes when those controls are absent.
5. Avoid a dense two-column dump of unrelated selects. Show one meaningful
   decision group at a time, explain its downstream effect, and preserve an
   explicit progress and confirmation state.

### Whole-home style-card comparison

1. All six style cards use the same realistic Taiwan apartment living-room
   framing, viewpoint, and daylight condition so the user compares style rather
   than room type, camera angle, or time of day.
2. Each card has at least two visible, buildable identifiers. The current
   identifiers are: Scandinavian (light oak, whitespace, natural light);
   Japanese (low furniture, wood slats, paper light); modern minimal (stone,
   clean lines, concealed storage); cream (arches, soft matte finish, warm
   ivory); industrial (concrete, black steel, leather); and American (wall
   moulding, walnut, classic furniture).
3. A card shows only the style name and one concise identifier line. Shared
   workflow explanation, including the Step 7 palette decision, appears once
   above the grid and is never repeated inside every card.
4. The legacy overall-style select is not displayed. Selecting a card remains
   the canonical source of the persisted `overallStyle` recommendation value,
   so API payloads and RAG behaviour stay unchanged.

### Confirmed end-to-end style and render sequence

1. Step 1 selects one of six whole-home style families. It is the shared
   recommendation constraint, not a per-room palette chooser.
2. Step 5 confirms each room's use, furniture, wall, floor, ceiling, and
   lighting within that selected family.
3. Step 6 compares the combined 2D+3D A/B configuration for each room, then
   allows the user to choose and micro-adjust the final configuration.
4. Step 7 shows exactly three visual palette cards from the selected style
   family next to the final configuration and view controls. The user must
   select one card before the configuration and render view can be locked.
5. Step 8 sends only that Step 7 palette card, the locked configuration,
   questionnaire context, and locked views to the remote render agent for a
   low-resolution confirmation render. It must not expose a second palette
   picker or silently change the chosen card.
6. Once the palette confirmation is accepted, every final room render uses the
   same selected palette. The persisted agent brief records the questionnaire,
   configuration snapshot, selected palette ID, and each room view.

### Data-source resilience

1. KAI PostgreSQL and RAG are the preferred sources. When either is unavailable,
   the application automatically uses the locally available catalog or rule
   fallback without asking the end user to choose a source.
2. Data-source provenance, connection failures, and fallback transitions are
   operational diagnostics only. They are logged for developers and are not
   shown as database, connection, test, or fallback labels in the user UI.
3. If neither source can provide a usable eligible item, the user sees an
   actionable domain message such as "找不到符合目前條件的項目，可調整需求後重試".
   The UI must not expose underlying infrastructure failure terminology.

### Per-room RAG refresh rule

1. Confirming a room runs that room's RAG recommendation once and does not
   block the user from continuing the questionnaire.
2. Later changes to furniture position, selected wall/floor material, lighting,
   or other configuration appearance do not rerun RAG.
3. A change to use, occupants, requested furniture, dimensions, non-negotiable
   conditions, or free-text need makes a fresh recommendation useful, but it
   never runs automatically. The user explicitly requests it with the concise
   action label `重新推薦`; nearby help text explains that it uses the room's
   latest needs.

### Questionnaire furniture coverage

1. Each room's first recommendation preselects the compatible recommended
   furniture. The user can uncheck it, change the variant or quantity, or add
   more items before confirming that room.
2. Every model-backed catalog item remains reachable from that room's concise
   `從家具庫增加` action. The catalog is searched in a dialog rather than dumped
   into the questionnaire, and an added item is immediately selected for the
   current room.
3. The questionnaire's `重新推薦` action is the only user-facing way to refresh
   RAG-derived recommendations after needs change. It never overwrites items
   the user selected or added from the catalog.

### Wall and floor pairing

1. Wall and floor recommendations are always presented as complete pairs.
   A recommendation card applies both finishes together; it must not make the
   user infer a pairing by selecting one item from each independent list.
2. Each pair card contains a Three.js-rendered, open-corner mini-room preview
   using the exact selected wall and floor textures. It is a material-comparison
   aid, not the authoritative room 3D view.
3. Individual wall or floor changes remain available through the material
   search dialogs and are explicitly treated as a custom choice. Ceiling and
   lighting remain independent decisions and are never added to wall-floor
   recommendation pairs.
# Material catalog display rule

- A source texture is not automatically a selectable residential finish. The questionnaire must exclude source assets that cannot truthfully be installed as the advertised surface (for example bark, wallpaper, wicker, or ground studies presented as flooring).
- The displayed material name must describe the installable finish, never expose an import filename or asset code. Where two valid records share a name, distinguish them with Chinese ordinals such as `（一）` and `（二）`.
- Each custom material card uses the exact swatch of that record. The paired
  Three.js mini-room preview is for combination judgement only; the room's
  2D+3D view remains the authoritative spatial preview.
- The interface does not disclose whether a material came from PostgreSQL or local resilience data. It only shows a user-actionable empty state: `找不到符合目前條件的項目，可調整需求後重試。`

## Per-room ceiling and lighting selection

- The per-room questionnaire must not make users infer ceiling construction or lighting from dropdown text alone. It shows the selected ceiling and lighting as two compact photo-backed summaries.
- Selecting either summary opens a focused modal with one photo card per valid construction or lighting option. The image is a reference for that exact option, not a replacement for the room's 2D+3D view.
- The full image grids stay inside the modal so the questionnaire remains scannable and does not compete with the wall/floor spatial material preview.

## Step 5 questionnaire information architecture

1. The questionnaire has three distinct levels: the product workflow, the
   questionnaire stages, and the current room's decision sections. They must
   never be presented as competing, equally prominent progress bars.
2. Questionnaire stages are named `全屋設定`, `逐房需求與材質`, and `全屋確認`.
   The second stage covers furniture, surfaces, ceiling, and lighting; it must
   not be labelled as furniture-only.
3. In the per-room stage, a fixed left context panel contains a small plan and
   each room's status. It distinguishes `空間已確認`, `自動暫存，尚未確認`, and
   `本房需求已確認` rather than treating them as the same state.
4. The main editor displays exactly one of six sections at a time: `房間用途`,
   `設備與畫面需求`, `家具配置`, `牆面與地板`, `天花與照明`, and `檢查並確認`.
   Its navigation shows a compact saved summary for every section.
5. The action area remains visible while editing. It offers previous/next
   section navigation, then exposes the single room-confirmation action only
   in `檢查並確認`. Confirmation continues to run the existing validation and
   persistence path; this layout does not weaken any data gate.
