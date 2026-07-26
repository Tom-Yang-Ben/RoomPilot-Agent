from __future__ import annotations

import hashlib

from backend.floorplan.vision import cody_semantic
from backend.floorplan.vision.cody_semantic import (
    cody_semantic_room_labeler_status,
    ensure_cody_semantic_weights,
)


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


def _fake_retrieve(payload: bytes):
    def retrieve(_url, destination):
        destination.write_bytes(payload)

    return retrieve


def test_cody_semantic_weights_existing_file_short_circuits(tmp_path, monkeypatch) -> None:
    weights = tmp_path / "training" / "model_finetuned_v5.pkl"
    weights.parent.mkdir()
    weights.write_bytes(b"weights")
    monkeypatch.setattr(
        cody_semantic.urllib.request,
        "urlretrieve",
        lambda *args: (_ for _ in ()).throw(AssertionError("should not download")),
    )

    result = ensure_cody_semantic_weights(root=tmp_path, env={})

    assert result["ok"] is True
    assert result["reason"] == "weights_present"
    assert result["downloaded"] is False


def test_cody_semantic_weights_custom_override_is_not_downloaded(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        cody_semantic.urllib.request,
        "urlretrieve",
        lambda *args: (_ for _ in ()).throw(AssertionError("custom weights should not download")),
    )

    result = ensure_cody_semantic_weights(
        root=tmp_path,
        env={"CC_WEIGHTS": "custom.pkl"},
    )

    assert result["ok"] is False
    assert result["reason"] == "custom_weights_missing"
    assert not (tmp_path / "custom.pkl").exists()


def test_cody_semantic_weights_checksum_mismatch_is_rejected(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cody_semantic, "_resolve_weights_url", lambda _env: "https://fake/weights")
    monkeypatch.setattr(
        cody_semantic.urllib.request,
        "urlretrieve",
        _fake_retrieve(b"tampered"),
    )
    monkeypatch.setattr(
        cody_semantic,
        "CODY_V5_WEIGHTS_SHA256",
        hashlib.sha256(b"expected").hexdigest(),
    )

    result = ensure_cody_semantic_weights(root=tmp_path, env={})

    weights = tmp_path / "training" / "model_finetuned_v5.pkl"
    assert result["ok"] is False
    assert result["reason"] == "weights_checksum_mismatch"
    assert not weights.exists()
    assert not weights.with_name(weights.name + ".part").exists()


def test_cody_semantic_weights_download_success(tmp_path, monkeypatch) -> None:
    payload = b"good weights"
    monkeypatch.setattr(cody_semantic, "_resolve_weights_url", lambda _env: "https://fake/weights")
    monkeypatch.setattr(
        cody_semantic.urllib.request,
        "urlretrieve",
        _fake_retrieve(payload),
    )
    monkeypatch.setattr(
        cody_semantic,
        "CODY_V5_WEIGHTS_SHA256",
        hashlib.sha256(payload).hexdigest(),
    )

    result = ensure_cody_semantic_weights(root=tmp_path, env={})

    weights = tmp_path / "training" / "model_finetuned_v5.pkl"
    assert result["ok"] is True
    assert result["reason"] == "weights_downloaded"
    assert weights.read_bytes() == payload
    assert not weights.with_name(weights.name + ".part").exists()


def test_cody_semantic_weights_no_download_channel_is_clear_failure(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cody_semantic, "_resolve_weights_url", lambda _env: None)

    result = ensure_cody_semantic_weights(root=tmp_path, env={})

    assert result["ok"] is False
    assert result["reason"] == "weights_download_unavailable"
