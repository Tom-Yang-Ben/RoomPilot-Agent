import json

from test_scene_workflow import ROOT, run_workflow_script
from backend.paths import STATIC_DIR


MATERIAL_MODULE = STATIC_DIR / "scene_material_schemes.js"


def test_three_material_schemes_preserve_layout_and_only_override_compatible_slots() -> None:
    module_uri = MATERIAL_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{ generateMaterialSchemes, applyMaterialScheme, restoreOriginalMaterials, updateFurnitureMaterialOverride }} from {json.dumps(module_uri)};

        const scene = {{
          style: {{ style_id: "scandinavian" }},
          style_card: {{ palette_hex: ["#f4efe7", "#b58b63", "#59636a", "#d7c9b8"] }},
          scene_objects: [{{
            furniture_id: "sofa-1",
            position_cm: {{ x: 120, y: 0, z: -35 }},
            rotation_y_deg: 90,
            material_slots: ["seat_fabric", "oak_frame", "steel_leg", "glass_shelf", "mystery"],
          }}],
        }};
        const catalog = {{
          surfaces: [
            {{ surface_id: "oak-a", category: "wood", suitable_styles: ["scandinavian"] }},
            {{ surface_id: "tile-a", category: "tile", suitable_styles: ["scandinavian"] }},
          ],
          style_surface_profiles: {{ scandinavian: {{ floor_surface_ids: ["oak-a", "tile-a"] }} }},
        }};
        const before = JSON.stringify(scene.scene_objects.map((item) => [item.position_cm, item.rotation_y_deg]));
        const schemes = generateMaterialSchemes(scene, catalog);
        const applied = applyMaterialScheme(scene, schemes[0]);
        const edited = updateFurnitureMaterialOverride(applied, {{ furnitureId: "sofa-1", slot: "seat_fabric", finish: "leather", colorHex: "#773322" }});
        const restoredMaterials = restoreOriginalMaterials(edited);
        const after = JSON.stringify(applied.scene_objects.map((item) => [item.position_cm, item.rotation_y_deg]));
        const slots = applied.scene_objects[0].material_overrides;

        console.log(JSON.stringify({{
          schemeIds: schemes.map((item) => item.id),
          before,
          after,
          roles: Object.fromEntries(Object.entries(slots).map(([key, value]) => [key, value.role])),
          unknownPreserved: slots.mystery.preserveOriginal,
          editedFinish: edited.scene_objects[0].material_overrides["role:fabric"].finish,
          restoredOriginal: restoredMaterials.use_original_materials,
        }}));
        """
    )

    assert result["schemeIds"] == ["A", "B", "C"]
    assert result["before"] == result["after"]
    assert result["roles"] == {
        "seat_fabric": "fabric",
        "oak_frame": "wood",
        "steel_leg": "metal",
        "glass_shelf": "glass",
        "mystery": "unknown",
    }
    assert result["unknownPreserved"] is True
    assert result["editedFinish"] == "leather"
    assert result["restoredOriginal"] is True
