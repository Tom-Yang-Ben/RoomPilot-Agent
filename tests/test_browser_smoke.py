from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest


pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[1]


def _unused_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_until_ready(url: str, timeout_seconds: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, URLError):
            time.sleep(0.1)
    raise AssertionError(f"RoomPilot server did not become ready: {url}")


def test_loopback_pages_load_without_external_runtime_dependencies(tmp_path: Path) -> None:
    if os.getenv("ROOMPILOT_BROWSER_TEST") != "1":
        pytest.skip("set ROOMPILOT_BROWSER_TEST=1 after installing Playwright Chromium")

    from playwright.sync_api import sync_playwright

    port = _unused_loopback_port()
    origin = f"http://127.0.0.1:{port}"
    environment = {
        **os.environ,
        "ROOMPILOT_PROFILE": "portable",
        "ROOMPILOT_CATALOG_PROVIDER": "fixture",
        "ROOMPILOT_RUNTIME_DIR": str(tmp_path / "runtime"),
        "ROOMPILOT_OCR_DISABLED": "1",
        "ROOMPILOT_RAG_ENABLED": "false",
        "OPENROUTER_INTAKE_ENABLED": "0",
        "OPENROUTER_SCENE_PLANNING_ENABLED": "0",
    }
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.server.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_until_ready(f"{origin}/api/catalog/status")
        page_errors: list[str] = []
        bad_resources: list[str] = []
        external_requests: list[str] = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.on(
                "request",
                lambda request: external_requests.append(request.url)
                if not request.url.startswith(origin)
                and not request.url.startswith(("data:", "blob:"))
                else None,
            )
            page.on(
                "response",
                lambda response: bad_resources.append(
                    f"{response.status} {response.url}"
                )
                if response.status >= 400
                and (
                    response.url.startswith(f"{origin}/static/")
                    or response.url in {origin, f"{origin}/library", f"{origin}/scene"}
                )
                else None,
            )

            for path in ("/", "/library", "/scene"):
                response = page.goto(f"{origin}{path}", wait_until="networkidle")
                assert response is not None and response.ok
                assert "RoomPilot" in page.title()

            status = page.request.get(f"{origin}/api/catalog/status")
            assert status.ok
            payload = status.json()
            assert payload["profile"] == "portable"
            assert payload["furniture"]["provider"] == "portable_fixture"
            browser.close()

        assert page_errors == []
        assert bad_resources == []
        assert external_requests == []
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
