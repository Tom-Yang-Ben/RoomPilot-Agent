from __future__ import annotations

import os
from pathlib import Path


def _repository_root(project_dir: Path) -> Path:
    git_marker = project_dir / ".git"
    if git_marker.is_file():
        first_line = git_marker.read_text(encoding="utf-8").splitlines()[0].strip()
        if first_line.lower().startswith("gitdir:"):
            git_dir = Path(first_line.split(":", 1)[1].strip())
            if not git_dir.is_absolute():
                git_dir = (project_dir / git_dir).resolve()
            if git_dir.parent.name == "worktrees" and git_dir.parent.parent.name == ".git":
                return git_dir.parent.parent.parent
    return project_dir


def project_runtime_dir(project_dir: Path) -> Path:
    """回傳所有 worktree 共用且可長期保存的執行資料目錄。"""
    configured = os.getenv("ROOMPILOT_RUNTIME_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return _repository_root(project_dir) / ".runtime"
