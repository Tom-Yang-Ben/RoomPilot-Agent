from __future__ import annotations

import hashlib
import re
from pathlib import Path

from fastapi.testclient import TestClient

from backend.server.main import app


STATIC = Path("backend/server/static")
client = TestClient(app)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def test_engineering_page_is_official_fastapi_frontend() -> None:
    response = client.get("/engineering?project_id=demo")
    assert response.status_code == 200
    assert "工程估算與文件生成" in response.text
    for element_id in (
        "revision",
        "completeness",
        "lock-status",
        "save-draft",
        "lock-revision",
        "generate-package",
        "job-progress",
        "job-error",
        "html-preview",
        "download-links",
    ):
        assert f'id="{element_id}"' in response.text


def test_frontend_adapter_maps_existing_state_without_direct_backends() -> None:
    source = (STATIC / "engineering.js").read_text(encoding="utf-8")
    for required in (
        "buildProjectSnapshot",
        "space_confirmation",
        "polygon_cm",
        "room_surface_assignments",
        "scene_objects",
        "appliance_requirements",
        "source_project_revision",
        'coordinate_unit: "cm"',
        "/api/v1/projects/",
        "/engineering-packages",
        "/api/v1/jobs/",
        "/api/v1/packages/",
        "?preview=1",
        "error.status = response.status",
        "existing.snapshot",
        "existing.completeness",
    ):
        assert required in source
    lowered = source.lower()
    for forbidden in (
        "openai.com",
        "anthropic.com",
        "neo4j",
        "postgresql://",
        "indexeddb",
    ):
        assert forbidden not in lowered


def test_static_module_hashes_are_current_and_scene_links_to_engineering() -> None:
    engineering_html = (STATIC / "engineering.html").read_text(encoding="utf-8")
    scene_html = (STATIC / "scene.html").read_text(encoding="utf-8")
    engineering_match = re.search(
        r"engineering\.js\?v=sha256-([0-9a-f]{12})", engineering_html
    )
    link_match = re.search(
        r"engineering_link\.js\?v=sha256-([0-9a-f]{12})", scene_html
    )
    assert engineering_match
    assert link_match
    assert engineering_match.group(1) == _hash(STATIC / "engineering.js")
    assert link_match.group(1) == _hash(STATIC / "engineering_link.js")
    assert 'id="engineering-documents-link"' in scene_html
