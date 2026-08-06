"""Master state machine：完整流程、計數器、失敗政策與可恢復上一動。"""
from pathlib import Path

from backend.agent.documents import DocKey
from backend.agent.master import MasterState

from .conftest import FakeImageGateway, build_test_master, make_png_b64


def _viewpoints() -> dict:
    stub = make_png_b64()
    return {
        "living": {"viewpoint_id": "vp-liv", "note": "從入口望向沙發", "image_b64": stub},
        "bedroom": {"viewpoint_id": "vp-bed", "note": "床側 45 度", "image_b64": stub},
    }


def test_full_happy_path(master, layout_json, questionnaire):
    pause = master.start(layout_json)
    assert pause.state == MasterState.AWAIT_QUESTIONNAIRE

    # S1–S4：需求、RAG、A/B 擺放與驗證
    pause = master.submit({"questionnaire": questionnaire})
    assert pause.state == MasterState.AWAIT_PLAN_CHOICE
    assert set(pause.payload["variants"]) == {"A", "B"}
    assert master.store.get(DocKey.variant(DocKey.SCENE, "A"))
    assert master.store.get(DocKey.variant(DocKey.VALIDATION, "B"))

    # 方案擇一＋視角 → S5a 單房色卡比對（兩組色卡）
    pause = master.submit({"variant": "A", "viewpoints": _viewpoints()})
    assert pause.state == MasterState.AWAIT_PALETTE_CHOICE
    assert len(pause.payload["images"]) == 2

    # 色卡擇一 → S5b 全房生圖
    pause = master.submit({"palette_id": "p1"})
    assert pause.state == MasterState.AWAIT_FEEDBACK
    assert {row["room_id"] for row in pause.payload["images"]} == {"living", "bedroom"}
    assert pause.payload["edit_remaining"] == 1

    # S6 改圖（僅一次）
    pause = master.submit({"feedback": "沙發改成米白色", "room_id": "living"})
    assert pause.state == MasterState.AWAIT_FEEDBACK
    assert pause.payload["edit_remaining"] == 0
    assert master.edit_used == 1

    # 第二次意見被額度擋下（計數在 Master，不在 LLM）
    pause = master.submit({"feedback": "再改深一點", "room_id": "living"})
    assert "額度已用完" in pause.message
    assert master.edit_used == 1

    # S7 設計手冊（PDF）
    pause = master.submit({"skip": True})
    assert pause.state == MasterState.DONE
    pdf_path = Path(pause.payload["pdf_path"])
    assert pdf_path.exists() and pdf_path.read_bytes()[:4] == b"%PDF"
    assert len(pause.payload["sections"]) == 8  # 新增「二、設計理念與亮點」章

    # 生圖紀錄：2 色卡 + 2 全房 + 1 改圖
    records = (master.store.get(DocKey.IMAGES) or {}).get("records") or []
    assert len(records) == 5
    stages = [row["stage"] for row in records]
    assert stages.count("palette_compare") == 2
    assert stages.count("full_render") == 2
    assert stages.count("edit") == 1


def test_undo_restores_previous_step(master, layout_json, questionnaire):
    master.start(layout_json)
    master.submit({"questionnaire": questionnaire})
    pause = master.submit({"variant": "A", "viewpoints": _viewpoints()})
    assert pause.state == MasterState.AWAIT_PALETTE_CHOICE
    assert master.store.get(DocKey.variant(DocKey.SCENE, "chosen"))

    pause = master.undo()
    assert pause.state == MasterState.AWAIT_PLAN_CHOICE
    assert master.store.get(DocKey.variant(DocKey.SCENE, "chosen")) is None

    # 恢復後可以改選另一方案
    pause = master.submit({"variant": "B", "viewpoints": _viewpoints()})
    assert pause.state == MasterState.AWAIT_PALETTE_CHOICE
    chosen = master.store.get(DocKey.variant(DocKey.SCENE, "chosen"))
    assert chosen["variant"] == "B"


def test_genpic_primary_fail_then_fallback_model(tmp_path, layout_json, questionnaire):
    gateway = FakeImageGateway(fail_primary=3)
    master = build_test_master(tmp_path, image_gateway=gateway)
    master.start(layout_json)
    master.submit({"questionnaire": questionnaire})
    pause = master.submit({"variant": "A", "viewpoints": _viewpoints()})
    assert pause.state == MasterState.AWAIT_PALETTE_CHOICE

    records = (master.store.get(DocKey.IMAGES) or {}).get("records") or []
    first = records[0]
    # 主模型 3 次失敗 → 提示原因 → 改用 nano banana 2 成功
    assert first["model"] == "google/nano-banana-2"
    failure_lines = [n for n in first["notices"] if "失敗" in n]
    assert len(failure_lines) >= 3
    assert any("改用備援模型" in n for n in first["notices"])
    # 之後的請求主模型已恢復（配額模擬耗盡）
    assert records[1]["model"] == "google/nano-banana"


def test_genpic_total_failure_pauses_then_skip_continues(
    tmp_path, layout_json, questionnaire
):
    gateway = FakeImageGateway(fail_primary=999, fail_fallback=999)
    master = build_test_master(tmp_path, image_gateway=gateway)
    master.start(layout_json)
    master.submit({"questionnaire": questionnaire})

    pause = master.submit({"variant": "A", "viewpoints": _viewpoints()})
    assert pause.state == MasterState.AWAIT_RENDER_RETRY
    assert pause.payload["stage"] == "palette"
    assert len(pause.payload["failure_notices"]) >= 6  # 兩個模型各 3 次

    pause = master.submit({"skip": True})  # 略過色卡比對 → 全房生圖也失敗
    assert pause.state == MasterState.AWAIT_RENDER_RETRY
    assert pause.payload["stage"] == "full"

    pause = master.submit({"skip": True})  # 略過全房生圖
    assert pause.state == MasterState.AWAIT_FEEDBACK

    pause = master.submit({"skip": True})  # 沒有生圖仍可輸出手冊
    assert pause.state == MasterState.DONE
    assert Path(pause.payload["pdf_path"]).exists()


def test_repair_loop_caps_at_configured_rounds(tmp_path):
    layout = {"rooms": [{"room_id": "tiny", "name": "儲物間", "width_cm": 100, "depth_cm": 100}]}
    questionnaire = {
        "styles": ["日式無印"],
        "rooms": [{"room_id": "tiny", "furniture_needs": ["雙人床"]}],
    }
    master = build_test_master(tmp_path)
    master.start(layout)
    pause = master.submit({"questionnaire": questionnaire})

    # 床永遠放不下：修復迴圈跑滿 3 次後帶著未解決旗標交給使用者裁決
    assert pause.state == MasterState.AWAIT_PLAN_CHOICE
    assert master.repair_rounds_used["A"] == master.config.repair_max_rounds == 3
    variant_a = pause.payload["variants"]["A"]
    assert variant_a["passed"] is False and variant_a["unresolved"] is True


def test_invalid_input_does_not_consume_a_step(master, layout_json, questionnaire):
    master.start(layout_json)
    master.submit({"questionnaire": questionnaire})
    checkpoints_before = len(master._checkpoints)

    pause = master.submit({"variant": "Z"})  # 不合法輸入
    assert "A 或 B" in pause.message
    assert pause.state == MasterState.AWAIT_PLAN_CHOICE
    assert len(master._checkpoints) == checkpoints_before  # 不算一動

    pause = master.submit({"variant": "A", "viewpoints": _viewpoints()})
    assert pause.state == MasterState.AWAIT_PALETTE_CHOICE
