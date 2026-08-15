from __future__ import annotations

import re
from pathlib import Path

from scripts.update_static_hashes import static_content_digest


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "backend" / "server" / "static"


def test_rag_page_assets_have_matching_content_hashes() -> None:
    html = (STATIC / "rag.html").read_text(encoding="utf-8")
    css_hash = re.search(r"rag\.css\?v=sha256-([0-9a-f]{64})", html)
    js_hash = re.search(r"rag\.js\?v=sha256-([0-9a-f]{64})", html)

    assert css_hash and css_hash.group(1) == static_content_digest(STATIC / "rag.css")
    assert js_hash and js_hash.group(1) == static_content_digest(STATIC / "rag.js")


def test_rag_navigation_is_hidden_from_formal_pages() -> None:
    for name in ("index.html", "styles.html", "library.html", "rag.html"):
        html = (STATIC / name).read_text(encoding="utf-8")
        assert 'href="/rag"' not in html


def test_rag_frontend_uses_safe_rendering_and_cancels_stale_requests() -> None:
    source = (STATIC / "rag.js").read_text(encoding="utf-8")

    assert "innerHTML" not in source
    assert "textContent" in source
    assert "AbortController" in source
    assert "activeRequest?.abort()" in source
    assert "activeRequest === requestController" in source
    assert 'fetch("/api/rag/status"' in source
    assert 'fetch("/api/rag/search/jobs"' in source
    assert "rag-progress-fill" in source
    assert "aria-valuenow" in source
    assert "waitForJob" in source
    assert "safeHttpUrl" in source


def test_rag_page_states_and_boundary_are_visible() -> None:
    html = (STATIC / "rag.html").read_text(encoding="utf-8")
    js = (STATIC / "rag.js").read_text(encoding="utf-8")

    for marker in (
        "rag-stage-list",
        "rag-debug-json",
        "rag-clarification",
        "rag-results",
        "rag-progress-track",
        "rag-progress-percent",
    ):
        assert f'id="{marker}"' in html
    assert "retrieval_only_no_geometry_legality" in html
