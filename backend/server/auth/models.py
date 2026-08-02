"""帳戶端的請求／回應契約與角色定義。"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


# 刻意不引入 pydantic[email]：email-validator 會連帶拉進 dnspython 與 idna，
# 而這裡的 email 只是登入識別字串，真正的有效性驗證是寄出驗證信（不在範圍內）。
# 這個式樣擋掉空白、缺 @、缺網域點號與明顯畸形的輸入。
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")
MAX_EMAIL_LENGTH = 254


def _normalize_email(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) > MAX_EMAIL_LENGTH:
        raise ValueError(f"email 不可超過 {MAX_EMAIL_LENGTH} 個字元")
    if not _EMAIL_PATTERN.match(cleaned):
        raise ValueError("email 格式不正確")
    # 網域大小寫不敏感，整串小寫化才不會讓同一人註冊出兩個帳號。
    return cleaned.casefold()


EmailAddress = Annotated[str, AfterValidator(_normalize_email)]


# 系統角色：決定「能不能建立專案、能不能鎖版出報告」。
# admin    —— 全部權限，含跨帳號檢視，供維運與資料遷移使用。
# designer —— 建立與編輯自己的專案、鎖定版本、產生工程報告。
# client   —— 只能檢視被分享的專案，不能修改幾何或鎖版。
SystemRole = Literal["admin", "designer", "client"]
SYSTEM_ROLES: tuple[str, ...] = ("admin", "designer", "client")

# 專案成員角色：決定「在這個專案裡能做什麼」，與系統角色是兩個維度。
ProjectRole = Literal["owner", "editor", "viewer"]
PROJECT_ROLES: tuple[str, ...] = ("owner", "editor", "viewer")

# 可寫入專案的成員角色；viewer 一律唯讀。
PROJECT_WRITE_ROLES: frozenset[str] = frozenset({"owner", "editor"})


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterRequest(StrictModel):
    email: EmailAddress
    password: str = Field(min_length=8, max_length=1024)
    display_name: str = Field(min_length=1, max_length=100)
    # 對外註冊只開放 designer 與 client；admin 一律由既有 admin 或遷移腳本指派。
    role: Literal["designer", "client"] = "designer"

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("display_name 不可只有空白")
        return cleaned


class LoginRequest(StrictModel):
    email: EmailAddress
    password: str = Field(min_length=1, max_length=1024)


class RefreshRequest(StrictModel):
    refresh_token: str = Field(min_length=1)


class UserPublic(StrictModel):
    user_id: str
    email: str
    display_name: str
    role: SystemRole
    created_at: datetime
    is_active: bool = True


class AdminSetActiveRequest(StrictModel):
    """管理員停用／恢復帳號；停用同時撤銷目標全部 refresh token。"""

    email: EmailAddress
    is_active: bool


class ChangePasswordRequest(StrictModel):
    """已登入者自行改密碼；目前密碼驗證失敗一律 400，不洩漏其他資訊。"""

    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=8, max_length=1024)


class AdminResetPasswordRequest(StrictModel):
    """管理員重設他人密碼——本產品無寄信基礎設施，「忘記密碼」由 admin
    設一組臨時密碼並口頭／訊息告知，使用者登入後再自行修改。"""

    email: EmailAddress
    new_password: str = Field(min_length=8, max_length=1024)


class TokenPair(StrictModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: UserPublic


class ProjectMember(StrictModel):
    user_id: str
    email: str
    display_name: str
    project_role: ProjectRole
    added_at: datetime


class AddProjectMemberRequest(StrictModel):
    email: EmailAddress
    project_role: Literal["editor", "viewer"] = "viewer"


class ProjectSummary(StrictModel):
    """「我的專案」列表用；不含 workflow 內容，避免列表頁載入整份場景。"""

    project_id: str
    name: str
    notes: str
    current_step: str
    revision: int
    project_role: ProjectRole
    created_at: str
    updated_at: str
