"""Access / refresh token 的簽發與驗證（HS256）。

簽章金鑰依序取自 ``ROOMPILOT_AUTH_SECRET`` 環境變數、專案 ``.env``，最後
才是 runtime 目錄下自動產生的 ``auth_secret.key``。自動產生只為了本機開發
不被卡住，正式部署必須明確設定環境變數，否則每個部署節點的金鑰都不同，
token 會無法跨節點驗證。
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import jwt

from ..project_store import _read_project_env


ALGORITHM = "HS256"
TokenType = Literal["access", "refresh"]

DEFAULT_ACCESS_TTL_MINUTES = 30
DEFAULT_REFRESH_TTL_DAYS = 14
# 允許的時鐘偏移；不放寬到分鐘級，避免過期 token 有明顯的可用尾巴。
LEEWAY_SECONDS = 10
# RFC 7518 §3.2 對 HS256 的金鑰下限。PyJWT 只發 warning，這裡升級成硬性
# 拒絕——短金鑰可離線暴力破解，等同所有帳號的簽章能力外流。
MIN_SECRET_BYTES = 32


class TokenError(Exception):
    """Token 無法被信任；呼叫端一律轉成 401。"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class TokenClaims:
    user_id: str
    token_type: TokenType
    jti: str
    expires_at: datetime
    email: str | None = None
    role: str | None = None


def _env_value(project_dir: Path, name: str) -> str | None:
    raw = os.getenv(name)
    if raw is None:
        raw = _read_project_env(project_dir / ".env").get(name)
    if raw is None:
        return None
    value = raw.strip()
    return value or None


def _env_int(project_dir: Path, name: str, default: int) -> int:
    raw = _env_value(project_dir, name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} 必須是整數") from exc
    if value < 1:
        raise RuntimeError(f"{name} 必須大於 0")
    return value


def resolve_secret(project_dir: Path, runtime_dir: Path) -> str:
    configured = _env_value(project_dir, "ROOMPILOT_AUTH_SECRET")
    if configured:
        return configured
    key_path = runtime_dir / "auth_secret.key"
    if key_path.is_file():
        existing = key_path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    generated = secrets.token_urlsafe(48)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    key_path.write_text(generated, encoding="utf-8")
    try:
        # 檔案內容等同於所有帳號的簽章能力，收斂成只有擁有者可讀。
        key_path.chmod(0o600)
    except OSError:
        # Windows 上 chmod 幾乎無作用，不因此讓服務起不來。
        pass
    return generated


class TokenService:
    def __init__(
        self,
        *,
        secret: str,
        access_ttl_minutes: int = DEFAULT_ACCESS_TTL_MINUTES,
        refresh_ttl_days: int = DEFAULT_REFRESH_TTL_DAYS,
    ) -> None:
        if not secret:
            raise RuntimeError("auth secret 不可為空")
        if len(secret.encode("utf-8")) < MIN_SECRET_BYTES:
            raise RuntimeError(
                f"ROOMPILOT_AUTH_SECRET 至少需要 {MIN_SECRET_BYTES} 位元組；"
                "可用 python -c \"import secrets;print(secrets.token_urlsafe(48))\" 產生"
            )
        self._secret = secret
        self.access_ttl = timedelta(minutes=access_ttl_minutes)
        self.refresh_ttl = timedelta(days=refresh_ttl_days)

    @classmethod
    def from_environment(cls, project_dir: Path, runtime_dir: Path) -> "TokenService":
        return cls(
            secret=resolve_secret(project_dir, runtime_dir),
            access_ttl_minutes=_env_int(
                project_dir,
                "ROOMPILOT_AUTH_ACCESS_TTL_MINUTES",
                DEFAULT_ACCESS_TTL_MINUTES,
            ),
            refresh_ttl_days=_env_int(
                project_dir,
                "ROOMPILOT_AUTH_REFRESH_TTL_DAYS",
                DEFAULT_REFRESH_TTL_DAYS,
            ),
        )

    def _encode(
        self,
        *,
        user_id: str,
        token_type: TokenType,
        ttl: timedelta,
        extra: dict[str, Any] | None = None,
    ) -> tuple[str, str, datetime]:
        issued_at = datetime.now(timezone.utc)
        expires_at = issued_at + ttl
        jti = uuid4().hex
        payload: dict[str, Any] = {
            "sub": user_id,
            "type": token_type,
            "jti": jti,
            "iat": int(issued_at.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        payload.update(extra or {})
        return jwt.encode(payload, self._secret, algorithm=ALGORITHM), jti, expires_at

    def issue_access_token(
        self, *, user_id: str, email: str, role: str
    ) -> tuple[str, datetime]:
        token, _jti, expires_at = self._encode(
            user_id=user_id,
            token_type="access",
            ttl=self.access_ttl,
            extra={"email": email, "role": role},
        )
        return token, expires_at

    def issue_refresh_token(self, *, user_id: str) -> tuple[str, str, datetime]:
        """回傳 (token, jti, expires_at)；jti 交給儲存層登記才能撤銷。"""
        return self._encode(
            user_id=user_id,
            token_type="refresh",
            ttl=self.refresh_ttl,
        )

    def decode(self, token: str, *, expected_type: TokenType) -> TokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[ALGORITHM],
                leeway=LEEWAY_SECONDS,
                options={"require": ["sub", "exp", "iat", "jti"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenError("TOKEN_EXPIRED") from exc
        except jwt.InvalidTokenError as exc:
            raise TokenError("TOKEN_INVALID") from exc

        token_type = payload.get("type")
        if token_type != expected_type:
            # access 與 refresh 不可互換使用，否則短期 token 會被當成續期憑證。
            raise TokenError("TOKEN_TYPE_MISMATCH")
        user_id = payload.get("sub")
        if not isinstance(user_id, str) or not user_id:
            raise TokenError("TOKEN_INVALID")
        return TokenClaims(
            user_id=user_id,
            token_type=token_type,
            jti=str(payload["jti"]),
            expires_at=datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc),
            email=payload.get("email"),
            role=payload.get("role"),
        )
