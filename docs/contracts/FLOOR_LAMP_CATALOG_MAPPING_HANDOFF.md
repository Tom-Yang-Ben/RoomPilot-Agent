# Floor Lamp Catalog Mapping Handoff

Date: 2026-07-31

Purpose: hand this note to another AI/data agent to fix the catalog data mapping for floor lamps. The RoomPilot app currently has floor lamp assets in source files, but the active PostgreSQL catalog payload does not expose any item as `normalized_type = floor-lamp`, so automatic soft decor cannot add a light.

## Current Runtime Symptom

Endpoint affected:

- `POST /api/scene/decorate`

Runtime rule:

- Auto soft decor maps `light` to catalog type `floor-lamp`.
- Code location: `backend/server/main.py`, `_AUTO_DECOR_TYPES`.

Current failure:

- `409 decor_model_missing`
- Reason: the runtime catalog provider returns zero usable `floor-lamp` items.

Current provider status:

```text
ROOMPILOT_CATALOG_PROVIDER=postgres
provider=kai_postgresql
database=roompilot_db
api_view=roompilot.furniture_catalog_current
payload_count=7958
model_count=7958
```

Runtime payload counts from `_furniture_payload_cache()`:

```text
floor-lamp        0 usable 0
lamp              0 usable 0
table-lamp        0 usable 0
work-lamp         0 usable 0
wall-lamp         0 usable 0
ceiling-lamp      0 usable 0
pendant-lamp      0 usable 0
lamp-shades-base  0 usable 0
```

## Old Source Data Has Floor Lamps

The older full appliance/furniture JSON has correctly typed floor lamps:

File:

- `JSON/furniture/all_furniture_appliance_catalog.json`

Counts:

```text
items=10550
type_code/type floor-lamp=116
floor-lamp with GLB URL=116
```

Example old item:

```json
{
  "id": "abo-floor-lamps-18-amazon-brand-rivet-mid-century-modern-standing-floor-lamp-with-white-shade-and-led-light-bulb-58-25-inches-matte-black-and-antique-brass",
  "name_en": "Amazon Brand - Rivet Mid Century Modern Standing Floor Lamp with White Shade and LED Light Bulb - 58.25 Inches, Matte Black and Antique Brass",
  "name_zh": "Amazon 品牌 - Rivet 中世紀現代落地燈，帶白色燈罩和 LED 燈泡 - 148.26 釐米，啞光黑色和古銅色",
  "category": "落地燈",
  "canonical_category_zh": "落地燈",
  "type": "floor-lamp",
  "type_code": "floor-lamp",
  "role": "照明",
  "role_code": "lighting",
  "width_cm": 44,
  "depth_cm": 44,
  "height_cm": 45,
  "glb_url": "https://ddgsm1yg3xikc.cloudfront.net/models/abo/furniture/abo-floor-lamps-18-amazon-brand-rivet-mid-century-modern-standing-floor-lamp-with-white-shade-and-led-light-bulb-58-25-inches-matte-black-and-antique-brass.glb"
}
```

Another high-priority review CSV also has valid floor lamps:

File:

- `scripts/sql/roompilot_high_priority_data_review.csv`

Counts:

```text
rows=1768
type_code floor-lamp=25
floor-lamp with CloudFront URL=25
```

Example rows include:

```text
abo-floor-lamps-02-stone-beam-modern-led-task-floor-lamp-49-h-with-bulb-antique-brass
abo-floor-lamps-03-iluminaci-n-moderna-stone-beam-l-mpara-de-pie-cepillado-inoxidable
abo-floor-lamps-28-amazon-brand-stone-beam-modern-pully-adjustable-living-room-standing-floor-lamp-with-light-bulb-33-x-33-x-64-inches-brushed-dark-brown
abo-floor-lamps-62-amazon-brand-stone-beam-traditional-floor-lamp-with-faux-wood-accent-led-bulb-included-65-h-dark-bronze
abo-floor-lamps-77-amazon-brand-stone-beam-modern-adjustable-floor-lamp-with-bulbs-and-off-white-shade-16-x-19-x-64-inches-dark-bronze
```

## New Cloud JSON Contains Floor-Lamp Assets But Lost Type Code

File:

- `backend/catalog/data/furniture_catalog_cloud_9350.json`

Counts:

```text
items=9350
type/type_code floor-lamp=0
name/id fuzzy floor-lamp matches=120
```

Example new cloud JSON item:

```json
{
  "id": "abo-floor-lamps-18-amazon-brand-rivet-mid-century-modern-standing-floor-lamp-with-white-shade-and-led-light-bulb-58-25-inches-matte-black-and-antique-brass",
  "name_en": "Amazon Brand - Rivet Mid Century Modern Standing Floor Lamp with White Shade and LED Light Bulb - 58.25 Inches, Matte Black and Antique Brass",
  "name_zh": "Amazon 品牌 - Rivet 中世紀現代落地燈，帶白色燈罩和 LED 燈泡 - 148.26 釐米，啞光黑色和古銅色",
  "canonical_category_zh": "落地燈",
  "width_cm": 38.1,
  "depth_cm": 38.1,
  "height_cm": 148,
  "glb_url": "https://ddgsm1yg3xikc.cloudfront.net/models/abo/furniture/abo-floor-lamps-18-amazon-brand-rivet-mid-century-modern-standing-floor-lamp-with-white-shade-and-led-light-bulb-58-25-inches-matte-black-and-antique-brass.glb"
}
```

Problem:

- The item is clearly a floor lamp by `id`, `name_en`, `name_zh`, and `canonical_category_zh`.
- But the canonical type field is missing from this newer cloud JSON.
- If PostgreSQL import or VLM classification uses this newer data without restoring `type_code`, these records can be mapped to wrong categories.

## PostgreSQL Runtime Data Appears Misclassified

The active payload has 34 lighting-ish records by id/name text search, but none are exposed as lighting types. Some `abo-lamps-*` records are mapped to unrelated types:

```text
normalized_type=sofa
furniture_id=abo-lamps-102-amazon-brand-rivet-andrews-contemporary-chair-with-removable-cushions-40-w-light-grey

normalized_type=rug
furniture_id=abo-lamps-169-amazon-brand-stone-beam-quarterfoil-wool-runner-rug-2-3-x-7-6-light-multi

normalized_type=flower-pots-planter
furniture_id=abo-lamps-185-amazon-brand-rivet-mid-century-stoneware-planter-with-wood-stand-8-27-h-light-green-ombre
```

This suggests the import/classification pipeline is not preserving lighting categories from the source taxonomy. It may be deriving type from a noisy folder/category or VLM result instead of the old canonical `type_code`.

## Desired Mapping Contract

For any item that is a floor lamp, the PostgreSQL API view must produce a row that maps through `backend/catalog/postgres_repository.py` into this runtime payload shape:

```json
{
  "furniture_id": "...",
  "normalized_type": "floor-lamp",
  "taxonomy_group": "soft_decor",
  "taxonomy_group_zh": "軟裝與燈飾",
  "taxonomy_type_zh": "落地燈",
  "role": "lighting",
  "catalog_role": "lighting",
  "has_model": true,
  "model_url": "https://ddgsm1yg3xikc.cloudfront.net/models/...glb",
  "size_cm": {
    "width": 38.1,
    "depth": 38.1,
    "height": 148
  }
}
```

Important repository mapping:

- `postgres_repository._row_to_catalog_item()` sets runtime `normalized_type` from:

```python
row.get("normalized_type") or _TYPE_ID_MAP.get(raw_category_code, raw_category_code)
```

Therefore the fix can happen in either:

1. PostgreSQL view/import data: set `normalized_type = 'floor-lamp'` for these records.
2. Or source import mapping: ensure `source_type/category_code/type_code` maps to `floor-lamp`.

Preferred fix: update the source-of-truth/import pipeline so the PostgreSQL view emits the correct canonical type, not a runtime-only patch.

## Suggested Matching Rules

Use source taxonomy first:

- If old `JSON/furniture/all_furniture_appliance_catalog.json` has the same `id` with `type_code = floor-lamp`, preserve that value.
- If `scripts/sql/roompilot_high_priority_data_review.csv` has the same `item_id` with `type_code = floor-lamp`, preserve that value.

Fallback heuristics for missing type code:

- `canonical_category_zh = '落地燈'` => `floor-lamp`
- `id` starts with `abo-floor-lamps-` or contains `-floor-lamps-` => `floor-lamp`
- `name_en` contains `Floor lamp`, `Floor/reading lamp`, or `Floor uplighter` => `floor-lamp`
- `name_zh` contains `落地燈` => `floor-lamp`

Do not map all `abo-lamps-*` to `floor-lamp`. That group has mixed products and some non-lamp furniture/decor in the current data.

## Minimum Data Patch Target

At minimum, make these counts non-zero in active PostgreSQL runtime:

```text
floor-lamp > 0
floor-lamp where glb_url/model_url is not empty > 0
```

Better target:

```text
floor-lamp around 116 from the old full catalog, or at least the 25 high-priority reviewed rows.
```

## Verification Commands

After data/import/view changes, run:

```powershell
$env:PYTHONIOENCODING='utf-8'
@'
from backend.server.main import _furniture_payload_cache
items=list(_furniture_payload_cache())
floor=[i for i in items if i.get("normalized_type") == "floor-lamp"]
usable=[i for i in floor if i.get("has_model") and i.get("model_url")]
print("payload_count", len(items))
print("floor-lamp", len(floor))
print("usable_floor-lamp", len(usable))
for item in usable[:5]:
    print(item.get("furniture_id"), item.get("name_en") or item.get("name_zh"), item.get("model_url"))
'@ | .\.venv\Scripts\python.exe -
```

Expected result:

```text
floor-lamp > 0
usable_floor-lamp > 0
```

Then run the soft decor tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_scene_soft_decor.py
```

Expected result:

```text
all tests pass
```

Full suite should no longer have the three `decor_model_missing` failures.
