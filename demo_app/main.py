"""
main.py — RoomPilot「走通骨架」Demo 後端(FastAPI)

把三塊接成一條線,讓老師看得到端到端流程:
  使用者一句話
    → [Agent(stub,柏彥待接真 LLM)] 解析意圖
    → [furniture_engine(真的,ancai 已完成)] 算出家具座標
    → [render_style(stub,舒媁待接 ControlNet)] 產出風格化示意圖
  ( upgrade_to_3d / 平面辨識(cody)之後接在 demo_room() 那裡 )

執行:
  pip install fastapi uvicorn shapely pillow
  uvicorn main:app --reload --port 8000
  瀏覽器開 http://127.0.0.1:8000
"""
from __future__ import annotations

import sys
from pathlib import Path
from collections import Counter

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# 讓 demo_app 找得到上一層的 furniture_engine
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parent))
sys.path.insert(0, str(BASE))

from furniture_engine.models import Room, Wall               # noqa: E402
from furniture_engine.placement import place_furniture_batch  # noqa: E402
from furniture_engine.schema import catalog_from_dict, placed_to_dict  # noqa: E402

import agent_stub            # noqa: E402  (柏彥的位置)
import render_style_stub     # noqa: E402  (舒媁的位置)

app = FastAPI(title="RoomPilot 走通骨架 Demo")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")


def demo_room() -> Room:
    """
    Demo 用固定房間 5m x 4m。
    ▶ 正式版:這裡改成呼叫 upgrade_to_3d / cody 的 floorplan2dxf,
       把上傳的平面圖解析成 Room(walls=...)。介面就是回一個 Room。
    """
    return Room(width=5, depth=4,
                walls=[Wall(0, 0, 5, 0), Wall(5, 0, 5, 4), Wall(5, 4, 0, 4), Wall(0, 4, 0, 0)])


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (BASE / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/health")
def health():
    return {"ok": True, "engine": "furniture_engine 已載入", "agent": "stub", "render_style": "stub"}


@app.post("/api/chat")
async def chat(req: Request):
    """一句話 → Agent 解析 → (若要擺家具)真的跑 furniture_engine → 回座標。"""
    body = await req.json()
    parsed = agent_stub.parse_command(body.get("text", ""))

    room = demo_room()
    placed_dicts = []
    if parsed["intent"] == "place_furniture" and parsed["items"]:
        counter = Counter()
        items = []
        for d in parsed["items"]:
            counter[d["type"]] += 1
            items.append((catalog_from_dict(d), f"{d['type']}_{counter[d['type']]}"))
        result = place_furniture_batch(room, items)   # ← 真引擎
        placed_dicts = [placed_to_dict(p) for p in result["placed"]]

    return JSONResponse({
        "reply": parsed["reply"],
        "intent": parsed["intent"],
        "style": parsed.get("style"),
        "room": {"width": room.width, "depth": room.depth},
        "placed": placed_dicts,
    })


@app.post("/api/render_style")
async def render_style(req: Request):
    """把目前場景 + 風格 → render_style(現在是 stub 示意圖)。"""
    body = await req.json()
    out = render_style_stub.render_style(
        body.get("room", {"width": 5, "depth": 4}),
        body.get("placed", []),
        body.get("style", "北歐"),
    )
    return JSONResponse(out)
