"""
demo_agent_flow.py — 模擬 Agent 呼叫 furniture_engine 的完整流程

用途:跟 Agent 核心(柏彥)對介面用的可執行範例。
執行:uv run python demo_agent_flow.py

介面規則(v0.1 提案):
- id 規則:{type}_{該類型流水號},每個類型各自從 1 開始編號
  例:sofa_1, table_1, sofa_2
- 失敗訊息詞彙表:
  「物件超出空間範圍」「與牆體穿透」「與「X」重疊」
  「找不到合法擺放位置」「找不到目標家具:{id}」
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo 根目錄，載入 backend 套件

from backend.engine.models import Room, Wall
from backend.engine.placement import place_furniture_batch
from backend.engine.adjustment import adjust_furniture
from backend.engine.schema import catalog_from_dict, placed_to_dict


def pretty(title: str, payload) -> None:
    print(f"\n===== {title} =====")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def run_adjust(scene, room, request: dict) -> dict:
    """處理一次 adjust_furniture 呼叫,target 不存在時優雅回報,不 crash"""
    target_id = request["input"]["target"]
    target = next((p for p in scene if p.id == target_id), None)

    if target is None:
        return {
            "success": False,
            "placed": None,
            "reason": f"找不到目標家具:{target_id}",
        }

    others = [p for p in scene if p.id != target.id]
    adj = adjust_furniture(room, target, others, request["input"])
    return {
        "success": adj["success"],
        "placed": placed_to_dict(adj["placed"]),
        "reason": adj["reason"],
    }


# ---------- 場景:正式版由 upgrade_to_3d / DXF 解析提供,demo 先寫死 ----------
room = Room(
    width=5, depth=4,
    walls=[Wall(0, 0, 5, 0), Wall(5, 0, 5, 4), Wall(5, 4, 0, 4), Wall(0, 4, 0, 0)],
)

# ---------- Round 1:Agent 呼叫 place_furniture ----------
request_1 = {
    "tool": "place_furniture",
    "input": {
        "items": [
            {"type": "sofa", "name": "三人沙發", "width": 2.0, "depth": 0.9},
            {"type": "table", "name": "茶几", "width": 1.0, "depth": 0.6},
        ]
    },
}
pretty("Agent -> Engine:place_furniture 請求", request_1)

# id 規則:{type}_{該類型流水號},每類型各自從 1 開始編
type_counter = Counter()
items = []
for d in request_1["input"]["items"]:
    type_counter[d["type"]] += 1
    items.append((catalog_from_dict(d), f"{d['type']}_{type_counter[d['type']]}"))

result = place_furniture_batch(room, items)
scene = result["placed"]  # 目前場景狀態(由呼叫端持有,引擎本身無狀態)

response_1 = {
    "success": len(result["failed"]) == 0,
    "placed": [placed_to_dict(p) for p in scene],
    "failed": result["failed"],
}
pretty("Engine -> Agent:place_furniture 回應", response_1)

# ---------- Round 2:adjust_furniture(move,成功案例)----------
request_2 = {
    "tool": "adjust_furniture",
    "input": {"action": "move", "target": "sofa_1", "dx": 0.5, "dy": 0},
}
pretty("Agent -> Engine:adjust_furniture 請求(move)", request_2)
response_2 = run_adjust(scene, room, request_2)
pretty("Engine -> Agent:adjust_furniture 回應", response_2)

# ---------- Round 3:失敗案例一(target id 不存在)----------
request_3 = {
    "tool": "adjust_furniture",
    "input": {"action": "move", "target": "chair_99", "dx": 0.5, "dy": 0},
}
pretty("Agent -> Engine:adjust_furniture 請求(id 不存在)", request_3)
response_3 = run_adjust(scene, room, request_3)
pretty("Engine -> Agent:adjust_furniture 回應(id 不存在)", response_3)

# ---------- Round 4:失敗案例二(移動出界,雙軸都被擋)----------
request_4 = {
    "tool": "adjust_furniture",
    "input": {"action": "move", "target": "table_1", "dx": 99, "dy": 99},
}
pretty("Agent -> Engine:adjust_furniture 請求(移動出界)", request_4)
response_4 = run_adjust(scene, room, request_4)
pretty("Engine -> Agent:adjust_furniture 回應(移動出界)", response_4)
