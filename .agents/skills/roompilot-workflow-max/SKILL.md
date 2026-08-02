---
name: roompilot-workflow-max
description: Route and execute RoomPilot product, architecture, API, data-contract, frontend, testing, security, delivery, documentation, and multi-owner changes with repository-aware owners, contracts, reusable templates, safe maximum parallelism, and evidence-based validation. Use for RoomPilot requirement framing, implementation planning, cross-folder integration, full or MVP delivery workflows, parallel-agent development, architecture or contract changes, code review, release readiness, and maintenance work.
---

# RoomPilot Workflow Max

Use this skill as a repository-aware workflow router. Treat current repository instructions,
contracts, code, and tests as truth; treat bundled templates as aids rather than authority.

## Apply the authority order

Resolve conflicts in this order:

1. Follow the user's explicit scope and authorization.
2. Follow the nearest applicable `AGENTS.md`.
3. Follow current `docs/contracts/` and owner profiles.
4. Follow current code, tests, and executable repository commands.
5. Use this skill's references and templates.

Never use a converted generic pattern to override a RoomPilot boundary.

## Run preflight before editing

1. Read the root `AGENTS.md` and `README.md` completely.
2. Read `docs/TEAM_AI_OWNERSHIP.md` and every affected `docs/owners/<OWNER>.md`.
3. Read the nearest `AGENTS.md`, target module documentation, and related contracts.
4. Run `git status --short`; preserve all unrelated and uncommitted work.
5. Trace inputs, outputs, units, schema versions, persistence boundaries, consumers, and tests.
6. State the intended files and validation commands before modifying files.
7. For cross-folder changes, record the root `AGENTS.md` cross-folder declaration.

Read [roompilot-baseline.md](references/roompilot-baseline.md) for the product/runtime map,
[owner-path-router.md](references/owner-path-router.md) for ownership, and
[contract-data-boundaries.md](references/contract-data-boundaries.md) for hard gates.

## Select a workflow mode

- **Focused mode:** Use for one-owner, low-risk, contract-preserving changes. Inspect, patch the
  smallest surface, run targeted tests, review the diff, and finish with repository gates.
- **Full mode:** Use for API/schema/persistence, cross-owner, production frontend, catalog/SQL,
  architecture, or release work. Frame requirements, freeze contracts, plan producer and consumer
  changes, implement, review, and run integration validation.
- **Maximum parallel mode:** Use when the user requests parallel work or the task contains at least
  two independent work packets and collaboration tools are available. Follow
  [parallel-execution.md](references/parallel-execution.md). Keep one integrator and never let two
  agents edit the same file or guess an unstable shared schema.

Use [workflow-routing.md](references/workflow-routing.md) to choose artifacts and templates.

## Execute the gated workflow

### 1. Frame

- Confirm the requested outcome, affected product step, scope, non-goals, and acceptance evidence.
- Identify the primary owner, collaborating owners, producer, consumer, and persistence boundary.
- Use the templates under `assets/templates/` only when the artifact adds decision value.

### 2. Stabilize contracts

- Inspect existing payloads and compatibility behavior before proposing fields.
- Define names, types, units, schema version, defaults, error semantics, and migration behavior.
- Assign a single writer for shared contracts. Do not start parallel producer/consumer edits until
  the contract is stable.

### 3. Build work packets

- Give every packet an owner, exact files, allowed behavior, inputs, outputs, contracts, tests,
  dependencies, and prohibited changes.
- Keep packets independent by directory and file. Reserve shared files for the integrator.

### 4. Implement minimally

- Extend the existing owner path; do not create a second FastAPI app or production frontend.
- Preserve legacy compatibility unless a versioned migration is explicitly approved.
- Keep domain decisions in their owning modules and adapters in integration paths.

### 5. Verify evidence

- Run the targeted producer and consumer tests selected from
  [validation-matrix.md](references/validation-matrix.md).
- Review the complete diff for owner violations, schema drift, unsafe fallbacks, secrets, runtime
  files, destructive commands, and unrelated changes.
- Run final repository gates when the task includes implementation or integration.

### 6. Deliver clearly

- Report outcome first, then changed files, contract impact, validation results, unverified items,
  and remaining risks.
- Distinguish existing failures from failures introduced by the change.
- Never claim a command, database rebuild path, browser result, or deployment was verified unless
  it actually ran.

## Enforce RoomPilot hard boundaries

- Use centimeters across modules; suffix new lengths and coordinates with `_cm`; use `_m2` for area.
- Keep `layout_json` as architectural layout and `scene_json` as proposal/edit/render state.
- Keep Graph RAG advisory; only `backend/engine/` decides placement, collision, clearance, and
  geometric legality.
- Keep catalog identity, active/quarantine state, CloudFront assets, and PostgreSQL data under Kai's
  boundary. Do not expose inactive, unmatched, or quarantined items.
- Keep appliances in questionnaire/render context; do not place them as official step-6 furniture.
- Keep `backend/server/static/` as the production frontend. Treat `frontend3d/` as an optional
  prototype unless a migration is explicitly approved.
- Treat the current `scripts/` tree as the only valid script baseline. Do not restore historical
  scripts or advertise missing Phase 3/4 rebuild tooling.

## Stop and escalate

Stop before acting when required authority, credentials, a destructive operation, an owner decision,
or a shared schema choice is missing. Also stop when the requested change would silently replace a
domain algorithm, expose quarantine, weaken strict PostgreSQL behavior, overwrite dirty files, or
create a second source of truth.

## Load supporting resources selectively

- Read [output-recipes.md](references/output-recipes.md) when choosing a document/review format.
- Read [source-transformation-map.md](references/source-transformation-map.md) when auditing the
  conversion or updating this skill.
- Read [claude-core-conversion.md](references/claude-core-conversion.md) and
  [claude-skills-conversion.md](references/claude-skills-conversion.md) when evaluating excluded or
  adapted Claude material.
- Copy and fill the matching file in `assets/templates/`; do not edit the template in place for a
  one-off task.

## Validate this skill

From the repository root, run:

```powershell
python .agents/skills/roompilot-workflow-max/scripts/audit_sources.py check
python .agents/skills/roompilot-workflow-max/scripts/validate_workflow.py
python C:\Users\KAI\.codex\skills\.system\skill-creator\scripts\quick_validate.py .agents/skills/roompilot-workflow-max
```

The first command detects unreviewed source drift. Regenerate the inventory with `write` only after
reviewing every added, removed, or changed source and updating the transformation map.
