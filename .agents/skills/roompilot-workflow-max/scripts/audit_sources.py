#!/usr/bin/env python3
"""Build or verify the source inventory used by roompilot-workflow-max."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
INVENTORY_PATH = SKILL_ROOT / "references" / "source-inventory.json"
SOURCE_ROOTS = (Path(".claude"), Path("VibeCoding_Workflow_Templates"))
TEXT_EXTENSIONS = {
    ".csv",
    ".dot",
    ".gitignore",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".session-snapshot",
    ".session-start",
    ".sh",
    ".ts",
    ".txt",
    ".yaml",
    ".yml",
}

ADAPTED_SKILLS = {
    "community-a11y-audit",
    "community-frontend-design",
    "sunnydata-api-design",
    "sunnydata-architecture-review",
    "sunnydata-code-review",
    "sunnydata-debugging",
    "sunnydata-deep-research",
    "sunnydata-design",
    "sunnydata-parallel-agents",
    "sunnydata-security",
    "sunnydata-testing",
}
REFERENCE_ONLY_SKILLS = {
    "community-react-composition",
    "community-react-performance",
    "community-ui-design-system",
    "community-ux-bencium-controlled",
    "sunnydata-infrastructure",
    "sunnydata-skill-authoring",
}
EXCLUDED_SKILLS = {
    "community-react-native",
    "community-ux-bencium-innovative",
    "community-web-guidelines",
    "sunnydata-branch-lifecycle",
    "sunnydata-shadcn-ui",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify(relative_path: str) -> tuple[str, bool]:
    """Return (disposition, mutable_runtime)."""
    normalized = relative_path.replace("\\", "/")
    if normalized.startswith("VibeCoding_Workflow_Templates/"):
        return "adapted-vibecoding-source", False

    if normalized.startswith(".claude/logs/") or normalized.startswith(
        ".claude/taskmaster-data/"
    ):
        return "excluded-runtime", True

    if normalized == ".claude/settings.json":
        return "excluded-claude-permissions", False
    if normalized.startswith(".claude/hooks/"):
        return "excluded-claude-hooks", False
    if normalized.startswith(".claude/statusline") or normalized == ".claude/STATUSLINE_GUIDE.md":
        return "excluded-statusline-oauth-binary", False
    if normalized.startswith(".claude/mcp-configs/"):
        return "excluded-tool-and-secret-config", False

    if normalized.startswith(".claude/skills/"):
        parts = normalized.split("/")
        if len(parts) < 3:
            return "synthesized-skill-index", False
        skill_name = parts[2]
        if skill_name in ADAPTED_SKILLS:
            return "adapted-skill-method", False
        if skill_name in REFERENCE_ONLY_SKILLS:
            return "reviewed-reference-only", False
        if skill_name in EXCLUDED_SKILLS:
            return "excluded-skill", False
        return "reviewed-skill-index-or-note", False

    if normalized.startswith(".claude/agents/"):
        return "synthesized-agent-role", False
    if normalized.startswith(".claude/commands/"):
        return "synthesized-command-workflow", False
    if normalized.startswith(".claude/rules/"):
        return "synthesized-rule", False
    if normalized.startswith(".claude/output-styles/"):
        return "adapted-output-recipe", False
    if normalized.startswith(".claude/coordination/"):
        return "adapted-coordination-template", False
    if normalized.startswith(".claude/context/"):
        return "adapted-empty-context-structure", False
    if normalized in {".claude/CLAUDE.md", ".claude/README.md", ".claude/WORKFLOW.md"}:
        return "synthesized-core-workflow", False
    return "reviewed-not-copied", False


def discover(repo_root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for source_root in SOURCE_ROOTS:
        absolute_root = repo_root / source_root
        if not absolute_root.exists():
            continue
        for path in sorted(candidate for candidate in absolute_root.rglob("*") if candidate.is_file()):
            relative = path.relative_to(repo_root).as_posix()
            disposition, mutable = classify(relative)
            entries.append(
                {
                    "path": relative,
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                    "extension": path.suffix.lower(),
                    "document_like": path.suffix.lower() in TEXT_EXTENSIONS,
                    "disposition": disposition,
                    "mutable_runtime": mutable,
                }
            )
    return entries


def build_inventory(repo_root: Path) -> dict[str, Any]:
    files = discover(repo_root)
    dispositions = Counter(item["disposition"] for item in files)
    extensions = Counter(item["extension"] or "<none>" for item in files)
    return {
        "schema_version": "1.0",
        "basis": "RoomPilot working-tree sources reviewed for safe Codex conversion",
        "source_roots": [root.as_posix() for root in SOURCE_ROOTS],
        "summary": {
            "files": len(files),
            "document_like_files": sum(bool(item["document_like"]) for item in files),
            "bytes": sum(int(item["bytes"]) for item in files),
            "by_disposition": dict(sorted(dispositions.items())),
            "by_extension": dict(sorted(extensions.items())),
        },
        "files": files,
    }


def write_inventory(inventory: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    output.write_text(payload, encoding="utf-8", newline="\n")
    print(f"Wrote {len(inventory['files'])} entries to {output}")


def check_inventory(current: dict[str, Any], stored_path: Path) -> int:
    if not stored_path.exists():
        print(f"ERROR: inventory is missing: {stored_path}", file=sys.stderr)
        return 1

    stored = json.loads(stored_path.read_text(encoding="utf-8"))
    stored_by_path = {item["path"]: item for item in stored.get("files", [])}
    current_by_path = {item["path"]: item for item in current.get("files", [])}

    if not current_by_path:
        print("WARNING: source roots are absent; validated stored inventory structure only.")
        return 0 if stored_by_path else 1

    added = sorted(set(current_by_path) - set(stored_by_path))
    removed = sorted(set(stored_by_path) - set(current_by_path))
    changed: list[str] = []
    mutable_changed: list[str] = []
    for path in sorted(set(current_by_path) & set(stored_by_path)):
        current_item = current_by_path[path]
        stored_item = stored_by_path[path]
        if current_item["sha256"] == stored_item["sha256"]:
            continue
        if current_item.get("mutable_runtime") or stored_item.get("mutable_runtime"):
            mutable_changed.append(path)
        else:
            changed.append(path)

    if added or removed or changed:
        if added:
            print("ERROR: unreviewed source files added:", file=sys.stderr)
            for path in added:
                print(f"  + {path}", file=sys.stderr)
        if removed:
            print("ERROR: inventoried source files removed:", file=sys.stderr)
            for path in removed:
                print(f"  - {path}", file=sys.stderr)
        if changed:
            print("ERROR: stable source files changed:", file=sys.stderr)
            for path in changed:
                print(f"  * {path}", file=sys.stderr)
        print("Review drift, update conversion docs, then run audit_sources.py write.", file=sys.stderr)
        return 1

    if mutable_changed:
        print(f"WARNING: ignored content drift in {len(mutable_changed)} runtime file(s).")
    print(f"PASS: source inventory covers {len(current_by_path)} files.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "write"), nargs="?", default="check")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path, default=INVENTORY_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    output = args.output if args.output.is_absolute() else (repo_root / args.output)
    if args.output == INVENTORY_PATH:
        output = INVENTORY_PATH
    inventory = build_inventory(repo_root)
    if args.action == "write":
        write_inventory(inventory, output)
        return 0
    return check_inventory(inventory, output)


if __name__ == "__main__":
    raise SystemExit(main())
