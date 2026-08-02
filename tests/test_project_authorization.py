"""帳戶端 API 與專案授權隔離。

重點在「別人的專案看不到、唯讀成員改不動」，這是加帳戶端的主要理由。
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.server.main import app


client = TestClient(app)


def _register(role: str = "designer") -> dict:
    """註冊一個新帳號並回傳其 token 與身分。"""
    email = f"{uuid.uuid4().hex[:12]}@example.com"
    response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "test-password-1234",
            "display_name": "測試使用者",
            "role": role,
        },
        headers={"Authorization": ""},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    return {
        "email": email,
        "auth": {"Authorization": f"Bearer {payload['access_token']}"},
        "refresh": payload["refresh_token"],
        "user": payload["user"],
    }


def _create_project(actor: dict, name: str = "授權測試案") -> str:
    response = client.post(
        "/api/projects", json={"name": name}, headers=actor["auth"]
    )
    assert response.status_code == 201, response.text
    return response.json()["project"]["project_id"]


def test_anonymous_requests_are_rejected(anonymous_client: TestClient) -> None:
    assert anonymous_client.get("/api/projects").status_code == 401
    assert anonymous_client.get("/api/auth/me").status_code == 401
    assert (
        anonymous_client.post("/api/projects", json={"name": "x"}).status_code == 401
    )


def test_registration_login_and_refresh_rotation() -> None:
    actor = _register()

    login = client.post(
        "/api/auth/login",
        json={"email": actor["email"], "password": "test-password-1234"},
        headers={"Authorization": ""},
    )
    assert login.status_code == 200
    refresh_token = login.json()["refresh_token"]

    first = client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
        headers={"Authorization": ""},
    )
    assert first.status_code == 200
    # 輪替：同一個 refresh token 不能用第二次，被竊的舊憑證才會失效。
    replay = client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
        headers={"Authorization": ""},
    )
    assert replay.status_code == 401


def test_wrong_password_and_unknown_email_are_indistinguishable() -> None:
    actor = _register()

    wrong_password = client.post(
        "/api/auth/login",
        json={"email": actor["email"], "password": "definitely-wrong"},
        headers={"Authorization": ""},
    )
    unknown_email = client.post(
        "/api/auth/login",
        json={"email": "nobody-here@example.com", "password": "definitely-wrong"},
        headers={"Authorization": ""},
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    # 訊息一致才不會洩漏「這個 email 有沒有註冊過」。
    assert wrong_password.json()["detail"] == unknown_email.json()["detail"]


def test_logout_revokes_the_refresh_token() -> None:
    actor = _register()

    assert (
        client.post(
            "/api/auth/logout",
            json={"refresh_token": actor["refresh"]},
            headers=actor["auth"],
        ).status_code
        == 204
    )
    assert (
        client.post(
            "/api/auth/refresh",
            json={"refresh_token": actor["refresh"]},
            headers={"Authorization": ""},
        ).status_code
        == 401
    )


def test_creator_becomes_owner_and_sees_the_project_in_their_list() -> None:
    actor = _register()
    project_id = _create_project(actor, "我的第一個案子")

    listing = client.get("/api/projects", headers=actor["auth"])
    assert listing.status_code == 200
    entries = {item["project_id"]: item for item in listing.json()}
    assert project_id in entries
    assert entries[project_id]["project_role"] == "owner"
    assert entries[project_id]["name"] == "我的第一個案子"


def test_another_designer_cannot_read_or_write_someone_elses_project() -> None:
    owner = _register()
    stranger = _register()
    project_id = _create_project(owner)

    # 回 404 而不是 403：403 會讓外人靠狀態碼確認某個 project_id 存在。
    assert (
        client.get(f"/api/projects/{project_id}", headers=stranger["auth"]).status_code
        == 404
    )
    assert (
        client.put(
            f"/api/projects/{project_id}/workflow",
            json={"workflow": {"hacked": True}},
            headers=stranger["auth"],
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/projects/{project_id}/renders", headers=stranger["auth"]
        ).status_code
        == 404
    )
    assert project_id not in {
        item["project_id"]
        for item in client.get("/api/projects", headers=stranger["auth"]).json()
    }


def test_shared_viewer_can_read_but_cannot_modify() -> None:
    owner = _register()
    viewer = _register(role="client")
    project_id = _create_project(owner)

    shared = client.post(
        f"/api/projects/{project_id}/members",
        json={"email": viewer["email"], "project_role": "viewer"},
        headers=owner["auth"],
    )
    assert shared.status_code == 201
    assert {member["project_role"] for member in shared.json()} == {"owner", "viewer"}

    assert (
        client.get(f"/api/projects/{project_id}", headers=viewer["auth"]).status_code
        == 200
    )
    # 唯讀成員擋在 403（他看得到專案，只是不能改），與非成員的 404 不同。
    assert (
        client.put(
            f"/api/projects/{project_id}/workflow",
            json={"workflow": {"note": "viewer edit"}},
            headers=viewer["auth"],
        ).status_code
        == 403
    )


def test_editor_can_modify_the_shared_project() -> None:
    owner = _register()
    editor = _register()
    project_id = _create_project(owner)

    client.post(
        f"/api/projects/{project_id}/members",
        json={"email": editor["email"], "project_role": "editor"},
        headers=owner["auth"],
    )

    assert (
        client.put(
            f"/api/projects/{project_id}/workflow",
            json={"workflow": {"note": "editor edit"}},
            headers=editor["auth"],
        ).status_code
        == 200
    )


def test_only_the_owner_manages_members_and_the_owner_cannot_be_removed() -> None:
    owner = _register()
    editor = _register()
    project_id = _create_project(owner)

    client.post(
        f"/api/projects/{project_id}/members",
        json={"email": editor["email"], "project_role": "editor"},
        headers=owner["auth"],
    )
    # editor 有寫入權，但不能改成員名單。
    assert (
        client.post(
            f"/api/projects/{project_id}/members",
            json={"email": "someone-else@example.com", "project_role": "viewer"},
            headers=editor["auth"],
        ).status_code
        == 403
    )
    # 移除擁有者會讓專案變成沒人能存取的孤兒。
    assert (
        client.delete(
            f"/api/projects/{project_id}/members/{owner['user']['user_id']}",
            headers=owner["auth"],
        ).status_code
        == 409
    )
    assert (
        client.delete(
            f"/api/projects/{project_id}/members/{editor['user']['user_id']}",
            headers=owner["auth"],
        ).status_code
        == 204
    )


def test_client_role_cannot_create_projects() -> None:
    homeowner = _register(role="client")

    response = client.post(
        "/api/projects", json={"name": "屋主自建"}, headers=homeowner["auth"]
    )

    assert response.status_code == 403
    assert response.json()["detail"]["error_code"] == "INSUFFICIENT_ROLE"


def test_engineering_documents_are_not_reachable_across_accounts() -> None:
    owner = _register()
    stranger = _register()
    project_id = _create_project(owner)

    # 快照端點同樣受專案授權保護，而不只是靠 id 難猜。
    assert (
        client.get(
            f"/api/v1/projects/{project_id}/revisions/R1/snapshot",
            headers=stranger["auth"],
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/projects/{project_id}/engineering-packages",
            json={"revision": "R1"},
            headers=stranger["auth"],
        ).status_code
        == 404
    )


@pytest.mark.parametrize("weak", ["short", ""])
def test_registration_rejects_weak_passwords(weak: str) -> None:
    response = client.post(
        "/api/auth/register",
        json={
            "email": f"{uuid.uuid4().hex[:10]}@example.com",
            "password": weak,
            "display_name": "x",
        },
        headers={"Authorization": ""},
    )

    assert response.status_code == 422


def test_duplicate_email_is_rejected() -> None:
    actor = _register()

    response = client.post(
        "/api/auth/register",
        json={
            "email": actor["email"],
            "password": "another-password",
            "display_name": "冒名者",
        },
        headers={"Authorization": ""},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] == "EMAIL_ALREADY_REGISTERED"
