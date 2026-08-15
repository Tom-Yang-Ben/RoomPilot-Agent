#!/usr/bin/env python3
"""Refresh content-addressed query strings for local static dependencies."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "backend" / "server" / "static"
REFERENCE = re.compile(
    r"(?P<prefix>(?:\.\/|\/static\/))"
    r"(?P<path>[^\"'?#]+\.(?:js|css))"
    r"\?v=sha256-(?P<digest>[0-9a-f]{12,64})"
)


def static_content_digest(path: Path, length: int = 64) -> str:
    """Hash static text with checkout-independent line endings."""
    content = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(content).hexdigest()[:length]


def _refresh(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")

    def replace(match: re.Match[str]) -> str:
        prefix = match.group("prefix")
        referenced = (
            STATIC / match.group("path")
            if prefix == "/static/"
            else path.parent / match.group("path")
        )
        if not referenced.is_file():
            return match.group(0)
        digest = static_content_digest(referenced, len(match.group("digest")))
        return f"{prefix}{match.group('path')}?v=sha256-{digest}"

    refreshed = REFERENCE.sub(replace, source)
    if refreshed == source:
        return False
    path.write_text(refreshed, encoding="utf-8", newline="\n")
    return True


def main() -> int:
    modules = sorted(STATIC.rglob("*.js"))
    for _ in range(len(modules) + 1):
        changed = False
        for path in modules:
            changed = _refresh(path) or changed
        if not changed:
            break
    else:
        raise RuntimeError("static module dependency hashes did not converge")

    for path in sorted(STATIC.rglob("*.html")):
        _refresh(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
