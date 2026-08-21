"""BGE-M3 sidecar：把 torch + sentence-transformers 關進自己的容器。

web 容器不裝 torch（2.5GB）。RAG 需要向量或重排時，
``backend/spatial_data/rag/model_runtime.py`` 會依 ``ROOMPILOT_RAG_REMOTE_URL``
改打這裡的 HTTP，而不是在本地載模型。沒設那個環境變數時，
web 仍走原本的行程內載入路徑，行為與 Docker 之前完全一樣。

這支只是薄薄的 HTTP 外殼：真正的模型生命週期、執行緒鎖與快取檢查
仍然由 ``RagModelRuntime`` 擁有，本檔不重做任何一項。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.spatial_data.rag.errors import RagDependencyError
from backend.spatial_data.rag.model_runtime import MODEL_RUNTIME
from backend.spatial_data.rag.settings import load_rag_settings

PROJECT_DIR = Path(__file__).resolve().parents[1]

app = FastAPI(title="RoomPilot RAG sidecar")


def _settings():
    return load_rag_settings(PROJECT_DIR)


class EmbedRequest(BaseModel):
    texts: list[str]


class RerankRequest(BaseModel):
    pairs: list[tuple[str, str]]


@app.get("/status")
def status() -> dict:
    return MODEL_RUNTIME.status(_settings())


@app.post("/embed")
def embed(body: EmbedRequest) -> dict:
    try:
        return {"vectors": MODEL_RUNTIME.embed(body.texts, _settings())}
    except RagDependencyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/rerank")
def rerank(body: RerankRequest) -> dict:
    try:
        return {"scores": MODEL_RUNTIME.rerank_pairs(list(body.pairs), _settings())}
    except RagDependencyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
