"""API 輸入邊界與錯誤訊息（QA 2026-08-01 #8）。

三件事：型別錯誤要回 422 而不是 500、上傳要有大小上限、專案名稱不能被
str() 硬轉成 Python repr 回顯給使用者。
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from backend.server.main import MAX_FLOORPLAN_BYTES, MAX_PROJECT_NAME_CHARS, app


client = TestClient(app)


@pytest.mark.parametrize(
    ("url", "body"),
    [
        ("/api/scene/generate", {"room_width_cm": "abc"}),
        ("/api/scene/generate", {"room_width_cm": [1, 2]}),
        ("/api/scene/generate", {"room_depth_cm": {"x": 1}}),
        ("/api/scene/generate", {"client_brief": "nope"}),
        ("/api/scene/layout", {"scene_objects": "not-a-list"}),
        ("/api/scene/layout", {"floorplan": "nope"}),
        ("/api/scene/validate", {"item": "nope"}),
        ("/api/scene/validate", {"others": "nope"}),
        ("/api/scene/decorate", {"scene_objects": 5}),
    ],
)
def test_scene_endpoints_reject_wrong_types_with_422(url: str, body: dict) -> None:
    response = client.post(url, json=body)

    assert response.status_code == 422, response.text


def test_scene_generate_still_accepts_numeric_strings() -> None:
    """夾帶字串數字的舊前端仍要能用；收緊型別不等於改契約。"""
    response = client.post(
        "/api/scene/generate",
        json={"room_width_cm": "420", "room_depth_cm": 360},
    )

    assert response.status_code == 200


def test_project_name_must_be_text_and_bounded() -> None:
    leaked = client.post("/api/projects", json={"name": {"evil": "repr"}})
    assert leaked.status_code == 422
    # 送 dict 進來時舊版會把 "{'evil': 'repr'}" 存成專案名稱。
    assert "evil" not in leaked.text

    too_long = client.post(
        "/api/projects", json={"name": "很長" * MAX_PROJECT_NAME_CHARS}
    )
    assert too_long.status_code == 422
    assert too_long.json()["detail"]["code"] == "project_name_too_long"


def test_project_notes_must_be_text() -> None:
    response = client.post("/api/projects", json={"name": "測試專案", "notes": ["a"]})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_project_notes"


def test_missing_project_does_not_point_at_a_screen_that_does_not_exist() -> None:
    response = client.get("/api/projects/does-not-exist")

    assert response.status_code == 404
    message = response.json()["detail"]["message"]
    assert "專案列表" not in message
    assert "首頁" in message


def test_dxf_upload_rejects_oversized_files() -> None:
    oversized = io.BytesIO(b"0" * (MAX_FLOORPLAN_BYTES + 1024))

    response = client.post(
        "/api/upload",
        files={"file": ("huge.dxf", oversized, "application/dxf")},
    )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "upload_too_large"


def test_floorplan_image_upload_rejects_oversized_files() -> None:
    oversized = io.BytesIO(b"0" * (MAX_FLOORPLAN_BYTES + 1024))

    response = client.post(
        "/api/floorplan/analyze",
        files={"file": ("huge.png", oversized, "image/png")},
    )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "upload_too_large"
