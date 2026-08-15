from pathlib import Path

from scripts import public_repo_check


def test_markdown_link_check_accepts_local_and_external_targets(tmp_path: Path) -> None:
    target = tmp_path / "target.md"
    target.write_text("ok", encoding="utf-8")
    document = tmp_path / "README.md"
    document.write_text(
        "[local](target.md#section) [external](https://example.test)",
        encoding="utf-8",
    )
    errors: list[str] = []

    public_repo_check._verify_markdown_links(errors, [document])

    assert errors == []


def test_markdown_link_check_reports_missing_target(tmp_path: Path) -> None:
    document = tmp_path / "README.md"
    document.write_text("[missing](does-not-exist.md)", encoding="utf-8")
    errors: list[str] = []

    public_repo_check._verify_markdown_links(errors, [document])

    assert len(errors) == 1
    assert "does-not-exist.md" in errors[0]


def test_text_hygiene_accepts_clean_text() -> None:
    errors: list[str] = []

    public_repo_check._verify_text_hygiene(errors, "clean.py", "value = 1\n")

    assert errors == []


def test_text_hygiene_reports_trailing_whitespace_and_blank_eof() -> None:
    errors: list[str] = []

    public_repo_check._verify_text_hygiene(
        errors,
        "dirty.py",
        "value = 1\nvalue = 2 \n\n",
    )

    assert errors == [
        "trailing whitespace: dirty.py:2",
        "extra blank line at end of file: dirty.py",
    ]
