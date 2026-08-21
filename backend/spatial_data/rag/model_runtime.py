"""Thread-safe, lazy, offline-only BGE-M3 model runtime."""

from __future__ import annotations

import importlib.util
import json
import os
import urllib.request
from pathlib import Path
from threading import Lock
from typing import Any

from .errors import RagDependencyError
from .settings import RagSettings


EMBED_MODEL = "BAAI/bge-m3"
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
EMBED_DIMENSION = 1024

REMOTE_URL_ENV = "ROOMPILOT_RAG_REMOTE_URL"
REMOTE_TIMEOUT_ENV = "ROOMPILOT_RAG_REMOTE_TIMEOUT_SECONDS"


def _remote_url() -> str:
    """把 embed/rerank 外包給 sidecar 的位址；空字串＝維持行程內載入。

    刻意只讀行程環境、不讀 `.env`：這是容器編排（docker-compose）設定的部署
    拓樸，不是使用者的模型偏好。若走 `settings.py` 的 `_setting`，`.env` 檔會
    蓋掉 compose 的值（那支是檔案優先），本機一份殘留設定就能讓 web 以為有
    sidecar 可用。
    """
    return os.getenv(REMOTE_URL_ENV, "").strip().rstrip("/")


def _remote_call(path: str, payload: dict[str, Any] | None) -> Any:
    url = f"{_remote_url()}{path}"
    timeout = float(os.getenv(REMOTE_TIMEOUT_ENV, "120"))
    # 與 backend/agent/llm.py 一致用 stdlib urllib：業務程式碼不 import httpx。
    request = urllib.request.Request(
        url,
        data=None if payload is None else json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - sidecar 任何失敗都是「依賴不可用」
        raise RagDependencyError(f"RAG sidecar unavailable at {url}") from exc


def _repo_cache_path(cache_dir: Path, repo_id: str) -> Path:
    return cache_dir / f"models--{repo_id.replace('/', '--')}"


def _repo_is_cached(cache_dir: Path, repo_id: str) -> bool:
    candidates = (
        _repo_cache_path(cache_dir, repo_id),
        cache_dir / "hub" / f"models--{repo_id.replace('/', '--')}",
        cache_dir / repo_id.split("/", 1)[-1],
    )
    for candidate in candidates:
        if (candidate / "config.json").is_file():
            return True
        snapshots = candidate / "snapshots"
        if snapshots.is_dir() and any(
            (path / "config.json").is_file()
            for path in snapshots.iterdir()
            if path.is_dir()
        ):
            return True
    return False


def model_cache_status(cache_dir: Path) -> dict[str, Any]:
    return {
        "cache_dir": str(cache_dir),
        "embedding_cached": _repo_is_cached(cache_dir, EMBED_MODEL),
        "reranker_cached": _repo_is_cached(cache_dir, RERANK_MODEL),
    }


def _sentence_transformers_cache_dir(cache_dir: Path) -> Path:
    """Resolve the same Hub directory used by the cache readiness check."""
    hub_dir = cache_dir / "hub"
    return hub_dir if hub_dir.is_dir() else cache_dir


class RagModelRuntime:
    def __init__(self) -> None:
        self._load_lock = Lock()
        self._inference_lock = Lock()
        self._models: tuple[Any, Any] | None = None
        self._load_key: tuple[str, str] | None = None
        self._device: str | None = None

    def status(self, settings: RagSettings) -> dict[str, Any]:
        if _remote_url():
            # 狀態頁不該因為 sidecar 沒起來就整頁爆掉，回報「不可用」即可。
            try:
                remote = dict(_remote_call("/status", None))
            except RagDependencyError as exc:
                remote = {"packages": {}, "loaded": False, "error": str(exc)}
            remote["remote_url"] = _remote_url()
            return remote

        packages = {
            name: importlib.util.find_spec(module) is not None
            for name, module in (
                ("torch", "torch"),
                ("sentence_transformers", "sentence_transformers"),
            )
        }
        cache = model_cache_status(settings.model_cache_dir)
        return {
            "embedding_model": EMBED_MODEL,
            "embedding_dimension": EMBED_DIMENSION,
            "reranker_model": RERANK_MODEL,
            "packages": packages,
            **cache,
            "loaded": self._models is not None,
            "device": self._device or settings.model_device,
        }

    @staticmethod
    def _resolve_device(requested: str, torch: Any) -> str:
        if requested not in {"auto", "cpu", "cuda", "mps"}:
            raise RagDependencyError(f"unsupported RAG model device: {requested}")
        if requested != "auto":
            return requested
        if torch.cuda.is_available():
            return "cuda"
        mps = getattr(getattr(torch, "backends", None), "mps", None)
        if mps is not None and mps.is_available():
            return "mps"
        return "cpu"

    def _load(self, settings: RagSettings) -> tuple[Any, Any]:
        key = (str(settings.model_cache_dir.resolve()), settings.model_device)
        if self._models is not None and self._load_key == key:
            return self._models

        status = self.status(settings)
        if not all(status["packages"].values()):
            raise RagDependencyError("RAG model packages are not installed")
        if not status["embedding_cached"] or not status["reranker_cached"]:
            raise RagDependencyError("RAG model weights are not cached")

        with self._load_lock:
            if self._models is not None and self._load_key == key:
                return self._models
            try:
                import torch
                from sentence_transformers import CrossEncoder, SentenceTransformer

                device = self._resolve_device(settings.model_device, torch)
                cache_folder = str(_sentence_transformers_cache_dir(settings.model_cache_dir))
                embedder = SentenceTransformer(
                    EMBED_MODEL,
                    device=device,
                    cache_folder=cache_folder,
                    local_files_only=True,
                )
                reranker = CrossEncoder(
                    RERANK_MODEL,
                    device=device,
                    max_length=512,
                    cache_folder=cache_folder,
                    local_files_only=True,
                )
                embedder.max_seq_length = 512
            except Exception as exc:
                raise RagDependencyError("RAG model weights could not be loaded") from exc
            self._models = (embedder, reranker)
            self._load_key = key
            self._device = device
            return self._models

    def embed(self, texts: list[str], settings: RagSettings) -> list[list[float]]:
        # 與同類的 rerank／rerank_pairs 一致先擋空輸入。少了這道，空清單會為了
        # 算零個向量而去載 4.6GB 模型（遠端模式則是一次沒有意義的 HTTP 往返）。
        if not texts:
            return []
        if _remote_url():
            return list(_remote_call("/embed", {"texts": texts})["vectors"])
        embedder, _ = self._load(settings)
        with self._inference_lock:
            vectors = embedder.encode(texts, normalize_embeddings=True)
        return [vector.tolist() if hasattr(vector, "tolist") else list(vector) for vector in vectors]

    def rerank(
        self,
        query: str,
        documents: list[str],
        settings: RagSettings,
    ) -> list[float]:
        if not documents:
            return []
        if _remote_url():
            return self.rerank_pairs([(query, document) for document in documents], settings)
        _, reranker = self._load(settings)
        with self._inference_lock:
            scores = reranker.predict([(query, document) for document in documents])
        return [float(score) for score in scores]

    def rerank_pairs(
        self,
        pairs: list[tuple[str, str]],
        settings: RagSettings,
    ) -> list[float]:
        if not pairs:
            return []
        if _remote_url():
            payload = {"pairs": [list(pair) for pair in pairs]}
            return [float(score) for score in _remote_call("/rerank", payload)["scores"]]
        _, reranker = self._load(settings)
        with self._inference_lock:
            scores = reranker.predict(pairs)
        return [float(score) for score in scores]


MODEL_RUNTIME = RagModelRuntime()
