from __future__ import annotations

import os
from pathlib import Path


def _repository_root(project_dir: Path) -> Path:
    """Resolve the main repository when running from a linked worktree."""
    git_marker = project_dir / ".git"
    if not git_marker.is_file():
        return project_dir

    lines = git_marker.read_text(encoding="utf-8").splitlines()
    if not lines or not lines[0].lower().startswith("gitdir:"):
        return project_dir

    git_dir = Path(lines[0].split(":", 1)[1].strip())
    if not git_dir.is_absolute():
        git_dir = (project_dir / git_dir).resolve()
    if git_dir.parent.name == "worktrees" and git_dir.parent.parent.name == ".git":
        return git_dir.parent.parent.parent
    return project_dir


def project_runtime_dir(project_dir: Path) -> Path:
    """Return the explicit or repository-shared directory for runtime data.

    This function only resolves a path. It deliberately does not create folders,
    scan sibling worktrees, or import legacy databases.
    """
    configured = os.getenv("ROOMPILOT_RUNTIME_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return _repository_root(project_dir) / ".runtime"
