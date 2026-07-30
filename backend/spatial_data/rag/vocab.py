"""Small, versioned vocabulary extracted from Django's RAG handoff."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent / "data"


@lru_cache(maxsize=1)
def load_vocab() -> dict[str, Any]:
    groups = json.loads((DATA_DIR / "category_groups.json").read_text(encoding="utf-8"))
    taxonomy = json.loads((DATA_DIR / "taxonomy.json").read_text(encoding="utf-8"))
    return {
        "groups": groups["groups"],
        "room_default_sets": groups["room_default_sets"],
        "styles": taxonomy["styles"],
        "style_compat": taxonomy["style_compat"],
        "patterns": taxonomy["patterns"],
        "moods": taxonomy["moods"],
    }
