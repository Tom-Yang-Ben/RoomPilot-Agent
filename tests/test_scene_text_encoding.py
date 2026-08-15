import json

from test_scene_workflow import ROOT, run_workflow_script


TEXT_MODULE = ROOT / "backend/server/static/scene_text_encoding.js"
SCENE_CONTROLLER = ROOT / "backend/server/static/scene_v2.js"


def test_mojibake_repair_restores_traditional_chinese_without_changing_valid_text() -> None:
    result = run_workflow_script(
        f"""
        import {{ repairMojibake }} from {json.dumps(TEXT_MODULE.as_uri())};
        const broken = (value) => String.fromCharCode(...new TextEncoder().encode(value));
        console.log(JSON.stringify({{
          room: repairMojibake(broken("臥室")),
          furniture: repairMojibake(`LAGAN ${{broken("雙門冰箱，獨立式/白色")}} 115/59 l`),
          validChinese: repairMojibake("咖啡桌"),
          validAccent: repairMojibake("Café"),
        }}));
        """
    )

    assert result == {
        "room": "臥室",
        "furniture": "LAGAN 雙門冰箱，獨立式/白色 115/59 l",
        "validChinese": "咖啡桌",
        "validAccent": "Café",
    }


def test_api_payload_repair_handles_nested_saved_project_data() -> None:
    result = run_workflow_script(
        f"""
        import {{ repairMojibakeDeep }} from {json.dumps(TEXT_MODULE.as_uri())};
        const broken = (value) => String.fromCharCode(...new TextEncoder().encode(value));
        const payload = repairMojibakeDeep({{
          project: {{
            workflow: {{
              rooms: [{{ name: broken("客廳") }}],
              scene_objects: [{{ name_zh_raw: broken("洗脫烘衣機") }}],
            }},
          }},
        }});
        console.log(JSON.stringify(payload));
        """
    )

    assert result["project"]["workflow"]["rooms"][0]["name"] == "客廳"
    assert (
        result["project"]["workflow"]["scene_objects"][0]["name_zh_raw"]
        == "洗脫烘衣機"
    )

    source = SCENE_CONTROLLER.read_text(encoding="utf-8")
    api_function = source.split("async function api(", 1)[1].split(
        "function sceneDataFromGenerateResponse", 1
    )[0]
    assert "repairMojibakeDeep(await response.json())" in api_function
