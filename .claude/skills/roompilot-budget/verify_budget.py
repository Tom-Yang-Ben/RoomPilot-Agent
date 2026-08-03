#!/usr/bin/env python3
"""核對工程預算報告與 ReportPayload 一致。

商業提案要防的是「LLM 編數字」；預算書沒有 LLM 文字，要防的是**排版時把資料弄錯**：
漏行、金額對不上、待詢價工項被填上金額、行情參考被混進小計、示範聲明被拿掉。

用法：
    python3 verify_budget.py --payload report_payload.json --html budget_report.html

退出碼：0 = 全部一致；1 = 有不一致；2 = 用法或檔案錯誤。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SUBTOTAL_RE = re.compile(r'data-subtotal="([^"]*)"')
LINE_RE = re.compile(r'<tr class="line"')
TASK_RE = re.compile(r'<tr class="task"')
MARKET_AMOUNT_RE = re.compile(r'class="num market-amount">([\d,]+)<')
AMOUNT_TEXT_RE = re.compile(r'class="num amount"[^>]*>([\d,—]+)<')
ATTR_RE = {
    "line_count": re.compile(r'data-line-count="([^"]*)"'),
    "known_subtotal": re.compile(r'data-known-subtotal="([^"]*)"'),
    "task_count": re.compile(r'data-task-count="([^"]*)"'),
    "total_days": re.compile(r'data-total-days="([^"]*)"'),
    "pending_risk": re.compile(r'data-pending-risk="([^"]*)"'),
    "demo": re.compile(r'data-demo="true"'),
}


def to_float(text: str):
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="核對預算報告與 ReportPayload 一致。")
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--html", type=Path, required=True)
    args = parser.parse_args(argv)

    for path in (args.payload, args.html):
        if not path.is_file():
            print(f"找不到檔案：{path}", file=sys.stderr)
            return 2

    payload = json.loads(args.payload.read_text(encoding="utf-8"))
    document = args.html.read_text(encoding="utf-8")

    estimate = payload.get("estimate") or {}
    lines = estimate.get("lines") or []
    schedule = payload.get("schedule") or {}
    tasks = schedule.get("tasks") or []
    risks = [
        item for item in (payload.get("risks") or {}).get("results") or []
        if not item.get("passed")
    ]

    failures: list[str] = []
    checks: list[str] = []

    # 0. 文件骨架：少了 meta charset，file:// 開啟時中文會變亂碼。
    #    HTTP 供應時有 content-type header 撐著看不出來，存成檔案交付就現形。
    lowered = document.lower()
    if 'charset="utf-8"' in lowered or "charset=utf-8" in lowered:
        checks.append("文件編碼宣告：meta charset=utf-8 ✓")
    else:
        failures.append("缺少 <meta charset=\"utf-8\">，用 file:// 開啟會出現亂碼")
    if not lowered.lstrip().startswith("<!doctype html>"):
        failures.append("缺少 <!doctype html>，瀏覽器會進入 quirks mode")

    def compare(label: str, expected, actual, formatter=str) -> None:
        if expected is None and actual is None:
            checks.append(f"{label}：兩邊皆無")
            return
        if actual is not None and expected is not None and abs(actual - expected) < 0.005:
            checks.append(f"{label}：{formatter(expected)} ✓")
        else:
            failures.append(
                f"{label} 不符：payload {formatter(expected)}，文件 {formatter(actual)}"
            )

    # 1. 明細行數
    rendered_lines = len(LINE_RE.findall(document))
    if rendered_lines == len(lines):
        checks.append(f"估價明細行數：{rendered_lines} ✓")
    else:
        failures.append(f"估價明細行數不符：payload {len(lines)} 行，文件 {rendered_lines} 行")

    declared = ATTR_RE["line_count"].search(document)
    if declared and int(declared.group(1)) != len(lines):
        failures.append(
            f"文件宣告的工項數 {declared.group(1)} 與 payload {len(lines)} 不符"
        )

    # 2/3. 逐行金額與待詢價標示
    rendered_subtotals = SUBTOTAL_RE.findall(document)
    if len(rendered_subtotals) != len(lines):
        failures.append(
            f"金額欄位數不符：payload {len(lines)}，文件 {len(rendered_subtotals)}"
        )
    else:
        mismatched = 0
        pending_with_amount = 0
        for line, cell in zip(lines, rendered_subtotals):
            priced = line.get("status") == "priced" and line.get("subtotal") is not None
            if priced:
                value = to_float(cell)
                if value is None or abs(value - float(line["subtotal"])) > 0.005:
                    mismatched += 1
                    failures.append(
                        f"工項 {line.get('work_item_code')} 小計不符："
                        f"payload {line.get('subtotal')}，文件 {cell}"
                    )
            elif cell != "pending":
                pending_with_amount += 1
                failures.append(
                    f"工項 {line.get('work_item_code')} 狀態為 "
                    f"{line.get('status')} 卻顯示金額 {cell}——待詢價不得補值"
                )
        if not mismatched and not pending_with_amount:
            checks.append(f"逐行小計與待詢價標示：{len(lines)} 行全數一致 ✓")

    # 4. 已知小計
    known = ATTR_RE["known_subtotal"].search(document)
    compare(
        "已知小計",
        estimate.get("known_subtotal"),
        to_float(known.group(1)) if known else None,
        lambda v: f"NT$ {v:,.2f}" if v is not None else "—",
    )

    # 5/6. 排程
    rendered_tasks = len(TASK_RE.findall(document))
    if tasks:
        if rendered_tasks == len(tasks):
            checks.append(f"排程作業數：{rendered_tasks} ✓")
        else:
            failures.append(
                f"排程作業數不符：payload {len(tasks)}，文件 {rendered_tasks}"
            )
        days = ATTR_RE["total_days"].search(document)
        compare(
            "預估總工期",
            schedule.get("estimated_total_days"),
            to_float(days.group(1)) if days else None,
            lambda v: f"{v} 日" if v is not None else "—",
        )

    # 7. 示範聲明
    if payload.get("demo_mode"):
        if ATTR_RE["demo"].search(document):
            checks.append("示範資料聲明：已保留 ✓")
        else:
            failures.append("payload demo_mode=true，但文件沒有示範資料聲明")

    # 8. 行情參考不得混入估價
    market_values = {to_float(v) for v in MARKET_AMOUNT_RE.findall(document)}
    market_values.discard(None)
    if market_values:
        payload_subtotals = {
            round(float(line["subtotal"]))
            for line in lines
            if line.get("subtotal") is not None
        }
        amount_values = {to_float(v) for v in AMOUNT_TEXT_RE.findall(document)}
        amount_values.discard(None)
        leaked = {
            value for value in amount_values & market_values
            if round(value) not in payload_subtotals
        }
        if leaked:
            failures.append(
                "行情參考的金額出現在估價明細：" + "、".join(f"{v:,.0f}" for v in sorted(leaked))
            )
        else:
            checks.append(
                f"行情參考獨立性：{len(market_values)} 個行情數字未混入估價明細 ✓"
            )
        if "這不是報價" not in document:
            failures.append("有行情參考區塊，但缺少「這不是報價」聲明")

    # 9. 待確認風險
    pending_risk = ATTR_RE["pending_risk"].search(document)
    if pending_risk is not None:
        compare(
            "待確認風險項數",
            float(len(risks)),
            to_float(pending_risk.group(1)),
            lambda v: f"{v:.0f} 項" if v is not None else "—",
        )

    for item in checks:
        print(f"  [OK]   {item}")
    print()
    if failures:
        print(f"[FAIL] {len(failures)} 項不一致：")
        for item in failures:
            print(f"  - {item}")
        return 1
    print(f"[PASS] {len(checks)} 項檢查全數通過，文件與 ReportPayload 一致。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
