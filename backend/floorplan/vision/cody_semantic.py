"""房型語意標註層的可用性檢查（DINOv2 路徑）。

Bella 的 Django 式 icon／zone 規則不需要任何模型檔就能跑，所以這個模組的職責是
**誠實回報語意層能不能動**，讓產品在資產缺失時穩定退回 fallback，而不是在請求
路徑上炸掉。

2026-07-30 起本模組改指 DINOv2：房型命名層已由 CubiCasa 語意投票換成凍結
DINOv2 ViT-S/14 ＋ 線性頭（own_eval 72 房保留集 79.2% → 90.3%）。隨之消失的是
整套 CubiCasa 資產管理——200MB v5 權重、GitHub Release 下載鏈與 token 交換、
`cubicasa/room/*_mask.npz` 遮罩快取、`infer_cubicasa.py` subprocess 推論。
DINOv2 的判定條件簡單得多，故本模組由 368 行縮到現在的規模：

* 線性頭 `backend/floorplan/room_head.npz`（15KB，進版控，clone 即得）
* `torch`（CPU 版即可，只推論不訓練）
* DINOv2 骨幹 88MB，`torch.hub` 首次下載後快取於 `~/.cache/torch/hub/`

授權上這也是本次改動的重點：DINOv2 程式碼與權重皆 Apache 2.0 可商用，v2.15 就
記載的「CubiCasa5k 權重 CC BY-NC 禁商用」硬閘至此解除。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping


DEFAULT_HEAD = Path("backend/floorplan/room_head.npz")
BACKBONE_CACHE_HINT = Path("~/.cache/torch/hub")
MODEL_VERSION = "cody_dinov2_room_head_v1"


def _head_path(
    *,
    root: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> Path:
    """線性頭實際路徑。`ROOM_HEAD` 環境變數可覆寫（A/B 驗收用）。

    `root` 只在測試裡指定；產品走 repo 根的相對路徑，與 `room_classifier.HEAD_PATH`
    的預設同一個檔案。
    """
    values = env if env is not None else os.environ
    override = values.get("ROOM_HEAD")
    if override:
        return Path(override)
    base = root if root is not None else Path.cwd()
    return base / DEFAULT_HEAD


def _torch_present() -> bool:
    """torch 是否可匯入。

    用 `find_spec` 而非真的 import：這個函式會被 API 的狀態端點呼叫，import torch
    要數秒並吃掉數百 MB，不該發生在每次健康檢查上。
    """
    from importlib.util import find_spec

    try:
        return find_spec("torch") is not None
    except (ImportError, ValueError):
        return False


def cody_semantic_room_labeler_status(
    *,
    root: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """回報 DINOv2 房型標註層能否在本機執行。

    `available` 為 False 時房型會退回面積規則（純幾何），品質明顯下降但不會中斷
    ——呼叫端可依 `fallback` 欄位向使用者說明降級原因。
    """
    head = _head_path(root=root, env=env)
    has_head = head.is_file()
    has_torch = _torch_present()
    available = has_head and has_torch
    if available:
        reason = "cody_semantic_ready"
    elif not has_head:
        reason = "missing_room_head"
    else:
        reason = "missing_torch"
    return {
        "available": available,
        "reason": reason,
        "model_version": MODEL_VERSION,
        "head_path": str(head),
        "head_present": has_head,
        "torch_present": has_torch,
        "backbone": "dinov2_vits14",
        "backbone_cache_hint": str(BACKBONE_CACHE_HINT),
        "license": "Apache-2.0",
        "fallback": None if available else "area_rules",
    }
