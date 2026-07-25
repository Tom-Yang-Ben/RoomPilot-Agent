from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from backend.server import main
from backend.server.project_store import ProjectStore


def _png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (32, 24), "#f4f1ea").save(output, format="PNG")
    return output.getvalue()


def test_project_bundle_restores_workflow_and_floorplan_in_isolated_runtime(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_store = ProjectStore(tmp_path / "source-runtime")
    monkeypatch.setattr(main, "PROJECT_STORE", source_store)
    client = TestClient(main.app)

    created = client.post(
        "/api/projects",
        json={"name": "跨電腦驗收", "notes": "保留原始平面圖"},
    ).json()["project"]
    project_id = created["project_id"]
    floorplan = _png_bytes()
    upload = client.post(
        f"/api/projects/{project_id}/floorplan",
        files={"file": ("home.png", floorplan, "image/png")},
    )
    assert upload.status_code == 201

    saved = client.put(
        f"/api/projects/{project_id}/workflow",
        json={
            "current_step": "space_confirmation",
            "workflow": {
                "_flow": {
                    "currentStep": "space_confirmation",
                    "completed": ["project", "upload", "recognition", "calibration"],
                },
                "space_confirmation": {
                    "rooms": [{"room_id": "room-1", "name": "臥室"}],
                    "source_url": f"/api/projects/{project_id}/floorplan/source",
                },
            },
        },
    )
    assert saved.status_code == 200

    exported = client.get(f"/api/projects/{project_id}/export")
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith(
        "application/vnd.roompilot.project+zip"
    )
    assert exported.headers["content-disposition"].endswith('.roompilot"')

    remote_store = ProjectStore(tmp_path / "remote-runtime")
    monkeypatch.setattr(main, "PROJECT_STORE", remote_store)
    imported = client.post(
        "/api/projects/import",
        files={
            "bundle": (
                "project.roompilot",
                exported.content,
                "application/vnd.roompilot.project+zip",
            )
        },
    )

    assert imported.status_code == 201
    restored = imported.json()["project"]
    restored_id = restored["project_id"]
    assert restored_id != project_id
    assert restored["name"] == "跨電腦驗收（匯入）"
    assert restored["current_step"] == "space_confirmation"
    assert restored["workflow"]["space_confirmation"]["rooms"] == [
        {"room_id": "room-1", "name": "臥室"}
    ]
    assert restored["workflow"]["space_confirmation"]["source_url"] == (
        f"/api/projects/{restored_id}/floorplan/source"
    )

    restored_source = client.get(
        f"/api/projects/{restored_id}/floorplan/source"
    )
    assert restored_source.status_code == 200
    assert restored_source.content == floorplan

    continued = client.put(
        f"/api/projects/{restored_id}/workflow",
        json={
            "current_step": "requirements",
            "expected_revision": restored["revision"],
            "workflow": {"requirements": {"completed": True}},
        },
    )
    assert continued.status_code == 200


def test_project_bundle_rejects_modified_floorplan(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = ProjectStore(tmp_path / "runtime")
    monkeypatch.setattr(main, "PROJECT_STORE", store)
    client = TestClient(main.app)
    floorplan = _png_bytes()
    manifest = {
        "format": main.PROJECT_BUNDLE_FORMAT,
        "version": main.PROJECT_BUNDLE_VERSION,
        "source_project_id": "a" * 32,
        "project": {
            "name": "遭修改的封包",
            "notes": "",
            "current_step": "upload",
            "workflow": {},
        },
        "floorplan": {
            "member": "floorplan.png",
            "filename": "home.png",
            "extension": ".png",
            "mime_type": "image/png",
            "sha256": hashlib.sha256(b"different").hexdigest(),
        },
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("floorplan.png", floorplan)

    response = client.post(
        "/api/projects/import",
        files={"bundle": ("modified.roompilot", output.getvalue(), "application/zip")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "project_bundle_checksum_mismatch"


def test_project_bundle_rejects_invalid_source_project_id(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = ProjectStore(tmp_path / "runtime")
    monkeypatch.setattr(main, "PROJECT_STORE", store)
    client = TestClient(main.app)
    manifest = {
        "format": main.PROJECT_BUNDLE_FORMAT,
        "version": main.PROJECT_BUNDLE_VERSION,
        "source_project_id": "a",
        "project": {
            "name": "不可取代一般文字",
            "notes": "",
            "current_step": "project",
            "workflow": {"requirements": {"answer": "warm and calm"}},
        },
        "floorplan": None,
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest))

    response = client.post(
        "/api/projects/import",
        files={"bundle": ("invalid.roompilot", output.getvalue(), "application/zip")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid_project_bundle"


def test_project_transfer_controls_are_wired_into_scene() -> None:
    html = main.STATIC_DIR.joinpath("scene.html").read_text(encoding="utf-8")
    controller = main.STATIC_DIR.joinpath("scene_v2.js").read_text(encoding="utf-8")

    assert 'id="export-project"' in html
    assert 'id="project-bundle-file"' in html
    assert 'id="import-project"' in html
    assert "/api/projects/import" in controller
    assert "/export`" in controller
    assert "await saveSequence" in controller
