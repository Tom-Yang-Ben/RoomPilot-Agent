# RoomPilot collaborator guide

Start with `AGENTS.md` and `README.md`, then read the nearest directory-level
`AGENTS.md` plus any affected contract under `docs/contracts/`.

The public default is the offline `portable` profile. It uses the project-authored
fixture catalog, SQLite project storage, procedural 3D furniture, and loopback-only
development hosting. The `full` profile is strict PostgreSQL and requires operators
to supply their own licensed data and assets; failures must remain visible.

Keep these boundaries intact:

- `layout_json` is recognition output; `scene_json` is generated/edited output.
- Cross-module geometry uses centimetres and `_cm` field names.
- Only `backend/engine/` decides placement, collision, clearance, and legality.
- `backend/server/static/` is the one production frontend.
- Do not commit secrets, user data, database dumps, model weights, large GLBs, or
  assets without verified redistribution rights.

Before handing off, run the validation commands documented in `AGENTS.md`. Do not
push, merge, publish, or deploy unless the user explicitly asks for that action.
