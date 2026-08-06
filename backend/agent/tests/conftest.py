"""共用假件與測資：不碰網路、不碰資料庫、不需要 OPENROUTER_API_KEY。"""
from __future__ import annotations

import base64
import io

import pytest
from PIL import Image

from backend.agent.llm import ImageResult, LLMError
from backend.agent.master import MasterAgent, MasterConfig
from backend.agent.subagents import (
    FurnitureAgent,
    GenPicAgent,
    ReportAgent,
    ValidationAgent,
)


def make_png_b64(color=(200, 180, 150), size=(64, 64)) -> str:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


class FakeImageGateway:
    """可程式化失敗次數的假 gateway；chat 一律失敗（迫使文字走 fallback）。"""

    available = True
    image_model = "google/nano-banana"
    image_fallback_model = "google/nano-banana-2"

    def __init__(self, fail_primary: int = 0, fail_fallback: int = 0) -> None:
        self.fail_primary = fail_primary
        self.fail_fallback = fail_fallback
        self.image_calls: list[str] = []

    def chat(self, messages, *, model=None, temperature=0.3, force_json=False) -> str:
        raise LLMError("測試環境不提供文字模型")

    def generate_image(self, prompt, *, images=(), model=None) -> ImageResult:
        used = model or self.image_model
        self.image_calls.append(used)
        if used == self.image_model and self.fail_primary > 0:
            self.fail_primary -= 1
            raise LLMError("配額不足（測試模擬）", model=used)
        if used == self.image_fallback_model and self.fail_fallback > 0:
            self.fail_fallback -= 1
            raise LLMError("備援模型也失敗（測試模擬）", model=used)
        return ImageResult(image_b64=make_png_b64(), model=used)


class FakeChatGateway:
    """依序回覆腳本化 JSON 的文字假件（生圖不支援）。"""

    available = True
    image_model = "google/nano-banana"
    image_fallback_model = "google/nano-banana-2"

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)

    def chat(self, messages, *, model=None, temperature=0.3, force_json=False) -> str:
        if not self._responses:
            raise LLMError("腳本已用完")
        return self._responses.pop(0)

    def generate_image(self, prompt, *, images=(), model=None) -> ImageResult:
        return ImageResult(image_b64=make_png_b64(), model=model or self.image_model)


class FakeRetriever:
    """依查詢文字裡的房間名路由候選清單。"""

    LIVING = [
        dict(catalog_id="sofa-l", name="三人布沙發", category="sofa", width_cm=180,
             depth_cm=90, height_cm=85, price=18900, score=0.95, style="japanese"),
        dict(catalog_id="sofa-s", name="雙人小沙發", category="sofa", width_cm=150,
             depth_cm=80, height_cm=82, price=12900, score=0.90, style="japanese"),
        dict(catalog_id="tv-1", name="電視櫃", category="media", width_cm=160,
             depth_cm=40, height_cm=50, price=6900, score=0.88),
        dict(catalog_id="ct-1", name="橡木茶几", category="coffee_table", width_cm=90,
             depth_cm=50, height_cm=45, price=3900, score=0.85),
        dict(catalog_id="rug-1", name="短毛地毯", category="rug", width_cm=200,
             depth_cm=140, height_cm=1, price=2900, score=0.80),
        dict(catalog_id="lp-1", name="立燈", category="lighting", width_cm=35,
             depth_cm=35, height_cm=150, price=1990, score=0.75),
    ]
    BEDROOM = [
        dict(catalog_id="bed-q", name="雙人床架", category="bed", width_cm=155,
             depth_cm=195, height_cm=95, price=15900, score=0.96, style="japanese"),
        dict(catalog_id="bed-s", name="單人床架", category="bed", width_cm=105,
             depth_cm=190, height_cm=95, price=9900, score=0.85),
        dict(catalog_id="wd-1", name="雙門衣櫃", category="wardrobe", width_cm=120,
             depth_cm=60, height_cm=200, price=11900, score=0.92,
             clearance={"side": "front", "depth_cm": 60}),
        dict(catalog_id="st-1", name="床頭櫃", category="side_table", width_cm=45,
             depth_cm=40, height_cm=50, price=2490, score=0.83),
        dict(catalog_id="rug-2", name="臥室地毯", category="rug", width_cm=160,
             depth_cm=120, height_cm=1, price=2400, score=0.78),
    ]
    TINY = [
        dict(catalog_id="bed-q", name="雙人床架", category="bed", width_cm=155,
             depth_cm=195, height_cm=95, price=15900, score=0.96),
    ]

    def search(self, query: str, *, top_k: int = 8) -> list[dict]:
        if "客廳" in query:
            return self.LIVING[:top_k]
        if "主臥" in query:
            return self.BEDROOM[:top_k]
        if "儲物間" in query:
            return self.TINY[:top_k]
        return []


@pytest.fixture
def layout_json() -> dict:
    return {
        "rooms": [
            {"room_id": "living", "name": "客廳", "width_cm": 420, "depth_cm": 360},
            {"room_id": "bedroom", "name": "主臥", "width_cm": 360, "depth_cm": 300},
        ]
    }


@pytest.fixture
def questionnaire() -> dict:
    return {
        "styles": ["日式無印"],
        "budget_total": 120000,
        "materials": {"牆面": "暖白乳膠漆", "地板": "淺橡木超耐磨", "天花板": "平頂白"},
        "palette_options": [
            {"palette_id": "p1", "name": "暖木米白", "colors": ["#EDE3D4", "#B9A38F"]},
            {"palette_id": "p2", "name": "灰藍木質", "colors": ["#9FB4C7", "#6C7A89"]},
        ],
        "rooms": [
            {
                "room_id": "living",
                "furniture_needs": ["三人沙發", "電視櫃", "茶几"],
                "appliances": ["壁掛冷氣"],
                "notes": "希望留出瑜伽空間",
            },
            {
                "room_id": "bedroom",
                "furniture_needs": ["雙人床", "衣櫃"],
                "appliances": ["除濕機"],
                "notes": "床不要正對門",
            },
        ],
        "extra_notes": "整體色調溫暖，預算內優先床墊品質",
    }


def build_test_master(
    tmp_path,
    *,
    image_gateway=None,
    retriever=None,
) -> MasterAgent:
    gateway = image_gateway if image_gateway is not None else FakeImageGateway()
    retriever = retriever if retriever is not None else FakeRetriever()
    return MasterAgent(
        FurnitureAgent(None, retriever=retriever),
        ValidationAgent(None),
        GenPicAgent(gateway),
        ReportAgent(None),
        config=MasterConfig(output_dir=str(tmp_path / "out")),
    )


@pytest.fixture
def master(tmp_path) -> MasterAgent:
    return build_test_master(tmp_path)
