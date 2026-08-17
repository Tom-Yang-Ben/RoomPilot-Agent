from __future__ import annotations

from pathlib import Path


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

    assert env["ROOMPILOT_PROFILE"] == "portable"
    assert env["ROOMPILOT_CATALOG_PROVIDER"] == ""
    assert env["ROOMPILOT_CATALOG_VISIBILITY"] == "public"
    assert env["ROOMPILOT_HOST"] == "127.0.0.1"
    assert env["OPENROUTER_API_KEY"] == ""
    assert env["OPENROUTER_SITE_URL"] == "http://127.0.0.1:8002"
    assert env["OPENROUTER_APP_NAME"] == "roompilot"

    assert env["DB_HOST"] == "127.0.0.1"
    assert env["DB_PORT"] == "5432"
    assert env["DB_NAME"] == "roompilot_db"
    assert env["DB_USER"] == "roompilot"
    assert env["DB_PASSWORD"] == ""
    assert env["DB_SSLMODE"] == "disable"
    assert env["DB_CONNECT_TIMEOUT"] == "10"
    assert env["DB_APPLICATION_NAME"] == "roompilot_catalog"
