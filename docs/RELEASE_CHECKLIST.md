# Public release checklist

This checklist is the final gate for publishing a RoomPilot root commit. It does not authorize pushing or changing the default branch.

## Repository boundary

- Work from a dedicated branch; keep `main` unchanged until review explicitly approves it.
- `git status --short` is empty before packaging.
- `scripts/public_repo_check.py` reports no secret, private path, oversized artifact, broken local Markdown link, stale fixed-count claim, or unexpected vendored runtime file.
- The public root contains no user projects, `.env`, database dump, model weight, product catalog, external manifest, large GLB, generated report, cache, or private evaluation data.
- Every bundled third-party runtime has a matching notice and SPDX license text.

## Reproducibility

Run from the repository root:

```powershell
uv sync --frozen --extra portable --group dev
uv run python scripts/generate_public_fixtures.py
uv run python scripts/update_static_hashes.py
uv run python scripts/public_repo_check.py
uv run pytest -q
node --check backend/server/static/scene_v2.js
node --check backend/server/static/scene_viewer.js
git diff --check
git status --short
```

Fixture generation and static-hash refresh must leave no uncommitted diff. Also run the opt-in browser smoke and disposable PostgreSQL contract jobs defined in `.github/workflows/ci.yml`; they must not contact production services.

## Publication

- Build the public branch from the verified tree, not from unreviewed history.
- Confirm the public root has exactly one parentless commit when using the clean-root publication workflow.
- Confirm its tree matches the reviewed cleanup branch exactly.
- Push only the named public branch, using `--force-with-lease` when replacing an earlier clean-root commit.
- Wait for every GitHub Actions job to complete successfully before calling the branch publishable.
- Do not create a PR, merge, release, or change the default branch unless separately requested.
