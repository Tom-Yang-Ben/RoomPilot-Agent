# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

"RoomPilot" turns a 2D CAD floor plan (DXF) into an editable 3D white-model room. There are **two independent implementations** in this repo — know which one you're touching:

- **`app/`** — the newer client/server rewrite. FastAPI backend (`ezdxf` + `shapely`) parses DXF into a wall/window/door JSON model; a Vite + React + React Three Fiber frontend renders it live. Focused purely on extracting building shell (walls/windows/doors); no furniture yet. **This is the active development surface.**
- **`2Dto3D.html`** — a legacy, self-contained single-file prototype ("AI Interior Copilot"). Parses DXF *client-side* in vanilla JS and renders with Three.js from a CDN. Has features the rewrite lacks (furniture catalog + placement, style brushing, doors-snap, undo). No build step.

There is no test framework, no linter, and **no git repository** here — don't reach for `git` commands. UI strings and comments throughout are **Traditional Chinese**; match that when editing UI text.

## Run / develop

### `app/` (backend + frontend, two terminals)

```bash
# backend — from app/backend/
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000

# frontend — from app/frontend/
npm install
npm run dev        # http://localhost:5173  (build: npm run build, preview: npm run preview)
```

Vite proxies `/api` → `localhost:8000`, so the browser sees same-origin and needs no CORS handling.

**Self-check (the closest thing to a test):** `python dxf_parser.py` from `app/backend/` parses all bundled plans in `pic/temp/` and asserts each yields walls, ≥1 solid wall polygon, and a scale in 1–200 m. Run this after touching the parser.

### `2Dto3D.html` (legacy)

Open the file directly in a browser — no install, no dev server. It loads Three.js 0.149.0 + addons via an `<script type="importmap">` CDN and Google Fonts, so it needs internet. A fallback shows "3D engine failed to load" if `window.__copilotReady` isn't set within 6s (e.g. CDN blocked).

## Architecture — `app/`

### The contract: DXF → JSON → 3D

The load-bearing interface is the JSON shape that `dxf_parser.py` produces and `Scene.jsx` consumes. Changing one side means changing the other. Per plan:

```
{ name, scale_basis, scale_m, wall_height, wall_thickness, fallback_all_walls,
  bbox:{minx,minz,maxx,maxz},
  wall_polys:[{exterior:[[x,z],…], holes:[[[x,z],…],…]}],   # solid wall footprints
  windows:[{x1,z1,x2,z2}], doors:[…],                       # line segments
  stats:{…} }
```

**Coordinate convention** (spans both sides, easy to get wrong): the parser emits plan-X as `x` and DXF-Y as `z` (so the model is 2D in the XZ plane, metres). The frontend maps `worldX = x`, `worldZ = -z`, Y = up — `Scene.jsx` negates z everywhere and extrudes walls with a `-π/2` X rotation.

### Backend (`app/backend/`)

- `main.py` — FastAPI, CORS wide open. Endpoints: `GET /api/plans` (lists `pic/temp/*.dxf`), `GET /api/plan?name=&scale_m=&thickness=&height=`, `POST /api/upload` (multipart DXF). `PIC_DIR` resolves to `../../pic/temp`; `os.path.basename(name)` guards against path traversal. Parse failures → HTTP 422.
- `dxf_parser.py` — the real work:
  - `_collect` walks modelspace, recursively exploding `INSERT`/`POLYLINE`/`MLINE` via `virtual_entities`, and classifies **each leaf entity by its own layer** (`classify`, multilingual keyword substrings, window/door checked before wall) — so window lines inside a block placed on a different layer are still caught.
  - `HATCH` fills are extracted as boundary rings, kept grouped per-hatch so even-odd XOR (`hatch_region`) can hollow out frame-style walls. Solid walls are often drawn as hatch, not lines — omitting them breaks the wall.
  - **Scale** (`scale_basis`): longer bbox side → metres. `manual` (the `scale_m` query param), else `insunits` (if `$INSUNITS` gives a plausible 2–80 m), else `normalized` (`DEFAULT_SPAN=12`). Aspect ratio is always preserved exactly because DXF units are unreliable.
  - **Wall mass** = `unary_union` of buffered wall centrelines (square caps + mitre joins so perpendicular walls meet in clean corners) ∪ hatch fill regions. The resulting polygon's holes are the rooms. **`thickness` is the buffer diameter** — raise it to merge double-line walls into one solid (and thus close rooms).
  - **No per-room segmentation** (needs a wall-graph solver, out of scope); the floor is just the bbox slab.

### Frontend (`app/frontend/src/`)

- `App.jsx` — all UI state + the fetch logic. Any knob change (`scale_m`, `thickness`, `height`, plan/upload selection) triggers a **250ms-debounced** refetch. `scaleM = null` means "let the backend auto-guess."
- `Scene.jsx` — R3F render. `Walls` extrudes each `wall_poly` shape (with holes) to `wall_height`; `SegBoxes` lays a box along each window/door segment; `Floor` is the bbox slab. drei `<Bounds>` auto-fits the camera per plan, `<OrbitControls>`, `<Grid>`.
  - **X-ray walls** (`makeWallMaterial` + the `Walls` `useFrame`): zooming in fades the wall *surfaces* between the camera and the orbit target so you can see into rooms (the `近景穿牆` checkbox). Done per-fragment via `onBeforeCompile` (injects a `vWorldPos` varying + a view-ray distance test into the standard material) because the backend unions all walls into one mesh — front and back walls share it, so per-mesh opacity can't single out the near side. Thresholds scale with the plan diagonal; `depthWrite`/`castShadow` are toggled off only once a wall is genuinely see-through.

## Architecture — `2Dto3D.html` (legacy)

Two phases toggled by `setStep("upload"|"editor")` (swaps CSS grid via `body` classes). `initEditor()` runs lazily once (`editorInited` guard) and is the whole Three.js app in one closure — mutable module-level state (`ROOM`, `objects`, `selected`, `wallMeshes`, `WALL_SEGS`, `selectedCells`, `history`) is shared across inner functions.

- **DXF pipeline:** `tokenizeDxf` → `parseDxfSegments` (flattens LINE/LWPOLYLINE/POLYLINE/ARC/CIRCLE/MLINE into layer-tagged 2D segments) → `addDxfRoom`. Detects wall/window layers by keyword (`WALL_KW`/`WIN_KW`, multilingual incl. CJK); if no wall layer, treats all segments as walls. Normalizes the longest edge to `dxfTargetSpan`, with `manualW`/`manualD` (the 1–200 m "scale" panel) as the calibration override. Falls back to `addDemoRoom` (hardcoded 5×4 m) on too few segments. `buildRoom()` resets room state; `rebuild()` also clears furniture, re-seeds, refreshes UI — call after scale/`uploadedDxfText` changes.
- **Editor:** `CATALOG` furniture types via `buildFurniture`/`addObject`; GLB import via `addGlbModel` (GLTFLoader). World is a `CELL = 0.5 m` grid (`snap`, `cellAtCursor`); placement validity `badAt` → `hitsWall`/`hitsFurniture`/`outOfBounds` (XZ AABB). Doors snap via `nearestWall`/`placeDoor`. `cells` tool selects floor cells; `applyStyleToCells` recolors from a `STYLES` palette. Custom orbit camera (`orbit.apply()`, not OrbitControls). Undo stack `history` (cap 50, `undoLast`).
- **Convention:** DOM wired by `getElementById` against static markup — element IDs are the contract between HTML and the JS closure. Dimensions are metres internally; inspector inputs are centimetres (÷100).

## Assets

`pic/temp/` holds the bundled DXF test plans (7 files) that the backend lists and the self-check exercises. `pic/` also contains reference floor-plan images; `pic/result/` has screenshots.
