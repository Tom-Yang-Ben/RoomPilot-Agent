from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OWNER_PROFILE_NAMES = {
    "BELLA.md",
    "CODY.md",
    "DJANGO.md",
    "KAI.md",
    "YEN.md",
    "ANCAI.md",
    "BEN.md",
}


def test_team_ai_guidance_covers_every_owner_and_primary_folder() -> None:
    assert {path.name for path in (ROOT / "docs/owners").glob("*.md")} == OWNER_PROFILE_NAMES

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
    assert "動手前必做" in agents
    assert "跨資料夾修改" in agents
    assert "修改前先閱讀 `AGENTS.md`" in claude


def test_owner_profiles_use_the_current_chinese_handoff_format() -> None:
    obsolete_english_headings = (
        "## Mission",
        "## Architecture",
        "## Before Editing",
        "## Cross-Folder Rules",
        "## Verification",
    )
    for name in OWNER_PROFILE_NAMES:
        profile = (ROOT / "docs/owners" / name).read_text(encoding="utf-8")
        assert "文件版本：2026-08-06" in profile, name
        assert "## AI 快速結論" in profile, name
        assert "## 最低驗證" in profile, name
        assert not any(heading in profile for heading in obsolete_english_headings), name


def test_current_architecture_docs_describe_one_eight_step_flow() -> None:
    paths = (
        "README.md",
        "AGENTS.md",
        "CLAUDE.md",
        "docs/TEAM_AI_OWNERSHIP.md",
        "docs/RoomPilot_現行版本總覽.md",
        "docs/使用者流程與系統架構圖.md",
    )
    documents = {
        path: (ROOT / path).read_text(encoding="utf-8")
        for path in paths
    }
    combined = "\n".join(documents.values())

    assert "單一 `configuration_snapshot`" in combined
    assert "Yen" in combined and "三個候選視角" in combined
    assert "每房一次" in combined
    assert "SQLite" in documents["README.md"]
    assert "SQLite" in documents["docs/TEAM_AI_OWNERSHIP.md"]
    assert "PostgreSQL 搬遷" in documents["README.md"]

    for endpoint in (
        "/api/ai-render/status",
        "/api/projects/{project_id}/ai-renders",
        "/api/projects/{project_id}/ai-renders/{room_id}/edit",
        "/api/projects/{project_id}/design-delivery",
    ):
        assert endpoint in combined, endpoint


def test_superseded_flow_documents_warn_ai_before_historical_details() -> None:
    historical_paths = (
        "docs/ROOMPILOT_6_8_AGENT_RENDER_IMPLEMENTATION_SPEC.md",
        "docs/BEN_第5第6步整合規格_中文.md",
        "docs/BELLA_TEST1_INTEGRATION_LOG.md",
        "docs/contracts/REMOTE_RENDER_CONTRACT.md",
    )
    for path in historical_paths:
        opening = (ROOT / path).read_text(encoding="utf-8")[:1200]
        assert "歷史" in opening or "Legacy" in opening, path
        assert "現行" in opening or "不得" in opening, path


def test_current_ai_guidance_local_markdown_links_exist() -> None:
    guidance_paths = (
        ROOT / "README.md",
        ROOT / "AGENTS.md",
        ROOT / "CLAUDE.md",
        ROOT / "docs/TEAM_AI_OWNERSHIP.md",
        ROOT / "docs/RoomPilot_現行版本總覽.md",
        ROOT / "docs/使用者流程與系統架構圖.md",
        ROOT / "docs/contracts/README.md",
        *(ROOT / "docs/owners" / name for name in OWNER_PROFILE_NAMES),
    )
    link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    missing_links: list[str] = []

    for source in guidance_paths:
        for raw_target in link_pattern.findall(source.read_text(encoding="utf-8")):
            target = raw_target.strip().strip("<>").split("#", 1)[0]
            if not target or re.match(r"^[a-z]+://", target, re.IGNORECASE):
                continue
            if not (source.parent / target).resolve().exists():
                missing_links.append(f"{source.relative_to(ROOT)}: {raw_target}")

    assert not missing_links, "Missing local Markdown links:\n" + "\n".join(missing_links)


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
