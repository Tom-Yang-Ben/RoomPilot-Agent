from __future__ import annotations

from pathlib import Path

import pytest

from backend.catalog.postgres_repository import catalog_provider_mode
from backend.runtime_profile import current_profile, portable_profile


def test_runtime_profile_defaults_to_portable(monkeypatch) -> None:
    monkeypatch.delenv("ROOMPILOT_PROFILE", raising=False)

    assert current_profile() == "portable"
    assert portable_profile() is True


def test_full_profile_selects_strict_postgres_by_default(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ROOMPILOT_PROFILE", "full")
    monkeypatch.delenv("ROOMPILOT_CATALOG_PROVIDER", raising=False)

    assert current_profile() == "full"
    assert catalog_provider_mode(tmp_path) == "postgres"


def test_portable_profile_selects_project_fixture_by_default(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ROOMPILOT_PROFILE", "portable")
    monkeypatch.delenv("ROOMPILOT_CATALOG_PROVIDER", raising=False)

    assert catalog_provider_mode(tmp_path) == "fixture"


@pytest.mark.parametrize("value", ["", "production", "auto", "json"])
def test_invalid_runtime_profile_fails_fast(monkeypatch, value: str) -> None:
    monkeypatch.setenv("ROOMPILOT_PROFILE", value)

    with pytest.raises(RuntimeError, match="invalid ROOMPILOT_PROFILE"):
        current_profile()


def test_invalid_catalog_provider_fails_fast(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ROOMPILOT_PROFILE", "portable")
    monkeypatch.setenv("ROOMPILOT_CATALOG_PROVIDER", "json")

    with pytest.raises(RuntimeError, match="expected fixture or postgres"):
        catalog_provider_mode(tmp_path)
