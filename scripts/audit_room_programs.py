#!/usr/bin/env python
"""五張「房型放什麼」清單對帳——2026-07-31 P0 量尺的工具化。

同一個房型在專案裡有五個互相矛盾的答案（實測害過人）：

  1. `backend/engine/room_strategy/README.md` v1 —— 人讀正式規格（SSOT）
  2. `backend/agent/knowledge.py` ROOM_MINIMUM_FAMILIES —— 機器 SSOT
  3. `backend/server/scene_service.py` SPACE_DEFAULTS —— 後端預設
  4. `scene_layout2d.js` recommendedFurnitureForRoom —— 前端 2D 種子
  5. `scene_v2.js` QUESTIONNAIRE_ROOM_FURNITURE_PROGRAMS —— 問卷預設

本工具逐房並排五表、以族系（family_of）折疊後標出「誰偏離了規格」。
改任何一張表之前先跑一次，改完再跑一次，避免『只改一張、誤判修好』。

    .venv/bin/python scripts/audit_room_programs.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.agent.knowledge import (  # noqa: E402
    ROOM_MINIMUM_FAMILIES,
    family_of,
    normalize_room_type,
)
from backend.server.scene_service import SPACE_DEFAULTS  # noqa: E402


def fold(types) -> set[str]:
    return {family_of(t) for t in types if t}


def parse_v1_spec() -> dict[str, set[str]]:
    """從 room_strategy README 的 12 房型表抽出「最少自動配置」欄的類型碼。"""
    text = (REPO_ROOT / "backend/engine/room_strategy/README.md").read_text(encoding="utf-8")
    rows: dict[str, set[str]] = {}
    for line in text.splitlines():
        m = re.match(r"^\|\s*\d+\s*\|\s*[^|]+\|\s*`(\w+)`[^|]*\|([^|]*)\|", line)
        if not m:
            continue
        code, minimum = m.group(1), m.group(2)
        if "空白" in minimum:
            rows[code] = set()
        else:
            rows[code] = set(re.findall(r"`([a-z0-9-]+)`", minimum))
    return rows


def parse_frontend_2d() -> dict[str, set[str]]:
    text = (REPO_ROOT / "backend/server/static/scene_layout2d.js").read_text(encoding="utf-8")
    body = text.split("const recommendations = {", 1)[1].split("};", 1)[0]
    rows: dict[str, set[str]] = {}
    # 每房一行；非貪婪跨行匹配會在第一個 ] 停下，只抓到第一件家具
    #（首版 bug，害前端差距被灌水），改為逐行解析。
    for line in body.splitlines():
        m = re.match(r"\s*(\w+):\s*\[(.*)\],?\s*$", line)
        if m:
            rows[m.group(1)] = set(re.findall(r'\["([a-z0-9-]+)"', m.group(2)))
    return rows


def parse_frontend_questionnaire() -> dict[str, set[str]]:
    text = (REPO_ROOT / "backend/server/static/scene_v2.js").read_text(encoding="utf-8")
    body = text.split("const QUESTIONNAIRE_ROOM_FURNITURE_PROGRAMS = Object.freeze({", 1)[1]
    body = body.split("\n});", 1)[0]
    rows: dict[str, set[str]] = {}
    for m in re.finditer(r"(\w+):\s*\{\s*defaults:\s*\[([^\]]*)\]", body):
        rows[m.group(1)] = set(re.findall(r'"([a-z0-9-]+)"', m.group(2)))
    return rows


def main() -> int:
    spec = parse_v1_spec()
    fe2d = parse_frontend_2d()
    feq = parse_frontend_questionnaire()

    rooms = sorted(set(spec) | set(ROOM_MINIMUM_FAMILIES))
    mismatch_rooms = 0
    print("以 v1 正式規格為基準，逐房比對（皆折疊為擺位族系）：")
    for room in rooms:
        want = fold(spec.get(room, set()))
        got = {
            "knowledge": fold(ROOM_MINIMUM_FAMILIES.get(room, ())),
            "SPACE_DEFAULTS": fold(SPACE_DEFAULTS.get(room, [])),
            "前端2D": fold(fe2d.get(room, set())),
            "問卷": fold(feq.get(room, set())),
        }
        # 前端表用的別名房型（如 circulation/storage）另行對照
        if room not in fe2d:
            for alias, target in (("circulation", "hallway"), ("studio", None)):
                if normalize_room_type(alias) == room and alias in fe2d:
                    got["前端2D"] = fold(fe2d[alias])
        diffs = {
            name: (want - value, value - want)
            for name, value in got.items()
            if (want - value) or (value - want)
        }
        flag = "❌" if diffs else "✅"
        if diffs:
            mismatch_rooms += 1
        print(f"\n{flag} {room:14} 規格最少 = {sorted(want) or '（空白）'}")
        for name, (missing, extra) in diffs.items():
            parts = []
            if missing:
                parts.append(f"缺 {sorted(missing)}")
            if extra:
                parts.append(f"多 {sorted(extra)}")
            print(f"     {name:14} {'；'.join(parts)}")

    print(f"\n總結：{len(rooms)} 房型中 {mismatch_rooms} 個至少有一張表偏離規格。")
    print("提醒：主臥床頭櫃 ×2／次臥 ×1 的數量差異任何一張機器表都表達不了（knowledge 待升級）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
