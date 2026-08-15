from __future__ import annotations

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
        "scripts",
        "tests",
    )
    for folder in guided_folders:
        assert (ROOT / folder / "AGENTS.md").is_file(), folder

    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "不可違反的契約" in agents
    assert "跨模組修改紀錄" in agents
    assert "Start with `AGENTS.md`" in claude


def test_readme_describes_current_flow_and_executable_startup() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "## 八步流程" in readme
    assert "8 連接外部供應商後產生 AI 渲染" in readme
    assert "十步流程" not in readme
    assert "uv sync --extra portable --group dev" in readme
    assert "uv run uvicorn backend.server.main:app" in readme
    assert "uv run pytest -q" in readme
    assert "127.0.0.1" in readme


def test_requirements_pin_all_non_ocr_direct_dependencies() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    expected_names = {
        re.split(r"[<>=!~]", requirement, maxsplit=1)[0].lower()
        for requirement in pyproject["project"]["optional-dependencies"]["portable"]
    }
    expected_names.update(
        re.split(r"[<>=!~]", requirement, maxsplit=1)[0].lower()
        for requirement in pyproject["dependency-groups"]["dev"]
    )

    requirement_lines = [
        line.strip()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    pinned_lines = [line for line in requirement_lines if not line.startswith("-e ")]
    assert all(re.fullmatch(r"[A-Za-z0-9_.-]+==[A-Za-z0-9_.+-]+(?:\s*;.*)?", line) for line in pinned_lines)
    pinned_names = {line.split("==", 1)[0].lower() for line in pinned_lines}
    assert expected_names <= pinned_names

    ocr_requirements = (ROOT / "requirements-ocr.txt").read_text(encoding="utf-8")
    assert "paddleocr==3.7.0" in ocr_requirements
    assert "paddlepaddle==3.3.1" in ocr_requirements


def test_formal_frontend_vendors_the_documented_three_release() -> None:
    assert not (ROOT / "frontend").exists()
    vendor = ROOT / "backend" / "server" / "static" / "vendor" / "three"
    assert (vendor / "build" / "three.module.min.js").is_file()
    assert (vendor / "LICENSE").is_file()
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "Three.js 0.165.0" in notices
