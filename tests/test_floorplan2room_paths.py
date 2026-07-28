"""floorplan2room 預設路徑必須脫離 current working directory。

`CC_WEIGHTS` 與 `CC_CACHE_DIR` 原本是相對字串，靠「從 repo 根執行」這個隱含前提
才會對。實測從 `backend/floorplan/` 執行時，兩者各自疊成
`backend/floorplan/backend/floorplan/model_finetuned_v5.pkl` 與
`backend/floorplan/cubicasa/room/`，權重與 137 份語意快取同時查不到，語意辨識
靜默退回面積規則、還會多觸發一次 200MB 下載嘗試。

cody_adapter 走 HTTP 請求路徑時同樣吃這兩個常數（`_cc_path`），伺服器 cwd 不保證
是 repo 根，所以錨定基準改成模組自身位置：權重在 `backend/floorplan/`、快取維持
repo 根的 `cubicasa/room/`（`.gitignore` 與 CODY_MAIN_SYNC_TODO 標明是跨分支契約
路徑，不可搬進套件目錄）。
"""
from __future__ import annotations

import hashlib
import importlib
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import urllib.request

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_DIR = REPO_ROOT / "backend" / "floorplan"


@pytest.fixture(scope="module")
def room_module():
    return importlib.import_module("backend.floorplan.floorplan2room")


def test_default_weights_anchor_to_the_package_directory(room_module) -> None:
    """權重與 floorplan2room.py 同層，路徑由模組位置推導而非 cwd。"""
    weights = Path(room_module.CC_WEIGHTS)

    assert weights.is_absolute(), "CC_WEIGHTS 預設值必須是絕對路徑"
    assert weights == PIPELINE_DIR / "model_finetuned_v5.pkl"


def test_default_cache_dir_stays_at_the_repo_root_contract_path(room_module) -> None:
    """`cubicasa/room/` 是跨分支契約路徑，錨定後位置不得改變。"""
    cache_dir = Path(room_module.CC_CACHE_DIR)

    assert cache_dir.is_absolute(), "CC_CACHE_DIR 預設值必須是絕對路徑"
    assert cache_dir == REPO_ROOT / "cubicasa" / "room"


def test_defaults_resolve_identically_when_run_from_the_package_directory() -> None:
    """回歸測試：從 backend/floorplan/ 執行不得再疊出第二層 backend/floorplan/。"""
    probe = textwrap.dedent(
        """
        import json
        from backend.floorplan import floorplan2room as room

        print(json.dumps({
            "weights": room.CC_WEIGHTS,
            "cache_dir": room.CC_CACHE_DIR,
        }))
        """
    )
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    env.pop("CC_WEIGHTS", None)
    env.pop("CC_CACHE_DIR", None)

    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=PIPELINE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr

    import json

    resolved = json.loads(result.stdout.strip().splitlines()[-1])
    assert Path(resolved["weights"]) == PIPELINE_DIR / "model_finetuned_v5.pkl"
    assert Path(resolved["cache_dir"]) == REPO_ROOT / "cubicasa" / "room"


def test_environment_overrides_still_win(tmp_path: Path) -> None:
    """CC_WEIGHTS / CC_CACHE_DIR 覆蓋機制是跨分支契約，錨定不得吃掉它。"""
    probe = textwrap.dedent(
        """
        import json
        from backend.floorplan import floorplan2room as room

        print(json.dumps({
            "weights": room.CC_WEIGHTS,
            "cache_dir": room.CC_CACHE_DIR,
        }))
        """
    )
    custom_weights = tmp_path / "ab_test.pkl"
    custom_cache = tmp_path / "masks"
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT),
        "CC_WEIGHTS": str(custom_weights),
        "CC_CACHE_DIR": str(custom_cache),
    }

    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=PIPELINE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr

    import json

    resolved = json.loads(result.stdout.strip().splitlines()[-1])
    assert Path(resolved["weights"]) == custom_weights
    assert Path(resolved["cache_dir"]) == custom_cache


def test_weights_download_creates_the_destination_directory(
    room_module, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """下載前要先建目錄，否則 200MB 抓完才在寫檔時炸掉。

    `vision/cody_semantic.py:201` 早就有 `weights.parent.mkdir`，這裡是漏掉的
    對應實作。
    """
    payload = b"fake-weights-payload"
    target = tmp_path / "missing" / "nested" / "model_finetuned_v5.pkl"
    assert not target.parent.exists()

    monkeypatch.delenv("CC_WEIGHTS", raising=False)
    monkeypatch.setattr(room_module, "CC_WEIGHTS", str(target))
    monkeypatch.setattr(
        room_module, "CC_WEIGHTS_SHA256", hashlib.sha256(payload).hexdigest()
    )
    monkeypatch.setattr(room_module, "_resolve_weights_url", lambda: "https://example/w")

    def _fake_retrieve(url: str, filename: str):
        Path(filename).write_bytes(payload)
        return filename, None

    monkeypatch.setattr(urllib.request, "urlretrieve", _fake_retrieve)

    assert room_module._ensure_cc_weights() is True
    assert target.is_file()
    assert target.read_bytes() == payload
    assert not target.with_name(target.name + ".part").exists()
