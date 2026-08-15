"""Thread-safe, lazy, offline-only BGE-M3 model runtime."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from threading import Lock
from typing import Any

from .errors import RagDependencyError
from .settings import RagSettings


EMBED_MODEL = "BAAI/bge-m3"
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
EMBED_DIMENSION = 1024


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
        _, reranker = self._load(settings)
        with self._inference_lock:
            scores = reranker.predict(pairs)
        return [float(score) for score in scores]


MODEL_RUNTIME = RagModelRuntime()
