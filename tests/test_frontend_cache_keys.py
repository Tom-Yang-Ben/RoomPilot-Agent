"""`frontend/` 的 `?v=sha256-` cache key 必須與檔案內容相符。

這類錯誤不會讓頁面壞掉——瀏覽器照樣載得到檔案——所以只會靜靜地失效：key 不再
隨內容變動，使用者拿到舊快取卻沒有任何徵兆。既有測試只釘住 scene / rag /
engineering 三個入口與一份手寫的相依表，`library.html` 的兩個 key 因此過期很久
都沒被發現，`scene_v2.js` 裡還有一個掛著 `sha256-` 前綴、值卻是手寫日期的宣告。

第二個成因是行尾。cache key 是內容的 SHA-256，同一份檔案在 CRLF 工作區會算出
不同的值；`.gitattributes` 的 `eol=lf` 只在檔案被檢出時生效，早於該規則存在的
檔案會留在 CRLF，於是「本機綠、新 clone 紅」。所以這裡連 CR 一起擋。
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from backend.paths import STATIC_DIR


# 只認 sha256- 前綴的宣告。`?v=20260708s` 這種手寫日期版本號不在本契約內——
# 要嘛別宣稱是 sha256，要嘛就得是真的。
DECLARATION = re.compile(
    r"""["'(]([^"'()\s]+?\.(?:js|css|mjs))\?v=sha256-([^"'()\s]+)"""
)

SCANNED_SUFFIXES = {".html", ".js", ".mjs", ".css"}


def _declarations() -> list[tuple[Path, str, str]]:
    found: list[tuple[Path, str, str]] = []
    for source in sorted(STATIC_DIR.rglob("*")):
        if source.suffix not in SCANNED_SUFFIXES:
            continue
        if "vendor" in source.relative_to(STATIC_DIR).parts:
            continue
        text = source.read_text(encoding="utf-8", errors="ignore")
        for match in DECLARATION.finditer(text):
            found.append((source, match.group(1), match.group(2)))
    return found


def _resolve(source: Path, reference: str) -> Path:
    """`/static/x.js` 走掛載前綴，`./x.js` 相對於引用它的檔案。"""
    if reference.startswith("/static/"):
        return STATIC_DIR / reference[len("/static/") :]
    return (source.parent / reference).resolve()


def test_every_declared_cache_key_matches_its_file() -> None:
    declarations = _declarations()
    assert declarations, "掃不到任何 cache key 宣告，代表這支測試的解析壞了"

    stale: list[str] = []
    for source, reference, declared in declarations:
        origin = source.relative_to(STATIC_DIR)
        target = _resolve(source, reference)
        if not target.is_file():
            stale.append(f"{origin} → {reference}：目標檔案不存在")
        elif not re.fullmatch(r"[0-9a-f]{12}|[0-9a-f]{64}", declared):
            stale.append(
                f"{origin} → {reference}：{declared} 不是 sha256"
                "（要 12 或 64 位小寫十六進位）"
            )
        else:
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            if not actual.startswith(declared):
                stale.append(
                    f"{origin} → {reference}：宣告 {declared}，實際 {actual[: len(declared)]}"
                )

    assert not stale, "cache key 與內容不符：\n" + "\n".join(stale)


def test_hashed_files_stay_lf_so_keys_are_machine_independent() -> None:
    """被雜湊的檔案含 CR，key 就會隨檢出這份 repo 的機器而變。"""
    crlf = {
        str(target.relative_to(STATIC_DIR))
        for source, reference, _ in _declarations()
        if (target := _resolve(source, reference)).is_file()
        and b"\r" in target.read_bytes()
    }
    assert not crlf, "被 cache key 雜湊的檔案含 CR：\n" + "\n".join(sorted(crlf))
