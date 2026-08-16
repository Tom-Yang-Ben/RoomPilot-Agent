from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "backend/server/static/scene_design_schemes.js").read_text(encoding="utf-8")


def test_design_scheme_contract_requires_canonical_project_configuration() -> None:
    assert "normalizeDesignSchemes" in SOURCE
    assert "project_configuration_schema_upgrade_required" in SOURCE
    assert "legacy.furniture" not in SOURCE
    assert "legacy.sceneData" not in SOURCE
    assert "schema_version: 3" in SOURCE
    assert 'active_scheme_id: activeId' in SOURCE


def test_scheme_a_and_b_share_the_same_confirmed_structures() -> None:
    assert "export function structuresForScheme" in SOURCE
    assert "void schemeId" in SOURCE
    assert "clone(structures[collection] || [])" in SOURCE
    assert "demolishedWallIds" not in SOURCE


def test_scheme_b_can_be_created_and_marked_stale_without_structure_cleanup() -> None:
    assert "ensureSchemeB" in SOURCE
    assert "deleteSchemeB" not in SOURCE
    assert "markSchemeLayoutsStale" in SOURCE
    assert "designSchemes.locked_scheme_id = null" in SOURCE


def test_room_level_scheme_selection_is_persistable_and_invalidates_snapshots() -> None:
    assert "room_selections: validRoomSelections(saved.room_selections)" in SOURCE
    assert "configuration_snapshot" in SOURCE
    assert "export function selectSchemeForRoom" in SOURCE
    assert "export function allRoomsHaveSchemeSelections" in SOURCE
    assert "designSchemes.configuration_snapshot = null" in SOURCE
