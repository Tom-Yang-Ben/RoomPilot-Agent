from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_team_ai_guidance_covers_every_owner_and_primary_folder() -> None:
    owner_profiles = {
        "BELLA.md",
        "CODY.md",
        "DJANGO.md",
        "KAI.md",
        "YEN.md",
        "ANCAI.md",
        "BEN.md",
    }
    assert {path.name for path in (ROOT / "docs/owners").glob("*.md")} == owner_profiles

    guided_folders = (
        "backend/agent",
        "backend/catalog",
        "backend/engine",
        "backend/floorplan",
        "backend/server",
        "backend/spatial_data",
        "backend/upgrade3d",
        "frontend3d",
        "scripts",
        "testdata",
        "tests",
    )
    for folder in guided_folders:
        assert (ROOT / folder / "AGENTS.md").is_file(), folder

    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Mandatory Read-Before-Write Gate" in agents
    assert "Cross-Folder Change Gate" in agents
    assert "Read `AGENTS.md` before changing code" in claude


def test_readme_describes_current_flow_and_executable_startup() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "現行八步流程" in readme
    assert "8 AI 渲染" in readme
    assert "十步流程" not in readme
    assert "pip install -r requirements.txt" in readme
    assert "uvicorn backend.server.main:app" in readme
    assert "-m pytest -q" in readme


def test_requirements_pin_all_non_ocr_direct_dependencies() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    expected_names = {"shapely", "pytest"}
    for group in ("server", "vision", "catalog"):
        expected_names.update(
            re.split(r"[<>=!~]", requirement, maxsplit=1)[0].lower()
            for requirement in pyproject["project"]["optional-dependencies"][group]
        )

    requirement_lines = [
        line.strip()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert all(re.fullmatch(r"[A-Za-z0-9_.-]+==[A-Za-z0-9_.+-]+", line) for line in requirement_lines)
    pinned_names = {line.split("==", 1)[0].lower() for line in requirement_lines}
    assert expected_names <= pinned_names

    ocr_requirements = (ROOT / "requirements-ocr.txt").read_text(encoding="utf-8")
    assert "-r requirements.txt" in ocr_requirements
    assert "paddleocr==3.7.0" in ocr_requirements
    assert "paddlepaddle==3.3.1" in ocr_requirements


def test_frontend_lock_matches_documented_team_versions() -> None:
    lock = json.loads((ROOT / "frontend3d/package-lock.json").read_text(encoding="utf-8"))
    packages = lock["packages"]
    assert packages["node_modules/react"]["version"] == "18.3.1"
    assert packages["node_modules/react-dom"]["version"] == "18.3.1"
    assert packages["node_modules/three"]["version"] == "0.160.1"
    assert packages["node_modules/@react-three/fiber"]["version"] == "8.18.0"
    assert packages["node_modules/@react-three/drei"]["version"] == "9.122.0"
    assert packages["node_modules/vite"]["version"] == "8.1.0"
