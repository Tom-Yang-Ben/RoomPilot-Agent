"""Upgrade persisted RoomPilot projects to the current schema.

Dry run (no writes):
    uv run --no-sync python scripts/migrate_project_schema.py --dry-run

Migrate with an automatic SQLite backup:
    uv run --no-sync python scripts/migrate_project_schema.py

Restore a backup (also creates a pre-restore safety backup):
    uv run --no-sync python scripts/migrate_project_schema.py --restore BACKUP_DIR
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.server.project_schema_migration import (
    migrate_runtime_schema,
    restore_runtime_backup,
)
from backend.server.runtime_paths import project_runtime_dir


ROOT = Path(__file__).resolve().parents[1]


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        default=project_runtime_dir(ROOT),
        help="Runtime directory containing projects.sqlite3.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report the migration count without writing or creating a backup.",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        help="Explicit backup directory for a migration.",
    )
    parser.add_argument(
        "--restore",
        type=Path,
        metavar="BACKUP_DIR",
        help="Restore a previously created backup instead of migrating.",
    )
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    if args.restore and (args.dry_run or args.backup_dir):
        raise SystemExit("--restore cannot be combined with --dry-run or --backup-dir")
    if args.restore:
        result = restore_runtime_backup(args.runtime_dir, args.restore)
    else:
        result = migrate_runtime_schema(
            args.runtime_dir,
            dry_run=args.dry_run,
            backup_dir=args.backup_dir,
        )
    print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
