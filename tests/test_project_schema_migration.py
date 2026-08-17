from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from backend.server.project_schema import (
    PROJECT_SCHEMA_VERSION,
    ProjectSchemaUpgradeRequired,
    migrate_project_workflow,
    require_current_project_schema,
)
from backend.server.project_schema_migration import (
    inspect_runtime_schema,
    migrate_runtime_schema,
    restore_runtime_backup,
)
from backend.server.project_store import ProjectStore


def _legacy_workflow() -> dict:
    return {
        "recognition": {
            "coordinate_system": {"unit": "meter"},
            "scale": {"distance_m": 6.3, "m_per_px": 0.01},
            "rooms": [
                {
                    "id": "living",
                    "centroid_m": {"x": 3, "y": 2},
                    "polygon_m": [
                        {"x": 0, "y": 0},
                        {"x": 6, "y": 0},
                        {"x": 6, "y": 4},
                    ],
                }
            ],
        },
        "space_confirmation": {
            "rooms": [
                {
                    "id": "living",
                    "polygon_m": [
                        {"x": 0, "y": 0},
                        {"x": 6, "y": 0},
                        {"x": 6, "y": 4},
                    ],
                }
            ],
            "structures": {
                "walls": [
                    {
                        "scheme_id": "baseline",
                        "demolition_candidate": True,
                        "start": {"x": 0, "y": 0},
                        "end": {"x": 6, "y": 0},
                        "thickness_m": 0.18,
                    }
                ]
            },
            "design_schemes": {
                "active_scheme_id": "B",
                "schemes": {
                    "A": {"id": "A", "kind": "baseline"},
                    "B": {"id": "B", "kind": "alternative"},
                },
            },
        },
        "requirements": {
            "basic": {"overallStyle": "北歐風"},
            "basicConfirmed": True,
            "finishes": {
                "confirmed": True,
                "stylePackId": "scandinavian-light",
                "wallMaterial": "paint",
                "wallColor": "#f4f1eb",
            },
        },
        "layout_2d": {
            "active_scheme_id": "B",
            "room_selections": {"living": "B"},
            "furniture": [{"id": "sofa-a", "xCm": 108, "yCm": 200}],
            "schemes": {
                "B": {
                    "furniture": [{"id": "sofa-b", "xCm": 120, "yCm": 200}],
                    "stale": False,
                }
            },
        },
        "white_model_3d": {
            "sceneData": {
                "floorplan": {
                    "width_cm": 600,
                    "depth_cm": 400,
                    "wall_segments": [
                        {
                            "start": {"x": -3, "z": -2},
                            "end": {"x": 3, "z": -2},
                        }
                    ],
                    "room_regions": [
                        {
                            "room_id": "living",
                            "exterior": [[-3, -2], [3, -2], [3, 2], [-3, 2]],
                            "holes": [],
                        }
                    ],
                },
                "scene_objects": [
                    {
                        "furniture_id": "sofa-b",
                        "normalized_type": "sofa",
                        "placement_room_id": "living",
                        "placement_engine": "furniture_engine",
                        "position_locked": True,
                        "position_cm": {"x": -192, "z": 0},
                        "size_cm": {"width": 200, "depth": 90, "height": 85},
                    }
                ],
            }
        },
    }


def _database(runtime_dir: Path, workflow: dict) -> Path:
    runtime_dir.mkdir(parents=True)
    database = runtime_dir / "projects.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE projects (
                project_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                current_step TEXT NOT NULL,
                workflow_json TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 0,
                upload_filename TEXT,
                upload_extension TEXT,
                upload_mime TEXT,
                upload_path TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO projects (
                project_id, name, current_step, workflow_json, revision,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-project",
                "Legacy",
                "white_model_3d",
                json.dumps(workflow),
                4,
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ),
        )
    return database


def _stored_workflow(database: Path) -> tuple[dict, int]:
    with sqlite3.connect(database) as connection:
        raw, revision = connection.execute(
            "SELECT workflow_json, revision FROM projects WHERE project_id = 'legacy-project'"
        ).fetchone()
    return json.loads(raw), int(revision)


def test_legacy_project_is_migrated_to_one_v4_configuration() -> None:
    migrated = migrate_project_workflow(_legacy_workflow()).workflow

    assert migrated["project_schema_version"] == PROJECT_SCHEMA_VERSION
    assert migrated["recognition"]["scale"] == {
        "distance_cm": 630.0,
        "cm_per_px": 1.0,
    }
    assert migrated["space_confirmation"]["rooms"][0]["polygon_cm"][1] == {
        "x": 600,
        "y": 0,
    }
    assert migrated["space_confirmation"]["structures"]["walls"][0]["thickness_cm"] == 18
    assert "scheme_id" not in migrated["space_confirmation"]["structures"]["walls"][0]
    assert "demolition_candidate" not in migrated["space_confirmation"]["structures"]["walls"][0]
    assert "design_schemes" not in migrated["space_confirmation"]
    requirements = migrated["requirements"]
    model = requirements["roomRequirementModel"]
    assert model["schemaVersion"] == 3
    assert model["globalProfile"] == {"overallStyle": "北歐風"}
    assert model["globalConfirmed"] is True
    assert model["globalFinishes"]["stylePackId"] == "scandinavian-light"
    assert "basic" not in requirements
    assert "basicConfirmed" not in requirements
    assert "finishes" not in requirements
    assert model["roomRequirements"]["living"]["surfaces"]["wallDefault"] == {
        "materialId": "paint",
        "color": "#f4f1eb",
    }
    configuration = migrated["configuration"]
    assert configuration["schema_version"] == PROJECT_SCHEMA_VERSION
    assert configuration["locked"] is False
    assert configuration["furniture"][0]["id"] == "sofa-b"
    assert "schemes" not in configuration
    assert "active_scheme_id" not in configuration
    assert "room_selections" not in configuration
    scene = configuration["sceneData"]
    assert scene["floorplan"]["coordinate_unit"] == "cm"
    assert scene["floorplan"]["wall_segments"][0]["end"] == {"x": 300, "z": -200}
    assert scene["scene_objects"][0]["position_cm"]["x"] == -200
    assert configuration["furniture"][0]["xCm"] == -200
    assert "furniture" not in migrated["layout_2d"]
    assert "schemes" not in migrated["layout_2d"]
    assert "sceneData" not in migrated["white_model_3d"]
    require_current_project_schema(migrated)
    assert migrate_project_workflow(migrated).changed is False


def test_project_store_rejects_unmigrated_workflow(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    _database(runtime, _legacy_workflow())
    store = ProjectStore(runtime)

    with pytest.raises(ProjectSchemaUpgradeRequired):
        store.get_project("legacy-project")


def test_runtime_migration_is_dry_run_idempotent_and_reversible(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    database = _database(runtime, _legacy_workflow())
    original_bytes = database.read_bytes()

    dry_run = migrate_runtime_schema(runtime, dry_run=True)
    assert dry_run.migrated_count == 1
    assert dry_run.backup_dir is None
    assert database.read_bytes() == original_bytes

    migrated = migrate_runtime_schema(runtime)
    assert migrated.migrated_count == 1
    assert migrated.backup_dir
    backup_dir = Path(migrated.backup_dir)
    assert (backup_dir / "manifest.json").is_file()
    workflow, revision = _stored_workflow(database)
    assert workflow["project_schema_version"] == PROJECT_SCHEMA_VERSION
    assert revision == 5
    assert inspect_runtime_schema(runtime).migrated_count == 0
    assert migrate_runtime_schema(runtime).migrated_count == 0

    restored = restore_runtime_backup(runtime, backup_dir)
    assert Path(restored.safety_backup_dir).is_dir()
    restored_workflow, restored_revision = _stored_workflow(database)
    assert "project_schema_version" not in restored_workflow
    assert restored_revision == 4
