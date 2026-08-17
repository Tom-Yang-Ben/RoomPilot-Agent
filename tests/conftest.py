"""Keep portable tests isolated from an operator's ignored local ``.env``.

Full-profile PostgreSQL and external-provider checks opt in explicitly in their
own tests. The default suite must remain offline and reproducible even when a
developer is actively running RoomPilot with a full-profile ``.env``.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FLOORPLAN_RUNTIME = PROJECT_ROOT / ".runtime" / "floorplan"
TEST_RUNTIME = Path(tempfile.mkdtemp(prefix="roompilot-pytest-"))

os.environ.update(
    {
        "PYTHON_DOTENV_DISABLED": "1",
        "ROOMPILOT_PROFILE": "portable",
        "ROOMPILOT_CATALOG_PROVIDER": "fixture",
        "ROOMPILOT_MODEL_DELIVERY_MODE": "local",
        "ROOMPILOT_RAG_ENABLED": "false",
        "ROOMPILOT_RUNTIME_DIR": str(TEST_RUNTIME),
        "ROOM_HEAD": str(FLOORPLAN_RUNTIME / "room_head.npz"),
        "ROOMPILOT_SYMBOL_LIBRARY": str(FLOORPLAN_RUNTIME / "symbol_lib.npz"),
    }
)


def pytest_sessionfinish() -> None:
    """Remove the isolated project runtime after the test session completes."""
    shutil.rmtree(TEST_RUNTIME, ignore_errors=True)
