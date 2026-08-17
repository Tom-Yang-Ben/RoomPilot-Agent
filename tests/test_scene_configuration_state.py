from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "backend/server/static/scene_configuration_state.js").read_text(
    encoding="utf-8"
)


def test_configuration_state_requires_canonical_v4_payload() -> None:
    assert "normalizeConfigurationState" in SOURCE
    assert "project_configuration_schema_upgrade_required" in SOURCE
    assert "schema_version: 4" in SOURCE
    assert "saved.furniture" in SOURCE
    assert "saved.sceneData" in SOURCE
    assert "active_scheme_id" not in SOURCE
    assert "room_selections" not in SOURCE


def test_configuration_state_clones_confirmed_structures() -> None:
    assert "export function cloneStructures" in SOURCE
    assert "clone(structures[collection] || [])" in SOURCE
    assert "demolishedWallIds" not in SOURCE


def test_configuration_can_be_marked_stale_and_unlocked() -> None:
    assert "markConfigurationStale" in SOURCE
    assert "configurationState.locked = false" in SOURCE


def test_configuration_state_persists_only_direct_furniture_and_scene() -> None:
    assert "persistConfigurationState" in SOURCE
    assert "configurationState.furniture" in SOURCE
    assert "configurationState.sceneData" in SOURCE
    assert "schemes" not in SOURCE
