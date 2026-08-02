"""登入失敗節流：擋掉單機暴力嘗試。

行程內記憶體實作，多 worker 部署時每個 worker 各自計數，因此這是「提高成本」
而不是嚴格上限。真正的邊界應該由反向代理或 WAF 提供；這裡的目的是讓單一
uvicorn 節點不會被一支腳本無限次嘗試。
"""

from __future__ import annotations

from collections import deque
from threading import Lock
from time import monotonic


DEFAULT_MAX_ATTEMPTS = 8
DEFAULT_WINDOW_SECONDS = 300.0


class LoginThrottle:
    def __init__(
        self,
        *,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._failures: dict[str, deque[float]] = {}
        self._lock = Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        attempts = self._failures.setdefault(key, deque())
        while attempts and now - attempts[0] > self.window_seconds:
            attempts.popleft()
        return attempts

    def retry_after_seconds(self, key: str) -> float | None:
        """仍在鎖定中則回剩餘秒數，否則 None。"""
        now = monotonic()
        with self._lock:
            attempts = self._prune(key, now)
            if len(attempts) < self.max_attempts:
                return None
            return max(0.0, self.window_seconds - (now - attempts[0]))

    def record_failure(self, key: str) -> None:
        now = monotonic()
        with self._lock:
            self._prune(key, now).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
