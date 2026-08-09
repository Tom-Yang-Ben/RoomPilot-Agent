"""並存 MasterAgent 管線入口的煙霧測試。

只驗證新寫的接線邏輯：feature flag 解析、狀態檔序列化往返、start→get 跨
「請求」的狀態存活。``master.start()`` 只讀 layout+rules（無 LLM/RAG），所以
不需要金鑰、資料庫或網路。
"""
from __future__ import annotations

import pytest

from backend.agent.master import MasterState
from backend.server import agent_pipeline_service as svc

LAYOUT = {"rooms": [{"room_id": "living", "name": "客廳", "width_cm": 420, "depth_cm": 360}]}


def test_pipeline_enabled_flag(monkeypatch):
    monkeypatch.delenv("ROOMPILOT_AGENT_PIPELINE", raising=False)
    assert svc.pipeline_enabled() is False
    for off in ("", "0", "false", "OFF", "no"):
        monkeypatch.setenv("ROOMPILOT_AGENT_PIPELINE", off)
        assert svc.pipeline_enabled() is False
    for on in ("1", "true", "yes"):
        monkeypatch.setenv("ROOMPILOT_AGENT_PIPELINE", on)
        assert svc.pipeline_enabled() is True


def test_start_persists_and_survives_reload(tmp_path):
    runtime, project = tmp_path, tmp_path
    pause = svc.start_pipeline(runtime, project, "proj-1", LAYOUT)
    assert pause["state"] == MasterState.AWAIT_QUESTIONNAIRE
    assert (tmp_path / "agent_pipeline" / "proj-1.json").is_file()

    # 新一輪請求會從磁碟 restore()，狀態必須存活。
    reloaded = svc.get_pipeline(runtime, project, "proj-1")
    assert reloaded["state"] == MasterState.AWAIT_QUESTIONNAIRE
    assert reloaded["payload"]["rooms"][0]["room_id"] == "living"


def test_submit_before_start_raises(tmp_path):
    with pytest.raises(svc.PipelineNotStarted):
        svc.submit_pipeline(tmp_path, tmp_path, "missing", {})


def test_bad_layout_raises_value_error(tmp_path):
    with pytest.raises(ValueError):
        svc.start_pipeline(tmp_path, tmp_path, "proj-2", {"rooms": []})
