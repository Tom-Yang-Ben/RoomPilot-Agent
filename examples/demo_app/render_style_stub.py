"""
render_style_stub.py — 「render_style」的假實作佔位(舒媁之後換成真 ControlNet/depth 生成)

現在(P0 保底):用 PIL 畫一張俯視示意圖(房間 + 家具,依風格上色),當作風格化結果。
                → Demo 一定交得出畫面,不依賴 GPU/API。
之後(舒媁):輸入改成「3D 固定視角圖 / 深度圖 + 風格 prompt」,輸出「ControlNet 生成的風格化圖」。
             **只要函式簽名(輸入 room/placed/style,輸出 image_base64)不變,串接不用改。**

介面契約(v0.1):
  render_style(room: dict, placed: list[dict], style: str) -> dict
    room   = {"width": float, "depth": float}
    placed = [ {id,type,name,width,depth,pos_x,pos_y,rotation}, ... ]  # = furniture_engine 的輸出
    回傳    = {"image_base64": "data:image/png;base64,...", "style": str, "note": str}
"""
import io
import base64
import math
from PIL import Image, ImageDraw

# 各風格的配色(牆 / 地板 / 家具)——之後由真模型的風格 prompt 取代
STYLE_PALETTE = {
    "北歐": {"wall": (236, 234, 227), "floor": (205, 183, 145), "furn": (183, 188, 192)},
    "日式": {"wall": (236, 228, 214), "floor": (216, 196, 160), "furn": (202, 191, 166)},
    "無印": {"wall": (236, 228, 214), "floor": (216, 196, 160), "furn": (202, 191, 166)},
    "工業": {"wall": (70, 72, 80), "floor": (141, 138, 134), "furn": (112, 115, 122)},
    "現代": {"wall": (240, 240, 244), "floor": (214, 214, 220), "furn": (150, 155, 165)},
}


def _rot_rect(cx, cy, w, d, deg):
    """回傳旋轉後矩形的四個角(公尺座標)"""
    a = math.radians(deg or 0)
    ca, sa = math.cos(a), math.sin(a)
    pts = [(-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)]
    return [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts]


def render_style(room: dict, placed: list, style: str) -> dict:
    pal = STYLE_PALETTE.get(style, STYLE_PALETTE["北歐"])
    W, H, PAD = 720, 560, 40
    rw = float(room.get("width", 5)) or 5
    rd = float(room.get("depth", 4)) or 4
    scale = min((W - 2 * PAD) / rw, (H - 2 * PAD) / rd)
    ox = (W - rw * scale) / 2
    oy = (H - rd * scale) / 2
    m2p = lambda x, y: (ox + x * scale, oy + y * scale)

    img = Image.new("RGB", (W, H), (247, 248, 250))
    dr = ImageDraw.Draw(img)

    # 地板
    dr.rectangle([m2p(0, 0), m2p(rw, rd)], fill=pal["floor"], outline=(60, 64, 70), width=3)
    # 家具(旋轉矩形)
    for p in placed or []:
        corners = _rot_rect(p["pos_x"], p["pos_y"], p["width"], p["depth"], p.get("rotation", 0))
        dr.polygon([m2p(x, y) for x, y in corners], fill=pal["furn"], outline=(40, 44, 50))
    # 風格色帶 + 標記(ASCII,避免字型缺字)
    dr.rectangle([0, 0, W, 30], fill=pal["wall"])
    dr.text((12, 9), f"STYLE PREVIEW  |  render_style = STUB (not real ControlNet yet)",
            fill=(60, 64, 70))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return {
        "image_base64": "data:image/png;base64," + b64,
        "style": style,
        "note": "示意圖(俯視上色)。render_style 尚未接 ControlNet,此為 P0 保底畫面。",
    }
