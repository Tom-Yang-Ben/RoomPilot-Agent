import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
OVERVIEW_PATH = ROOT / "docs" / "RoomPilot_現行版本總覽.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(document: str, heading: str) -> str:
    start = document.index(heading) + len(heading)
    remainder = document[start:]
    next_heading = re.search(r"^##? ", remainder, flags=re.MULTILINE)
    return remainder[: next_heading.start()] if next_heading else remainder


def test_readme_and_overview_link_to_each_other() -> None:
    readme = _read(README_PATH)
    overview = _read(OVERVIEW_PATH)

    assert "(docs/RoomPilot_現行版本總覽.md)" in readme
    assert "[README](../README.md)" in overview
    assert "README 是安裝、啟動、資產準備與常用測試的操作入口" in readme
    assert "本文件負責產品流程、跨模組協作、資料邊界與接入狀態" in overview


def test_product_flow_steps_match() -> None:
    readme_flow = _section(_read(README_PATH), "## 現行流程")
    overview_flow = _section(_read(OVERVIEW_PATH), "## 產品流程")

    readme_steps = [
        int(value)
        for value in re.findall(r"^(?:→ )?(\d+) ", readme_flow, flags=re.MULTILINE)
    ]
    overview_steps = [
        int(value)
        for value in re.findall(r"^\|\s*(\d+)\s*\|", overview_flow, flags=re.MULTILINE)
    ]

    assert readme_steps == list(range(1, 12))
    assert overview_steps == readme_steps


def test_shared_runtime_and_data_invariants_match() -> None:
    readme = _read(README_PATH)
    overview = _read(OVERVIEW_PATH)

    shared_invariants = (
        "/scene",
        "backend/server/main.py",
        "coordinate_unit: \"cm\"",
        "_cm",
        "_m2",
    )
    for invariant in shared_invariants:
        assert invariant in readme
        assert invariant in overview


def test_team_module_ownership_matches() -> None:
    readme = _read(README_PATH)
    overview = _read(OVERVIEW_PATH)
    ownership = {
        "Cody": ("backend/floorplan/", "backend/upgrade3d/"),
        "Kai": ("backend/catalog/",),
        "Django": ("backend/spatial_data/",),
        "Yen": ("backend/agent/",),
        "AN": ("backend/engine/",),
        "Bella": ("backend/server/", "frontend3d/"),
    }

    for owner, paths in ownership.items():
        assert owner in readme
        assert owner in overview
        for path in paths:
            assert path in readme
            assert path in overview
