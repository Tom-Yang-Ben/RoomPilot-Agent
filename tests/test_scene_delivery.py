from fastapi.testclient import TestClient

from backend.server.main import app


def test_scene_page_exposes_real_viewer_and_delivery_controls_without_image_generation() -> None:
    client = TestClient(app)

    page = client.get("/scene")
    viewer_source = client.get("/static/scene_viewer.js")
    flow_source = client.get("/static/scene_v2.js")

    assert page.status_code == viewer_source.status_code == flow_source.status_code == 200
    assert page.headers["cache-control"] == "no-store"
    assert all(mode in page.text for mode in ("自由旋轉", "正俯視", "走動", "編輯家具"))
    assert all(label in page.text for label in ("鎖定視角並編輯家具", "保存即時寫實方案"))
    assert "function setViewMode(mode)" in viewer_source.text
    assert "function capturePng()" in viewer_source.text
    assert "async function exportGlb()" in viewer_source.text
    assert 'lastSceneData?.floorplan?.coordinate_unit === "cm" ? 0.01 : 1' in viewer_source.text
    assert "exportRoot.scale.setScalar(exportScale)" in viewer_source.text
    assert "/v1/images" not in flow_source.text
    assert "generative image" not in flow_source.text.lower()


def test_dxf_white_model_does_not_duplicate_walls_as_floor_overlay_lines() -> None:
    client = TestClient(app)
    viewer_source = client.get("/static/scene_viewer.js")

    assert viewer_source.status_code == 200
    assert (
        "buildFloorPlanOverlay(roomGroup, planSegments.length ? planSegments : wallSegments"
        not in viewer_source.text
    )


def test_locked_camera_is_preserved_when_style_reload_rebuilds_the_room() -> None:
    client = TestClient(app)
    viewer_source = client.get("/static/scene_viewer.js")

    assert viewer_source.status_code == 200
    room_creation = viewer_source.text.split("function createRoom(sceneData)", 1)[1].split(
        "function createHangingLights",
        1,
    )[0]
    assert "if (!cameraLocked)" in room_creation
    assert room_creation.index("if (!cameraLocked)") < room_creation.index(
        'setViewMode("orbit")'
    )
