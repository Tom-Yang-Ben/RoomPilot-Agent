# Taiwan Residential StylePack Definition

Source folder: `C:\Users\user\Documents\test1\室內風格色卡_台灣住宅版`

This document turns the 6 style groups and 18 palette cards into implementation-ready StylePack rules for RoomPilot step 9. A StylePack is not only a palette. It must drive wall/floor PBR materials, furniture replacement candidates, decor, lighting, camera mood, and protection rules for user-specified furniture.

## Global Contract

Each card maps the four visible swatches to:

1. `wall`: main wall color and wall PBR material.
2. `soft`: fabric/curtain/rug color and fabric roughness.
3. `wood_or_floor`: floor, cabinet, and major wood tone.
4. `accent`: accent furniture, decor, plant, metal, leather, or feature color.

User-specified furniture is protected:

- `model_locked`: never replace the GLB when switching style.
- `material_locked`: keep user-selected color/material.
- unlocked system furniture can be replaced by same room role and same style candidate.
- fixed equipment such as sanitary fixtures, kitchen sink, wall openings, windows, and doors are not style-replaced.

## Shared Rendering Profiles

| Profile | Use | Three.js/PBR settings |
|---|---|---|
| `soft_daylight` | 北歐、奶油、日式自然 | HDR apartment daylight, 4000-4300K, environment 1.05, contact shadow 0.50, GTAO 1.1, ACES |
| `warm_evening` | 奶油、日式茶室、美式溫馨 | HDR warm interior, 3000-3400K, environment 0.9, key light warm, contact shadow 0.58 |
| `gallery_neutral` | 現代簡約、現代輕奢 | HDR neutral studio, 4300-4800K, environment 1.0, stronger reflections, GTAO 1.2 |
| `industrial_contrast` | 工業風 | HDR low-key studio, 3600-3900K, environment 0.82, contact shadow 0.68, stronger metal reflection |

## Style Groups

### 01 北歐

Core design language: bright, light wood, soft fabric, low visual weight, plants, woven texture, modular sofa, simple open storage. Avoid heavy dark walls and glossy luxury finishes.

| Card | Palette Mapping | Materials | Furniture Rules | Decor/Lighting |
|---|---|---|---|---|
| `scandinavian_natural_wood` / 北歐 自然木質 | wall `暖白`, soft `燕麥米`, floor `淺橡木`, accent `鼠尾草綠` | mineral warm white wall, light oak floor/cabinet, oatmeal linen fabric, matte sage accent | modular fabric sofa, low light-oak TV bench, rectangular or rounded light-oak coffee table, slim wood dining table | woven pendant, plants in corner, linen rug, sheer curtain |
| `scandinavian_bright_fresh` / 北歐 清新明亮 | wall warm white, soft pale beige, floor pale oak, accent blue-green/soft green | brighter mineral paint, pale oak, cotton/linen fabric | compact low-arm sofa, round coffee table, open shelf, light dining set | white sheer curtain, light pendant, small plants |
| `scandinavian_low_saturation` / 北歐 低彩度質感 | wall greige white, soft gray-beige, floor muted oak, accent gray/olive | greige limewash, muted oak floor, textured gray fabric | straight but soft-edged sofa, low media cabinet, simple side table | low saturation rug, framed botanical art, warm indirect light |

Placement rules:

- Living room sofa faces TV/main wall and should sit on a rug zone.
- Keep window side visually light: no tall dark cabinet in front of window.
- Add plants near balcony/window if clearance allows.

### 02 日式

Core design language: low furniture, natural wood, calm empty space, paper/woven lighting, sliding-door feeling, muted earth tones. Avoid glossy metal, oversized sofa, and high-contrast decoration.

| Card | Palette Mapping | Materials | Furniture Rules | Decor/Lighting |
|---|---|---|---|---|
| `japanese_wabi_nature` / 日式 侘寂自然 | wall clay beige, soft raw linen, floor pale natural wood, accent moss/stone | limewash/clay wall, pale wood floor, linen/cotton fabric, matte ceramic | low platform bed, low table, simple wood shelf, floor cushion if appropriate | paper pendant, ceramic vase, minimal branch/plant |
| `japanese_tea_zen` / 日式 茶室禪意 | wall warm beige, soft tatami beige, floor medium wood, accent tea brown/olive | earth plaster wall, medium oak/walnut, tatami-like textile | low dining/tea table, bench or low chair, wood slat cabinet | paper lantern, indirect warm lighting, minimal decor |
| `japanese_modern_wa` / 日式 現代和風 | wall warm white, soft gray beige, floor clean oak, accent charcoal/wood | smoother mineral wall, oak floor, matte black small accents | low clean sofa, platform bed, slatted cabinet, compact dining table | linear paper pendant, concealed warm lighting |

Placement rules:

- Prefer low profiles and clear circulation.
- Bed against longest quiet wall; if space allows, add one low nightstand instead of two bulky units.
- Avoid filling every wall; preserve empty wall surfaces.

### 03 現代簡約

Core design language: clean geometry, fewer objects, controlled contrast, integrated storage, linear lighting, stone/gray/white materials. Avoid decorative clutter and overly rustic surfaces.

| Card | Palette Mapping | Materials | Furniture Rules | Decor/Lighting |
|---|---|---|---|---|
| `modern_minimal_black_white` / 現代簡約 黑白俐落 | wall crisp white, soft light gray, floor stone gray, accent black | smooth mineral wall, gray tile/microcement floor, matte black metal | low black/white TV console, clean rectangular sofa, glass/stone coffee table | track/linear light, minimal art, no heavy plants |
| `modern_minimal_warm_gray` / 現代簡約 暖灰質感 | wall warm gray-white, soft taupe, floor warm gray wood/stone, accent bronze/walnut | warm gray limewash, stone gray tile, taupe fabric | modular sofa, slim cabinet, rounded rectangle table | indirect light, warm metal accent |
| `modern_minimal_natural_blank` / 現代簡約 自然留白 | wall warm white, soft beige, floor pale oak/stone, accent muted brown | warm white paint, pale oak, matte fabric | fewer pieces, integrated low storage, simple bed/dining forms | concealed light, single statement decor |

Placement rules:

- Strong alignment to walls and axes.
- Furniture count should be lower than other styles.
- Prefer built-in or wall-aligned storage; avoid scattered small pieces.

### 04 奶油風

Core design language: warm beige, soft curves, rounded furniture, creamy fabric, subtle French details, soft light. Avoid black-heavy contrast and exposed industrial hardware.

| Card | Palette Mapping | Materials | Furniture Rules | Decor/Lighting |
|---|---|---|---|---|
| `cream_milky_white` / 奶油風 奶油米白 | wall milk white, soft cream fabric, floor light warm wood, accent beige/tan | limewash milk wall, light oak floor, boucle/linen fabric | curved sofa, round coffee table, rounded dining chair, upholstered bed | warm pendant, sheer curtain, soft rug |
| `cream_french_mist` / 奶油風 法式柔霧 | wall warm ivory, soft blush beige, floor pale stone/wood, accent muted brass | smooth warm wall, pale stone or oak, brass low gloss | curved sofa, arched/round mirror, elegant dining set | small chandelier/pendant, cove light, wall molding if available |
| `cream_milk_tea_wood` / 奶油風 奶茶木質 | wall cream beige, soft oatmeal, floor milk-tea wood, accent caramel | cream mineral wall, warm oak/walnut-light floor, textured fabric | warm wood cabinet, soft-edge sofa, rounded table | warm indirect light, linen curtain |

Placement rules:

- Use curves where possible: round tables, rounded sofa/chairs.
- Add rug under main seating; avoid sharp high-contrast blocks.
- Lighting should be warm and soft, not cool daylight.

### 05 工業風

Core design language: concrete, black iron, dark wood, leather, track light, open shelving, strong contrast. Avoid delicate pastel soft styling and overly bright white scenes.

| Card | Palette Mapping | Materials | Furniture Rules | Decor/Lighting |
|---|---|---|---|---|
| `industrial_black_iron_concrete` / 工業風 黑鐵水泥 | wall concrete gray, metal black, wood dark walnut, accent leather brown | concrete wall/microcement floor, black metal, dark walnut, brown leather | leather sofa, black iron shelf, black media cabinet, dark wood coffee table | track light, mesh cabinet, exposed shelf |
| `industrial_vintage_workshop` / 工業風 復古工坊 | wall aged gray/beige, metal black, wood vintage brown, accent copper/leather | aged plaster/concrete, dark reclaimed wood, black/copper metal | leather chair, workbench-like table, open shelf | warm filament pendant, black track |
| `industrial_minimal_cool` / 工業風 極簡冷調 | wall cool gray, floor microcement, furniture black/gray, accent dark wood | cool concrete, microcement, matte black metal | simpler black furniture, straight sofa, minimal open shelf | cooler track light, sparse decor |

Placement rules:

- Open shelving can occupy long wall; keep it aligned and not floating randomly.
- Leather sofa or dark sofa anchors living room.
- Track lights align with long axis or main circulation.

### 06 美式

Core design language: comfortable, larger furniture, symmetry, warm wood, panel/molding feeling, classic lamps, layered soft furnishings. Avoid ultra-minimal empty rooms.

| Card | Palette Mapping | Materials | Furniture Rules | Decor/Lighting |
|---|---|---|---|---|
| `american_country_warm` / 美式 鄉村溫馨 | wall warm ivory, soft beige fabric, floor medium warm wood, accent sage/blue | warm wall paint, medium oak/walnut floor, cotton/linen fabric | large sofa, armchair, wood coffee table, sideboard | table lamp, curtain, patterned rug, framed art |
| `american_classic_elegant` / 美式 經典優雅 | wall ivory, soft muted blue/gray, floor walnut, accent brass/deep blue | ivory wall with molding, walnut floor, fabric/leather, brass | symmetrical sofa/chairs, classic dining table, cabinet with panels | chandelier/pendant, table lamps, framed art |
| `american_modern_luxe` / 美式 現代輕奢 | wall soft white, soft gray/beige, floor walnut/stone, accent brass/black | smooth wall, walnut or stone floor, brass metal, glass | cleaner large sofa, marble/glass coffee table, metal accent table | warm neutral lighting, brass fixture, refined decor |

Placement rules:

- Prefer symmetry in living/dining rooms.
- Add side tables and lamps if space allows.
- Furniture can be larger than Scandinavian/Japanese, but must preserve clear circulation.

## Implementation Mapping

Recommended code target:

- `roompilot/server/static/scene_style_packs.js`
  - replace the current lightweight `STYLE_PACKS` card metadata with the full fields below.
  - keep existing `STYLE_MATERIAL_OPTIONS`, but derive it from card materials.

Each card should eventually export:

```js
{
  id: "scandinavian_natural_wood",
  styleId: "scandinavian",
  name: "自然木質",
  sourceImage: "/static/style_cards/01_北歐/01_北歐_自然木質.webp",
  palette: ["#F7F3EA", "#D9CBB9", "#D8B17A", "#7E8B68"],
  wall: {
    color: "#F7F3EA",
    surfaceOption: "warm_white",
    pbr: { material: "mineral-paint", roughness: 0.88, metalness: 0, normalScale: 0.12 }
  },
  floor: {
    color: "#D8B17A",
    surfaceOption: "light_oak",
    pbr: { material: "oak-plank", roughness: 0.48, metalness: 0, reflection: 0.24 }
  },
  furniture: {
    color: "#D9CBB9",
    accent: "#7E8B68",
    materialLanguage: ["light_oak", "linen", "rattan", "matte_ceramic"],
    replacementPolicy: "same-style-unlocked-only"
  },
  furnitureRules: {
    sofa: ["modular_fabric_sofa", "low_arm_linen_sofa"],
    coffeeTable: ["light_oak_rect_table", "round_light_oak_table"],
    tvBench: ["low_light_oak_tv_bench"],
    lighting: ["rattan_pendant", "warm_floor_lamp"],
    decor: ["linen_rug", "plant", "botanical_wall_art"]
  },
  placementRules: {
    livingRoom: { rug: true, plantsNearWindow: true, keepWindowClear: true },
    bedroom: { lowVisualWeight: true, warmWoodStorage: true }
  },
  lighting: {
    profile: "soft_daylight",
    hdr: "apartment-daylight",
    colorTemperatureK: 4200,
    environmentIntensity: 1.05,
    contactShadow: 0.5,
    gtaoIntensity: 1.1,
    toneMapping: "ACESFilmic"
  }
}
```

## Acceptance Criteria

- Choosing a card changes wall/floor/furniture materials, not only colors.
- Unlocked furniture is replaced by same role and same style when available.
- User-specified furniture keeps model/material locks.
- The 3D viewer lighting changes with the card profile.
- Style cards show the source image or compressed preview.
- Wall and floor material choices are filtered by the selected style/card.
- A living room should visibly differ between 北歐自然木質, 工業黑鐵水泥, and 美式經典優雅 without changing the floor plan.
