from __future__ import annotations

import hashlib

import numpy as np
from backend.floorplan.vision import cody_semantic
from backend.floorplan.vision.cody_semantic import (
    cody_semantic_room_labeler_status,
    ensure_cody_semantic_masks,
    ensure_cody_semantic_weights,
    load_cody_semantic_mask,
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
    _write_room_mask(cache_dir / "floor15_mask.npz")

    status = cody_semantic_room_labeler_status(root=tmp_path, env={})

    assert status["available"] is True
    assert status["reason"] == "cody_semantic_ready"
    assert status["cache_count"] == 1


def test_cody_semantic_room_labeler_ignores_invalid_cache(tmp_path) -> None:
    cache_dir = tmp_path / "cubicasa" / "room"
    cache_dir.mkdir(parents=True)
    (cache_dir / "floor15_mask.npz").write_bytes(b"placeholder")

    status = cody_semantic_room_labeler_status(root=tmp_path, env={})

    assert status["available"] is False
    assert status["reason"] == "missing_cody_cubicasa_weights_or_cache"
    assert status["cache_count"] == 0


def _fake_retrieve(payload: bytes):
    def retrieve(_url, destination):
        destination.write_bytes(payload)

    return retrieve


def _write_room_mask(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    room = np.array([[3, 4], [5, 6]], dtype=np.uint8)
    icon = np.array([[0, 1], [2, 0]], dtype=np.uint8)
    wall = room == 2
    window = icon == 1
    door = icon == 2
    np.savez_compressed(
        path,
        wall=wall,
        window=window,
        door=door,
        room=room,
        icon=icon,
    )


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


def test_cody_semantic_masks_reuse_existing_cache_without_runner(tmp_path) -> None:
    image = tmp_path / "uploads" / "plan.png"
    image.parent.mkdir()
    image.write_bytes(b"image")
    _write_room_mask(tmp_path / "cubicasa" / "room" / "plan_mask.npz")

    result = ensure_cody_semantic_masks(
        [image],
        root=tmp_path,
        env={},
        runner=lambda _command: (_ for _ in ()).throw(AssertionError("should not infer")),
    )

    assert result["ok"] is True
    assert result["reason"] == "semantic_masks_cached"
    assert result["generated"] == []


def test_cody_semantic_mask_loader_validates_cody_fields(tmp_path) -> None:
    mask = tmp_path / "cubicasa" / "room" / "plan_mask.npz"
    _write_room_mask(mask)

    result = load_cody_semantic_mask(mask)

    assert result["shape"] == (2, 2)
    assert result["arrays"]["room"].dtype == np.uint8
    assert result["arrays"]["icon"].dtype == np.uint8
    assert result["arrays"]["window"].dtype == bool
    assert result["arrays"]["door"].dtype == bool


def test_cody_semantic_masks_reject_incomplete_cache(tmp_path) -> None:
    image = tmp_path / "uploads" / "plan.png"
    image.parent.mkdir()
    image.write_bytes(b"image")
    cache = tmp_path / "cubicasa" / "room" / "plan_mask.npz"
    cache.parent.mkdir(parents=True)
    np.savez_compressed(cache, room=np.zeros((2, 2), dtype=np.uint8))
    monkeypatch_error = AssertionError("should not infer without weights")

    result = ensure_cody_semantic_masks(
        [image],
        root=tmp_path,
        env={"CC_WEIGHTS": "missing.pkl"},
        runner=lambda _command: (_ for _ in ()).throw(monkeypatch_error),
    )

    assert result["ok"] is False
    assert result["reason"] == "custom_weights_missing"


def test_cody_semantic_mask_loader_rejects_shape_mismatch(tmp_path) -> None:
    mask = tmp_path / "bad_mask.npz"
    np.savez_compressed(
        mask,
        wall=np.zeros((2, 2), dtype=bool),
        window=np.zeros((2, 2), dtype=bool),
        door=np.zeros((2, 2), dtype=bool),
        room=np.zeros((2, 3), dtype=np.uint8),
        icon=np.zeros((2, 2), dtype=np.uint8),
    )

    try:
        load_cody_semantic_mask(mask)
    except ValueError as exc:
        assert "inconsistent shapes" in str(exc)
    else:
        raise AssertionError("shape mismatch should fail")


def test_cody_semantic_masks_fail_clearly_without_inference_script(tmp_path) -> None:
    weights = tmp_path / "training" / "model_finetuned_v5.pkl"
    weights.parent.mkdir()
    weights.write_bytes(b"weights")
    image = tmp_path / "uploads" / "plan.png"
    image.parent.mkdir()
    image.write_bytes(b"image")

    result = ensure_cody_semantic_masks([image], root=tmp_path, env={})

    assert result["ok"] is False
    assert result["reason"] == "inference_script_missing"
    assert result["script_path"].endswith(
        "backend\\floorplan\\infer_cubicasa.py"
    ) or result["script_path"].endswith("backend/floorplan/infer_cubicasa.py")


def test_cody_semantic_masks_runner_generates_missing_cache(tmp_path) -> None:
    weights = tmp_path / "training" / "model_finetuned_v5.pkl"
    weights.parent.mkdir()
    weights.write_bytes(b"weights")
    script = tmp_path / "backend" / "floorplan" / "infer_cubicasa.py"
    script.parent.mkdir(parents=True)
    script.write_text("# fake cody inference script\n", encoding="utf-8")
    image = tmp_path / "uploads" / "plan.png"
    image.parent.mkdir()
    image.write_bytes(b"image")
    commands = []

    def fake_runner(command):
        commands.append(command)
        cache_dir = tmp_path / "cubicasa" / "room"
        _write_room_mask(cache_dir / "plan_mask.npz")

    result = ensure_cody_semantic_masks([image], root=tmp_path, env={}, runner=fake_runner)

    assert result["ok"] is True
    assert result["reason"] == "semantic_masks_generated"
    assert len(commands) == 1
    assert commands[0][2] == str(weights)
    assert commands[0][3].endswith("cubicasa\\room") or commands[0][3].endswith(
        "cubicasa/room"
    )
    assert result["generated"] == [str(tmp_path / "cubicasa" / "room" / "plan_mask.npz")]


def test_cody_semantic_masks_do_not_infer_when_weights_are_missing(tmp_path, monkeypatch) -> None:
    image = tmp_path / "uploads" / "plan.png"
    image.parent.mkdir()
    image.write_bytes(b"image")
    monkeypatch.setattr(cody_semantic, "_resolve_weights_url", lambda _env: None)

    result = ensure_cody_semantic_masks(
        [image],
        root=tmp_path,
        env={},
        runner=lambda _command: (_ for _ in ()).throw(AssertionError("should not infer")),
    )

    assert result["ok"] is False
    assert result["reason"] == "weights_download_unavailable"
