from __future__ import annotations

from datetime import datetime, timezone
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.catalog import postgres_admin_repository as admin_repository
from backend.catalog.postgres_admin_repository import (
    CatalogAdminActivationError,
    CatalogAdminConflict,
)
from backend.server import catalog_admin, main


CLIENT = TestClient(main.app)
TOKEN = "phase2-test-token"
AUTH_HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "X-RoomPilot-Admin-Actor": "kai-test",
}


def _enable_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(catalog_admin, "catalog_admin_writes_enabled", lambda _project: True)
    monkeypatch.setattr(catalog_admin, "catalog_admin_token", lambda _project: TOKEN)


def _create_payload() -> dict:
    return {
        "item_id": "kai-phase2-chair-01",
        "category_code": "dining-chair",
        "name_en": "Kai Phase 2 Chair",
        "name_zh": "Kai 第二階段椅",
        "width_cm": 45,
        "depth_cm": 52,
        "height_cm": 82,
        "styles": [{"style_code": "modern", "confidence": 0.9}],
        "room_codes": ["dining_room"],
        "annotation": {
            "object_type_zh": "餐椅",
            "description": "CRUD 測試家具",
            "rag_text": ["餐椅", "現代"],
            "confidence": 0.95,
        },
        "raw_data": {"test_marker": "phase2"},
    }


def _admin_record(*, include_raw_data: bool = False) -> dict:
    record = {
        "schema_version": "catalog.admin.v1",
        "coordinate_unit": "cm",
        "item_id": "kai-phase2-chair-01",
        "kind": "furniture",
        "is_active": False,
        "updated_at": "2026-07-27T12:00:00+00:00",
    }
    if include_raw_data:
        record["raw_data"] = {"test_marker": "phase2"}
    return record


def test_admin_api_fails_closed_when_token_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(catalog_admin, "catalog_admin_writes_enabled", lambda _project: True)
    monkeypatch.setattr(catalog_admin, "catalog_admin_token", lambda _project: "")

    response = CLIENT.get("/api/admin/furniture/example")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "catalog_admin_not_configured"


def test_admin_api_rejects_missing_or_wrong_bearer_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_admin(monkeypatch)

    missing = CLIENT.get("/api/admin/furniture/example")
    wrong = CLIENT.get(
        "/api/admin/furniture/example",
        headers={"Authorization": "Bearer wrong"},
    )

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    assert wrong.json()["detail"]["code"] == "catalog_admin_unauthorized"


def test_admin_api_disables_writes_outside_strict_postgres_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(catalog_admin, "catalog_admin_writes_enabled", lambda _project: False)

    response = CLIENT.get("/api/admin/furniture/example", headers=AUTH_HEADERS)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "catalog_admin_requires_strict_postgres"


def test_admin_create_passes_validated_furniture_to_kai_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_admin(monkeypatch)
    captured: dict = {}

    def fake_create(project, payload, *, actor, include_raw_data):
        captured.update(
            project=project,
            payload=payload,
            actor=actor,
            include_raw_data=include_raw_data,
        )
        return _admin_record()

    monkeypatch.setattr(catalog_admin, "create_furniture", fake_create)

    response = CLIENT.post(
        "/api/admin/furniture",
        json=_create_payload(),
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 201
    assert response.json()["action"] == "created"
    assert response.json()["item"]["is_active"] is False
    assert captured["actor"] == "kai-test"
    assert captured["payload"]["category_code"] == "dining-chair"
    assert captured["payload"]["width_cm"] == 45
    assert captured["include_raw_data"] is False


def test_admin_read_returns_raw_data_only_when_explicitly_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_admin(monkeypatch)
    requested: list[bool] = []

    def fake_get(_project, _item_id, *, include_raw_data):
        requested.append(include_raw_data)
        return _admin_record(include_raw_data=include_raw_data)

    monkeypatch.setattr(catalog_admin, "get_admin_furniture", fake_get)

    normal = CLIENT.get("/api/admin/furniture/example", headers=AUTH_HEADERS)
    raw = CLIENT.get(
        "/api/admin/furniture/example?include_raw_data=true",
        headers=AUTH_HEADERS,
    )

    assert normal.status_code == 200
    assert "raw_data" not in normal.json()["item"]
    assert raw.json()["item"]["raw_data"] == {"test_marker": "phase2"}
    assert requested == [False, True]


def test_admin_patch_maps_activation_gate_to_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_admin(monkeypatch)
    monkeypatch.setattr(
        catalog_admin,
        "patch_furniture",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            CatalogAdminActivationError(
                "catalog_item_not_ready_for_activation",
                context={"missing": ["glb", "front_image"]},
            )
        ),
    )

    response = CLIENT.patch(
        "/api/admin/furniture/example",
        json={"is_active": True},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "catalog_item_not_ready_for_activation",
        "missing": ["glb", "front_image"],
    }


def test_admin_patch_maps_optimistic_lock_conflict_to_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_admin(monkeypatch)
    monkeypatch.setattr(
        catalog_admin,
        "patch_furniture",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            CatalogAdminConflict(
                "catalog_item_version_conflict",
                context={"current_updated_at": "2026-07-27T12:00:00+00:00"},
            )
        ),
    )

    response = CLIENT.patch(
        "/api/admin/furniture/example",
        json={
            "name_zh": "新版",
            "expected_updated_at": "2026-07-27T11:00:00Z",
        },
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "catalog_item_version_conflict"


def test_admin_delete_is_a_soft_delete_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_admin(monkeypatch)
    captured: dict = {}

    def fake_delete(project, item_id, **kwargs):
        captured.update(project=project, item_id=item_id, **kwargs)
        return _admin_record()

    monkeypatch.setattr(catalog_admin, "soft_delete_furniture", fake_delete)

    response = CLIENT.delete(
        "/api/admin/furniture/example",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["action"] == "soft_deleted"
    assert response.json()["item"]["is_active"] is False
    assert captured["item_id"] == "example"
    assert captured["actor"] == "kai-test"


def test_admin_input_rejects_appliance_shape_and_invalid_dimensions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_admin(monkeypatch)
    payload = _create_payload()
    payload["kind"] = "appliance"
    payload["width_cm"] = -1

    response = CLIENT.post(
        "/api/admin/furniture",
        json=payload,
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 422


def test_admin_patch_rejects_null_for_non_nullable_sql_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_admin(monkeypatch)

    response = CLIENT.patch(
        "/api/admin/furniture/example",
        json={"name_en": None, "is_active": None},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 422


def test_admin_response_hides_raw_payloads_by_default() -> None:
    record = {
        "item_id": "example",
        "raw_data": {"private_source": "full-row"},
        "annotation": {
            "description": "safe",
            "raw_response": {"provider": "full-response"},
        },
    }

    hidden = admin_repository._response_record(record, include_raw_data=False)
    included = admin_repository._response_record(record, include_raw_data=True)

    assert "raw_data" not in hidden
    assert "raw_response" not in hidden["annotation"]
    assert included["raw_data"] == {"private_source": "full-row"}
    assert included["annotation"]["raw_response"] == {"provider": "full-response"}


def test_transaction_commits_success_and_rolls_back_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeConnection:
        closed = False
        autocommit = True

        def __init__(self) -> None:
            self.commits = 0
            self.rollbacks = 0

        def commit(self) -> None:
            self.commits += 1

        def rollback(self) -> None:
            self.rollbacks += 1

    class FakePool:
        def __init__(self, connection) -> None:
            self.connection = connection
            self.returned = []

        def getconn(self):
            return self.connection

        def putconn(self, connection, close=False) -> None:
            self.returned.append((connection, close))

    success_connection = FakeConnection()
    success_pool = FakePool(success_connection)
    monkeypatch.setattr(admin_repository, "_connection_pool", lambda _project: success_pool)

    with admin_repository._transaction(main.PROJECT_DIR):
        pass

    assert success_connection.commits == 1
    assert success_connection.rollbacks == 0
    assert success_pool.returned == [(success_connection, False)]

    failure_connection = FakeConnection()
    failure_pool = FakePool(failure_connection)
    monkeypatch.setattr(admin_repository, "_connection_pool", lambda _project: failure_pool)

    with pytest.raises(RuntimeError, match="rollback-me"):
        with admin_repository._transaction(main.PROJECT_DIR):
            raise RuntimeError("rollback-me")

    assert failure_connection.commits == 0
    assert failure_connection.rollbacks == 1
    assert failure_pool.returned == [(failure_connection, False)]


def test_patch_revision_requires_timezone() -> None:
    with pytest.raises(CatalogAdminConflict) as captured:
        admin_repository._as_utc(datetime(2026, 7, 27, 12, 0))

    assert captured.value.code == "catalog_expected_updated_at_timezone_required"
    assert admin_repository._as_utc(
        datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
    ) == datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)


@pytest.mark.skipif(
    os.getenv("ROOMPILOT_TEST_POSTGRES_CRUD") != "1",
    reason="set ROOMPILOT_TEST_POSTGRES_CRUD=1 for the live transaction smoke test",
)
def test_live_postgres_crud_transaction_and_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the real API/DB contract and remove only the row created here."""
    item_id = f"kai-phase2-smoke-{uuid4().hex}"
    live_token = "phase2-live-smoke-token"
    headers = {
        "Authorization": f"Bearer {live_token}",
        "X-RoomPilot-Admin-Actor": "kai-live-smoke",
    }
    monkeypatch.setenv("ROOMPILOT_CATALOG_PROVIDER", "postgres")
    monkeypatch.setenv("ROOMPILOT_CATALOG_ADMIN_TOKEN", live_token)

    try:
        payload = _create_payload()
        payload["item_id"] = item_id
        created = CLIENT.post(
            "/api/admin/furniture?include_raw_data=true",
            json=payload,
            headers=headers,
        )
        assert created.status_code == 201, created.text
        created_item = created.json()["item"]
        assert created_item["is_active"] is False
        assert created_item["coordinate_unit"] == "cm"
        assert created_item["raw_data"] == {"test_marker": "phase2"}

        read_hidden = CLIENT.get(
            f"/api/admin/furniture/{item_id}",
            headers=headers,
        )
        assert read_hidden.status_code == 200
        assert "raw_data" not in read_hidden.json()["item"]

        updated = CLIENT.patch(
            f"/api/admin/furniture/{item_id}",
            json={
                "name_zh": "Kai 第二階段實庫測試椅",
                "expected_updated_at": created_item["updated_at"],
            },
            headers=headers,
        )
        assert updated.status_code == 200, updated.text
        updated_item = updated.json()["item"]
        assert updated_item["name_zh"] == "Kai 第二階段實庫測試椅"

        rejected_activation = CLIENT.patch(
            f"/api/admin/furniture/{item_id}",
            json={
                "is_active": True,
                "expected_updated_at": updated_item["updated_at"],
            },
            headers=headers,
        )
        assert rejected_activation.status_code == 422
        assert rejected_activation.json()["detail"]["code"] == (
            "catalog_item_not_ready_for_activation"
        )
        assert "glb" in rejected_activation.json()["detail"]["missing"]

        deleted = CLIENT.delete(
            f"/api/admin/furniture/{item_id}",
            params={"expected_updated_at": updated_item["updated_at"]},
            headers=headers,
        )
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["item"]["is_active"] is False

        with admin_repository._borrow_connection(main.PROJECT_DIR) as connection:
            with admin_repository._dict_cursor(connection) as cursor:
                cursor.execute(
                    """
                    SELECT action
                    FROM roompilot.furniture_admin_audit
                    WHERE item_id = %s
                    ORDER BY event_id
                    """,
                    (item_id,),
                )
                assert [row["action"] for row in cursor.fetchall()] == [
                    "create",
                    "update",
                    "soft_delete",
                ]
                cursor.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM roompilot.furniture_catalog_api_current
                    WHERE item_id = %s
                    """,
                    (item_id,),
                )
                assert cursor.fetchone()["count"] == 0
    finally:
        with admin_repository._transaction(main.PROJECT_DIR) as connection:
            with admin_repository._dict_cursor(connection) as cursor:
                cursor.execute(
                    "DELETE FROM roompilot.furniture_admin_audit WHERE item_id = %s",
                    (item_id,),
                )
                cursor.execute(
                    "DELETE FROM roompilot.furniture_items WHERE item_id = %s",
                    (item_id,),
                )
                cursor.execute(
                    """
                    SELECT
                        (SELECT COUNT(*) FROM roompilot.furniture_items WHERE item_id = %s)
                            AS item_count,
                        (SELECT COUNT(*) FROM roompilot.furniture_admin_audit WHERE item_id = %s)
                            AS audit_count
                    """,
                    (item_id, item_id),
                )
                cleanup = cursor.fetchone()
                assert cleanup == {"item_count": 0, "audit_count": 0}
