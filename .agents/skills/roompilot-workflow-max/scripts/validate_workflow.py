#!/usr/bin/env python3
"""Validate roompilot-workflow-max structure, links, guardrails, and source coverage."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]

REFERENCE_FILES = [
    "references/roompilot-baseline.md",
    "references/owner-path-router.md",
    "references/contract-data-boundaries.md",
    "references/workflow-routing.md",
    "references/parallel-execution.md",
    "references/validation-matrix.md",
    "references/output-recipes.md",
    "references/source-transformation-map.md",
    "references/claude-core-conversion.md",
    "references/claude-skills-conversion.md",
    "references/source-inventory.json",
]
TEMPLATE_FILES = [
    "assets/templates/02-task-brief-prd.md",
    "assets/templates/03-bdd-acceptance.md",
    "assets/templates/04-adr.md",
    "assets/templates/05-architecture-change.md",
    "assets/templates/06-api-data-contract.md",
    "assets/templates/07-module-spec-tests.md",
    "assets/templates/08-project-structure.md",
    "assets/templates/09-dependency-map.md",
    "assets/templates/10-component-relationships.md",
    "assets/templates/11-code-review-refactor.md",
    "assets/templates/12-frontend-technical.md",
    "assets/templates/13-security-readiness.md",
    "assets/templates/14-deployment-runbook.md",
    "assets/templates/15-documentation-maintenance.md",
    "assets/templates/16-wbs-work-packets.md",
    "assets/templates/17-frontend-ia.md",
]
REQUIRED_FILES = [
    "SKILL.md",
    "agents/openai.yaml",
    "scripts/audit_sources.py",
    "scripts/validate_workflow.py",
    *REFERENCE_FILES,
    *TEMPLATE_FILES,
]

GUARDRAILS = [
    "AGENTS.md",
    "git status --short",
    "layout_json",
    "scene_json",
    "_cm",
    "_m2",
    "backend/engine/",
    "backend/server/static/",
    "PostgreSQL",
    "quarantine",
]
VIBE_SOURCES = [
    "INDEX.md",
    "output_style.md",
    "01_workflow_manual.md",
    "02_project_brief_and_prd.md",
    "03_behavior_driven_development_guide.md",
    "04_architecture_decision_record_template.md",
    "05_architecture_and_design_document.md",
    "06_api_design_specification.md",
    "07_module_specification_and_tests.md",
    "08_project_structure_guide.md",
    "09_file_dependencies_template.md",
    "10_class_relationships_template.md",
    "11_code_review_and_refactoring_guide.md",
    "12_frontend_architecture_specification.md",
    "13_security_and_readiness_checklists.md",
    "14_deployment_and_operations_guide.md",
    "15_documentation_and_maintenance_guide.md",
    "16_wbs_development_plan_template.md",
    "17_frontend_information_architecture_template.md",
]
DANGEROUS_PATTERNS = {
    "recursive deletion": re.compile(r"\brm\s+-rf\b", re.IGNORECASE),
    "hard reset": re.compile(r"\bgit\s+reset\s+--hard\b", re.IGNORECASE),
    "checkout discard": re.compile(r"\bgit\s+checkout\s+--\b", re.IGNORECASE),
    "docker prune": re.compile(r"\bdocker\s+system\s+prune\b", re.IGNORECASE),
    "volume deletion": re.compile(r"\bdocker\s+compose\s+down\s+-v\b", re.IGNORECASE),
    "Claude OAuth": re.compile(r"CLAUDE_CODE_OAUTH_TOKEN"),
    "unbounded latest package": re.compile(r"\bnpx\b[^\n]*@latest", re.IGNORECASE),
}
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-source-check", action="store_true")
    return parser.parse_args()


def read_utf8(path: Path, errors: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        errors.append(f"invalid UTF-8: {path}: {exc}")
        return ""


def validate_frontmatter(skill_text: str, errors: list[str]) -> None:
    if not skill_text.startswith("---\n"):
        errors.append("SKILL.md must start with YAML frontmatter")
        return
    parts = skill_text.split("---\n", 2)
    if len(parts) < 3:
        errors.append("SKILL.md frontmatter is not closed")
        return
    keys = []
    for line in parts[1].splitlines():
        if ":" in line:
            keys.append(line.split(":", 1)[0].strip())
    if keys != ["name", "description"]:
        errors.append(f"SKILL.md frontmatter keys must be name, description; found {keys}")
    if "name: roompilot-workflow-max" not in parts[1]:
        errors.append("SKILL.md has the wrong skill name")


def validate_links(markdown_path: Path, text: str, errors: list[str]) -> None:
    for target in LINK_PATTERN.findall(text):
        clean = target.strip().strip("<>").split("#", 1)[0]
        if not clean or re.match(r"^(?:https?://|mailto:|[A-Za-z]:[/\\])", clean):
            continue
        resolved = (markdown_path.parent / clean).resolve()
        if not resolved.exists():
            errors.append(f"broken link in {markdown_path.relative_to(SKILL_ROOT)}: {target}")


def main() -> int:
    args = parse_args()
    errors: list[str] = []

    for relative in REQUIRED_FILES:
        path = SKILL_ROOT / relative
        if not path.is_file():
            errors.append(f"missing required file: {relative}")

    markdown_texts: dict[Path, str] = {}
    for path in sorted(SKILL_ROOT.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() in {".md", ".yaml", ".yml", ".json", ".py"}:
            text = read_utf8(path, errors)
            if text and not text.endswith("\n"):
                errors.append(f"missing terminal newline: {path.relative_to(SKILL_ROOT)}")
            for line_number, line in enumerate(text.splitlines(), start=1):
                if line.endswith((" ", "\t")):
                    errors.append(
                        f"trailing whitespace: {path.relative_to(SKILL_ROOT)}:{line_number}"
                    )
            if path.suffix.lower() == ".md":
                markdown_texts[path] = text
                validate_links(path, text, errors)

    skill_path = SKILL_ROOT / "SKILL.md"
    skill_text = markdown_texts.get(skill_path, "")
    validate_frontmatter(skill_text, errors)
    for token in GUARDRAILS:
        if token not in skill_text and token not in "\n".join(markdown_texts.values()):
            errors.append(f"missing RoomPilot guardrail token: {token}")

    ui_text = read_utf8(SKILL_ROOT / "agents" / "openai.yaml", errors)
    if "display_name: \"RoomPilot Workflow Max\"" not in ui_text:
        errors.append("agents/openai.yaml display_name is missing or stale")
    if "$roompilot-workflow-max" not in ui_text:
        errors.append("agents/openai.yaml default_prompt must mention $roompilot-workflow-max")

    for relative in ["SKILL.md", *REFERENCE_FILES[:-1]]:
        path = SKILL_ROOT / relative
        if path.exists() and "TODO" in read_utf8(path, errors):
            errors.append(f"unresolved TODO outside templates: {relative}")

    for relative in ["SKILL.md", *TEMPLATE_FILES]:
        path = SKILL_ROOT / relative
        if not path.exists():
            continue
        text = read_utf8(path, errors)
        for label, pattern in DANGEROUS_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"dangerous operational recipe ({label}) in {relative}")

    source_map_path = SKILL_ROOT / "references" / "source-transformation-map.md"
    if source_map_path.exists():
        source_map = read_utf8(source_map_path, errors)
        for source in VIBE_SOURCES:
            if source not in source_map:
                errors.append(f"source transformation map does not cover {source}")

    if not args.skip_source_check:
        audit = subprocess.run(
            [sys.executable, str(SKILL_ROOT / "scripts" / "audit_sources.py"), "check"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if audit.returncode != 0:
            errors.append("source inventory check failed:\n" + audit.stdout + audit.stderr)
        elif audit.stdout.strip():
            print(audit.stdout.strip())

    if errors:
        print(f"FAIL: {len(errors)} validation error(s)", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"PASS: validated {len(REQUIRED_FILES)} required files and {len(markdown_texts)} Markdown files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
