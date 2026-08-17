"""首頁 bundled asset 與 cache key 契約。"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path


STATIC = Path(__file__).parents[1] / "backend" / "server" / "static"


def test_homepage_hero_asset_exists_and_cache_key_matches() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    match = re.search(
        r'src="/static/(?P<path>assets/home/roompilot-home-hero-v2\.webp)'
        r'\?v=sha256-(?P<digest>[0-9a-f]{12})"',
        html,
    )

    assert match, "首頁必須引用有 content hash 的專案自有 hero 圖片"
    asset = STATIC / match.group("path")
    assert asset.is_file()
    assert hashlib.sha256(asset.read_bytes()).hexdigest()[:12] == match.group("digest")


def test_homepage_hero_is_decorative_and_prioritized() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    hero = re.search(r'<div class="home-hero-media".*?</div>', html, re.DOTALL)

    assert hero
    assert 'alt=""' in hero.group(0)
    assert 'fetchpriority="high"' in hero.group(0)
