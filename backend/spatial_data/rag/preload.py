"""bge-m3 的背景預載。

CPU 上第一次載入權重需要約 34 秒。若等到使用者送出問卷才載，第一個使用者
會盯著轉圈；若在啟動時同步載入，開發者每次 reload 都要多等半分鐘。所以用
背景執行緒在啟動後載入，並讓 API 能查詢就緒狀態——未就緒時檢索退成純結構化
過濾（``semantic=false``），需求指紋會標記為過期，模型就緒後下一次送出自動
補算語意排序。

``ROOMPILOT_RAG_PRELOAD=0`` 可停用；模型常駐約 2–4GB 記憶體，記憶體吃緊的
部署要自行評估。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from threading import Lock, Thread
from time import monotonic
from typing import Any

from .model_runtime import EMBED_MODEL, MODEL_RUNTIME, RagModelRuntime
from .settings import load_rag_settings


@dataclass
class PreloadState:
    status: str = "idle"  # idle | loading | ready | failed | disabled
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None

    def elapsed_seconds(self) -> float | None:
        if self.started_at is None:
            return None
        end = self.finished_at if self.finished_at is not None else monotonic()
        return round(end - self.started_at, 2)


class EmbeddingPreloader:
    def __init__(self, runtime: RagModelRuntime = MODEL_RUNTIME) -> None:
        self.runtime = runtime
        self._state = PreloadState()
        self._lock = Lock()
        self._thread: Thread | None = None

    @staticmethod
    def enabled() -> bool:
        return os.getenv("ROOMPILOT_RAG_PRELOAD", "1").strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            state = self._state
            return {
                "model": EMBED_MODEL,
                "status": state.status,
                "elapsed_seconds": state.elapsed_seconds(),
                "error": state.error,
                # ready 才代表檢索會帶語意排序；其餘狀態一律降級。
                "semantic_available": state.status == "ready",
            }

    def is_ready(self) -> bool:
        with self._lock:
            return self._state.status == "ready"

    def start(self, project_dir: Path) -> None:
        """啟動背景載入。重複呼叫安全，載入中或已完成時直接返回。"""
        if not self.enabled():
            with self._lock:
                self._state = PreloadState(status="disabled")
            return
        with self._lock:
            if self._state.status in {"loading", "ready"}:
                return
            self._state = PreloadState(status="loading", started_at=monotonic())
            thread = Thread(
                target=self._run,
                args=(project_dir,),
                name="roompilot-rag-preload",
                daemon=True,
            )
            self._thread = thread
        thread.start()

    def _run(self, project_dir: Path) -> None:
        try:
            settings = load_rag_settings(project_dir)
            # 實際編碼一次而不只是載入權重：第一次 forward 會觸發延遲初始化，
            # 只 load 的話那份成本會落到第一個真實請求上。
            self.runtime.embed(["預載暖機"], settings)
        except Exception as exc:  # noqa: BLE001 - 預載失敗只降級，不影響服務
            with self._lock:
                self._state.status = "failed"
                self._state.finished_at = monotonic()
                self._state.error = f"{type(exc).__name__}: {exc}"[:300]
            return
        with self._lock:
            self._state.status = "ready"
            self._state.finished_at = monotonic()
            self._state.error = None


PRELOADER = EmbeddingPreloader()
