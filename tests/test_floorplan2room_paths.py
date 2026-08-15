"""辨識期資產的預設路徑必須脫離 current working directory。

原本這支測的是 `CC_WEIGHTS` 與 `CC_CACHE_DIR`：兩者曾是相對字串，靠「從 repo 根
執行」這個隱含前提才會對，從 `backend/floorplan/` 執行時會各自疊成
`backend/floorplan/backend/floorplan/…`，權重與語意快取同時查不到。

2026-07-30 CubiCasa 血統整批移除後那兩個常數不再存在，但**失效模式沒有消失，只是
換了主角**。DINOv2 路徑同樣有兩個由模組位置推導的資產路徑：

* `room_classifier.HEAD_PATH` → `.runtime/floorplan/room_head.npz`
* `symbol_match.LIB_PATH` → `.runtime/floorplan/symbol_lib.npz`

兩者的共同危險在於**找不到檔不會報錯**——`_load()` 與 `load_lib()` 都回 None，
房型退回面積規則、模板比對停用。公開 repository 不附來源未證實的訓練產物，
所以這裡釘住絕對 runtime 路徑、缺件降級，以及環境變數覆寫。
"""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_DIR = REPO_ROOT / "backend" / "floorplan"
RUNTIME_MODEL_DIR = REPO_ROOT / ".runtime" / "floorplan"


@pytest.fixture(scope="module")
def room_classifier():
    return importlib.import_module("backend.floorplan.room_classifier")


@pytest.fixture(scope="module")
def symbol_match():
    return importlib.import_module("backend.floorplan.symbol_match")


def test_room_head_anchors_to_runtime_directory(room_classifier) -> None:
    """未附授權模型時只解析到忽略版控的 runtime 目錄。"""
    head = Path(room_classifier.HEAD_PATH)

    assert head.is_absolute(), "HEAD_PATH 預設值必須是絕對路徑"
    assert head == RUNTIME_MODEL_DIR / "room_head.npz"


def test_missing_room_head_disables_optional_semantics(room_classifier) -> None:
    """portable clone 沒有本地線性頭時必須安全降級。"""
    head = Path(room_classifier.HEAD_PATH)

    assert not head.is_file()
    room_classifier._state = "unloaded"
    assert room_classifier.available() is False


def test_symbol_lib_anchors_to_runtime_directory(symbol_match) -> None:
    """模板庫預設只從忽略版控的 runtime 目錄讀取。"""
    lib = Path(symbol_match.LIB_PATH)

    assert lib.is_absolute(), "LIB_PATH 預設值必須是絕對路徑"
    assert lib == RUNTIME_MODEL_DIR / "symbol_lib.npz"


def test_missing_symbol_library_is_an_explicit_safe_fallback(symbol_match) -> None:
    """portable clone 無模板庫時回 None，不製造假辨識結果。"""
    lib = Path(symbol_match.LIB_PATH)
    assert not lib.is_file()

    symbol_match._lib_cache = "unloaded"
    loaded = symbol_match.load_lib()
    assert loaded is None


def test_defaults_resolve_identically_when_run_from_the_package_directory() -> None:
    """回歸測試：從 backend/floorplan/ 執行不得再疊出第二層 backend/floorplan/。"""
    probe = textwrap.dedent(
        """
        import json
        from backend.floorplan import room_classifier, symbol_match

        print(json.dumps({
            "head": room_classifier.HEAD_PATH,
            "lib": symbol_match.LIB_PATH,
        }))
        """
    )
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    env.pop("ROOM_HEAD", None)

    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=PIPELINE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr

    resolved = json.loads(result.stdout.strip().splitlines()[-1])
    assert Path(resolved["head"]) == RUNTIME_MODEL_DIR / "room_head.npz"
    assert Path(resolved["lib"]) == RUNTIME_MODEL_DIR / "symbol_lib.npz"


def test_room_head_environment_override_still_wins(tmp_path: Path) -> None:
    """`ROOM_HEAD` 覆蓋機制是 A/B 驗收的入口，錨定不得吃掉它。"""
    probe = textwrap.dedent(
        """
        import json
        from backend.floorplan import room_classifier

        print(json.dumps({"head": room_classifier.HEAD_PATH}))
        """
    )
    custom_head = tmp_path / "ab_head.npz"
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT),
        "ROOM_HEAD": str(custom_head),
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

    resolved = json.loads(result.stdout.strip().splitlines()[-1])
    assert Path(resolved["head"]) == custom_head
