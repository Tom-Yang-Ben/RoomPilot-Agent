# Scripts and Data Operations

Owners: Kai for the catalog, GLB/image delivery tools and `scripts/sql/`;
Cody/Ben for recognition dataset tools; Bella for release/integration utilities.

The operational commands in `scripts/README.md` assume the repository root is
`D:\RoomPilot-Agent`. Keep reusable script defaults relative to the repository
root derived from `Path(__file__)`; do not add paths to personal work folders.

- Scripts must be idempotent or expose an explicit dry-run mode.
- Database writes require `.env`, transaction safety, and validation counts.
- Generated outputs and large assets do not belong in Git.
- Never silently delete or prune catalog rows.
- Document the exact command and expected result beside each operational script.
- `roompilot_glb_downloader.py` may write only after dry-run review; validate the
  GLB magic header and keep downloaded models outside Git.
- `roompilot_s3_glb_uploader.py` and `roompilot_s3_image_uploader.py` must remain
  dry-run by default. AWS writes require `--execute`; size-mismatch overwrites
  additionally require `--force`. Never overwrite the source manifest.
- `roompilot_s3_image_uploader.py` reuses the GLB uploader's path, AWS, resume,
  and atomic CSV helpers, so producer and consumer CLI checks are both required
  when their shared behavior changes.
- `roompilot_catalog_manager.py prune-missing` must preview by default. Applying
  changes requires `--apply`, a backup, and an explicit report.
- Normalized furniture dimensions remain `width_cm`, `depth_cm`, and
  `height_cm`; operational scripts must not introduce ambiguous geometry units.

Minimum verification for these catalog operations:

```powershell
python scripts/roompilot_glb_downloader.py --help
python scripts/roompilot_s3_glb_uploader.py --help
python scripts/roompilot_s3_image_uploader.py --help
python scripts/roompilot_catalog_manager.py --list
python -m pytest -q tests/test_image_manifest_contract.py
git diff --check
git status --short
```

