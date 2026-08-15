"""外接模型設定：模型 id 一律從 `.env` 讀，且每顆綁定的功能不會互相串線。

只測「設定 → 生效值」這條線，不打網路。`.env` 檔的值由 `load_dotenv(override=False)`
載入，行程環境優先，所以 `monkeypatch.setenv` 一定蓋得過開發機的 `.env`。
"""
from __future__ import annotations

import os

import pytest

from backend.agent.llm import OpenRouterGateway, default_text_model, report_model
from backend.floorplan.vlm_judge import get_vision_models
from backend.model_config import REGISTRY, model_default, model_id, model_list
from backend.server.ai_render_service import _palette_gateway
from backend.server.intake_service import _models as intake_models
from backend.server.scene_service import get_openrouter_models


def test_every_feature_resolves_to_a_model_id() -> None:
    """離線（`.env` 沒設）也要有可用預設，否則呼叫端會送出空 model 給供應商。"""
    for key in REGISTRY:
        if key == "palette_fallback":  # 刻意留空＝退回 genpic 主模型
            continue
        assert model_default(key), key
        assert model_id(key), key


@pytest.mark.parametrize(
    ("env_name", "resolve"),
    [
        ("ROOMPILOT_INTAKE_MODEL", lambda: intake_models()[0]),
        ("ROOMPILOT_SCENE_MODEL", lambda: get_openrouter_models()[0]),
        ("ROOMPILOT_AGENT_TEXT_MODEL", default_text_model),
        ("ROOMPILOT_REPORT_MODEL", report_model),
        ("ROOMPILOT_GENPIC_MODEL", lambda: OpenRouterGateway().image_model),
        ("ROOMPILOT_GENPIC_FALLBACK_MODEL", lambda: OpenRouterGateway().image_fallback_model),
        ("ROOMPILOT_GENPIC_PALETTE_MODEL", lambda: _palette_gateway().image_model),
        (
            "ROOMPILOT_GENPIC_PALETTE_FALLBACK_MODEL",
            lambda: _palette_gateway().image_fallback_model,
        ),
        ("OPENROUTER_VISION_MODELS", lambda: get_vision_models()[0]),
    ],
)
def test_each_feature_reads_its_own_env_var(monkeypatch, env_name, resolve) -> None:
    """一個功能一個變數：改 A 功能的模型不得改到 B 功能。"""
    monkeypatch.setenv(env_name, "vendor/pinned-model")
    assert resolve() == "vendor/pinned-model"


def test_palette_fallback_defaults_to_the_step8_render_model(monkeypatch) -> None:
    """色卡（第 7 步）用較貴的 pro；它掛掉要退回第 8 步那顆，而不是退回內建常數。"""
    monkeypatch.setenv("ROOMPILOT_GENPIC_PALETTE_FALLBACK_MODEL", "")  # 空＝未設定
    monkeypatch.setenv("ROOMPILOT_GENPIC_MODEL", "vendor/step8-model")
    assert _palette_gateway().image_fallback_model == "vendor/step8-model"


def test_shared_openrouter_models_still_works_as_the_generic_fallback(monkeypatch) -> None:
    """既有 `.env` 只設 OPENROUTER_MODELS 的部署不能被這次改動打斷。"""
    monkeypatch.setenv("ROOMPILOT_INTAKE_MODEL", "")
    monkeypatch.setenv("OPENROUTER_MODELS", "vendor/a,vendor/b")
    assert intake_models() == ["vendor/a", "vendor/b"]
    assert model_list("intake") == ["vendor/a", "vendor/b"]
    assert model_id("intake") == "vendor/a"


def test_reading_models_never_leaks_env_file_secrets_into_the_process(monkeypatch) -> None:
    """讀模型設定不得把 `.env` 整份灌進 os.environ。

    灌進去的話，「刪掉金鑰應該回 503」會被本機 `.env` 悄悄救活，離線模式與
    未設定金鑰的誠實失敗全部失效（`tests/test_ai_render_openrouter.py` 那條 503）。
    """
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    model_id("genpic")
    model_list("floorplan_vision")
    assert os.getenv("OPENROUTER_API_KEY") is None
