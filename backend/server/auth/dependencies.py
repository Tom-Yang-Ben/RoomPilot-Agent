"""FastAPI 授權 dependency。

系統角色（能不能建立專案）與專案角色（在這個專案裡能做什麼）是兩個維度，
兩者都在這裡收斂，路由端不自己拼授權條件。
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import Depends, HTTPException, Request, status

from .models import PROJECT_WRITE_ROLES
from .service import AuthService
from .tokens import TokenError


_auth_service: AuthService | None = None
_user_store_getter: Callable[[], Any] | None = None


def configure(*, auth_service: AuthService, user_store: Any) -> None:
    """由 main.py 在建立 app 時注入；測試可重新呼叫換掉實作。

    ``user_store`` 可以是實例或 getter；傳 getter 才能在 PROJECT_STORE 被替換時
    自動跟著換到同一個資料庫。
    """
    global _auth_service, _user_store_getter
    _auth_service = auth_service
    _user_store_getter = user_store if callable(user_store) else (lambda: user_store)


def get_auth_service() -> AuthService:
    if _auth_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_code": "AUTH_NOT_CONFIGURED", "message": "帳戶服務尚未初始化"},
        )
    return _auth_service


def get_user_store() -> Any:
    if _user_store_getter is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_code": "AUTH_NOT_CONFIGURED", "message": "帳戶服務尚未初始化"},
        )
    return _user_store_getter()


def _unauthorized(reason: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error_code": reason, "message": "請重新登入"},
        headers={"WWW-Authenticate": "Bearer"},
    )


def _project_not_visible() -> HTTPException:
    """非成員與不存在的專案回同一個 404。

    回 403 會讓外人靠狀態碼判斷某個 project_id 是否存在；這裡刻意讓兩種情況
    無法區分。
    """
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error_code": "PROJECT_NOT_FOUND", "message": "找不到專案"},
    )


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("Authorization") or ""
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def current_user(request: Request) -> dict[str, Any]:
    token = _bearer_token(request)
    if token is None:
        raise _unauthorized("MISSING_BEARER_TOKEN")
    try:
        return get_auth_service().resolve_access_token(token)
    except TokenError as exc:
        raise _unauthorized(exc.reason) from exc


def optional_current_user(request: Request) -> dict[str, Any] | None:
    """給「登入後顯示更多、未登入也能看」的公開端點使用。"""
    try:
        return current_user(request)
    except HTTPException:
        return None


def require_system_role(*roles: str) -> Callable[..., dict[str, Any]]:
    allowed = frozenset(roles)

    def dependency(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        if user["role"] == "admin" or user["role"] in allowed:
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "INSUFFICIENT_ROLE",
                "message": f"這個操作需要 {'／'.join(sorted(allowed))} 角色",
            },
        )

    return dependency


def _project_role(project_id: str, user: dict[str, Any]) -> str:
    if user["role"] == "admin":
        return "owner"
    role = get_user_store().get_project_role(
        project_id=project_id, user_id=user["user_id"]
    )
    if role is None:
        raise _project_not_visible()
    return role


def project_reader(
    project_id: str, user: dict[str, Any] = Depends(current_user)
) -> dict[str, Any]:
    """可讀取這個專案；viewer 也通過。"""
    return {**user, "project_role": _project_role(project_id, user)}


def project_editor(
    project_id: str, user: dict[str, Any] = Depends(current_user)
) -> dict[str, Any]:
    """可修改這個專案；viewer 擋在這裡。"""
    role = _project_role(project_id, user)
    if role not in PROJECT_WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "PROJECT_READ_ONLY",
                "message": "你在這個專案是唯讀成員",
            },
        )
    return {**user, "project_role": role}


def project_owner(
    project_id: str, user: dict[str, Any] = Depends(current_user)
) -> dict[str, Any]:
    """只有擁有者能做的事：加減成員、刪除專案。"""
    role = _project_role(project_id, user)
    if role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "PROJECT_OWNER_REQUIRED",
                "message": "只有專案擁有者可以執行這個操作",
            },
        )
    return {**user, "project_role": role}
