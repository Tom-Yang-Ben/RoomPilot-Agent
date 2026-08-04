from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from backend.spatial_data.rag.anthropic_parser import parse_query as parse_anthropic_query
from backend.spatial_data.rag.errors import RagDependencyError, RagUpstreamError
from backend.spatial_data.rag.models import RagQueryItem, RagQueryPlan, RagSearchRequest
from backend.spatial_data.rag.openai_parser import ParsedQuery, parse_query
from backend.spatial_data.rag.parser import parse_query as parse_configured_query
from backend.spatial_data.rag.preload import EmbeddingPreloader
from backend.spatial_data.rag.ranking import (
    allocate_budget,
    build_filters,
    mood_score,
    normalize_rerank_score,
    rank_candidates,
    style_score,
)
from backend.spatial_data.rag.service import FurnitureRagService
from backend.spatial_data.rag.settings import RagSettings, load_rag_settings
from backend.spatial_data.rag.vocab import load_vocab


def _settings(
    tmp_path: Path,
    *,
    api_key: str = "server-secret",
    provider: str = "openai",
) -> RagSettings:
    return RagSettings(
        enabled=True,
        parser_provider=provider,
        openai_api_key=api_key if provider == "openai" else "",
        anthropic_api_key=api_key if provider == "anthropic" else "",
        parser_model=(
            "claude-sonnet-4-6" if provider == "anthropic" else "gpt-5.6-sol"
        ),
        parser_reasoning_effort="low",
        parser_timeout_seconds=10,
        anthropic_max_tokens=4096,
        model_cache_dir=tmp_path / "models",
        model_device="cpu",
    )


def _item(
    item_id: str = "sofa",
    *,
    category_group: str | None = "sofa",
    role: str | None = "anchor",
    inferred: bool = False,
) -> RagQueryItem:
    return RagQueryItem(
        item_id=item_id,
        label_zh="沙發",
        category_group=category_group,
        quantity=1,
        priority="must_have",
        is_inferred=inferred,
        semantic_query="現代簡約米色布面沙發，線條俐落並帶有溫馨放鬆氛圍",
        styles=["modern_minimal"],
        price_max=None,
        max_width_cm=None,
        max_height_cm=None,
        role=role,
        size_hint=None,
    )


def _plan(*, items: list[RagQueryItem] | None = None) -> RagQueryPlan:
    return RagQueryPlan(
        room_type="living_room",
        styles=["modern_minimal"],
        moods=["溫馨"],
        pattern=None,
        color_hint="米色",
        material_hint="布",
        price_level=None,
        budget_total=35_000,
        is_set=False,
        items=items or [_item()],
        confidence=0.9,
        needs_clarification=False,
        clarify_question=None,
        clarify_options=[],
        reasoning="使用者明確要求客廳沙發。",
    )


def test_controlled_schema_preserves_nulls_and_rejects_unknown_values() -> None:
    item = _item(category_group=None, role=None)
    plan = _plan(items=[item])

    assert item.category_group is None
    assert item.max_width_cm is None
    assert plan.pattern is None

    with pytest.raises(ValidationError):
        RagQueryItem.model_validate(
            {**_item().model_dump(), "category_group": "appliance"}
        )
    with pytest.raises(ValidationError, match="clarify_question"):
        RagQueryPlan.model_validate(
            {**plan.model_dump(), "needs_clarification": True, "clarify_question": None}
        )


@pytest.mark.parametrize(
    ("provider", "key_name", "model_name"),
    [
        ("openai", "OPENAI_API_KEY", "gpt-5.6-sol"),
        ("anthropic", "ANTHROPIC_API_KEY", "claude-sonnet-4-6"),
    ],
)
def test_settings_select_only_the_configured_rag_parser(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    key_name: str,
    model_name: str,
) -> None:
    monkeypatch.setenv("ROOMPILOT_RAG_PARSER_PROVIDER", provider)
    monkeypatch.setenv(key_name, "selected-secret")
    monkeypatch.setenv("ROOMPILOT_RAG_PARSER_MODEL", "")

    settings = load_rag_settings(tmp_path)

    assert settings.parser_provider == provider
    assert settings.parser_api_key == "selected-secret"
    assert settings.parser_model == model_name


def test_preloader_does_not_load_models_when_rag_is_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    embed_calls: list[object] = []
    runtime = SimpleNamespace(embed=lambda *args: embed_calls.append(args))
    monkeypatch.setenv("ROOMPILOT_RAG_ENABLED", "false")
    monkeypatch.setenv("ROOMPILOT_RAG_PRELOAD", "1")

    preloader = EmbeddingPreloader(runtime=runtime)
    preloader.start(tmp_path)

    assert preloader.status()["status"] == "disabled"
    assert preloader.status()["semantic_available"] is False
    assert embed_calls == []


def test_budget_filters_and_django_score_formula() -> None:
    item = _item()
    plan = _plan()
    stats = {"sofa": {"p33": 9_000, "median": 20_000, "p67": 32_000}}
    allocated = allocate_budget(plan.items, plan.budget_total, stats)
    vocab = load_vocab()

    assert allocated == {"sofa": 45_500}
    filters = build_filters(item, plan, allocated, stats, vocab["groups"])
    assert filters["room_type"] == "living_room"
    assert filters["price_max"] == 45_500
    assert "沙發" in filters["categories"]

    metadata = {
        "style_primary": "modern_minimal",
        "style_secondary": "scandinavian",
        "moods_flat": "溫馨|放鬆",
        "confidence": 0.9,
    }
    assert style_score(metadata, ["modern_minimal"], vocab["style_compat"]) == 1
    assert mood_score(metadata, ["溫馨"]) == 1
    assert normalize_rerank_score(0.95) == 0.95
    ranked = rank_candidates(
        item=item,
        plan=plan,
        candidates=[{"item_id": "A", "metadata": metadata, "cosine_similarity": 0.8}],
        rerank_scores=[0.95],
        dominant_style="modern_minimal",
        compatibility=vocab["style_compat"],
    )
    assert ranked[0]["scores"]["final"] == 0.96


class _FakeResponses:
    def __init__(self, response: object | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.kwargs: dict[str, object] = {}

    def parse(self, **kwargs: object) -> object:
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response


class _FakeMessages(_FakeResponses):
    pass


def test_openai_parser_uses_structured_outputs_without_fallback(tmp_path: Path) -> None:
    response = SimpleNamespace(
        output_parsed=_plan(),
        usage=SimpleNamespace(input_tokens=10, output_tokens=20, total_tokens=30),
    )
    responses = _FakeResponses(response=response)
    parsed = parse_query(
        "想找米色現代沙發",
        _settings(tmp_path),
        client=SimpleNamespace(responses=responses),
    )

    assert parsed.plan.room_type == "living_room"
    assert parsed.usage == {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}
    assert responses.kwargs["model"] == "gpt-5.6-sol"
    assert responses.kwargs["text_format"] is RagQueryPlan
    assert responses.kwargs["reasoning"] == {"effort": "low"}
    assert responses.kwargs["store"] is False
    assert "server-secret" not in str(responses.kwargs)

    with pytest.raises(RagDependencyError, match="OPENAI_API_KEY"):
        parse_query("沙發", _settings(tmp_path, api_key=""), client=object())
    with pytest.raises(RagUpstreamError, match="failed"):
        parse_query(
            "沙發",
            _settings(tmp_path),
            client=SimpleNamespace(responses=_FakeResponses(error=TimeoutError())),
        )


def test_anthropic_parser_uses_structured_outputs_without_fallback(tmp_path: Path) -> None:
    response = SimpleNamespace(
        parsed_output=_plan(),
        stop_reason="end_turn",
        usage=SimpleNamespace(input_tokens=11, output_tokens=22),
    )
    messages = _FakeMessages(response=response)
    settings = _settings(tmp_path, provider="anthropic")
    parsed = parse_anthropic_query(
        "modern living room sofa",
        settings,
        client=SimpleNamespace(messages=messages),
    )

    assert parsed.plan.room_type == "living_room"
    assert parsed.usage == {"input_tokens": 11, "output_tokens": 22, "total_tokens": 33}
    assert messages.kwargs["model"] == "claude-sonnet-4-6"
    assert messages.kwargs["output_format"] is RagQueryPlan
    assert messages.kwargs["max_tokens"] == 4096
    assert "server-secret" not in str(messages.kwargs)

    with pytest.raises(RagDependencyError, match="ANTHROPIC_API_KEY"):
        parse_anthropic_query(
            "sofa",
            _settings(tmp_path, api_key="", provider="anthropic"),
            client=object(),
        )
    with pytest.raises(RagUpstreamError, match="failed"):
        parse_anthropic_query(
            "sofa",
            settings,
            client=SimpleNamespace(messages=_FakeMessages(error=TimeoutError())),
        )
    with pytest.raises(RagUpstreamError, match="refusal"):
        parse_anthropic_query(
            "sofa",
            settings,
            client=SimpleNamespace(
                messages=_FakeMessages(
                    response=SimpleNamespace(stop_reason="refusal", parsed_output=None)
                )
            ),
        )


def test_configured_parser_rejects_unknown_provider(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    invalid = RagSettings(**{**settings.__dict__, "parser_provider": "other"})
    with pytest.raises(RagDependencyError, match="must be openai or anthropic"):
        parse_configured_query("sofa", invalid, client=object())
    with pytest.raises(RagUpstreamError, match="refusal"):
        parse_query(
            "沙發",
            _settings(tmp_path),
            client=SimpleNamespace(
                responses=_FakeResponses(response=SimpleNamespace(output_parsed=None))
            ),
        )


class _FakeModels:
    def __init__(self) -> None:
        self.embed_batches: list[list[str]] = []
        self.rerank_pair_batches: list[list[tuple[str, str]]] = []

    def embed(self, texts: list[str], settings: RagSettings) -> list[list[float]]:
        assert texts
        self.embed_batches.append(list(texts))
        return [[1.0, 0.0] for _ in texts]

    def rerank(
        self, query: str, documents: list[str], settings: RagSettings
    ) -> list[float]:
        return [0.95 - index * 0.05 for index, _ in enumerate(documents)]

    def rerank_pairs(
        self, pairs: list[tuple[str, str]], settings: RagSettings
    ) -> list[float]:
        self.rerank_pair_batches.append(list(pairs))
        return [0.95 - index * 0.05 for index, _ in enumerate(pairs)]


class _FakeRepository:
    class RagFilters:
        from_mapping = staticmethod(
            __import__(
                "backend.catalog.rag_repository", fromlist=["RagFilters"]
            ).RagFilters.from_mapping
        )

    @staticmethod
    def load_group_price_stats(project_dir: Path, groups: dict) -> dict:
        return {"sofa": {"p33": 10_000, "median": 20_000, "p67": 30_000}}

    @staticmethod
    def search_embedding_candidates(
        project_dir: Path,
        vector: list[float],
        filters: object,
        *,
        match_count: int,
        embedding_model: str,
    ) -> list[dict]:
        assert match_count == 50
        return [
            {
                "item_id": "SOFA-1",
                "embedded_text": "米色現代沙發",
                "metadata": {
                    "category": "沙發",
                    "price_twd": 18_000,
                    "width_cm": 180,
                    "depth_cm": 85,
                    "height_cm": 75,
                    "style_primary": "modern_minimal",
                    "moods_flat": "溫馨",
                    "confidence": 0.9,
                    "duplicate_group": "SOFA-GROUP-1",
                },
                "cosine_distance": 0.1,
                "cosine_similarity": 0.9,
            },
            {
                "item_id": "SOFA-1-DUP",
                "embedded_text": "同款米色現代沙發",
                "metadata": {
                    "category": "沙發",
                    "price_twd": 19_000,
                    "style_primary": "modern_minimal",
                    "moods_flat": "溫馨",
                    "confidence": 0.8,
                    "duplicate_group": "SOFA-GROUP-1",
                },
                "cosine_distance": 0.2,
                "cosine_similarity": 0.8,
            },
        ]


class _CountingModels(_FakeModels):
    def __init__(self) -> None:
        super().__init__()
        self.document_counts: list[int] = []

    def rerank(
        self, query: str, documents: list[str], settings: RagSettings
    ) -> list[float]:
        self.document_counts.append(len(documents))
        return super().rerank(query, documents, settings)


class _FiftyCandidateRepository(_FakeRepository):
    @staticmethod
    def search_embedding_candidates(
        project_dir: Path,
        vector: list[float],
        filters: object,
        *,
        match_count: int,
        embedding_model: str,
    ) -> list[dict]:
        assert match_count == 50
        return [
            {
                "item_id": f"ITEM-{index:02d}",
                "embedded_text": f"candidate {index}",
                "metadata": {"confidence": 0.8},
                "cosine_distance": index / 100,
                "cosine_similarity": 1 - index / 100,
            }
            for index in range(50)
        ]


def test_service_reranks_top_20_or_12_by_item_role(tmp_path: Path) -> None:
    models = _CountingModels()
    service = FurnitureRagService(
        tmp_path,
        model_runtime=models,
        repository=_FiftyCandidateRepository,
    )
    settings = _settings(tmp_path)
    vocab = load_vocab()
    price_stats = {"sofa": {"p33": 10_000, "median": 20_000, "p67": 30_000}}

    normal = _item(item_id="normal", role="anchor")
    service._search_item(
        normal,
        _plan(items=[normal]),
        settings,
        {"normal": 30_000},
        price_stats,
        vocab,
        "modern_minimal",
    )
    accent = _item(item_id="accent", role="accent", inferred=True)
    service._search_item(
        accent,
        _plan(items=[accent]),
        settings,
        {"accent": 30_000},
        price_stats,
        vocab,
        "modern_minimal",
    )

    assert models.document_counts == [20, 12]


def test_service_groups_hydrates_and_deduplicates_results(tmp_path: Path) -> None:
    plan = _plan(
        items=[
            _item(),
            _item(item_id="accent_sofa", role="accent", inferred=True),
        ]
    )
    settings = _settings(tmp_path)

    def parser(text: str, parser_settings: RagSettings) -> ParsedQuery:
        return ParsedQuery(plan=plan, usage={"input_tokens": 1, "output_tokens": 2, "total_tokens": 3})

    def catalog_loader(project_dir: Path, item_ids: list[str]) -> dict[str, dict]:
        return {
            "SOFA-1": {
                "name_zh": "測試沙發",
                "name_en": "Test sofa",
                "image_url": "https://cdn.example.com/sofa.jpg",
                "model_url": "https://cdn.example.com/sofa.glb",
                "has_model": True,
                "preview_images": {},
            }
        }

    models = _FakeModels()
    service = FurnitureRagService(
        tmp_path,
        parser=parser,
        model_runtime=models,
        repository=_FakeRepository,
        catalog_loader=catalog_loader,
    )
    service._require_ready = lambda: (
        settings,
        {"database": {"current_embeddings": 7_958}},
    )

    progress_updates: list[tuple[int, str, str]] = []
    payload = service.search(
        RagSearchRequest(query="想找米色現代沙發", top_k=8),
        progress=lambda percent, stage, message: progress_updates.append(
            (percent, stage, message)
        ),
    )

    assert payload["schema_version"] == "roompilot.rag.search.v1"
    assert payload["source"]["vector_store"] == "postgresql_pgvector"
    assert payload["source"]["current_embeddings"] == 7_958
    assert payload["boundary"] == "retrieval_only_no_geometry_legality"
    assert len(payload["blocks"][0]["hits"]) == 1
    furniture = payload["blocks"][0]["hits"][0]["furniture"]
    assert furniture["item_id"] == "SOFA-1"
    assert furniture["coordinate_unit"] == "cm"
    assert furniture["image_url"].startswith("https://")
    assert payload["blocks"][1]["hits"] == []
    assert len(models.embed_batches) == 1
    assert len(models.embed_batches[0]) == 2
    assert len(models.rerank_pair_batches) == 1
    assert len(models.rerank_pair_batches[0]) == 4
    assert [percent for percent, _, _ in progress_updates] == sorted(
        percent for percent, _, _ in progress_updates
    )
    assert progress_updates[-1][:2] == (100, "completed")
    assert {stage for _, stage, _ in progress_updates} >= {
        "embedding",
        "vector_search",
        "reranking",
        "hydrating",
    }

    def assert_private_fields_absent(value: object) -> None:
        if isinstance(value, dict):
            assert "embedding" not in value
            assert "openai_api_key" not in value
            for child in value.values():
                assert_private_fields_absent(child)
        elif isinstance(value, list):
            for child in value:
                assert_private_fields_absent(child)

    assert_private_fields_absent(payload)
