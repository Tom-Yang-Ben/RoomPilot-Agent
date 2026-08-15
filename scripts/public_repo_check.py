"""Fail fast when the public worktree contains release-blocking material."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TREE_BYTES = 50 * 1024 * 1024
FORBIDDEN_PREFIXES = (
    "JSON/",
    "RoomPilot_Docs/",
    "VibeCoding_Workflow_Templates/",
    "backend/server/static/frontend3d/",
    "data/dataset/",
    "data/testdata/",
    "docs/01_專題進度/",
    "docs/04_契約與規格/",
    "docs/ai-harness/",
    "docs/archive/",
    "docs/backlog/",
    "docs/superpowers/",
    "frontend/",
    "graphify-out/",
    "manual_test_kit/",
)
FORBIDDEN_SUFFIXES = (
    ".bak",
    ".glb",
    ".gltf",
    ".key",
    ".onnx",
    ".npz",
    ".p12",
    ".pem",
    ".pfx",
    ".pt",
    ".pth",
    ".safetensors",
    ".sqlite",
    ".sqlite3",
    ".sql.gz",
    ".tar",
    ".tgz",
    ".zip",
)
FORBIDDEN_PATHS = {
    "backend/agent/IMPLEMENTATION_REPORT.md",
    "backend/catalog/cloud_catalog.py",
    "backend/server/postgres_catalog.py",
    "docker_postgresql/DOCKER_ONECLICK.md",
    "scripts/catalog/remove_excluded_catalog_assets_from_manifests.py",
    "scripts/verify_ikea_offline_backup.py",
    "scripts/sql/import_catalog_to_postgres.py",
    "scripts/sql/import_furniture_embeddings_to_postgres.py",
    "scripts/sql/import_official_catalog_to_postgres.py",
    "scripts/sql/roompilot_catalog_10550_schema.sql",
    "scripts/sql/roompilot_furniture_embeddings_schema.sql",
    "scripts/sql/roompilot_postgresql_schema.sql",
    "tests/test_verify_ikea_offline_backup.py",
}
SECRET_PATTERNS = {
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "OpenAI-style token": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "Stripe live key": re.compile(r"\bsk_live_[A-Za-z0-9]{16,}\b"),
    "credential-bearing URL": re.compile(
        r"[a-z][a-z0-9+.-]*://[^/@:\s]+:[^/@\s]+@", re.IGNORECASE
    ),
}
RELEASE_BLOCKING_TEXT_PATTERNS = {
    "fixed private catalog count": re.compile(
        r"\b(?:1[,]?508|7[,]?958|8[,]?557|10[,]?550)\b"
    ),
    "retired private CDN": re.compile(r"ddgsm1yg3xikc[.]cloudfront[.]net"),
    "retired private manifest": re.compile(
        r"(?:glb_upload_all_result|image_upload_all_result)[.]csv"
    ),
}
VENDORED_RUNTIME_PATHS = {
    "backend/server/static/vendor/draco/README.md",
    "backend/server/static/vendor/draco/draco_decoder.js",
    "backend/server/static/vendor/draco/draco_decoder.wasm",
    "backend/server/static/vendor/draco/draco_wasm_wrapper.js",
    "backend/server/static/vendor/three/LICENSE",
    "backend/server/static/vendor/three/build/three.module.min.js",
    "backend/server/static/vendor/three/examples/jsm/controls/OrbitControls.js",
    "backend/server/static/vendor/three/examples/jsm/environments/RoomEnvironment.js",
    "backend/server/static/vendor/three/examples/jsm/exporters/GLTFExporter.js",
    "backend/server/static/vendor/three/examples/jsm/loaders/DRACOLoader.js",
    "backend/server/static/vendor/three/examples/jsm/loaders/GLTFLoader.js",
    "backend/server/static/vendor/three/examples/jsm/math/SimplexNoise.js",
    "backend/server/static/vendor/three/examples/jsm/postprocessing/EffectComposer.js",
    "backend/server/static/vendor/three/examples/jsm/postprocessing/GTAOPass.js",
    "backend/server/static/vendor/three/examples/jsm/postprocessing/MaskPass.js",
    "backend/server/static/vendor/three/examples/jsm/postprocessing/OutputPass.js",
    "backend/server/static/vendor/three/examples/jsm/postprocessing/Pass.js",
    "backend/server/static/vendor/three/examples/jsm/postprocessing/RenderPass.js",
    "backend/server/static/vendor/three/examples/jsm/postprocessing/ShaderPass.js",
    "backend/server/static/vendor/three/examples/jsm/shaders/CopyShader.js",
    "backend/server/static/vendor/three/examples/jsm/shaders/GTAOShader.js",
    "backend/server/static/vendor/three/examples/jsm/shaders/OutputShader.js",
    "backend/server/static/vendor/three/examples/jsm/shaders/PoissonDenoiseShader.js",
    "backend/server/static/vendor/three/examples/jsm/utils/BufferGeometryUtils.js",
    "backend/server/static/vendor/three/examples/jsm/utils/TextureUtils.js",
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
CANONICAL_MARKDOWN = (
    ROOT / "README.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "SECURITY.md",
    ROOT / "THIRD_PARTY_NOTICES.md",
    ROOT / "docs" / "README.md",
    ROOT / "docs" / "ARCHITECTURE.md",
    ROOT / "docs" / "ASSET_POLICY.md",
    ROOT / "docs" / "DEVELOPMENT.md",
    ROOT / "docs" / "FULL_PROFILE.md",
    ROOT / "docs" / "KNOWN_LIMITATIONS.md",
    ROOT / "docs" / "TEAM_AI_OWNERSHIP.md",
    ROOT / "docs" / "contracts" / "README.md",
    ROOT / "backend" / "floorplan" / "README.md",
    ROOT / "backend" / "catalog" / "data" / "README.md",
    ROOT / "scripts" / "README.md",
    ROOT / "scripts" / "sql" / "README.md",
    *(ROOT / "docs" / "owners").glob("*.md"),
)
MARKDOWN_LINK = re.compile(r"!?\[[^]]*\]\((<[^>]+>|[^)\s]+)")


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


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


def _verify_markdown_links(
    errors: list[str], markdown_paths: Iterable[Path] | None = None
) -> None:
    for document in markdown_paths or CANONICAL_MARKDOWN:
        if not document.is_file():
            errors.append(f"canonical document missing: {_display_path(document)}")
            continue
        text = document.read_text(encoding="utf-8")
        for match in MARKDOWN_LINK.finditer(text):
            raw_target = match.group(1).strip("<>")
            target = unquote(raw_target.split("#", 1)[0])
            if not target or target.startswith("#"):
                continue
            if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE):
                continue
            resolved = (
                ROOT / target.lstrip("/")
                if target.startswith("/")
                else document.parent / target
            ).resolve()
            if not resolved.exists():
                errors.append(
                    "broken canonical link: "
                    f"{_display_path(document)} -> {raw_target}"
                )


def _verify_text_hygiene(errors: list[str], relative: str, text: str) -> None:
    for line_number, line in enumerate(text.splitlines(), start=1):
        if line.rstrip(" \t") != line:
            errors.append(f"trailing whitespace: {relative}:{line_number}")
    if text.endswith("\n\n"):
        errors.append(f"extra blank line at end of file: {relative}")


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
        if relative in FORBIDDEN_PATHS:
            errors.append(f"forbidden legacy path: {relative}")
        if relative.casefold().endswith(FORBIDDEN_SUFFIXES):
            errors.append(f"forbidden public artifact: {relative}")
        if path.suffix.casefold() not in TEXT_SUFFIXES or size > 2 * 1024 * 1024:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if not relative.startswith("backend/server/static/vendor/"):
            _verify_text_hygiene(errors, relative, text)
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"possible {label}: {relative}")
        if (
            relative != "scripts/public_repo_check.py"
            and not relative.startswith("backend/server/static/vendor/")
        ):
            for label, pattern in RELEASE_BLOCKING_TEXT_PATTERNS.items():
                if pattern.search(text):
                    errors.append(f"{label}: {relative}")

    if total_bytes > MAX_TREE_BYTES:
        errors.append(f"public tree exceeds 50 MiB: {total_bytes} bytes")

    vendor_paths = {
        relative
        for relative in relative_paths
        if relative.startswith("backend/server/static/vendor/")
    }
    for relative in sorted(vendor_paths - VENDORED_RUNTIME_PATHS):
        errors.append(f"unexpected vendored runtime file: {relative}")
    for relative in sorted(VENDORED_RUNTIME_PATHS - vendor_paths):
        errors.append(f"required vendored runtime file missing: {relative}")

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
    markdown_paths = sorted(
        set(CANONICAL_MARKDOWN)
        | {path for path in paths if path.suffix.casefold() == ".md"}
    )
    _verify_markdown_links(errors, markdown_paths)

    if errors:
        print("Public repository check failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Public repository check passed: {len(paths)} files, {total_bytes} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
