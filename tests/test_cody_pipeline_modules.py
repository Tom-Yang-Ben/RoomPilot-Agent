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
    # 2026-07-30 CubiCasa 血統移除：apply_cubicasa_patches 與 infer_cubicasa
    # 一併刪除（前者是上游程式庫的 numpy 2.x 補丁，後者是遮罩推論腳本），
    # 房型命名層改由 room_classifier 的 DINOv2 裁切分類承擔。
    "backend.floorplan.room_classifier",
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
    """cody_adapter 會用到的公開函式，鎖住名稱避免上游改名無聲失聯。

    2026-07-30 起 `ensure_cc_masks`／`classify_rooms_cc` 隨 CubiCasa 一併移除，
    改鎖 DINOv2 路徑實際踩到的四個進入點。`detect_room_text`／`detect_text_boxes`
    特別重要——adapter 必須在 `detect_symbols` 之前呼叫它們，順序反了不會報錯、
    只會讓文字抑制與 OCR 證據層靜默失效。
    """
    module = importlib.import_module("backend.floorplan.floorplan2room")

    for name in ("process", "build_rooms", "detect_symbols",
                 "detect_room_text", "detect_text_boxes"):
        assert callable(getattr(module, name, None)), f"floorplan2room 缺少 {name}"
