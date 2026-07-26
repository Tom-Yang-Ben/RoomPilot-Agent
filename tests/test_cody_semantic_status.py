from __future__ import annotations

from backend.floorplan.vision.cody_semantic import cody_semantic_room_labeler_status


def test_cody_semantic_room_labeler_reports_fallback_without_assets(tmp_path) -> None:
    status = cody_semantic_room_labeler_status(root=tmp_path, env={})

    assert status["available"] is False
    assert status["reason"] == "missing_cody_cubicasa_weights_or_cache"
    assert status["model_version"] == "cody_cubicasa_v5"
    assert status["weights_path"].endswith("training\\model_finetuned_v5.pkl") or status[
        "weights_path"
    ].endswith("training/model_finetuned_v5.pkl")
    assert status["weights_sha256"].startswith("b7a280d2")
    assert status["fallback"] == "django_icon_zone_rules"
    assert status["weights_present"] is False
    assert status["cache_count"] == 0


def test_cody_semantic_room_labeler_can_use_precomputed_cache(tmp_path) -> None:
    cache_dir = tmp_path / "cubicasa" / "room"
    cache_dir.mkdir(parents=True)
    (cache_dir / "floor15_mask.npz").write_bytes(b"placeholder")

    status = cody_semantic_room_labeler_status(root=tmp_path, env={})

    assert status["available"] is True
    assert status["reason"] == "cody_semantic_ready"
    assert status["cache_count"] == 1
