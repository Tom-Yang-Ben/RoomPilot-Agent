"""一鍵測試「最後一步」：生圖 → 設計手冊 PDF（含客廳日光＋夜間兩張）。

跑的是 agent pipeline（MasterAgent → ReportAgent），也就是客廳夜間光影功能所在。
把問卷/格局/家具型錄都放在同資料夾 data/，改資料不用動程式。

用法（從 repo 根目錄）：
    .venv/Scripts/python.exe manual_test_kit/run_manual_test.py            # 離線假圖（免金鑰）
    .venv/Scripts/python.exe manual_test_kit/run_manual_test.py --real     # 真的打 OpenRouter 生圖

離線模式：日光圖=暖色、夜間圖=深藍，方便直接在 PDF 裡看出客廳有兩張。
真實模式：需 OPENROUTER_API_KEY；影像與手冊前言/理念改由真模型產生，家具仍用 data/ 的假型錄。
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent
REPO = KIT.parent
sys.path.insert(0, str(REPO))  # 讓 backend.agent 可被 import（從任何路徑執行都行）

# Windows 主控台預設 cp950 會卡中文/符號輸出；統一切 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from PIL import Image, ImageDraw  # repo 既有依賴

from backend.agent.documents import DocKey
from backend.agent.llm import ImageResult, LLMError
from backend.agent.master import MasterAgent, MasterConfig, MasterState
from backend.agent.subagents import (
    FurnitureAgent,
    GenPicAgent,
    ReportAgent,
    ValidationAgent,
)

DATA = KIT / "data"
OUT = KIT / "output"


# --------------------------------------------------------------- 離線假件

def _png_b64(bg: tuple[int, int, int], label: str, size=(640, 480)) -> str:
    img = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(img)
    ink = (245, 245, 245) if sum(bg) < 360 else (60, 55, 50)
    try:
        font = ImageDraw.ImageFont.load_default(size=40)
    except TypeError:  # 舊版 Pillow
        font = ImageDraw.ImageFont.load_default()
    draw.text((28, 28), label, fill=ink, font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


class LocalImageGateway:
    """離線假生圖：依提示詞是否含「夜」決定畫暖色(日)或深藍(夜)色塊，永不失敗。"""

    available = True
    image_model = "local-fake/day"
    image_fallback_model = "local-fake/fallback"

    def __init__(self) -> None:
        self.log: list[str] = []

    def chat(self, messages, *, model=None, temperature=0.3, force_json=False, reasoning=None):
        # 不接文字模型 → 報告前言/理念走 deterministic 底稿。
        raise LLMError("離線測試不提供文字模型")

    def generate_image(self, prompt, *, images=(), model=None) -> ImageResult:
        night = "夜" in prompt
        self.log.append("night" if night else "day")
        seq = len(self.log)
        # 刻意用 day/night 專屬 model 名（忽略傳入的 model），讓 PDF 標註一看就懂。
        if night:
            return ImageResult(image_b64=_png_b64((28, 33, 62), f"NIGHT #{seq}"), model="local-fake/night")
        return ImageResult(image_b64=_png_b64((236, 226, 205), f"DAY #{seq}"), model="local-fake/day")


class LocalRetriever:
    """依查詢文字裡的房名（客廳/主臥）回傳 data/ 的假型錄。"""

    def __init__(self, catalog: dict) -> None:
        self._catalog = {k: v for k, v in catalog.items() if not k.startswith("_")}

    def search(self, query: str, *, top_k: int = 8) -> list[dict]:
        for token, rows in self._catalog.items():
            if token in (query or ""):
                return list(rows)[:top_k]
        return []


# ------------------------------------------------------------------- 流程

def _load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def main() -> int:
    real = "--real" in sys.argv or os.getenv("MANUAL_TEST_REAL")
    layout = _load("layout_json.json")
    questionnaire = _load("questionnaire.json")
    catalog = _load("furniture_candidates.json")

    if real:
        from backend.agent.llm import OpenRouterGateway

        gw = OpenRouterGateway()
        if not gw.available:
            print("[X] --real 需要 OPENROUTER_API_KEY，未設定。改用預設離線模式即可。")
            return 1
        image_gateway, report_gateway = gw, gw
        print(f">> 真實模式：OpenRouter 生圖 model={gw.image_model}")
    else:
        image_gateway, report_gateway = LocalImageGateway(), None
        print(">> 離線模式：假圖（日光=暖色 / 夜間=深藍），報告走 deterministic 底稿")

    OUT.mkdir(parents=True, exist_ok=True)
    master = MasterAgent(
        FurnitureAgent(None, retriever=LocalRetriever(catalog)),
        ValidationAgent(None),
        GenPicAgent(image_gateway),
        ReportAgent(report_gateway),
        config=MasterConfig(output_dir=str(OUT)),
    )

    # S0 載入格局 → S1 問卷 → S3/4 A/B 方案
    master.start(layout)
    master.submit({"questionnaire": questionnaire})

    # 擇 A 方案 + 逐房視角（img2img 參考圖；假模式用純色佔位）
    ref = _png_b64((210, 210, 210), "VIEWPOINT")
    viewpoints = {
        r["room_id"]: {
            "viewpoint_id": f"vp-{r['room_id']}",
            "note": r.get("name", ""),
            "image_b64": ref,
        }
        for r in layout["rooms"]
    }
    pause = master.submit({"variant": "A", "viewpoints": viewpoints})

    # S5a 色卡比對（有色卡才需擇一）
    if pause.state == MasterState.AWAIT_PALETTE_CHOICE:
        palette_id = (questionnaire.get("palette_options") or [{}])[0].get("palette_id")
        pause = master.submit({"palette_id": palette_id})

    if pause.state == MasterState.AWAIT_RENDER_RETRY:
        print("[WARN] 生圖階段失敗，原因：", pause.payload.get("failure_notices"))
        pause = master.submit({"skip": True})

    # 跳過改圖 → S7 輸出設計手冊 PDF
    if pause.state == MasterState.AWAIT_FEEDBACK:
        pause = master.submit({"skip": True})

    # ---- 結果摘要 ----
    records = (master.store.get(DocKey.IMAGES) or {}).get("records") or []
    print("\n=== 生圖紀錄 ===")
    for r in records:
        print(f"  [{r['stage']:>17}] {r['room_id']:<8} {r['image_id']}  (model={r['model']})")
    night = [r for r in records if r["stage"] == "full_render_night"]
    print(f"\n客廳夜間圖數量：{len(night)}  → " + (", ".join(r["room_id"] for r in night) or "（無）"))

    pdf = pause.payload.get("pdf_path")
    print(f"\n[OK] 設計手冊 PDF：{pdf}")
    print("   （第七章「渲染成果」客廳應有日光＋夜間兩張並列）")
    return 0 if pdf and Path(pdf).exists() else 2


if __name__ == "__main__":
    raise SystemExit(main())
