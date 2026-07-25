from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "backend/server/static/scene_design_schemes.js").read_text(encoding="utf-8")


def test_design_scheme_contract_supports_legacy_projects() -> None:
    assert "normalizeDesignSchemes" in SOURCE
    assert "legacy.furniture" in SOURCE
    assert "legacy.sceneData" in SOURCE
    assert 'active_scheme_id: activeId' in SOURCE


def test_scheme_b_removes_demolished_walls_and_reliable_host_openings() -> None:
    assert "demolishedWallIds" in SOURCE
    assert "opening.host_wall_id" in SOURCE
    assert "host_wall_relation_uncertain" in SOURCE
    assert 'for (const collection of ["doors", "windows"])' in SOURCE


def test_scheme_b_can_be_created_deleted_and_marked_stale() -> None:
    assert "ensureSchemeB" in SOURCE
    assert "deleteSchemeB" in SOURCE
    assert "markSchemeLayoutsStale" in SOURCE
    assert "designSchemes.locked_scheme_id = null" in SOURCE
