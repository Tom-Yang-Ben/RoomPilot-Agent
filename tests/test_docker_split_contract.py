"""docker-compose 功能拆解的契約測試。

拆容器只動了兩處程式碼，兩處都由環境變數開關：

- ``ROOMPILOT_RAG_REMOTE_URL``    未設 → BGE-M3 照舊在行程內載入
- ``PLAYWRIGHT_WS_ENDPOINT``      未設 → 第 8 步 PDF 照舊開本機 Chromium

「未設就等於原本行為」是整個拆解不影響既有部署的前提，所以兩個方向都要驗。
"""

from __future__ import annotations

import importlib.util
import io
import json
import re
import urllib.request
from pathlib import Path

import pytest

from backend.spatial_data.rag import model_runtime
from backend.spatial_data.rag.errors import RagDependencyError
from backend.spatial_data.rag.settings import load_rag_settings


ROOT = Path(__file__).resolve().parents[1]
BUILD_PDF = ROOT / "backend/agent/skills/roompilot-delivery-pdf/scripts/build_pdf.py"


# ----------------------------------------------------------------- RAG sidecar

class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def captured_requests(monkeypatch):
    """攔截 urllib，記錄 sidecar 被打了什麼。"""
    calls: list[dict] = []

    def fake_urlopen(request, timeout=None):
        calls.append(
            {
                "url": request.full_url,
                "body": json.loads(request.data.decode()) if request.data else None,
            }
        )
        return _FakeResponse(json.dumps({"vectors": [[0.5]], "scores": [1.5]}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return calls


def test_rag_stays_in_process_when_remote_url_unset(monkeypatch, captured_requests):
    monkeypatch.delenv(model_runtime.REMOTE_URL_ENV, raising=False)

    assert model_runtime._remote_url() == ""
    status = model_runtime.MODEL_RUNTIME.status(load_rag_settings(ROOT))

    # 本機路徑會回報套件與權重快取狀態，而且完全不碰網路。
    assert "torch" in status["packages"]
    assert "remote_url" not in status
    assert captured_requests == []


def test_rag_embed_goes_to_sidecar_when_remote_url_set(monkeypatch, captured_requests):
    monkeypatch.setenv(model_runtime.REMOTE_URL_ENV, "http://rag:8009/")

    vectors = model_runtime.MODEL_RUNTIME.embed(["沙發"], settings=None)

    assert vectors == [[0.5]]
    # 尾端斜線要被吃掉，不能打成 http://rag:8009//embed
    assert captured_requests[0]["url"] == "http://rag:8009/embed"
    assert captured_requests[0]["body"] == {"texts": ["沙發"]}


def test_rag_rerank_reuses_the_pairs_endpoint(monkeypatch, captured_requests):
    monkeypatch.setenv(model_runtime.REMOTE_URL_ENV, "http://rag:8009")

    scores = model_runtime.MODEL_RUNTIME.rerank("客廳", ["沙發", "餐椅"], settings=None)

    assert scores == [1.5]
    assert captured_requests[0]["url"] == "http://rag:8009/rerank"
    assert captured_requests[0]["body"] == {"pairs": [["客廳", "沙發"], ["客廳", "餐椅"]]}


def test_rag_empty_input_never_reaches_the_network(monkeypatch, captured_requests):
    monkeypatch.setenv(model_runtime.REMOTE_URL_ENV, "http://rag:8009")

    assert model_runtime.MODEL_RUNTIME.rerank("客廳", [], settings=None) == []
    assert model_runtime.MODEL_RUNTIME.rerank_pairs([], settings=None) == []
    # embed 原本沒有這道防護，空清單會照樣送出去（本機模式則是為了零個向量
    # 去載 4.6GB 模型）。2026-08-22 實跑 rag sidecar 時打到 503 才發現。
    assert model_runtime.MODEL_RUNTIME.embed([], settings=None) == []
    assert captured_requests == []


def test_rag_status_degrades_instead_of_raising_when_sidecar_is_down(monkeypatch):
    monkeypatch.setenv(model_runtime.REMOTE_URL_ENV, "http://rag:8009")

    def boom(request, timeout=None):
        raise OSError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", boom)

    # 狀態頁不該因為 sidecar 沒起來就整頁爆掉。
    status = model_runtime.MODEL_RUNTIME.status(settings=None)
    assert status["loaded"] is False
    assert status["remote_url"] == "http://rag:8009"
    assert "unavailable" in status["error"]

    # 但真的要算向量時，必須明確失敗，不能安靜回空值。
    with pytest.raises(RagDependencyError):
        model_runtime.MODEL_RUNTIME.embed(["沙發"], settings=None)


# -------------------------------------------------------------- 遠端 Chromium

class _FakePage:
    def __init__(self, record):
        self._record = record

    def goto(self, url, **_):
        self._record["goto"] = url

    def pdf(self, **kwargs):
        Path(kwargs["path"]).write_bytes(b"%PDF-1.4\n")


class _FakeBrowser:
    def __init__(self, record):
        self._record = record

    def new_page(self):
        return _FakePage(self._record)

    def close(self):
        self._record["closed"] = True


class _FakeChromium:
    def __init__(self, record):
        self._record = record

    def connect(self, endpoint):
        self._record["mode"] = ("connect", endpoint)
        return _FakeBrowser(self._record)

    def launch(self):
        self._record["mode"] = ("launch", None)
        return _FakeBrowser(self._record)


class _FakePlaywright:
    def __init__(self, record):
        self.chromium = _FakeChromium(record)


class _FakeSyncPlaywright:
    def __init__(self, record):
        self._record = record

    def __enter__(self):
        return _FakePlaywright(self._record)

    def __exit__(self, *exc):
        return False


def _load_build_pdf():
    spec = importlib.util.spec_from_file_location("roompilot_build_pdf", BUILD_PDF)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        (None, ("launch", None)),
        ("", ("launch", None)),  # 空字串等同沒設，不能被當成 ws 位址
        ("ws://chromium:3000/", ("connect", "ws://chromium:3000/")),
    ],
)
def test_build_pdf_picks_browser_by_ws_endpoint(monkeypatch, tmp_path, endpoint, expected):
    pytest.importorskip("playwright")
    record: dict = {}
    monkeypatch.setattr(
        "playwright.sync_api.sync_playwright", lambda: _FakeSyncPlaywright(record)
    )
    if endpoint is None:
        monkeypatch.delenv("PLAYWRIGHT_WS_ENDPOINT", raising=False)
    else:
        monkeypatch.setenv("PLAYWRIGHT_WS_ENDPOINT", endpoint)

    html = tmp_path / "report.html"
    html.write_text("<html><body>提案</body></html>", encoding="utf-8")
    pdf = tmp_path / "report.pdf"

    _load_build_pdf().html_to_pdf(html, pdf, "RoomPilot")

    assert record["mode"] == expected
    assert record["closed"] is True
    # 遠端瀏覽器解析的是自己那一側的 file://，所以路徑必須原樣送出。
    assert record["goto"] == html.resolve().as_uri()
    assert pdf.read_bytes().startswith(b"%PDF")


# --------------------------------------------------------- compose ↔ Dockerfile

def test_every_compose_build_target_exists_in_the_dockerfile():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "docker/Dockerfile").read_text(encoding="utf-8")

    wanted = set(re.findall(r"^\s+target:\s*(\S+)\s*$", compose, re.MULTILINE))
    defined = set(re.findall(r"^FROM\s+\S+\s+AS\s+(\S+)\s*$", dockerfile, re.MULTILINE))

    assert wanted, "compose 應該至少 build 一個 target"
    assert wanted <= defined, f"compose 指到不存在的 target: {wanted - defined}"


def test_vite_proxy_does_not_swallow_its_own_base_path():
    """Vite 的 base 是 /static/frontend3d/，proxy 不能把整段 /static 轉給 FastAPI。

    2026-08-22 實跑才發現：原本的 ``'/static': target`` 會連 dev server 自己的
    位址（含 /@vite/client 與 HMR 用戶端）一起轉走，`5173` 上拿到的永遠是
    FastAPI 那份**已建置**的舊產物，HMR 完全不可能觸發。這個測試釘住修法。
    """
    config = (ROOT / "frontend/vite.config.js").read_text(encoding="utf-8")

    base = re.search(r"^\s*base:\s*['\"](\S+?)['\"]", config, re.MULTILINE)
    assert base, "vite.config.js 應該有 base"
    base_path = base.group(1)                      # /static/frontend3d/

    keys = re.findall(r"^\s*'([^']+)':\s*target,\s*$", config, re.MULTILINE)
    assert keys, "應該至少有一條 proxy 規則"

    for key in keys:
        if key.startswith("^"):
            assert not re.compile(key).search(base_path), (
                f"proxy regex {key!r} 仍會吃掉 dev server 自己的 base {base_path!r}"
            )
        else:
            assert not base_path.startswith(key), (
                f"proxy 字串前綴 {key!r} 會把 base {base_path!r} 整段轉給 FastAPI，"
                "dev server 將永遠拿不到自己的頁面"
            )

    # 其餘 /static/** 仍必須轉出去，否則材質與 GLB 在 dev server 上會 404。
    static_rule = next((k for k in keys if "static" in k), None)
    assert static_rule and static_rule.startswith("^"), "應以 RegExp 排除 base"
    assert re.compile(static_rule).search("/static/scene.html")


def test_playwright_client_and_browser_images_are_the_same_version():
    """版本對不上時 chromium.connect() 會被協定版本擋下，且錯誤訊息很難懂。"""
    pinned = re.search(
        r"^playwright==(\S+)$",
        (ROOT / "requirements-delivery.txt").read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    dockerfile = (ROOT / "docker/Dockerfile").read_text(encoding="utf-8")

    assert pinned, "requirements-delivery.txt 應該釘住 playwright 版本"
    assert f"mcr.microsoft.com/playwright:v{pinned.group(1)}-" in dockerfile
    assert f"playwright@{pinned.group(1)}" in dockerfile
