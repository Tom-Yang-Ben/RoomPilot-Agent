"""End-to-end LLM parser -> PostgreSQL pgvector -> Django reranker service."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Any, Callable

from ...catalog import rag_repository
from ...catalog.postgres_repository import get_catalog_items_by_ids
from .errors import (
    RagDatabaseError,
    RagDependencyError,
    RagDisabledError,
    RagError,
)
from .model_runtime import EMBED_MODEL, MODEL_RUNTIME, RERANK_MODEL, RagModelRuntime
from .models import RagQueryItem, RagQueryPlan, RagSearchRequest
from .openai_parser import ParsedQuery
from .parser import parse_query
from .ranking import (
    RERANK_TOP_K,
    RERANK_TOP_K_LIGHT,
    VEC_TOP_K,
    allocate_budget,
    build_filters,
    rank_candidates,
)
from .settings import RagSettings, load_rag_settings
from .vocab import load_vocab


Parser = Callable[[str, RagSettings], ParsedQuery]
CatalogLoader = Callable[[Path, list[str]], dict[str, dict[str, Any]]]
ProgressReporter = Callable[[int, str, str], None]


class FurnitureRagService:
    def __init__(
        self,
        project_dir: Path,
        *,
        parser: Parser = parse_query,
        model_runtime: RagModelRuntime = MODEL_RUNTIME,
        repository: Any = rag_repository,
        catalog_loader: CatalogLoader = get_catalog_items_by_ids,
    ) -> None:
        self.project_dir = project_dir
        self._parser = parser
        self._models = model_runtime
        self._repository = repository
        self._catalog_loader = catalog_loader
        self._price_stats: dict[str, dict[str, float]] | None = None
        self._price_stats_lock = Lock()

    def _settings(self) -> RagSettings:
        return load_rag_settings(self.project_dir)

    def status(self) -> dict[str, Any]:
        settings = self._settings()
        model_status = dict(self._models.status(settings))
        # The API reports cache readiness, not the server's local filesystem layout.
        model_status.pop("cache_dir", None)
        provider = settings.parser_provider
        provider_valid = provider in {"openai", "openrouter", "anthropic"}
        parser_package_name = "openai" if provider == "openrouter" else provider
        parser_package = (
            importlib.util.find_spec(parser_package_name) is not None
            if provider_valid
            else False
        )
        blockers: list[str] = []
        if not settings.enabled:
            blockers.append("feature_disabled")
        if not provider_valid:
            blockers.append("parser_provider_invalid")
        elif not settings.parser_api_key:
            blockers.append(f"{provider}_api_key_missing")
        if provider_valid and not parser_package:
            blockers.append(f"{provider}_package_missing")
        if not all(model_status["packages"].values()):
            blockers.append("rag_model_packages_missing")
        if not model_status["embedding_cached"]:
            blockers.append("embedding_model_cache_missing")
        if not model_status["reranker_cached"]:
            blockers.append("reranker_model_cache_missing")

        try:
            database = self._repository.embedding_status(self.project_dir)
            if database["current_embeddings"] <= 0:
                blockers.append("furniture_embeddings_empty")
            if not database["search_function_available"]:
                blockers.append("filtered_search_function_missing")
        except Exception:
            database = {
                "provider": "postgresql_pgvector",
                "embedding_model": EMBED_MODEL,
                "embedding_dimension": 0,
                "current_embeddings": 0,
                "search_function_available": False,
                "available": False,
            }
            blockers.append("postgresql_unavailable")
        else:
            database["available"] = True

        return {
            "schema_version": "roompilot.rag.status.v1",
            "enabled": settings.enabled,
            "ready": not blockers,
            "blockers": blockers,
            "parser": {
                "provider": provider,
                "model": settings.parser_model,
                "reasoning_effort": (
                    settings.parser_reasoning_effort
                    if provider in {"openai", "openrouter"}
                    else None
                ),
                "max_tokens": (
                    settings.anthropic_max_tokens if provider == "anthropic" else None
                ),
                "key_configured": bool(settings.parser_api_key),
                "package_available": parser_package,
            },
            "models": model_status,
            "database": database,
            "boundary": "retrieval_only_no_geometry_legality",
        }

    def _require_ready(self) -> tuple[RagSettings, dict[str, Any]]:
        settings = self._settings()
        if not settings.enabled:
            raise RagDisabledError("ROOMPILOT_RAG_ENABLED is false")
        status = self.status()
        if status["blockers"]:
            if status["blockers"] == ["feature_disabled"]:
                raise RagDisabledError("ROOMPILOT_RAG_ENABLED is false")
            raise RagDependencyError(
                "RAG prerequisites are unavailable: " + ", ".join(status["blockers"])
            )
        return settings, status

    def _load_price_stats(self, groups: dict[str, dict[str, Any]]) -> dict[str, dict[str, float]]:
        if self._price_stats is not None:
            return self._price_stats
        with self._price_stats_lock:
            if self._price_stats is None:
                try:
                    self._price_stats = self._repository.load_group_price_stats(
                        self.project_dir, groups
                    )
                except Exception as exc:
                    raise RagDatabaseError("PostgreSQL price statistics are unavailable") from exc
        return self._price_stats

    def _search_item(
        self,
        item: RagQueryItem,
        plan: RagQueryPlan,
        settings: RagSettings,
        allocated: dict[str, int],
        price_stats: dict[str, dict[str, float]],
        vocab: dict[str, Any],
        dominant_style: str | None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[float], list[dict[str, Any]]]:
        filters_dict = build_filters(
            item, plan, allocated, price_stats, vocab["groups"]
        )
        filters = self._repository.RagFilters.from_mapping(filters_dict)
        vector = self._models.embed([item.semantic_query], settings)[0]
        try:
            candidates = self._repository.search_embedding_candidates(
                self.project_dir,
                vector,
                filters,
                match_count=VEC_TOP_K,
                embedding_model=EMBED_MODEL,
            )
        except Exception as exc:
            raise RagDatabaseError("PostgreSQL vector search failed") from exc

        rerank_count = (
            RERANK_TOP_K_LIGHT if item.is_inferred or item.role == "accent" else RERANK_TOP_K
        )
        candidates = candidates[:rerank_count]
        raw_scores = self._models.rerank(
            item.semantic_query,
            [str(candidate.get("embedded_text") or "") for candidate in candidates],
            settings,
        )
        ranked = rank_candidates(
            item=item,
            plan=plan,
            candidates=candidates,
            rerank_scores=raw_scores,
            dominant_style=dominant_style,
            compatibility=vocab["style_compat"],
        )
        return filters.public_dict(), ranked, raw_scores, candidates

    @staticmethod
    def _report(
        reporter: ProgressReporter | None,
        percent: int,
        stage: str,
        message: str,
    ) -> None:
        if reporter is None:
            return
        try:
            reporter(max(0, min(100, int(percent))), stage, message)
        except Exception:
            # Progress reporting is observational and must never break retrieval.
            return

    def _search_items_batched(
        self,
        order: list[RagQueryItem],
        plan: RagQueryPlan,
        settings: RagSettings,
        allocated: dict[str, int],
        price_stats: dict[str, dict[str, float]],
        vocab: dict[str, Any],
        dominant_style: str | None,
        progress: ProgressReporter | None,
    ) -> dict[str, dict[str, Any]]:
        self._report(
            progress,
            28,
            "embedding",
            "載入 BGE-M3／reranker，並批次產生查詢向量。",
        )
        vectors = self._models.embed(
            [item.semantic_query for item in order], settings
        )
        self._report(progress, 43, "vector_search", "查詢向量完成，開始 SQL 篩選。")

        retrieved: list[tuple[RagQueryItem, dict[str, Any], list[dict[str, Any]]]] = []
        item_count = max(len(order), 1)
        for index, (item, vector) in enumerate(zip(order, vectors, strict=True)):
            filters_dict = build_filters(
                item, plan, allocated, price_stats, vocab["groups"]
            )
            filters = self._repository.RagFilters.from_mapping(filters_dict)
            try:
                candidates = self._repository.search_embedding_candidates(
                    self.project_dir,
                    vector,
                    filters,
                    match_count=VEC_TOP_K,
                    embedding_model=EMBED_MODEL,
                )
            except Exception as exc:
                raise RagDatabaseError("PostgreSQL vector search failed") from exc
            rerank_count = (
                RERANK_TOP_K_LIGHT
                if item.is_inferred or item.role == "accent"
                else RERANK_TOP_K
            )
            retrieved.append((item, filters.public_dict(), candidates[:rerank_count]))
            percent = 43 + round(15 * (index + 1) / item_count)
            self._report(
                progress,
                percent,
                "vector_search",
                f"PostgreSQL 已完成 {index + 1}/{item_count} 個品項的 top-50 檢索。",
            )

        pairs: list[tuple[str, str]] = []
        slices: list[tuple[int, int]] = []
        for item, _, candidates in retrieved:
            start = len(pairs)
            pairs.extend(
                (item.semantic_query, str(candidate.get("embedded_text") or ""))
                for candidate in candidates
            )
            slices.append((start, len(pairs)))

        self._report(
            progress,
            62,
            "reranking",
            f"批次 rerank {len(pairs)} 組查詢與家具證據。",
        )
        raw_score_batches: list[list[float]] = []
        if hasattr(self._models, "rerank_pairs"):
            all_scores = self._models.rerank_pairs(pairs, settings)
            raw_score_batches = [all_scores[start:end] for start, end in slices]
        else:
            raw_score_batches = [
                self._models.rerank(
                    item.semantic_query,
                    [str(candidate.get("embedded_text") or "") for candidate in candidates],
                    settings,
                )
                for item, _, candidates in retrieved
            ]

        results: dict[str, dict[str, Any]] = {}
        for item, filters, candidates, raw_scores in zip(
            (row[0] for row in retrieved),
            (row[1] for row in retrieved),
            (row[2] for row in retrieved),
            raw_score_batches,
            strict=True,
        ):
            ranked = rank_candidates(
                item=item,
                plan=plan,
                candidates=candidates,
                rerank_scores=raw_scores,
                dominant_style=dominant_style,
                compatibility=vocab["style_compat"],
            )
            results[item.item_id] = {
                "filters": filters,
                "ranked": ranked,
                "raw_scores": raw_scores,
                "candidates": candidates,
            }
        self._report(progress, 84, "reranking", "Django 分數融合與排序完成。")
        return results

    @staticmethod
    def _furniture_payload(
        candidate: dict[str, Any], catalog_item: dict[str, Any] | None
    ) -> dict[str, Any]:
        metadata = candidate.get("metadata") or {}
        catalog_item = catalog_item or {}
        previews = catalog_item.get("preview_images") or {}
        return {
            "item_id": candidate["item_id"],
            "name_zh": catalog_item.get("name_zh") or metadata.get("name_zh") or candidate["item_id"],
            "name_en": catalog_item.get("name_en") or "",
            "category": metadata.get("category") or catalog_item.get("category_label"),
            "normalized_type": catalog_item.get("normalized_type"),
            "price_twd": metadata.get("price_twd"),
            "price_is_estimated": bool(metadata.get("price_is_estimated", False)),
            "style_primary": metadata.get("style_primary"),
            "style_secondary": metadata.get("style_secondary"),
            "role": metadata.get("role"),
            "size_class": metadata.get("size_class"),
            "coordinate_unit": "cm",
            "width_cm": metadata.get("width_cm"),
            "depth_cm": metadata.get("depth_cm"),
            "height_cm": metadata.get("height_cm"),
            "image_url": catalog_item.get("image_url"),
            "preview_images": previews,
            "model_url": catalog_item.get("model_url"),
            "has_model": bool(catalog_item.get("has_model")),
        }

    def search(
        self,
        request: RagSearchRequest,
        progress: ProgressReporter | None = None,
    ) -> dict[str, Any]:
        started = perf_counter()
        self._report(progress, 3, "readiness", "確認 API、模型快取與 PostgreSQL。")
        settings, readiness = self._require_ready()
        ready_at = perf_counter()
        self._report(progress, 8, "parsing", "由 LLM 將自然語言解析為受控條件。")
        parsed = self._parser(request.query, settings)
        parsed_at = perf_counter()
        self._report(progress, 20, "planning", "查詢解析完成，計算品項與預算條件。")

        plan = parsed.plan
        vocab = load_vocab()
        price_stats = self._load_price_stats(vocab["groups"])
        allocated = allocate_budget(plan.items, plan.budget_total, price_stats)
        order = sorted(plan.items, key=lambda item: 0 if item.role == "anchor" else 1)
        dominant_style = str(plan.styles[0]) if plan.styles else None
        item_results = self._search_items_batched(
            order,
            plan,
            settings,
            allocated,
            price_stats,
            vocab,
            dominant_style,
            progress,
        )
        if not dominant_style and order:
            first_result = item_results[order[0].item_id]
            first_ranked = first_result["ranked"]
            if first_ranked:
                dominant_style = str(
                    (first_ranked[0].get("metadata") or {}).get("style_primary") or ""
                ) or None
                if dominant_style:
                    first_result["ranked"] = rank_candidates(
                        item=order[0],
                        plan=plan,
                        candidates=first_result["candidates"],
                        rerank_scores=first_result["raw_scores"],
                        dominant_style=dominant_style,
                        compatibility=vocab["style_compat"],
                    )
        retrieved_at = perf_counter()

        seen_ids: set[str] = set()
        seen_groups: set[str] = set()
        selected_by_item: list[tuple[RagQueryItem, dict[str, Any], list[dict[str, Any]]]] = []
        all_ids: list[str] = []
        for item in order:
            result = item_results[item.item_id]
            selected: list[dict[str, Any]] = []
            for candidate in result["ranked"]:
                item_id = str(candidate["item_id"])
                duplicate_group = str((candidate.get("metadata") or {}).get("duplicate_group") or "")
                if item_id in seen_ids or (duplicate_group and duplicate_group in seen_groups):
                    continue
                seen_ids.add(item_id)
                if duplicate_group:
                    seen_groups.add(duplicate_group)
                selected.append(candidate)
                all_ids.append(item_id)
                if len(selected) >= request.top_k:
                    break
            selected_by_item.append((item, result, selected))

        self._report(progress, 90, "hydrating", "讀取正式家具與 CloudFront 資產。")
        try:
            catalog = self._catalog_loader(self.project_dir, all_ids)
        except Exception as exc:
            raise RagDatabaseError("PostgreSQL catalog hydration failed") from exc

        blocks: list[dict[str, Any]] = []
        for item, result, selected in selected_by_item:
            hits = []
            for rank, candidate in enumerate(selected, start=1):
                item_id = str(candidate["item_id"])
                hits.append(
                    {
                        "rank": rank,
                        "furniture": self._furniture_payload(candidate, catalog.get(item_id)),
                        "scores": candidate["scores"],
                        "duplicate_group": (candidate.get("metadata") or {}).get("duplicate_group") or None,
                    }
                )
            blocks.append(
                {
                    "item_id": item.item_id,
                    "label_zh": item.label_zh,
                    "category_group": item.category_group,
                    "quantity": item.quantity,
                    "is_inferred": item.is_inferred,
                    "price_cap": allocated.get(item.item_id),
                    "filters": result["filters"],
                    "hits": hits,
                }
            )

        estimated_total = sum(
            int(block["hits"][0]["furniture"].get("price_twd") or 0) * int(block["quantity"])
            for block in blocks
            if block["hits"]
        )
        finished = perf_counter()
        self._report(progress, 98, "formatting", "整理分組結果與檢索證據。")
        style_zh = vocab["styles"].get(dominant_style or "", {}).get("zh", "")
        payload = {
            "schema_version": "roompilot.rag.search.v1",
            "query": request.query,
            "source": {
                "parser_provider": settings.parser_provider,
                "parser_model": settings.parser_model,
                "embedding_model": EMBED_MODEL,
                "reranker_model": RERANK_MODEL,
                "vector_store": "postgresql_pgvector",
                "current_embeddings": readiness["database"]["current_embeddings"],
            },
            "parsed_query": plan.model_dump(mode="json"),
            "parser_usage": parsed.usage,
            "clarification": {
                "needed": plan.needs_clarification,
                "question": plan.clarify_question,
                "options": plan.clarify_options,
            },
            "dominant_style": dominant_style,
            "style_zh": style_zh,
            "budget_total": plan.budget_total,
            "estimated_total": estimated_total,
            "blocks": blocks,
            "timings_ms": {
                "readiness": round((ready_at - started) * 1000, 1),
                "parse": round((parsed_at - ready_at) * 1000, 1),
                "retrieve_and_rerank": round((retrieved_at - parsed_at) * 1000, 1),
                "hydrate": round((finished - retrieved_at) * 1000, 1),
                "total": round((finished - started) * 1000, 1),
            },
            "boundary": "retrieval_only_no_geometry_legality",
        }
        self._report(progress, 100, "completed", "RAG 檢索完成。")
        return payload


__all__ = ["FurnitureRagService", "RagError"]
