"""並存的 MasterAgent 管線入口（feature flag: ``ROOMPILOT_AGENT_PIPELINE``）。

不改動 ``scene_service`` 的正式 step 6。這是與現行「LLM 選件 + engine 擺放 +
``resolve_placements`` 修復」並存、可隨時回退的第二條路徑，讓 ``backend.agent``
的 Master + 四個 sub-agent（Furniture 擺放 / Validation 驗證 / Gen_Pic / Report）
能端到端被真正呼叫，用來驗證兩條路徑的一致性。

狀態序列化到 ``runtime_dir/agent_pipeline/<project_id>.json``，刻意不放進 project
的 workflow blob：master 狀態含生圖 base64，會撐爆 2MB workflow 上限，也會被
``project_store`` 的顯示字串壓縮邏輯改壞。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock

from ..agent import MasterAgent, build_gateway, build_master
from ..agent.tools.base import ToolError

# ponytail: 資料轉接與輸出對帳「未做」。agent 管線（SceneDoc/documents）與
# scene_service（site_payload/engine objects）是不同 document model；尚未實作
# (1) 把正式 step6 的輸入轉接餵進 agent 管線，(2) 兩條路徑輸出的擺放/驗證結果
# 對帳比對。目前入口只讓 agent 管線能被獨立呼叫，尚不能宣稱與 step6 等價。
# 接上「用 agent 管線重現 step6 並逐件對帳」時補這兩層。

# ponytail: 單一全域鎖序列化所有專案的管線操作；示範/驗證入口足夠，
# 真要並發吞吐再換成 per-project 鎖。
_LOCK = Lock()

_DISABLED_VALUES = {"", "0", "false", "no", "off"}


class PipelineNotStarted(RuntimeError):
    """該專案尚未 ``start()`` 過管線。"""

    def __init__(self, project_id: str) -> None:
        super().__init__(f"專案 {project_id} 尚未啟動 Agent 管線，請先呼叫 start。")


def pipeline_enabled() -> bool:
    return os.getenv("ROOMPILOT_AGENT_PIPELINE", "").strip().lower() not in _DISABLED_VALUES


def pipeline_status() -> dict:
    return {
        "enabled": pipeline_enabled(),
        "gateway_configured": build_gateway() is not None,
        "flag": "ROOMPILOT_AGENT_PIPELINE",
    }


def _state_path(runtime_dir, project_id: str) -> Path:
    safe = "".join(ch for ch in str(project_id) if ch.isalnum() or ch in "-_")
    if not safe:
        raise ValueError("project_id 不合法")
    directory = Path(runtime_dir) / "agent_pipeline"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{safe}.json"


def _build(project_dir) -> MasterAgent:
    # sub-agent 無狀態，每次請求重建；狀態一律靠 restore()。retriever 用正式
    # SpatialRagRetriever（lazy import，DB 不可用時 furniture 階段依契約暫停）。
    return build_master(gateway=build_gateway(), project_dir=project_dir)


def _load(runtime_dir, project_dir, project_id: str) -> MasterAgent | None:
    path = _state_path(runtime_dir, project_id)
    if not path.is_file():
        return None
    master = _build(project_dir)
    master.restore(json.loads(path.read_text(encoding="utf-8")))
    return master


def _save(runtime_dir, project_id: str, master: MasterAgent) -> None:
    path = _state_path(runtime_dir, project_id)
    path.write_text(json.dumps(master.to_dict(), ensure_ascii=False), encoding="utf-8")


def start_pipeline(runtime_dir, project_dir, project_id, layout_json, rules_json=None) -> dict:
    with _LOCK:
        master = _build(project_dir)
        try:
            pause = master.start(layout_json, rules_json)
        except ToolError as exc:  # 例如 layout_json 缺 rooms —— 轉可讀 422
            raise ValueError(exc.reason) from exc
        _save(runtime_dir, project_id, master)
        return pause.to_dict()


def submit_pipeline(runtime_dir, project_dir, project_id, payload) -> dict:
    with _LOCK:
        master = _load(runtime_dir, project_dir, project_id)
        if master is None:
            raise PipelineNotStarted(project_id)
        pause = master.submit(payload or {})
        _save(runtime_dir, project_id, master)
        return pause.to_dict()


def undo_pipeline(runtime_dir, project_dir, project_id) -> dict:
    with _LOCK:
        master = _load(runtime_dir, project_dir, project_id)
        if master is None:
            raise PipelineNotStarted(project_id)
        restored = master.undo()
        _save(runtime_dir, project_id, master)
        return {"undone": restored is not None, **master.pause.to_dict()}


def get_pipeline(runtime_dir, project_dir, project_id) -> dict:
    with _LOCK:
        master = _load(runtime_dir, project_dir, project_id)
        if master is None:
            raise PipelineNotStarted(project_id)
        return master.pause.to_dict()
