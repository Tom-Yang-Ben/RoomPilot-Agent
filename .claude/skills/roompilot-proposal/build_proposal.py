#!/usr/bin/env python3
"""把 ReportPayload 與 agent 寫的文案組成商業提案 HTML。

分工是刻意的：
  - **文案**由 agent 寫，放在 prose.json（風格故事、逐房敘述、開場收尾）。
  - **數字與素材**由本腳本從 ReportPayload 取出並排版，agent 碰不到。

所以提案再怎麼華麗，面積、金額、工期都不可能是編的——它們沒有經過語言模型。

用法：
    python3 build_proposal.py --payload report_payload.json --prose prose.json \
        --out proposal.html [--base-url http://localhost:8000]

prose.json 結構（缺的欄位會留白，不會報錯）：
    {
      "hero_title": "...",
      "hero_subtitle": "...",
      "style_card": "自然木質",          // 選色票用；不填則取該風格第一張
      "style_story": "...",
      "rooms": {"living-1": {"headline": "...", "story": "..."}},
      "closing": "..."
    }
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

FALLBACK_PALETTE = ["#F3EBDD", "#D3B48A", "#8B684B"]

CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body {
  margin: 0; padding: 0;
  font-family: "PingFang TC", "Noto Sans TC", "Helvetica Neue", sans-serif;
  color: #23201c; background: #fbf9f6; line-height: 1.75;
  -webkit-font-smoothing: antialiased;
}
.page { max-width: 940px; margin: 0 auto; padding: 0 32px 96px; }
.hero { padding: 88px 0 40px; border-bottom: 1px solid rgba(0,0,0,.08); }
.eyebrow {
  font-size: 12px; letter-spacing: .22em; text-transform: uppercase;
  color: #8a7f70; margin: 0 0 20px;
}
.hero h1 {
  font-size: clamp(30px, 5vw, 46px); line-height: 1.25; margin: 0 0 18px;
  font-weight: 600; letter-spacing: -.01em;
}
.hero p.sub { font-size: 18px; color: #5d564d; margin: 0; max-width: 34em; }
.palette { display: flex; gap: 0; margin: 36px 0 0; border-radius: 4px; overflow: hidden; }
.palette span { flex: 1; height: 56px; }
.palette-note { font-size: 12px; color: #8a7f70; margin: 10px 0 0; }
section { padding: 56px 0; border-bottom: 1px solid rgba(0,0,0,.08); }
section:last-of-type { border-bottom: 0; }
h2 {
  font-size: 13px; letter-spacing: .18em; text-transform: uppercase;
  color: #8a7f70; font-weight: 600; margin: 0 0 24px;
}
h3 { font-size: 24px; margin: 0 0 14px; font-weight: 600; letter-spacing: -.01em; }
p { margin: 0 0 16px; }
p:last-child { margin-bottom: 0; }
.lede { font-size: 17px; max-width: 40em; }
figure { margin: 0 0 24px; }
figure img {
  width: 100%; max-width: 100%; height: auto; display: block;
  border-radius: 6px; background: #efeae2;
}
figcaption { font-size: 13px; color: #8a7f70; margin-top: 10px; }
.room { margin-bottom: 64px; }
.room:last-child { margin-bottom: 0; }
.facts { width: 100%; border-collapse: collapse; margin-top: 24px; font-size: 14px; }
.facts th, .facts td {
  text-align: left; padding: 11px 0; border-bottom: 1px solid rgba(0,0,0,.07);
  vertical-align: top;
}
.facts th { width: 34%; font-weight: 500; color: #6b6259; }
.facts tr:last-child th, .facts tr:last-child td { border-bottom: 0; }
.summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 28px; }
.stat .label { font-size: 12px; letter-spacing: .12em; color: #8a7f70; text-transform: uppercase; }
.stat .value { font-size: 30px; font-weight: 600; margin-top: 6px; letter-spacing: -.02em; }
.stat .unit { font-size: 14px; font-weight: 400; color: #6b6259; margin-left: 4px; }
ul { margin: 0; padding-left: 1.2em; }
li { margin-bottom: 8px; }
.notice {
  background: #fdf3e3; border: 1px solid #e8d4ae; border-radius: 6px;
  padding: 16px 18px; font-size: 14px; color: #6b5636; margin-bottom: 28px;
}
footer {
  padding: 40px 0 0; font-size: 12px; color: #9a9084; line-height: 2;
  border-top: 1px solid rgba(0,0,0,.08);
}
footer code { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 11px; }
.missing { color: #b0a89c; font-style: italic; }
@media print {
  body { background: #fff; }
  .page { max-width: none; padding: 0 12mm; }
  @page { size: A4; margin: 16mm 0; }
  .hero { padding-top: 0; }
  section { padding: 24px 0; break-inside: auto; }
  .room, figure, .facts, .stat { break-inside: avoid; }
  h3 { break-after: avoid; }
  .notice { border-color: #999; }
}
"""


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def paragraphs(text: str | None, css_class: str = "") -> str:
    if not text:
        return f'<p class="missing">（此段文案未提供）</p>'
    attr = f' class="{css_class}"' if css_class else ""
    blocks = [block.strip() for block in str(text).split("\n\n") if block.strip()]
    return "".join(f"<p{attr}>{esc(block)}</p>" for block in blocks)


def number(value: Any, digits: int = 0) -> str:
    """數字一律由這裡格式化，確保與 payload 一致且可被 verify_numbers 追回。"""
    if value is None:
        return "—"
    if digits == 0:
        return f"{round(float(value)):,}"
    return f"{float(value):,.{digits}f}"


def load_palette(repo_root: Path, style_id: str | None, card_name: str | None):
    cards_file = repo_root / "backend" / "catalog" / "data" / "taiwan_style_cards.json"
    if not cards_file.is_file() or not style_id:
        return FALLBACK_PALETTE, None, None
    data = json.loads(cards_file.read_text(encoding="utf-8"))
    for style in data.get("styles", []):
        if style.get("style_id") != style_id:
            continue
        cards = style.get("cards") or []
        chosen = None
        if card_name:
            chosen = next((c for c in cards if c.get("name_zh") == card_name), None)
        chosen = chosen or (cards[0] if cards else None)
        if chosen:
            return (
                chosen.get("palette_hex") or FALLBACK_PALETTE,
                style.get("style_name_zh"),
                chosen.get("name_zh"),
            )
        return FALLBACK_PALETTE, style.get("style_name_zh"), None
    return FALLBACK_PALETTE, None, None


def room_facts(room: dict, quantity: dict | None) -> str:
    rows: list[tuple[str, str]] = []
    geometry = room.get("geometry") or {}
    if quantity:
        rows.append(("地坪面積", f"{number(quantity.get('floor_area_m2'), 2)} m²"))
        rows.append(("牆面淨面積", f"{number(quantity.get('net_wall_area_m2'), 2)} m²"))
    length, width = geometry.get("length_cm"), geometry.get("width_cm")
    if length and width:
        rows.append(("空間尺寸", f"{number(length)} × {number(width)} cm"))
    if geometry.get("height_cm"):
        rows.append(("天花高度", f"{number(geometry['height_cm'])} cm"))

    materials = room.get("materials") or []
    if materials:
        rows.append((
            "材料計畫",
            "、".join(str(item.get("name")) for item in materials if item.get("name")),
        ))
    furniture = room.get("furniture") or []
    if furniture:
        pieces = []
        for item in furniture:
            name = item.get("name") or item.get("category") or "家具"
            w, d, h = item.get("width_cm"), item.get("depth_cm"), item.get("height_cm")
            if w and d and h:
                pieces.append(
                    f"{name}（{number(w)}×{number(d)}×{number(h)} cm）"
                )
            else:
                pieces.append(str(name))
        rows.append(("配置品項", "、".join(pieces)))

    if not rows:
        return ""
    body = "".join(
        f"<tr><th>{esc(label)}</th><td>{esc(value)}</td></tr>" for label, value in rows
    )
    return f'<table class="facts">{body}</table>'


def build(payload: dict, prose: dict, repo_root: Path, base_url: str) -> str:
    snapshot = payload.get("snapshot") or {}
    rooms = snapshot.get("rooms") or []
    quantities = {
        item.get("room_id"): item
        for item in (payload.get("quantities") or {}).get("rooms", [])
    }
    estimate = payload.get("estimate") or {}
    schedule = payload.get("schedule") or {}
    narratives = payload.get("narratives") or {}

    primary_style = next(
        (room.get("style") for room in rooms if room.get("style")), None
    )
    palette, style_zh, card_zh = load_palette(
        repo_root, primary_style, prose.get("style_card")
    )

    project_name = snapshot.get("project_name") or payload.get("project_id") or "專案"
    revision = payload.get("revision") or ""

    parts: list[str] = []
    parts.append(f"<title>{esc(project_name)}｜設計提案</title>")
    parts.append(f"<style>{CSS}</style>")
    parts.append('<div class="page">')

    # Hero
    parts.append('<header class="hero">')
    parts.append(
        f'<p class="eyebrow">{esc(project_name)}　·　鎖定版本 {esc(revision)}</p>'
    )
    parts.append(f"<h1>{esc(prose.get('hero_title') or project_name)}</h1>")
    if prose.get("hero_subtitle"):
        parts.append(f'<p class="sub">{esc(prose["hero_subtitle"])}</p>')
    swatches = "".join(
        f'<span style="background:{esc(color)}"></span>' for color in palette
    )
    parts.append(f'<div class="palette">{swatches}</div>')
    label = "　·　".join(
        piece for piece in (style_zh, card_zh and f"{card_zh}色票") if piece
    )
    parts.append(
        f'<p class="palette-note">{esc(label)}　{esc(" ".join(palette))}</p>'
    )
    parts.append("</header>")

    if payload.get("demo_mode"):
        parts.append(
            f'<div class="notice" style="margin-top:32px">'
            f'{esc(payload.get("demo_disclaimer") or "示範資料，非正式報價。")}</div>'
        )

    # 風格故事
    parts.append("<section>")
    parts.append("<h2>設計理念</h2>")
    parts.append(paragraphs(prose.get("style_story"), "lede"))
    parts.append("</section>")

    # 逐房
    if rooms:
        parts.append("<section>")
        parts.append("<h2>空間提案</h2>")
        for room in rooms:
            room_id = room.get("room_id")
            room_prose = (prose.get("rooms") or {}).get(room_id) or {}
            parts.append('<div class="room">')
            for render in room.get("renders") or []:
                url = str(render.get("render_url") or "")
                if url.startswith("/") and base_url:
                    url = base_url.rstrip("/") + url
                caption = render.get("view_name") or room.get("name") or ""
                parts.append(
                    f'<figure><img src="{esc(url)}" alt="{esc(caption)}">'
                    f"<figcaption>{esc(caption)}</figcaption></figure>"
                )
            headline = room_prose.get("headline") or room.get("name") or room_id
            parts.append(f"<h3>{esc(headline)}</h3>")
            parts.append(paragraphs(room_prose.get("story")))
            parts.append(room_facts(room, quantities.get(room_id)))
            parts.append("</div>")
        parts.append("</section>")

    # 數字摘要（全部來自 payload）
    parts.append("<section>")
    parts.append("<h2>工程概要</h2>")
    stats = [
        ("空間數", number(len(rooms)), "間"),
        (
            "地坪總面積",
            number((payload.get("quantities") or {}).get("total_floor_area_m2"), 2),
            "m²",
        ),
        ("已知工程小計", f"NT$ {number(estimate.get('known_subtotal'))}", ""),
        ("預估總工期", number(schedule.get("estimated_total_days"), 1), "日"),
    ]
    parts.append('<div class="summary">')
    for label_text, value, unit in stats:
        unit_html = f'<span class="unit">{esc(unit)}</span>' if unit else ""
        parts.append(
            f'<div class="stat"><div class="label">{esc(label_text)}</div>'
            f'<div class="value">{esc(value)}{unit_html}</div></div>'
        )
    parts.append("</div>")
    pending = estimate.get("pending_quote_count")
    if pending:
        parts.append(
            f'<div class="notice" style="margin-top:32px">其中 {esc(number(pending))} '
            f"個工項尚待廠商書面報價，未計入上述小計。</div>"
        )
    for key in ("construction_summary", "cost_summary", "schedule_summary"):
        if narratives.get(key):
            parts.append(f"<p>{esc(narratives[key])}</p>")
    parts.append("</section>")

    # 假設與排除
    assumptions = payload.get("assumptions") or []
    exclusions = payload.get("exclusions") or []
    if assumptions or exclusions:
        parts.append("<section>")
        parts.append("<h2>前提與範圍</h2>")
        if assumptions:
            parts.append("<p><strong>本提案假設</strong></p><ul>")
            parts.extend(f"<li>{esc(item)}</li>" for item in assumptions)
            parts.append("</ul>")
        if exclusions:
            parts.append(
                '<p style="margin-top:24px"><strong>不含項目</strong></p><ul>'
            )
            parts.extend(f"<li>{esc(item)}</li>" for item in exclusions)
            parts.append("</ul>")
        parts.append("</section>")

    if prose.get("closing"):
        parts.append("<section>")
        parts.append("<h2>下一步</h2>")
        parts.append(paragraphs(prose["closing"], "lede"))
        parts.append("</section>")

    parts.append("<footer>")
    parts.append(
        f'資料版本 <code>{esc(payload.get("schema_version"))}</code>　·　'
        f'套件 <code>{esc(payload.get("package_id"))}</code><br>'
        f'快照雜湊 <code>{esc(payload.get("snapshot_hash"))}</code><br>'
        f'產生時間 {esc(payload.get("generated_at"))}<br>'
        "本文件的所有面積、金額與工期均取自同一份 ReportPayload，與工程預算報告同源。"
    )
    parts.append("</footer>")
    parts.append("</div>")
    return "\n".join(parts)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="由 ReportPayload 與文案組出商業提案 HTML。")
    parser.add_argument("--payload", type=Path, required=True, help="report_payload.json")
    parser.add_argument("--prose", type=Path, required=True, help="agent 寫的文案 JSON")
    parser.add_argument("--out", type=Path, required=True, help="輸出 HTML 路徑")
    parser.add_argument(
        "--base-url", default="", help="生圖相對路徑要接的主機，例如 http://localhost:8000"
    )
    args = parser.parse_args(argv)

    for path in (args.payload, args.prose):
        if not path.is_file():
            print(f"找不到檔案：{path}", file=sys.stderr)
            return 2

    payload = json.loads(args.payload.read_text(encoding="utf-8"))
    prose = json.loads(args.prose.read_text(encoding="utf-8"))
    repo_root = Path(__file__).resolve().parents[3]

    document = build(payload, prose, repo_root, args.base_url)
    args.out.write_text(document, encoding="utf-8")
    print(f"已產生 {args.out}（{len(document.encode('utf-8')):,} bytes）")
    print("下一步：python3 verify_numbers.py --payload ... --html ... 核對數字")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
