# RoomPilot Instructions for Claude

Read `AGENTS.md` before changing code. It is the repository-wide working
agreement and contains the mandatory read-before-write and cross-folder gates.

Then read:

1. `README.md`
2. `docs/TEAM_AI_OWNERSHIP.md`
3. The relevant profile in `docs/owners/`
4. The nearest path-specific `AGENTS.md`
5. Relevant contracts under `docs/contracts/`

## Before Any Edit

Report the target owner, files, input/output contract, and tests. If more than
one owner's folder is involved, use the cross-folder change template from
`AGENTS.md` before editing.

Never:

- merge a teammate's whole branch into Bella without reviewing individual
  commits and paths;
- create a second FastAPI app or second production frontend;
- move geometry decisions into Graph RAG, the browser, or the LLM;
- change centimeter payloads without producer and consumer tests;
- treat quarantined catalog data as official furniture;
- overwrite unrelated local modifications.

## Current Product Boundary

The production experience is the eight-step FastAPI/static web workflow in
`backend/server/`. Recognition ends at `layout_json`; proposal generation and
editing use `scene_json`. Furniture legality is computed by
`backend/engine/`. The React app in `frontend3d/` is a secondary prototype.

Ownership and branch evidence are documented in
`docs/TEAM_AI_OWNERSHIP.md`; do not infer responsibility from a Git author name
alone.

