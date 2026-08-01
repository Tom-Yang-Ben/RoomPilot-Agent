"""型錄不可用時不得整頁白屏（QA 2026-08-01 #10）。

home / styles / library 的頂層 await 原本沒有 catch：模組被拒絕時瀏覽器只留
一片白畫布，使用者連 503 都看不到。
"""

from __future__ import annotations

import json
import re

import pytest

from test_scene_workflow import ROOT, run_workflow_script


STATIC = ROOT / "backend" / "server" / "static"
PAGES = ("home.js", "styles.js", "library.js")


@pytest.mark.parametrize("page", PAGES)
def test_top_level_await_is_guarded(page: str) -> None:
    source = (STATIC / page).read_text(encoding="utf-8")

    assert "reportPageBootFailure" in source, f"{page} 沒有回報啟動失敗"
    # 每個頂層 await 都必須在 try 區塊裡（縮排代表它不在模組頂層）。
    unguarded = [
        line
        for line in source.splitlines()
        if re.match(r"^(await |(const|let|var)\s+\w+\s*=\s*await )", line)
    ]
    assert unguarded == [], f"{page} 仍有沒有 catch 的頂層 await：{unguarded}"


def test_common_exports_the_shared_failure_reporter() -> None:
    """橫幅的實際 DOM 行為由 tests/static/page_boot_failure.test.mjs 驗證。"""
    source = (STATIC / "common.js").read_text(encoding="utf-8")

    assert "export function reportPageBootFailure" in source
    assert 'id = "page-boot-error"' in source or '"page-boot-error"' in source
