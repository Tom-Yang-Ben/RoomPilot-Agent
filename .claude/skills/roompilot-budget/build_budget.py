#!/usr/bin/env python3
"""把 ReportPayload 排成工程預算報告 HTML（附列印樣式）。

與商業提案（roompilot-proposal）相反：這份文件**沒有任何 LLM 文字**。
每一格都是 payload 既有欄位，本腳本只做排版與格式化，不做計算、不補值。

台灣行情（taiwan_renovation_price_seed.json）以獨立區塊呈現，
**不併入任何小計**——依 PRICE_AND_PRODUCTIVITY_POLICY.md，公開資料參考不等於廠商正式報價。

用法：
    python3 build_budget.py --payload report_payload.json --out budget_report.html
    python3 build_budget.py --payload ... --out ... --no-market-reference
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

# 行情 work_code 與正式 work_item_code 的對應。刻意保守：
# 只有語意與單位都對得上才標對應，其餘明說沒有——寧可留白，不要誤導。
SEED_WORK_ITEM_HINTS: dict[str, str] = {
    "wall_wrap.carpentry": "無對應工項",
    "wall_cladding.single_face": "近似 WALL-WOOD-PANEL，但單位不同（坪 vs m²）",
    "partition.wood": "無對應工項（工項清單未含隔間）",
    "electrical.outlet_relocation": "ELEC-POWER-POINT（單位一致）",
    "electrical.new_circuit": "ELEC-POWER-POINT／ELEC-LIGHT-POINT（單位一致）",
    "furniture.system_cabinet_modification": (
        "近似 BUILTIN-CABINET-INSTALL，但單位不同（台尺 vs 件）"
    ),
}

UNIT_ZH = {"m": "m", "m2": "m²", "ping": "坪", "point": "點", "chi": "台尺", "unit": "件"}

CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body {
  margin: 0; font-family: "PingFang TC", "Noto Sans TC", "Helvetica Neue", sans-serif;
  color: #1c2430; background: #f2f5f9; line-height: 1.6; font-size: 14px;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
.page { max-width: 1080px; margin: 0 auto; padding: 36px 32px 80px; }
header {
  background: #1f3a5f; color: #fff; border-radius: 12px;
  padding: 26px 30px 22px; margin-bottom: 18px;
}
h1 { font-size: 25px; margin: 0 0 8px; font-weight: 700; letter-spacing: -.01em; }
.meta { font-size: 12px; color: #b9c8dc; line-height: 1.9; }
.meta strong { color: #fff; }
.meta code { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 11px; color: #dce7f5; }
.dash {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 14px; margin: 18px 0 4px;
}
.dash .card {
  background: #fff; border: 1px solid #dde4ee; border-top: 3px solid #1f3a5f;
  border-radius: 10px; padding: 14px 16px;
}
.dash .card .label { font-size: 11px; letter-spacing: .1em; color: #5d6b80; font-weight: 600; }
.dash .card .value {
  font-size: 26px; font-weight: 700; margin-top: 6px;
  font-variant-numeric: tabular-nums; color: #1f3a5f;
}
.dash .card .value .unit { font-size: 13px; color: #5d6b80; font-weight: 500; margin-left: 3px; }
.dash .card.good { border-top-color: #1a7f4e; }
.dash .card.good .value { color: #1a7f4e; }
.dash .card.warn { border-top-color: #b45309; }
.dash .card.warn .value { color: #b45309; }
section {
  margin-top: 24px; background: #fff; border: 1px solid #dde4ee;
  border-radius: 12px; padding: 22px 24px 20px;
}
h2 {
  font-size: 15px; font-weight: 700; margin: 0; color: #1f3a5f;
  padding-bottom: 10px; border-bottom: 2px solid #1f3a5f;
}
.hint { font-size: 12px; color: #5d6b80; margin: 10px 0 12px; }
table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12.5px; }
th, td { padding: 8px 9px; border-bottom: 1px solid #e8edf4; text-align: left; vertical-align: top; }
thead th {
  background: #eef3fa; font-weight: 700; font-size: 11.5px; color: #31445e;
  border-bottom: 2px solid #c3d2e5; white-space: nowrap;
}
tbody tr:nth-child(even) td { background: #fafcff; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
td.amount { font-weight: 700; color: #1a7f4e; }
tr.group td {
  background: #e3ebf6 !important; font-weight: 700; font-size: 12px;
  color: #1f3a5f; border-left: 3px solid #1f3a5f;
}
tfoot td {
  font-weight: 700; border-top: 3px double #1f3a5f; border-bottom: 0;
  padding-top: 12px; font-size: 13.5px; color: #1f3a5f; background: #eef3fa;
}
.pending { color: #b45309; font-weight: 700; background: #fff7ea !important; }
.notice {
  border: 1px solid #dde4ee; border-left: 4px solid #1f3a5f; background: #f7fafd;
  border-radius: 6px; padding: 13px 15px; font-size: 12.5px; margin: 14px 0 4px;
  line-height: 1.7;
}
.notice.warn { border-left-color: #b45309; border-color: #f0dcbb; background: #fff7ea; color: #7c5210; }
.small { font-size: 11.5px; color: #5d6b80; }
ul { margin: 8px 0 0; padding-left: 1.3em; }
li { margin-bottom: 5px; }
footer { margin-top: 30px; padding: 16px 6px 0; font-size: 11px; color: #7d8aa0; line-height: 1.9; }
@media print {
  body { background: #fff; font-size: 11px; }
  .page { max-width: none; padding: 0; }
  @page { size: A4; margin: 12mm 10mm; }
  header { border-radius: 0; padding: 16px 18px 14px; }
  section { border: 0; border-radius: 0; padding: 10px 0 4px; break-inside: auto; }
  table { font-size: 9.5px; }
  thead { display: table-header-group; }
  tr, .notice, .dash .card { break-inside: avoid; }
  h2 { break-after: avoid; }
  .dash { gap: 8px; }
}
"""


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def money(value: Any) -> str:
    return "—" if value is None else f"{round(float(value)):,}"


def num(value: Any, digits: int = 2) -> str:
    if value is None:
        return "—"
    text = f"{float(value):,.{digits}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def unit_of(code: Any) -> str:
    return UNIT_ZH.get(str(code), str(code or ""))


def table(headers: list[tuple[str, bool]], rows: list[str], foot: str = "") -> str:
    head = "".join(
        f'<th class="num">{esc(label)}</th>' if is_num else f"<th>{esc(label)}</th>"
        for label, is_num in headers
    )
    tfoot = f"<tfoot>{foot}</tfoot>" if foot else ""
    return (
        f"<table><thead><tr>{head}</tr></thead>"
        f'<tbody>{"".join(rows)}</tbody>{tfoot}</table>'
    )


def quantity_section(payload: dict) -> str:
    quantities = payload.get("quantities") or {}
    rooms = quantities.get("rooms") or []
    if not rooms:
        return ""
    names = {
        room.get("room_id"): room.get("name")
        for room in (payload.get("snapshot") or {}).get("rooms") or []
    }
    rows = []
    for room in rooms:
        rows.append(
            "<tr>"
            f'<td>{esc(names.get(room.get("room_id")) or room.get("room_id"))}</td>'
            f'<td class="num">{num(room.get("length_cm"), 0)} × {num(room.get("width_cm"), 0)}</td>'
            f'<td class="num">{num(room.get("height_cm"), 0)}</td>'
            f'<td class="num">{num(room.get("floor_area_m2"))}</td>'
            f'<td class="num">{num(room.get("ceiling_area_m2"))}</td>'
            f'<td class="num">{num(room.get("perimeter_m"))}</td>'
            f'<td class="num">{num(room.get("gross_wall_area_m2"))}</td>'
            f'<td class="num">{num(room.get("opening_area_m2"))}</td>'
            f'<td class="num">{num(room.get("net_wall_area_m2"))}</td>'
            f'<td class="small">{esc(room.get("geometry_source"))}</td>'
            "</tr>"
        )
    foot = (
        "<tr>"
        '<td colspan="3">合計</td>'
        f'<td class="num">{num(quantities.get("total_floor_area_m2"))}</td>'
        f'<td class="num">{num(quantities.get("total_ceiling_area_m2"))}</td>'
        '<td class="num">—</td><td class="num">—</td><td class="num">—</td>'
        f'<td class="num">{num(quantities.get("total_net_wall_area_m2"))}</td>'
        "<td></td></tr>"
    )
    headers = [
        ("房間", False), ("長 × 寬 (cm)", True), ("高 (cm)", True),
        ("地坪 (m²)", True), ("天花 (m²)", True), ("周長 (m)", True),
        ("牆面毛 (m²)", True), ("開口 (m²)", True), ("牆面淨 (m²)", True),
        ("來源", False),
    ]
    return (
        "<section><h2>一、工程量（決定性計算）</h2>"
        '<p class="hint">由鎖定版本的幾何資料計算，未提供的開口不從影像推測。</p>'
        + table(headers, rows, foot)
        + "</section>"
    )


def estimate_section(payload: dict) -> str:
    estimate = payload.get("estimate") or {}
    lines = estimate.get("lines") or []
    names = {
        room.get("room_id"): room.get("name")
        for room in (payload.get("snapshot") or {}).get("rooms") or []
    }
    rows: list[str] = []
    current_room = object()
    for line in lines:
        room_id = line.get("room_id")
        if room_id != current_room:
            current_room = room_id
            rows.append(
                f'<tr class="group"><td colspan="11">{esc(names.get(room_id) or room_id)}</td></tr>'
            )
        priced = line.get("status") == "priced" and line.get("subtotal") is not None
        amount = (
            f'<td class="num amount" data-subtotal="{esc(line.get("subtotal"))}">'
            f"{money(line.get('subtotal'))}</td>"
            if priced
            else '<td class="num pending" data-subtotal="pending">待詢價</td>'
        )
        rows.append(
            f'<tr class="line" data-code="{esc(line.get("work_item_code"))}">'
            f'<td><code>{esc(line.get("work_item_code"))}</code></td>'
            f'<td>{esc(line.get("trade"))}</td>'
            f'<td>{esc(line.get("name"))}</td>'
            f'<td>{esc(unit_of(line.get("unit")))}</td>'
            f'<td class="num">{num(line.get("raw_quantity"))}</td>'
            f'<td class="num">{num((line.get("waste_rate") or 0) * 100, 1)}%</td>'
            f'<td class="num">{num(line.get("pricing_quantity"), 3)}</td>'
            f'<td class="num">{money(line.get("material_unit_price"))}</td>'
            f'<td class="num">{money(line.get("labor_unit_price"))}</td>'
            f'<td class="num">{money(line.get("other_unit_price"))}</td>'
            f"{amount}</tr>"
        )
    foot = (
        '<tr><td colspan="10">已知小計（不含待詢價工項）</td>'
        f'<td class="num" data-known-subtotal="{esc(estimate.get("known_subtotal"))}">'
        f'{money(estimate.get("known_subtotal"))}</td></tr>'
    )
    headers = [
        ("工項代碼", False), ("工別", False), ("項目", False), ("單位", False),
        ("數量", True), ("損耗", True), ("計價量", True),
        ("材料", True), ("人工", True), ("其他", True), ("小計 (TWD)", True),
    ]
    pending = estimate.get("pending_quote_count") or 0
    total = estimate.get("estimated_total")
    blocks = [
        "<section><h2>二、工程估價明細</h2>",
        f'<p class="hint">共 <span data-line-count="{len(lines)}">{len(lines)}</span> '
        "個工項。小計 = 計價量 ×（材料 + 人工 + 其他）；計價量 = 數量 ×（1 + 損耗率）。</p>",
        table(headers, rows, foot),
    ]
    if pending:
        blocks.append(
            f'<div class="notice warn">其中 <strong>{pending}</strong> 個工項缺正式價格，'
            "狀態為 <code>pending_quote</code>，小計為空且<strong>未計入</strong>上方合計。"
            "取得廠商書面報價後才會有金額，系統不會補猜。</div>"
        )
    blocks.append(
        f'<div class="notice">總計狀態：'
        + (
            f"全部工項皆有價格，預估總額 <strong>NT$ {money(total)}</strong>。"
            if total is not None
            else "尚有工項待詢價，因此<strong>不產生總額</strong>——避免形成假的總價。"
        )
        + f'<br><span class="small">{esc(estimate.get("disclaimer"))}</span></div>'
    )
    blocks.append("</section>")
    return "".join(blocks)


def schedule_section(payload: dict) -> str:
    schedule = payload.get("schedule") or {}
    tasks = schedule.get("tasks") or []
    if not tasks:
        return ""
    rows = []
    for task in tasks:
        rows.append(
            '<tr class="task">'
            f'<td>{esc(task.get("name"))}</td>'
            f'<td><code>{esc(task.get("work_item_code"))}</code></td>'
            f'<td class="num">{num(task.get("quantity"))} {esc(unit_of(task.get("unit")))}</td>'
            f'<td class="num">{num(task.get("daily_productivity"))}</td>'
            f'<td class="num">{num(task.get("crew_count"), 0)}</td>'
            f'<td class="num">{num(task.get("preparation_days"))}</td>'
            f'<td class="num">{num(task.get("construction_days"))}</td>'
            f'<td class="num">{num(task.get("waiting_days"))}</td>'
            f'<td class="num">{num(task.get("total_days"))}</td>'
            f'<td class="num">{num(task.get("start_day"))} – {num(task.get("finish_day"))}</td>'
            f'<td class="small">{esc("、".join(task.get("predecessor_task_ids") or []) or "—")}</td>'
            "</tr>"
        )
    headers = [
        ("作業", False), ("工項代碼", False), ("數量", True), ("日產能", True),
        ("工班", True), ("準備日", True), ("施工日", True), ("等待日", True),
        ("總日數", True), ("起訖（日）", True), ("前置作業", False),
    ]
    unknown = schedule.get("unknown_duration_count") or 0
    blocks = [
        "<section><h2>三、初步排程</h2>",
        f'<p class="hint">共 <span data-task-count="{len(tasks)}">{len(tasks)}</span> '
        "項作業，依結構化工率與前後置關係推算，尚未納入材料交期、社區施工時段與搬運條件。</p>",
        table(headers, rows),
        f'<div class="notice">預估總工期 <strong data-total-days="'
        f'{esc(schedule.get("estimated_total_days"))}">'
        f'{num(schedule.get("estimated_total_days"))}</strong> 日'
        + (f"，其中 {unknown} 項缺工率資料。" if unknown else "。")
        + f'<br><span class="small">{esc(schedule.get("disclaimer"))}</span></div>',
        "</section>",
    ]
    return "".join(blocks)


def mep_section(payload: dict) -> str:
    rooms = (payload.get("retrieval") or {}).get("rooms") or []
    names = {
        room.get("room_id"): room.get("name")
        for room in (payload.get("snapshot") or {}).get("rooms") or []
    }
    rows = []
    for room in rooms:
        for item in room.get("mep_suggestions") or []:
            rows.append(
                "<tr>"
                f'<td>{esc(names.get(item.get("room_id")) or item.get("room_id"))}</td>'
                f'<td>{esc(item.get("related_item_name"))}</td>'
                f'<td>{esc(item.get("system"))}</td>'
                f'<td>{esc(item.get("reason"))}</td>'
                f'<td>{"是" if item.get("covered_by_existing_point") else "否"}</td>'
                f'<td class="small">{esc(item.get("source_id"))}／{esc(item.get("confidence"))}</td>'
                "</tr>"
            )
    if not rows:
        return ""
    headers = [
        ("房間", False), ("關聯設備", False), ("系統", False),
        ("建議原因", False), ("既有點位涵蓋", False), ("來源／信心", False),
    ]
    return (
        "<section><h2>四、水電與空調需求建議</h2>"
        '<p class="hint">僅為需求提示，實際點位、迴路、線徑與容量由設計師與水電技師現場確認。</p>'
        + table(headers, rows)
        + "</section>"
    )


def risk_section(payload: dict) -> str:
    risks = payload.get("risks") or {}
    results = risks.get("results") or []
    if not results:
        return ""
    pending = [item for item in results if not item.get("passed")]
    passed = [item for item in results if item.get("passed")]
    rows = []
    for item in pending + passed:
        rows.append(
            "<tr>"
            f'<td>{"待確認" if not item.get("passed") else "通過"}</td>'
            f'<td>{esc(item.get("severity"))}</td>'
            f'<td><code>{esc(item.get("rule"))}</code></td>'
            f'<td>{esc(item.get("message"))}</td>'
            f'<td>{"需專業確認" if item.get("professional_confirmation_required") else "—"}</td>'
            f'<td class="small">{esc(item.get("rule_source"))}</td>'
            "</tr>"
        )
    headers = [
        ("狀態", False), ("嚴重度", False), ("規則", False),
        ("說明", False), ("專業確認", False), ("判定來源", False),
    ]
    return (
        "<section><h2>五、風險與待確認事項</h2>"
        f'<p class="hint">待確認 <span data-pending-risk="{len(pending)}">{len(pending)}</span> 項、'
        f"通過 {len(passed)} 項。承重牆、迴路、線徑、管徑、排水坡度、防水規格、"
        "空調容量與法規核准一律不自動判定。</p>"
        + table(headers, rows)
        + "</section>"
    )


def market_section(repo_root: Path) -> str:
    seed_file = repo_root / "backend" / "catalog" / "data" / "taiwan_renovation_price_seed.json"
    if not seed_file.is_file():
        return ""
    seed = json.loads(seed_file.read_text(encoding="utf-8"))
    rates = seed.get("rates") or []
    if not rates:
        return ""
    sources = {item.get("id"): item for item in seed.get("sources") or []}
    rows = []
    for rate in rates:
        band = rate.get("range_twd") or {}
        cited = "、".join(
            str(sources.get(sid, {}).get("publisher") or sid)
            for sid in rate.get("source_ids") or []
        )
        note = rate.get("normalization_note") or ""
        rows.append(
            '<tr class="market">'
            f'<td><code>{esc(rate.get("work_code"))}</code></td>'
            f'<td>{esc(unit_of(rate.get("unit")))}</td>'
            f'<td class="num market-amount">{money(band.get("low"))}</td>'
            f'<td class="num market-amount">{money(band.get("base"))}</td>'
            f'<td class="num market-amount">{money(band.get("high"))}</td>'
            f'<td class="small">{esc("、".join(rate.get("inclusions") or []))}</td>'
            f'<td class="small">{esc("、".join(rate.get("exclusions") or []))}</td>'
            f'<td class="small">{esc(SEED_WORK_ITEM_HINTS.get(str(rate.get("work_code")), "—"))}</td>'
            f'<td class="small">{esc(cited)}<br>{esc(rate.get("valid_as_of"))}'
            + (f'<br>{esc(note)}' if note else "")
            + "</td></tr>"
        )
    headers = [
        ("工項代碼", False), ("單位", False), ("低", True), ("中位", True), ("高", True),
        ("含", False), ("不含", False), ("與本報告工項的對應", False), ("來源／時點", False),
    ]
    return (
        "<section><h2>六、市場行情參考（不計入報價）</h2>"
        '<div class="notice warn"><strong>這不是報價。</strong>'
        "下表為公開資料整理的台灣裝潢行情區間，依 "
        "<code>PRICE_AND_PRODUCTIVITY_POLICY.md</code> 的價格優先順序，"
        "公開資料參考位階低於廠商書面報價，且「網路文章價格 ≠ 廠商正式報價」。"
        "本區塊<strong>未計入</strong>第二節的任何小計，僅供判斷詢價結果是否落在合理帶。</div>"
        + table(headers, rows)
        + '<p class="small" style="margin-top:10px">'
        f'資料版本 {esc(seed.get("catalog_version"))}　·　幣別 {esc(seed.get("currency"))}'
        f'　·　地區 {esc(seed.get("region"))}　·　共 {len(rates)} 個工項</p>'
        + "</section>"
    )


def scope_section(payload: dict) -> str:
    assumptions = payload.get("assumptions") or []
    exclusions = payload.get("exclusions") or []
    if not assumptions and not exclusions:
        return ""
    blocks = ["<section><h2>七、前提與排除</h2>"]
    if assumptions:
        blocks.append("<p><strong>假設</strong></p><ul>")
        blocks.extend(f"<li>{esc(item)}</li>" for item in assumptions)
        blocks.append("</ul>")
    if exclusions:
        blocks.append('<p style="margin-top:14px"><strong>不含項目</strong></p><ul>')
        blocks.extend(f"<li>{esc(item)}</li>" for item in exclusions)
        blocks.append("</ul>")
    blocks.append("</section>")
    return "".join(blocks)


def build(payload: dict, repo_root: Path, market: bool) -> str:
    snapshot = payload.get("snapshot") or {}
    project_name = snapshot.get("project_name") or payload.get("project_id") or "專案"
    # 必須是完整文件而非片段：少了 meta charset，用 file:// 開啟時瀏覽器會猜編碼，
    # 中文一律變亂碼（HTTP 供應時有 header 撐著，看不出問題，存成檔案就現形）。
    parts = [
        "<!doctype html>",
        '<html lang="zh-Hant"><head>',
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{esc(project_name)}｜工程預算報告</title>",
        f"<style>{CSS}</style>",
        "</head><body>",
        '<div class="page">',
        "<header>",
        f"<h1>{esc(project_name)}　工程預算報告</h1>",
        '<div class="meta">'
        f'鎖定版本 <strong>{esc(payload.get("revision"))}</strong>　·　'
        f'產生時間 {esc(payload.get("generated_at"))}　·　'
        f'狀態 {esc(payload.get("status"))}<br>'
        f'快照雜湊 <code>{esc(payload.get("snapshot_hash"))}</code>　·　'
        f'套件 <code>{esc(payload.get("package_id"))}</code>'
        "</div>",
        "</header>",
    ]
    if payload.get("demo_mode"):
        parts.append(
            '<div class="notice warn" data-demo="true"><strong>示範資料聲明</strong><br>'
            f'{esc(payload.get("demo_disclaimer") or "示範資料，非正式報價。")}</div>'
        )

    # 總覽卡：把讀者最先要找的四個數字放在最前面，數值皆取自 payload。
    estimate = payload.get("estimate") or {}
    schedule = payload.get("schedule") or {}
    estimate_lines = estimate.get("lines") or []
    pending_count = estimate.get("pending_quote_count") or 0
    dash_cards = [
        ("", "估價工項", f"{len(estimate_lines)}", "項"),
        ("good", "已知小計 (TWD)", money(estimate.get("known_subtotal")), ""),
        (
            "warn" if pending_count else "",
            "待詢價工項",
            f"{pending_count}",
            f"／{len(estimate_lines)} 項",
        ),
        ("", "預估總工期", num(schedule.get("estimated_total_days")), "日"),
    ]
    parts.append('<div class="dash">')
    for card_class, label, value, unit in dash_cards:
        unit_html = f'<span class="unit">{esc(unit)}</span>' if unit else ""
        parts.append(
            f'<div class="card {card_class}"><div class="label">{esc(label)}</div>'
            f'<div class="value">{esc(value)}{unit_html}</div></div>'
        )
    parts.append("</div>")

    narratives = payload.get("narratives") or {}
    for key in ("construction_summary", "cost_summary", "schedule_summary", "risk_summary"):
        if narratives.get(key):
            parts.append(f'<p class="hint">{esc(narratives[key])}</p>')

    parts.append(quantity_section(payload))
    parts.append(estimate_section(payload))
    parts.append(schedule_section(payload))
    parts.append(mep_section(payload))
    parts.append(risk_section(payload))
    if market:
        parts.append(market_section(repo_root))
    parts.append(scope_section(payload))
    parts.append(
        "<footer>"
        f'資料版本 <code>{esc(payload.get("schema_version"))}</code>　·　'
        "本報告所有數值取自同一份 ReportPayload，與商業提案共用相同的快照雜湊。<br>"
        "本文件為設計與詢價前的初步資料，不是正式施工圖或承攬報價。"
        "</footer></div></body></html>"
    )
    return "\n".join(part for part in parts if part)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="由 ReportPayload 產生工程預算報告 HTML。")
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--no-market-reference", action="store_true", help="不附市場行情參考區塊"
    )
    args = parser.parse_args(argv)

    if not args.payload.is_file():
        print(f"找不到檔案：{args.payload}", file=sys.stderr)
        return 2
    payload = json.loads(args.payload.read_text(encoding="utf-8"))
    repo_root = Path(__file__).resolve().parents[3]

    document = build(payload, repo_root, not args.no_market_reference)
    args.out.write_text(document, encoding="utf-8")
    print(f"已產生 {args.out}（{len(document.encode('utf-8')):,} bytes）")
    print("下一步：python3 verify_budget.py --payload ... --html ... 核對一致性")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
