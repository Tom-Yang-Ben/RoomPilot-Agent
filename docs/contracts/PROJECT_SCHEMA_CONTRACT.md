# Project Persistence Schema Contract

Last updated: 2026-08-17

RoomPilot browser projects use `project_schema_version: 3` at the root of every
persisted `workflow_json`. The production application reads only v3. Older
projects must be upgraded offline with the repository migration command before
the application opens them.

## Canonical ownership

| Data | Canonical location |
|---|---|
| Recognition/layout evidence | `recognition` (`layout_json`, centimeters) |
| Confirmed rooms and structures | `space_confirmation` (centimeters) |
| Requirements and finishes | `requirements` |
| A/B state, furniture, and per-scheme scene | `configuration` |
| Step completion metadata | `_flow`, `layout_2d`, `white_model_3d` |

`configuration.schema_version` is `3`. Its `schemes.A` and optional
`schemes.B` own both `furniture` and `sceneData`. The following retired
locations must not be written or read by production code:

- `layout_2d.furniture` and `layout_2d.schemes`
- `white_model_3d.sceneData`
- `space_confirmation.design_schemes`
- root-level `design_schemes`, `furniture`, or `furniture2d`

Persisted geometry uses centimeters only. New fields use `_cm`; persisted
`*_m`, `polygon_m`, `m_per_px`, and `distance_m` fields are invalid in v3.

## Upgrade and backup

Inspect without writing:

```powershell
uv run --no-sync python scripts/migrate_project_schema.py --dry-run
```

Upgrade all projects in the configured runtime:

```powershell
uv run --no-sync python scripts/migrate_project_schema.py
```

The write command first creates a SQLite backup under
`.runtime/backups/project-schema-v3-<UTC timestamp>/`. The manifest records a
SHA-256 checksum and migrated project count. Uploads and renders are not
rewritten.

Restore a backup:

```powershell
uv run --no-sync python scripts/migrate_project_schema.py --restore <backup-dir>
```

Restore validates the backup checksum and creates a second pre-restore safety
backup before replacing the database. Stop the RoomPilot server before upgrade
or restore operations.

## Producer and consumer

- Producer: `backend/server/static/scene_v2.js::workflowPayload()`.
- Persistence validator: `backend/server/project_store.py`.
- Upgrade boundary: `backend/server/project_schema.py` and
  `scripts/migrate_project_schema.py`.
- Consumer: `backend/server/static/scene_restore_controller.js`.

Schema changes are incomplete unless migration, restore, project-store, and
browser restore tests all pass.
