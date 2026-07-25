"""_ensure_cc_weights 權重自動下載測試：快取命中、使用者覆寫、校驗失敗、成功落地。"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import floorplan2room as fp


def _fake_retrieve(payload):
    def retrieve(url, dst):
        with open(dst, "wb") as f:
            f.write(payload)
    return retrieve


def test_existing_file_short_circuits(tmp_path, monkeypatch):
    w = tmp_path / "w.pkl"
    w.write_bytes(b"weights")
    monkeypatch.setattr(fp, "CC_WEIGHTS", str(w))
    monkeypatch.setattr(fp.urllib.request, "urlretrieve",
                        lambda *a: (_ for _ in ()).throw(AssertionError("不應下載")))
    assert fp._ensure_cc_weights() is True


def test_user_override_never_downloads(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_WEIGHTS", str(tmp_path / "custom.pkl"))
    monkeypatch.setattr(fp, "CC_WEIGHTS", str(tmp_path / "custom.pkl"))
    monkeypatch.setattr(fp.urllib.request, "urlretrieve",
                        lambda *a: (_ for _ in ()).throw(AssertionError("覆寫權重缺失不代抓")))
    assert fp._ensure_cc_weights() is False


def test_checksum_mismatch_rejected(tmp_path, monkeypatch):
    w = tmp_path / "w.pkl"
    monkeypatch.delenv("CC_WEIGHTS", raising=False)
    monkeypatch.setattr(fp, "CC_WEIGHTS", str(w))
    monkeypatch.setattr(fp, "CC_WEIGHTS_SHA256", hashlib.sha256(b"expected").hexdigest())
    monkeypatch.setattr(fp, "_resolve_weights_url", lambda: "https://fake/w.pkl")
    monkeypatch.setattr(fp.urllib.request, "urlretrieve", _fake_retrieve(b"tampered"))
    assert fp._ensure_cc_weights() is False
    assert not w.exists()
    assert not (tmp_path / "w.pkl.part").exists()


def test_download_success(tmp_path, monkeypatch):
    w = tmp_path / "w.pkl"
    payload = b"good weights"
    monkeypatch.delenv("CC_WEIGHTS", raising=False)
    monkeypatch.setattr(fp, "CC_WEIGHTS", str(w))
    monkeypatch.setattr(fp, "CC_WEIGHTS_SHA256", hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr(fp, "_resolve_weights_url", lambda: "https://fake/w.pkl")
    monkeypatch.setattr(fp.urllib.request, "urlretrieve", _fake_retrieve(payload))
    assert fp._ensure_cc_weights() is True
    assert w.read_bytes() == payload
    assert not (tmp_path / "w.pkl.part").exists()


def test_download_error_cleans_up(tmp_path, monkeypatch):
    w = tmp_path / "w.pkl"
    monkeypatch.delenv("CC_WEIGHTS", raising=False)
    monkeypatch.setattr(fp, "CC_WEIGHTS", str(w))
    monkeypatch.setattr(fp, "_resolve_weights_url", lambda: "https://fake/w.pkl")

    def boom(url, dst):
        with open(dst, "wb") as f:
            f.write(b"partial")
        raise OSError("網路中斷")

    monkeypatch.setattr(fp.urllib.request, "urlretrieve", boom)
    assert fp._ensure_cc_weights() is False
    assert not (tmp_path / "w.pkl.part").exists()


def test_no_channel_returns_false(tmp_path, monkeypatch):
    """私有 repo 且無 token：明確失敗，不嘗試下載。"""
    w = tmp_path / "w.pkl"
    monkeypatch.delenv("CC_WEIGHTS", raising=False)
    monkeypatch.setattr(fp, "CC_WEIGHTS", str(w))
    monkeypatch.setattr(fp, "_resolve_weights_url", lambda: None)
    monkeypatch.setattr(fp.urllib.request, "urlretrieve",
                        lambda *a: (_ for _ in ()).throw(AssertionError("無管道不應下載")))
    assert fp._ensure_cc_weights() is False


def test_gh_token_env_priority(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tok-env")
    assert fp._gh_token() == "tok-env"
