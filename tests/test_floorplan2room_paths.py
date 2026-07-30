"""辨識期資產的預設路徑必須脫離 current working directory。

原本這支測的是 `CC_WEIGHTS` 與 `CC_CACHE_DIR`：兩者曾是相對字串，靠「從 repo 根
執行」這個隱含前提才會對，從 `backend/floorplan/` 執行時會各自疊成
`backend/floorplan/backend/floorplan/…`，權重與語意快取同時查不到。

2026-07-30 CubiCasa 血統整批移除後那兩個常數不再存在，但**失效模式沒有消失，只是
換了主角**。DINOv2 路徑同樣有兩個由模組位置推導的資產路徑：

* `room_classifier.HEAD_PATH` → `backend/floorplan/room_head.npz`（15KB 線性頭）
* `symbol_match.LIB_PATH` → `backend/floorplan/symbol_lib.npz`（943 條模板庫）

兩者的共同危險在於**找不到檔不會報錯**——`_load()` 與 `load_lib()` 都回 None，
房型靜默退回面積規則、模板比對靜默停用，只有評測分數悄悄掉下來。cody_adapter 走
HTTP 請求路徑時伺服器 cwd 不保證是 repo 根，所以這裡把「絕對路徑 ＋ 錨定在套件
目錄 ＋ 檔案真的在」三件事一起釘住。
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


@pytest.fixture(scope="module")
def room_classifier():
    return importlib.import_module("backend.floorplan.room_classifier")


@pytest.fixture(scope="module")
def symbol_match():
    return importlib.import_module("backend.floorplan.symbol_match")


def test_room_head_anchors_to_the_package_directory(room_classifier) -> None:
    """線性頭與 room_classifier.py 同層，路徑由模組位置推導而非 cwd。"""
    head = Path(room_classifier.HEAD_PATH)

    assert head.is_absolute(), "HEAD_PATH 預設值必須是絕對路徑"
    assert head == PIPELINE_DIR / "room_head.npz"


def test_room_head_file_actually_exists(room_classifier) -> None:
    """缺檔時 DINOv2 分類靜默停用（只印警告），故以測試釘住檔案真的在版控裡。"""
    head = Path(room_classifier.HEAD_PATH)

    assert head.is_file(), f"線性頭不在 {head}——房型會靜默退回面積規則"


def test_symbol_lib_anchors_to_the_package_directory(symbol_match) -> None:
    """模板庫與消費它的 symbol_match.py 同目錄（2026-07-29 由 repo 根移入）。

    舊寫法由模組位置往上三層推導，只搬 `backend/floorplan/` 而不保持整個 repo
    目錄結構就會解析到錯路徑——這正是 MAIN_SYNC_TODO 第 9 點記載的失效模式。
    """
    lib = Path(symbol_match.LIB_PATH)

    assert lib.is_absolute(), "LIB_PATH 預設值必須是絕對路徑"
    assert lib == PIPELINE_DIR / "symbol_lib.npz"


def test_symbol_lib_loads_into_a_non_empty_library(symbol_match) -> None:
    """`load_lib()` 找不到檔時回 None、`match_symbols()` 回空清單，不報錯。"""
    lib = Path(symbol_match.LIB_PATH)
    assert lib.is_file(), f"模板庫不在 {lib}——模板比對會靜默停用"

    loaded = symbol_match.load_lib()
    assert loaded is not None
    assert len(loaded["rasters"]) > 0


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
    assert Path(resolved["head"]) == PIPELINE_DIR / "room_head.npz"
    assert Path(resolved["lib"]) == PIPELINE_DIR / "symbol_lib.npz"


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
