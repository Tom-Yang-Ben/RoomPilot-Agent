#!/usr/bin/env python3
"""把 content.json 排版成交付 PDF。

分工：這支腳本擁有版面與品牌樣式，你（Claude）只負責寫 content.json 裡的文字。
這樣每一份交付文件的視覺才會一致，而且你不用每次重想排版。

用法：
    python3 build_pdf.py content.json -o 交付文件.pdf [--base-dir .] [--keep-html]

--base-dir 是圖片相對路徑的根目錄（通常就是成果包資料夾）。
content.json 的完整欄位說明見 references/content-schema.md。所有區塊都是選填，
缺的區塊會直接跳過，不會產生空白章節。
"""

import argparse
import base64
import html
import json
import mimetypes
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"

# 幾乎沒有顏色變化的圖，通常是壞掉或還沒產生的圖面。
BLANK_IMAGE_COLORS = 8
WARNINGS = []


def esc(text):
    """跳脫使用者文字，但保留 <b>/<br> 這類簡單標記的意圖：一律跳脫最安全。"""
    return html.escape(str(text)) if text is not None else ""


def para(text):
    """把換行轉成段落，讓 content.json 裡可以直接寫多段文字。"""
    if not text:
        return ""
    blocks = [b.strip() for b in str(text).split("\n") if b.strip()]
    return "".join(f"<p>{esc(b)}</p>" for b in blocks)


def img_src(src, base_dir):
    """回傳可嵌入的 data URI；找不到檔案時回傳 None，讓呼叫端畫佔位框。"""
    if not src:
        return None
    p = Path(src)
    if not p.is_absolute():
        p = (base_dir / p).resolve()
    if not p.exists():
        return None
    _warn_if_blank(p)
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


def _warn_if_blank(path):
    """幾乎純色的圖多半是壞掉的圖面。把它當成有效圖排進提案，屋主會直接看到一塊空白。"""
    try:
        from PIL import Image
    except ImportError:
        return
    try:
        with Image.open(path) as im:
            colors = im.convert("RGB").resize((48, 48)).getcolors(maxcolors=48 * 48)
    except Exception:
        return
    if colors is not None and len(colors) < BLANK_IMAGE_COLORS:
        WARNINGS.append(
            f"{path.name} 幾乎是純色（僅 {len(colors)} 種顏色）——確認這是不是還沒產生的圖面。"
            "若是，不要當成有效圖排進去，改用文字或表格說明，並寫進 appendix.limits。"
        )


def figure(src, caption, base_dir, missing_label="（此空間尚無渲染圖）", cls=""):
    uri = img_src(src, base_dir)
    inner = (
        f'<img src="{uri}">' if uri
        else f'<div class="img-missing">{esc(missing_label)}</div>'
    )
    cap = f"<figcaption>{esc(caption)}</figcaption>" if caption else ""
    klass = f' class="{cls}"' if cls else ""
    return f"<figure{klass}>{inner}{cap}</figure>"


def section_head(no, title, title_en=""):
    en = f'<span class="en">{esc(title_en)}</span>' if title_en else ""
    return (
        f'<div class="section-head"><span class="section-no">{esc(no)}</span>'
        f"<h1>{esc(title)}</h1>{en}</div>"
    )


# --------------------------------------------------------------------------
# 各區塊
# --------------------------------------------------------------------------

def render_cover(meta, base_dir):
    uri = img_src(meta.get("cover_image"), base_dir)
    bg = f'style="background-image:url({uri})"' if uri else 'style="background:#FAF7F2"'
    meta_cells = "".join(
        f'<div><span class="k">{esc(m.get("label"))}</span>{esc(m.get("value"))}</div>'
        for m in meta.get("cover_meta", [])
    )
    return f"""<section class="page cover">
  <div class="cover-image" {bg}></div>
  <div class="cover-kicker">{esc(meta.get('kicker', '室內設計提案 · Interior Design Proposal'))}</div>
  <h1>{esc(meta.get('project_name', '設計提案'))}</h1>
  <div class="cover-sub">{esc(meta.get('subtitle', ''))}</div>
  <div class="cover-meta">{meta_cells}</div>
</section>"""


def render_statement(st, no='01'):
    pillars = "".join(
        f'<div class="pillar avoid-break"><h3>{esc(p.get("title"))}</h3>{para(p.get("body"))}</div>'
        for p in st.get("pillars", [])
    )
    return f"""<section class="page">
  {section_head(no, st.get('title', '設計總論'), st.get('title_en', 'Design Statement'))}
  <div class="lead">{esc(st.get('hook', ''))}</div>
  <div class="pillars">{pillars}</div>
</section>"""


def render_whats_new(wn, no='01'):
    """第二版之後才有的區塊。屋主最想知道的是「我上次說的那件事你改了沒」，
    所以這一頁緊接封面，不能藏在文件最後。"""
    rows = "".join(
        f'<tr><td>{esc(i.get("feedback"))}</td><td>{esc(i.get("response"))}</td></tr>'
        for i in (wn.get("items") or [])
    )
    tbl = (
        '<table class="spec"><tr><th>你提到的</th><th>這一版怎麼處理</th></tr>'
        f"{rows}</table>" if rows else ""
    )
    return f"""<section class="page">
  {section_head(no, wn.get('title', '這一版改了什麼'), wn.get('title_en', "What's Changed"))}
  <div class="lead">{esc(wn.get('hook', ''))}</div>
  {para(wn.get('body'))}
  {tbl}
</section>"""


def render_overview(ov, base_dir, no='02'):
    facts = "".join(
        f'<div><span class="k">{esc(f.get("label"))}</span><span class="v">{esc(f.get("value"))}</span></div>'
        for f in ov.get("facts", [])
    )
    facts_html = f'<div class="facts">{facts}</div>' if facts else ""
    plan = (
        figure(ov.get("plan_image"), ov.get("plan_caption"), base_dir, "（尚無平面圖）")
        if ov.get("plan_image") or ov.get("plan_caption") else ""
    )
    return f"""<section class="page">
  {section_head(no, ov.get('title', '全案速覽'), ov.get('title_en', 'At a Glance'))}
  {para(ov.get('intro'))}
  {facts_html}
  {plan}
</section>"""


def render_room(no, room, base_dir):
    why = "".join(
        f'<li><span class="t">{esc(r.get("title"))}</span>{esc(r.get("body"))}</li>'
        for r in room.get("rationale", [])
    )
    why_html = f'<div class="block"><h3>為什麼這樣設計</h3><ul class="why">{why}</ul></div>' if why else ""
    look_html = (
        f'<div class="block"><h3>這個空間長什麼樣</h3>{para(room.get("look"))}</div>'
        if room.get("look") else ""
    )
    specs = "".join(
        f'<tr><td>{esc(s.get("label"))}</td><td>{esc(s.get("value"))}</td></tr>'
        for s in room.get("specs", [])
    )
    specs_html = (
        '<table class="spec avoid-break"><tr><th>項目</th><th>規格與尺寸</th></tr>'
        f"{specs}</table>" if specs else ""
    )
    extra = "".join(
        figure(i.get("src"), i.get("caption"), base_dir) for i in room.get("extra_images", [])
    )
    extra_html = f'<div class="img-grid">{extra}</div>' if extra else ""
    scene = (
        f'<div class="scene-line">{esc(room.get("scene_line"))}</div>'
        if room.get("scene_line") else ""
    )
    return f"""<section class="page">
  {section_head(no, room.get('name', '空間'), room.get('name_en', ''))}
  {figure(room.get('hero_image'), room.get('hero_caption'), base_dir, cls='hero')}
  {scene}
  <div class="two-col">{look_html}{why_html}</div>
  {specs_html}
  {extra_html}
</section>"""


def render_palette(pal, materials, no='M'):
    swatches = "".join(
        f'<div class="swatch avoid-break"><div class="chip" style="background:{esc(s.get("hex", "#eee"))}"></div>'
        f'<span class="n">{esc(s.get("name"))}</span><span class="u">{esc(s.get("usage"))}</span></div>'
        for s in (pal.get("swatches") or [])
    )
    sw_html = f'<div class="swatches">{swatches}</div>' if swatches else ""
    rows = "".join(
        f'<tr><td>{esc(m.get("area"))}</td><td>{esc(m.get("spec"))}<br>'
        f'<span class="en">{esc(m.get("why", ""))}</span></td></tr>'
        for m in (materials or [])
    )
    mat_html = (
        '<table class="spec"><tr><th>部位</th><th>材質與選用理由</th></tr>'
        f"{rows}</table>" if rows else ""
    )
    return f"""<section class="page">
  {section_head(no, pal.get('title', '色彩與材質'), pal.get('title_en', 'Palette & Materials'))}
  {para(pal.get('intro'))}
  {sw_html}
  {mat_html}
</section>"""


def render_lighting(lt, no='L'):
    rows = "".join(
        f'<tr><td>{esc(i.get("label"))}</td><td>{esc(i.get("value"))}</td></tr>'
        for i in (lt.get("items") or [])
    )
    tbl = f'<table class="spec"><tr><th>位置</th><th>燈具與氛圍</th></tr>{rows}</table>' if rows else ""
    return f"""<section class="page">
  {section_head(no, lt.get('title', '燈光與氛圍'), lt.get('title_en', 'Lighting'))}
  {para(lt.get('intro'))}
  {tbl}
</section>"""


def render_closing(nx, ap, no='N'):
    notes = "".join(f"<li>{esc(n)}</li>" for n in (nx.get("notes") or []))
    notes_html = f'<ul class="notes">{notes}</ul>' if notes else ""
    files = "".join(
        f'<tr><td>{esc(f.get("name"))}</td><td>{esc(f.get("desc"))}</td></tr>'
        for f in (ap.get("files") or [])
    )
    files_html = (
        '<h3 class="label" style="margin-top:var(--sp-5)">檔案清單 FILES</h3>'
        f'<table class="spec"><tr><th>檔名</th><th>說明</th></tr>{files}</table>' if files else ""
    )
    limits = "".join(f"<li>{esc(l)}</li>" for l in (ap.get("limits") or []))
    limits_html = (
        '<h3 class="label" style="margin-top:var(--sp-5)">已知限制 LIMITATIONS</h3>'
        f'<ul class="notes limits">{limits}</ul>' if limits else ""
    )
    version = (
        f'<p class="en" style="margin-top:var(--sp-5);font-size:var(--fs-caption)">'
        f'{esc(ap.get("version_line", ""))}</p>' if ap.get("version_line") else ""
    )
    return f"""<section class="page">
  {section_head(no, nx.get('title', '接下來'), nx.get('title_en', 'Next Steps'))}
  {para(nx.get('body'))}
  {notes_html}
  <hr class="rule">
  {files_html}
  {limits_html}
  {version}
</section>"""


# --------------------------------------------------------------------------

def build_html(content, base_dir):
    tokens = (ASSETS / "tokens.css").read_text(encoding="utf-8")
    layout = (ASSETS / "report.css").read_text(encoding="utf-8")
    meta = content.get("meta", {})

    # 章節編號連續編下去，缺的區塊不留號——屋主看到跳號會以為少了一頁。
    counter = {"n": 0}

    def nxt():
        counter["n"] += 1
        return f"{counter['n']:02d}"

    parts = [render_cover(meta, base_dir)]
    if content.get("whats_new"):
        parts.append(render_whats_new(content["whats_new"], nxt()))
    if content.get("statement"):
        parts.append(render_statement(content["statement"], nxt()))
    if content.get("overview"):
        parts.append(render_overview(content["overview"], base_dir, nxt()))
    for room in content.get("rooms", []):
        parts.append(render_room(nxt(), room, base_dir))
    if content.get("palette") or content.get("materials"):
        parts.append(render_palette(content.get("palette", {}), content.get("materials"), nxt()))
    if content.get("lighting"):
        parts.append(render_lighting(content["lighting"], nxt()))
    if content.get("next_steps") or content.get("appendix"):
        parts.append(render_closing(content.get("next_steps", {}), content.get("appendix", {}), nxt()))

    return f"""<!DOCTYPE html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<title>{esc(meta.get('project_name', '交付文件'))}</title>
<style>{tokens}
{layout}</style></head><body>{''.join(parts)}</body></html>"""


def html_to_pdf(html_path, pdf_path, footer_text):
    from playwright.sync_api import sync_playwright

    footer = (
        '<div style="width:100%;font-size:7pt;color:#A8A29E;'
        'font-family:Inter,sans-serif;padding:0 18mm;display:flex;'
        'justify-content:space-between;">'
        f"<span>{html.escape(footer_text)}</span>"
        '<span class="pageNumber"></span></div>'
    )
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
        page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            display_header_footer=True,
            header_template="<div></div>",
            footer_template=footer,
            margin={"top": "14mm", "bottom": "16mm", "left": "0", "right": "0"},
        )
        browser.close()


def _radical_map():
    """部首碼位 → 一般漢字。

    康熙部首區（U+2F00–）本身有 NFKC 對應；CJK 部首補充區（U+2E80–）沒有，
    但兩區的字元名稱是平行的（CJK RADICAL LONG ONE ↔ KANGXI RADICAL LONG），
    所以用名稱去橋接，不必手寫對照表。對不上的就留著，不影響畫面。
    """
    kangxi = {}
    for cp in range(0x2F00, 0x2FD6):
        ch = chr(cp)
        try:
            kangxi[unicodedata.name(ch).replace("KANGXI RADICAL ", "")] = \
                unicodedata.normalize("NFKC", ch)
        except ValueError:
            continue

    mapping = {chr(cp): unicodedata.normalize("NFKC", chr(cp))
               for cp in range(0x2F00, 0x2FD6)}
    suffixes = (" ONE", " TWO", " THREE", " C-SIMPLIFIED", " SIMPLIFIED", " VARIANT FORM")
    for cp in range(0x2E80, 0x2EF4):
        ch = chr(cp)
        try:
            base = unicodedata.name(ch).replace("CJK RADICAL ", "")
        except ValueError:
            continue
        for cand in (base, *(base[: -len(s)] for s in suffixes if base.endswith(s))):
            if cand in kangxi:
                mapping[ch] = kangxi[cand]
                break
    return {k: v for k, v in mapping.items() if v != k}


def normalize_cjk_codepoints(pdf_path):
    """把文字層裡的康熙部首碼位正規化回一般漢字。

    Chromium 用 Noto CJK 產 PDF 時，部分字（文、山、人、面…）的 ToUnicode 對應會落在
    康熙部首區（U+2E80–U+2FDF）。畫面完全正常，但屋主在 PDF 裡搜尋「文山」會找不到，
    複製出來也是錯字。這裡重寫 ToUnicode CMap，讓文字層跟畫面一致。
    """
    try:
        import pikepdf
    except ImportError:
        return 0

    radicals = _radical_map()

    def norm_hex(raw):
        """只正規化「目的端」的 Unicode 值；來源端是字碼，動了會壞掉。"""
        try:
            text = bytes.fromhex(raw).decode("utf-16-be")
        except (ValueError, UnicodeDecodeError):
            return raw
        fixed_text = "".join(radicals.get(ch, ch) for ch in text)
        return fixed_text.encode("utf-16-be").hex().upper() if fixed_text != text else raw

    def fix_bfchar(m):
        # <src> <dst> 成對出現，只改第二個
        body = re.sub(
            r"(<[0-9A-Fa-f]+>\s*)<([0-9A-Fa-f]+)>",
            lambda p: f"{p.group(1)}<{norm_hex(p.group(2))}>",
            m.group(2),
        )
        return m.group(1) + body + m.group(3)

    def fix_bfrange(m):
        # <lo> <hi> <dst> 三個一組，只改第三個
        body = re.sub(
            r"(<[0-9A-Fa-f]+>\s*<[0-9A-Fa-f]+>\s*)<([0-9A-Fa-f]+)>",
            lambda p: f"{p.group(1)}<{norm_hex(p.group(2))}>",
            m.group(2),
        )
        return m.group(1) + body + m.group(3)

    fixed = 0
    with pikepdf.open(pdf_path, allow_overwriting_input=True) as pdf:
        # 掃全檔物件而不只是頁面資源——字型也可能掛在 XObject 或 Form 底下。
        for obj in pdf.objects:
            try:
                tu = obj.get("/ToUnicode") if isinstance(obj, pikepdf.Dictionary) else None
            except (AttributeError, TypeError):
                continue
            if tu is None:
                continue
            try:
                data = tu.read_bytes().decode("latin-1")
            except Exception:
                continue
            new = re.sub(r"(beginbfchar)([\s\S]*?)(endbfchar)", fix_bfchar, data)
            new = re.sub(r"(beginbfrange)([\s\S]*?)(endbfrange)", fix_bfrange, new)
            if new != data:
                tu.write(new.encode("latin-1"))
                fixed += 1
        if fixed:
            pdf.save()
    return fixed


def layout_report(pdf_path, dpi=40):
    """回報每頁內容到哪裡結束，抓出「整頁只有一張落單表格」這種殘頁。

    為什麼要自動做：手動一頁頁截圖看排版很花時間，而且每份文件都得重來一次。
    這裡直接算給你看，你只要照建議精簡文案再跑一次就好。
    """
    try:
        from PIL import Image
    except ImportError:
        return []
    with tempfile.TemporaryDirectory() as td:
        try:
            subprocess.run(
                ["pdftoppm", "-png", "-r", str(dpi), str(pdf_path), f"{td}/p"],
                check=True, capture_output=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return []
        pages = sorted(Path(td).glob("p*.png"))
        report = []
        for i, img_path in enumerate(pages, start=1):
            with Image.open(img_path) as im:
                g = im.convert("L")
                w, h = g.size
                px = g.load()
                # 頁尾的頁碼在每一頁都有，會讓「內容到哪結束」永遠是滿的；
                # 所以只看版心（頁高 3%–90%）。
                top, foot = int(h * 0.03), int(h * 0.90)
                bottom = top
                for y in range(foot - 1, top - 1, -1):
                    if any(px[x, y] < 235 for x in range(0, w, 3)):
                        bottom = y
                        break
                report.append({"page": i, "fill": round((bottom - top) / (foot - top), 3)})
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("content", help="content.json 路徑")
    ap.add_argument("-o", "--output", default="交付文件.pdf")
    ap.add_argument("--base-dir", default=None, help="圖片相對路徑的根目錄（預設為 content.json 所在資料夾）")
    ap.add_argument("--keep-html", action="store_true", help="保留中繼 HTML 方便除錯")
    ap.add_argument("--no-layout-check", action="store_true", help="略過孤行殘頁檢查")
    args = ap.parse_args()

    content_path = Path(args.content).resolve()
    content = json.loads(content_path.read_text(encoding="utf-8"))
    base_dir = Path(args.base_dir).resolve() if args.base_dir else content_path.parent

    out = Path(args.output).resolve()
    html_path = out.with_suffix(".html")
    html_path.write_text(build_html(content, base_dir), encoding="utf-8")

    meta = content.get("meta", {})
    footer = " · ".join(x for x in [meta.get("project_name"), meta.get("version")] if x)
    html_to_pdf(html_path, out, footer or "RoomPilot")

    if not args.keep_html:
        html_path.unlink(missing_ok=True)

    fixed = normalize_cjk_codepoints(out)

    print(f"✅ 已輸出：{out}")
    if fixed:
        print(f"   已修正 {fixed} 個字型的文字層碼位（PDF 內可正常搜尋中文）")

    missing = [
        f"{r.get('name')} → {r['hero_image']}"
        for r in content.get("rooms", [])
        if r.get("hero_image") and not img_src(r["hero_image"], base_dir)
    ]
    if missing:
        print("⚠️ 找不到下列圖檔，已用佔位框代替：")
        for m in missing:
            print(f"   - {m}")

    for w in dict.fromkeys(WARNINGS):
        print(f"⚠️ {w}")

    if not args.no_layout_check:
        report = layout_report(out)
        total = len(report)
        # 真正的殘頁是「續頁」：前一頁被塞滿，溢出來的兩三行自己占一頁。
        # 章節本身短（例如設計總論只有三個主張）不算問題，不要逼人加廢話。
        # 封面是滿版設計、最後一頁收尾本來就短，兩者都跳過。
        orphans = [
            r for i, r in enumerate(report)
            if 2 < r["page"] < total and r["fill"] < 0.5 and report[i - 1]["fill"] > 0.80
        ]
        if orphans:
            print("\n⚠️ 下列頁面是前一頁溢出來的殘頁：")
            for r in orphans:
                print(f"   - 第 {r['page']} 頁：內容只到版心 {r['fill']:.0%}，前一頁已滿")
            print("   一個空間一頁是這份文件的節奏。修前一頁的內容（由輕到重）："
                  "精簡 look 一兩句、rationale 減到 2 條、specs 減到 4 列、"
                  "移除 extra_images。不要靠加字把殘頁填滿，加出來的一定是廢話。")
        elif total:
            print(f"   版面檢查：{total} 頁，無孤行殘頁")


if __name__ == "__main__":
    main()
