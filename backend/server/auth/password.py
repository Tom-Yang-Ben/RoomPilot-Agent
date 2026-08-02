"""密碼雜湊：標準庫 pbkdf2_hmac，不引入 bcrypt/passlib 的編譯相依。

儲存格式為單一字串，欄位以 ``$`` 分隔：

    pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>

迭代次數寫在雜湊字串裡，日後調高參數時舊密碼仍可驗證，使用者下次登入
成功即自動升級（見 :func:`needs_rehash`）。
"""

from __future__ import annotations

import base64
import hmac
import secrets
from hashlib import pbkdf2_hmac


ALGORITHM = "pbkdf2_sha256"
# OWASP Password Storage Cheat Sheet 對 PBKDF2-HMAC-SHA256 的建議下限。
DEFAULT_ITERATIONS = 600_000
SALT_BYTES = 16
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 1024


class InvalidPasswordHash(ValueError):
    """儲存的雜湊字串不符合格式，視為無法驗證而非驗證失敗。"""


def _b64encode(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64decode(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def validate_password_strength(password: str) -> None:
    """在雜湊前擋掉明顯不可接受的密碼，錯誤訊息給前端直接顯示。"""
    if not isinstance(password, str) or not password:
        raise ValueError("密碼不可為空")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"密碼至少需要 {MIN_PASSWORD_LENGTH} 個字元")
    if len(password) > MAX_PASSWORD_LENGTH:
        # 過長輸入會讓 pbkdf2 成為可放大的 CPU 成本，直接擋在入口。
        raise ValueError(f"密碼不可超過 {MAX_PASSWORD_LENGTH} 個字元")


def hash_password(password: str, *, iterations: int = DEFAULT_ITERATIONS) -> str:
    validate_password_strength(password)
    salt = secrets.token_bytes(SALT_BYTES)
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{ALGORITHM}${iterations}${_b64encode(salt)}${_b64encode(digest)}"


def _parse(stored: str) -> tuple[int, bytes, bytes]:
    try:
        algorithm, raw_iterations, salt_text, digest_text = stored.split("$")
    except (AttributeError, ValueError) as exc:
        raise InvalidPasswordHash("password hash format invalid") from exc
    if algorithm != ALGORITHM:
        raise InvalidPasswordHash(f"unsupported algorithm: {algorithm}")
    try:
        iterations = int(raw_iterations)
        salt = _b64decode(salt_text)
        digest = _b64decode(digest_text)
    except (ValueError, TypeError) as exc:
        raise InvalidPasswordHash("password hash fields invalid") from exc
    if iterations < 1 or not salt or not digest:
        raise InvalidPasswordHash("password hash fields invalid")
    return iterations, salt, digest


def verify_password(password: str, stored: str) -> bool:
    """常數時間比對；格式壞掉時回 False，呼叫端不需區分兩種失敗。"""
    if not isinstance(password, str) or not password:
        return False
    try:
        iterations, salt, expected = _parse(stored)
    except InvalidPasswordHash:
        return False
    candidate = pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)


def needs_rehash(stored: str, *, iterations: int = DEFAULT_ITERATIONS) -> bool:
    """雜湊參數落後於目前設定時回 True，讓登入流程順手升級。"""
    try:
        stored_iterations, _salt, _digest = _parse(stored)
    except InvalidPasswordHash:
        return True
    return stored_iterations < iterations
