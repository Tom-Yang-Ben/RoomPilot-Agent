# Recognition Test Data

Owner: Cody. Reviewers: Django for room/spatial labels and Ben for QA.

- Keep fixtures small, intentional, and attributable to a test.
- Separate source image, ground truth, and generated result.
- Do not overwrite human-reviewed labels with model output.
- Large training datasets and generated caches stay outside Git.
- Every fixture change must name the test or evaluation it supports.

## `Asset/` — symbol evaluation corpus from the `cody` branch

`Asset/` holds the cropped floorplan symbol images Cody uses to measure
recognition filters. It was imported from branch `origin/cody` with
`git checkout origin/cody -- testdata/Asset`; the `cody` branch remains the
upstream source, so send corrections there first and re-import.

Layout — 1,576 PNG files, 31 MB, one directory per symbol class:

| Path | Files |
| :--- | ---: |
| `Asset/door` | 86 |
| `Asset/bathroom/tub` | 67 |
| `Asset/bathroom/washbasin` | 128 |
| `Asset/bathroom/wc` | 104 |
| `Asset/bedroom/beds` | 442 |
| `Asset/bedroom/wardrobe` | 111 |
| `Asset/kitchen/cook_stove` | 180 |
| `Asset/kitchen/dinner_table` | 73 |
| `Asset/kitchen/sink` | 149 |
| `Asset/livingroom/chairs` | 120 |
| `Asset/livingroom/sofas` | 116 |

Every file is named `<class>_NNN.png` with a zero-padded three-digit index.

`Asset/door` is the reference set behind the door filter's stated 84/86 (98%)
baseline; `door_001` and `door_007` are the two known hard samples, where a
multi-line door leaf is geometrically identical to a window symbol. Do not
tighten the filter until those two are handled deliberately.

### Relationship to `door/`

The older `door/` directory (19 files, `door_typeXX_NNN.png`) is a strict
subset of `Asset/door` — all 19 blobs appear byte-identical inside the 86.
The two directories coexist for now: `door/` keeps existing scripts and
snapshots working, `Asset/door` is the current evaluation set. Retiring
`door/` is the recognition owner's call, and must happen together with the
default path in `backend/floorplan/eval_doors.py`, which still points at
`testdata/door`.

Nothing else under `testdata/` was touched by this import. In particular
`png/`, `pngans/`, `chk/`, `dxf/`, and `pic/` stay on their main-branch
contents, because `png/builder_plan_630.png` backs the server sample endpoint
and several hard-coded test assertions.

