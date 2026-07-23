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


def legacy_runtime_dirs(project_dir: Path) -> list[Path]:
    """找出需要合併至共用資料庫的舊 worktree 執行資料目錄。"""
    repository = _repository_root(project_dir)
    candidates = [project_dir / ".runtime"]
    worktrees_dir = repository / ".worktrees"
    if worktrees_dir.is_dir():
        candidates.extend(path / ".runtime" for path in worktrees_dir.iterdir() if path.is_dir())
    git_worktrees_dir = repository / ".git" / "worktrees"
    if git_worktrees_dir.is_dir():
        for registration in git_worktrees_dir.iterdir():
            gitdir_file = registration / "gitdir"
            if not gitdir_file.is_file():
                continue
            registered_git_marker = Path(
                gitdir_file.read_text(encoding="utf-8").strip()
            )
            if registered_git_marker.name == ".git":
                candidates.append(registered_git_marker.parent / ".runtime")
    shared = project_runtime_dir(project_dir).resolve()
    return list(
        dict.fromkeys(
            path.resolve()
            for path in candidates
            if path.is_dir() and path.resolve() != shared
        )
    )
