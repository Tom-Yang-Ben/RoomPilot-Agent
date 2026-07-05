# 
    CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`2Dto3D.html` — a single self-contained HTML file ("AI Interior Copilot", Traditional Chinese UI). It ingests a 2D CAD floor plan (DXF) and renders it as an editable 3D white-model room with furniture placement. There is no build system, no backend, no package manager, and no tests. Everything (HTML/CSS/JS) lives in that one file.

`2Dto3D.html` is currently staged-but-deleted in the working tree. Restore it before editing: `git restore 2Dto3D.html` (or `git checkout 2Dto3D.html`).

## Run / develop

Open `2Dto3D.html` directly in a browser. It needs an internet connection — Three.js 0.149.0 and its addons load from a CDN via an `<script type="importmap">`, and fonts from Google Fonts. No install, no dev server. Edit the file and refresh.

A fallback script shows a "3D engine failed to load" message if `window.__copilotReady` isn't set within 6s (e.g. CDN blocked).

## Architecture

Two phases, toggled by `setStep("upload"|"editor")` which swaps CSS grid layouts via `body` classes:

1. **Upload** (`uploadModule`) — drag/drop or pick a `.dxf`, read it into the global `uploadedDxfText`, then `gotoEditor()` lazily runs `initEditor()` once (`editorInited` guard) and exposes `editorAPI = {resize, rebuild}`.
2. **Editor** (`initEditor`) — the whole Three.js app, defined in one big closure. Mutable module-level state (e.g. `ROOM`, `objects`, `selected`, `wallMeshes`, `WALL_SEGS`, `selectedCells`, `history`) is shared across all inner functions.

### DXF → 3D pipeline

`tokenizeDxf` (DXF group-code/value pairs) → `parseDxfSegments` (flattens LINE / LWPOLYLINE / POLYLINE / ARC / CIRCLE / MLINE into 2D segments tagged by layer) → `addDxfRoom`:

- Detects wall/window layers by keyword match (`WALL_KW`, `WIN_KW`, multilingual incl. CJK). If no wall-named layer exists, treats all segments as walls.
- Normalizes the longest plan edge to `dxfTargetSpan` to guess real-world meters; `manualW`/`manualD` override this (the "scale" panel, 1–200 m) — this is the calibration knob for DXF files with unknown units.
- Extrudes each wall segment into a box mesh, adds glass window panels.
- Falls back to `addDemoRoom` (a hardcoded 5×4 m room) if parsing yields too few segments.

`buildRoom()` orchestrates the above and resets all room state; `rebuild()` additionally clears furniture, re-seeds, and refreshes the UI — call it after `uploadedDxfText` or scale changes.

### Editor mechanics

- **Furniture**: `CATALOG` defines types; `buildFurniture`/`addObject` create grouped meshes. GLB import via `addGlbModel` (three GLTFLoader addon).
- **Grid + placement**: world is a `CELL = 0.5 m` grid; `snap`, `cellAtCursor`, etc. Placement validity via `badAt` → `hitsWall` / `hitsFurniture` / `outOfBounds` (AABB overlap on XZ). Doors snap to the nearest wall (`nearestWall`/`placeDoor`).
- **Style brushing**: `cells` tool rectangle-selects floor cells (`selectedCells`); `applyStyleToCells` recolors floor/walls/windows near the selection from a `STYLES` palette.
- **Camera**: a custom orbit object (`orbit.apply()` with az/pol/dist), not OrbitControls.
- **Undo**: command stack in `history` (cap 50), popped by `undoLast`.
- **Render loop**: `loop()` rAF-renders; `resize()` syncs canvas to its CSS box (called on window resize and panel collapse).

### Conventions

- UI strings, comments, and toasts are Traditional Chinese — match that when touching UI text.
- DOM is wired by `document.getElementById` against the static markup; element IDs are the contract between markup and the JS closure.
- Dimensions are meters internally; the inspector inputs are centimeters (divide by 100).

