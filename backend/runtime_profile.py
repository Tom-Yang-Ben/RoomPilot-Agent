"""Public runtime profile selection.

The public repository starts in a self-contained portable mode.  Full mode is
an explicit opt-in for developers who provide their own PostgreSQL catalog and
licensed assets.
"""

from __future__ import annotations

import os
from typing import Literal


RuntimeProfile = Literal["portable", "full"]
VALID_RUNTIME_PROFILES = frozenset({"portable", "full"})


def current_profile() -> RuntimeProfile:
    value = os.getenv("ROOMPILOT_PROFILE", "portable").strip().casefold()
    if value not in VALID_RUNTIME_PROFILES:
        choices = ", ".join(sorted(VALID_RUNTIME_PROFILES))
        raise RuntimeError(
            f"invalid ROOMPILOT_PROFILE={value!r}; expected one of: {choices}"
        )
    return value  # type: ignore[return-value]


def portable_profile() -> bool:
    return current_profile() == "portable"
