"""Fail fast when the public worktree contains release-blocking material."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TREE_BYTES = 150 * 1024 * 1024
FORBIDDEN_PREFIXES = (
    "JSON/",
    "RoomPilot_Docs/",
    "VibeCoding_Workflow_Templates/",
    "backend/server/static/frontend3d/",
    "data/dataset/",
    "data/testdata/",
    "frontend/",
    "graphify-out/",
    "manual_test_kit/",
)
FORBIDDEN_SUFFIXES = (
    ".glb",
    ".gltf",
    ".onnx",
    ".npz",
    ".pt",
    ".pth",
    ".safetensors",
    ".sql.gz",
)
SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "OpenAI-style token": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
}
TEXT_SUFFIXES = {
    "",
    ".css",
    ".csv",
    ".dxf",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".ps1",
    ".sh",
    ".sql",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}


def _git_lines(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return [line for line in result.stdout.splitlines() if line]


def _candidate_paths() -> list[Path]:
    names = _git_lines("ls-files", "--cached", "--others", "--exclude-standard")
    return sorted(
        {
            ROOT / name
            for name in names
            if (ROOT / name).is_file()
        }
    )


def _verify_fixture_manifest(errors: list[str]) -> None:
    path = ROOT / "examples" / "fixtures" / "manifest.json"
    if not path.is_file():
        errors.append("missing examples/fixtures/manifest.json")
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    for item in payload.get("assets", []):
        asset = ROOT / str(item.get("path") or "")
        if not asset.is_file():
            errors.append(f"manifest asset missing: {asset.relative_to(ROOT)}")
            continue
        digest = hashlib.sha256(asset.read_bytes()).hexdigest()
        if digest != item.get("sha256"):
            errors.append(f"manifest checksum mismatch: {asset.relative_to(ROOT)}")
        if not item.get("copyright") or not item.get("license") or not item.get("source"):
            errors.append(f"manifest provenance incomplete: {asset.relative_to(ROOT)}")


def main() -> int:
    errors: list[str] = []
    paths = _candidate_paths()
    relative_paths = [path.relative_to(ROOT).as_posix() for path in paths]

    ignored_tracked = _git_lines("ls-files", "-ci", "--exclude-standard")
    if ignored_tracked:
        errors.append("tracked files match .gitignore: " + ", ".join(ignored_tracked[:10]))

    total_bytes = 0
    for path, relative in zip(paths, relative_paths, strict=True):
        size = path.stat().st_size
        total_bytes += size
        if size > MAX_FILE_BYTES:
            errors.append(f"file exceeds 10 MiB: {relative} ({size} bytes)")
        if relative.startswith(FORBIDDEN_PREFIXES):
            errors.append(f"forbidden public path: {relative}")
        if relative.casefold().endswith(FORBIDDEN_SUFFIXES):
            errors.append(f"forbidden public artifact: {relative}")
        if path.suffix.casefold() not in TEXT_SUFFIXES or size > 2 * 1024 * 1024:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"possible {label}: {relative}")

    if total_bytes > MAX_TREE_BYTES:
        errors.append(f"public tree exceeds 150 MiB: {total_bytes} bytes")

    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    if "filter=lfs" in attributes:
        errors.append("Git LFS filters are not allowed in the public root")

    for html in (
        ROOT / "backend/server/static/scene.html",
        ROOT / "backend/server/static/library.html",
        ROOT / "backend/server/static/panorama/panorama.html",
    ):
        if "unpkg.com" in html.read_text(encoding="utf-8"):
            errors.append(f"runtime CDN dependency remains: {html.relative_to(ROOT)}")

    _verify_fixture_manifest(errors)

    if errors:
        print("Public repository check failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Public repository check passed: {len(paths)} files, {total_bytes} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
