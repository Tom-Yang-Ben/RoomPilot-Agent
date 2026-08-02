"""帳戶端 API：註冊、登入、續期、登出、專案成員與「我的專案」。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from .dependencies import (
    current_user,
    get_auth_service,
    get_user_store,
    project_owner,
    project_reader,
    require_system_role,
)
from .models import (
    AddProjectMemberRequest,
    AdminResetPasswordRequest,
    ChangePasswordRequest,
    LoginRequest,
    ProjectMember,
    ProjectSummary,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserPublic,
)
from .service import AuthenticationFailed, RegistrationFailed
from .throttle import LoginThrottle
from .tokens import TokenError
from .user_store import UserNotFound


def _client_key(request: Request, email: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}|{email}"


def build_auth_router() -> APIRouter:
    router = APIRouter(prefix="/api", tags=["auth"])
    throttle = LoginThrottle()

    def _throttled(retry_after: float) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error_code": "TOO_MANY_LOGIN_ATTEMPTS",
                "message": f"登入嘗試過於頻繁，請於 {int(retry_after) + 1} 秒後再試",
            },
            headers={"Retry-After": str(int(retry_after) + 1)},
        )

    @router.post(
        "/auth/register",
        response_model=TokenPair,
        status_code=status.HTTP_201_CREATED,
    )
    def register(body: RegisterRequest) -> TokenPair:
        try:
            result = get_auth_service().register(body)
        except RegistrationFailed as exc:
            if exc.reason == "EMAIL_ALREADY_REGISTERED":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error_code": "EMAIL_ALREADY_REGISTERED",
                        "message": "這個 email 已經註冊過",
                    },
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error_code": "REGISTRATION_FAILED", "message": exc.reason},
            ) from exc
        return TokenPair(**result)

    @router.post("/auth/login", response_model=TokenPair)
    def login(body: LoginRequest, request: Request) -> TokenPair:
        key = _client_key(request, body.email)
        retry_after = throttle.retry_after_seconds(key)
        if retry_after is not None:
            raise _throttled(retry_after)
        try:
            result = get_auth_service().authenticate(body)
        except AuthenticationFailed as exc:
            throttle.record_failure(key)
            # 不區分「email 不存在」與「密碼錯誤」，避免帳號列舉。
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error_code": "INVALID_CREDENTIALS",
                    "message": "email 或密碼不正確",
                },
            ) from exc
        throttle.reset(key)
        return TokenPair(**result)

    @router.post("/auth/refresh", response_model=TokenPair)
    def refresh(body: RefreshRequest) -> TokenPair:
        try:
            result = get_auth_service().refresh(body.refresh_token)
        except TokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error_code": exc.reason, "message": "請重新登入"},
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        return TokenPair(**result)

    @router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
    def logout(body: RefreshRequest) -> Response:
        get_auth_service().logout(body.refresh_token)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get("/auth/me", response_model=UserPublic)
    def me(user: dict[str, Any] = Depends(current_user)) -> UserPublic:
        return UserPublic(**user)

    @router.post("/auth/password", response_model=TokenPair)
    def change_password(
        body: ChangePasswordRequest,
        user: dict[str, Any] = Depends(current_user),
    ) -> TokenPair:
        try:
            result = get_auth_service().change_password(
                user["user_id"], body.current_password, body.new_password
            )
        except AuthenticationFailed as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "CURRENT_PASSWORD_INCORRECT",
                    "message": "目前密碼不正確",
                },
            ) from exc
        return TokenPair(**result)

    @router.post("/auth/admin/reset-password", response_model=UserPublic)
    def admin_reset_password(
        body: AdminResetPasswordRequest,
        _admin: dict[str, Any] = Depends(require_system_role("admin")),
    ) -> UserPublic:
        try:
            record = get_auth_service().admin_reset_password(
                body.email, body.new_password
            )
        except UserNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error_code": "USER_NOT_FOUND",
                    "message": "找不到這個 email 的帳號",
                },
            ) from exc
        return UserPublic(**record)

    @router.get("/projects", response_model=list[ProjectSummary])
    def list_my_projects(
        user: dict[str, Any] = Depends(current_user),
    ) -> list[ProjectSummary]:
        rows = get_user_store().list_projects_for_user(user["user_id"])
        return [ProjectSummary(**row) for row in rows]

    @router.get(
        "/projects/{project_id}/members",
        response_model=list[ProjectMember],
    )
    def list_members(
        project_id: str,
        _user: dict[str, Any] = Depends(project_reader),
    ) -> list[ProjectMember]:
        return [
            ProjectMember(**row)
            for row in get_user_store().list_project_members(project_id)
        ]

    @router.post(
        "/projects/{project_id}/members",
        response_model=list[ProjectMember],
        status_code=status.HTTP_201_CREATED,
    )
    def add_member(
        project_id: str,
        body: AddProjectMemberRequest,
        _user: dict[str, Any] = Depends(project_owner),
    ) -> list[ProjectMember]:
        store = get_user_store()
        target = store.find_user_by_email(body.email)
        if target is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error_code": "USER_NOT_FOUND",
                    "message": "這個 email 還沒有註冊帳號",
                },
            )
        store.add_project_member(
            project_id=project_id,
            user_id=target["user_id"],
            project_role=body.project_role,
        )
        return [
            ProjectMember(**row) for row in store.list_project_members(project_id)
        ]

    @router.delete(
        "/projects/{project_id}/members/{user_id}",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    def remove_member(
        project_id: str,
        user_id: str,
        owner: dict[str, Any] = Depends(project_owner),
    ) -> Response:
        store = get_user_store()
        if store.get_project_role(project_id=project_id, user_id=user_id) == "owner":
            # 移除擁有者會讓專案變成沒人能存取的孤兒。
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error_code": "CANNOT_REMOVE_OWNER",
                    "message": "不能移除專案擁有者",
                },
            )
        del owner
        store.remove_project_member(project_id=project_id, user_id=user_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
