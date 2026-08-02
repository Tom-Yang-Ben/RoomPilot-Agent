"""前端宿主表必須與後端一致，欄位要能在 2D↔3D 同步中往返。

前端吸附用 scene_tabletop_hosts.js 的鏡像表，權威判定在後端；兩張表
漂移的話會出現「前端吸得上去、伺服器說不合法」的分裂行為。
"""
from __future__ import annotations

import json

from backend.catalog.style_db import TABLETOP_HOST_TYPES
from backend.paths import STATIC_DIR
from test_scene_workflow import run_workflow_script


def test_frontend_host_table_matches_backend() -> None:
    module_uri = (STATIC_DIR / "scene_tabletop_hosts.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ TABLETOP_HOST_TYPES }} from {json.dumps(module_uri)};
        const sorted_table = Object.fromEntries(
          Object.entries(TABLETOP_HOST_TYPES).map(([key, hosts]) => [key, [...hosts].sort()])
        );
        console.log(JSON.stringify(sorted_table));
        """
    )
    frontend = result
    backend = {key: sorted(hosts) for key, hosts in TABLETOP_HOST_TYPES.items()}
    assert frontend == backend, "前後端宿主相容表漂移，兩邊要一起改"


def test_host_fields_survive_the_2d_3d_round_trip() -> None:
    """檯面小物只從 3D 型錄進場（2D 圖示庫沒有 vase），
    所以往返方向是 scene_object → 2D → scene_object。"""
    layout_uri = (STATIC_DIR / "scene_layout2d.js").as_uri()
    sync_uri = (STATIC_DIR / "scene_configuration_sync.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ toSceneFurniture }} from {json.dumps(layout_uri)};
        import {{ upsertFurniture2dFromSceneObject }} from {json.dumps(sync_uri)};
        const sceneObject = {{
          furniture_id: "vase-1",
          normalized_type: "vase",
          name_zh_raw: "花瓶",
          size_cm: {{ width: 18, depth: 18, height: 30 }},
          position_cm: {{ x: 0, z: 0 }},
          rotation_y_deg: 0,
          host_object_id: "table-1",
          host_surface_height_cm: 74,
        }};
        const back = upsertFurniture2dFromSceneObject([], sceneObject)[0];
        const out = toSceneFurniture(back);
        console.log(JSON.stringify({{
          back_host: back.hostObjectId,
          back_height: back.hostSurfaceHeightCm,
          out_host: out.host_object_id,
          out_height: out.host_surface_height_cm,
        }}));
        """
    )
    assert result == {
        "back_host": "table-1",
        "back_height": 74,
        "out_host": "table-1",
        "out_height": 74,
    }, "宿主欄位在 scene_object→2D→scene_object 往返中遺失"


def test_surface_height_uses_seat_height_for_seating_hosts() -> None:
    module_uri = (STATIC_DIR / "scene_tabletop_hosts.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ hostSurfaceHeightCm }} from {json.dumps(module_uri)};
        console.log(JSON.stringify([
          hostSurfaceHeightCm("dining-table", 74),
          hostSurfaceHeightCm("sofa", 80),
          hostSurfaceHeightCm("bed", 120),
        ]));
        """
    )
    table_height, sofa_height, bed_height = result
    assert table_height == 74, "硬檯面就是宿主全高"
    assert sofa_height == 40, "沙發取半高（抱枕在坐面不是浮在椅背頂）"
    assert bed_height == 50, "床取半高但夾在 50 以內"
