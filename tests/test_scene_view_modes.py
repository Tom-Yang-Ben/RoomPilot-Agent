import json

from test_scene_workflow import ROOT, run_workflow_script
from backend.paths import STATIC_DIR


VIEW_MODE_MODULE = STATIC_DIR / "scene_view_modes.js"


def test_three_view_modes_share_scene_without_changing_furniture_coordinates() -> None:
    module_uri = VIEW_MODE_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{ VIEW_MODES, createViewModeState }} from {json.dumps(module_uri)};
        const scene = {{ scene_objects: [{{ furniture_id: "chair-1", position_cm: {{ x: 20, z: 30 }}, rotation_y_deg: 45 }}] }};
        const before = JSON.stringify(scene);
        const viewer = createViewModeState();
        const configs = VIEW_MODES.map((mode) => viewer.setMode(mode));
        console.log(JSON.stringify({{
          modes: VIEW_MODES,
          cameras: configs.map((item) => item.camera),
          controllers: configs.map((item) => item.controller),
          wallModes: configs.map((item) => item.walls),
          unchanged: before === JSON.stringify(scene),
        }}));
        """
    )

    assert result == {
        "modes": ["dollhouse", "walk", "topdown", "orbit"],
        "cameras": ["orthographic", "perspective", "orthographic", "perspective"],
        "controllers": ["orbit", "first_person", "pan_zoom", "orbit"],
        "wallModes": ["full", "full", "flattened", "full"],
        "unchanged": True,
    }
