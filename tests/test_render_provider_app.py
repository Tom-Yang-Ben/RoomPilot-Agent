from __future__ import annotations

import asyncio
import base64
import logging
from pathlib import Path

import httpx
import pytest

from backend import render_provider_app


def test_log_handler_falls_back_to_stderr_when_file_is_unwritable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def reject_file_log(*_args, **_kwargs):
        raise PermissionError("log is locked")

    monkeypatch.setattr(logging, "FileHandler", reject_file_log)

    handler = render_provider_app._build_log_handler(tmp_path / "provider.log")

    assert type(handler) is logging.StreamHandler


def test_decode_reference_image_accepts_png_data_url() -> None:
    raw = b"roompilot"
    encoded = base64.b64encode(raw).decode("ascii")

    assert render_provider_app._decode_reference_image(
        f"data:image/png;base64,{encoded}"
    ) == raw


@pytest.mark.parametrize(
    "value",
    [None, "", "https://example.com/image.png", "data:image/png;base64,not-base64"],
)
def test_decode_reference_image_rejects_invalid_input(value: object) -> None:
    with pytest.raises(ValueError):
        render_provider_app._decode_reference_image(value)


def test_prompt_preserves_room_geometry_and_furniture() -> None:
    prompt = render_provider_app._prompt(
        {
            "mode": "palette_comparison",
            "room_views": [{"room_id": "room-1"}],
            "agent_generation_handoff": {
                "rooms": [{"room_id": "room-1", "name": "臥室"}]
            },
            "requirements": {"room_requirements": [{"room_id": "room-1"}]},
            "render_brief": {"user_notes": "保留窗戶並使用自然木質"},
        },
        {"card_id": "natural", "name": "自然木質"},
    )

    assert "preserve the exact camera" in prompt
    assert "Never add, remove, move" in prompt
    assert "臥室" in prompt
    assert "保留窗戶並使用自然木質" in prompt


def test_gemini_model_rejects_non_gemini_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOMPILOT_GEMINI_IMAGE_MODEL", "openai/gpt-image-1")

    with pytest.raises(ValueError, match="gemini_image_model_required"):
        render_provider_app._gemini_image_model()


@pytest.mark.parametrize(
    ("status_code", "detail"),
    [
        (401, "openrouter_authentication_failed"),
        (402, "openrouter_payment_required"),
        (403, "openrouter_model_access_denied"),
        (429, "openrouter_rate_limited"),
        (500, "openrouter_http_500"),
    ],
)
def test_openrouter_errors_keep_their_actionable_status(
    status_code: int,
    detail: str,
) -> None:
    assert render_provider_app._openrouter_error_detail(status_code) == detail


def test_generate_variant_uses_openrouter_gemini_and_reference_image(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}
    generated = b"generated-image"

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        captured["json"] = __import__("json").loads(request.content)
        return httpx.Response(
            200,
            json={"data": [{"b64_json": base64.b64encode(generated).decode("ascii")}]},
        )

    monkeypatch.setattr(render_provider_app, "GENERATED_DIR", tmp_path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv(
        "ROOMPILOT_GEMINI_IMAGE_MODEL", "google/gemini-3.1-flash-image"
    )
    monkeypatch.setenv("ROOMPILOT_PUBLIC_BASE_URL", "http://127.0.0.1:8047")
    transport = httpx.MockTransport(handler)

    async def run() -> dict[str, object]:
        async with httpx.AsyncClient(
            transport=transport,
            headers=render_provider_app._openrouter_headers("sk-or-test"),
        ) as client:
            return await render_provider_app._generate_variant(
                client,
                {
                    "project_id": "project-1",
                    "mode": "palette_comparison",
                    "room_views": [{"room_id": "room-1"}],
                    "style_packs": [{"card_id": "natural", "name": "自然木質"}],
                },
                b"reference-image",
                "natural",
            )

    result = asyncio.run(run())
    request_json = captured["json"]

    assert captured["url"] == "https://openrouter.ai/api/v1/images"
    assert captured["authorization"] == "Bearer sk-or-test"
    assert request_json["model"] == "google/gemini-3.1-flash-image"
    assert request_json["input_references"][0]["image_url"]["url"].startswith(
        "data:image/png;base64,"
    )
    assert result["preview_url"].startswith(
        "http://127.0.0.1:8047/static/generated/project-1/"
    )
    output_files = list((tmp_path / "project-1").glob("*.png"))
    assert len(output_files) == 1
    assert output_files[0].read_bytes() == generated
