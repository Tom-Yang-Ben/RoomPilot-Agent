#!/usr/bin/env python3
"""核對提案文件裡的每一個數字都能在 ReportPayload 找到出處。

這支腳本是整個 proposal skill 的防線。文案可以華麗，數字不行——
只要出現一個 payload 裡沒有的數字，就是 LLM 自己編的，直接 FAIL。

用法：
    python3 verify_numbers.py --payload report_payload.json --html proposal.html
    python3 verify_numbers.py --payload ... --html ... --allow 2026   # 明確放行

比對規則（寬鬆到剛好能吸收排版四捨五入，不會更寬）：
    文件數字 n 合格 ⇔ payload 中存在數字 p，使 n == p
                      或 n == round(p) / round(p,1) / round(p,2)
退出碼：0 = 全部有出處；1 = 有無出處數字；2 = 用法或檔案錯誤。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# 前後不得緊鄰英數或 . # _ ——藉此排除十六進位色碼、雜湊、package_id 這類含數字的識別碼。
NUMBER_RE = re.compile(r"(?<![0-9A-Za-z_.#])(\d[\d,]*(?:\.\d+)?)(?![0-9A-Za-z_.])")
TAG_RE = re.compile(r"<[^>]+>")
DROP_BLOCK_RE = re.compile(r"<(style|script)\b.*?</\1>", re.DOTALL | re.IGNORECASE)
HEX_RE = re.compile(r"#[0-9A-Fa-f]{3,8}\b")


def to_float(token: str) -> float | None:
    try:
        return float(token.replace(",", ""))
    except ValueError:
        return None


def harvest(node: Any, sink: set[float]) -> None:
    """把 payload 裡所有數字收進 sink：數值欄位本身，以及字串裡寫出來的數字。"""
    if isinstance(node, bool):
        return
    if isinstance(node, (int, float)):
        sink.add(float(node))
        return
    if isinstance(node, str):
        for match in NUMBER_RE.finditer(node):
            value = to_float(match.group(1))
            if value is not None:
                sink.add(value)
        return
    if isinstance(node, dict):
        for value in node.values():
            harvest(value, sink)
        return
    if isinstance(node, list):
        for value in node:
            harvest(value, sink)


def structural_counts(payload: dict) -> set[float]:
    """文件會寫出的結構性計數（房間數等），這些是 payload 的長度而非欄位值。"""
    counts: set[float] = set()
    snapshot = payload.get("snapshot") or {}
    counts.add(float(len(snapshot.get("rooms") or [])))
    counts.add(float(len((payload.get("estimate") or {}).get("lines") or [])))
    counts.add(float(len((payload.get("schedule") or {}).get("tasks") or [])))
    counts.add(float(len(payload.get("assumptions") or [])))
    counts.add(float(len(payload.get("exclusions") or [])))
    for room in snapshot.get("rooms") or []:
        counts.add(float(len(room.get("furniture") or [])))
        counts.add(float(len(room.get("materials") or [])))
        counts.add(float(len(room.get("renders") or [])))
    return counts


def html_to_text(document: str) -> str:
    text = DROP_BLOCK_RE.sub(" ", document)
    text = TAG_RE.sub(" ", text)
    return HEX_RE.sub(" ", text)


def matches(value: float, allowed: set[float]) -> bool:
    for source in allowed:
        if value == source:
            return True
        if value == round(source):
            return True
        if value == round(source, 1) or value == round(source, 2):
            return True
    return False


def backed_by(value: float, allowed: set[float], is_percent: bool) -> bool:
    """百分比另外認定：「省下 35%」要能對到 payload 的 0.35，而不是某個無關的 35。

    百分比是行銷文案最常見的造假管道，而小整數在近百個 payload 數字裡很容易
    偶然撞上（例如工率 35.0）。所以 N% 一律要求 N/100 有出處。
    """
    if is_percent:
        return matches(value / 100.0, allowed)
    return matches(value, allowed)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="核對提案文件的數字是否都出自 ReportPayload。"
    )
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument(
        "--allow", action="append", default=[],
        help="明確放行的數字（會在報告中列出，請節制使用）",
    )
    args = parser.parse_args(argv)

    for path in (args.payload, args.html):
        if not path.is_file():
            print(f"找不到檔案：{path}", file=sys.stderr)
            return 2

    payload = json.loads(args.payload.read_text(encoding="utf-8"))
    document = args.html.read_text(encoding="utf-8")

    allowed: set[float] = set()
    harvest(payload, allowed)
    allowed |= structural_counts(payload)

    manual: set[float] = set()
    for token in args.allow:
        value = to_float(token)
        if value is None:
            print(f"--allow 的值不是數字：{token}", file=sys.stderr)
            return 2
        manual.add(value)
    allowed |= manual

    # 文件骨架：少了 meta charset，file:// 開啟時中文會變亂碼。
    # HTTP 供應時有 content-type header 撐著看不出來，存成檔案交付就現形。
    lowered = document.lower()
    encoding_ok = 'charset="utf-8"' in lowered or "charset=utf-8" in lowered
    doctype_ok = lowered.lstrip().startswith("<!doctype html>")

    text = html_to_text(document)
    unbacked: list[tuple[str, str]] = []
    checked = 0
    seen_ok: set[float] = set()

    for match in NUMBER_RE.finditer(text):
        value = to_float(match.group(1))
        if value is None:
            continue
        checked += 1
        tail = text[match.end():match.end() + 2].lstrip()
        is_percent = tail.startswith("%") or tail.startswith("％")
        if backed_by(value, allowed, is_percent):
            seen_ok.add(value)
            continue
        start = max(0, match.start() - 28)
        end = min(len(text), match.end() + 28)
        context = " ".join(text[start:end].split())
        label = f"{match.group(1)}%" if is_percent else match.group(1)
        unbacked.append((label, context))

    print(f"payload 可用數字 {len(allowed)} 個（含結構性計數 {len(structural_counts(payload))} 個）")
    if manual:
        print(f"!! 人工放行 {len(manual)} 個：{'、'.join(str(v) for v in sorted(manual))}")
    print(f"文件中檢出數字 {checked} 處，相異值 {len(seen_ok) + len({u[0] for u in unbacked})} 個")
    print()

    structure: list[str] = []
    if not encoding_ok:
        structure.append('缺少 <meta charset="utf-8">，用 file:// 開啟會出現亂碼')
    if not doctype_ok:
        structure.append("缺少 <!doctype html>，瀏覽器會進入 quirks mode")

    if unbacked or structure:
        if unbacked:
            print(f"[FAIL] {len(unbacked)} 處數字在 ReportPayload 找不到出處：")
            for token, context in unbacked:
                print(f"  - {token}    …{context}…")
            print("這些數字不是從資料來的。改成引用 payload 既有欄位，或刪掉。")
            print()
        if structure:
            print(f"[FAIL] 文件骨架 {len(structure)} 項缺失：")
            for item in structure:
                print(f"  - {item}")
        return 1

    print("[PASS] 文件中每一個數字都能在 ReportPayload 找到出處，且文件骨架完整。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
