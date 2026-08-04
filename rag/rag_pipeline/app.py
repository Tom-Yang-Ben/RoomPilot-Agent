"""Gradio UI：輸入家具風格/設計需求 → 解析條件 → 兩階段檢索 → 結果卡片。

需求解析與檢索分別在 query_parser.py / retriever.py，本檔只負責介面與呈現。
結果卡片直接顯示預渲染 PNG（縮圖轉 base64 內嵌，不必設定 Gradio 檔案服務路徑）。

用法：
    .venv-rag/bin/python rag_pipeline/app.py
    瀏覽器開啟 http://127.0.0.1:7860
"""

from __future__ import annotations

import base64
import html
import io
import json
import sys
from functools import lru_cache
from pathlib import Path

import gradio as gr

sys.path.insert(0, str(Path(__file__).resolve().parent))

from query_parser import parse_query  # noqa: E402
from retriever import load_data, retrieve  # noqa: E402

PROJ = Path(__file__).resolve().parent.parent
RENDER_META = PROJ / "vlm_annotation" / "render_meta_full.jsonl"
MAX_CLARIFY = 4
THUMB = 240

ROOM_ZH = {
    "living_room": "客廳", "bedroom": "臥室", "dining_room": "餐廳", "study": "書房",
    "entryway": "玄關", "kids_room": "兒童房", "outdoor": "戶外",
    "bathroom": "浴室", "kitchen": "廚房",
}


@lru_cache(maxsize=1)
def render_index() -> dict:
    """id → 正面渲染圖路徑。

    索引檔不在版控內（每行都是本機絕對路徑），且渲染圖有 2 GB 也不隨 repo 散布，
    所以新環境很可能沒有這個檔。缺檔時回空 dict 讓卡片無圖即可——
    跟 thumb_data_uri() 對缺圖的處理一致，不該讓整個查詢掛掉。
    重建方式：.venv-rag/bin/python vlm_annotation/build_render_meta_full.py
    """
    if not RENDER_META.exists():
        print(f"[app] 找不到 {RENDER_META.name}，卡片將不顯示縮圖", flush=True)
        return {}

    index = {}
    with RENDER_META.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if row.get("images"):
                index[row["id"]] = row["images"][0]
    return index


@lru_cache(maxsize=2048)
def thumb_data_uri(path: str) -> str:
    """PNG → 240px 縮圖 → base64 data URI（避免處理 Gradio 靜態檔路徑授權）。"""
    from PIL import Image

    try:
        img = Image.open(path).convert("RGB")
        img.thumbnail((THUMB, THUMB))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=82)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


def condition_markdown(parsed: dict) -> str:
    rows = []
    if parsed.get("room_type"):
        rows.append(f"**房型** {ROOM_ZH.get(parsed['room_type'], parsed['room_type'])}")
    if parsed.get("styles"):
        zh = load_data()["styles_zh"]
        rows.append("**風格** " + "、".join(f"{zh.get(s, s)}({s})" for s in parsed["styles"]))
    if parsed.get("moods"):
        rows.append("**氛圍** " + "、".join(parsed["moods"]))
    if parsed.get("pattern"):
        rows.append(f"**圖樣** {parsed['pattern']}")
    if parsed.get("budget_total"):
        rows.append(f"**總預算** {parsed['budget_total']:,}")
    if parsed.get("price_level"):
        rows.append(f"**價位** {parsed['price_level']}")
    if parsed.get("color_hint"):
        rows.append(f"**顏色** {parsed['color_hint']}")
    if parsed.get("material_hint"):
        rows.append(f"**材質** {parsed['material_hint']}")
    rows.append(f"**解析把握度** {parsed.get('confidence', 0):.2f}")
    return "### 解析出的條件\n" + "　｜　".join(rows) + f"\n\n<sub>{html.escape(parsed.get('reasoning', ''))}</sub>"


def card_html(row: dict, images: dict) -> str:
    m = row["meta"]
    img = thumb_data_uri(images.get(m["furniture_id"], ""))
    img_tag = (
        f'<img src="{img}" style="width:100%;height:150px;object-fit:contain;background:#f6f6f6;border-radius:6px">'
        if img else '<div style="height:150px;background:#f0f0f0;border-radius:6px"></div>'
    )
    conflict = (
        '<span style="background:#fde68a;padding:1px 5px;border-radius:4px;font-size:11px">分類已修正</span>'
        if m.get("category_conflict") else ""
    )
    zh = load_data()["styles_zh"]
    moods = (m.get("moods_flat") or "").replace("|", "、")
    link = m.get("furniture_id", "")

    return f"""
<div style="border:1px solid #e3e3e3;border-radius:10px;padding:10px;width:220px;">
  {img_tag}
  <div style="font-size:13px;font-weight:600;margin:6px 0 2px;line-height:1.35;height:36px;overflow:hidden">
    {html.escape(m['name_zh'][:40])}
  </div>
  <div style="font-size:12px;color:#555">
    {html.escape(m['category'])} {conflict}<br>
    {html.escape(zh.get(m['style_primary'], m['style_primary']))}｜{html.escape(moods)}<br>
    {m['width_cm']:.0f}×{m['depth_cm']:.0f}×{m['height_cm']:.0f} cm<br>
    <b style="color:#b45309">NT$ {m['price_twd']:,}</b>
  </div>
  <div style="font-size:11px;color:#888;margin-top:4px">
    綜合 {row['score_final']:.3f}（相關 {row['score_rerank']:.2f}／風格 {row['score_style']:.2f}／氛圍 {row['score_mood']:.2f}）
  </div>
  <div style="font-size:10px;color:#bbb;margin-top:2px;word-break:break-all">{html.escape(link)}</div>
</div>"""


def results_html(result: dict) -> str:
    images = render_index()
    parts = []

    head = []
    if result.get("dominant_style"):
        head.append(f"主導風格 <b>{html.escape(result['style_zh'])}({html.escape(result['dominant_style'])})</b>")
    if result.get("budget_total"):
        head.append(f"預算 NT$ {result['budget_total']:,}　首選組合總價 <b>NT$ {result['estimated_total']:,}</b>")
    if head:
        parts.append(f'<div style="margin-bottom:10px;font-size:14px">{"　｜　".join(head)}</div>')

    for block in result["blocks"]:
        tag = ('<span style="background:#dbeafe;padding:1px 6px;border-radius:4px;font-size:12px">建議加入</span>'
               if block["is_inferred"] else "")
        qty = f" ×{block['quantity']}" if block["quantity"] > 1 else ""
        cap = f'<span style="color:#888;font-size:12px">　分配預算 NT$ {block["price_cap"]:,}</span>' if block.get("price_cap") else ""
        parts.append(f'<h3 style="margin:16px 0 8px">{html.escape(block["label_zh"])}{qty} {tag}{cap}</h3>')

        if not block["hits"]:
            parts.append('<div style="color:#b91c1c">這個條件下沒有符合的物件，請放寬預算或尺寸限制。</div>')
            continue
        cards = "".join(card_html(r, images) for r in block["hits"])
        parts.append(f'<div style="display:flex;flex-wrap:wrap;gap:12px">{cards}</div>')

    return "".join(parts)


def search(query: str):
    query = (query or "").strip()
    if not query:
        return ("", "", gr.update(visible=False), *[gr.update(visible=False)] * MAX_CLARIFY, "")

    parsed = parse_query(query)
    result = retrieve(parsed)

    clarify_md = ""
    show_row = False
    btns = [gr.update(visible=False) for _ in range(MAX_CLARIFY)]
    if parsed.get("needs_clarification") and parsed.get("clarify_question"):
        clarify_md = f"**需要確認**：{parsed['clarify_question']}（下方結果先依目前理解呈現）"
        show_row = True
        for i, opt in enumerate(parsed.get("clarify_options", [])[:MAX_CLARIFY]):
            btns[i] = gr.update(value=opt, visible=True)

    return (condition_markdown(parsed), clarify_md, gr.update(visible=show_row), *btns, results_html(result))


def refine(query: str, option: str):
    return search(f"{query}，{option}")


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="RoomPilot 家具風格檢索") as demo:  # Gradio 6：theme 改在 launch() 傳
        gr.Markdown("# RoomPilot 家具風格檢索\n輸入想要的風格或設計，系統會解析條件並從 9,349 件家具中找出最合適的物件。")

        with gr.Row():
            query = gr.Textbox(
                label="你想要什麼樣的家具？",
                placeholder="例如：想要日式侘寂感、預算兩萬內的客廳沙發",
                scale=5,
            )
            go = gr.Button("檢索", variant="primary", scale=1)

        gr.Examples(
            examples=[
                "想要日式侘寂感、預算兩萬內的客廳沙發",
                "北歐風溫馨感的客廳，幫我配一整組，預算十萬",
                "臥室想弄成 loft 那種調調，牆面深色水泥",
                "餐廳要一張餐桌配四張餐椅，中古世紀現代風",
                "想找便宜一點的椅子",
            ],
            inputs=query,
        )

        condition = gr.Markdown()
        clarify = gr.Markdown()
        with gr.Row(visible=False) as clarify_row:
            opt_buttons = [gr.Button(visible=False, size="sm") for _ in range(MAX_CLARIFY)]
        results = gr.HTML()

        outputs = [condition, clarify, clarify_row, *opt_buttons, results]
        go.click(search, inputs=query, outputs=outputs)
        query.submit(search, inputs=query, outputs=outputs)
        for btn in opt_buttons:
            btn.click(refine, inputs=[query, btn], outputs=outputs)

    return demo


if __name__ == "__main__":
    # 啟動時先把 bge-m3 / reranker / Chroma 載進來，避免第一次查詢乾等一分鐘
    print("預熱模型與索引…", flush=True)
    from retriever import load_collection, load_models

    load_models()
    print(f"索引就緒：{load_collection().count()} 筆", flush=True)

    build_ui().launch(
        server_name="127.0.0.1",
        server_port=7860,
        theme=gr.themes.Soft(),
    )
