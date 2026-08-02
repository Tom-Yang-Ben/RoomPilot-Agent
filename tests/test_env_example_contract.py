from __future__ import annotations

from pathlib import Path

from backend.catalog import postgres_repository


ROOT = Path(__file__).resolve().parents[1]


def _env_example() -> dict[str, str]:
    pairs: dict[str, str] = {}
    for raw_line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        pairs[key] = value
    return pairs


def test_env_example_documents_openrouter_and_postgres_catalog_defaults() -> None:
    env = _env_example()
    source = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert env["OPENROUTER_API_KEY"] == ""
    assert env["OPENROUTER_SITE_URL"] == "http://127.0.0.1:8002"
    assert env["OPENROUTER_APP_NAME"] == "roompilot"

    assert env["ROOMPILOT_CATALOG_PROVIDER"] == "postgres"
    assert env["ROOMPILOT_RUNTIME_CATALOG_PROVIDER"] == "json"
    assert env["ROOMPILOT_PROJECT_STORE_PROVIDER"] == "sqlite"
    assert env["DB_HOST"] == "localhost"
    assert env["DB_PORT"] == "5432"
    assert env["DB_NAME"] == "roompilot_db"
    assert env["DB_ADMIN_DB"] == "postgres"
    assert env["DB_USER"] == "postgres"
    assert env["DB_PASSWORD"] == ""
    assert env["DB_SSLMODE"] == "disable"
    assert env["PGSSLROOTCERT"] == ""
    assert env["DB_CONNECT_TIMEOUT"] == "10"
    assert env["DB_APPLICATION_NAME"] == "roompilot_local"

    assert "方案 A：組員本機 PostgreSQL（預設啟用）" in source
    assert "方案 B：AWS RDS 雲端 PostgreSQL（選用，預設全部註解）" in source
    assert "# DB_HOST=roompilot-postgres-prod.REPLACE_ME.ap-east-2.rds.amazonaws.com" in source
    assert "# DB_USER=roompilot_api" in source
    assert "# DB_PASSWORD=" in source
    assert "# DB_SSLMODE=verify-full" in source
    assert "# PGSSLROOTCERT=C:/Users/REPLACE_ME/RoomPilot-Agent/certs/global-bundle.pem" in source


def test_postgres_runtime_config_passes_the_rds_ca_bundle(
    tmp_path: Path, monkeypatch
) -> None:
    keys = (
        "DB_HOST",
        "DB_PORT",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD",
        "DB_SSLMODE",
        "PGSSLROOTCERT",
        "DB_CONNECT_TIMEOUT",
        "DB_APPLICATION_NAME",
    )
    for key in keys:
        monkeypatch.delenv(key, raising=False)

    ca_path = tmp_path / "global-bundle.pem"
    (tmp_path / ".env").write_text(
        "\n".join(
            (
                "DB_HOST=roompilot.example.rds.amazonaws.com",
                "DB_PORT=5432",
                "DB_NAME=roompilot_db",
                "DB_USER=roompilot_api",
                "DB_PASSWORD=secret",
                "DB_SSLMODE=verify-full",
                f"PGSSLROOTCERT={ca_path.as_posix()}",
                "DB_CONNECT_TIMEOUT=15",
                "DB_APPLICATION_NAME=roompilot_api",
            )
        ),
        encoding="utf-8",
    )

    assert postgres_repository._database_config(tmp_path) == {
        "host": "roompilot.example.rds.amazonaws.com",
        "port": 5432,
        "dbname": "roompilot_db",
        "user": "roompilot_api",
        "password": "secret",
        "connect_timeout": 15,
        "sslmode": "verify-full",
        "sslrootcert": ca_path.as_posix(),
        "application_name": "roompilot_api",
    }
