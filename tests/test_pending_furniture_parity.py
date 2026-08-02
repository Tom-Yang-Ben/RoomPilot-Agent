"""待處理判定與修復動作的一致性（QA 2026-08-01 #5、#6）。

三個症狀同源——前端自己另立一套標準：
1. 掃碰撞時沒排除 placement_failed 佔位（伺服器有排除），合法移動被打成待處理。
2. 位移被夾短，訊息卻固定寫「已移動 25 公分」。
3. unassigned 群組照樣渲染重排／換小／擇優，這三個動作必然失敗。
"""

from __future__ import annotations

from test_scene_workflow import ROOT
from backend.paths import STATIC_DIR


def _scene_v2() -> str:
    return (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")


def _slice_function(source: str, name: str) -> str:
    start = source.index(f"function {name}")
    return source[start : source.index("\nfunction ", start + 1)]


def test_collision_scan_ignores_failed_placeholders() -> None:
    """放不下的家具停在 (0,0)，拿它比對會誤傷房間中央的合法家具。"""
    body = _slice_function(_scene_v2(), "itemCollision")

    assert "other.placementFailed === true" in body
    assert "return false" in body


def test_server_still_excludes_failed_placements_from_collision() -> None:
    """對照組：伺服器端的標準不能反過來被改掉。"""
    source = (ROOT / "backend" / "server" / "scene_service.py").read_text(encoding="utf-8")

    assert 'not o.get("placement_failed")' in source


def test_move_reports_the_distance_actually_travelled() -> None:
    viewer = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")

    assert "const movedCm = Math.round(" in viewer
    assert "已移動 ${movedCm} 公分" in viewer
    # 固定寫 step 的舊訊息不能留著。
    assert "已移動 ${Math.round(step)} 公分" not in viewer
    # 完全走不動時要說出來，而不是回報成功。
    assert "已經在可用範圍邊緣" in viewer


def test_unassigned_group_hides_actions_that_cannot_succeed() -> None:
    source = _scene_v2()

    assert 'const unassigned = group.roomId === "unassigned"' in source
    # 重排／換小需要房間尺寸，擇優需要房間，unassigned 一律不渲染。
    assert "const repairAction = unassigned\n        ? \"\"" in source
    assert "${group.items.length && !unassigned ?" in source
    assert "這件家具沒有歸屬房間" in source
