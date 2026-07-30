"""房型語意層可用性回報（DINOv2 路徑）。

2026-07-30 CubiCasa 血統整批移除前，這支測的是一整套資產管理：200MB v5 權重的
GitHub Release 下載鏈與 SHA-256 校驗、token 換 S3 簽名、`cubicasa/room/*_mask.npz`
遮罩快取的欄位／尺寸驗證、`infer_cubicasa.py` 的 subprocess 呼叫。那 15 支測試
連同它們守護的機制一併消失（權重、快取、推論腳本都不存在了）。

DINOv2 路徑的判定簡單得多——只有「線性頭在不在」與「torch 裝了沒」兩個條件，
所以本檔的職責縮回一件事：**狀態回報必須誠實**。這件事仍然要緊，因為 available
為 False 時房型會靜默退回面積規則（own_eval 72 房 90.3% 掉回幾何猜測的水準），
前端要靠這裡的 `reason` 與 `fallback` 才說得出為什麼降級。
"""
from __future__ import annotations

from backend.floorplan.vision.cody_semantic import (
    DEFAULT_HEAD,
    MODEL_VERSION,
    cody_semantic_room_labeler_status,
)


def _head(tmp_path):
    """在 tmp_path 下造出線性頭。內容不重要——狀態檢查只看檔案存在與否，
    真正的載入驗證在 room_classifier._load()（那裡會讀 npz 欄位）。"""
    target = tmp_path / DEFAULT_HEAD
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"fake-linear-head")
    return target


def test_reports_missing_head_when_asset_absent(tmp_path) -> None:
    status = cody_semantic_room_labeler_status(root=tmp_path, env={})

    assert status["available"] is False
    assert status["reason"] == "missing_room_head"
    assert status["head_present"] is False
    assert status["fallback"] == "area_rules"


def test_reports_ready_when_head_and_torch_are_both_present(tmp_path) -> None:
    """torch 是本 repo 的實際安裝狀態——有裝才會走 ready 這條分支。"""
    _head(tmp_path)
    status = cody_semantic_room_labeler_status(root=tmp_path, env={})

    if not status["torch_present"]:
        # 沒裝 torch 的環境（例如只做前端的隊員）應誠實回報缺 torch 而非 ready。
        assert status["available"] is False
        assert status["reason"] == "missing_torch"
        assert status["fallback"] == "area_rules"
        return

    assert status["available"] is True
    assert status["reason"] == "cody_semantic_ready"
    assert status["fallback"] is None


def test_head_path_reflects_the_root_it_was_asked_about(tmp_path) -> None:
    """`root` 是測試注入點；產品走 cwd。回報的路徑必須是真的去看的那個。"""
    head = _head(tmp_path)
    status = cody_semantic_room_labeler_status(root=tmp_path, env={})

    assert status["head_path"] == str(head)
    assert status["head_present"] is True


def test_room_head_env_override_is_honoured(tmp_path) -> None:
    """`ROOM_HEAD` 是 A/B 驗收的入口，狀態檢查必須跟著它走，否則會回報
    「資產齊備」卻實際載入另一個檔——A/B 結果無從解釋。"""
    custom = tmp_path / "ab" / "variant_head.npz"
    custom.parent.mkdir(parents=True)
    custom.write_bytes(b"variant")

    status = cody_semantic_room_labeler_status(
        root=tmp_path, env={"ROOM_HEAD": str(custom)}
    )

    assert status["head_path"] == str(custom)
    assert status["head_present"] is True


def test_env_override_pointing_at_nothing_is_reported_as_missing(tmp_path) -> None:
    """覆寫到不存在的路徑不得因為預設位置有檔就回報 ready。"""
    _head(tmp_path)  # 預設位置有檔，但覆寫指向別處

    status = cody_semantic_room_labeler_status(
        root=tmp_path, env={"ROOM_HEAD": str(tmp_path / "nope.npz")}
    )

    assert status["available"] is False
    assert status["reason"] == "missing_room_head"
    assert status["head_present"] is False


def test_status_declares_the_apache_licensed_backbone(tmp_path) -> None:
    """授權欄位是這次改動的重點：CubiCasa5k 權重 CC BY-NC 禁商用，DINOv2 是
    Apache 2.0 可商用。下游合規檢查讀這個欄位，不得回退成 CubiCasa 的描述。"""
    status = cody_semantic_room_labeler_status(root=tmp_path, env={})

    assert status["license"] == "Apache-2.0"
    assert status["backbone"] == "dinov2_vits14"
    assert status["model_version"] == MODEL_VERSION
    assert "cubicasa" not in str(status).lower()
