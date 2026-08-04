"""Keep the default test suite deterministic and independent of local PostgreSQL."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


if os.getenv("ROOMPILOT_TEST_POSTGRES_MAIN") != "1":
    os.environ["ROOMPILOT_PROJECT_STORE_PROVIDER"] = "sqlite"

if os.getenv("ROOMPILOT_TEST_POSTGRES_CATALOGS") != "1":
    os.environ["ROOMPILOT_CATALOG_PROVIDER"] = "json"

if os.getenv("ROOMPILOT_TEST_POSTGRES_RUNTIME_CATALOGS") != "1":
    os.environ["ROOMPILOT_RUNTIME_CATALOG_PROVIDER"] = "json"

# 選件 agent 在正式環境隨 OPENROUTER_API_KEY 啟用。測試必須離線且確定，
# 所以預設關掉；要實打 OpenRouter 時設 ROOMPILOT_TEST_OPENROUTER_SELECTION=1。
if os.getenv("ROOMPILOT_TEST_OPENROUTER_SELECTION") != "1":
    os.environ["OPENROUTER_SELECTION_ENABLED"] = "0"


@pytest.fixture(scope="session", autouse=True)
def isolated_project_store_for_api_tests():
    """Prevent API tests from writing either the developer's SQLite or PostgreSQL."""
    from backend.server import main
    from backend.server.project_store import ProjectStore

    original_store = main.PROJECT_STORE
    with TemporaryDirectory(prefix="roompilot-pytest-projects-") as directory:
        test_store = ProjectStore(Path(directory) / "runtime")
        main.PROJECT_STORE = test_store
        try:
            yield
        finally:
            main.PROJECT_STORE = original_store
            test_store.close()
