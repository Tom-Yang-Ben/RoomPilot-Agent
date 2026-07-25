from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENTS_PATH = ROOT / "AGENTS.md"
CLAUDE_PATH = ROOT / "CLAUDE.md"
OVERVIEW_PATH = ROOT / "docs" / "RoomPilot_現行版本總覽.md"


def test_ai_instruction_entrypoints_are_identical() -> None:
    assert AGENTS_PATH.read_bytes() == CLAUDE_PATH.read_bytes()


def test_ai_entrypoints_and_overview_reference_each_other() -> None:
    instructions = AGENTS_PATH.read_text(encoding="utf-8")
    overview = OVERVIEW_PATH.read_text(encoding="utf-8")

    assert "docs/RoomPilot_現行版本總覽.md" in instructions
    assert "`AGENTS.md` 與 `CLAUDE.md`" in overview
    assert "目前固定為十一個編號步驟" in overview
