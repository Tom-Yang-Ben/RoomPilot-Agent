"""第 6 步待處理清單的 DOM 行為門檻。

契約測試只比對 scene_v2.js 的原始碼字串，所以「按鈕畫得出來、handler 卻是死的」會全綠通過——
2026-08-01 的 QA 就是這樣被三件放不下的家具卡在第 6 步。這裡改用 jsdom 真的按下按鈕，
要求每個修復動作都留下使用者看得見的訊息。

本機安裝：`cd tests/static && npm install`
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from test_scene_workflow import ROOT

STATIC_TESTS = ROOT / "tests" / "static"


def test_step_six_pending_actions_never_fail_silently() -> None:
    if shutil.which("node") is None:
        pytest.skip("需要 node 才能執行 jsdom 行為測試")
    if not (STATIC_TESTS / "node_modules" / "jsdom").exists():
        pytest.skip("尚未安裝 jsdom：先執行 `cd tests/static && npm install`")

    result = subprocess.run(
        ["node", "--test"],
        cwd=STATIC_TESTS,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
