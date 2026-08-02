"""帳號生命週期：改密碼、管理員重設、過期 refresh token 清理接線。

本產品無寄信基礎設施，「忘記密碼」由 admin 重設臨時密碼替代；兩種改法
都撤銷目標帳號全部 refresh token——改密碼視同懷疑舊憑證外洩。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.server import main
from backend.server.main import app

client = TestClient(app)


def _register(password: str = "old-password-1") -> dict:
    response = client.post(
        "/api/auth/register",
        json={
            "email": f"lifecycle-{uuid4().hex[:10]}@local.test",
            "password": password,
            "display_name": "生命週期測試",
            "role": "designer",
        },
    )
    assert response.status_code == 201
    return response.json()


def _bearer(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_change_password_rejects_wrong_current_password() -> None:
    tokens = _register()
    response = client.post(
        "/api/auth/password",
        json={"current_password": "not-the-password", "new_password": "new-password-1"},
        headers=_bearer(tokens),
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "CURRENT_PASSWORD_INCORRECT"


def test_change_password_rotates_credentials_and_revokes_old_sessions() -> None:
    tokens = _register("old-password-1")
    email = tokens["user"]["email"]
    response = client.post(
        "/api/auth/password",
        json={"current_password": "old-password-1", "new_password": "new-password-2"},
        headers=_bearer(tokens),
    )
    assert response.status_code == 200
    fresh = response.json()

    # 舊 refresh token（其他裝置的 session）必須全部作廢。
    revoked = client.post(
        "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert revoked.status_code == 401
    # 回傳的新憑證可用。
    renewed = client.post(
        "/api/auth/refresh", json={"refresh_token": fresh["refresh_token"]}
    )
    assert renewed.status_code == 200
    # 新密碼可登入、舊密碼不行。
    assert client.post(
        "/api/auth/login", json={"email": email, "password": "new-password-2"}
    ).status_code == 200
    assert client.post(
        "/api/auth/login", json={"email": email, "password": "old-password-1"}
    ).status_code == 401


def test_admin_reset_password_is_admin_only() -> None:
    designer = _register()
    target = _register("victim-password-1")
    response = client.post(
        "/api/auth/admin/reset-password",
        json={"email": target["user"]["email"], "new_password": "hijacked-pass-1"},
        headers=_bearer(designer),
    )
    assert response.status_code == 403


def test_admin_reset_password_sets_temporary_password_and_revokes_sessions() -> None:
    target = _register("forgotten-pass-1")
    email = target["user"]["email"]
    # 不帶 headers → conftest 預設 admin 身分。
    response = client.post(
        "/api/auth/admin/reset-password",
        json={"email": email, "new_password": "temp-password-9"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == email

    assert client.post(
        "/api/auth/refresh", json={"refresh_token": target["refresh_token"]}
    ).status_code == 401
    assert client.post(
        "/api/auth/login", json={"email": email, "password": "temp-password-9"}
    ).status_code == 200
    assert client.post(
        "/api/auth/login", json={"email": email, "password": "forgotten-pass-1"}
    ).status_code == 401


def test_admin_reset_password_for_unknown_email_is_404() -> None:
    response = client.post(
        "/api/auth/admin/reset-password",
        json={"email": "nobody@local.test", "new_password": "whatever-123"},
    )
    assert response.status_code == 404


def test_login_purges_expired_refresh_tokens() -> None:
    """purge_expired_refresh_tokens 曾經零呼叫端，表會無上限成長；
    現在掛在登入成功後。登入過一次，再手動 purge 應該撈不到東西。"""
    tokens = _register("purge-check-11")
    store = main.user_store()
    store.register_refresh_token(
        jti=f"expired-{uuid4().hex[:8]}",
        user_id=tokens["user"]["user_id"],
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    login = client.post(
        "/api/auth/login",
        json={"email": tokens["user"]["email"], "password": "purge-check-11"},
    )
    assert login.status_code == 200
    assert store.purge_expired_refresh_tokens() == 0, "登入時就該把過期的清掉"


def test_admin_can_deactivate_and_reactivate_an_account() -> None:
    target = _register("disable-me-123")
    email = target["user"]["email"]
    # 停用（conftest 預設 admin 身分）。
    response = client.post(
        "/api/auth/admin/set-active", json={"email": email, "is_active": False}
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    # 停用立即生效：登入 403、既有 access token 401、refresh 401。
    login = client.post(
        "/api/auth/login", json={"email": email, "password": "disable-me-123"}
    )
    assert login.status_code == 403
    assert login.json()["detail"]["error_code"] == "ACCOUNT_DISABLED"
    assert client.get("/api/auth/me", headers=_bearer(target)).status_code == 401
    assert client.post(
        "/api/auth/refresh", json={"refresh_token": target["refresh_token"]}
    ).status_code == 401

    # 恢復後可重新登入。
    restore = client.post(
        "/api/auth/admin/set-active", json={"email": email, "is_active": True}
    )
    assert restore.status_code == 200
    assert client.post(
        "/api/auth/login", json={"email": email, "password": "disable-me-123"}
    ).status_code == 200


def test_admin_cannot_deactivate_their_own_account() -> None:
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    response = client.post(
        "/api/auth/admin/set-active",
        json={"email": me.json()["email"], "is_active": False},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] == "SELF_DEACTIVATION_BLOCKED"


def test_set_active_is_admin_only() -> None:
    designer = _register()
    target = _register()
    response = client.post(
        "/api/auth/admin/set-active",
        json={"email": target["user"]["email"], "is_active": False},
        headers=_bearer(designer),
    )
    assert response.status_code == 403
