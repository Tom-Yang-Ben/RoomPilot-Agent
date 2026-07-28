"""cody 管線模組的可載入性冒煙測試。

`docs/CODY_MAIN_SYNC_TODO.md` 第 2 點要求預設入口改走 floorplan2room，前置是把
cody 分支的四個管線模組與兩份設定檔搬進 backend/floorplan/。搬入當下還沒有任何
產品程式碼 import 它們（入口切換另案處理），所以需要這支測試守住兩件事：

1. 四個模組能以「套件成員」方式 import——cody 端是以腳本執行，模組內用扁平
   import 取兄弟模組，靠 floorplan2room.py 頂端的 sys.path.insert 生效。若日後
   有人清掉那段，這裡會立刻紅。
2. 兩份 .ini 設定檔存在且能被 configparser 解析——floorplan2room 的黑白與彩色
   兩條管線都以它們為預設參數來源。
"""
from __future__ import annotations

import configparser
import importlib
from pathlib import Path

import pytest

PIPELINE_DIR = Path(__file__).resolve().parents[1] / "backend" / "floorplan"

MODULES = (
    "backend.floorplan.floorplan2room",
    "backend.floorplan.floorplan2dxf_color",
    "backend.floorplan.symbol_match",
    "backend.floorplan.apply_cubicasa_patches",
)

CONFIGS = ("config.ini", "config_color.ini")


@pytest.mark.parametrize("module_name", MODULES)
def test_pipeline_module_imports_as_package_member(module_name: str) -> None:
    assert importlib.import_module(module_name) is not None


@pytest.mark.parametrize("config_name", CONFIGS)
def test_pipeline_config_is_present_and_parsable(config_name: str) -> None:
    path = PIPELINE_DIR / config_name
    assert path.is_file()

    parser = configparser.ConfigParser(inline_comment_prefixes=(";", "#"))
    parser.read(path, encoding="utf-8")
    assert parser.sections()


def test_floorplan2room_exposes_the_entry_points_the_adapter_will_need() -> None:
    """入口切換（TODO 第 2 點）會用到的公開函式，先鎖住名稱避免上游改名無聲失聯。"""
    module = importlib.import_module("backend.floorplan.floorplan2room")

    for name in ("process", "build_rooms", "ensure_cc_masks", "classify_rooms_cc"):
        assert callable(getattr(module, name, None)), f"floorplan2room 缺少 {name}"
