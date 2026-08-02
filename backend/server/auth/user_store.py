"""使用者、refresh token 與專案成員的儲存層。

對稱於 ``project_store`` 的 provider 模式，而且刻意與專案資料放在同一個資料庫：
SQLite 用同一個 ``projects.sqlite3``，PostgreSQL 借用 ``PostgresProjectStore``
既有的連線池。授權查詢因此可以直接 JOIN 專案表，也不會多開第二個連線池。
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from ..project_store import ProjectStoreUnavailable
from .models import PROJECT_ROLES, SYSTEM_ROLES


class EmailAlreadyRegistered(ValueError):
    """該 email 已有帳號；註冊端要轉成 409 而不是 500。"""


class UserNotFound(KeyError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _validate_roles(*, role: str | None = None, project_role: str | None = None) -> None:
    if role is not None and role not in SYSTEM_ROLES:
        raise ValueError(f"未知的系統角色: {role}")
    if project_role is not None and project_role not in PROJECT_ROLES:
        raise ValueError(f"未知的專案角色: {project_role}")


def _user(row: Any) -> dict[str, Any]:
    return {
        "user_id": row["user_id"],
        "email": row["email"],
        "display_name": row["display_name"],
        "role": row["role"],
        "password_hash": row["password_hash"],
        "created_at": _parse_datetime(row["created_at"]),
    }


def public_user(record: dict[str, Any]) -> dict[str, Any]:
    """去掉 password_hash，任何往外送的路徑都必須經過這裡。"""
    return {key: value for key, value in record.items() if key != "password_hash"}


class SqliteUserStore:
    """與 ProjectStore 共用 projects.sqlite3 的使用者儲存。"""

    provider = "sqlite"

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    jti TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS project_members (
                    project_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    project_role TEXT NOT NULL,
                    added_at TEXT NOT NULL,
                    PRIMARY KEY (project_id, user_id),
                    FOREIGN KEY(project_id) REFERENCES projects(project_id)
                        ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_project_members_user "
                "ON project_members(user_id, project_id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user "
                "ON refresh_tokens(user_id)"
            )
            # 專案歸屬欄位：與 projects 表同庫才能在列表查詢直接 JOIN。
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(projects)").fetchall()
            }
            if columns and "owner_id" not in columns:
                connection.execute("ALTER TABLE projects ADD COLUMN owner_id TEXT")

    def create_user(
        self, *, email: str, password_hash: str, display_name: str, role: str
    ) -> dict[str, Any]:
        _validate_roles(role=role)
        user_id = uuid4().hex
        now = _utc_now()
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO users (
                        user_id, email, password_hash, display_name, role, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        email,
                        password_hash,
                        display_name,
                        role,
                        now.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise EmailAlreadyRegistered(email) from exc
        return self.get_user_by_id(user_id)

    def get_user_by_id(self, user_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
        if row is None:
            raise UserNotFound(user_id)
        return _user(row)

    def find_user_by_email(self, email: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            ).fetchone()
        return _user(row) if row is not None else None

    def update_password_hash(self, user_id: str, password_hash: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE users SET password_hash = ? WHERE user_id = ?",
                (password_hash, user_id),
            )

    def count_users(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM users").fetchone()
        return int(row["total"])

    def register_refresh_token(
        self, *, jti: str, user_id: str, expires_at: datetime
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO refresh_tokens (jti, user_id, expires_at, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (jti, user_id, expires_at.isoformat(), _utc_now().isoformat()),
            )

    def is_refresh_token_active(self, jti: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT expires_at FROM refresh_tokens WHERE jti = ?", (jti,)
            ).fetchone()
        if row is None:
            return False
        return _parse_datetime(row["expires_at"]) > _utc_now()

    def revoke_refresh_token(self, jti: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM refresh_tokens WHERE jti = ?", (jti,))

    def revoke_all_refresh_tokens(self, user_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM refresh_tokens WHERE user_id = ?", (user_id,)
            )

    def purge_expired_refresh_tokens(self) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM refresh_tokens WHERE expires_at <= ?",
                (_utc_now().isoformat(),),
            )
            return cursor.rowcount or 0

    def set_project_owner(self, project_id: str, user_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE projects SET owner_id = ? WHERE project_id = ?",
                (user_id, project_id),
            )
            connection.execute(
                """
                INSERT INTO project_members (project_id, user_id, project_role, added_at)
                VALUES (?, ?, 'owner', ?)
                ON CONFLICT(project_id, user_id) DO UPDATE SET project_role = 'owner'
                """,
                (project_id, user_id, _utc_now().isoformat()),
            )

    def add_project_member(
        self, *, project_id: str, user_id: str, project_role: str
    ) -> None:
        _validate_roles(project_role=project_role)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO project_members (project_id, user_id, project_role, added_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(project_id, user_id)
                    DO UPDATE SET project_role = excluded.project_role
                """,
                (project_id, user_id, project_role, _utc_now().isoformat()),
            )

    def remove_project_member(self, *, project_id: str, user_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM project_members WHERE project_id = ? AND user_id = ?",
                (project_id, user_id),
            )

    def get_project_role(self, *, project_id: str, user_id: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT project_role FROM project_members
                WHERE project_id = ? AND user_id = ?
                """,
                (project_id, user_id),
            ).fetchone()
        return row["project_role"] if row is not None else None

    def project_has_owner(self, project_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT owner_id FROM projects WHERE project_id = ?", (project_id,)
            ).fetchone()
        return row is not None and bool(row["owner_id"])

    def list_project_members(self, project_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT m.user_id, m.project_role, m.added_at, u.email, u.display_name
                FROM project_members AS m
                JOIN users AS u ON u.user_id = m.user_id
                WHERE m.project_id = ?
                ORDER BY m.added_at, m.user_id
                """,
                (project_id,),
            ).fetchall()
        return [
            {
                "user_id": row["user_id"],
                "email": row["email"],
                "display_name": row["display_name"],
                "project_role": row["project_role"],
                "added_at": _parse_datetime(row["added_at"]),
            }
            for row in rows
        ]

    def list_projects_for_user(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT p.project_id, p.name, p.notes, p.current_step, p.revision,
                       p.created_at, p.updated_at, m.project_role
                FROM project_members AS m
                JOIN projects AS p ON p.project_id = m.project_id
                WHERE m.user_id = ?
                ORDER BY p.updated_at DESC, p.project_id
                """,
                (user_id,),
            ).fetchall()
        return [
            {
                "project_id": row["project_id"],
                "name": row["name"],
                "notes": row["notes"],
                "current_step": row["current_step"],
                "revision": int(row["revision"]),
                "project_role": row["project_role"],
                "created_at": _iso(row["created_at"]),
                "updated_at": _iso(row["updated_at"]),
            }
            for row in rows
        ]

    def list_unowned_project_ids(self) -> list[str]:
        """遷移用：帳戶端上線前建立的專案沒有 owner。"""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT project_id FROM projects WHERE owner_id IS NULL OR owner_id = ''"
            ).fetchall()
        return [row["project_id"] for row in rows]

    def find_first_admin(self) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM users WHERE role = 'admin'
                ORDER BY created_at, user_id LIMIT 1
                """
            ).fetchone()
        return _user(row) if row is not None else None

    def close(self) -> None:
        """對稱於 PostgreSQL 生命週期；SQLite 每次操作自行開關。"""


class PostgresUserStore:
    """借用 PostgresProjectStore 連線池的使用者儲存。"""

    provider = "postgres"

    def __init__(self, connection_factory: Any) -> None:
        # connection_factory 是 PostgresProjectStore._connection 這個
        # context manager，共用同一個池才不會出現第二組連線上限。
        self._connection = connection_factory

    @staticmethod
    def _cursor(connection: Any):
        from psycopg2.extras import RealDictCursor

        return connection.cursor(cursor_factory=RealDictCursor)

    def create_user(
        self, *, email: str, password_hash: str, display_name: str, role: str
    ) -> dict[str, Any]:
        _validate_roles(role=role)
        import psycopg2

        user_id = uuid4().hex
        try:
            with self._connection() as connection:
                with self._cursor(connection) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO roompilot.users (
                            user_id, email, password_hash, display_name, role
                        ) VALUES (%s, %s, %s, %s, %s)
                        RETURNING *
                        """,
                        (user_id, email, password_hash, display_name, role),
                    )
                    return _user(cursor.fetchone())
        except psycopg2.errors.UniqueViolation as exc:
            raise EmailAlreadyRegistered(email) from exc

    def get_user_by_id(self, user_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            with self._cursor(connection) as cursor:
                cursor.execute(
                    "SELECT * FROM roompilot.users WHERE user_id = %s", (user_id,)
                )
                row = cursor.fetchone()
        if row is None:
            raise UserNotFound(user_id)
        return _user(row)

    def find_user_by_email(self, email: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            with self._cursor(connection) as cursor:
                cursor.execute(
                    "SELECT * FROM roompilot.users WHERE email = %s", (email,)
                )
                row = cursor.fetchone()
        return _user(row) if row is not None else None

    def update_password_hash(self, user_id: str, password_hash: str) -> None:
        with self._connection() as connection:
            with self._cursor(connection) as cursor:
                cursor.execute(
                    "UPDATE roompilot.users SET password_hash = %s WHERE user_id = %s",
                    (password_hash, user_id),
                )

    def count_users(self) -> int:
        with self._connection() as connection:
            with self._cursor(connection) as cursor:
                cursor.execute("SELECT COUNT(*) AS total FROM roompilot.users")
                return int(cursor.fetchone()["total"])

    def register_refresh_token(
        self, *, jti: str, user_id: str, expires_at: datetime
    ) -> None:
        with self._connection() as connection:
            with self._cursor(connection) as cursor:
                cursor.execute(
                    """
                    INSERT INTO roompilot.refresh_tokens (jti, user_id, expires_at)
                    VALUES (%s, %s, %s)
                    """,
                    (jti, user_id, expires_at),
                )

    def is_refresh_token_active(self, jti: str) -> bool:
        with self._connection() as connection:
            with self._cursor(connection) as cursor:
                cursor.execute(
                    "SELECT expires_at FROM roompilot.refresh_tokens WHERE jti = %s",
                    (jti,),
                )
                row = cursor.fetchone()
        if row is None:
            return False
        return _parse_datetime(row["expires_at"]) > _utc_now()

    def revoke_refresh_token(self, jti: str) -> None:
        with self._connection() as connection:
            with self._cursor(connection) as cursor:
                cursor.execute(
                    "DELETE FROM roompilot.refresh_tokens WHERE jti = %s", (jti,)
                )

    def revoke_all_refresh_tokens(self, user_id: str) -> None:
        with self._connection() as connection:
            with self._cursor(connection) as cursor:
                cursor.execute(
                    "DELETE FROM roompilot.refresh_tokens WHERE user_id = %s",
                    (user_id,),
                )

    def purge_expired_refresh_tokens(self) -> int:
        with self._connection() as connection:
            with self._cursor(connection) as cursor:
                cursor.execute(
                    "DELETE FROM roompilot.refresh_tokens WHERE expires_at <= NOW()"
                )
                return cursor.rowcount or 0

    def set_project_owner(self, project_id: str, user_id: str) -> None:
        with self._connection() as connection:
            with self._cursor(connection) as cursor:
                cursor.execute(
                    "UPDATE roompilot.projects SET owner_id = %s WHERE project_id = %s",
                    (user_id, project_id),
                )
                cursor.execute(
                    """
                    INSERT INTO roompilot.project_members (
                        project_id, user_id, project_role
                    ) VALUES (%s, %s, 'owner')
                    ON CONFLICT (project_id, user_id)
                        DO UPDATE SET project_role = 'owner'
                    """,
                    (project_id, user_id),
                )

    def add_project_member(
        self, *, project_id: str, user_id: str, project_role: str
    ) -> None:
        _validate_roles(project_role=project_role)
        with self._connection() as connection:
            with self._cursor(connection) as cursor:
                cursor.execute(
                    """
                    INSERT INTO roompilot.project_members (
                        project_id, user_id, project_role
                    ) VALUES (%s, %s, %s)
                    ON CONFLICT (project_id, user_id)
                        DO UPDATE SET project_role = EXCLUDED.project_role
                    """,
                    (project_id, user_id, project_role),
                )

    def remove_project_member(self, *, project_id: str, user_id: str) -> None:
        with self._connection() as connection:
            with self._cursor(connection) as cursor:
                cursor.execute(
                    """
                    DELETE FROM roompilot.project_members
                    WHERE project_id = %s AND user_id = %s
                    """,
                    (project_id, user_id),
                )

    def get_project_role(self, *, project_id: str, user_id: str) -> str | None:
        with self._connection() as connection:
            with self._cursor(connection) as cursor:
                cursor.execute(
                    """
                    SELECT project_role FROM roompilot.project_members
                    WHERE project_id = %s AND user_id = %s
                    """,
                    (project_id, user_id),
                )
                row = cursor.fetchone()
        return row["project_role"] if row is not None else None

    def project_has_owner(self, project_id: str) -> bool:
        with self._connection() as connection:
            with self._cursor(connection) as cursor:
                cursor.execute(
                    "SELECT owner_id FROM roompilot.projects WHERE project_id = %s",
                    (project_id,),
                )
                row = cursor.fetchone()
        return row is not None and bool(row["owner_id"])

    def list_project_members(self, project_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            with self._cursor(connection) as cursor:
                cursor.execute(
                    """
                    SELECT m.user_id, m.project_role, m.added_at,
                           u.email, u.display_name
                    FROM roompilot.project_members AS m
                    JOIN roompilot.users AS u ON u.user_id = m.user_id
                    WHERE m.project_id = %s
                    ORDER BY m.added_at, m.user_id
                    """,
                    (project_id,),
                )
                rows = cursor.fetchall()
        return [
            {
                "user_id": row["user_id"],
                "email": row["email"],
                "display_name": row["display_name"],
                "project_role": row["project_role"],
                "added_at": _parse_datetime(row["added_at"]),
            }
            for row in rows
        ]

    def list_projects_for_user(self, user_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            with self._cursor(connection) as cursor:
                cursor.execute(
                    """
                    SELECT p.project_id, p.name, p.notes, p.current_step, p.revision,
                           p.created_at, p.updated_at, m.project_role
                    FROM roompilot.project_members AS m
                    JOIN roompilot.projects AS p ON p.project_id = m.project_id
                    WHERE m.user_id = %s
                    ORDER BY p.updated_at DESC, p.project_id
                    """,
                    (user_id,),
                )
                rows = cursor.fetchall()
        return [
            {
                "project_id": row["project_id"],
                "name": row["name"],
                "notes": row["notes"],
                "current_step": row["current_step"],
                "revision": int(row["revision"]),
                "project_role": row["project_role"],
                "created_at": _iso(row["created_at"]),
                "updated_at": _iso(row["updated_at"]),
            }
            for row in rows
        ]

    def list_unowned_project_ids(self) -> list[str]:
        with self._connection() as connection:
            with self._cursor(connection) as cursor:
                cursor.execute(
                    """
                    SELECT project_id FROM roompilot.projects
                    WHERE owner_id IS NULL OR owner_id = ''
                    """
                )
                rows = cursor.fetchall()
        return [row["project_id"] for row in rows]

    def find_first_admin(self) -> dict[str, Any] | None:
        with self._connection() as connection:
            with self._cursor(connection) as cursor:
                cursor.execute(
                    """
                    SELECT * FROM roompilot.users WHERE role = 'admin'
                    ORDER BY created_at, user_id LIMIT 1
                    """
                )
                row = cursor.fetchone()
        return _user(row) if row is not None else None

    def close(self) -> None:
        """連線池由 PostgresProjectStore 擁有，這裡不重複關閉。"""


def build_user_store(project_store: Any) -> SqliteUserStore | PostgresUserStore:
    """依既有 project store 的 provider 建立對應的使用者儲存，不做靜默 fallback。"""
    provider = getattr(project_store, "provider", "sqlite")
    if provider == "postgres":
        return PostgresUserStore(project_store._connection)
    try:
        database_path = project_store.database_path
    except AttributeError as exc:
        # 專案儲存拿不出資料庫位置，等同於使用者資料也無處可讀。回報成
        # 「儲存不可用」而不是 AttributeError，呼叫端才能映射成 503。
        raise ProjectStoreUnavailable("user_store_unavailable") from exc
    return SqliteUserStore(database_path)
