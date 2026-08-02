"""Keep the default test suite deterministic and independent of local PostgreSQL."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


if os.getenv("ROOMPILOT_TEST_POSTGRES_MAIN") != "1":
    os.environ["ROOMPILOT_PROJECT_STORE_PROVIDER"] = "sqlite"

if os.getenv("ROOMPILOT_TEST_POSTGRES_CATALOGS") != "1":
    os.environ["ROOMPILOT_CATALOG_PROVIDER"] = "json"

if os.getenv("ROOMPILOT_TEST_POSTGRES_RUNTIME_CATALOGS") != "1":
    os.environ["ROOMPILOT_RUNTIME_CATALOG_PROVIDER"] = "json"

# 選件 agent 在正式環境隨 OPENROUTER_API_KEY 啟用。測試必須離線且確定，
# 所以預設關掉；要實打 OpenRouter 時設 ROOMPILOT_TEST_OPENROUTER_SELECTION=1。
if os.getenv("ROOMPILOT_TEST_OPENROUTER_SELECTION") != "1":
    os.environ["OPENROUTER_SELECTION_ENABLED"] = "0"

# bge-m3 權重載入約 34 秒且常駐數 GB。import backend.server.main 就會觸發
# 背景預載，測試不需要語意排序，一律關掉；要實測檢索品質時設為 1。
if os.getenv("ROOMPILOT_TEST_RAG_PRELOAD") != "1":
    os.environ["ROOMPILOT_RAG_PRELOAD"] = "0"


@pytest.fixture(scope="session", autouse=True)
def isolated_project_store_for_api_tests():
    """Prevent API tests from writing either the developer's SQLite or PostgreSQL."""
    from backend.server import main
    from backend.server.auth import dependencies as auth_dependencies
    from backend.server.auth.service import AuthService
    from backend.server.auth.tokens import TokenService
    from backend.server.project_store import ProjectStore

    original_store = main.PROJECT_STORE
    original_auth_service = main.AUTH_SERVICE
    with TemporaryDirectory(prefix="roompilot-pytest-projects-") as directory:
        test_store = ProjectStore(Path(directory) / "runtime")
        main.PROJECT_STORE = test_store
        # 使用者儲存由 main.user_store() 依當下的 PROJECT_STORE 解析，換掉專案
        # store 就會跟著走，這裡只需要固定簽章金鑰與較長 TTL，讓測試不受
        # 隨機金鑰與時鐘影響。
        test_auth = AuthService(
            main.user_store,
            TokenService(
                secret="roompilot-pytest-secret-key-at-least-32-bytes",
                access_ttl_minutes=600,
            ),
        )
        main.AUTH_SERVICE = test_auth
        auth_dependencies.configure(
            auth_service=test_auth, user_store=main.user_store
        )
        try:
            yield
        finally:
            main.PROJECT_STORE = original_store
            main.AUTH_SERVICE = original_auth_service
            auth_dependencies.configure(
                auth_service=original_auth_service, user_store=main.user_store
            )
            test_store.close()


@pytest.fixture(scope="session", autouse=True)
def authenticated_test_client(isolated_project_store_for_api_tests):
    """讓既有 API 測試預設以已登入身分呼叫。

    帳戶端上線後每個 /api/projects 端點都需要 bearer token。與其在數十個既有
    測試裡逐一補 header，這裡替 TestClient 補上預設身分——走的仍是真實的 JWT
    驗證路徑，不是繞過授權。

    身分刻意用 admin：部分測試直接以 PROJECT_STORE 建立專案，沒有經過會指派
    owner 的 API，只有 admin 看得到那些專案。

    要測未登入或跨帳號隔離時，明確傳入自己的 Authorization header
    （空字串即代表匿名），或使用 anonymous_client fixture。
    """
    from weakref import WeakKeyDictionary

    from starlette.testclient import TestClient

    from backend.server import main
    from backend.server.auth.models import LoginRequest, RegisterRequest
    from backend.server.auth.service import RegistrationFailed

    headers_by_store: "WeakKeyDictionary[object, str]" = WeakKeyDictionary()
    last_header: list[str] = []

    def identity_header() -> str | None:
        """替目前作用中的 store 準備測試身分。

        個別測試會 monkeypatch PROJECT_STORE 到自己的暫存目錄，使用者儲存會
        跟著換到那個資料庫，先前註冊的帳號在那裡並不存在。所以身分要以 store
        為單位建立與快取，而不是整個 session 共用一個。
        """
        try:
            store = main.user_store()
        except Exception:
            # 測試刻意把 store 換成不可用的替身時，仍要送出請求並帶著身分，
            # 才驗得到後端回 503 而不是提前變成 401。簽發不碰資料庫，所以就算
            # 這是本次 session 第一個請求也拿得到 token。
            if last_header:
                return last_header[0]
            token, _expires = main.AUTH_SERVICE.token_service.issue_access_token(
                user_id="pytest-offline-identity",
                email="pytest-owner@example.com",
                role="admin",
            )
            return f"Bearer {token}"
        cached = headers_by_store.get(store)
        if cached is not None:
            return cached
        credentials = {
            "email": "pytest-owner@example.com",
            "password": "pytest-password",
        }
        try:
            tokens = main.AUTH_SERVICE.register(
                RegisterRequest(**credentials, display_name="pytest owner")
            )
        except RegistrationFailed:
            tokens = main.AUTH_SERVICE.authenticate(LoginRequest(**credentials))
        header = f"Bearer {tokens['access_token']}"
        headers_by_store[store] = header
        last_header[:] = [header]
        return header

    original_request = TestClient.request

    def request_with_default_identity(self, method, url, *args, **kwargs):
        if not getattr(self, "_roompilot_anonymous", False):
            headers = dict(kwargs.get("headers") or {})
            if not any(key.lower() == "authorization" for key in headers):
                header = identity_header()
                if header is not None:
                    headers["Authorization"] = header
                    kwargs["headers"] = headers
        return original_request(self, method, url, *args, **kwargs)

    TestClient.request = request_with_default_identity
    try:
        yield identity_header
    finally:
        TestClient.request = original_request


@pytest.fixture
def anonymous_client():
    """未帶任何身分的 client，用來驗證端點確實擋下未登入請求。"""
    from starlette.testclient import TestClient

    from backend.server.main import app

    client = TestClient(app)
    client._roompilot_anonymous = True
    return client
