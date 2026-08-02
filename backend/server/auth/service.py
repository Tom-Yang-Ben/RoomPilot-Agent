"""註冊、登入、續期與登出的業務規則。"""

from __future__ import annotations

import os
from typing import Any, Callable

from .models import LoginRequest, RegisterRequest
from .password import hash_password, needs_rehash, verify_password
from .tokens import TokenError, TokenService
from .user_store import EmailAlreadyRegistered, UserNotFound, public_user


# 帳號不存在時仍要付出一次雜湊成本，否則回應時間會洩漏「這個 email 有沒有註冊」。
# 內容不重要，只要格式合法、迭代次數與正式雜湊相同即可。
_DUMMY_HASH = hash_password("roompilot-timing-equalizer")


class AuthenticationFailed(Exception):
    """帳密錯誤；對外一律是同一句訊息，不區分 email 不存在或密碼錯誤。"""


class AccountDisabled(Exception):
    """帳號已被管理員停用。密碼驗證通過後才拋，不洩漏帳號存在性。"""


class SelfDeactivationBlocked(Exception):
    """不允許停用自己——最後一個 admin 把自己鎖在門外就沒人能解鎖了。"""


class RegistrationFailed(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class AuthService:
    def __init__(
        self,
        user_store: Any | Callable[[], Any],
        token_service: TokenService,
    ) -> None:
        # 接受實例或 getter：使用者資料與專案資料必須在同一個資料庫，而
        # PROJECT_STORE 可能在執行期被替換（測試、provider 切換）。傳 getter
        # 才能保證兩者永遠指向同一處。
        self._user_store_getter: Callable[[], Any] = (
            user_store if callable(user_store) else (lambda: user_store)
        )
        self.token_service = token_service

    @property
    def user_store(self) -> Any:
        return self._user_store_getter()

    def _bootstrap_role(self, requested_role: str) -> str:
        """第一個註冊的帳號成為 admin，讓全新環境有人能做遷移與跨帳號維運。

        正式部署應在開放註冊前先建立 admin，或設
        ``ROOMPILOT_AUTH_DISABLE_FIRST_ADMIN=1`` 關閉這個行為——否則最先搶到
        註冊的人就會拿到 admin。
        """
        if os.getenv("ROOMPILOT_AUTH_DISABLE_FIRST_ADMIN", "").strip() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            return requested_role
        if self.user_store.count_users() == 0:
            return "admin"
        return requested_role

    def register(self, request: RegisterRequest) -> dict[str, Any]:
        role = self._bootstrap_role(request.role)
        try:
            record = self.user_store.create_user(
                email=request.email,
                password_hash=hash_password(request.password),
                display_name=request.display_name,
                role=role,
            )
        except EmailAlreadyRegistered as exc:
            raise RegistrationFailed("EMAIL_ALREADY_REGISTERED") from exc
        except ValueError as exc:
            raise RegistrationFailed(str(exc)) from exc
        if record["role"] == "admin":
            # 帳戶端上線前建立的專案沒有 owner，沒人收養就永遠沒人能開。
            self.adopt_unowned_projects(record["user_id"])
        return self.issue_tokens(record)

    def adopt_unowned_projects(self, user_id: str) -> int:
        """把沒有 owner 的既有專案指派給指定使用者，冪等。"""
        project_ids = self.user_store.list_unowned_project_ids()
        for project_id in project_ids:
            self.user_store.set_project_owner(project_id, user_id)
        return len(project_ids)

    def authenticate(self, request: LoginRequest) -> dict[str, Any]:
        record = self.user_store.find_user_by_email(request.email)
        stored_hash = record["password_hash"] if record else _DUMMY_HASH
        matched = verify_password(request.password, stored_hash)
        if record is None or not matched:
            raise AuthenticationFailed()
        if not record.get("is_active", True):
            raise AccountDisabled()
        if needs_rehash(stored_hash):
            # 雜湊參數調高後，趁本次已驗證的明文順手升級。
            self.user_store.update_password_hash(
                record["user_id"], hash_password(request.password)
            )
        # 順手清掉整庫已過期的 refresh token——這張表沒有其他清理排程，
        # 登入是唯一夠頻繁又已經在寫庫的時機。
        self.user_store.purge_expired_refresh_tokens()
        return self.issue_tokens(record)

    def change_password(
        self, user_id: str, current_password: str, new_password: str
    ) -> dict[str, Any]:
        """已登入者改密碼。舊密碼驗證失敗拋 AuthenticationFailed。

        改密碼視同懷疑舊憑證外洩：撤銷該帳號所有 refresh token，回傳一組
        新憑證給目前這個 session，其他裝置一律要重新登入。
        """
        record = self.user_store.get_user_by_id(user_id)
        if not verify_password(current_password, record["password_hash"]):
            raise AuthenticationFailed()
        self.user_store.update_password_hash(user_id, hash_password(new_password))
        self.user_store.revoke_all_refresh_tokens(user_id)
        return self.issue_tokens(record)

    def admin_reset_password(self, email: str, new_password: str) -> dict[str, Any]:
        """管理員重設他人密碼（無寄信基礎設施的「忘記密碼」替代方案）。

        撤銷目標帳號所有 refresh token；找不到帳號拋 UserNotFound。
        """
        record = self.user_store.find_user_by_email(email)
        if record is None:
            raise UserNotFound(email)
        self.user_store.update_password_hash(
            record["user_id"], hash_password(new_password)
        )
        self.user_store.revoke_all_refresh_tokens(record["user_id"])
        return public_user(record)

    def issue_tokens(self, record: dict[str, Any]) -> dict[str, Any]:
        access_token, expires_at = self.token_service.issue_access_token(
            user_id=record["user_id"],
            email=record["email"],
            role=record["role"],
        )
        refresh_token, jti, refresh_expires_at = (
            self.token_service.issue_refresh_token(user_id=record["user_id"])
        )
        self.user_store.register_refresh_token(
            jti=jti,
            user_id=record["user_id"],
            expires_at=refresh_expires_at,
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
            "user": public_user(record),
        }

    def refresh(self, refresh_token: str) -> dict[str, Any]:
        claims = self.token_service.decode(refresh_token, expected_type="refresh")
        if not self.user_store.is_refresh_token_active(claims.jti):
            # 簽章有效但不在白名單：已登出、已輪替，或被撤銷。
            raise TokenError("REFRESH_TOKEN_REVOKED")
        try:
            record = self.user_store.get_user_by_id(claims.user_id)
        except UserNotFound as exc:
            raise TokenError("USER_NOT_FOUND") from exc
        if not record.get("is_active", True):
            raise TokenError("ACCOUNT_DISABLED")
        # 輪替：舊 refresh token 立即作廢，被竊取的舊憑證無法繼續換發。
        self.user_store.revoke_refresh_token(claims.jti)
        return self.issue_tokens(record)

    def logout(self, refresh_token: str) -> None:
        """登出永遠回成功；壞掉或過期的 token 本來就已經不能用了。"""
        try:
            claims = self.token_service.decode(refresh_token, expected_type="refresh")
        except TokenError:
            return
        self.user_store.revoke_refresh_token(claims.jti)

    def resolve_access_token(self, token: str) -> dict[str, Any]:
        claims = self.token_service.decode(token, expected_type="access")
        try:
            record = self.user_store.get_user_by_id(claims.user_id)
        except UserNotFound as exc:
            raise TokenError("USER_NOT_FOUND") from exc
        # 每次驗證都撈使用者紀錄，停用因此立即生效——尚未過期的 access
        # token 不必等 30 分鐘 TTL 走完。
        if not record.get("is_active", True):
            raise TokenError("ACCOUNT_DISABLED")
        return public_user(record)

    def set_account_active(
        self, *, actor_user_id: str, email: str, active: bool
    ) -> dict[str, Any]:
        """管理員停用／恢復帳號。停用同時撤銷該帳號全部 refresh token。"""
        record = self.user_store.find_user_by_email(email)
        if record is None:
            raise UserNotFound(email)
        if record["user_id"] == actor_user_id and not active:
            raise SelfDeactivationBlocked()
        self.user_store.set_user_active(record["user_id"], active)
        if not active:
            self.user_store.revoke_all_refresh_tokens(record["user_id"])
        return public_user(self.user_store.get_user_by_id(record["user_id"]))
