"""Schedule Service：只用結構化 ProductivityRecord 與 TaskDependency。

排程公式：
    施工日 = ceil(工程量 / (日產能 × 工班數))
    總工日 = 準備日 + 施工日 + 等待日
再依 task_dependencies（同房間 finish-to-start + lag）推開始/完成日。

demo_mode=False 時不得使用 is_synthetic 工率；缺工率 →
status=productivity_data_missing，不虛構工期。
"""
from __future__ import annotations

import math
from uuid import uuid4

from ..contracts import (
    ProjectSnapshot,
    QuantityResult,
    RetrievalResult,
    ScheduleResult,
    ScheduleTask,
)
from ..knowledge_repo import JsonKnowledgeRepository


class ScheduleService:
    def __init__(
        self,
        knowledge: JsonKnowledgeRepository,
        demo_mode: bool = False,
    ) -> None:
        self.knowledge = knowledge
        self.demo_mode = demo_mode

    def plan(
        self,
        snapshot: ProjectSnapshot,
        quantities: QuantityResult,
        retrieval: RetrievalResult,
    ) -> ScheduleResult:
        del snapshot, quantities
        productivity_by_code = {}
        for item in self.knowledge.productivity_records():
            if item.get("is_synthetic") and not self.demo_mode:
                continue
            if item.get("daily_productivity") is None:
                continue
            productivity_by_code[item["work_item_code"]] = item
        dependencies = self.knowledge.task_dependencies()

        tasks: list[ScheduleTask] = []
        task_by_room_code: dict[tuple[str, str], ScheduleTask] = {}

        for room in retrieval.rooms:
            for work_item in room.work_items:
                record = productivity_by_code.get(work_item.work_item_code)
                if record:
                    daily = float(record["daily_productivity"])
                    crew = int(record.get("crew_count", 1))
                    construction_days = float(
                        math.ceil(work_item.quantity / (daily * max(crew, 1)))
                    )
                    preparation_days = float(record.get("preparation_days", 0))
                    waiting_days = float(record.get("waiting_days", 0))
                    total_days = preparation_days + construction_days + waiting_days
                    status = "estimated"
                    source = record.get("source")
                    confidence = record.get("confidence", "low")
                else:
                    daily = None
                    crew = None
                    construction_days = None
                    preparation_days = 0
                    waiting_days = 0
                    total_days = None
                    status = "productivity_data_missing"
                    source = None
                    confidence = "low"

                task = ScheduleTask(
                    task_id=f"task_{uuid4().hex[:10]}",
                    room_id=room.room_id,
                    work_item_code=work_item.work_item_code,
                    name=work_item.name,
                    quantity=work_item.quantity,
                    unit=work_item.unit,
                    daily_productivity=daily,
                    crew_count=crew,
                    preparation_days=preparation_days,
                    construction_days=construction_days,
                    waiting_days=waiting_days,
                    total_days=total_days,
                    predecessor_task_ids=[],
                    start_day=None,
                    finish_day=None,
                    source=source,
                    confidence=confidence,
                    status=status,
                )
                tasks.append(task)
                task_by_room_code[(room.room_id, work_item.work_item_code)] = task

        # 把 knowledge dependency code 轉成同房間 task id。
        lag_by_task_pair: dict[tuple[str, str], float] = {}
        for dep in dependencies:
            for room_id, code in list(task_by_room_code):
                if code != dep["task_code"]:
                    continue
                task = task_by_room_code[(room_id, code)]
                predecessor = task_by_room_code.get(
                    (room_id, dep["predecessor_code"])
                )
                if predecessor:
                    task.predecessor_task_ids.append(predecessor.task_id)
                    lag_by_task_pair[(task.task_id, predecessor.task_id)] = float(
                        dep.get("lag_days", 0)
                    )

        by_id = {task.task_id: task for task in tasks}
        unresolved = {task.task_id for task in tasks}
        while unresolved:
            progressed = False
            for task_id in list(unresolved):
                task = by_id[task_id]
                predecessors = [by_id[item] for item in task.predecessor_task_ids]
                if any(item.task_id in unresolved for item in predecessors):
                    continue
                if task.total_days is None or any(
                    item.finish_day is None for item in predecessors
                ):
                    # 自身缺工率、或前置工作排不出完成日：不虛構日期。
                    task.start_day = None
                    task.finish_day = None
                    unresolved.remove(task_id)
                    progressed = True
                    continue
                start = 1.0
                if predecessors:
                    start = max(
                        float(item.finish_day)
                        + lag_by_task_pair.get((task.task_id, item.task_id), 0)
                        + 1
                        for item in predecessors
                    )
                task.start_day = start
                task.finish_day = round(start + task.total_days - 1, 2)
                unresolved.remove(task_id)
                progressed = True
            if not progressed:
                # 防止循環依賴或缺資料造成無限迴圈。
                for task_id in unresolved:
                    task = by_id[task_id]
                    if task.total_days is not None:
                        task.status = "productivity_data_missing"
                    task.start_day = None
                    task.finish_day = None
                break

        known_finishes = [
            task.finish_day for task in tasks if task.finish_day is not None
        ]
        unknown_count = sum(1 for task in tasks if task.total_days is None)
        uses_demo = any(
            task.source and "synthetic" in task.source.lower() for task in tasks
        )
        if uses_demo:
            disclaimer = (
                "目前啟用 DEMO_MODE，工期使用合成示範工率，只供流程與排程畫面展示；"
                "實際工期需依材料交期、社區時段、現場條件與工班確認。"
            )
        else:
            disclaimer = (
                "工期依版本化工率、工班數、等待時間及前置工作估算；"
                "缺少工率的項目顯示資料不足，需由設計師及工班修正。"
            )
        return ScheduleResult(
            tasks=tasks,
            estimated_total_days=max(known_finishes) if known_finishes else None,
            unknown_duration_count=unknown_count,
            disclaimer=disclaimer,
        )
