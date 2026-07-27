# Scripts and Data Operations

Owners: Kai for `scripts/sql/`; Cody/Ben for recognition dataset tools; Bella
for release/integration utilities.

- Scripts must be idempotent or expose an explicit dry-run mode.
- Database writes require `.env`, transaction safety, and validation counts.
- Generated outputs and large assets do not belong in Git.
- Never silently delete or prune catalog rows.
- Document the exact command and expected result beside each operational script.

