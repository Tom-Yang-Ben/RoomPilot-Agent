"""Read modular static source families for structural contract tests.

The production browser loads these files as ES modules and ordered stylesheets.
Source-oriented tests should inspect the complete family instead of assuming all
workflow code still lives in one entrypoint file.
"""

from __future__ import annotations

from pathlib import Path


SCENE_CONTROLLER_MODULES = (
    "scene_v2.js",
    "scene_floorplan_controller.js",
    "scene_configuration_controller.js",
    "scene_scheme_controller.js",
    "scene_structure_controller.js",
    "scene_structure_editor_controller.js",
    "scene_questionnaire_controller.js",
    "scene_questionnaire_furniture_controller.js",
    "scene_layout_controller.js",
    "scene_replacement_controller.js",
    "scene_modeling_controller.js",
    "scene_proposal_controller.js",
    "scene_event_bindings.js",
    "scene_restore_controller.js",
)

SCENE_VIEWER_MODULES = (
    "scene_gltf_cache.js",
    "scene_viewer_coordinates.js",
    "scene_viewer_labels.js",
    "scene_viewer_materials.js",
    "scene_viewer_architecture.js",
    "scene_viewer.js",
)

SCENE_STYLESHEETS = (
    "site.css",
    "scene.css",
    "scene-questionnaire.css",
    "scene-structure.css",
    "scene-workflow.css",
)


def read_static_family(static_dir: Path, names: tuple[str, ...]) -> str:
    return "\n".join(
        (static_dir / name).read_text(encoding="utf-8")
        for name in names
    )


def scene_controller_source(static_dir: Path) -> str:
    return read_static_family(static_dir, SCENE_CONTROLLER_MODULES)


def scene_viewer_source(static_dir: Path) -> str:
    return read_static_family(static_dir, SCENE_VIEWER_MODULES)


def scene_stylesheet_source(static_dir: Path) -> str:
    return read_static_family(static_dir, SCENE_STYLESHEETS)
