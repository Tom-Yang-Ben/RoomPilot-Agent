"""密碼雜湊與 token 簽發／驗證的單元契約。"""

from __future__ import annotations

import secrets
from datetime import timedelta

import pytest

from backend.server.auth.models import RegisterRequest
from backend.server.auth.password import (
    DEFAULT_ITERATIONS,
    hash_password,
    needs_rehash,
    verify_password,
)
from backend.server.auth.throttle import LoginThrottle
from backend.server.auth.tokens import TokenError, TokenService


SECRET = secrets.token_urlsafe(48)


def test_password_hash_is_salted_and_verifiable() -> None:
    first = hash_password("correct-horse-battery")
    second = hash_password("correct-horse-battery")

    assert first != second, "相同密碼必須因為隨機 salt 產生不同雜湊"
    assert first.startswith(f"pbkdf2_sha256${DEFAULT_ITERATIONS}$")
    assert verify_password("correct-horse-battery", first)
    assert verify_password("correct-horse-battery", second)
    assert not verify_password("wrong-password", first)


def test_password_hash_never_contains_the_plaintext() -> None:
    stored = hash_password("my-secret-passphrase")

    assert "my-secret-passphrase" not in stored


def test_corrupt_hash_fails_closed_instead_of_raising() -> None:
    assert not verify_password("anything", "not-a-valid-hash")
    assert not verify_password("anything", "")
    # 壞掉的雜湊必須被視為需要重設，而不是默默當成有效。
    assert needs_rehash("not-a-valid-hash")


def test_rehash_is_requested_when_iterations_fall_behind() -> None:
    legacy = hash_password("still-works", iterations=1000)

    assert verify_password("still-works", legacy)
    assert needs_rehash(legacy)
    assert not needs_rehash(hash_password("fresh-enough-password"))


@pytest.mark.parametrize("password", ["", "short", "a" * 1025])
def test_unacceptable_passwords_are_rejected_before_hashing(password: str) -> None:
    with pytest.raises(ValueError):
        hash_password(password)


def test_short_signing_secret_is_refused() -> None:
    # PyJWT 只對短金鑰發 warning；短金鑰可離線暴力破解，必須是硬性錯誤。
    with pytest.raises(RuntimeError):
        TokenService(secret="too-short")


def test_access_and_refresh_tokens_are_not_interchangeable() -> None:
    service = TokenService(secret=SECRET)
    access, _expires = service.issue_access_token(
        user_id="u1", email="a@example.com", role="designer"
    )
    refresh, jti, _refresh_expires = service.issue_refresh_token(user_id="u1")

    assert service.decode(access, expected_type="access").role == "designer"
    assert service.decode(refresh, expected_type="refresh").jti == jti
    with pytest.raises(TokenError):
        service.decode(refresh, expected_type="access")
    with pytest.raises(TokenError):
        service.decode(access, expected_type="refresh")


def test_tampered_token_is_rejected() -> None:
    service = TokenService(secret=SECRET)
    token, _expires = service.issue_access_token(
        user_id="u1", email="a@example.com", role="client"
    )

    with pytest.raises(TokenError):
        service.decode(f"{token}x", expected_type="access")
    # 換一把金鑰也必須驗不過，否則等於沒有簽章保護。
    with pytest.raises(TokenError):
        TokenService(secret=secrets.token_urlsafe(48)).decode(
            token, expected_type="access"
        )


def test_expired_token_is_rejected() -> None:
    service = TokenService(secret=SECRET)
    service.access_ttl = timedelta(seconds=-60)
    token, _expires = service.issue_access_token(
        user_id="u1", email="a@example.com", role="designer"
    )

    with pytest.raises(TokenError) as error:
        service.decode(token, expected_type="access")
    assert error.value.reason == "TOKEN_EXPIRED"


def test_email_is_normalized_and_validated() -> None:
    request = RegisterRequest(
        email="  Ben@Example.COM ", password="abcd1234", display_name=" Ben "
    )

    assert request.email == "ben@example.com"
    assert request.display_name == "Ben"
    for invalid in ["not-an-email", "a@b", "a b@example.com", "@example.com"]:
        with pytest.raises(ValueError):
            RegisterRequest(
                email=invalid, password="abcd1234", display_name="x"
            )


def test_login_throttle_locks_after_repeated_failures() -> None:
    throttle = LoginThrottle(max_attempts=3, window_seconds=300)

    assert throttle.retry_after_seconds("ip|a@example.com") is None
    for _ in range(3):
        throttle.record_failure("ip|a@example.com")

    assert throttle.retry_after_seconds("ip|a@example.com") is not None
    # 節流以 key 為單位，不能波及其他帳號。
    assert throttle.retry_after_seconds("ip|b@example.com") is None
    throttle.reset("ip|a@example.com")
    assert throttle.retry_after_seconds("ip|a@example.com") is None
