# RoomPilot Team AI Ownership and Architecture

This document maps remote branches and current repository folders to the people
and responsibilities used by RoomPilot. It is based on branch history, current
code, tests, and existing team documentation. Git authorship alone is not
treated as ownership because Bella has already integrated many teammate patches.

## Branch Map

| Team label | Remote branch | Current responsibility | Notes |
|---|---|---|---|
| Bella | `origin/bella` | Integration, FastAPI, persistence, production UI and 2D/3D workflow | Current remote ref may match `main`; active integration work continues on Bella test branches |
| Cody | `origin/cody` | Recognition models, evaluation, datasets, walls/doors/windows/rooms | Large training assets stay outside the integrated runtime tree |
| Django | `origin/django` | Room inference, furniture-symbol evidence, spatial data, RAG annotations | Only compatible algorithms and schemas are ported; not the whole Version4 tree |
| Kai | `origin/kai` | Catalog, AWS/CloudFront manifest, PostgreSQL import and data delivery | Historical branch also contains experiments outside the current catalog boundary |
| Yen | `origin/yen` | Requirements, structured preferences, selection and repair decision flow | Current production UI is still integrated by Bella |
| Ancai | `origin/ancai`, `origin/ancai-dev` | Placement engine and 2D+3D interaction prototypes | Scene-lab experiments require Bella review before entering production UI |
| Ben | `origin/ben` and Cody-history commits | Recognition QA, model/evaluation assets, project documentation | Works with Cody on recognition and with Bella on release verification |

## Folder Ownership and Data Flow

| Folder | Owner | Collaborators | Input | Output / Function |
|---|---|---|---|---|
| `backend/server/` | Bella | All owners at adapters | HTTP, project state, `layout_json`, requirements | FastAPI, persistence, API adapters, eight-step UI, `scene_json` orchestration |
| `backend/server/static/` | Bella | Yen for questionnaire, Ancai for interaction, Cody/Django for correction UI | API payloads | Production HTML/CSS/JS and Three.js editing |
| `backend/floorplan/` | Cody | Django, Ben | PNG/JPG/DXF and scale confirmation | Walls, doors, windows, rooms, confidence/evaluation, `layout_json` |
| `backend/floorplan/vision/` | Cody | Django for room/icon inference | Decoded/profiled image | Normalized recognition analysis in centimeters |
| `backend/spatial_data/` | Django | Cody producer, Ancai/Bella consumers | Confirmed room/opening geometry | Spatial measurements, adjacency/evaluation records; no rendering |
| `backend/catalog/` | Kai | Django for RAG labels, Bella for API | Official catalog and manifest | Verified furniture/material records and retrieval metadata |
| `JSON/` | Kai | Bella validation | Import/export source metadata | Catalog manifests and furniture JSON handoff |
| `scripts/sql/` | Kai | Bella API integration | Verified catalog JSON/CSV | PostgreSQL schema, dry-run validation and transactional import |
| `backend/agent/` | Yen | Kai retrieval, Ancai legality, Bella API | Requirements, room context, catalog candidates | Selection, explanations and repair intents; never final geometry |
| `backend/engine/` | Ancai | Yen and Bella | Room, walls, furniture candidates | Placement, collision, clearance, movement and legality |
| `backend/upgrade3d/` | Cody | Ancai and Bella | Confirmed DXF/layout | 3D-ready wall/floor/opening geometry |
| `frontend3d/` | Bella | Ancai prototype review | DXF/scene API | Secondary React/R3F prototype, not the production workflow |
| `testdata/` | Cody | Django and Ben | Curated images/DXF/ground truth | Reproducible recognition fixtures |
| `tests/` | Matching owner | Bella end-to-end review | Public behavior | Unit, API, contract and visual regression gates |
| `docs/contracts/` | Bella | All affected owners | Agreed interfaces | Cross-folder schema and lifecycle source of truth |
| `examples/` | Ancai/Yen | Bella | Domain objects and intents | Small executable demonstrations |

Generated `.runtime/`, `.tmp/`, caches, weights, and local databases have no
source-code owner and must not be committed.

## Cross-Module Architecture

```text
floorplan image / DXF
  -> Cody recognition
  -> Django spatial relationships and evaluation
  -> layout_json
  -> Yen requirement/selection decisions
  -> Kai catalog and relationship retrieval
  -> Ancai geometry placement and validation
  -> scene_json
  -> Bella FastAPI, persistence and production 2D/3D UI
```

Graph RAG may enrich Kai/Django retrieval with room, style, furniture, material,
and restriction relationships. Ancai remains authoritative for geometry and
rules.

## Shared Change Protocol

1. The producer owner changes and versions the contract.
2. The consumer owner updates its adapter, not a duplicate implementation.
3. Bella verifies API/persistence and end-to-end UI behavior.
4. Tests cover both producer and consumer.
5. The relevant owner profile and contract are updated in the same change.

Examples:

- New floorplan field: Cody + Django if spatial, then Bella adapter tests.
- New furniture metadata: Kai + Yen retrieval, then Bella API/UI tests.
- New placement rule: Ancai + Yen explanation, then Bella workflow tests.
- New questionnaire output: Yen + Bella, plus Kai/Ancai only if their inputs
  change.

## Owner Profiles

- [Bella](owners/BELLA.md)
- [Cody](owners/CODY.md)
- [Django](owners/DJANGO.md)
- [Kai](owners/KAI.md)
- [Yen](owners/YEN.md)
- [Ancai](owners/ANCAI.md)
- [Ben](owners/BEN.md)

