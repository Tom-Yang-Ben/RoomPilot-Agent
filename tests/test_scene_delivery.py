import json

from fastapi.testclient import TestClient

from test_scene_workflow import ROOT, run_workflow_script
from backend.server.main import app


DELIVERY_MODULE = ROOT / "backend" / "server" / "static" / "scene_delivery.js"


def test_delivery_manifest_has_four_views_four_outputs_and_truthful_bom() -> None:
    module_uri = DELIVERY_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{ buildDeliveryManifest }} from {json.dumps(module_uri)};
        const scene = {{ scene_objects: [
          {{ furniture_id: "known", name_zh_raw: "沙發", price_twd: 12800 }},
          {{ furniture_id: "unknown", name_zh_raw: "邊桌" }},
        ] }};
        console.log(JSON.stringify(buildDeliveryManifest(scene, {{ hasConfirmedDxf: true }})));
        """
    )

    assert result["viewModes"] == ["dollhouse", "walk", "topdown", "orbit"]
    assert result["outputs"] == ["png", "glb", "dxf", "pdf"]
    assert result["bom"]["knownSubtotalTwd"] == 12800
    assert result["bom"]["pendingEstimateIds"] == ["unknown"]
    assert result["usesGenerativeImageApi"] is False


def test_scene_page_exposes_real_viewer_and_delivery_controls_without_image_generation() -> None:
    client = TestClient(app)

    page = client.get("/scene")
    viewer_source = client.get("/static/scene_viewer.js")
    flow_source = client.get("/static/scene_v2.js")

    assert page.status_code == viewer_source.status_code == flow_source.status_code == 200
    assert page.headers["cache-control"] == "no-store"
    assert all(mode in page.text for mode in ("全屋家具配置", "正俯視", "室內透視"))
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


def test_delivery_keeps_furniture_and_sourced_engineering_estimates_separate() -> None:
    module_uri = DELIVERY_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{ buildDeliveryManifest }} from {json.dumps(module_uri)};
        const scene = {{ scene_objects: [{{ furniture_id: "bed-1", name_zh_raw: "床", price_twd: 12800 }}] }};
        const costReport = {{
          status: "concept_estimate",
          totals_twd: {{ low: 5000, base: 9000, high: 14000 }},
          items: [{{ id: "change-wall-01", source_ids: ["uptogo-wall-wrap-2026"], price_date: "2026-04-25" }}],
          needs_quote: [{{ id: "mep-unknown" }}],
          disclaimer_zh: "網路公開行情概算；施工前須現場丈量並取得正式報價。",
        }};
        console.log(JSON.stringify(buildDeliveryManifest(scene, {{ costReport, hasConfirmedDxf: true }})));
        """
    )

    assert result["bom"]["knownSubtotalTwd"] == 12800
    assert result["engineeringEstimate"]["totalsTwd"] == {"low": 5000, "base": 9000, "high": 14000}
    assert result["engineeringEstimate"]["sourceIds"] == ["uptogo-wall-wrap-2026"]
    assert result["engineeringEstimate"]["needsQuoteIds"] == ["mep-unknown"]
    assert result["engineeringEstimate"]["status"] == "concept_estimate"
    assert "正式報價" in result["engineeringEstimate"]["disclaimerZh"]
    assert result["privacy"]["projectOnly"] is True
    assert result["privacy"]["usedForTraining"] is False
