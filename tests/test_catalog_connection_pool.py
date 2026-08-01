"""連線池在滿載時排隊而不是立刻 503（QA 2026-08-01 BLOCKER #2）。

psycopg2 的 ``ThreadedConnectionPool.getconn()`` 在池滿時直接丟 PoolError，
所以舊版第 DB_POOL_MAX+1 個併發請求就會 503（含 /api/health），而且訊息
被翻譯成「請先執行匯入流程」，把瞬時滿載說成型錄沒匯入。
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from backend.catalog import postgres_repository as repo


class _FakeConnection:
    def __init__(self) -> None:
        self.autocommit = False
        self.closed = False

    def rollback(self) -> None:  # pragma: no cover - 只在例外路徑用到
        pass


class _FakePool:
    """複製 psycopg2 的關鍵行為：借滿之後 getconn() 立刻丟例外。"""

    def __init__(self, minimum: int, maximum: int, **_config: object) -> None:
        self.maximum = maximum
        self.lock = threading.Lock()
        self.borrowed = 0
        self.peak = 0
        self.exhausted_calls = 0

    def getconn(self) -> _FakeConnection:
        with self.lock:
            if self.borrowed >= self.maximum:
                self.exhausted_calls += 1
                raise RuntimeError("connection pool exhausted")
            self.borrowed += 1
            self.peak = max(self.peak, self.borrowed)
        return _FakeConnection()

    def putconn(self, _connection: _FakeConnection, close: bool = False) -> None:
        with self.lock:
            self.borrowed -= 1

    def closeall(self) -> None:  # pragma: no cover - 測試不走關閉路徑
        pass


@pytest.fixture
def fake_pool(monkeypatch: pytest.MonkeyPatch):
    """把真實 psycopg2 池換成假的，並確保測試前後池表乾淨。"""
    import psycopg2.pool

    created: list[_FakePool] = []

    def factory(minimum: int, maximum: int, **config: object) -> _FakePool:
        pool = _FakePool(minimum, maximum, **config)
        created.append(pool)
        return pool

    monkeypatch.setattr(psycopg2.pool, "ThreadedConnectionPool", factory)
    monkeypatch.setattr(repo, "_POOLS", {})
    yield created
    repo._POOLS.clear()


def _borrow_for(project_dir: Path, hold: threading.Event, done: list[str]) -> None:
    with repo._borrow_connection(project_dir):
        hold.wait(timeout=5)
    done.append("ok")


def test_requests_beyond_pool_max_queue_instead_of_failing(
    monkeypatch: pytest.MonkeyPatch, fake_pool: list[_FakePool], tmp_path: Path
) -> None:
    monkeypatch.setenv("DB_POOL_MAX", "2")
    monkeypatch.setenv("DB_POOL_MIN", "1")
    monkeypatch.setenv("DB_POOL_TIMEOUT", "5")

    hold = threading.Event()
    done: list[str] = []
    threads = [
        threading.Thread(target=_borrow_for, args=(tmp_path, hold, done))
        for _ in range(6)
    ]
    for thread in threads:
        thread.start()
    hold.set()
    for thread in threads:
        thread.join(timeout=10)

    assert done == ["ok"] * 6
    pool = fake_pool[0]
    # 號誌把併發壓在上限內，所以底層池從來沒被借爆。
    assert pool.peak <= 2
    assert pool.exhausted_calls == 0


def test_pool_timeout_is_reported_as_busy_not_as_missing_import(
    monkeypatch: pytest.MonkeyPatch, fake_pool: list[_FakePool], tmp_path: Path
) -> None:
    monkeypatch.setenv("DB_POOL_MAX", "1")
    monkeypatch.setenv("DB_POOL_MIN", "1")
    monkeypatch.setenv("DB_POOL_TIMEOUT", "0.2")

    with repo._borrow_connection(tmp_path):
        with pytest.raises(repo.CatalogPoolTimeout) as caught:
            with repo._borrow_connection(tmp_path):
                pass  # pragma: no cover - 借不到就進不來

    assert "DB_POOL_MAX" in str(caught.value)


def test_permit_is_released_when_the_body_raises(
    monkeypatch: pytest.MonkeyPatch, fake_pool: list[_FakePool], tmp_path: Path
) -> None:
    """借用區塊丟例外時號誌必須歸還，否則池會被慢慢漏光。"""
    monkeypatch.setenv("DB_POOL_MAX", "1")
    monkeypatch.setenv("DB_POOL_MIN", "1")
    monkeypatch.setenv("DB_POOL_TIMEOUT", "0.2")

    for _ in range(3):
        with pytest.raises(ValueError):
            with repo._borrow_connection(tmp_path):
                raise ValueError("boom")

    with repo._borrow_connection(tmp_path) as connection:
        assert connection is not None
